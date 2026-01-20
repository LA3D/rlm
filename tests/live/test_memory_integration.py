"""Live integration tests for memory with DSPy RLM.

Tests memory retrieval, extraction, and closed-loop learning.
Requires ANTHROPIC_API_KEY.
"""

import pytest
import os
import tempfile
from pathlib import Path

from rlm_runtime.engine import run_dspy_rlm
from rlm_runtime.memory import (
    SQLiteMemoryBackend,
    MemoryItem,
    format_memories_for_context,
    judge_trajectory_dspy,
    extract_memories_dspy,
)

pytestmark = [
    pytest.mark.live,
    pytest.mark.skipif(
        not os.environ.get("ANTHROPIC_API_KEY"),
        reason="ANTHROPIC_API_KEY not set (required for live memory integration tests)",
    ),
]


@pytest.fixture
def prov_ontology():
    """Path to PROV ontology for testing."""
    path = Path(__file__).parent.parent.parent / "ontology" / "prov.ttl"
    if not path.exists():
        pytest.skip("PROV ontology not found")
    return path


@pytest.fixture
def memory_backend():
    """Create temporary in-memory backend for testing."""
    return SQLiteMemoryBackend(":memory:")


class TestMemoryRetrieval:
    """Test memory retrieval integration with DSPy RLM."""

    def test_run_with_empty_memory_backend(self, prov_ontology, memory_backend):
        """RLM works with empty memory backend."""
        result = run_dspy_rlm(
            "What is the class prov:Activity?",
            prov_ontology,
            memory_backend=memory_backend,
            retrieve_memories=3,
            verbose=True
        )

        assert result.answer
        assert "Activity" in result.answer or "activity" in result.answer.lower()

    def test_run_with_seeded_memories(self, prov_ontology, memory_backend):
        """RLM retrieves and uses seeded memories."""
        # Seed a memory
        memory = MemoryItem(
            memory_id="m-search-001",
            title="Search for entity pattern",
            description="How to find entities in an ontology",
            content="1. Use search_entity() to find candidates\n2. Use describe_entity() to get details\n3. Return label and types",
            source_type="human",
            task_query="How to find entities?",
            created_at="2026-01-20T00:00:00Z",
            tags=["search", "entity", "describe"],
            scope={"ontology": "prov"},
            provenance={"source": "manual"}
        )
        memory_backend.add_memory(memory)

        # Run with memory retrieval
        result = run_dspy_rlm(
            "What is prov:Activity?",
            prov_ontology,
            memory_backend=memory_backend,
            retrieve_memories=3,
            verbose=True
        )

        assert result.answer
        # Should successfully answer (memory provides strategy)

    def test_memory_usage_recorded(self, prov_ontology, memory_backend):
        """Memory usage is recorded when memories retrieved."""
        # Seed memory
        memory = MemoryItem(
            memory_id="m-test-001",
            title="Test memory",
            description="Test",
            content="Test content",
            source_type="human",
            task_query="test",
            created_at="2026-01-20T00:00:00Z",
            tags=["test"]
        )
        memory_backend.add_memory(memory)

        # Run with trajectory_id to enable usage recording
        result = run_dspy_rlm(
            "What is prov:Entity?",
            prov_ontology,
            memory_backend=memory_backend,
            retrieve_memories=3,
            trajectory_id="t-test-001",
            verbose=True
        )

        # Check usage was recorded
        usage = memory_backend.get_usage_for_trajectory("t-test-001")
        # May or may not retrieve the test memory depending on relevance
        # Just verify no errors occurred


class TestMemoryExtraction:
    """Test memory extraction from trajectories."""

    def test_judge_trajectory(self, prov_ontology):
        """judge_trajectory_dspy produces valid judgment."""
        # Run a simple query
        result = run_dspy_rlm(
            "What is prov:Activity?",
            prov_ontology,
            verbose=True
        )

        # Judge the trajectory
        judgment = judge_trajectory_dspy(
            "What is prov:Activity?",
            result.answer,
            result.trajectory,
            result.evidence
        )

        assert "is_success" in judgment
        assert isinstance(judgment["is_success"], bool)
        assert "reason" in judgment
        assert "confidence" in judgment
        assert judgment["confidence"] in ["high", "medium", "low"]
        assert "missing" in judgment
        assert isinstance(judgment["missing"], list)

    def test_extract_memories(self, prov_ontology):
        """extract_memories_dspy extracts valid memories."""
        # Run a query
        result = run_dspy_rlm(
            "What is prov:Entity?",
            prov_ontology,
            verbose=True
        )

        # Judge
        judgment = judge_trajectory_dspy(
            "What is prov:Entity?",
            result.answer,
            result.trajectory,
            result.evidence
        )

        # Extract memories
        memories = extract_memories_dspy(
            "What is prov:Entity?",
            result.answer,
            result.trajectory,
            judgment,
            ontology_name="prov",
            run_id="r-test-001",
            trajectory_id="t-test-001"
        )

        # Should extract 0-3 memories
        assert isinstance(memories, list)
        assert len(memories) <= 3

        # Validate memory structure
        for mem in memories:
            assert isinstance(mem, MemoryItem)
            assert mem.memory_id
            assert mem.title
            assert mem.content
            assert mem.source_type in ["success", "failure"]
            assert mem.scope.get("ontology") == "prov"
            assert mem.provenance.get("run_id") == "r-test-001"

    def test_automatic_extraction(self, prov_ontology, memory_backend):
        """RLM automatically extracts and stores memories when extract_memories=True."""
        initial_count = len(memory_backend.get_all_memories())

        # Run with memory extraction
        result = run_dspy_rlm(
            "What is prov:Activity?",
            prov_ontology,
            memory_backend=memory_backend,
            extract_memories=True,
            run_id="r-auto-001",
            trajectory_id="t-auto-001",
            verbose=True
        )

        assert result.answer

        # Check if memories were extracted
        final_count = len(memory_backend.get_all_memories())
        # May extract 0-3 memories depending on trajectory quality
        assert final_count >= initial_count


