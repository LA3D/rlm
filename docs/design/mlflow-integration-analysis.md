# MLflow Integration Analysis for RLM Runtime

**Date:** 2026-01-21
**Status:** ✅ **IMPLEMENTED** (2026-01-21)
**Context:** Research code with strong observability and introspection requirements

## Implementation Status

**✅ COMPLETED:** The enhanced MLflow integration described in this document has been fully implemented as of 2026-01-21.

**Implementation:**
- Module: `rlm_runtime/logging/mlflow_integration.py`
- Tests: `tests/live/test_logging.py` (6 new MLflow tests, all passing)
- Documentation: See "Observability and Experiment Tracking" section in `CLAUDE.md`

**Key features delivered:**
- ✅ Enhanced `mlflow.dspy.autolog()` configuration
- ✅ Experiment and run organization
- ✅ Parameters, metrics, and tags logging
- ✅ Artifact logging (trajectory, SPARQL, evidence)
- ✅ Custom tracking URI support
- ✅ Programmatic querying via `mlflow.search_runs()`
- ✅ Graceful degradation (warnings on failure)
- ✅ Dual logging (JSONL + MLflow)

---

## Executive Summary

Our current MLflow integration (`mlflow.dspy.autolog()`) is **minimal** and **underutilized**. MLflow provides far more value than just the UI—it's a complete programmatic experiment tracking system with structured query APIs, designed specifically for research workflows.

**Key Finding:** We should significantly expand our MLflow usage to complement (not replace) our JSONL logging with structured experiment tracking.

**Update (2026-01-21):** This analysis led to a successful implementation. See "Implementation Status" above.

---

## Current Implementation Status

### What We're Doing ✅
```python
if enable_mlflow:
    try:
        import mlflow
        mlflow.dspy.autolog()  # Default parameters only
    except ImportError:
        print("Warning: MLflow not installed, skipping auto-tracing")
```

**Problems:**
- ❌ Using all default parameters (missing optimization traces, compilation logs)
- ❌ No experiment organization (everything goes to "Default")
- ❌ No run metadata (parameters, metrics, tags)
- ❌ No artifact logging (memory packs, ontologies, queries)
- ❌ Cannot programmatically query results
- ❌ No integration with our ReasoningBank SQLite schema

---

## MLflow's Full Capabilities (What We're Missing)

### 1. **Structured Experiment Tracking**

MLflow organizes work in a hierarchy:

```
Experiment (e.g., "PROV Ontology Queries")
├── Run 1: "Entity discovery - iteration 1"
│   ├── Parameters: {ontology: "prov.ttl", max_iterations: 8}
│   ├── Metrics: {iteration_count: 5, converged: True, memories_retrieved: 3}
│   ├── Tags: {query_type: "entity-discovery", ontology: "prov"}
│   ├── Traces: [DSPy execution traces with LLM calls]
│   └── Artifacts: {trajectory.jsonl, memory_pack.jsonl, sparql_queries/}
├── Run 2: "Activity relationships - iteration 2"
└── ...
```

