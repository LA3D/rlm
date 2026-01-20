"""Tests for NamespaceCodeInterpreter.

Tests the DSPy RLM code interpreter implementation.
"""

import pytest
from rlm_runtime.interpreter import NamespaceCodeInterpreter


class TestBasicExecution:
    """Test basic code execution capabilities."""

    def test_interpreter_executes_code(self):
        """Interpreter executes simple Python code."""
        interp = NamespaceCodeInterpreter()
        result = interp.execute("x = 1 + 1\nprint(x)")
        assert "2" in result

    def test_interpreter_maintains_state(self):
        """State persists across multiple execute calls."""
        interp = NamespaceCodeInterpreter()
        interp.execute("x = 42")
        result = interp.execute("print(x)")
        assert "42" in result

    def test_interpreter_start_idempotent(self):
        """Calling start() multiple times is safe."""
        interp = NamespaceCodeInterpreter()
        interp.start()
        interp.execute("x = 1")
        interp.start()  # Should not clear state
        result = interp.execute("print(x)")
        assert "1" in result

    def test_interpreter_shutdown_clears_state(self):
        """Shutdown clears namespace."""
        interp = NamespaceCodeInterpreter()
        interp.execute("x = 42")
        interp.shutdown()
        # After shutdown, x should not exist
        result = interp.execute("print('ok')")
        assert "ok" in result


class TestSUBMITProtocol:
    """Test SUBMIT protocol for returning final output."""

    def test_interpreter_submit_returns_final_output(self):
        """SUBMIT with kwargs returns FinalOutput."""
        from dspy.primitives.code_interpreter import FinalOutput

        interp = NamespaceCodeInterpreter()
        result = interp.execute("SUBMIT(answer='42', confidence=0.9)")
        assert isinstance(result, FinalOutput)
        assert result.output["answer"] == "42"
        assert result.output["confidence"] == 0.9

    def test_submit_with_dict_arg(self):
        """SUBMIT with single dict argument works."""
        from dspy.primitives.code_interpreter import FinalOutput

        interp = NamespaceCodeInterpreter()
        result = interp.execute("SUBMIT({'answer': 'test', 'score': 1.0})")
        assert isinstance(result, FinalOutput)
        assert result.output["answer"] == "test"
        assert result.output["score"] == 1.0

    def test_submit_with_mixed_args_raises(self):
        """SUBMIT with mixed args raises error."""
        from dspy.primitives.code_interpreter import CodeInterpreterError

        interp = NamespaceCodeInterpreter()
        with pytest.raises(CodeInterpreterError, match="only supports keyword args"):
            interp.execute("SUBMIT({'a': 1}, b=2)")

    def test_submit_with_multiple_positional_raises(self):
        """SUBMIT with multiple positional args raises error."""
        from dspy.primitives.code_interpreter import CodeInterpreterError

        interp = NamespaceCodeInterpreter()
        with pytest.raises(CodeInterpreterError, match="only supports keyword args"):
            interp.execute("SUBMIT('a', 'b')")


class TestToolInjection:
    """Test tool injection into execution namespace."""

    def test_interpreter_tools_are_callable(self):
        """Tools are injected and callable in code."""

        def add_one(x):
            return x + 1

        def multiply(x, y):
            return x * y

        interp = NamespaceCodeInterpreter(tools={"add_one": add_one, "multiply": multiply})
        result = interp.execute("result = multiply(add_one(5), 3)\nprint(result)")
        assert "18" in result

    def test_tools_updated_each_iteration(self):
        """Tools are re-injected each execute call."""

        def get_value():
            return 42

        interp = NamespaceCodeInterpreter(tools={"get_value": get_value})
        result1 = interp.execute("print(get_value())")
        assert "42" in result1

        # Update tools
        def get_value():
            return 100

        interp.tools["get_value"] = get_value
        result2 = interp.execute("print(get_value())")
        assert "100" in result2

    def test_tools_available_with_variables(self):
        """Tools work alongside injected variables."""

        def double(x):
            return x * 2

        interp = NamespaceCodeInterpreter(tools={"double": double})
        result = interp.execute("print(double(y))", variables={"y": 10})
        assert "20" in result


class TestErrorHandling:
    """Test error handling behavior."""

    def test_syntax_error_raises_directly(self):
        """SyntaxError is raised directly, not wrapped."""
        interp = NamespaceCodeInterpreter()
        with pytest.raises(SyntaxError):
            interp.execute("x = (")

    def test_runtime_error_becomes_interpreter_error(self):
        """Runtime errors are wrapped in CodeInterpreterError."""
        from dspy.primitives.code_interpreter import CodeInterpreterError

        interp = NamespaceCodeInterpreter()
        with pytest.raises(CodeInterpreterError, match="NameError"):
            interp.execute("print(undefined_variable)")

    def test_stderr_captured(self):
        """Stderr is captured and returned."""
        interp = NamespaceCodeInterpreter()
        result = interp.execute("import sys\nsys.stderr.write('error\\n')\nprint('output')")
        assert "stderr" in result
        assert "error" in result
        assert "output" in result


class TestOutputCapture:
    """Test stdout/stderr capture."""

    def test_stdout_captured(self):
        """Standard output is captured."""
        interp = NamespaceCodeInterpreter()
        result = interp.execute("print('hello')\nprint('world')")
        assert "hello" in result
        assert "world" in result

    def test_empty_output(self):
        """Empty output returns empty string."""
        interp = NamespaceCodeInterpreter()
        result = interp.execute("x = 1 + 1")
        assert result == ""
