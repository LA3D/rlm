"""DSPy RLM engine for ontology query construction.

Provides structured query construction with typed outputs, bounded tools,
and host-Python code execution.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any
import os


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
) -> DSPyRLMResult:
    """Run DSPy RLM for ontology query construction.

    Args:
        query: User question to answer
        ontology_path: Path to ontology file (TTL/RDF)
        max_iterations: Maximum RLM iterations (default 8)
        max_llm_calls: Maximum LLM calls (default 16)
        verbose: Whether to print execution trace (default False)
        model: Root model for RLM (default Sonnet 4.5)
        sub_model: Sub-model for delegated reasoning (default Haiku)

    Returns:
        DSPyRLMResult with answer, sparql, evidence, trajectory

    Raises:
        ValueError: If ANTHROPIC_API_KEY not set
        FileNotFoundError: If ontology_path doesn't exist
    """
    if not os.environ.get("ANTHROPIC_API_KEY"):
        raise ValueError("ANTHROPIC_API_KEY must be set in environment")

    ontology_path = Path(ontology_path)
    if not ontology_path.exists():
        raise FileNotFoundError(f"Ontology not found: {ontology_path}")

    # Import DSPy (deferred to allow testing without API key)
    import dspy
    from rdflib import Graph

    from rlm.ontology import GraphMeta
    from rlm_runtime.interpreter import NamespaceCodeInterpreter
    from rlm_runtime.tools import make_ontology_tools

    # Configure DSPy models
    dspy.configure(lm=dspy.LM(model, temperature=0.2, max_tokens=1400, cache=False))
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

    onto_name = ontology_path.stem
    meta = GraphMeta(graph=g, name=onto_name)

    # Create bounded tools
    tools = make_ontology_tools(meta, include_sparql=True)

    # Build context
    context = "\n".join(
        [
            "You are exploring an RDF ontology via bounded tools.",
            "Do not dump large structures. Use tools to discover entities, then SUBMIT your answer.",
            "",
            meta.summary(),
            "",
            "Goal: Answer the query grounded in retrieved evidence.",
        ]
    )

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
    return DSPyRLMResult(
        answer=pred.answer,
        sparql=pred.sparql if hasattr(pred, "sparql") else None,
        evidence=pred.evidence if hasattr(pred, "evidence") else {},
        trajectory=trajectory_dicts,
        iteration_count=len(trajectory),
        converged=True,  # DSPy RLM always returns something
    )
