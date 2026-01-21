"""Test minimal tool surface across diverse ontologies.

Tests minimal tools (search_entity + sparql_select + SPARQL templates) with:
1. PROV - OWL-DL, uses custom prov:definition
2. SKOS - RDFS+, uses skos:definition + rdfs:comment
3. SystemsLite - OWL-DL foundational ontology, uses rdfs:comment
4. VOID - RDFS, uses dcterms:description

This verifies minimal tools work across different metadata conventions.
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
from rlm_runtime.tools.ontology_tools import make_search_entity_tool, make_sparql_select_tool
from rlm.ontology import GraphMeta
from rdflib import Graph


def test_ontology(
    name: str,
    ontology_path: Path,
    query: str,
    expected_term: str
) -> Optional[dict]:
    """Test minimal tools with a specific ontology.

    Args:
        name: Ontology name for logging
        ontology_path: Path to ontology file
        query: Test query
        expected_term: Term expected in answer (for quality check)

    Returns:
        Metrics dict or None on failure
    """
    print(f"\n{'='*80}")
    print(f"Testing: {name}")
    print(f"{'='*80}")
    print(f"Query: {query}")

    if not ontology_path.exists():
        print(f"  ✗ Ontology not found: {ontology_path}")
        return None

    # Load ontology
    g = Graph()
    g.parse(ontology_path)
    meta = GraphMeta(graph=g, name=ontology_path.stem)

    # Create MINIMAL tool set (only search + sparql)
    tools = {
        'search_entity': make_search_entity_tool(meta),
        'sparql_select': make_sparql_select_tool(meta)
    }

    # Build sense card WITH SPARQL templates
    sense_card_obj = build_sense_card(str(ontology_path), name)
    sense_card = format_sense_card(sense_card_obj, include_sparql_templates=True)

    print(f"\nSense card preview:")
    print(f"  Description property: {sense_card_obj.metadata.primary_desc_prop()}")
    print(f"  Label property: {sense_card_obj.metadata.primary_label_prop()}")
    print(f"  Formalism: {sense_card_obj.formalism.level}")
    print(f"  Triples: {sense_card_obj.triple_count:,}")

    # Build context
    context = f"{meta.summary()}\n\n{sense_card}"

    log_path = project_root / f"test_minimal_{name.lower().replace(' ', '_')}.jsonl"

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

        # Check if expected term is in answer
        answer_quality = expected_term.lower() in result.answer.lower()

        metrics = {
            'ontology': name,
            'iterations': result.iteration_count,
            'converged': result.converged,
            'answer_length': len(result.answer),
            'evidence_fields': len(result.evidence) if result.evidence else 0,
            'has_sparql': result.sparql is not None and len(result.sparql) > 0,
            'found_expected_term': answer_quality
        }

        print(f"\n  ✓ Iterations: {metrics['iterations']}")
        print(f"  ✓ Converged: {metrics['converged']}")
        print(f"  ✓ Answer: {metrics['answer_length']} chars")
        print(f"  ✓ Evidence: {metrics['evidence_fields']} fields")
        print(f"  ✓ Expected term '{expected_term}' found: {answer_quality}")

        return metrics

    except Exception as e:
        print(f"  ✗ Test failed: {e}")
        import traceback
        traceback.print_exc()
        return None


def main():
    print("=" * 80)
    print("Minimal Tool Surface: Multi-Ontology Test")
    print("=" * 80)
    print("Testing: search_entity + sparql_select + SPARQL templates")

    # Check API key
    if not os.environ.get("ANTHROPIC_API_KEY"):
        print("ERROR: ANTHROPIC_API_KEY not set")
        return 1

    # Define test cases with diverse ontologies
    test_cases = [
        {
            'name': 'PROV',
            'path': project_root / 'ontology' / 'prov.ttl',
            'query': 'What is Activity in PROV?',
            'expected': 'period of time'
        },
        {
            'name': 'SKOS',
            'path': project_root / 'ontology' / 'skos.ttl',
            'query': 'What is a Concept in SKOS?',
            'expected': 'idea or notion'
        },
        {
            'name': 'SystemsLite',
            'path': project_root / 'ontology' / 'dul' / 'SystemsLite.ttl',
            'query': 'What is a System in SystemsLite?',
            'expected': 'component'
        },
        {
            'name': 'VOID',
            'path': project_root / 'ontology' / 'void_official.ttl',
            'query': 'What is a Dataset in VOID?',
            'expected': 'RDF'
        },
    ]

    # Run tests
    results = []
    for test in test_cases:
        result = test_ontology(
            test['name'],
            test['path'],
            test['query'],
            test['expected']
        )
        if result:
            results.append(result)

    # Summary
    if results:
        print("\n" + "=" * 80)
        print("SUMMARY RESULTS")
        print("=" * 80)

        total_iterations = sum(r['iterations'] for r in results)
        avg_iterations = total_iterations / len(results)
        converged_count = sum(1 for r in results if r['converged'])
        quality_count = sum(1 for r in results if r['found_expected_term'])

        print(f"\nTests run: {len(results)}/{len(test_cases)}")
        print(f"Convergence rate: {converged_count}/{len(results)} ({100*converged_count/len(results):.0f}%)")
        print(f"Quality rate: {quality_count}/{len(results)} ({100*quality_count/len(results):.0f}%)")
        print(f"Average iterations: {avg_iterations:.1f}")

        print("\nPer-ontology breakdown:")
        print(f"{'Ontology':<15} {'Iterations':<12} {'Converged':<12} {'Quality'}")
        print("-" * 60)
        for r in results:
            conv_mark = "✓" if r['converged'] else "✗"
            qual_mark = "✓" if r['found_expected_term'] else "✗"
            print(f"{r['ontology']:<15} {r['iterations']:<12} {conv_mark:<12} {qual_mark}")

        # Decision
        print("\n" + "=" * 80)
        if converged_count == len(results) and quality_count >= len(results) * 0.75:
            print("✓ VERDICT: Minimal tools work well across diverse ontologies")
            print("Recommendation: Adopt minimal tool surface")
            return 0
        else:
            print("⚠ VERDICT: Some tests failed - review failures")
            return 1

    return 1


if __name__ == "__main__":
    sys.exit(main())
