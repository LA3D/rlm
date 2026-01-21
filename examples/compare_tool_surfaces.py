"""Compare tool surface designs: Full tools vs Minimal tools.

Tests two approaches:
1. Full tools: search_entity, describe_entity, probe_relationships, sparql_select
2. Minimal tools: search_entity, sparql_select + enhanced sense card with SPARQL templates

Hypothesis: Minimal tools with better sense card guidance will be faster and more flexible.
"""

import os
import sys
from pathlib import Path
from typing import Optional

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from rlm_runtime.ontology import build_sense_card, format_sense_card
from rlm_runtime.engine.dspy_rlm import run_dspy_rlm_with_tools
from rlm_runtime.tools.ontology_tools import make_ontology_tools, make_search_entity_tool, make_sparql_select_tool
from rlm.ontology import GraphMeta
from rdflib import Graph


def run_with_full_tools(query: str, ontology_path: Path, test_name: str) -> Optional[dict]:
    """Run test with full tool surface (all 4 tools)."""
    print(f"\n{'='*70}")
    print(f"TEST: {test_name} (FULL TOOLS)")
    print(f"{'='*70}")

    # Load ontology
    g = Graph()
    g.parse(ontology_path)
    meta = GraphMeta(graph=g, name=ontology_path.stem)

    # Create FULL tool set
    tools = make_ontology_tools(meta, include_sparql=True)
    print(f"Tools available: {list(tools.keys())}")

    # Build sense card (standard format, no SPARQL templates)
    sense_card_obj = build_sense_card(str(ontology_path), ontology_path.stem)
    sense_card = format_sense_card(sense_card_obj, include_sparql_templates=False)

    # Build context
    context = f"{meta.summary()}\n\n{sense_card}"

    log_path = project_root / f"test_tools_full_{test_name}.jsonl"

    try:
        result = run_dspy_rlm_with_tools(
            query,
            context,
            tools,
            ns=meta.namespaces,
            max_iterations=10,
            max_llm_calls=20,
            log_path=str(log_path),
            verbose=False
        )

        metrics = {
            'approach': 'full_tools',
            'test_name': test_name,
            'iterations': result.iteration_count,
            'converged': result.converged,
            'answer_length': len(result.answer),
            'evidence_fields': len(result.evidence) if result.evidence else 0,
            'has_sparql': result.sparql is not None and len(result.sparql) > 0
        }

        print(f"  ✓ Iterations: {metrics['iterations']}")
        print(f"  ✓ Converged: {metrics['converged']}")
        print(f"  ✓ Answer: {metrics['answer_length']} chars")
        print(f"  ✓ Evidence: {metrics['evidence_fields']} fields")

        return metrics

    except Exception as e:
        print(f"  ✗ Test failed: {e}")
        import traceback
        traceback.print_exc()
        return None


def run_with_minimal_tools(query: str, ontology_path: Path, test_name: str) -> Optional[dict]:
    """Run test with minimal tool surface (search_entity + sparql_select) + enhanced sense card."""
    print(f"\n{'='*70}")
    print(f"TEST: {test_name} (MINIMAL TOOLS)")
    print(f"{'='*70}")

    # Load ontology
    g = Graph()
    g.parse(ontology_path)
    meta = GraphMeta(graph=g, name=ontology_path.stem)

    # Create MINIMAL tool set (only search + sparql)
    tools = {
        'search_entity': make_search_entity_tool(meta),
        'sparql_select': make_sparql_select_tool(meta)
    }
    print(f"Tools available: {list(tools.keys())}")

    # Build sense card WITH SPARQL templates
    sense_card_obj = build_sense_card(str(ontology_path), ontology_path.stem)
    sense_card = format_sense_card(sense_card_obj, include_sparql_templates=True)

    # Build context
    context = f"{meta.summary()}\n\n{sense_card}"

    log_path = project_root / f"test_tools_minimal_{test_name}.jsonl"

    try:
        result = run_dspy_rlm_with_tools(
            query,
            context,
            tools,
            ns=meta.namespaces,
            max_iterations=10,
            max_llm_calls=20,
            log_path=str(log_path),
            verbose=False
        )

        metrics = {
            'approach': 'minimal_tools',
            'test_name': test_name,
            'iterations': result.iteration_count,
            'converged': result.converged,
            'answer_length': len(result.answer),
            'evidence_fields': len(result.evidence) if result.evidence else 0,
            'has_sparql': result.sparql is not None and len(result.sparql) > 0
        }

        print(f"  ✓ Iterations: {metrics['iterations']}")
        print(f"  ✓ Converged: {metrics['converged']}")
        print(f"  ✓ Answer: {metrics['answer_length']} chars")
        print(f"  ✓ Evidence: {metrics['evidence_fields']} fields")

        return metrics

    except Exception as e:
        print(f"  ✗ Test failed: {e}")
        import traceback
        traceback.print_exc()
        return None