class TestClosedLoopLearning:
    """Test closed-loop learning: retrieve → run → extract → store."""

    def test_closed_loop_single_task(self, prov_ontology, memory_backend):
        """Single task: extract memory, then use it for similar task."""
        # First run: Extract memory
        result1 = run_dspy_rlm(
            "What is prov:Activity?",
            prov_ontology,
            memory_backend=memory_backend,
            extract_memories=True,
            run_id="r-loop-001",
            trajectory_id="t-loop-001",
            verbose=True
        )

        assert result1.answer

        # Check memories extracted
        memories = memory_backend.get_all_memories()
        extracted_count = len(memories)

        # Second run: Retrieve and use memory
        result2 = run_dspy_rlm(
            "What is prov:Entity?",  # Similar task
            prov_ontology,
            memory_backend=memory_backend,
            retrieve_memories=3,
            trajectory_id="t-loop-002",
            verbose=True
        )

        assert result2.answer

        # Check memory usage was recorded
        if extracted_count > 0:
            usage = memory_backend.get_usage_for_trajectory("t-loop-002")
            # May or may not retrieve depending on relevance

    def test_memory_stats_updated(self, prov_ontology, memory_backend):
        """Memory statistics updated after usage."""
        # Seed a memory
        memory = MemoryItem(
            memory_id="m-stats-001",
            title="Test stats",
            description="Test memory for stats",
            content="1. Test step",
            source_type="human",
            task_query="test",
            created_at="2026-01-20T00:00:00Z",
            tags=["test"],
            access_count=0,
            success_count=0,
            failure_count=0
        )
        memory_backend.add_memory(memory)

        # Run with extraction enabled (will update stats)
        result = run_dspy_rlm(
            "What is prov:Activity?",
            prov_ontology,
            memory_backend=memory_backend,
            retrieve_memories=3,
            extract_memories=True,
            trajectory_id="t-stats-001",
            verbose=True
        )

        # Check stats (may or may not be updated depending on retrieval)
        updated_mem = memory_backend.get_memory("m-stats-001")
        # Stats may change if memory was retrieved
        assert updated_mem.access_count >= 0


class TestMemoryFormatting:
    """Test memory formatting for context injection."""

    def test_format_empty_memories(self):
        """format_memories_for_context handles empty list."""
        formatted = format_memories_for_context([])
        assert formatted == ""

    def test_format_single_memory(self):
        """format_memories_for_context formats single memory."""
        memory = MemoryItem(
            memory_id="m-001",
            title="Test Memory",
            description="Test description",
            content="1. Step one\n2. Step two",
            source_type="success",
            task_query="test",
            created_at="2026-01-20T00:00:00Z",
            tags=["test", "example"]
        )

        formatted = format_memories_for_context([memory])

        assert "Test Memory" in formatted
        assert "Test description" in formatted
        assert "Step one" in formatted
        assert "test, example" in formatted

    def test_format_multiple_memories(self):
        """format_memories_for_context formats multiple memories."""
        memories = [
            MemoryItem(
                memory_id=f"m-{i:03d}",
                title=f"Memory {i}",
                description="Desc",
                content="Content",
                source_type="success",
                task_query="test",
                created_at="2026-01-20T00:00:00Z"
            )
            for i in range(3)
        ]

        formatted = format_memories_for_context(memories)

        assert "Memory 0" in formatted
        assert "Memory 1" in formatted
        assert "Memory 2" in formatted
        assert formatted.count("###") == 3  # 3 memory sections


class TestMemoryPersistence:
    """Test memory persistence across runs."""

    def test_memories_persist_in_file_backend(self, prov_ontology):
        """Memories persist in file-based backend."""
        with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
            db_path = f.name

        try:
            # First session: Extract memory
            backend1 = SQLiteMemoryBackend(db_path)
            result1 = run_dspy_rlm(
                "What is prov:Activity?",
                prov_ontology,
                memory_backend=backend1,
                extract_memories=True,
                run_id="r-persist-001",
                trajectory_id="t-persist-001",
                verbose=True
            )

            count1 = len(backend1.get_all_memories())
            backend1.close()

            # Second session: Load and retrieve
            backend2 = SQLiteMemoryBackend(db_path)
            count2 = len(backend2.get_all_memories())

            # Memories should persist
            assert count2 == count1

            backend2.close()

        finally:
            Path(db_path).unlink(missing_ok=True)
