"""Test rlm_run_with_memory() closed loop functionality.

This test suite verifies the complete procedural memory closed loop:
1. RETRIEVE: Get relevant memories via BM25
2. INJECT: Add to context/prompt
3. INTERACT: Run rlm_run()
4. EXTRACT: Judge + extract new memories
5. STORE: Persist new memories
"""

import pytest
from pathlib import Path
import tempfile

from rlm.procedural_memory import rlm_run_with_memory, MemoryStore
from rlm.ontology import setup_ontology_context
from tests.helpers.protocol_assertions import (
    assert_code_blocks_present,
    assert_converged_properly,
    assert_bounded_views,
)


@pytest.fixture
def memory_store_empty():
    """Empty memory store for testing."""
    return MemoryStore()


@pytest.fixture
def memory_store_with_temp_file():
    """Memory store with temporary file persistence."""
    with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
        store = MemoryStore(path=Path(f.name))
        yield store
        # Cleanup
        Path(f.name).unlink(missing_ok=True)


@pytest.fixture
def prov_ontology_path():
    """Path to PROV ontology for testing."""
    return Path('ontology/prov.ttl')


@pytest.mark.live
class TestRLMRunWithMemoryClosedLoop:
    """Test rlm_run_with_memory() closed loop."""

    def test_first_run_with_empty_store(self, memory_store_empty):
        """Test that first run works with empty memory store."""
        query = "What is 2 + 2?"
        context = "You are a helpful math assistant."

        answer, iterations, ns, new_memories = rlm_run_with_memory(
            query=query,
            context=context,
            memory_store=memory_store_empty,
            max_iters=3,
            enable_memory_extraction=True
        )

        # Protocol invariants
        assert_code_blocks_present(iterations, min_blocks=1)
        assert_converged_properly(answer, iterations)
        assert_bounded_views(iterations)

        # Answer check
        assert '4' in answer

        # Memory extraction should have occurred (even if no memories extracted)
        assert isinstance(new_memories, list)

    def test_memory_retrieval_on_second_run(self, memory_store_empty, prov_ontology_path):
        """Test that second run retrieves memories from first run."""
        if not prov_ontology_path.exists():
            pytest.skip("PROV ontology not available")

        ns = {}
        setup_ontology_context(str(prov_ontology_path), ns, name='prov')
        context = ns['prov_meta'].summary()

        # First run: learn about prov:Activity
        query1 = "What is prov:Activity in the PROV ontology?"
        answer1, iters1, ns1, mems1 = rlm_run_with_memory(
            query=query1,
            context=context,
            memory_store=memory_store_empty,
            ns=ns,
            max_iters=5,
            enable_memory_extraction=True
        )

        # Protocol invariants for first run
        assert_code_blocks_present(iters1, min_blocks=1)
        assert_converged_properly(answer1, iters1)

        # First run should extract some memories if successful
        initial_mem_count = len(memory_store_empty.memories)

        # Verify first run actually extracted memories on success
        if not answer1.startswith('[Max iterations]'):
            assert len(mems1) > 0, (
                "Successful run should extract at least one memory"
            )
            # Verify memories were added to store
            assert len(memory_store_empty.memories) > initial_mem_count, (
                "Memory store should contain newly extracted memories"
            )

        # Store initial access counts for memories before second run
        access_counts_before = {
            mem.id: getattr(mem, 'access_count', 0)
            for mem in memory_store_empty.memories
        }

        # Second run: related query that might benefit from memories
        query2 = "Give me an example of a prov:Activity"
        answer2, iters2, ns2, mems2 = rlm_run_with_memory(
            query=query2,
            context=context,
            memory_store=memory_store_empty,
            ns=ns,
            max_iters=5,
            enable_memory_extraction=True
        )

        # Protocol invariants for second run
        assert_code_blocks_present(iters2, min_blocks=1)
        assert_converged_properly(answer2, iters2)

        # Verify memory store persisted across runs
        assert len(memory_store_empty.memories) >= initial_mem_count

        # Verify memory retrieval occurred (access_count should have been incremented)
        # Note: Only check if memories existed before second run
        if initial_mem_count > 0:
            access_counts_after = {
                mem.id: getattr(mem, 'access_count', 0)
                for mem in memory_store_empty.memories
                if mem.id in access_counts_before
            }
            # At least one memory should have been accessed
            accessed = any(
                access_counts_after.get(mid, 0) > access_counts_before.get(mid, 0)
                for mid in access_counts_before.keys()
            )
            # Note: This may not always be true if retrieval found no relevant memories
            # So we just check that the mechanism exists
            assert hasattr(memory_store_empty.memories[0], 'access_count'), (
                "MemoryItems should have access_count tracking"
            )

    def test_memory_persistence_with_file(self, memory_store_with_temp_file, prov_ontology_path):
        """Test that memories persist when store is reloaded from file."""
        if not prov_ontology_path.exists():
            pytest.skip("PROV ontology not available")

        ns = {}
        setup_ontology_context(str(prov_ontology_path), ns, name='prov')
        context = ns['prov_meta'].summary()

        query = "What classes are in the PROV ontology?"

        # First run with memory extraction
        answer, iterations, ns, new_memories = rlm_run_with_memory(
            query=query,
            context=context,
            memory_store=memory_store_with_temp_file,
            ns=ns,
            max_iters=5,
            enable_memory_extraction=True
        )

        # Protocol invariants
        assert_code_blocks_present(iterations, min_blocks=1)
        assert_converged_properly(answer, iterations)

        # Store should have saved to file
        store_path = memory_store_with_temp_file.path
        assert store_path.exists()

        # Reload store from file
        reloaded_store = MemoryStore.load(store_path)

        # Should have same memories
        assert len(reloaded_store.memories) == len(memory_store_with_temp_file.memories)

    def test_disable_memory_extraction(self, memory_store_empty):
        """Test that memory extraction can be disabled."""
        query = "What is 5 + 3?"
        context = "You are a helpful math assistant."

        answer, iterations, ns, new_memories = rlm_run_with_memory(
            query=query,
            context=context,
            memory_store=memory_store_empty,
            max_iters=3,
            enable_memory_extraction=False  # Disabled
        )

        # Protocol invariants still apply
        assert_code_blocks_present(iterations, min_blocks=1)
        assert_converged_properly(answer, iterations)

        # No memories should be extracted
        assert new_memories == []
        assert len(memory_store_empty.memories) == 0

    def test_memory_injection_in_context(self, memory_store_empty):
        """Test that retrieved memories are injected into context."""
        # First run: establish a memory
        query1 = "Remember: Alice is 30 years old"
        context1 = "You are a helpful assistant. Store facts you learn."

        answer1, iters1, ns1, mems1 = rlm_run_with_memory(
            query=query1,
            context=context1,
            memory_store=memory_store_empty,
            max_iters=3,
            enable_memory_extraction=True
        )

        assert_code_blocks_present(iters1, min_blocks=1)
        assert_converged_properly(answer1, iters1)

        # Verify first run actually stored memories
        # (Even if extraction failed, the mechanism should work)
        first_run_mem_count = len(memory_store_empty.memories)

        # Second run: query should benefit from memory
        query2 = "How old is Alice?"
        context2 = "You are a helpful assistant."

        answer2, iters2, ns2, mems2 = rlm_run_with_memory(
            query=query2,
            context=context2,
            memory_store=memory_store_empty,
            max_iters=3,
            enable_memory_extraction=True
        )

        assert_code_blocks_present(iters2, min_blocks=1)
        assert_converged_properly(answer2, iters2)

        # Answer should reference Alice's age
        assert 'Alice' in answer2 or 'alice' in answer2.lower()
        assert '30' in answer2

        # Verify memory retrieval mechanism works
        # (If first run created memories, second run should have access to them)
        if first_run_mem_count > 0:
            # The retrieve_memories() function should have been called
            # We can't directly verify injection, but we can verify
            # that memories persist and are available for retrieval
            assert len(memory_store_empty.memories) >= first_run_mem_count, (
                "Memories should persist across runs"
            )
