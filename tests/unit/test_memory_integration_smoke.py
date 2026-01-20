"""Smoke tests for memory integration (no API calls required).

Tests the integration points between memory backend and DSPy RLM
without requiring ANTHROPIC_API_KEY.
"""

import pytest
from datetime import datetime, timezone
from pathlib import Path

from rlm_runtime.memory import (
    SQLiteMemoryBackend,
    MemoryItem,
    format_memories_for_context,
)


class TestMemoryBackendIntegration:
    """Test memory backend integration points."""

    def test_create_backend_and_store_memory(self):
        """Can create backend and store memory."""
        backend = SQLiteMemoryBackend(":memory:")

        memory = MemoryItem(
            memory_id="m-001",
            title="Test Strategy",
            description="A test strategy",
            content="1. Step one\n2. Step two",
            source_type="success",
            task_query="test query",
            created_at=datetime.now(timezone.utc).isoformat(),
            tags=["test"],
            scope={"ontology": "test"},
            provenance={"run_id": "r-001"}
        )

        mem_id = backend.add_memory(memory)
        assert mem_id == "m-001"

        # Retrieve it
        retrieved = backend.get_memory("m-001")
        assert retrieved.title == "Test Strategy"

    def test_retrieve_and_format_workflow(self):
        """Full workflow: store → retrieve → format."""
        backend = SQLiteMemoryBackend(":memory:")

        # Store multiple memories
        for i in range(3):
            memory = MemoryItem(
                memory_id=f"m-{i:03d}",
                title=f"Strategy {i}",
                description=f"Description {i}",
                content=f"1. Step {i}a\n2. Step {i}b",
                source_type="success",
                task_query="test",
                created_at=datetime.now(timezone.utc).isoformat(),
                tags=["test", f"tag{i}"]
            )
            backend.add_memory(memory)

        # Retrieve
        memories = backend.retrieve("test strategy", k=2)
        assert len(memories) <= 2

        # Format for context
        formatted = format_memories_for_context(memories)
        assert "Retrieved Procedural Memories" in formatted

    def test_full_provenance_chain(self):
        """Test full provenance: run → trajectory → judgment → memory."""
        backend = SQLiteMemoryBackend(":memory:")

        # Add run
        run_id = backend.add_run(
            "r-001",
            model="claude-sonnet-4-5",
            ontology_name="prov",
            ontology_path="/path/to/prov.ttl",
            notes="Test run"
        )

        # Add trajectory
        trajectory_id = backend.add_trajectory(
            "t-001",
            run_id,
            "What is Activity?",
            "Activity is a class...",
            3,
            True,
            {"iterations": [{"code": "x=1", "output": "1"}]}
        )

        # Add judgment
        backend.add_judgment(
            trajectory_id,
            is_success=True,
            reason="Answer is correct",
            confidence="high",
            missing=[]
        )

        # Add memory with provenance
        memory = MemoryItem(
            memory_id="m-001",
            title="Activity Pattern",
            description="How to describe Activity",
            content="1. Search for Activity\n2. Describe it",
            source_type="success",
            task_query="What is Activity?",
            created_at=datetime.now(timezone.utc).isoformat(),
            scope={"ontology": "prov"},
            provenance={"run_id": run_id, "trajectory_id": trajectory_id}
        )
        backend.add_memory(memory)

        # Verify chain
        retrieved_memory = backend.get_memory("m-001")
        assert retrieved_memory.provenance["run_id"] == run_id
        assert retrieved_memory.provenance["trajectory_id"] == trajectory_id

        trajectory = backend.get_trajectory(trajectory_id)
        assert trajectory["run_id"] == run_id

        judgment = backend.get_judgment(trajectory_id)
        assert judgment["is_success"] is True

    def test_memory_usage_tracking(self):
        """Test memory usage tracking workflow."""
        backend = SQLiteMemoryBackend(":memory:")

        # Create run and trajectory
        backend.add_run("r-001")
        backend.add_trajectory("t-001", "r-001", "query", "answer", 1, True, {})

        # Create memory
        memory = MemoryItem(
            memory_id="m-001",
            title="Test",
            description="Test",
            content="Test",
            source_type="success",
            task_query="test",
            created_at=datetime.now(timezone.utc).isoformat()
        )
        backend.add_memory(memory)

        # Record usage
        backend.record_usage("t-001", "m-001", rank=1, score=0.95)

        # Verify usage
        usage = backend.get_usage_for_trajectory("t-001")
        assert len(usage) == 1
        assert usage[0]["memory_id"] == "m-001"
        assert usage[0]["rank"] == 1
        assert usage[0]["score"] == 0.95

        # Update stats
        backend.update_memory_stats("m-001", accessed=True, success=True)

        # Verify stats
        updated = backend.get_memory("m-001")
        assert updated.access_count == 1
        assert updated.success_count == 1
        assert updated.failure_count == 0

    def test_memory_deduplication(self):
        """Test content-based deduplication."""
        backend = SQLiteMemoryBackend(":memory:")

        # Create two identical memories with different IDs
        title = "Duplicate Strategy"
        content = "1. Same step\n2. Same step"

        # Compute stable ID
        id1 = MemoryItem.compute_id(title, content)
        id2 = MemoryItem.compute_id(title, content)

        assert id1 == id2  # Same content → same ID

        # Add first memory
        mem1 = MemoryItem(
            memory_id=id1,
            title=title,
            description="First",
            content=content,
            source_type="success",
            task_query="test",
            created_at=datetime.now(timezone.utc).isoformat()
        )
        backend.add_memory(mem1)

        # Try to add duplicate (should skip)
        mem2 = MemoryItem(
            memory_id=id2,  # Same ID
            title=title,
            description="Second",  # Different description
            content=content,
            source_type="success",
            task_query="test",
            created_at=datetime.now(timezone.utc).isoformat()
        )
        backend.add_memory(mem2)

        # Should only have one memory
        all_memories = backend.get_all_memories()
        assert len(all_memories) == 1
        # Original description preserved
        assert all_memories[0].description == "First"

    def test_memory_filtering(self):
        """Test filtering memories by source_type and ontology."""
        backend = SQLiteMemoryBackend(":memory:")

        # Add memories with different source types
        for i, source_type in enumerate(["success", "success", "failure"]):
            memory = MemoryItem(
                memory_id=f"m-{i:03d}",
                title=f"Memory {i}",
                description="Desc",
                content="Content",
                source_type=source_type,
                task_query="test",
                created_at=datetime.now(timezone.utc).isoformat(),
                scope={"ontology": "prov" if i < 2 else "foaf"}
            )
            backend.add_memory(memory)

        # Filter by source_type
        success_memories = backend.get_all_memories({"source_type": "success"})
        assert len(success_memories) == 2

        failure_memories = backend.get_all_memories({"source_type": "failure"})
        assert len(failure_memories) == 1

        # Filter by ontology
        prov_memories = backend.get_all_memories({"ontology": "prov"})
        assert len(prov_memories) == 2

    def test_stats_aggregation(self):
        """Test database statistics."""
        backend = SQLiteMemoryBackend(":memory:")

        # Add entities
        backend.add_run("r-001")
        backend.add_run("r-002")

        backend.add_trajectory("t-001", "r-001", "q1", "a1", 1, True, {})
        backend.add_trajectory("t-002", "r-001", "q2", "a2", 1, True, {})
        backend.add_trajectory("t-003", "r-002", "q3", "a3", 1, True, {})

        backend.add_judgment("t-001", True, "reason", "high", [])

        for i in range(5):
            memory = MemoryItem(
                memory_id=f"m-{i:03d}",
                title=f"M{i}",
                description="D",
                content="C",
                source_type="success",
                task_query="t",
                created_at=datetime.now(timezone.utc).isoformat()
            )
            backend.add_memory(memory)

        backend.record_usage("t-001", "m-000", 1, 0.9)
        backend.record_usage("t-001", "m-001", 2, 0.8)

        # Get stats
        stats = backend.get_stats()

        assert stats["runs"] == 2
        assert stats["trajectories"] == 3
        assert stats["judgments"] == 1
        assert stats["memory_items"] == 5
        assert stats["memory_usage"] == 2


