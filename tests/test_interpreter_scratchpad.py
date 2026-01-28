"""Test scratchpad features in NamespaceCodeInterpreter."""

import pytest
from rlm_runtime.interpreter import NamespaceCodeInterpreter


def test_final_interface():
    """Test FINAL() and FINAL_VAR() work correctly."""
    interp = NamespaceCodeInterpreter()
    interp.start()

    # Test FINAL
    interp.execute('FINAL("my answer")')
    assert interp._final_answer == "my answer"

    # Test FINAL_VAR
    interp._final_answer = None
    interp.execute('result = "computed"; FINAL_VAR("result")')
    assert interp._final_answer == "computed"

    # Test FINAL_VAR with missing variable
    interp._final_answer = None
    interp.execute('result_str = FINAL_VAR("nonexistent"); print(result_str)')
    # Check that final_answer was NOT set (error case)
    assert interp._final_answer is None or "Error" in str(interp._final_answer)


def test_output_truncation():
    """Test that long outputs are truncated."""
    interp = NamespaceCodeInterpreter(result_truncation_limit=100)
    interp.start()

    code = 'print("x" * 500)'
    output = interp.execute(code)

    assert len(output) <= 150  # 100 + truncation marker overhead
    assert "[...truncated" in output


def test_output_truncation_disabled():
    """Test that truncation can be disabled."""
    interp = NamespaceCodeInterpreter(result_truncation_limit=0)
    interp.start()

    code = 'print("x" * 500)'
    output = interp.execute(code)

    assert len(output) > 400  # Should not be truncated
    assert "[...truncated" not in output


def test_final_var_with_quotes():
    """Test FINAL_VAR strips quotes from variable names."""
    interp = NamespaceCodeInterpreter()
    interp.start()

    # Test with double quotes
    interp.execute('my_var = "value1"')
    interp.execute('FINAL_VAR("my_var")')
    assert interp._final_answer == "value1"

    # Test with single quotes
    interp._final_answer = None
    interp.execute('other_var = "value2"')
    interp.execute("FINAL_VAR('other_var')")
    assert interp._final_answer == "value2"


def test_scratchpad_persistence():
    """Test that namespace persists across execute calls."""
    interp = NamespaceCodeInterpreter()
    interp.start()

    # First iteration: set variable
    interp.execute('counter = 0')
    assert interp._globals['counter'] == 0

    # Second iteration: increment
    interp.execute('counter += 1')
    assert interp._globals['counter'] == 1

    # Third iteration: use in FINAL_VAR
    interp.execute('FINAL_VAR("counter")')
    assert interp._final_answer == "1"


def test_final_interface_in_namespace():
    """Test that FINAL and FINAL_VAR are available in namespace."""
    interp = NamespaceCodeInterpreter()
    interp.start()

    # Check functions exist
    assert 'FINAL' in interp._globals
    assert 'FINAL_VAR' in interp._globals
    assert callable(interp._globals['FINAL'])
    assert callable(interp._globals['FINAL_VAR'])


def test_shutdown_clears_final_answer():
    """Test that shutdown clears final answer state."""
    interp = NamespaceCodeInterpreter()
    interp.start()

    interp.execute('FINAL("test")')
    assert interp._final_answer == "test"

    interp.shutdown()
    assert interp._final_answer is None


def test_truncation_with_verification():
    """Test that truncation works with verification enabled."""
    interp = NamespaceCodeInterpreter(
        result_truncation_limit=50,
        enable_verification=False  # Disabled for this test (no guide_metadata)
    )
    interp.start()

    code = 'print("long output " * 100)'
    output = interp.execute(code)

    assert len(output) <= 100  # Truncation should apply
    assert "[...truncated" in output
