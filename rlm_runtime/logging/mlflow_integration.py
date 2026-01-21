"""MLflow integration for DSPy RLM tracking.

Provides structured experiment tracking, parameter/metric logging,
and artifact storage with graceful degradation when MLflow unavailable.

Requirements:
    - mlflow >= 2.17.0 (for DSPy integration with mlflow.dspy.autolog)
    - Optional dependency - system degrades gracefully if not installed

Install:
    uv pip install mlflow
"""

from __future__ import annotations

from pathlib import Path
from typing import Optional
import warnings


def setup_mlflow_tracking(
    experiment_name: Optional[str] = None,
    run_name: Optional[str] = None,
    tracking_uri: Optional[str] = None,
    log_compilation: bool = False,
) -> tuple[bool, Optional[str]]:
    """Setup MLflow tracking with enhanced DSPy autolog.

    Args:
        experiment_name: Name of MLflow experiment (creates if doesn't exist)
        run_name: Optional name for this run
        tracking_uri: Optional tracking URI (e.g., "sqlite:///path/to/mlflow.db")
        log_compilation: Whether to log optimizer compilation traces (can be verbose)

    Returns:
        (success, run_id) - Whether setup succeeded and the active run ID

    Example:
        success, run_id = setup_mlflow_tracking(
            experiment_name="PROV Queries",
            run_name="entity-discovery-v1",
            tracking_uri="sqlite:///experiments/mlflow.db"
        )
        if success:
            print(f"MLflow tracking active: {run_id}")
    """
    try:
        import mlflow

        # Check for DSPy integration (requires mlflow >= 2.17.0)
        if not hasattr(mlflow, 'dspy'):
            warnings.warn(
                "MLflow DSPy integration not available. "
                "Please upgrade to mlflow >= 2.17.0 for full DSPy support. "
                "Install: uv pip install 'mlflow>=2.17.0'",
                UserWarning
            )
            return False, None

        # Set tracking URI if provided
        if tracking_uri:
            mlflow.set_tracking_uri(tracking_uri)

        # Configure DSPy autolog BEFORE starting run to avoid leaking runs on failure
        mlflow.dspy.autolog(
            log_traces=True,                           # Inference traces
            log_traces_from_compile=log_compilation,   # Optimizer traces (opt-in)
            log_traces_from_eval=True,                 # Evaluation traces
            log_compiles=True,                         # Optimization metadata
            log_evals=True,                            # Evaluation metrics
            silent=False,                              # Show what's being logged
        )

        # Set or create experiment
        if experiment_name:
            mlflow.set_experiment(experiment_name)

        # Start a new run (after autolog configuration)
        mlflow.start_run(run_name=run_name)
        run_id = mlflow.active_run().info.run_id

        return True, run_id

    except ImportError:
        warnings.warn("MLflow not installed, skipping tracking", UserWarning)
        return False, None
    except Exception as e:
        warnings.warn(f"MLflow setup failed: {e}", UserWarning)
        # End any active run to avoid leaks
        try:
            import mlflow
            if mlflow.active_run():
                mlflow.end_run()
        except:
            pass
        return False, None


def log_run_params(
    query: str,
    ontology_name: str,
    max_iterations: int,
    model: str,
    sub_model: str,
    has_memory: bool,
) -> None:
    """Log run parameters (searchable, comparable).

    Parameters are logged to the active MLflow run and can be used
    for filtering and comparison via mlflow.search_runs().

    Args:
        query: User query being answered
        ontology_name: Name of the ontology being queried
        max_iterations: Maximum RLM iterations allowed
        model: Root model identifier
        sub_model: Sub-model identifier for delegated reasoning
        has_memory: Whether memory backend is enabled

    Example:
        log_run_params(
            query="What is Activity?",
            ontology_name="prov",
            max_iterations=8,
            model="anthropic/claude-sonnet-4-5-20250929",
            sub_model="anthropic/claude-3-5-haiku-20241022",
            has_memory=True
        )
    """
    try:
        import mlflow

        mlflow.log_params({
            "query": query,
            "ontology": ontology_name,
            "max_iterations": max_iterations,
            "model": model,
            "sub_model": sub_model,
            "has_memory": has_memory,
        })

    except Exception as e:
        warnings.warn(f"Failed to log MLflow params: {e}", UserWarning)