**Source:** [MLflow Tracking](https://mlflow.org/docs/latest/ml/tracking/)

### 2. **Programmatic Query API**

Unlike our JSONL logs (which require manual parsing), MLflow provides structured queries:

```python
import mlflow

# Get all successful runs sorted by iteration count
successful_runs = mlflow.search_runs(
    filter_string="metrics.converged = True AND tags.ontology = 'prov'",
    order_by=["metrics.iteration_count ASC"]
)

# Returns pandas DataFrame for analysis
print(successful_runs[['run_id', 'metrics.iteration_count', 'params.query']])
```

**Source:** [MLflow Data Analyses with DataFrames](https://www.databricks.com/blog/2019/10/03/analyzing-your-mlflow-data-with-dataframes.html)

### 3. **Trace Search and Analysis**

MLflow provides dedicated trace query APIs (new in 2.17+):

```python
# Search traces by execution time, status, timestamps
traces_df = mlflow.search_traces(
    filter_string="trace.status = 'OK' AND trace.execution_time_ms > 5000",
    order_by=["timestamp_ms DESC"],
    return_type="dataframe"  # or "list" for Trace objects
)

# DataFrame columns: trace_id, state, execution_duration, inputs, outputs, tags
```

**Source:** [Search Traces | MLflow](https://mlflow.org/docs/latest/genai/tracing/search-traces/)

### 4. **Enhanced DSPy Autologging**

We're missing critical DSPy autolog features:

```python
mlflow.dspy.autolog(
    log_traces=True,                    # ✅ Currently enabled
    log_traces_from_compile=True,       # ❌ Should enable (optimizer traces)
    log_traces_from_eval=True,          # ✅ Currently enabled
    log_compiles=True,                  # ❌ Should enable (optimization metadata)
    log_evals=True,                     # ❌ Should enable (evaluation metrics)
    silent=False                        # Show what's being logged
)
```

**Why it matters:**
- `log_traces_from_compile=True`: Captures optimizer iterations (crucial for curriculum learning)
- `log_compiles=True`: Records Teleprompter optimization metadata
- `log_evals=True`: Logs evaluation metrics from DSPy's Evaluate

**Source:** [mlflow.dspy.autolog](https://mlflow.org/docs/latest/python_api/mlflow.dspy.html)

**Warning:** [Tracking DSPy Optimizers](https://dspy.ai/tutorials/optimizer_tracking/) notes that compilation can trigger hundreds of invocations. Should be opt-in for large curriculum runs.

### 5. **SQLite Backend (Shared with ReasoningBank)**

MLflow defaults to `sqlite:///mlflow.db` in the working directory. We can configure it to use the same directory as our ReasoningBank:

```python
# Set tracking URI to our memory directory
import mlflow
mlflow.set_tracking_uri("sqlite:///path/to/memory/mlflow.db")

# Or via environment variable
os.environ["MLFLOW_TRACKING_URI"] = "sqlite:///memory/mlflow.db"
```

**Source:** [Tracking Experiments with Local Database](https://mlflow.org/docs/latest/ml/tracking/tutorials/local-database/)

**Benefits:**
- ✅ All research data in one location
- ✅ Easy backup/archival (copy directory)
- ✅ No external services required
- ✅ Git-friendly (can .gitignore or commit)

### 6. **Artifact Logging**

We can log ReasoningBank artifacts to MLflow:

```python
with mlflow.start_run():
    # Log trajectory
    mlflow.log_artifact("trajectory.jsonl", artifact_path="trajectories")

    # Log memory pack
    mlflow.log_artifact("memory_pack.jsonl", artifact_path="memories")

    # Log ontology
    mlflow.log_artifact("prov.ttl", artifact_path="ontologies")

    # Log SPARQL queries
    mlflow.log_text(result.sparql, "query.sparql")
```

---

## Comparison: JSONL vs MLflow

### Current JSONL Logging

**Strengths:**
- ✅ Simple, human-readable format
- ✅ Easy to stream/tail during execution
- ✅ No dependencies
- ✅ Works without any setup

**Weaknesses:**
- ❌ Manual parsing required for analysis
- ❌ No structured queries (regex/grep only)
- ❌ No built-in aggregation/metrics
- ❌ No experiment organization
- ❌ Hard to compare across runs

### MLflow Tracking

**Strengths:**
- ✅ Structured experiment organization
- ✅ SQL-like query language
- ✅ Pandas DataFrame integration
- ✅ Built-in metrics aggregation
- ✅ Artifact version tracking
- ✅ Optional UI for exploration
- ✅ Designed for research workflows

**Weaknesses:**
- ❌ Heavier dependency (46 packages)
- ❌ Requires some configuration
- ❌ Less human-readable raw format

---

## Recommended Integration Strategy

### Option 1: **Dual Logging (Recommended for Research)**

Keep JSONL for detailed step-by-step traces, add MLflow for experiment-level organization:

```python
def run_dspy_rlm(
    query: str,
    ontology_path: Path,
    *,
    experiment_name: Optional[str] = None,
    run_name: Optional[str] = None,
    enable_mlflow: bool = True,
    mlflow_log_compilation: bool = False,  # Opt-in for optimizer
    log_path: Optional[Path] = None,
    **kwargs
):
    # Setup MLflow experiment
    if enable_mlflow:
        try:
            import mlflow

            # Configure autolog
            mlflow.dspy.autolog(
                log_traces=True,
                log_traces_from_compile=mlflow_log_compilation,
                log_compiles=True,
                log_evals=True,
                silent=False
            )

            # Set experiment (logical grouping)
            if experiment_name:
                mlflow.set_experiment(experiment_name)

            # Start run
            mlflow.start_run(run_name=run_name or f"query-{trajectory_id[:8]}")

            # Log parameters
            mlflow.log_param("ontology", ontology_path.stem)
            mlflow.log_param("query", query)
            mlflow.log_param("max_iterations", max_iterations)
            mlflow.log_param("model", model)

            # Log tags for filtering
            mlflow.set_tag("ontology_name", onto_name)
            mlflow.set_tag("has_memory", memory_backend is not None)

        except ImportError:
            enable_mlflow = False

    # ... existing code ...

    # Execute RLM
    result = rlm(query=query, context=context)

    # Log to MLflow
    if enable_mlflow:
        # Log metrics
        mlflow.log_metric("iteration_count", result.iteration_count)
        mlflow.log_metric("converged", 1 if result.converged else 0)
        if retrieved_memories:
            mlflow.log_metric("memories_retrieved", len(retrieved_memories))

        # Log artifacts
        if log_path:
            mlflow.log_artifact(str(log_path), artifact_path="trajectories")

        if result.sparql:
            mlflow.log_text(result.sparql, "query.sparql")

        mlflow.end_run()

    return result
```

### Option 2: **JSONL Only (Current, Minimal)**

Keep current approach if:
- You never need to compare runs
- Manual log parsing is acceptable
- Minimal dependencies are critical

### Option 3: **MLflow Only (Not Recommended)**

Replace JSONL with MLflow. **Not recommended** because:
- Loses real-time tail-ability during execution
- Less transparent for debugging
- Harder to export for external tools

---

## Concrete Recommendations

### Immediate Actions (Phase 7 Enhancement)

1. **Enhance `mlflow.dspy.autolog()` configuration:**
   ```python
   mlflow.dspy.autolog(
       log_traces=True,
       log_traces_from_compile=False,  # Keep False by default
       log_traces_from_eval=True,
       log_compiles=True,              # ADD: Log optimization metadata
       log_evals=True,                 # ADD: Log evaluation metrics
       silent=False
   )
   ```

2. **Add experiment and run context:**
   ```python
   mlflow.set_experiment(experiment_name or "rlm-ontology-queries")
   with mlflow.start_run(run_name=run_name):
       # ... existing code ...
   ```

3. **Log structured metadata:**
   ```python
   # Parameters (searchable, comparable)
   mlflow.log_param("ontology", onto_name)
   mlflow.log_param("query", query)
   mlflow.log_param("max_iterations", max_iterations)

   # Metrics (aggregatable, plottable)
   mlflow.log_metric("iteration_count", result.iteration_count)
   mlflow.log_metric("converged", 1 if result.converged else 0)

   # Tags (filterable)
   mlflow.set_tag("ontology_name", onto_name)
   mlflow.set_tag("query_type", infer_query_type(query))
   ```

4. **Log key artifacts:**
   ```python
   mlflow.log_artifact(str(log_path), artifact_path="trajectories")
   mlflow.log_text(result.sparql, "query.sparql")
   ```

5. **Configure shared SQLite backend:**
   ```python
   # In CLI or run_dspy_rlm setup
   mlflow.set_tracking_uri(f"sqlite:///{memory_path.parent}/mlflow.db")
   ```

### Medium-Term (Phase 8: CLI)

6. **Add analysis commands to CLI:**
   ```bash
   # List experiments
   rlm-runtime mlflow list-experiments

   # Search runs
   rlm-runtime mlflow search --ontology prov --converged true

   # Export results
   rlm-runtime mlflow export --experiment-name "PROV queries" --output results.csv
   ```

7. **Create analysis notebooks:**
   - Jupyter notebook showing `mlflow.search_runs()` for comparing approaches
   - Examples of trace analysis with `mlflow.search_traces()`

### Long-Term (Research Publications)

8. **Curriculum evaluation framework:**
   - Use MLflow to track curriculum progression
   - Compare performance across ontologies
   - Generate publication-ready metrics

9. **Memory pack evaluation:**
   - Track memory retrieval effectiveness
   - Measure transfer learning across domains
   - A/B test different memory strategies

---

## Implementation Priority

### Phase 7 Enhancement ✅ COMPLETED (2026-01-21)
- [x] Expand `autolog()` parameters
- [x] Add experiment/run context
- [x] Log parameters, metrics, tags
- [x] Configure SQLite backend
- [x] Update tests

**Implementation details:**
- `rlm_runtime/logging/mlflow_integration.py`: Helper functions for setup, params, metrics, tags, artifacts
- `rlm_runtime/engine/dspy_rlm.py`: Integrated MLflow tracking with 5 new parameters
- `tests/live/test_logging.py`: 6 comprehensive tests (all passing)

### Phase 8: CLI (Future)
- [ ] Add MLflow query commands
- [ ] Export functionality
- [ ] Analysis utilities

### Future: Advanced Features
- [ ] Curriculum tracking
- [ ] Cross-ontology comparison
- [ ] Memory effectiveness analysis

---

## Code Changes Required

### 1. Enhanced `run_dspy_rlm()` signature

```python
def run_dspy_rlm(
    query: str,
    ontology_path: str | Path,
    *,
    # ... existing params ...
    enable_mlflow: bool = False,
    mlflow_experiment: Optional[str] = None,
    mlflow_run_name: Optional[str] = None,
    mlflow_log_compilation: bool = False,
    mlflow_tracking_uri: Optional[str] = None,
) -> DSPyRLMResult:
```

### 2. MLflow setup helper

```python
def _setup_mlflow(
    experiment_name: Optional[str],
    run_name: Optional[str],
    tracking_uri: Optional[str],
    log_compilation: bool,
) -> bool:
    """Setup MLflow tracking with enhanced configuration."""
    try:
        import mlflow

        # Configure tracking URI
        if tracking_uri:
            mlflow.set_tracking_uri(tracking_uri)

        # Enhanced autolog
        mlflow.dspy.autolog(
            log_traces=True,
            log_traces_from_compile=log_compilation,
            log_compiles=True,
            log_evals=True,
            silent=False
        )

        # Set experiment
        mlflow.set_experiment(experiment_name or "rlm-ontology-queries")

        # Start run
        mlflow.start_run(run_name=run_name)

        return True

    except ImportError:
        return False
```

### 3. MLflow logging integration

```python
def _log_to_mlflow(
    query: str,
    ontology_path: Path,
    result: DSPyRLMResult,
    memory_backend: Optional[MemoryBackend],
    log_path: Optional[Path],
    **params
):
    """Log structured data to MLflow."""
    import mlflow

    # Parameters
    mlflow.log_param("ontology", ontology_path.stem)
    mlflow.log_param("query", query)
    for key, value in params.items():
        if value is not None:
            mlflow.log_param(key, value)

    # Metrics
    mlflow.log_metric("iteration_count", result.iteration_count)
    mlflow.log_metric("converged", 1 if result.converged else 0)

    # Tags
    mlflow.set_tag("ontology_name", ontology_path.stem)
    mlflow.set_tag("has_memory", memory_backend is not None)

    # Artifacts
    if log_path:
        mlflow.log_artifact(str(log_path), artifact_path="trajectories")
    if result.sparql:
        mlflow.log_text(result.sparql, "query.sparql")
```

---

## Testing Strategy

### Unit Tests

```python
def test_mlflow_integration_graceful_degradation(prov_ontology, temp_log):
    """Test that MLflow failure doesn't break execution."""
    with patch('mlflow.dspy.autolog', side_effect=Exception("MLflow error")):
        result = run_dspy_rlm(
            "What is Entity?",
            prov_ontology,
            enable_mlflow=True,
            log_path=temp_log
        )
    assert result.answer  # Should still work

def test_mlflow_logs_parameters(prov_ontology, temp_log):
    """Test that parameters are logged to MLflow."""
    pytest.importorskip("mlflow")

    with mlflow.start_run() as run:
        result = run_dspy_rlm(
            "What is Entity?",
            prov_ontology,
            enable_mlflow=True,
            max_iterations=5
        )

    # Check logged params
    client = mlflow.tracking.MlflowClient()
    run_data = client.get_run(run.info.run_id)
    assert run_data.data.params["ontology"] == "prov"
    assert run_data.data.params["max_iterations"] == "5"
```

### Integration Tests

```python
def test_mlflow_search_runs(prov_ontology):
    """Test that runs can be queried programmatically."""
    pytest.importorskip("mlflow")

    mlflow.set_experiment("test-experiment")

    # Run multiple queries
    for query in ["What is Entity?", "What is Activity?"]:
        run_dspy_rlm(query, prov_ontology, enable_mlflow=True)

    # Search runs
    df = mlflow.search_runs(
        filter_string="params.ontology = 'prov'"
    )

    assert len(df) >= 2
    assert "metrics.iteration_count" in df.columns
```

---

## References

### Core Documentation
- [MLflow Tracking](https://mlflow.org/docs/latest/ml/tracking/)
- [MLflow Tracing for LLM Observability](https://mlflow.org/docs/latest/tracing/)
- [MLflow DSPy Flavor](https://mlflow.org/docs/latest/genai/flavors/dspy/)

### API References
- [mlflow.dspy.autolog()](https://mlflow.org/docs/latest/python_api/mlflow.dspy.html)
- [Search Traces](https://mlflow.org/docs/latest/genai/tracing/search-traces/)
- [Query Traces](https://mlflow.org/docs/3.0.1/tracing/api/search)

### Research Workflows
- [MLflow Data Analyses with DataFrames](https://www.databricks.com/blog/2019/10/03/analyzing-your-mlflow-data-with-dataframes.html)
- [Tracking DSPy Optimizers with MLflow](https://dspy.ai/tutorials/optimizer_tracking/)
- [Practical AI Observability with MLflow Tracing](https://mlflow.org/blog/ai-observability-mlflow-tracing)

### Configuration
- [Tracking Experiments with Local Database](https://mlflow.org/docs/latest/ml/tracking/tutorials/local-database/)
- [Backend Stores](https://mlflow.org/docs/latest/self-hosting/architecture/backend-store/)

---

## Conclusion

**Current state:** MLflow is underutilized—we're only using autolog with defaults.

**Recommendation:** Enhance MLflow integration to complement JSONL logging with structured experiment tracking, programmatic queries, and artifact versioning.

**Impact:**
- ✅ Better experiment organization
- ✅ Easy cross-run comparison
- ✅ Publication-ready metrics
- ✅ No loss of existing JSONL benefits

**Implementation:** Phase 7 enhancement (30-60 minutes of work)
