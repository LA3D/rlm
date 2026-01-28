"""DSPy ReAct engine for ontology query construction.

Alternative execution pattern using dspy.ReAct (simpler Thought-Action-Observation loop)
instead of dspy.RLM. Shares the same scratchpad infrastructure (interpreter, tools, context).
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Optional, TYPE_CHECKING
import os
import warnings

if TYPE_CHECKING:
    from rlm_runtime.memory import MemoryBackend


# Reuse DSPyRLMResult from dspy_rlm
from .dspy_rlm import DSPyRLMResult


def run_dspy_react(
    query: str,
    ontology_path: str | Path,
    *,
    max_iterations: int = 8,
    verbose: bool = False,
    model: str = "anthropic/claude-sonnet-4-5-20250929",
    sub_model: str = "anthropic/claude-3-5-haiku-20241022",
    sense_card: Optional[str] = None,
    memory_backend: Optional["MemoryBackend"] = None,
    retrieve_memories: int = 3,
    extract_memories: bool = False,
    enable_verification: bool = False,
    enable_curriculum_retrieval: bool = False,
    result_truncation_limit: int = 10000,
    require_agent_guide: bool = False,
    run_id: Optional[str] = None,
    trajectory_id: Optional[str] = None,
    log_path: Optional[str | Path] = None,
    enable_mlflow: bool = False,
    mlflow_experiment: Optional[str] = None,
    mlflow_run_name: Optional[str] = None,
    mlflow_tracking_uri: Optional[str] = None,
    mlflow_tags: Optional[dict[str, str]] = None,
    log_llm_calls: bool = True,
) -> DSPyRLMResult:
    """Run DSPy ReAct for ontology query construction with scratchpad features.

    ReAct uses simpler Thought → Action → Observation loop (vs RLM's code generation).
    Shares infrastructure: same interpreter, tools, truncation, verification, memory.

    Args:
        query: User question to answer
        ontology_path: Path to ontology file (TTL/RDF)
        max_iterations: Maximum ReAct iterations (default 8)
        verbose: Whether to print execution trace (default False)
        model: Root model for ReAct (default Sonnet 4.5)
        sub_model: Sub-model for delegated reasoning (default Haiku)
        sense_card: Optional pre-built sense card. If None, loads AGENT_GUIDE.md or generates.
        memory_backend: Optional MemoryBackend for retrieval/extraction
        retrieve_memories: Number of memories to retrieve if backend provided (default 3)
        extract_memories: Whether to extract and store memories after execution (default False)
        enable_verification: Whether to inject verification feedback after SPARQL queries (default False)
        enable_curriculum_retrieval: Whether to use curriculum-aware memory retrieval (default False)
        result_truncation_limit: Max chars for REPL output (0=unlimited, default 10000)
        require_agent_guide: Error if no AGENT_GUIDE.md found (default False allows fallback)
        run_id: Optional run ID for provenance tracking
        trajectory_id: Optional trajectory ID for provenance tracking
        log_path: Optional path to JSONL log file for trajectory logging
        enable_mlflow: Whether to enable MLflow tracking (default False)
        mlflow_experiment: Optional MLflow experiment name
        mlflow_run_name: Optional name for this MLflow run
        mlflow_tracking_uri: Optional MLflow tracking URI
        mlflow_tags: Optional dict of custom tags
        log_llm_calls: Whether to log LLM calls in trajectory log (default True)

    Returns:
        DSPyRLMResult with answer, sparql, evidence, trajectory

    Raises:
        ValueError: If ANTHROPIC_API_KEY not set
        FileNotFoundError: If ontology_path doesn't exist

    Examples:
        # Basic ReAct usage
        result = run_dspy_react("What is Activity?", "prov.ttl")

        # With memory and logging
        from rlm_runtime.memory import SQLiteMemoryBackend
        backend = SQLiteMemoryBackend("memory.db")
        result = run_dspy_react(
            "What is Entity?",
            "prov.ttl",
            memory_backend=backend,
            retrieve_memories=3,
            log_path="trajectory.jsonl"
        )
    """
    if not os.environ.get("ANTHROPIC_API_KEY"):
        raise ValueError("ANTHROPIC_API_KEY must be set in environment")

    ontology_path = Path(ontology_path)
    if not ontology_path.exists():
        raise FileNotFoundError(f"Ontology not found: {ontology_path}")

    onto_name = ontology_path.stem

    # Import DSPy (deferred to allow testing without API key)
    import dspy
    from rdflib import Graph

    from rlm.ontology import GraphMeta
    from rlm_runtime.interpreter import NamespaceCodeInterpreter
    from rlm_runtime.tools.ontology_tools import make_search_entity_tool, make_sparql_select_tool
    from rlm_runtime.context import load_rich_sense_card

    # Auto-generate IDs
    if memory_backend and not run_id:
        import uuid
        run_id = f"run-{uuid.uuid4().hex[:8]}"

    if not trajectory_id:
        import uuid
        trajectory_id = f"traj-{uuid.uuid4().hex[:8]}"

    # Setup logging callbacks
    callbacks = []
    memory_logger = None

    if log_path:
        from rlm_runtime.logging import TrajectoryCallback, MemoryEventLogger

        traj_callback = TrajectoryCallback(
            log_path,
            run_id or "unknown",
            trajectory_id,
            log_llm_calls=log_llm_calls
        )
        callbacks.append(traj_callback)

        if memory_backend:
            memory_logger = MemoryEventLogger(
                log_path,
                run_id or "unknown",
                trajectory_id
            )

        if verbose:
            print(f"Logging trajectory to: {log_path}")

    # Setup MLflow tracking
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
            run_name=mlflow_run_name or f"react-{trajectory_id[:8]}",
            tracking_uri=mlflow_tracking_uri,
            log_compilation=False,  # ReAct doesn't use compilation
        )

        if mlflow_active:
            log_run_params(
                query=query,
                ontology_name=onto_name,
                max_iterations=max_iterations,
                model=model,
                sub_model=sub_model,
                has_memory=memory_backend is not None,
                pattern="react",  # Tag pattern type
            )

            log_run_tags(
                ontology_name=onto_name,
                custom_tags={**mlflow_tags, "pattern": "react"} if mlflow_tags else {"pattern": "react"},
            )

            if verbose:
                print(f"MLflow tracking active: experiment={mlflow_experiment or 'default'}, run={mlflow_run_id}")

    # Configure DSPy models
    dspy.configure(
        lm=dspy.LM(model, temperature=0.2, max_tokens=4096, cache=False),
        callbacks=callbacks
    )

    # Load ontology
    g = Graph()
    suffix = ontology_path.suffix.lower()
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

    fmt = format_map.get(suffix)
    if fmt:
        g.parse(ontology_path, format=fmt)
    else:
        g.parse(ontology_path)

    meta = GraphMeta(graph=g, name=onto_name)

    # Load AGENT_GUIDE.md metadata if verification enabled
    guide_metadata = None
    if enable_verification:
        from rlm_runtime.tools.verification_feedback import load_agent_guide_for_ontology

        guide_metadata = load_agent_guide_for_ontology(ontology_path)
        if guide_metadata is None and verbose:
            print(f"Warning: enable_verification=True but no AGENT_GUIDE.md found for {onto_name}")

    # Record run in memory backend
    if memory_backend and run_id:
        memory_backend.add_run(
            run_id,
            model=model,
            ontology_name=onto_name,
            ontology_path=str(ontology_path),
            notes=f"Query: {query} (pattern: react)"
        )

        if memory_logger:
            memory_logger.log_run_creation(run_id, model, onto_name)

    # Create bounded tools (same as RLM)
    tools = {
        'search_entity': make_search_entity_tool(meta),
        'sparql_select': make_sparql_select_tool(meta)
    }

    # Retrieve memories
    memory_context = ""
    retrieved_memories = []
    if memory_backend and retrieve_memories > 0:
        from rlm_runtime.memory.extraction import format_memories_for_context

        if enable_curriculum_retrieval:
            from rlm_runtime.memory.curriculum_retrieval import retrieve_with_curriculum

            retrieved_memories = retrieve_with_curriculum(
                query,
                memory_backend,
                k=retrieve_memories,
                ontology_name=onto_name
            )
            if verbose:
                print(f"Retrieved {len(retrieved_memories)} memories (curriculum-aware)")
        else:
            retrieved_memories = memory_backend.retrieve(query, k=retrieve_memories)
            if verbose:
                print(f"Retrieved {len(retrieved_memories)} memories")

        if retrieved_memories:
            exemplar_memories = [m for m in retrieved_memories if m.source_type == 'exemplar']
            regular_memories = [m for m in retrieved_memories if m.source_type != 'exemplar']

            memory_context = format_memories_for_context(retrieved_memories)

            if memory_logger:
                memory_logger.log_retrieval(query, retrieved_memories, retrieve_memories)

    # Load rich sense card
    if sense_card is None:
        sense_card = load_rich_sense_card(
            ontology_path,
            onto_name,
            fallback_to_generated=not require_agent_guide,
        )

    # Build context (same structure as RLM)
    context_parts = [
        "You are exploring an RDF ontology via bounded tools.",
        "Do not dump large structures. Use tools to discover entities, then SUBMIT your answer.",
        "",
        "IMPORTANT: When calling SUBMIT, use keyword arguments with literal values or inline expressions.",
        "Example: SUBMIT(answer='The answer is...', sparql='SELECT...', evidence={'key': value})",
        "",
        "## Reasoning Process with State Tracking",
        "",
        "Each iteration should follow THINK → ACT → VERIFY → REFLECT cycles with explicit state tracking:",
        "",
        "**THINK**: State what you've discovered and what to do next.",
        "**ACT**: Execute code (search, query, describe).",
        "**VERIFY**: Check results match expectations.",
        "**REFLECT**: Self-critique before SUBMIT.",
        "",
    ]

    # Inject sense card
    if sense_card:
        context_parts.append("## Ontology Affordances (Sense Card)")
        context_parts.append("")
        context_parts.append("CONSULT THE SENSE CARD to understand:")
        context_parts.append("- Which annotation properties to use for labels/descriptions")
        context_parts.append("- What metadata vocabulary is present")
        context_parts.append("- What OWL constructs are available")
        context_parts.append("- SPARQL query templates for common tasks")
        context_parts.append("")
        context_parts.append(sense_card)
        context_parts.append("")

    # Add graph summary
    context_parts.append(meta.summary())

    # Inject memories
    if memory_context:
        context_parts.append("")
        if enable_curriculum_retrieval and exemplar_memories:
            context_parts.append("## Reasoning Chain Exemplars")
            context_parts.append("")
            context_parts.append("Follow these state-tracking patterns from successful queries:")
            context_parts.append("")
            for mem in exemplar_memories:
                context_parts.append(f"### {mem.title}")
                context_parts.append(mem.content)
                context_parts.append("")

        if regular_memories:
            from rlm_runtime.memory.extraction import format_memories_for_context
            regular_context = format_memories_for_context(regular_memories)
            if regular_context:
                context_parts.append("## Procedural Memories from Successful Runs")
                context_parts.append("")
                context_parts.append(regular_context)

    context_parts.extend([
        "",
        "Goal: Answer the query grounded in retrieved evidence.",
    ])

    context = "\n".join(context_parts)

    # Define signature (same as RLM)
    class QueryConstructionSig(dspy.Signature):
        """Construct answer using bounded ontology tools with explicit reasoning cycles."""

        query: str = dspy.InputField(desc="User question to answer using the ontology.")
        context: str = dspy.InputField(desc="Ontology metadata, statistics, and guidance.")

        thinking: str = dspy.OutputField(
            desc="THINK: What you learned from exploration, what patterns/entities you found, what you'll do next."
        )
        verification: str = dspy.OutputField(
            desc="VERIFY: Check results match expectations."
        )
        reflection: str = dspy.OutputField(
            desc="REFLECT: Self-critique before SUBMIT."
        )

        answer: str = dspy.OutputField(desc="Final grounded answer in natural language.")
        sparql: str = dspy.OutputField(desc="SPARQL query executed (if used), otherwise empty string.")
        evidence: dict = dspy.OutputField(desc="Grounding evidence: URIs, result samples with actual data.")

    # Create ReAct module (simpler than RLM)
    try:
        react = dspy.ReAct(
            QueryConstructionSig,
            tools=list(tools.values()),
            max_iters=max_iterations,
        )
    except Exception as e:
        # Fallback if ReAct doesn't support interpreter parameter
        # ReAct typically doesn't need custom interpreter - tools are called directly
        warnings.warn(f"Failed to create ReAct with custom config: {e}", UserWarning)
        react = dspy.ReAct(QueryConstructionSig, tools=list(tools.values()))

    # Execute
    try:
        try:
            pred = react(query=query, context=context)
        except AttributeError as e:
            if "'NoneType' object has no attribute 'strip'" in str(e):
                raise ValueError(
                    "Model refused to generate code for this query. "
                    "This may be due to content safety filters. "
                    f"Original error: {e}"
                ) from e
            raise

        # Extract trajectory (ReAct structure may differ from RLM)
        trajectory = getattr(pred, "trajectory", [])
        trajectory_dicts = []
        for step in trajectory:
            if isinstance(step, dict):
                trajectory_dicts.append(step)
            else:
                trajectory_dicts.append({
                    "action": getattr(step, "action", ""),
                    "output": str(getattr(step, "output", "")),
                })

        # Check convergence
        converged = hasattr(pred, "answer") and pred.answer

        # Build result
        result = DSPyRLMResult(
            answer=pred.answer if hasattr(pred, "answer") else "",
            sparql=pred.sparql if hasattr(pred, "sparql") else None,
            evidence=pred.evidence if hasattr(pred, "evidence") else {},
            trajectory=trajectory_dicts,
            iteration_count=len(trajectory),
            converged=bool(converged),
            thinking=getattr(pred, "thinking", None),
            verification=getattr(pred, "verification", None),
            reflection=getattr(pred, "reflection", None),
        )

        # Log metrics to MLflow
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
                    "pattern": "react",
                },
                rlm_log_path=str(log_path) if log_path else None,
            )

            if memory_logger:
                memory_logger.log_trajectory_creation(
                    trajectory_id,
                    run_id,
                    query,
                    result.iteration_count,
                    result.converged
                )

        # Record memory usage
        if memory_backend and retrieved_memories and trajectory_id:
            for i, mem in enumerate(retrieved_memories, 1):
                memory_backend.record_usage(
                    trajectory_id=trajectory_id,
                    memory_id=mem.memory_id,
                    rank=i,
                    score=None
                )

                if memory_logger:
                    memory_logger.log_usage_record(trajectory_id, mem.memory_id, i, None)

                memory_backend.update_memory_stats(mem.memory_id, accessed=True)

                if memory_logger:
                    memory_logger.log_stats_update(mem.memory_id, accessed=True)

        # Extract and store memories if requested (same logic as RLM)
        if memory_backend and extract_memories:
            from rlm_runtime.memory.extraction import judge_trajectory_dspy, extract_memories_dspy

            judgment = judge_trajectory_dspy(
                query,
                result.answer,
                result.trajectory,
                result.evidence,
                thinking=result.thinking,
                verification=result.verification,
                reflection=result.reflection,
                model=sub_model
            )

            if verbose:
                print(f"Judgment: {'Success' if judgment['is_success'] else 'Failure'} ({judgment['confidence']})")

            if memory_logger:
                memory_logger.log_judgment(trajectory_id, judgment)

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

            if memory_logger:
                source_type = "success" if judgment["is_success"] else "failure"
                memory_logger.log_extraction(trajectory_id, new_memories, source_type)

            for mem in new_memories:
                was_duplicate = memory_backend.has_memory(mem.memory_id)
                memory_backend.add_memory(mem)
                if verbose:
                    print(f"Extracted memory: {mem.title}")

                if memory_logger:
                    memory_logger.log_storage(mem.memory_id, mem.title, was_duplicate)

            # Update memory stats
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

            # Update MLflow metrics
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
        # Cleanup callbacks and MLflow
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

        if mlflow_active:
            from rlm_runtime.logging.mlflow_integration import end_mlflow_run
            end_mlflow_run()

    return result
