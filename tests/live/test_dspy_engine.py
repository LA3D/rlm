"""Live tests for DSPy RLM engine.

These tests require ANTHROPIC_API_KEY and make actual API calls.
"""

import pytest
import os
from pathlib import Path
from rlm_runtime.engine import run_dspy_rlm, DSPyRLMResult


# Skip all tests if API key not available
pytestmark = pytest.mark.skipif(
    not os.environ.get("ANTHROPIC_API_KEY"),
    reason="ANTHROPIC_API_KEY not set",
)


@pytest.fixture
def prov_ontology():
    """Path to PROV ontology for testing."""
    onto_path = Path(__file__).parents[2] / "ontology" / "prov.ttl"
    if not onto_path.exists():
        pytest.skip(f"Test ontology not found: {onto_path}")
    return onto_path


class TestDSPyRLMExecution:
    """Test DSPy RLM engine execution."""

    def test_run_returns_structured_result(self, prov_ontology):
        """run_dspy_rlm returns DSPyRLMResult with non-empty answer."""
        result = run_dspy_rlm(
            query="What is the Activity class?",
            ontology_path=prov_ontology,
            max_iterations=4,
            max_llm_calls=8,
            verbose=False,
        )

        # Check result structure
        assert isinstance(result, DSPyRLMResult)
        assert isinstance(result.answer, str)
        assert len(result.answer) > 0
        assert isinstance(result.trajectory, list)
        assert result.iteration_count >= 0
        assert isinstance(result.converged, bool)

    def test_result_has_evidence(self, prov_ontology):
        """Result includes evidence dictionary."""
        result = run_dspy_rlm(
            query="What is the Activity class?",
            ontology_path=prov_ontology,
            max_iterations=4,
            max_llm_calls=8,
        )

        assert isinstance(result.evidence, dict)

    def test_trajectory_captured(self, prov_ontology):
        """Trajectory includes execution steps."""
        result = run_dspy_rlm(
            query="What properties does Activity have?",
            ontology_path=prov_ontology,
            max_iterations=4,
            max_llm_calls=8,
        )

        # Should have at least one step
        assert len(result.trajectory) > 0
        # Each step should be a dict
        for step in result.trajectory:
            assert isinstance(step, dict)

    def test_api_key_required(self, prov_ontology):
        """Execution fails without API key."""
        # Temporarily remove API key
        old_key = os.environ.pop("ANTHROPIC_API_KEY", None)
        try:
            with pytest.raises(ValueError, match="ANTHROPIC_API_KEY"):
                run_dspy_rlm(
                    query="test",
                    ontology_path=prov_ontology,
                    max_iterations=1,
                )
        finally:
            if old_key:
                os.environ["ANTHROPIC_API_KEY"] = old_key

    def test_invalid_ontology_path_fails(self):
        """Execution fails with non-existent ontology."""
        with pytest.raises(FileNotFoundError):
            run_dspy_rlm(
                query="test",
                ontology_path="/nonexistent/ontology.ttl",
                max_iterations=1,
            )


class TestDSPyRLMParameters:
    """Test parameter handling."""

    def test_custom_max_iterations(self, prov_ontology):
        """Custom max_iterations parameter works."""
        result = run_dspy_rlm(
            query="What is Activity?",
            ontology_path=prov_ontology,
            max_iterations=2,  # Very low limit
            max_llm_calls=4,
        )

        # Should still return a result
        assert isinstance(result, DSPyRLMResult)
        assert len(result.answer) > 0

    def test_verbose_parameter(self, prov_ontology):
        """Verbose parameter doesn't break execution."""
        # With verbose=True, should print to console but still work
        result = run_dspy_rlm(
            query="What is Activity?",
            ontology_path=prov_ontology,
            max_iterations=2,
            max_llm_calls=4,
            verbose=True,
        )

        assert isinstance(result, DSPyRLMResult)
        assert len(result.answer) > 0
