"""Tests for protocol assertion helpers.

Tests the trajectory normalization and assertion functions.
"""

import pytest
from tests.helpers.protocol_assertions import (
    normalize_dspy_trajectory,
    normalize_trajectory,
    assert_code_blocks_present,
    assert_bounded_views,
    assert_tool_called,
)


class TestTrajectoryNormalization:
    """Test trajectory normalization functions."""

    def test_normalize_dspy_trajectory(self):
        """DSPy trajectory (list of dicts) is normalized correctly."""
        dspy_trajectory = [
            {"code": "x = 1 + 1", "output": "2"},
            {"code": "print(x)", "output": "2"},
        ]

        normalized = normalize_dspy_trajectory(dspy_trajectory)

        assert len(normalized) == 2
        assert normalized[0].code_blocks[0].code == "x = 1 + 1"
        assert normalized[0].code_blocks[0].result.stdout == "2"
        assert normalized[1].code_blocks[0].code == "print(x)"
        assert normalized[1].code_blocks[0].result.stdout == "2"

    def test_normalize_dspy_trajectory_empty(self):
        """Empty DSPy trajectory is handled."""
        normalized = normalize_dspy_trajectory([])
        assert normalized == []

    def test_normalize_dspy_trajectory_no_output(self):
        """DSPy trajectory with no output is handled."""
        dspy_trajectory = [
            {"code": "x = 1", "output": ""},
        ]

        normalized = normalize_dspy_trajectory(dspy_trajectory)
        assert len(normalized) == 1
        # Empty output should result in None result
        assert normalized[0].code_blocks[0].result is None

    def test_normalize_trajectory_auto_detects_format(self):
        """normalize_trajectory auto-detects DSPy format."""
        dspy_trajectory = [
            {"code": "x = 1", "output": "ok"},
        ]

        normalized = normalize_trajectory(dspy_trajectory)
        assert len(normalized) == 1
        assert normalized[0].code_blocks[0].code == "x = 1"


class TestAssertionsWithDSPyTrajectory:
    """Test protocol assertions work with DSPy trajectories."""

    def test_assert_code_blocks_present_with_dspy(self):
        """assert_code_blocks_present works with DSPy trajectory."""
        trajectory = [
            {"code": "x = 1", "output": "ok"},
            {"code": "y = 2", "output": "ok"},
        ]

        # Should not raise
        assert_code_blocks_present(trajectory, min_blocks=2)

    def test_assert_code_blocks_present_fails_with_too_few(self):
        """assert_code_blocks_present fails with too few blocks."""
        trajectory = [
            {"code": "x = 1", "output": "ok"},
        ]

        with pytest.raises(AssertionError, match="Expected at least 2 code blocks"):
            assert_code_blocks_present(trajectory, min_blocks=2)

    def test_assert_bounded_views_with_dspy(self):
        """assert_bounded_views works with DSPy trajectory."""
        trajectory = [
            {"code": "x = 1", "output": "ok"},
        ]

        # Should not raise (output is small)
        assert_bounded_views(trajectory, max_output_chars=100)

    def test_assert_bounded_views_fails_with_large_output(self):
        """assert_bounded_views fails with large output."""
        large_output = "x" * 20000
        trajectory = [
            {"code": "x = 1", "output": large_output},
        ]

        with pytest.raises(AssertionError, match="REPL output too large"):
            assert_bounded_views(trajectory, max_output_chars=10000)

    def test_assert_tool_called_with_dspy(self):
        """assert_tool_called works with DSPy trajectory."""
        trajectory = [
            {"code": "result = search_entity('Activity')", "output": "[...]"},
            {"code": "info = describe_entity('prov:Activity')", "output": "{...}"},
        ]

        # Should not raise
        assert_tool_called(trajectory, "search_entity", at_least=1)
        assert_tool_called(trajectory, "describe_entity", at_least=1)

    def test_assert_tool_called_fails_when_not_found(self):
        """assert_tool_called fails when tool not called."""
        trajectory = [
            {"code": "x = 1 + 1", "output": "2"},
        ]

        with pytest.raises(AssertionError, match="Expected.*to be called at least 1 times"):
            assert_tool_called(trajectory, "search_entity", at_least=1)
