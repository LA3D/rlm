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


# Mark all tests as live (API calls) and skip if API key not available
pytestmark = [
    pytest.mark.live,
    pytest.mark.skipif(
        not os.environ.get("ANTHROPIC_API_KEY"),
        reason="ANTHROPIC_API_KEY not set (required for live tests)",
    ),
]


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


@pytest.fixture
def isolated_mlflow():
    """Isolate MLflow tracking to a temporary directory."""
    mlflow = pytest.importorskip("mlflow")

    # Save original tracking URI
    original_uri = mlflow.get_tracking_uri()

    # Create temp directory for MLflow
    import tempfile
    import shutil
    temp_dir = tempfile.mkdtemp()
    temp_uri = f"file:{temp_dir}/mlruns"

    # Set temp tracking URI
    mlflow.set_tracking_uri(temp_uri)

    yield temp_uri

    # Restore original URI and cleanup
    mlflow.set_tracking_uri(original_uri)
    if os.path.exists(temp_dir):
        shutil.rmtree(temp_dir)


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

    # Should have run creation
    assert "run_creation" in event_types
    run_event = next(e for e in events if e["event"] == "run_creation")
    assert run_event["run_id"] == "test-run-001"
    assert run_event["ontology_name"] == "prov"

    # Should have trajectory creation
    assert "trajectory_creation" in event_types
    traj_event = next(e for e in events if e["event"] == "trajectory_creation")
    assert traj_event["trajectory_id"] == "test-traj-001"
    assert traj_event["run_id"] == "test-run-001"

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


def test_mlflow_logs_parameters(prov_ontology, temp_log, isolated_mlflow):
    """Test that parameters are logged to MLflow."""
    mlflow = pytest.importorskip("mlflow")

    result = run_dspy_rlm(
        "What is Entity?",
        prov_ontology,
        max_iterations=5,
        enable_mlflow=True,
        mlflow_experiment="test-params",
        log_path=temp_log,
    )

    # Query the run
    runs = mlflow.search_runs(experiment_names=["test-params"])
    assert len(runs) >= 1

    # Check logged params
    latest_run = runs.iloc[0]
    assert latest_run["params.ontology"] == "prov"
    assert latest_run["params.max_iterations"] == "5"
    assert latest_run["params.query"] == "What is Entity?"


def test_mlflow_logs_metrics(prov_ontology, temp_log, isolated_mlflow):
    """Test that metrics are logged to MLflow."""
    mlflow = pytest.importorskip("mlflow")

    result = run_dspy_rlm(
        "What is Activity?",
        prov_ontology,
        max_iterations=5,
        enable_mlflow=True,
        mlflow_experiment="test-metrics",
        log_path=temp_log,
    )

    runs = mlflow.search_runs(experiment_names=["test-metrics"])
    latest_run = runs.iloc[0]

    # Check metrics
    assert "metrics.iteration_count" in latest_run
    assert "metrics.converged" in latest_run
    assert latest_run["metrics.converged"] == 1.0  # Should be 1 for True


def test_mlflow_search_runs_programmatic(prov_ontology, temp_log, isolated_mlflow):
    """Test programmatic querying of MLflow runs."""
    mlflow = pytest.importorskip("mlflow")

    # Run multiple queries
    for query in ["What is Entity?", "What is Activity?"]:
        run_dspy_rlm(
            query,
            prov_ontology,
            max_iterations=3,
            enable_mlflow=True,
            mlflow_experiment="test-search",
        )

    # Search with filter
    runs = mlflow.search_runs(
        experiment_names=["test-search"],
        filter_string="params.ontology = 'prov'",
        order_by=["metrics.iteration_count ASC"]
    )

    assert len(runs) >= 2
    assert "params.query" in runs.columns
    assert "metrics.iteration_count" in runs.columns


def test_mlflow_custom_tracking_uri(prov_ontology, temp_log, tmp_path):
    """Test custom SQLite tracking URI."""
    mlflow = pytest.importorskip("mlflow")

    db_path = tmp_path / "mlflow.db"

    result = run_dspy_rlm(
        "What is Entity?",
        prov_ontology,
        max_iterations=3,
        enable_mlflow=True,
        mlflow_tracking_uri=f"sqlite:///{db_path}",
        mlflow_experiment="test-uri",
    )

    # Verify database was created
    assert db_path.exists()

    # Verify we can query it
    mlflow.set_tracking_uri(f"sqlite:///{db_path}")
    runs = mlflow.search_runs(experiment_names=["test-uri"])
    assert len(runs) >= 1


def test_mlflow_with_memory_extraction(prov_ontology, temp_db, temp_log, isolated_mlflow):
    """Test MLflow metrics with memory extraction."""
    mlflow = pytest.importorskip("mlflow")
    from datetime import datetime, timezone

    backend = SQLiteMemoryBackend(temp_db)

    # Seed with a memory
    from rlm_runtime.memory import MemoryItem

    seed_memory = MemoryItem(
        memory_id="test-mlflow-001",
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

    result = run_dspy_rlm(
        "What is Activity?",
        prov_ontology,
        max_iterations=5,
        memory_backend=backend,
        retrieve_memories=3,
        extract_memories=True,
        enable_mlflow=True,
        mlflow_experiment="test-memory-extraction",
        log_path=temp_log,
    )

    # Query the run
    runs = mlflow.search_runs(experiment_names=["test-memory-extraction"])
    assert len(runs) > 0, "No MLflow runs found for experiment"
    latest_run = runs.iloc[0]

    # Check memory-related metrics
    assert "metrics.memories_retrieved" in latest_run
    assert "metrics.memories_extracted" in latest_run
    assert "metrics.judgment_success" in latest_run
    assert latest_run["metrics.memories_retrieved"] >= 1


def test_mlflow_with_custom_tags(prov_ontology, temp_log, isolated_mlflow):
    """Test MLflow custom tags."""
    mlflow = pytest.importorskip("mlflow")

    result = run_dspy_rlm(
        "What is Entity?",
        prov_ontology,
        max_iterations=3,
        enable_mlflow=True,
        mlflow_experiment="test-tags",
        mlflow_tags={"experiment": "v2", "user": "test-user"},
        log_path=temp_log,
    )

    # Query the run
    runs = mlflow.search_runs(experiment_names=["test-tags"])
    assert len(runs) > 0, "No MLflow runs found for experiment"
    latest_run = runs.iloc[0]

    # Check custom tags
    assert latest_run["tags.experiment"] == "v2"
    assert latest_run["tags.user"] == "test-user"
    assert latest_run["tags.ontology"] == "prov"
