"""Test extract_memories() with real LLM calls.

This test suite verifies that extract_memories() correctly extracts
reusable procedural memories from successful RLM trajectories.
"""

import pytest
from pathlib import Path

from rlm.core import rlm_run
from rlm.ontology import setup_ontology_context
from rlm.procedural_memory import (
    extract_memories,
    judge_trajectory,
    extract_trajectory_artifact,
    MemoryItem
)


@pytest.fixture
def prov_ontology_path():
    """Path to PROV ontology for testing."""
    return Path('ontology/prov.ttl')


@pytest.mark.live
class TestExtractMemoriesLive:
    """Test extract_memories() with real LLM."""

    def test_extracts_from_success_trajectory(self, prov_ontology_path):
        """Test that memories are extracted from successful trajectories."""
        if not prov_ontology_path.exists():
            pytest.skip("PROV ontology not available")

        # Run a successful RLM query
        ns = {}
        setup_ontology_context(str(prov_ontology_path), ns, name='prov')
        context = ns['prov_meta'].summary()

        query = "What is prov:Activity and how is it used?"
        answer, iterations, ns = rlm_run(
            query,
            context,
            ns=ns,
            max_iters=5
        )

        # Extract artifact and judge
        artifact = extract_trajectory_artifact(query, answer, iterations, ns)
        judgment = judge_trajectory(artifact, ns)

        # Extract memories
        memories = extract_memories(artifact, judgment, ns)

        # Assertions about memories
        assert isinstance(memories, list)

        # Should extract at most 3 memories (as per spec)
        assert len(memories) <= 3

        # Each memory should be a MemoryItem
        for mem in memories:
            assert isinstance(mem, MemoryItem)
            assert hasattr(mem, 'title')
            assert hasattr(mem, 'description')
            assert hasattr(mem, 'content')
            assert hasattr(mem, 'source_type')
            assert hasattr(mem, 'task_query')

            # Fields should be populated
            assert len(mem.title) > 0
            assert len(mem.description) > 0
            assert len(mem.content) > 0
            assert mem.source_type in ['success', 'failure', 'mixed']
            assert mem.task_query == query

    def test_no_memories_from_failed_trajectory(self):
        """Test that no memories are extracted from failed trajectories."""
        from rlm._rlmpaper_compat import RLMIteration

        # Create a clearly failed trajectory
        iterations = [
            RLMIteration(
                prompt="What is foo?",
                response="I don't know.",
                code_blocks=[],
                final_answer=None,
                iteration_time=0.1
            )
        ]

        artifact = extract_trajectory_artifact(
            task="What is foo?",
            answer="[Max iterations] No answer produced",
            iterations=iterations,
            ns={}
        )

        judgment = judge_trajectory(artifact, {})

        # Extract memories from failed trajectory
        memories = extract_memories(artifact, judgment, {})

        # Should extract 0 or very few memories from failures
        assert isinstance(memories, list)
        assert len(memories) <= 1  # Maybe extract a failure pattern, but not procedures

    def test_memory_content_structure(self, prov_ontology_path):
        """Test that extracted memory content has proper structure."""
        if not prov_ontology_path.exists():
            pytest.skip("PROV ontology not available")

        # Run RLM
        ns = {}
        setup_ontology_context(str(prov_ontology_path), ns, name='prov')
        context = ns['prov_meta'].summary()

        query = "Find and describe the prov:Entity class"
        answer, iterations, ns = rlm_run(
            query,
            context,
            ns=ns,
            max_iters=5
        )

        artifact = extract_trajectory_artifact(query, answer, iterations, ns)
        judgment = judge_trajectory(artifact, ns)
        memories = extract_memories(artifact, judgment, ns)

        if len(memories) > 0:
            # Check first memory structure
            mem = memories[0]

            # Content should be markdown-formatted steps
            assert '- ' in mem.content or '1. ' in mem.content or '* ' in mem.content, (
                "Memory content should be formatted as steps"
            )

            # Title should be concise
            assert len(mem.title) < 100, "Title should be concise"

            # Description should be informative
            assert len(mem.description) > 10, "Description should be informative"

            # Should have metadata
            assert mem.id is not None
            assert mem.created_at is not None
            assert isinstance(mem.tags, list)

    def test_memories_vary_by_trajectory(self, prov_ontology_path):
        """Test that different trajectories produce different memories."""
        if not prov_ontology_path.exists():
            pytest.skip("PROV ontology not available")

        ns1 = {}
        setup_ontology_context(str(prov_ontology_path), ns1, name='prov')
        context = ns1['prov_meta'].summary()

        # First trajectory: explore Activity
        query1 = "What is prov:Activity?"
        answer1, iters1, ns1 = rlm_run(query1, context, ns=ns1, max_iters=5)
        artifact1 = extract_trajectory_artifact(query1, answer1, iters1, ns1)
        judgment1 = judge_trajectory(artifact1, ns1)
        memories1 = extract_memories(artifact1, judgment1, ns1)

        ns2 = {}
        setup_ontology_context(str(prov_ontology_path), ns2, name='prov')

        # Second trajectory: explore Entity
        query2 = "What is prov:Entity?"
        answer2, iters2, ns2 = rlm_run(query2, context, ns=ns2, max_iters=5)
        artifact2 = extract_trajectory_artifact(query2, answer2, iters2, ns2)
        judgment2 = judge_trajectory(artifact2, ns2)
        memories2 = extract_memories(artifact2, judgment2, ns2)

        # Both should produce memories
        assert isinstance(memories1, list)
        assert isinstance(memories2, list)

        # If both successful, memories should reference different concepts
        if len(memories1) > 0 and len(memories2) > 0:
            mem1_text = ' '.join([m.title + m.description + m.content for m in memories1])
            mem2_text = ' '.join([m.title + m.description + m.content for m in memories2])

            # They should not be identical
            assert mem1_text != mem2_text

    def test_memory_source_type(self, prov_ontology_path):
        """Test that memory source_type is correctly set."""
        if not prov_ontology_path.exists():
            pytest.skip("PROV ontology not available")

        ns = {}
        setup_ontology_context(str(prov_ontology_path), ns, name='prov')
        context = ns['prov_meta'].summary()

        query = "List classes in PROV ontology"
        answer, iterations, ns = rlm_run(query, context, ns=ns, max_iters=5)

        artifact = extract_trajectory_artifact(query, answer, iterations, ns)
        judgment = judge_trajectory(artifact, ns)
        memories = extract_memories(artifact, judgment, ns)

        for mem in memories:
            # Source type should match trajectory success (correct key is 'is_success')
            if judgment.get('is_success'):
                assert mem.source_type in ['success', 'mixed']
            else:
                assert mem.source_type in ['failure', 'mixed']

    def test_memory_tags(self, prov_ontology_path):
        """Test that memories have appropriate tags."""
        if not prov_ontology_path.exists():
            pytest.skip("PROV ontology not available")

        ns = {}
        setup_ontology_context(str(prov_ontology_path), ns, name='prov')
        context = ns['prov_meta'].summary()

        query = "What is prov:wasGeneratedBy?"
        answer, iterations, ns = rlm_run(query, context, ns=ns, max_iters=5)

        artifact = extract_trajectory_artifact(query, answer, iterations, ns)
        judgment = judge_trajectory(artifact, ns)
        memories = extract_memories(artifact, judgment, ns)

        for mem in memories:
            assert isinstance(mem.tags, list)
            # Tags should be non-empty for useful categorization
            # (though empty tags are technically valid)
            if len(mem.tags) > 0:
                for tag in mem.tags:
                    assert isinstance(tag, str)
                    assert len(tag) > 0
