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

        # Inject tools
        self._globals.update(self.tools)

        # Define SUBMIT function
        def SUBMIT(*args, **kwargs):
            if args:
                if len(args) == 1 and isinstance(args[0], dict) and not kwargs:
                    raise _SubmitCalled(args[0])
                raise CodeInterpreterError("SUBMIT only supports keyword args or a single dict argument.")
            raise _SubmitCalled(dict(kwargs))

        self._globals["SUBMIT"] = SUBMIT

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
