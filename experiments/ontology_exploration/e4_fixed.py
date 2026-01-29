#!/usr/bin/env python3
"""E4 Fixed: Guide-Based Query Construction (Using Guide Summary)

Fixes the original E4 bug where passing 41KB JSON as input field caused issues.
Instead, we pass a concise guide summary extracted from the full guide.

This tests whether having pre-built semantic knowledge helps query construction.
"""

import sys
import os
from pathlib import Path
from datetime import datetime
import json

project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

import dspy
from rdflib import Graph, RDF, RDFS, OWL, Namespace
from rlm_runtime.interpreter.namespace_interpreter import NamespaceCodeInterpreter

# Single test query for now
TEST_QUERY = "What activities can generate entities?"

def create_guide_summary(guide: dict) -> str:
    """Extract concise summary from full guide."""
    summary_parts = []

    # Overview
    if 'ontology_overview' in guide:
        ov = guide['ontology_overview']
        summary_parts.append(f"{ov['name']}: {ov['purpose']}")

    # Core classes from first category
    if 'semantic_categories' in guide and len(guide['semantic_categories']) > 0:
        core = guide['semantic_categories'][0]
        summary_parts.append(f"\nCore Classes: {', '.join([c['name'] for c in core['classes'][:5]])}")

    # Key properties from properties section
    if 'properties' in guide and 'object_properties' in guide['properties']:
        props = guide['properties']['object_properties'][:8]
        summary_parts.append("\nKey Properties:")
        for p in props:
            summary_parts.append(f"- {p['name']}: {p['description'][:80] if p.get('description') else 'Links entities'}")

    # Query patterns
    if 'query_patterns' in guide:
        summary_parts.append(f"\nCommon Patterns: {len(guide['query_patterns'])} templates available")
        for qp in guide['query_patterns'][:2]:
            summary_parts.append(f"- {qp['name']}: {qp['description'][:60]}")

    return '\n'.join(summary_parts)


def run_query_with_guide(query_text: str, guide_summary: str, ont, lm):
    """Run with guide summary."""
    class QuerySig(dspy.Signature):
        """Construct SPARQL query with guide assistance."""
        question: str = dspy.InputField()
        guide: str = dspy.InputField(desc="Ontology guide summary")
        ont: object = dspy.InputField(desc="rdflib Graph")

        sparql_query: str = dspy.OutputField()
        explanation: str = dspy.OutputField()

    interpreter = NamespaceCodeInterpreter(result_truncation_limit=5000)
    tools = {'RDF': RDF, 'RDFS': RDFS, 'OWL': OWL, 'Namespace': Namespace}

    rlm = dspy.RLM(QuerySig, max_iterations=10, max_llm_calls=8, verbose=False,
                   interpreter=interpreter, tools=tools)

    result = rlm(question=query_text, guide=guide_summary, ont=ont)
    return result


def run_query_without_guide(query_text: str, ont, lm):
    """Run without guide (baseline)."""
    class QuerySig(dspy.Signature):
        """Construct SPARQL query by exploring ontology."""
        question: str = dspy.InputField()
        ont: object = dspy.InputField(desc="rdflib Graph")

        sparql_query: str = dspy.OutputField()
        explanation: str = dspy.OutputField()

    interpreter = NamespaceCodeInterpreter(result_truncation_limit=5000)
    tools = {'RDF': RDF, 'RDFS': RDFS, 'OWL': OWL, 'Namespace': Namespace}

    rlm = dspy.RLM(QuerySig, max_iterations=10, max_llm_calls=8, verbose=False,
                   interpreter=interpreter, tools=tools)

    result = rlm(question=query_text, ont=ont)
    return result


