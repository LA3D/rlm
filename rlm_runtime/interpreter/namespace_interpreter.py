"""NamespaceCodeInterpreter for DSPy RLM.

Host-Python interpreter (non-sandboxed) that executes code in a persistent namespace
with tool injection and SUBMIT protocol support.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from io import StringIO
import sys
import time
from typing import Any, Callable


class _SubmitCalled(Exception):
    """Internal exception to signal SUBMIT was called with final output."""

    def __init__(self, payload: dict[str, Any]):
        self.payload = payload


@dataclass
class NamespaceCodeInterpreter:
    """Host-Python interpreter for DSPy RLM (non-sandboxed).

    State persists across execute() calls (DSPy iterations).
    Tools are injected as globals each iteration by DSPy.

    Thread Safety:
        NOT thread-safe. Each RLM instance reuses the same interpreter with shared
        _globals dict. For concurrent runs, create separate RLM instances per thread.
        See: docs/design/dspy-rlm-architecture-review.md

    Attributes:
        tools: Dictionary of tool functions to inject into execution namespace
        output_fields: Optional list of output field definitions for DSPy
        _tools_registered: Flag used by DSPy to track tool registration state
    """

    tools: dict[str, Callable[..., Any]] = field(default_factory=dict)
    output_fields: list[dict] | None = None
    _tools_registered: bool = False  # DSPy may toggle this attribute

    def __post_init__(self):
        self._started = False
        self._globals: dict[str, Any] = {}

    def start(self) -> None:
        """Initialize the interpreter namespace."""
        if self._started:
            return
        self._globals = {}
        self._started = True

    def shutdown(self) -> None:
        """Clear the interpreter namespace and reset state."""
        self._globals.clear()
        self._started = False

    def _instrument_tools_if_needed(self, tools: dict[str, Any]) -> dict[str, Any]:
        """Wrap tools with callback instrumentation if DSPy callbacks are active.

        Args:
            tools: Dictionary of tool functions

        Returns:
            Dictionary of instrumented tools (or original tools if no callbacks)
        """
        import dspy
        import uuid
        from functools import wraps

        # Check if callbacks are active
        callbacks = dspy.settings.get('callbacks', [])
        if not callbacks:
            return tools

        # Wrap each tool
        instrumented = {}
        for name, tool_func in tools.items():
            # Skip non-callable tools (SUBMIT, etc.)
            if not callable(tool_func):
                instrumented[name] = tool_func
                continue

            @wraps(tool_func)
            def make_instrumented_tool(func, tool_name):
                def instrumented_tool(*args, **kwargs):
                    # Generate unique call ID
                    call_id = f"tool-{uuid.uuid4().hex[:8]}"

                    # Prepare inputs dict
                    inputs = {
                        'args': args,
                        'kwargs': kwargs,
                    }

                    # Create mock tool instance for callback API
                    class ToolInstance:
                        __name__ = tool_name

                    instance = ToolInstance()

                    # Emit on_tool_start
                    for callback in callbacks:
                        if hasattr(callback, 'on_tool_start'):
                            try:
                                callback.on_tool_start(call_id, instance, inputs)
                            except Exception as e:
                                print(f"Warning: Callback on_tool_start failed: {e}")

                    # Execute tool
                    exception = None
                    outputs = None
                    try:
                        outputs = func(*args, **kwargs)
                    except Exception as e:
                        exception = e

                    # Emit on_tool_end
                    for callback in callbacks:
                        if hasattr(callback, 'on_tool_end'):
                            try:
                                callback.on_tool_end(call_id, {'result': outputs}, exception)
                            except Exception as e2:
                                print(f"Warning: Callback on_tool_end failed: {e2}")

                    # Re-raise exception if tool failed
                    if exception:
                        raise exception

                    return outputs
                return instrumented_tool

            instrumented[name] = make_instrumented_tool(tool_func, name)

        return instrumented

    def _validate_and_clean_code(self, code: str) -> str:
        """Validate and clean code before execution.

        Detects common syntax errors and attempts to fix them:
        - Triple backticks inside code blocks (markdown formatting)
        - Other common formatting issues

        Args:
            code: Raw code string from LLM

        Returns:
            Cleaned code string

        Raises:
            SyntaxError: If code has unfixable syntax errors
        """
        from dspy.primitives.code_interpreter import CodeInterpreterError

        # Check for triple backticks inside code (common LLM error)
        lines = code.split('\n')
        cleaned_lines = []
        inside_string = False
        quote_char = None

        for line in lines:
            # Skip lines that are just markdown code fences
            stripped = line.strip()
            if stripped in ('```python', '```'):
                continue

            # Detect if line starts a multiline string
            for i, char in enumerate(line):
                if char in ('"', "'") and (i == 0 or line[i-1] != '\\'):
                    if not inside_string:
                        inside_string = True
                        quote_char = char
                    elif char == quote_char:
                        inside_string = False
                        quote_char = None

            # If not inside string and line has triple backticks, it's likely an error
            if not inside_string and '```' in line:
                # This is likely a markdown code fence accidentally included
                continue

            cleaned_lines.append(line)

        cleaned_code = '\n'.join(cleaned_lines)

        # Try to compile to catch syntax errors early with better error message
        try:
            compile(cleaned_code, "<dspy-repl>", "exec")
        except SyntaxError as e:
            # Provide helpful error message
            raise CodeInterpreterError(
                f"Syntax error in code at line {e.lineno}: {e.msg}\n"
                f"Common issues:\n"
                f"  - Check for extra ```python or ``` markers (markdown formatting)\n"
                f"  - Verify all strings are properly closed\n"
                f"  - Check for proper indentation"
            ) from e

        return cleaned_code

    def execute(self, code: str, variables: dict[str, Any] | None = None) -> Any:
        """Execute code in the persistent namespace.

        Args:
            code: Python code to execute
            variables: Optional variables to inject into namespace

        Returns:
            - FinalOutput if SUBMIT was called
            - stdout content if no SUBMIT
            - Combined stderr/stdout if errors occurred

        Raises:
            SyntaxError: If code has syntax errors (raised directly)
            CodeInterpreterError: If runtime errors occur (wrapped)
        """
        from dspy.primitives.code_interpreter import CodeInterpreterError, FinalOutput

        if not self._started:
            self.start()

        if variables:
            self._globals.update(variables)

        # Inject tools (with callback instrumentation if available)
        instrumented_tools = self._instrument_tools_if_needed(self.tools)
        self._globals.update(instrumented_tools)

        # Define SUBMIT function with helpful error messages
        def SUBMIT(*args, **kwargs):
            """Submit final output. Use keyword arguments matching output fields.

            Correct usage:
                SUBMIT(answer="Your answer", sparql="SELECT ...", evidence={"key": "value"})
                SUBMIT({"answer": "...", "sparql": "...", "evidence": {...}})

            Wrong usage (will error):
                SUBMIT(answer, sparql, evidence)  # Positional args - use keyword args!
            """
            if args:
                if len(args) == 1 and isinstance(args[0], dict) and not kwargs:
                    raise _SubmitCalled(args[0])
                raise CodeInterpreterError(
                    "SUBMIT requires keyword arguments. "
                    "Use: SUBMIT(answer='...', sparql='...', evidence={...}) "
                    "NOT: SUBMIT(answer, sparql, evidence)"
                )
            raise _SubmitCalled(dict(kwargs))

        self._globals["SUBMIT"] = SUBMIT

        # Pre-validate code for common syntax issues
        code = self._validate_and_clean_code(code)

        # Capture stdout/stderr
        stdout_capture = StringIO()
        stderr_capture = StringIO()
        old_stdout, old_stderr = sys.stdout, sys.stderr
        start = time.time()
        try:
            sys.stdout, sys.stderr = stdout_capture, stderr_capture
            exec(compile(code, "<dspy-repl>", "exec"), self._globals)
        except _SubmitCalled as e:
            return FinalOutput(e.payload)
        except SyntaxError:
            raise
        except Exception as e:
            raise CodeInterpreterError(f"{type(e).__name__}: {e}") from e
        finally:
            sys.stdout, sys.stderr = old_stdout, old_stderr

        stdout = stdout_capture.getvalue()
        stderr = stderr_capture.getvalue().strip()
        if stderr:
            return f"[stderr]\n{stderr}\n\n[stdout]\n{stdout}"
        return stdout
