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
        thinking: Final thinking from the reasoning cycle (what was learned)
        verification: Final verification checks performed
        reflection: Final self-critique before submitting
    """

    answer: str
    sparql: str | None = None
    evidence: dict | None = None
    trajectory: list[dict] = None
    iteration_count: int = 0
    converged: bool = True
    # Reasoning fields from Think-Act-Verify-Reflect cycles
    thinking: str | None = None
    verification: str | None = None
    reflection: str | None = None

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
    sense_card: Optional[str] = None,
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
        sense_card: Optional pre-built sense card (~500 chars) for ontology affordances.
                    Use rlm.ontology.format_sense_card() to generate. Enables ablation
                    experiments comparing baseline vs sense-augmented context.
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

    Thread Safety:
        Not thread-safe due to NamespaceCodeInterpreter (shared _globals dict).
        For concurrent runs, call this function from separate threads/processes,
        not by sharing RLM instances. Each call creates a fresh RLM instance internally.

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

        # With sense card for ablation experiments
        from rlm.ontology import build_sense_structured, format_sense_card
        sense = build_sense_structured("prov.ttl", name="prov_sense", ns={})
        card = format_sense_card(sense)
        result = run_dspy_rlm(
            "What is Activity?",
            "prov.ttl",
            sense_card=card,
            memory_backend=backend
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
    from rlm_runtime.tools.ontology_tools import make_search_entity_tool, make_sparql_select_tool
    from rlm_runtime.ontology import build_sense_card, format_sense_card

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
    # Increased max_tokens to 4096 (from 1400) to prevent truncation of long outputs
    # with detailed answers, SPARQL, thinking, verification, reflection, AND evidence
    dspy.configure(
        lm=dspy.LM(model, temperature=0.2, max_tokens=4096, cache=False),
        callbacks=callbacks  # Always pass list (empty or populated)
    )
    sub_lm = dspy.LM(sub_model, temperature=0.2, max_tokens=2048, cache=False)

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

    # Create MINIMAL bounded tools (search_entity + sparql_select)
    # Based on testing, minimal tools are 55% faster (4.5 vs 10 iterations average)
    # and work across diverse metadata conventions (PROV, SKOS, RDFS, DCTERMS)
    tools = {
        'search_entity': make_search_entity_tool(meta),
        'sparql_select': make_sparql_select_tool(meta)
    }

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
        "IMPORTANT: When calling SUBMIT, use keyword arguments with literal values or inline expressions.",
        "Example: SUBMIT(answer='The answer is...', sparql='SELECT...', evidence={'key': value})",
        "",
        "## Reasoning Process",
        "",
        "Each iteration should follow THINK → ACT → VERIFY → REFLECT cycles:",
        "",
        "**THINK**: State what you learned and what you'll do next.",
        "- 'I found Protein class with organism property linking to Taxon...'",
        "- 'E. coli K-12 strains are siblings (materialized), so I'll use VALUES clause...'",
        "",
        "**ACT**: Execute code (search, query, describe).",
        "",
        "**VERIFY**: Check results match expectations (like running tests).",
        "- 'Results have protein field ✓'",
        "- 'Results have sequence field with amino acids ✓' (NOT just sequence_length!)",
        "- 'Query returned expected columns ✓'",
        "",
        "**REFLECT**: Self-critique before SUBMIT.",
        "- 'Evidence includes actual sequences, not just metadata'",
        "- 'All required fields are present with correct types'",
        "- 'URIs are valid and grounded in results'",
        "",
        "When you SUBMIT, include your final thinking, verification, and reflection.",
        "Evidence MUST include actual data samples (sequences, labels, descriptions) NOT just counts or lengths.",
        "",
    ]

    # Auto-generate sense card with SPARQL templates if not provided
    # Minimal tools need SPARQL templates for effective query construction
    if sense_card is None:
        sense_card_obj = build_sense_card(str(ontology_path), onto_name)
        sense_card = format_sense_card(sense_card_obj, include_sparql_templates=True)

    # Inject sense card FIRST (before meta summary)
    if sense_card:
        context_parts.append("## Ontology Affordances (Sense Card)")
        context_parts.append("")
        context_parts.append("CONSULT THE SENSE CARD to understand:")
        context_parts.append("- Which annotation properties to use for labels/descriptions")
        context_parts.append("- What metadata vocabulary is present (SKOS, DCTERMS, etc.)")
        context_parts.append("- What OWL constructs are available (restrictions, disjoints, etc.)")
        context_parts.append("- Maturity indicators (version, deprecations, imports)")
        context_parts.append("- SPARQL query templates for common tasks")
        context_parts.append("")
        context_parts.append(sense_card)
        context_parts.append("")

    # Then add graph summary
    context_parts.append(meta.summary())

    # Inject memories if available
    if memory_context:
        context_parts.append("")
        context_parts.append(memory_context)

    context_parts.extend([
        "",
        "Goal: Answer the query grounded in retrieved evidence.",
    ])

    context = "\n".join(context_parts)

    # Define typed signature with explicit reasoning fields (Think-Act-Verify-Reflect)
    class QueryConstructionSig(dspy.Signature):
        """Construct answer using bounded ontology tools with explicit reasoning cycles.

        Follow THINK → ACT → VERIFY → REFLECT cycles to ensure grounded answers
        with consistent evidence formats.
        """

        query: str = dspy.InputField(desc="User question to answer using the ontology.")
        context: str = dspy.InputField(desc="Ontology metadata (sense card), statistics, and navigation guidance. Consult the sense card to understand annotation conventions and formalism level.")

        # Reasoning fields for explicit think-act-verify-reflect cycles
        thinking: str = dspy.OutputField(
            desc="THINK: What you learned from exploration, what patterns/entities you found, what you'll do next. State discoveries and next steps."
        )
        verification: str = dspy.OutputField(
            desc="VERIFY: Check results match expectations. Do fields have correct types? Are URIs valid? Did query return expected columns?"
        )
        reflection: str = dspy.OutputField(
            desc="REFLECT: Self-critique before SUBMIT. Is answer grounded? Does evidence include actual data (not just metadata like lengths/counts)?"
        )

        # Final outputs
        answer: str = dspy.OutputField(desc="Final grounded answer in natural language.")
        sparql: str = dspy.OutputField(
            desc="SPARQL query executed (if used), otherwise empty string."
        )
        evidence: dict = dspy.OutputField(
            desc="Grounding evidence: URIs, result samples with actual data (sequences, labels, descriptions - not just counts or lengths)."
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
        try:
            pred = rlm(query=query, context=context)
        except AttributeError as e:
            # Check if this is a refusal error (DSPy tries to call .strip() on None)
            if "'NoneType' object has no attribute 'strip'" in str(e):
                # This is likely a model refusal - provide a better error message
                raise ValueError(
                    "Model refused to generate code for this query. "
                    "This may be due to content safety filters. "
                    "Try rephrasing the query to avoid potentially sensitive terms. "
                    f"Original error: {e}"
                ) from e
            # Re-raise other AttributeErrors
            raise

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

        # Detect convergence: DSPy RLM sets final_reasoning="Extract forced final output"
        # when max iterations are reached without successful SUBMIT call
        final_reasoning = getattr(pred, "final_reasoning", "")
        converged = final_reasoning != "Extract forced final output"

        # Build result with reasoning fields
        result = DSPyRLMResult(
            answer=pred.answer,
            sparql=pred.sparql if hasattr(pred, "sparql") else None,
            evidence=pred.evidence if hasattr(pred, "evidence") else {},
            trajectory=trajectory_dicts,
            iteration_count=len(trajectory),
            converged=converged,
            # Reasoning fields from Think-Act-Verify-Reflect cycles
            thinking=getattr(pred, "thinking", None),
            verification=getattr(pred, "verification", None),
            reflection=getattr(pred, "reflection", None),
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

            # Judge trajectory with Think-Act-Verify-Reflect reasoning fields
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


def run_dspy_rlm_with_tools(
    query: str,
    context: str,
    tools: dict[str, Any],
    *,
    ontology_name: str = "remote",
    ns: dict = None,
    max_iterations: int = 8,
    max_llm_calls: int = 16,
    verbose: bool = False,
    model: str = "anthropic/claude-sonnet-4-5-20250929",
    sub_model: str = "anthropic/claude-3-5-haiku-20241022",
    sense_card: Optional[str] = None,
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
    """Run DSPy RLM with custom tools (no ontology file required).

    This variant accepts pre-built tools and context directly, supporting remote
    SPARQL endpoints and other custom tool configurations without requiring a
    local ontology file.

    Args:
        query: User question to answer
        context: Context string describing the task and tools
        tools: Dict mapping tool names to callable functions
        ontology_name: Name for tracking/logging purposes (default "remote")
        ns: Optional namespace dict to merge with interpreter (default None)
        max_iterations: Maximum RLM iterations (default 8)
        max_llm_calls: Maximum LLM calls (default 16)
        verbose: Whether to print execution trace (default False)
        model: Root model for RLM (default Sonnet 4.5)
        sub_model: Sub-model for delegated reasoning (default Haiku)
        sense_card: Optional pre-built sense card to append to context. If provided,
                    will be injected after the main context string.
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

    Thread Safety:
        Not thread-safe due to NamespaceCodeInterpreter (shared _globals dict).
        For concurrent runs, call this function from separate threads/processes.
        Each call creates a fresh RLM instance internally.

    Examples:
        from rlm_runtime.tools import make_sparql_tools

        # Remote SPARQL with UniProt
        ns = {}
        tools = make_sparql_tools(
            endpoint="https://sparql.uniprot.org/sparql",
            ns=ns,
            max_results=100
        )
        context = "You are querying UniProt via SPARQL. Use tools to explore."

        result = run_dspy_rlm_with_tools(
            "What are Kinase proteins in humans?",
            context=context,
            tools=tools,
            ontology_name="uniprot",
            ns=ns,
            log_path="trajectory.jsonl"
        )

        # With memory backend
        from rlm_runtime.memory import SQLiteMemoryBackend
        backend = SQLiteMemoryBackend("memory.db")

        result = run_dspy_rlm_with_tools(
            "What is taxon 9606?",
            context=context,
            tools=tools,
            ontology_name="uniprot",
            ns=ns,
            memory_backend=backend,
            retrieve_memories=3,
            extract_memories=True
        )
    """
    if not os.environ.get("ANTHROPIC_API_KEY"):
        raise ValueError("ANTHROPIC_API_KEY must be set in environment")

    # Import DSPy (deferred to allow testing without API key)
    import dspy

    from rlm_runtime.interpreter import NamespaceCodeInterpreter

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
                ontology_name=ontology_name,
                max_iterations=max_iterations,
                model=model,
                sub_model=sub_model,
                has_memory=memory_backend is not None,
            )

            # Log tags for filtering
            log_run_tags(
                ontology_name=ontology_name,
                custom_tags=mlflow_tags,
            )

            if verbose:
                print(f"MLflow tracking active: experiment={mlflow_experiment or 'default'}, run={mlflow_run_id}")

    # Configure DSPy models and callbacks
    # Increased max_tokens to 4096 (from 1400) to prevent truncation of long outputs
    # with detailed answers, SPARQL, thinking, verification, reflection, AND evidence
    dspy.configure(
        lm=dspy.LM(model, temperature=0.2, max_tokens=4096, cache=False),
        callbacks=callbacks  # Always pass list (empty or populated)
    )
    sub_lm = dspy.LM(sub_model, temperature=0.2, max_tokens=2048, cache=False)

    # Record run in memory backend if provided
    if memory_backend and run_id:
        memory_backend.add_run(
            run_id,
            model=model,
            ontology_name=ontology_name,
            ontology_path="remote",  # No local file for remote endpoints
            notes=f"Query: {query}"
        )

        # Log run creation
        if memory_logger:
            memory_logger.log_run_creation(run_id, model, ontology_name)

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

    # Inject reasoning process guidance
    reasoning_guidance = """