def log_run_metrics(
    iteration_count: int,
    converged: bool,
    memories_retrieved: int = 0,
    memories_extracted: int = 0,
    judgment_success: Optional[bool] = None,
) -> None:
    """Log run metrics (aggregatable, plottable).

    Metrics are logged to the active MLflow run and can be aggregated
    across runs for analysis and visualization.

    Args:
        iteration_count: Number of RLM iterations taken
        converged: Whether execution converged successfully
        memories_retrieved: Number of memories retrieved from backend
        memories_extracted: Number of new memories extracted
        judgment_success: Whether trajectory judgment was successful (if judged)

    Example:
        log_run_metrics(
            iteration_count=3,
            converged=True,
            memories_retrieved=2,
            memories_extracted=1,
            judgment_success=True
        )
    """
    try:
        import mlflow

        metrics = {
            "iteration_count": iteration_count,
            "converged": 1 if converged else 0,
            "memories_retrieved": memories_retrieved,
            "memories_extracted": memories_extracted,
        }

        # Add judgment metric if available
        if judgment_success is not None:
            metrics["judgment_success"] = 1 if judgment_success else 0

        mlflow.log_metrics(metrics)

    except Exception as e:
        warnings.warn(f"Failed to log MLflow metrics: {e}", UserWarning)


def log_run_tags(
    ontology_name: str,
    query_type: Optional[str] = None,
    custom_tags: Optional[dict] = None,
) -> None:
    """Log run tags (filterable).

    Tags provide categorical metadata for filtering runs.
    All tags are stored as strings.

    Args:
        ontology_name: Name of the ontology (for grouping)
        query_type: Optional query type (e.g., "entity-discovery", "hierarchy")
        custom_tags: Optional dict of custom tags

    Example:
        log_run_tags(
            ontology_name="prov",
            query_type="entity-discovery",
            custom_tags={"experiment": "v2", "user": "researcher"}
        )
    """
    try:
        import mlflow

        tags = {
            "ontology": ontology_name,
        }

        if query_type:
            tags["query_type"] = query_type

        if custom_tags:
            tags.update(custom_tags)

        mlflow.set_tags(tags)

    except Exception as e:
        warnings.warn(f"Failed to log MLflow tags: {e}", UserWarning)


def log_artifacts(
    log_path: Optional[Path] = None,
    sparql_query: Optional[str] = None,
    evidence: Optional[dict] = None,
) -> None:
    """Log artifacts (trajectory, SPARQL, evidence).

    Artifacts are stored as files in the MLflow run directory
    and can be downloaded for later analysis.

    Args:
        log_path: Path to trajectory JSONL log file
        sparql_query: SPARQL query that was executed
        evidence: Grounding evidence dict

    Example:
        log_artifacts(
            log_path=Path("trajectory.jsonl"),
            sparql_query="SELECT ?s WHERE { ?s a prov:Activity }",
            evidence={"uris": ["prov:Activity"], "result_count": 5}
        )
    """
    try:
        import mlflow
        import json
        import tempfile

        # Log trajectory JSONL if available
        if log_path and log_path.exists():
            mlflow.log_artifact(str(log_path), artifact_path="trajectory")

        # Log SPARQL query using mlflow.log_text (no temp files needed)
        if sparql_query:
            try:
                mlflow.log_text(sparql_query, "queries/query.sparql")
            except AttributeError:
                # Fallback for older MLflow versions without log_text
                temp_sparql = None
                try:
                    with tempfile.NamedTemporaryFile(mode="w", suffix=".sparql", delete=False) as f:
                        f.write(sparql_query)
                        temp_sparql = f.name
                    mlflow.log_artifact(temp_sparql, artifact_path="queries")
                finally:
                    if temp_sparql and Path(temp_sparql).exists():
                        Path(temp_sparql).unlink()

        # Log evidence using mlflow.log_dict (no temp files needed)
        if evidence:
            try:
                mlflow.log_dict(evidence, "evidence/evidence.json")
            except (AttributeError, TypeError):
                # Fallback: AttributeError for older MLflow, TypeError for non-serializable objects
                temp_evidence = None
                try:
                    with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
                        # Use default=str to handle non-JSON-serializable objects
                        json.dump(evidence, f, indent=2, default=str)
                        temp_evidence = f.name
                    mlflow.log_artifact(temp_evidence, artifact_path="evidence")
                finally:
                    if temp_evidence and Path(temp_evidence).exists():
                        Path(temp_evidence).unlink()

    except Exception as e:
        warnings.warn(f"Failed to log MLflow artifacts: {e}", UserWarning)


def end_mlflow_run() -> None:
    """Cleanly end the current MLflow run.

    Should be called at the end of execution to properly
    close the run and write all data.

    Example:
        setup_mlflow_tracking(experiment_name="test")
        # ... do work ...
        end_mlflow_run()
    """
    try:
        import mlflow

        if mlflow.active_run():
            mlflow.end_run()

    except Exception as e:
        warnings.warn(f"Failed to end MLflow run: {e}", UserWarning)