class TestMemoryFormatting:
    """Test memory formatting for context injection."""

    def test_format_creates_markdown_sections(self):
        """Formatted output has proper markdown structure."""
        memories = [
            MemoryItem(
                memory_id="m-001",
                title="Strategy One",
                description="First strategy",
                content="1. Do this\n2. Then that",
                source_type="success",
                task_query="test",
                created_at=datetime.now(timezone.utc).isoformat(),
                tags=["tag1", "tag2"]
            ),
            MemoryItem(
                memory_id="m-002",
                title="Strategy Two",
                description="Second strategy",
                content="- Option A\n- Option B",
                source_type="success",
                task_query="test",
                created_at=datetime.now(timezone.utc).isoformat()
            )
        ]

        formatted = format_memories_for_context(memories)

        # Check structure
        assert "## Retrieved Procedural Memories" in formatted
        assert "### 1. Strategy One" in formatted
        assert "### 2. Strategy Two" in formatted
        assert "*First strategy*" in formatted
        assert "*Second strategy*" in formatted
        assert "1. Do this" in formatted
        assert "- Option A" in formatted
        assert "tag1, tag2" in formatted

    def test_format_handles_edge_cases(self):
        """Formatting handles empty tags and special characters."""
        memory = MemoryItem(
            memory_id="m-001",
            title="Test & <Special>",
            description="Test 'quotes' and \"quotes\"",
            content="# Header\n\n**Bold** text",
            source_type="success",
            task_query="test",
            created_at=datetime.now(timezone.utc).isoformat(),
            tags=[]  # Empty tags
        )

        formatted = format_memories_for_context([memory])

        # Should not crash on special characters
        assert "Test & <Special>" in formatted
        assert "'quotes'" in formatted
        # Tags section should not appear if empty
        assert "Tags:" not in formatted or "*Tags: *" not in formatted