## Reasoning Process

Each iteration should follow THINK → ACT → VERIFY → REFLECT cycles:

**THINK**: State what you learned and what you'll do next.
- 'I found Protein class with organism property linking to Taxon...'
- 'E. coli K-12 strains are siblings (materialized), so I'll use VALUES clause...'

**ACT**: Execute code (search, query, describe).

**VERIFY**: Check results match expectations (like running tests).
- 'Results have protein field ✓'
- 'Results have sequence field with amino acids ✓' (NOT just sequence_length!)
- 'Query returned expected columns ✓'

**REFLECT**: Self-critique before SUBMIT.
- 'Evidence includes actual sequences, not just metadata'
- 'All required fields are present with correct types'
- 'URIs are valid and grounded in results'

When you SUBMIT, include your final thinking, verification, and reflection.
Evidence MUST include actual data samples (sequences, labels, descriptions) NOT just counts or lengths.
"""
    context = context + "\n" + reasoning_guidance

    # Inject sense card if provided
    if sense_card:
        context = context + "\n\n## Ontology Affordances (Sense Card)\n" + sense_card

    # Inject memories into context if available
    if memory_context:
        context = context + "\n\n" + memory_context

    # Define typed signature with explicit reasoning fields (Think-Act-Verify-Reflect)
    class QueryConstructionSig(dspy.Signature):
        """Construct answer using bounded tools with explicit reasoning cycles.

        Follow THINK → ACT → VERIFY → REFLECT cycles to ensure grounded answers
        with consistent evidence formats.
        """

        query: str = dspy.InputField(desc="User question to answer.")
        context: str = dspy.InputField(desc="Task instructions, tool descriptions, and navigation guidance. If a sense card is provided, consult it to understand annotation conventions.")

        # Reasoning fields for explicit think-act-verify-reflect cycles
        thinking: str = dspy.OutputField(
            desc="THINK: What you learned from exploration, what patterns/entities you found, what you'll do next. State discoveries and next steps."
        )
        verification: str = dspy.OutputField(
            desc="VERIFY: Check results match expectations. Do fields have correct types? Are URIs valid? Did query return expected columns?"
        )
        reflection: str = dspy.OutputField(
            desc="REFLECT: Self-critique before SUBMIT. Is answer grounded? Does evidence include actual data (not just metadata like lengths/counts)?"
        )

        # Final outputs
        answer: str = dspy.OutputField(desc="Final grounded answer in natural language.")
        sparql: str = dspy.OutputField(
            desc="SPARQL query executed (if used), otherwise empty string."
        )
        evidence: dict = dspy.OutputField(
            desc="Grounding evidence: URIs, result samples with actual data (sequences, labels, descriptions - not just counts or lengths)."
        )

    # Create interpreter
    # Note: The tools already capture `ns` in their closures and write results back to it.
    # The interpreter doesn't need to know about the namespace dict.
    interpreter = NamespaceCodeInterpreter()

    # Create RLM
    rlm = dspy.RLM(
        QueryConstructionSig,
        max_iterations=max_iterations,
        max_llm_calls=max_llm_calls,
        verbose=verbose,
        tools=tools,
        sub_lm=sub_lm,
        interpreter=interpreter,
    )

    # Execute
    # Wrap execution in try/finally to ensure cleanup
    try:
        try:
            pred = rlm(query=query, context=context)
        except AttributeError as e:
            # Check if this is a refusal error (DSPy tries to call .strip() on None)
            if "'NoneType' object has no attribute 'strip'" in str(e):
                # This is likely a model refusal - provide a better error message
                raise ValueError(
                    "Model refused to generate code for this query. "
                    "This may be due to content safety filters. "
                    "Try rephrasing the query to avoid potentially sensitive terms. "
                    f"Original error: {e}"
                ) from e
            # Re-raise other AttributeErrors
            raise

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

        # Detect convergence: DSPy RLM sets final_reasoning="Extract forced final output"
        # when max iterations are reached without successful SUBMIT call
        final_reasoning = getattr(pred, "final_reasoning", "")
        converged = final_reasoning != "Extract forced final output"

        # Build result with reasoning fields
        result = DSPyRLMResult(
            answer=pred.answer,
            sparql=pred.sparql if hasattr(pred, "sparql") else None,
            evidence=pred.evidence if hasattr(pred, "evidence") else {},
            trajectory=trajectory_dicts,
            iteration_count=len(trajectory),
            converged=converged,
            # Reasoning fields from Think-Act-Verify-Reflect cycles
            thinking=getattr(pred, "thinking", None),
            verification=getattr(pred, "verification", None),
            reflection=getattr(pred, "reflection", None),
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

            # Judge trajectory with Think-Act-Verify-Reflect reasoning fields
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
                ontology_name=ontology_name,
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
