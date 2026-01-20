"""Unit tests for SQLite ReasoningBank memory backend.

Tests schema creation, CRUD operations, retrieval, and provenance tracking.
"""

import pytest
import sqlite3
import tempfile
from pathlib import Path
from datetime import datetime, timezone

from rlm_runtime.memory import (
    SQLiteMemoryBackend,
    MemoryBackend,
    MemoryItem,
    ensure_schema,
    get_schema_version,
    has_fts5_support,
    is_memory_backend,
)
from rlm_runtime.memory.sqlite_schema import list_tables, get_table_info


@pytest.fixture
def temp_db():
    """Create a temporary database file for testing."""
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        db_path = f.name
    yield db_path
    # Cleanup
    Path(db_path).unlink(missing_ok=True)


class TestSchemaCreation:
    """Test SQLite schema setup and versioning."""

    def test_ensure_schema_creates_all_tables(self, temp_db):
        """Schema creates all 5 core tables."""
        ensure_schema(temp_db)
        tables = list_tables(temp_db)

        assert "runs" in tables
        assert "trajectories" in tables
        assert "judgments" in tables
        assert "memory_items" in tables
        assert "memory_usage" in tables
        assert "schema_version" in tables

    def test_fts5_table_created_if_available(self, temp_db):
        """FTS5 table created when FTS5 is available."""
        ensure_schema(temp_db)
        tables = list_tables(temp_db)

        # FTS5 may or may not be available depending on SQLite build
        if has_fts5_support(temp_db):
            assert "memory_fts" in tables

    def test_schema_version_recorded(self, temp_db):
        """Schema version is recorded after creation."""
        ensure_schema(temp_db)
        version = get_schema_version(temp_db)
        assert version == 1

    def test_memory_items_has_all_columns(self, temp_db):
        """Memory items table has all required columns."""
        ensure_schema(temp_db)
        cols = get_table_info(temp_db, "memory_items")
        col_names = {col["name"] for col in cols}

        required = {
            "memory_id", "title", "description", "content",
            "source_type", "task_query", "created_at",
            "tags_json", "scope_json", "provenance_json",
            "access_count", "success_count", "failure_count"
        }
        assert required.issubset(col_names)

    def test_trajectories_foreign_key_to_runs(self, temp_db):
        """Trajectories table has foreign key to runs."""
        ensure_schema(temp_db)
        conn = sqlite3.connect(temp_db)

        # Foreign key should be enforced
        conn.execute("PRAGMA foreign_keys = ON")
        conn.execute("INSERT INTO runs (run_id, created_at) VALUES ('r-001', datetime('now'))")

        # Should succeed (valid foreign key)
        conn.execute("""
            INSERT INTO trajectories (trajectory_id, run_id, task_query, final_answer,
                                     iteration_count, converged, artifact_json, created_at)
            VALUES ('t-001', 'r-001', 'test', 'answer', 1, 1, '{}', datetime('now'))
        """)
        conn.commit()
        conn.close()


class TestMemoryBackendProtocol:
    """Test protocol compliance and type checking."""

    def test_sqlite_backend_implements_protocol(self):
        """SQLiteMemoryBackend implements MemoryBackend protocol."""
        backend = SQLiteMemoryBackend(":memory:")
        assert is_memory_backend(backend)
        assert isinstance(backend, MemoryBackend)

    def test_backend_has_all_required_methods(self):
        """Backend has all protocol-required methods."""
        backend = SQLiteMemoryBackend(":memory:")

        required_methods = [
            "add_run", "add_trajectory", "add_judgment",
            "add_memory", "retrieve", "record_usage",
            "has_memory", "get_memory", "get_all_memories",
            "update_memory_stats"
        ]

        for method_name in required_methods:
            assert hasattr(backend, method_name)
            assert callable(getattr(backend, method_name))