def main():
    print("=" * 80)
    print("Tool Surface Comparison: Full vs Minimal")
    print("=" * 80)

    # Check API key
    if not os.environ.get("ANTHROPIC_API_KEY"):
        print("ERROR: ANTHROPIC_API_KEY not set")
        return 1

    ontology_path = project_root / "ontology" / "prov.ttl"
    if not ontology_path.exists():
        print(f"ERROR: {ontology_path} not found")
        return 1

    # Test query
    query = "What is Activity in PROV? How does it relate to Entity and Agent?"

    print(f"\nQuery: {query}")
    print(f"Ontology: {ontology_path.name}")

    # Run both approaches
    full_metrics = run_with_full_tools(query, ontology_path, "prov_activity")
    minimal_metrics = run_with_minimal_tools(query, ontology_path, "prov_activity")

    # Comparison
    if full_metrics and minimal_metrics:
        print("\n" + "=" * 80)
        print("COMPARISON RESULTS")
        print("=" * 80)

        print(f"\nIteration count:")
        print(f"  Full tools:    {full_metrics['iterations']}")
        print(f"  Minimal tools: {minimal_metrics['iterations']}")

        iter_diff = full_metrics['iterations'] - minimal_metrics['iterations']
        if iter_diff > 0:
            print(f"  → Minimal tools saved {iter_diff} iterations ✓")
        elif iter_diff < 0:
            print(f"  → Minimal tools added {abs(iter_diff)} iterations")
        else:
            print(f"  → Same iteration count")

        print(f"\nConvergence:")
        print(f"  Full tools:    {full_metrics['converged']}")
        print(f"  Minimal tools: {minimal_metrics['converged']}")

        print(f"\nAnswer quality:")
        print(f"  Full tools:    {full_metrics['answer_length']} chars")
        print(f"  Minimal tools: {minimal_metrics['answer_length']} chars")

        print(f"\nEvidence collected:")
        print(f"  Full tools:    {full_metrics['evidence_fields']} fields")
        print(f"  Minimal tools: {minimal_metrics['evidence_fields']} fields")

        # Decision
        print("\n" + "=" * 80)
        print("ASSESSMENT")
        print("=" * 80)

        improvements = []
        regressions = []

        if iter_diff > 0:
            improvements.append(f"Reduced iterations by {iter_diff}")
        elif iter_diff < 0:
            regressions.append(f"Increased iterations by {abs(iter_diff)}")

        if minimal_metrics['converged'] and not full_metrics['converged']:
            improvements.append("Achieved convergence (full tools did not)")
        elif not minimal_metrics['converged'] and full_metrics['converged']:
            regressions.append("Failed to converge (full tools did)")

        if improvements:
            print("\n✓ Improvements with minimal tools:")
            for imp in improvements:
                print(f"  + {imp}")

        if regressions:
            print("\n✗ Regressions with minimal tools:")
            for reg in regressions:
                print(f"  - {reg}")

        if not regressions:
            print("\n" + "=" * 80)
            print("✓ VERDICT: Minimal tools + enhanced sense card are effective")
            print("Recommendation: Adopt minimal tool surface")
            print("=" * 80)
            return 0
        else:
            print("\n" + "=" * 80)
            print("⚠ VERDICT: Mixed results - review trade-offs")
            print("=" * 80)
            return 0

    return 1


if __name__ == "__main__":
    sys.exit(main())
