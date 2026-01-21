"""Live tests for trajectory logging and observability.

Requires ANTHROPIC_API_KEY environment variable.
"""

import os
import json
import tempfile
from pathlib import Path

import pytest

from rlm_runtime.engine.dspy_rlm import run_dspy_rlm
from rlm_runtime.memory import SQLiteMemoryBackend


@pytest.fixture
def prov_ontology():
    """Path to PROV ontology."""
    return Path(__file__).parent.parent.parent / "ontology" / "prov.ttl"


@pytest.fixture
def temp_db():
    """Temporary SQLite database."""
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        db_path = f.name
    yield db_path
    # Cleanup
    if os.path.exists(db_path):
        os.unlink(db_path)


@pytest.fixture
def temp_log():
    """Temporary JSONL log file."""
    with tempfile.NamedTemporaryFile(suffix=".jsonl", delete=False, mode="w") as f:
        log_path = f.name
    yield log_path
    # Cleanup
    if os.path.exists(log_path):
        os.unlink(log_path)


def test_trajectory_logging_basic(prov_ontology, temp_log):
    """Test basic trajectory logging without memory backend.

    Note: Tool calls are executed in the Python namespace by NamespaceCodeInterpreter,
    so they don't trigger DSPy BaseCallback hooks. Tool execution details are captured
    in the result.trajectory list instead.
    """
    result = run_dspy_rlm(
        "What is Activity?",
        prov_ontology,
        max_iterations=5,
        verbose=True,
        log_path=temp_log,
        log_llm_calls=True,
    )

    # Verify result
    assert result.answer
    assert "Activity" in result.answer

    # Verify log file exists and contains events
    assert os.path.exists(temp_log)
    events = []
    with open(temp_log, "r") as f:
        for line in f:
            events.append(json.loads(line))

    # Should have session_start, module events, and session_end
    # Note: Tool calls are executed in the Python namespace, so they don't
    # trigger BaseCallback hooks. They're captured in the trajectory instead.
    event_types = [e["event"] for e in events]
    assert "session_start" in event_types
    assert "module_start" in event_types
    assert "module_end" in event_types
    assert "session_end" in event_types

    # LLM calls should be logged (unless disabled)
    assert "llm_call" in event_types
    assert "llm_response" in event_types

    # All events should have timestamps and run_id
    for event in events:
        assert "timestamp" in event
        assert "run_id" in event
        assert "trajectory_id" in event

    # Tool calls should be in the result trajectory
    assert len(result.trajectory) > 0
    # Trajectory steps should have code
    assert any("code" in step for step in result.trajectory)


def test_memory_event_logging(prov_ontology, temp_db, temp_log):
    """Test memory event logging with retrieval and extraction."""
    from datetime import datetime, timezone

    backend = SQLiteMemoryBackend(temp_db)

    # Seed with a memory
    from rlm_runtime.memory import MemoryItem

    seed_memory = MemoryItem(
        memory_id="test-seed-001",
        title="Activity is a core PROV class",
        description="Activity represents things that occur over time",
        content="Use describe_entity('prov:Activity') to get details",
        source_type="manual",
        task_query="What is Activity?",
        created_at=datetime.now(timezone.utc).isoformat(),
        tags=["prov", "entity-discovery"],
        scope={"ontology": "prov", "task_types": ["entity-discovery"]},
        provenance={"source": "test"},
    )
    backend.add_memory(seed_memory)

    # Run with memory retrieval and extraction
    result = run_dspy_rlm(
        "What is Activity?",
        prov_ontology,
        max_iterations=5,
        verbose=True,
        memory_backend=backend,
        retrieve_memories=3,
        extract_memories=True,
        log_path=temp_log,
        run_id="test-run-001",
        trajectory_id="test-traj-001",
    )

    # Verify result
    assert result.answer
    assert "Activity" in result.answer

    # Verify log file contains memory events
    events = []
    with open(temp_log, "r") as f:
        for line in f:
            events.append(json.loads(line))

    event_types = [e["event"] for e in events]

    # Should have memory retrieval
    assert "memory_retrieval" in event_types
    retrieval_event = next(e for e in events if e["event"] == "memory_retrieval")
    assert retrieval_event["k_requested"] == 3
    assert retrieval_event["k_retrieved"] >= 1

    # Should have trajectory judgment
    assert "trajectory_judgment" in event_types
    judgment_event = next(e for e in events if e["event"] == "trajectory_judgment")
    assert "is_success" in judgment_event
    assert "reason" in judgment_event

    # Should have memory extraction (if judgment successful)
    if judgment_event["is_success"]:
        assert "memory_extraction" in event_types
        extraction_event = next(e for e in events if e["event"] == "memory_extraction")
        assert extraction_event["extracted_count"] >= 0

    # Should have memory usage records
    assert "memory_usage_record" in event_types

    # Should have stats updates
    assert "memory_stats_update" in event_types

    # Verify trajectory was stored
    traj = backend.get_trajectory("test-traj-001")
    assert traj is not None
    assert traj["task_query"] == "What is Activity?"
    assert traj["run_id"] == "test-run-001"
    assert traj["final_answer"] == result.answer


def test_mlflow_integration(prov_ontology, temp_log):
    """Test MLflow auto-tracing integration."""
    pytest.importorskip("mlflow", reason="MLflow not installed")

    result = run_dspy_rlm(
        "What is Entity?",
        prov_ontology,
        max_iterations=5,
        verbose=True,
        log_path=temp_log,
        enable_mlflow=True,
    )

    # Verify result (MLflow tracing should not affect correctness)
    assert result.answer
    assert "Entity" in result.answer


def test_auto_generated_ids(prov_ontology, temp_db, temp_log):
    """Test that run_id and trajectory_id are auto-generated if not provided."""
    backend = SQLiteMemoryBackend(temp_db)

    result = run_dspy_rlm(
        "What is Agent?",
        prov_ontology,
        max_iterations=5,
        memory_backend=backend,
        log_path=temp_log,
    )

    # Verify result
    assert result.answer

    # Verify events have auto-generated IDs
    events = []
    with open(temp_log, "r") as f:
        for line in f:
            events.append(json.loads(line))

    # All events should have run_id and trajectory_id
    for event in events:
        assert "run_id" in event
        assert "trajectory_id" in event
        # Should be UUID format
        assert event["run_id"].startswith("run-")
        assert event["trajectory_id"].startswith("traj-")

    # Verify run was recorded in database
    stats = backend.get_stats()
    assert stats["runs"] >= 1
    assert stats["trajectories"] >= 1
