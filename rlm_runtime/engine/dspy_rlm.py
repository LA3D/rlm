"""DSPy RLM engine for ontology query construction.

Provides structured query construction with typed outputs, bounded tools,
and host-Python code execution with optional memory integration.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Optional, TYPE_CHECKING
import os
import warnings

if TYPE_CHECKING:
    from rlm_runtime.memory import MemoryBackend


@dataclass
class DSPyRLMResult:
    """Result from DSPy RLM execution.

    Attributes:
        answer: Natural language answer to the query
        sparql: SPARQL query that was executed (if applicable)
        evidence: Grounding evidence (URIs, result samples, etc.)
        trajectory: List of execution steps
        iteration_count: Number of iterations taken
        converged: Whether execution converged successfully
    """

    answer: str
    sparql: str | None = None
    evidence: dict | None = None
    trajectory: list[dict] = None
    iteration_count: int = 0
    converged: bool = True

    def __post_init__(self):
        if self.trajectory is None:
            self.trajectory = []
        if self.evidence is None:
            self.evidence = {}


def run_dspy_rlm(
    query: str,
    ontology_path: str | Path,
    *,
    max_iterations: int = 8,
    max_llm_calls: int = 16,
    verbose: bool = False,
    model: str = "anthropic/claude-sonnet-4-5-20250929",
    sub_model: str = "anthropic/claude-3-5-haiku-20241022",
    memory_backend: Optional["MemoryBackend"] = None,
    retrieve_memories: int = 3,
    extract_memories: bool = False,
    run_id: Optional[str] = None,
    trajectory_id: Optional[str] = None,
    log_path: Optional[str | Path] = None,
    enable_mlflow: bool = False,
    mlflow_experiment: Optional[str] = None,
    mlflow_run_name: Optional[str] = None,
    mlflow_tracking_uri: Optional[str] = None,
    mlflow_log_compilation: bool = False,
    mlflow_tags: Optional[dict[str, str]] = None,
    log_llm_calls: bool = True,
) -> DSPyRLMResult:
    """Run DSPy RLM for ontology query construction with optional memory integration and logging.

    Args:
        query: User question to answer
        ontology_path: Path to ontology file (TTL/RDF)
        max_iterations: Maximum RLM iterations (default 8)
        max_llm_calls: Maximum LLM calls (default 16)
        verbose: Whether to print execution trace (default False)
        model: Root model for RLM (default Sonnet 4.5)
        sub_model: Sub-model for delegated reasoning (default Haiku)
        memory_backend: Optional MemoryBackend for retrieval/extraction
        retrieve_memories: Number of memories to retrieve if backend provided (default 3)
        extract_memories: Whether to extract and store memories after execution (default False)
        run_id: Optional run ID for provenance tracking
        trajectory_id: Optional trajectory ID for provenance tracking
        log_path: Optional path to JSONL log file for trajectory logging
        enable_mlflow: Whether to enable MLflow tracking (default False)
        mlflow_experiment: Optional MLflow experiment name (creates if doesn't exist)
        mlflow_run_name: Optional name for this MLflow run
        mlflow_tracking_uri: Optional MLflow tracking URI (e.g., "sqlite:///mlflow.db")
        mlflow_log_compilation: Whether to log optimizer compilation traces (default False)
        mlflow_tags: Optional dict of custom tags for filtering runs
        log_llm_calls: Whether to log LLM calls in trajectory log (default True)

    Returns:
        DSPyRLMResult with answer, sparql, evidence, trajectory

    Raises:
        ValueError: If ANTHROPIC_API_KEY not set
        FileNotFoundError: If ontology_path doesn't exist

    Examples:
        from rlm_runtime.memory import SQLiteMemoryBackend

        # Basic usage with memory retrieval and logging
        backend = SQLiteMemoryBackend("memory.db")
        result = run_dspy_rlm(
            "What is Activity?",
            "prov.ttl",
            memory_backend=backend,
            retrieve_memories=3,
            log_path="trajectory.jsonl"
        )

        # With memory extraction and basic MLflow
        result = run_dspy_rlm(
            "What is Entity?",
            "prov.ttl",
            memory_backend=backend,
            extract_memories=True,
            enable_mlflow=True
        )

        # MLflow with experiment organization
        result = run_dspy_rlm(
            "What is Activity?",
            "prov.ttl",
            enable_mlflow=True,
            mlflow_experiment="PROV Ontology Queries",
            mlflow_run_name="activity-discovery-v1"
        )

        # MLflow with custom SQLite backend and tags
        result = run_dspy_rlm(
            "What is Activity?",
            "prov.ttl",
            enable_mlflow=True,
            mlflow_tracking_uri="sqlite:///experiments/mlflow.db",
            mlflow_tags={"experiment": "v2", "user": "researcher"}
        )

        # Query results programmatically
        import mlflow
        runs = mlflow.search_runs(
            filter_string="params.ontology = 'prov' AND metrics.converged = 1",
            order_by=["metrics.iteration_count ASC"]
        )
    """
    if not os.environ.get("ANTHROPIC_API_KEY"):
        raise ValueError("ANTHROPIC_API_KEY must be set in environment")

    ontology_path = Path(ontology_path)
    if not ontology_path.exists():
        raise FileNotFoundError(f"Ontology not found: {ontology_path}")

    # Extract ontology name early (needed for MLflow setup)
    onto_name = ontology_path.stem

    # Import DSPy (deferred to allow testing without API key)
    import dspy
    from rdflib import Graph

    from rlm.ontology import GraphMeta
    from rlm_runtime.interpreter import NamespaceCodeInterpreter
    from rlm_runtime.tools import make_ontology_tools

    # Auto-generate run_id if not provided and memory backend exists
    if memory_backend and not run_id:
        import uuid
        run_id = f"run-{uuid.uuid4().hex[:8]}"

    # Auto-generate trajectory_id if not provided
    if not trajectory_id:
        import uuid
        trajectory_id = f"traj-{uuid.uuid4().hex[:8]}"

    # Setup logging callbacks
    callbacks = []
    memory_logger = None

    if log_path:
        from rlm_runtime.logging import TrajectoryCallback, MemoryEventLogger

        # Trajectory callback for DSPy events
        traj_callback = TrajectoryCallback(
            log_path,
            run_id or "unknown",
            trajectory_id,
            log_llm_calls=log_llm_calls
        )
        callbacks.append(traj_callback)

        # Memory event logger (if using memory backend)
        if memory_backend:
            memory_logger = MemoryEventLogger(
                log_path,
                run_id or "unknown",
                trajectory_id
            )

        if verbose:
            print(f"Logging trajectory to: {log_path}")

    # Setup MLflow tracking if requested
    mlflow_active = False
    mlflow_run_id = None

    if enable_mlflow:
        from rlm_runtime.logging.mlflow_integration import (
            setup_mlflow_tracking,
            log_run_params,
            log_run_tags,
        )

        mlflow_active, mlflow_run_id = setup_mlflow_tracking(
            experiment_name=mlflow_experiment,
            run_name=mlflow_run_name or f"query-{trajectory_id[:8]}",
            tracking_uri=mlflow_tracking_uri,
            log_compilation=mlflow_log_compilation,
        )

        if mlflow_active:
            # Log parameters immediately (before execution)
            log_run_params(
                query=query,
                ontology_name=onto_name,
                max_iterations=max_iterations,
                model=model,
                sub_model=sub_model,
                has_memory=memory_backend is not None,
            )

            # Log tags for filtering
            log_run_tags(
                ontology_name=onto_name,
                custom_tags=mlflow_tags,
            )

            if verbose:
                print(f"MLflow tracking active: experiment={mlflow_experiment or 'default'}, run={mlflow_run_id}")

    # Configure DSPy models and callbacks
    dspy.configure(
        lm=dspy.LM(model, temperature=0.2, max_tokens=1400, cache=False),
        callbacks=callbacks  # Always pass list (empty or populated)
    )
    sub_lm = dspy.LM(sub_model, temperature=0.2, max_tokens=1200, cache=False)

    # Load ontology with format auto-detection
    g = Graph()

    # Detect format from file extension
    format_map = {
        '.ttl': 'turtle',
        '.rdf': 'xml',
        '.owl': 'xml',
        '.nt': 'ntriples',
        '.n3': 'n3',
        '.jsonld': 'json-ld',
        '.trig': 'trig',
        '.nq': 'nquads',
    }

    suffix = ontology_path.suffix.lower()
    fmt = format_map.get(suffix)

    # Parse with detected format or let rdflib auto-detect
    if fmt:
        g.parse(ontology_path, format=fmt)
    else:
        # Let rdflib auto-detect from file extension
        g.parse(ontology_path)

    meta = GraphMeta(graph=g, name=onto_name)

    # Record run in memory backend if provided
    if memory_backend and run_id:
        memory_backend.add_run(
            run_id,
            model=model,
            ontology_name=onto_name,
            ontology_path=str(ontology_path),
            notes=f"Query: {query}"
        )

        # Log run creation
        if memory_logger:
            memory_logger.log_run_creation(run_id, model, onto_name)

    # Create bounded tools
    tools = make_ontology_tools(meta, include_sparql=True)

    # Retrieve memories if backend provided
    memory_context = ""
    retrieved_memories = []
    if memory_backend and retrieve_memories > 0:
        from rlm_runtime.memory.extraction import format_memories_for_context

        retrieved_memories = memory_backend.retrieve(query, k=retrieve_memories)
        if retrieved_memories:
            memory_context = format_memories_for_context(retrieved_memories)
            if verbose:
                print(f"Retrieved {len(retrieved_memories)} memories")

            # Log memory retrieval event
            if memory_logger:
                memory_logger.log_retrieval(query, retrieved_memories, retrieve_memories)

    # Build context
    context_parts = [
        "You are exploring an RDF ontology via bounded tools.",
        "Do not dump large structures. Use tools to discover entities, then SUBMIT your answer.",
        "",
        meta.summary(),
    ]

    # Inject memories if available
    if memory_context:
        context_parts.append("")
        context_parts.append(memory_context)

    context_parts.extend([
        "",
        "Goal: Answer the query grounded in retrieved evidence.",
    ])

    context = "\n".join(context_parts)

    # Define typed signature
    class QueryConstructionSig(dspy.Signature):
        """Construct answer using bounded ontology tools, optionally via SPARQL."""

        query: str = dspy.InputField(desc="User question to answer using the ontology.")
        context: str = dspy.InputField(desc="Ontology summary and tool instructions.")

        answer: str = dspy.OutputField(desc="Final grounded answer in natural language.")
        sparql: str = dspy.OutputField(
            desc="SPARQL query executed (if used), otherwise empty string."
        )
        evidence: dict = dspy.OutputField(
            desc="Grounding evidence: URIs, result samples, tool outputs."
        )

    # Create RLM
    rlm = dspy.RLM(
        QueryConstructionSig,
        max_iterations=max_iterations,
        max_llm_calls=max_llm_calls,
        verbose=verbose,
        tools=tools,
        sub_lm=sub_lm,
        interpreter=NamespaceCodeInterpreter(),
    )

    # Execute
    # Wrap execution in try/finally to ensure cleanup
    try:
        pred = rlm(query=query, context=context)

        # Extract trajectory
        trajectory = getattr(pred, "trajectory", [])
        # Convert trajectory steps to dicts (they may be custom objects)
        trajectory_dicts = []
        for step in trajectory:
            if isinstance(step, dict):
                trajectory_dicts.append(step)
            else:
                # Try to convert to dict
                trajectory_dicts.append(
                    {
                        "code": getattr(step, "code", ""),
                        "output": str(getattr(step, "output", "")),
                    }
                )

        # Build result
        result = DSPyRLMResult(
            answer=pred.answer,
            sparql=pred.sparql if hasattr(pred, "sparql") else None,
            evidence=pred.evidence if hasattr(pred, "evidence") else {},
            trajectory=trajectory_dicts,
            iteration_count=len(trajectory),
            converged=True,  # DSPy RLM always returns something
        )

        # Log initial metrics to MLflow (before memory extraction)
        if mlflow_active:
            from rlm_runtime.logging.mlflow_integration import log_run_metrics

            log_run_metrics(
                iteration_count=result.iteration_count,
                converged=result.converged,
                memories_retrieved=len(retrieved_memories) if retrieved_memories else 0,
            )

        # Store trajectory in memory backend
        if memory_backend and trajectory_id and run_id:
            memory_backend.add_trajectory(
                trajectory_id=trajectory_id,
                run_id=run_id,
                task_query=query,
                final_answer=result.answer,
                iteration_count=result.iteration_count,
                converged=result.converged,
                artifact={
                    "sparql": result.sparql,
                    "evidence": result.evidence,
                    "trajectory": result.trajectory,
                },
                rlm_log_path=str(log_path) if log_path else None,
            )

            # Log trajectory creation
            if memory_logger:
                memory_logger.log_trajectory_creation(
                    trajectory_id,
                    run_id,
                    query,
                    result.iteration_count,
                    result.converged
                )

        # Record memory usage if memories were retrieved
        if memory_backend and retrieved_memories and trajectory_id:
            for i, mem in enumerate(retrieved_memories, 1):
                memory_backend.record_usage(
                    trajectory_id=trajectory_id,
                    memory_id=mem.memory_id,
                    rank=i,
                    score=None  # BM25 score not currently exposed
                )

                # Log usage recording
                if memory_logger:
                    memory_logger.log_usage_record(trajectory_id, mem.memory_id, i, None)

                # Update access count
                memory_backend.update_memory_stats(mem.memory_id, accessed=True)

                # Log stats update
                if memory_logger:
                    memory_logger.log_stats_update(mem.memory_id, accessed=True)

        # Extract and store memories if requested
        if memory_backend and extract_memories:
            from rlm_runtime.memory.extraction import judge_trajectory_dspy, extract_memories_dspy

            # Judge trajectory
            judgment = judge_trajectory_dspy(
                query,
                result.answer,
                result.trajectory,
                result.evidence,
                model=sub_model
            )

            if verbose:
                print(f"Judgment: {'Success' if judgment['is_success'] else 'Failure'} ({judgment['confidence']})")
                print(f"Reason: {judgment['reason']}")

            # Log judgment
            if memory_logger:
                memory_logger.log_judgment(trajectory_id, judgment)

            # Extract memories
            new_memories = extract_memories_dspy(
                query,
                result.answer,
                result.trajectory,
                judgment,
                ontology_name=onto_name,
                run_id=run_id,
                trajectory_id=trajectory_id,
                model=sub_model
            )

            # Log extraction
            if memory_logger:
                source_type = "success" if judgment["is_success"] else "failure"
                memory_logger.log_extraction(trajectory_id, new_memories, source_type)

            # Store memories
            for mem in new_memories:
                was_duplicate = memory_backend.has_memory(mem.memory_id)
                memory_backend.add_memory(mem)
                if verbose:
                    print(f"Extracted memory: {mem.title}")

                # Log storage
                if memory_logger:
                    memory_logger.log_storage(mem.memory_id, mem.title, was_duplicate)

            # Update memory stats based on judgment
            if retrieved_memories and trajectory_id:
                for mem in retrieved_memories:
                    if judgment["is_success"]:
                        memory_backend.update_memory_stats(mem.memory_id, success=True)
                        if memory_logger:
                            memory_logger.log_stats_update(mem.memory_id, success=True)
                    else:
                        memory_backend.update_memory_stats(mem.memory_id, failure=True)
                        if memory_logger:
                            memory_logger.log_stats_update(mem.memory_id, failure=True)

            # Update MLflow metrics with extraction results
            if mlflow_active:
                from rlm_runtime.logging.mlflow_integration import log_run_metrics

                log_run_metrics(
                    iteration_count=result.iteration_count,
                    converged=result.converged,
                    memories_retrieved=len(retrieved_memories) if retrieved_memories else 0,
                    memories_extracted=len(new_memories),
                    judgment_success=judgment["is_success"],
                )


    finally:
        # Always cleanup callbacks and MLflow, even on exceptions
        if callbacks:
            for callback in callbacks:
                if hasattr(callback, 'close'):
                    try:
                        callback.close()
                    except Exception as e:
                        warnings.warn(f"Failed to close callback: {e}", UserWarning)

        if memory_logger:
            try:
                memory_logger.close()
            except Exception as e:
                warnings.warn(f"Failed to close memory logger: {e}", UserWarning)

        # End MLflow run if active
        if mlflow_active:
            from rlm_runtime.logging.mlflow_integration import end_mlflow_run
            end_mlflow_run()

    return result
