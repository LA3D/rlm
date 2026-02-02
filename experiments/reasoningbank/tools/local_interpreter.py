"""Local Python interpreter that bypasses Deno sandbox.

Executes code directly in host Python process with persistent namespace.
This avoids the DSPy Deno/Pyodide sandbox corruption issues where tools
become undefined after certain operations.
"""

import sys
import traceback
from io import StringIO
from typing import Any, Callable

from dspy.primitives.code_interpreter import FinalOutput, CodeInterpreterError


class _SubmitCalled(Exception):
    """Internal exception to signal SUBMIT was called."""
    def __init__(self, output: dict):
        self.output = output


class LocalPythonInterpreter:
    """Execute Python code directly in host process.

    Unlike DSPy's PythonInterpreter which uses Deno/Pyodide WASM sandbox,
    this runs code via exec() in the host Python. Benefits:
    - Persistent namespace (tools don't disappear)
    - Faster execution (no WASM overhead)
    - No sandbox corruption issues

    Trade-off: No security sandbox (acceptable for controlled experiments).
    """

    def __init__(
        self,
        tools: dict[str, Callable] | None = None,
        output_fields: list[dict] | None = None,
        **kwargs  # Accept and ignore other PythonInterpreter args
    ):
        """Initialize interpreter.

        Args:
            tools: Dict mapping tool names to callable functions
            output_fields: Output field definitions for SUBMIT signature
            **kwargs: Ignored (compatibility with PythonInterpreter)
        """
        self.tools = dict(tools) if tools else {}
        self.output_fields = output_fields or []
        self.namespace: dict[str, Any] = {}
        self._setup_namespace()

    def _setup_namespace(self):
        """Initialize namespace with builtins and tools."""
        # Start with builtins
        self.namespace = {
            '__builtins__': __builtins__,
            'print': print,  # Explicit for clarity
        }

        # Add common imports
        import json
        import re
        self.namespace['json'] = json
        self.namespace['re'] = re

        # Add tools
        for name, fn in self.tools.items():
            self.namespace[name] = self._wrap_tool(name, fn)

        # Add SUBMIT function
        self.namespace['SUBMIT'] = self._make_submit()
        # Expose FinalOutput class (some code checks for it)
        self.namespace['FinalOutput'] = FinalOutput

    def _wrap_tool(self, name: str, fn: Callable) -> Callable:
        """Wrap tool to handle both positional and keyword args."""
        def wrapped(*args, **kwargs):
            try:
                return fn(*args, **kwargs)
            except Exception as e:
                return {'error': str(e), 'tool': name}
        wrapped.__name__ = name
        wrapped.__doc__ = fn.__doc__
        return wrapped

    def _make_submit(self) -> Callable:
        """Create SUBMIT function that raises internal exception."""
        field_names = [f['name'] for f in self.output_fields] if self.output_fields else ['sparql', 'answer']

        def submit(*args, **kwargs):
            """Submit final output. Use positional or keyword args."""
            output = {}

            # Handle positional args
            for i, arg in enumerate(args):
                if i < len(field_names):
                    output[field_names[i]] = arg

            # Handle keyword args (override positional)
            output.update(kwargs)

            # Handle single dict argument
            if len(args) == 1 and isinstance(args[0], dict) and not kwargs:
                output = args[0]

            # Raise internal exception to exit exec()
            raise _SubmitCalled(output)

        return submit

    def execute(self, code: str, variables: dict[str, Any] | None = None) -> Any:
        """Execute code and return output.

        Args:
            code: Python code to execute
            variables: Variables to inject into namespace

        Returns:
            Captured stdout string, or FinalOutput if SUBMIT was called
        """
        # Inject variables
        if variables:
            self.namespace.update(variables)

        # Capture stdout
        old_stdout = sys.stdout
        sys.stdout = captured = StringIO()

        try:
            exec(code, self.namespace)
            output = captured.getvalue()
            return output if output else None

        except _SubmitCalled as sc:
            # SUBMIT was called - return FinalOutput
            return FinalOutput(sc.output)

        except SyntaxError as e:
            raise SyntaxError(f"Invalid Python syntax: {e}")

        except Exception as e:
            # Return error info but don't crash
            tb = traceback.format_exc()
            error_output = captured.getvalue()
            error_msg = f"{error_output}\nError: {type(e).__name__}: {e}\n{tb}"
            return error_msg

        finally:
            sys.stdout = old_stdout

    def __call__(self, code: str, variables: dict[str, Any] | None = None) -> Any:
        """Execute code (callable interface)."""
        return self.execute(code, variables)

    def start(self) -> None:
        """No-op for compatibility."""
        pass

    def shutdown(self) -> None:
        """Clear namespace."""
        self.namespace.clear()
        self._setup_namespace()

    def __enter__(self):
        return self

    def __exit__(self, *_):
        self.shutdown()


def create_local_interpreter(tools: dict[str, Callable] | None = None,
                              output_fields: list[dict] | None = None) -> LocalPythonInterpreter:
    """Factory function to create LocalPythonInterpreter.

    Args:
        tools: Dict mapping tool names to callable functions
        output_fields: Output field definitions for SUBMIT

    Returns:
        Configured LocalPythonInterpreter instance
    """
    return LocalPythonInterpreter(tools=tools, output_fields=output_fields)