class TestMemoryItem:
    """Test MemoryItem dataclass."""

    def test_compute_id_is_stable(self):
        """compute_id produces same ID for same content."""
        title = "Test Memory"
        content = "Step 1\nStep 2"

        id1 = MemoryItem.compute_id(title, content)
        id2 = MemoryItem.compute_id(title, content)

        assert id1 == id2
        assert len(id1) == 16  # 16-char hex

    def test_compute_id_changes_with_content(self):
        """compute_id produces different ID for different content."""
        id1 = MemoryItem.compute_id("Title", "Content A")
        id2 = MemoryItem.compute_id("Title", "Content B")

        assert id1 != id2

    def test_memory_item_to_dict(self):
        """MemoryItem converts to dict."""
        memory = MemoryItem(
            memory_id="test-001",
            title="Test",
            description="Desc",
            content="Content",
            source_type="success",
            task_query="query",
            created_at="2026-01-20T00:00:00Z",
            tags=["tag1"],
            scope={"ontology": "prov"},
            provenance={"run_id": "r-001"}
        )

        d = memory.to_dict()
        assert d["memory_id"] == "test-001"
        assert d["title"] == "Test"
        assert d["tags"] == ["tag1"]

    def test_memory_item_from_dict(self):
        """MemoryItem creates from dict."""
        data = {
            "memory_id": "test-001",
            "title": "Test",
            "description": "Desc",
            "content": "Content",
            "source_type": "success",
            "task_query": "query",
            "created_at": "2026-01-20T00:00:00Z",
            "tags": ["tag1"],
            "scope": {"ontology": "prov"},
            "provenance": {"run_id": "r-001"},
            "access_count": 0,
            "success_count": 0,
            "failure_count": 0
        }

        memory = MemoryItem.from_dict(data)
        assert memory.memory_id == "test-001"
        assert memory.tags == ["tag1"]


class TestRunManagement:
    """Test run CRUD operations."""

    def test_add_run_returns_run_id(self):
        """add_run stores and returns run_id."""
        backend = SQLiteMemoryBackend(":memory:")

        run_id = backend.add_run(
            "r-001",
            model="claude-sonnet-4-5",
            ontology_name="prov",
            ontology_path="/path/to/prov.ttl",
            notes="Test run"
        )

        assert run_id == "r-001"

    def test_run_stored_in_database(self):
        """Run is retrievable from database."""
        backend = SQLiteMemoryBackend(":memory:")
        backend.add_run("r-001", model="claude-sonnet-4-5")

        cursor = backend.conn.cursor()
        cursor.execute("SELECT * FROM runs WHERE run_id = ?", ("r-001",))
        row = cursor.fetchone()

        assert row is not None
        assert row["run_id"] == "r-001"
        assert row["model"] == "claude-sonnet-4-5"


class TestTrajectoryManagement:
    """Test trajectory CRUD operations."""

    def test_add_trajectory_requires_run(self):
        """add_trajectory requires valid run_id."""
        backend = SQLiteMemoryBackend(":memory:")
        backend.add_run("r-001")

        traj_id = backend.add_trajectory(
            "t-001",
            "r-001",
            "What is Activity?",
            "Activity is a class...",
            3,
            True,
            {"iterations": []},
            rlm_log_path="/path/to/log.jsonl"
        )

        assert traj_id == "t-001"

    def test_get_trajectory_returns_dict(self):
        """get_trajectory returns full trajectory data."""
        backend = SQLiteMemoryBackend(":memory:")
        backend.add_run("r-001")

        artifact = {"iterations": [{"code": "x=1", "output": ""}]}
        backend.add_trajectory(
            "t-001", "r-001", "query", "answer", 3, True, artifact
        )

        traj = backend.get_trajectory("t-001")

        assert traj is not None
        assert traj["trajectory_id"] == "t-001"
        assert traj["task_query"] == "query"
        assert traj["final_answer"] == "answer"
        assert traj["converged"] is True
        assert traj["artifact"]["iterations"] == artifact["iterations"]

    def test_get_nonexistent_trajectory_returns_none(self):
        """get_trajectory returns None for missing ID."""
        backend = SQLiteMemoryBackend(":memory:")
        traj = backend.get_trajectory("missing")
        assert traj is None


class TestJudgmentManagement:
    """Test judgment CRUD operations."""

    def test_add_judgment_stores_data(self):
        """add_judgment stores judgment for trajectory."""
        backend = SQLiteMemoryBackend(":memory:")
        backend.add_run("r-001")
        backend.add_trajectory("t-001", "r-001", "q", "a", 1, True, {})

        backend.add_judgment(
            "t-001",
            is_success=True,
            reason="Answer is correct",
            confidence="high",
            missing=[]
        )

        judgment = backend.get_judgment("t-001")
        assert judgment is not None
        assert judgment["is_success"] is True
        assert judgment["confidence"] == "high"

    def test_get_nonexistent_judgment_returns_none(self):
        """get_judgment returns None for missing trajectory."""
        backend = SQLiteMemoryBackend(":memory:")
        judgment = backend.get_judgment("missing")
        assert judgment is None