def main():
    print("\n" + "=" * 70)
    print("E4 FIXED: GUIDE-BASED QUERY CONSTRUCTION")
    print("=" * 70)
    print(f"Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")

    # Load ontology
    print("Loading PROV ontology...")
    ontology_path = project_root / "ontology" / "prov.ttl"
    ont = Graph()
    ont.parse(ontology_path)
    print(f"✓ Loaded {len(ont)} triples\n")

    # Load guide and create summary
    print("Loading guide...")
    guide_path = project_root / "experiments" / "ontology_exploration" / "e3_retry_guide.json"
    with open(guide_path, 'r') as f:
        guide = json.load(f)

    guide_summary = create_guide_summary(guide)
    print(f"✓ Guide summary created ({len(guide_summary)} chars)")
    print(f"  Full guide: {len(json.dumps(guide))} chars")
    print(f"  Compression: {len(guide_summary) / len(json.dumps(guide)) * 100:.1f}%\n")

    # Configure DSPy (disable caching to ensure fresh runs)
    lm = dspy.LM("anthropic/claude-sonnet-4-5-20250929", max_tokens=4096, cache=False)
    dspy.configure(lm=lm)

    print("=" * 70)
    print(f"QUERY: {TEST_QUERY}")
    print("=" * 70)
    print()

    # Condition A: WITHOUT guide
    print("-" * 70)
    print("CONDITION A: WITHOUT GUIDE (Baseline)")
    print("-" * 70)

    lm.history = []
    start = datetime.now()

    try:
        result_no_guide = run_query_without_guide(TEST_QUERY, ont, lm)
        elapsed_no = (datetime.now() - start).total_seconds()

        calls_no = len(lm.history)
        input_tokens_no = 0
        output_tokens_no = 0
        for call in lm.history:
            if isinstance(call, dict) and 'usage' in call:
                usage = call['usage']
                input_tokens_no += usage.get('prompt_tokens', 0)
                output_tokens_no += usage.get('completion_tokens', 0)
        tokens_no = input_tokens_no + output_tokens_no
        cost_no = (input_tokens_no / 1_000_000 * 3.0 + output_tokens_no / 1_000_000 * 15.0)

        print(f"✓ Completed in {elapsed_no:.1f}s")
        print(f"  LM calls: {calls_no}")
        print(f"  Tokens: {tokens_no:,}")
        print(f"  Cost: ${cost_no:.4f}")
        print(f"  SPARQL: {result_no_guide.sparql_query[:80]}...")

    except Exception as e:
        print(f"✗ Failed: {e}")
        result_no_guide = None
        elapsed_no = 0
        calls_no = 0
        tokens_no = 0
        cost_no = 0

    print()

    # Condition B: WITH guide
    print("-" * 70)
    print("CONDITION B: WITH GUIDE")
    print("-" * 70)

    lm.history = []
    start = datetime.now()

    try:
        result_with_guide = run_query_with_guide(TEST_QUERY, guide_summary, ont, lm)
        elapsed_with = (datetime.now() - start).total_seconds()

        calls_with = len(lm.history)
        input_tokens_with = 0
        output_tokens_with = 0
        for call in lm.history:
            if isinstance(call, dict) and 'usage' in call:
                usage = call['usage']
                input_tokens_with += usage.get('prompt_tokens', 0)
                output_tokens_with += usage.get('completion_tokens', 0)
        tokens_with = input_tokens_with + output_tokens_with
        cost_with = (input_tokens_with / 1_000_000 * 3.0 + output_tokens_with / 1_000_000 * 15.0)

        print(f"✓ Completed in {elapsed_with:.1f}s")
        print(f"  LM calls: {calls_with}")
        print(f"  Tokens: {tokens_with:,}")
        print(f"  Cost: ${cost_with:.4f}")
        print(f"  SPARQL: {result_with_guide.sparql_query[:80]}...")

    except Exception as e:
        print(f"✗ Failed: {e}")
        result_with_guide = None
        elapsed_with = 0
        calls_with = 0
        tokens_with = 0
        cost_with = 0

    print()

    # Comparison
    if result_no_guide and result_with_guide:
        print("-" * 70)
        print("COMPARISON")
        print("-" * 70)

        time_pct = (elapsed_with - elapsed_no) / elapsed_no * 100 if elapsed_no > 0 else 0
        tokens_pct = (tokens_with - tokens_no) / tokens_no * 100 if tokens_no > 0 else 0
        cost_pct = (cost_with - cost_no) / cost_no * 100 if cost_no > 0 else 0

        print(f"Time: {elapsed_no:.1f}s → {elapsed_with:.1f}s "
              f"({elapsed_with - elapsed_no:+.1f}s, {time_pct:+.1f}%)")
        print(f"LM calls: {calls_no} → {calls_with} ({calls_with - calls_no:+d})")
        print(f"Tokens: {tokens_no:,} → {tokens_with:,} "
              f"({tokens_with - tokens_no:+,}, {tokens_pct:+.1f}%)")
        print(f"Cost: ${cost_no:.4f} → ${cost_with:.4f} "
              f"(${cost_with - cost_no:+.4f}, {cost_pct:+.1f}%)")

        # Break-even
        guide_cost = 0.2491  # E3-Retry
        savings_per_query = cost_no - cost_with
        if savings_per_query > 0:
            break_even = guide_cost / savings_per_query
            print(f"\nBreak-even: {break_even:.1f} queries (guide cost ${guide_cost:.4f})")
        else:
            print(f"\nNo per-query savings (guide increased cost)")

    print()
    print("=" * 70)
    print("E4 COMPLETED")
    print("=" * 70)

    # Save results
    results = {
        'query': TEST_QUERY,
        'timestamp': datetime.now().isoformat(),
        'guide_summary_length': len(guide_summary),
        'condition_a_no_guide': {
            'success': result_no_guide is not None,
            'elapsed_seconds': elapsed_no,
            'lm_calls': calls_no,
            'tokens': tokens_no,
            'cost_usd': cost_no,
            'sparql': result_no_guide.sparql_query if result_no_guide else None
        },
        'condition_b_with_guide': {
            'success': result_with_guide is not None,
            'elapsed_seconds': elapsed_with,
            'lm_calls': calls_with,
            'tokens': tokens_with,
            'cost_usd': cost_with,
            'sparql': result_with_guide.sparql_query if result_with_guide else None
        }
    }

    results_path = project_root / "experiments" / "ontology_exploration" / "e4_results.json"
    with open(results_path, 'w') as f:
        json.dump(results, f, indent=2)

    print(f"Results saved to: {results_path}")


if __name__ == "__main__":
    main()
