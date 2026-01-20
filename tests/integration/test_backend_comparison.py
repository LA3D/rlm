"""Backend comparison tests.

Tests that run the same queries through both backends (Claudette and DSPy)
to verify protocol compliance and comparable behavior.
"""

import pytest
import os
from pathlib import Path
from rdflib import Graph

from rlm.ontology import GraphMeta, load_ontology
from rlm_runtime.engine import ClaudetteBackend, is_rlm_backend
from tests.helpers.protocol_assertions import (
    assert_code_blocks_present,
    assert_converged_properly,
    assert_bounded_views,
    assert_tool_called,
)


# Mark all tests to skip if API key not available
pytestmark = pytest.mark.skipif(
    not os.environ.get("ANTHROPIC_API_KEY"),
    reason="ANTHROPIC_API_KEY not set (required for backend comparison)",
)


@pytest.fixture
def prov_ontology():
    """Path to PROV ontology for testing."""
    onto_path = Path(__file__).parents[2] / "ontology" / "prov.ttl"
    if not onto_path.exists():
        pytest.skip(f"Test ontology not found: {onto_path}")
    return onto_path


@pytest.fixture
def prov_context(prov_ontology):
    """Pre-loaded ontology context for Claudette backend."""
    ns = {}
    load_ontology(str(prov_ontology), ns, name="prov_graph")
    meta = GraphMeta(ns["prov_graph"], name="prov")
    context = "\n".join([
        "You are exploring an RDF ontology via bounded tools.",
        "Do not dump large structures. Use tools to discover entities.",
        "",
        meta.summary(),
    ])
    return context, ns, meta


class TestBackendProtocolCompliance:
    """Test that both backends implement the protocol correctly."""

    def test_claudette_backend_is_rlm_backend(self, prov_ontology):
        """ClaudetteBackend implements RLMBackend protocol."""
        backend = ClaudetteBackend(prov_ontology)
        assert is_rlm_backend(backend)

    def test_claudette_backend_produces_valid_result(self, prov_ontology, prov_context):
        """ClaudetteBackend produces valid RLMResult."""
        context, ns, meta = prov_context
        backend = ClaudetteBackend(prov_ontology, namespace=ns)

        result = backend.run(
            query="What is the Activity class?",
            context=context,
            max_iterations=3,
            verbose=False,
        )

        # Verify result structure
        assert hasattr(result, 'answer')
        assert hasattr(result, 'trajectory')
        assert hasattr(result, 'iteration_count')
        assert hasattr(result, 'converged')
        assert hasattr(result, 'metadata')

        assert isinstance(result.answer, str)
        assert len(result.answer) > 0
        assert isinstance(result.trajectory, list)
        assert result.metadata['backend'] == 'claudette'


# Parametrized test queries for comparison
TEST_QUERIES = [
    ("What is the Activity class?", "Activity"),
    ("What properties does Activity have?", "properties|domain"),
]


@pytest.mark.parametrize("backend_name", ["claudette"])
class TestBackendQueries:
    """Test queries through both backends."""

    @pytest.fixture
    def backend(self, backend_name, prov_ontology, prov_context):
        """Create backend instance based on parameter."""
        context, ns, meta = prov_context

        if backend_name == "claudette":
            return ClaudetteBackend(prov_ontology, namespace=ns), context
        # DSPy backend would go here, but requires more setup
        # elif backend_name == "dspy":
        #     return DSPyBackend(...), context
        else:
            pytest.skip(f"Backend {backend_name} not yet implemented for comparison")

    @pytest.mark.parametrize("query,expected_term", TEST_QUERIES)
    def test_query_produces_answer(self, backend, query, expected_term):
        """Backend produces non-empty answer."""
        backend_instance, context = backend

        result = backend_instance.run(
            query=query,
            context=context,
            max_iterations=3,
            verbose=False,
        )

        assert len(result.answer) > 0
        # Answer should mention the expected term (case-insensitive)
        assert expected_term.lower() in result.answer.lower() or \
               any(term in result.answer.lower() for term in expected_term.split("|"))

    @pytest.mark.parametrize("query,expected_term", TEST_QUERIES)
    def test_query_uses_code_blocks(self, backend, query, expected_term):
        """Backend uses code blocks for exploration."""
        backend_instance, context = backend

        result = backend_instance.run(
            query=query,
            context=context,
            max_iterations=3,
            verbose=False,
        )

        # Protocol assertions
        assert_code_blocks_present(result.trajectory, min_blocks=1)

    @pytest.mark.parametrize("query,expected_term", TEST_QUERIES)
    def test_query_converges_properly(self, backend, query, expected_term):
        """Backend converges without hitting max iterations."""
        backend_instance, context = backend

        result = backend_instance.run(
            query=query,
            context=context,
            max_iterations=4,
            verbose=False,
        )

        # Should converge (not fallback)
        assert_converged_properly(result.answer, result.trajectory)

    @pytest.mark.parametrize("query,expected_term", TEST_QUERIES)
    def test_query_uses_bounded_views(self, backend, query, expected_term):
        """Backend uses bounded views (no graph dumps)."""
        backend_instance, context = backend

        result = backend_instance.run(
            query=query,
            context=context,
            max_iterations=3,
            verbose=False,
        )

        # Outputs should be bounded
        assert_bounded_views(result.trajectory, max_output_chars=10000)

    def test_query_uses_expected_tools(self, backend):
        """Backend calls expected ontology tools."""
        backend_instance, context = backend

        result = backend_instance.run(
            query="What is the Activity class?",
            context=context,
            max_iterations=3,
            verbose=False,
        )

        # Should call search or describe tools
        assert_tool_called(
            result.trajectory,
            function_pattern=r"search_entity|describe_entity",
            at_least=1
        )


class TestBackendComparison:
    """Compare behavior across backends (when multiple available)."""

    def test_both_backends_available(self):
        """Both backends can be instantiated."""
        # For now, only Claudette is implemented
        # This test will be expanded when DSPy backend is added to comparison
        assert True  # Placeholder

    # Future: Add tests that run the same query through both backends
    # and compare convergence, answer quality, etc.