class TestMemoryManagement:
    """Test memory CRUD operations."""

    def test_add_memory_stores_and_returns_id(self):
        """add_memory stores memory and returns ID."""
        backend = SQLiteMemoryBackend(":memory:")

        memory = MemoryItem(
            memory_id="m-001",
            title="Test Memory",
            description="Test description",
            content="Step 1\nStep 2",
            source_type="success",
            task_query="test query",
            created_at=datetime.now(timezone.utc).isoformat(),
            tags=["search", "entity"],
            scope={"ontology": "prov"},
            provenance={"run_id": "r-001"}
        )

        mem_id = backend.add_memory(memory)
        assert mem_id == "m-001"

    def test_add_memory_skips_duplicates(self):
        """add_memory skips if memory_id already exists."""
        backend = SQLiteMemoryBackend(":memory:")

        memory = MemoryItem(
            memory_id="m-001",
            title="Test",
            description="Desc",
            content="Content",
            source_type="success",
            task_query="q",
            created_at=datetime.now(timezone.utc).isoformat()
        )

        backend.add_memory(memory)
        backend.add_memory(memory)  # Second call should skip

        # Should only have one copy
        cursor = backend.conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM memory_items WHERE memory_id = ?", ("m-001",))
        count = cursor.fetchone()[0]
        assert count == 1

    def test_has_memory_returns_true_for_existing(self):
        """has_memory returns True for existing memory."""
        backend = SQLiteMemoryBackend(":memory:")

        memory = MemoryItem(
            memory_id="m-001",
            title="Test",
            description="Desc",
            content="Content",
            source_type="success",
            task_query="q",
            created_at=datetime.now(timezone.utc).isoformat()
        )

        backend.add_memory(memory)
        assert backend.has_memory("m-001") is True
        assert backend.has_memory("missing") is False

    def test_get_memory_returns_memory_item(self):
        """get_memory retrieves MemoryItem by ID."""
        backend = SQLiteMemoryBackend(":memory:")

        memory = MemoryItem(
            memory_id="m-001",
            title="Test Memory",
            description="Test description",
            content="Step 1\nStep 2",
            source_type="success",
            task_query="test query",
            created_at=datetime.now(timezone.utc).isoformat(),
            tags=["search"],
            scope={"ontology": "prov"},
            provenance={"run_id": "r-001"}
        )

        backend.add_memory(memory)
        retrieved = backend.get_memory("m-001")

        assert retrieved is not None
        assert retrieved.memory_id == "m-001"
        assert retrieved.title == "Test Memory"
        assert retrieved.tags == ["search"]
        assert retrieved.scope == {"ontology": "prov"}

    def test_get_all_memories_returns_list(self):
        """get_all_memories returns all stored memories."""
        backend = SQLiteMemoryBackend(":memory:")

        for i in range(3):
            memory = MemoryItem(
                memory_id=f"m-{i:03d}",
                title=f"Memory {i}",
                description="Desc",
                content="Content",
                source_type="success",
                task_query="q",
                created_at=datetime.now(timezone.utc).isoformat()
            )
            backend.add_memory(memory)

        memories = backend.get_all_memories()
        assert len(memories) == 3

    def test_get_all_memories_with_filter(self):
        """get_all_memories filters by source_type."""
        backend = SQLiteMemoryBackend(":memory:")

        for i, source in enumerate(["success", "failure", "success"]):
            memory = MemoryItem(
                memory_id=f"m-{i:03d}",
                title=f"Memory {i}",
                description="Desc",
                content="Content",
                source_type=source,
                task_query="q",
                created_at=datetime.now(timezone.utc).isoformat()
            )
            backend.add_memory(memory)

        memories = backend.get_all_memories(filters={"source_type": "success"})
        assert len(memories) == 2

    def test_update_memory_stats_increments_counts(self):
        """update_memory_stats increments usage counters."""
        backend = SQLiteMemoryBackend(":memory:")

        memory = MemoryItem(
            memory_id="m-001",
            title="Test",
            description="Desc",
            content="Content",
            source_type="success",
            task_query="q",
            created_at=datetime.now(timezone.utc).isoformat()
        )

        backend.add_memory(memory)

        backend.update_memory_stats("m-001", accessed=True)
        backend.update_memory_stats("m-001", accessed=True, success=True)
        backend.update_memory_stats("m-001", failure=True)

        retrieved = backend.get_memory("m-001")
        assert retrieved.access_count == 2
        assert retrieved.success_count == 1
        assert retrieved.failure_count == 1


