"""Test RLM with dataset memory integration using protocol assertions.

This test suite verifies RLM can use memory operations correctly:
- Add facts to memory and query them
- Combine ontology exploration with memory storage
- Persist memory across multiple RLM runs
- Use work graphs for intermediate results

All tests verify RLM protocol invariants.
"""

import pytest
from pathlib import Path

from rlm.core import rlm_run
from rlm.dataset import setup_dataset_context
from rlm.ontology import setup_ontology_context
from tests.helpers.protocol_assertions import (
    assert_code_blocks_present,
    assert_converged_properly,
    assert_bounded_views,
    assert_tool_called,
)


@pytest.fixture
def prov_ontology_path():
    """Path to PROV ontology for testing."""
    return Path('ontology/prov.ttl')


@pytest.mark.live
class TestRLMWithMemory:
    """Test RLM with dataset memory operations."""

    def test_basic_memory_operations(self):
        """Test RLM can add to and query memory with protocol compliance."""
        ns = {}
        setup_dataset_context(ns)

        context = """
        You have access to memory operations:
        - mem_add(subject, predicate, object, source='agent', reason=None)
        - mem_query(sparql, limit=100)
        - mem_describe(uri, limit=20)

        Store facts you discover in memory.
        """

        query = "Remember that Alice is 30 years old and Bob is 25 years old. Then query memory to confirm what you stored."

        answer, iterations, ns = rlm_run(
            query=query,
            context=context,
            ns=ns,
            max_iters=5
        )

        # Protocol invariants
        assert_code_blocks_present(iterations, min_blocks=1)
        assert_converged_properly(answer, iterations)
        assert_bounded_views(iterations)

        # Memory-specific assertions
        assert_tool_called(iterations, "mem_add", at_least=2)
        assert_tool_called(iterations, "mem_query", at_least=1)

        # Verify memory state
        ds_meta = ns['ds_meta']

        # More specific check: verify actual triples exist
        mem_triples = list(ds_meta.mem.triples((None, None, None)))
        assert len(mem_triples) >= 2, (
            f"Should have stored at least 2 facts about Alice and Bob, "
            f"found {len(mem_triples)} triples"
        )

        # Check provenance
        assert len(ds_meta.prov) > 0, "Should have provenance records"

        # Verify answer mentions the facts
        assert 'Alice' in answer or 'alice' in answer.lower()
        assert 'Bob' in answer or 'bob' in answer.lower()

    def test_ontology_memory_integration(self, prov_ontology_path):
        """Test RLM using ontology + memory together."""
        if not prov_ontology_path.exists():
            pytest.skip("PROV ontology not available")

        ns = {}
        setup_dataset_context(ns)
        setup_ontology_context(str(prov_ontology_path), ns, name='prov')

        context = """
        You have access to:
        1. The PROV ontology in 'prov_meta' with classes and properties
        2. Memory operations: mem_add(), mem_query(), mem_describe()

        Use the ontology to understand PROV concepts, then store examples in memory.
        """

        query = """
        Find the Activity class in the PROV ontology.
        Store its comment in memory using the pattern:
          subject: http://www.w3.org/ns/prov#Activity
          predicate: http://example.org/hasNote
          object: <the comment text>

        Then query memory to verify it was stored.
        """

        answer, iterations, ns = rlm_run(
            query=query,
            context=context,
            ns=ns,
            max_iters=8
        )

        # Protocol invariants
        assert_code_blocks_present(iterations, min_blocks=2)
        assert_converged_properly(answer, iterations)
        assert_bounded_views(iterations)

        # Tool usage
        assert_tool_called(iterations, "search_by_label|describe_entity", at_least=1)
        assert_tool_called(iterations, "mem_add", at_least=1)
        assert_tool_called(iterations, "mem_query", at_least=1)

        # Verify ontology was loaded
        prov_meta = ns['prov_meta']
        assert len(prov_meta.classes) > 0, "Should have loaded ontology classes"

        # Verify memory was used
        ds_meta = ns['ds_meta']
        mem_triples = list(ds_meta.mem.triples((None, None, None)))
        assert len(mem_triples) > 0, (
            f"Should have stored facts from ontology, found {len(mem_triples)}"
        )
        assert len(ds_meta.prov) > 0, "Should have provenance"

    def test_memory_persistence_across_runs(self):
        """Test that memory persists across multiple RLM runs in same namespace."""
        ns = {}
        setup_dataset_context(ns)

        context = "You have memory operations: mem_add(), mem_query()"

        # First run: store facts
        query1 = "Store these facts: Alice knows Bob, Bob knows Charlie."
        answer1, iters1, ns = rlm_run(query1, context, ns=ns, max_iters=5)

        # Protocol invariants for first run
        assert_code_blocks_present(iters1, min_blocks=1)
        assert_converged_properly(answer1, iters1)
        assert_tool_called(iters1, "mem_add", at_least=2)

        mem_size_after_first = len(list(ns['ds_meta'].mem.triples((None, None, None))))
        assert mem_size_after_first > 0, "First run should add to memory"

        # Second run: use stored facts
        query2 = "Query memory to find who knows who. List all relationships."
        answer2, iters2, ns = rlm_run(query2, context, ns=ns, max_iters=5)

        # Protocol invariants for second run
        assert_code_blocks_present(iters2, min_blocks=1)
        assert_converged_properly(answer2, iters2)
        assert_tool_called(iters2, "mem_query", at_least=1)

        # Memory should persist
        mem_size_after_second = len(list(ns['ds_meta'].mem.triples((None, None, None))))
        assert mem_size_after_second >= mem_size_after_first, (
            f"Memory should persist: had {mem_size_after_first} triples, "
            f"now have {mem_size_after_second}"
        )

        # Provenance should track both runs
        assert len(ns['ds_meta'].prov) > 0, "Should have provenance from both runs"

        # Answer should contain the facts
        assert 'Alice' in answer2 or 'alice' in answer2.lower()
        assert 'Bob' in answer2 or 'bob' in answer2.lower()

    def test_work_graph_workflow(self):
        """Test RLM using work graphs for intermediate results."""
        ns = {}
        setup_dataset_context(ns)

        context = """
        You have access to:
        - mem_add(), mem_query() for permanent memory
        - work_create(task_id) returns (uri, graph) for temporary work
        - work_to_mem(task_id, reason=...) to promote validated results
        - work_cleanup(task_id) to remove scratch graphs

        Use work graphs for intermediate analysis before adding to memory.
        """

        query = """
        Create a work graph called 'analysis'.
        Add some test triples to it.
        Then promote only the validated ones to memory.
        Clean up the work graph when done.
        """

        answer, iterations, ns = rlm_run(
            query=query,
            context=context,
            ns=ns,
            max_iters=8
        )

        # Protocol invariants
        assert_code_blocks_present(iterations, min_blocks=3)
        assert_converged_properly(answer, iterations)
        assert_bounded_views(iterations)

        # Tool usage
        assert_tool_called(iterations, "work_create", at_least=1)
        assert_tool_called(iterations, "work_cleanup|work_to_mem", at_least=1)

        ds_meta = ns['ds_meta']

        # Work graphs should be cleaned up
        assert len(ds_meta.work_graphs) == 0, (
            f"Work graphs should be cleaned up, found {len(ds_meta.work_graphs)}"
        )

        # But memory should have the promoted facts
        mem_triples = list(ds_meta.mem.triples((None, None, None)))
        assert len(mem_triples) > 0, (
            f"Should have promoted facts to memory, found {len(mem_triples)}"
        )

        # Provenance should show operations
        assert len(ds_meta.prov) > 0, "Should have provenance events"