class TestPackIntegration:
    """Test pack export/import with full workflow."""

    def test_export_import_preserves_all_data(self):
        """Export → import preserves all memory fields."""
        import tempfile

        backend1 = SQLiteMemoryBackend(":memory:")

        # Create memory with all fields populated
        memory = MemoryItem(
            memory_id=MemoryItem.compute_id("Title", "Content"),
            title="Complete Memory",
            description="Full description",
            content="1. Step one\n2. Step two\n3. Step three",
            source_type="success",
            task_query="How to do X?",
            created_at="2026-01-20T12:00:00Z",
            tags=["tag1", "tag2", "tag3"],
            scope={"ontology": "prov", "task_types": ["entity_search"]},
            provenance={"run_id": "r-001", "trajectory_id": "t-001"},
            access_count=5,
            success_count=3,
            failure_count=2
        )
        backend1.add_memory(memory)

        # Export to pack
        with tempfile.NamedTemporaryFile(suffix=".jsonl", delete=False) as f:
            pack_path = f.name

        try:
            from rlm_runtime.memory import export_pack, import_pack

            export_pack(backend1, pack_path)

            # Import to new backend
            backend2 = SQLiteMemoryBackend(":memory:")
            result = import_pack(backend2, pack_path)

            assert result["imported"] == 1

            # Verify all fields preserved
            imported = backend2.get_memory(memory.memory_id)
            assert imported.title == memory.title
            assert imported.description == memory.description
            assert imported.content == memory.content
            assert imported.source_type == memory.source_type
            assert imported.task_query == memory.task_query
            assert imported.tags == memory.tags
            assert imported.scope == memory.scope
            assert imported.provenance == memory.provenance
            # Note: stats reset on import (access_count, etc.)

        finally:
            Path(pack_path).unlink(missing_ok=True)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