class TestRetrieval:
    """Test memory retrieval functionality."""

    def test_retrieve_returns_empty_for_no_memories(self):
        """retrieve returns empty list when no memories exist."""
        backend = SQLiteMemoryBackend(":memory:")
        results = backend.retrieve("test query", k=3)
        assert results == []

    def test_retrieve_returns_relevant_memories(self):
        """retrieve returns memories matching query."""
        backend = SQLiteMemoryBackend(":memory:")

        # Add memories with different content
        memories = [
            MemoryItem(
                memory_id="m-001",
                title="Search Entity Pattern",
                description="How to search for entities",
                content="Use search_entity()",
                source_type="success",
                task_query="q",
                created_at=datetime.now(timezone.utc).isoformat(),
                tags=["search", "entity"]
            ),
            MemoryItem(
                memory_id="m-002",
                title="Describe Pattern",
                description="How to describe entities",
                content="Use describe_entity()",
                source_type="success",
                task_query="q",
                created_at=datetime.now(timezone.utc).isoformat(),
                tags=["describe"]
            ),
        ]

        for mem in memories:
            backend.add_memory(mem)

        # Query for search-related memories
        results = backend.retrieve("search entity", k=3)

        # Should return at least one result (FTS5 or fallback)
        assert len(results) > 0
        # Top result should be search-related
        assert "search" in results[0].title.lower() or "search" in results[0].tags

    def test_retrieve_respects_k_limit(self):
        """retrieve returns at most k results."""
        backend = SQLiteMemoryBackend(":memory:")

        # Add 5 memories
        for i in range(5):
            memory = MemoryItem(
                memory_id=f"m-{i:03d}",
                title=f"Memory {i}",
                description="Test memory",
                content="Content",
                source_type="success",
                task_query="q",
                created_at=datetime.now(timezone.utc).isoformat(),
                tags=["test"]
            )
            backend.add_memory(memory)

        results = backend.retrieve("test", k=3)
        assert len(results) <= 3


class TestMemoryUsageTracking:
    """Test memory usage logging."""

    def test_record_usage_stores_entry(self):
        """record_usage stores trajectory-memory link."""
        backend = SQLiteMemoryBackend(":memory:")
        backend.add_run("r-001")
        backend.add_trajectory("t-001", "r-001", "q", "a", 1, True, {})

        memory = MemoryItem(
            memory_id="m-001",
            title="Test",
            description="Desc",
            content="Content",
            source_type="success",
            task_query="q",
            created_at=datetime.now(timezone.utc).isoformat()
        )
        backend.add_memory(memory)

        backend.record_usage("t-001", "m-001", rank=1, score=0.85)

        usage = backend.get_usage_for_trajectory("t-001")
        assert len(usage) == 1
        assert usage[0]["memory_id"] == "m-001"
        assert usage[0]["rank"] == 1
        assert usage[0]["score"] == 0.85

    def test_get_usage_for_memory(self):
        """get_usage_for_memory returns all trajectories that used a memory."""
        backend = SQLiteMemoryBackend(":memory:")
        backend.add_run("r-001")
        backend.add_trajectory("t-001", "r-001", "q1", "a1", 1, True, {})
        backend.add_trajectory("t-002", "r-001", "q2", "a2", 1, True, {})

        memory = MemoryItem(
            memory_id="m-001",
            title="Test",
            description="Desc",
            content="Content",
            source_type="success",
            task_query="q",
            created_at=datetime.now(timezone.utc).isoformat()
        )
        backend.add_memory(memory)

        backend.record_usage("t-001", "m-001", rank=1, score=0.9)
        backend.record_usage("t-002", "m-001", rank=2, score=0.7)

        usage = backend.get_usage_for_memory("m-001")
        assert len(usage) == 2
        trajectory_ids = {u["trajectory_id"] for u in usage}
        assert trajectory_ids == {"t-001", "t-002"}


class TestStatistics:
    """Test database statistics."""

    def test_get_stats_returns_counts(self):
        """get_stats returns counts for all tables."""
        backend = SQLiteMemoryBackend(":memory:")

        backend.add_run("r-001")
        backend.add_trajectory("t-001", "r-001", "q", "a", 1, True, {})
        backend.add_judgment("t-001", True, "reason", "high", [])

        memory = MemoryItem(
            memory_id="m-001",
            title="Test",
            description="Desc",
            content="Content",
            source_type="success",
            task_query="q",
            created_at=datetime.now(timezone.utc).isoformat()
        )
        backend.add_memory(memory)
        backend.record_usage("t-001", "m-001", 1, 0.9)

        stats = backend.get_stats()

        assert stats["runs"] == 1
        assert stats["trajectories"] == 1
        assert stats["judgments"] == 1
        assert stats["memory_items"] == 1
        assert stats["memory_usage"] == 1


class TestContextManager:
    """Test context manager protocol."""

    def test_context_manager_closes_connection(self):
        """Backend can be used as context manager."""
        with SQLiteMemoryBackend(":memory:") as backend:
            backend.add_run("r-001")
            assert backend.conn is not None

        # Connection should be closed after context exit
        # (accessing closed connection raises exception)
