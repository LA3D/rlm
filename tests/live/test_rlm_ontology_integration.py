"""Comprehensive RLM + Ontology integration test with protocol assertions.

This test verifies the full Stage 1 workflow:
1. Load ontology with meta-graph scaffolding
2. Build sense document
3. Use RLM to answer complex questions using bounded views
4. Progressive disclosure in action

All tests verify RLM protocol invariants (code blocks, convergence, bounded views).
"""

import pytest
from pathlib import Path

from rlm.core import rlm_run
from rlm.ontology import setup_ontology_context, build_sense
from tests.helpers.protocol_assertions import (
    assert_code_blocks_present,
    assert_converged_properly,
    assert_bounded_views,
    assert_grounded_answer,
    assert_tool_called,
)


@pytest.fixture
def prov_ontology_path():
    """Path to PROV ontology for testing."""
    return Path('ontology/prov.ttl')


@pytest.fixture
def sio_ontology_path():
    """Path to SIO ontology for testing."""
    return Path('ontology/sio/sio-release.owl')


@pytest.mark.live
class TestRLMOntologyIntegration:
    """Test RLM with ontology integration using protocol assertions."""

    def test_simple_exploration_with_progressive_disclosure(self, prov_ontology_path):
        """Test simple ontology exploration uses REPL for progressive disclosure."""
        ns = {}
        setup_ontology_context(str(prov_ontology_path), ns, name='prov')

        # Context is just the summary - not the full graph!
        context = ns['prov_meta'].summary()

        query = """What is the Activity class in the PROV ontology?
        Use search_by_label and describe_entity to explore."""

        answer, iterations, ns = rlm_run(
            query,
            context,
            ns=ns,
            max_iters=5
        )

        # Protocol invariants
        assert_code_blocks_present(iterations, min_blocks=1)
        assert_converged_properly(answer, iterations)
        assert_bounded_views(iterations, max_output_chars=10000)

        # Tool usage
        assert_tool_called(iterations, "search_by_label|describe_entity", at_least=1)

        # Groundedness
        assert_grounded_answer(answer, iterations, min_score=0.3)

        # Basic sanity checks
        assert 'Activity' in answer or 'activity' in answer.lower()
        assert len(iterations) > 0
        assert len(iterations) <= 5

    def test_complex_query_with_sense_document(self, prov_ontology_path):
        """Test RLM can handle complex queries with sense documents."""
        ns = {}
        build_sense(str(prov_ontology_path), name='prov_sense', ns=ns)

        # Context is the sense document summary
        context = ns['prov_sense'].summary

        query = """Based on the PROV ontology sense document, what are the key patterns
        for modeling provenance? Specifically, explain the reification pattern and
        provide a SPARQL query example."""

        answer, iterations, ns = rlm_run(
            query,
            context,
            ns=ns,
            max_iters=5
        )

        # Protocol invariants
        assert_code_blocks_present(iterations, min_blocks=1)
        assert_converged_properly(answer, iterations)
        assert_bounded_views(iterations)

        # Groundedness
        assert_grounded_answer(answer, iterations, min_score=0.2)

        # Content checks
        assert len(answer) > 100  # Should have substantial answer
        assert len(iterations) > 0

    def test_comparing_ontologies(self, prov_ontology_path, sio_ontology_path):
        """Test RLM can compare multiple ontologies."""
        if not sio_ontology_path.exists():
            pytest.skip("SIO ontology not available")

        ns = {}
        # Build sense for PROV
        build_sense(str(prov_ontology_path), name='prov_sense', ns=ns)

        # Build sense for SIO
        build_sense(str(sio_ontology_path), name='sio_sense', ns=ns)

        # Context is both sense documents
        context = {
            'prov': ns['prov_sense'].summary,
            'sio': ns['sio_sense'].summary
        }

        query = """Compare the PROV and SIO ontologies. What are the key differences
        in their domains, structure, and modeling approaches?"""

        answer, iterations, ns = rlm_run(
            query,
            context,
            ns=ns,
            max_iters=5
        )

        # Protocol invariants
        assert_code_blocks_present(iterations, min_blocks=1)
        assert_converged_properly(answer, iterations)
        assert_bounded_views(iterations)

        # Content checks - should mention both ontologies
        assert 'PROV' in answer or 'prov' in answer.lower()
        assert 'SIO' in answer or 'sio' in answer.lower()

    def test_progressive_disclosure_with_hierarchy_navigation(self, prov_ontology_path):
        """Test progressive disclosure: start small, explore as needed."""
        ns = {}
        setup_ontology_context(str(prov_ontology_path), ns, name='prov')

        # Start with minimal context - just stats
        context = f"""PROV Ontology: {len(ns['prov_meta'].classes)} classes, {len(ns['prov_meta'].properties)} properties
        Available tools: search_by_label, describe_entity, graph_stats"""

        query = """Find all classes related to 'influence' in the PROV ontology
        and explain their relationships."""

        answer, iterations, ns = rlm_run(
            query,
            context,
            ns=ns,
            max_iters=5
        )

        # Protocol invariants
        assert_code_blocks_present(iterations, min_blocks=1)
        assert_converged_properly(answer, iterations)
        assert_bounded_views(iterations)

        # Progressive disclosure verification
        assert_tool_called(iterations, "search_by_label|describe_entity", at_least=1)

        # Verify exploration happened across multiple iterations
        code_blocks_per_iter = [len(it.code_blocks) for it in iterations if it.code_blocks]
        assert sum(code_blocks_per_iter) >= 2, (
            "Progressive disclosure requires multiple exploration steps"
        )

        # Content checks
        assert 'influence' in answer.lower()

    def test_uses_repl_not_direct_graph_access(self, prov_ontology_path):
        """Verify RLM uses REPL tools (not direct graph dumps)."""
        ns = {}
        setup_ontology_context(str(prov_ontology_path), ns, name='prov')

        context = ns['prov_meta'].summary()
        query = "List 3 classes in the PROV ontology"

        answer, iterations, ns = rlm_run(
            query,
            context,
            ns=ns,
            max_iters=3
        )

        # Protocol invariants
        assert_code_blocks_present(iterations, min_blocks=1)
        assert_converged_properly(answer, iterations)
        assert_bounded_views(iterations)

        # Verify bounded views - no iteration should dump entire graph
        for iteration in iterations:
            for cb in iteration.code_blocks:
                if cb.result and cb.result.stdout:
                    # REPL output should be bounded
                    assert len(cb.result.stdout) < 10000, (
                        "REPL output too large - suggests full graph dump"
                    )

        # Verify tools were used
        assert_tool_called(iterations, "search_by_label|describe_entity|graph_stats", at_least=1)

    def test_convergence_metrics(self, prov_ontology_path):
        """Test that RLM converges efficiently (not just brute force)."""
        ns = {}
        setup_ontology_context(str(prov_ontology_path), ns, name='prov')

        context = ns['prov_meta'].summary()
        query = "What is prov:Activity?"

        answer, iterations, ns = rlm_run(
            query,
            context,
            ns=ns,
            max_iters=5
        )

        # Protocol invariants
        assert_code_blocks_present(iterations, min_blocks=1)
        assert_converged_properly(answer, iterations)

        # Efficiency check - should converge in reasonable iterations
        assert len(iterations) <= 5, (
            f"RLM took {len(iterations)} iterations for simple query. "
            f"This suggests inefficient exploration."
        )

        # Groundedness
        assert_grounded_answer(answer, iterations, min_score=0.3)
