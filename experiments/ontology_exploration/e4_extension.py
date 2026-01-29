#!/usr/bin/env python3
"""E4 Extension: Multiple Query Types

Tests guide effectiveness across 3 query complexity levels:
1. Simple: Direct property lookup
2. Relationship: Multi-hop navigation
3. Semantic: Conceptual understanding

Hypothesis: Guide should help MORE with complex queries.
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

# Three test queries of increasing complexity
TEST_QUERIES = [
    {
        'id': 'simple',
        'question': "What activities can generate entities?",
        'complexity': 'Simple - direct property lookup'
    },
    {
        'id': 'relationship',
        'question': "How are agents related to activities?",
        'complexity': 'Relationship - multi-hop navigation'
    },
    {
        'id': 'semantic',
        'question': "What is the difference between Generation and Derivation?",
        'complexity': 'Semantic - conceptual understanding'
    }
]

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


def extract_metrics(lm):
    """Extract metrics from LM history."""
    calls = len(lm.history)
    input_tokens = 0
    output_tokens = 0
    for call in lm.history:
        if isinstance(call, dict) and 'usage' in call:
            usage = call['usage']
            input_tokens += usage.get('prompt_tokens', 0)
            output_tokens += usage.get('completion_tokens', 0)

    tokens = input_tokens + output_tokens
    cost = (input_tokens / 1_000_000 * 3.0 + output_tokens / 1_000_000 * 15.0)

    return {
        'lm_calls': calls,
        'input_tokens': input_tokens,
        'output_tokens': output_tokens,
        'total_tokens': tokens,
        'cost_usd': cost
    }


def main():
    print("\n" + "=" * 70)
    print("E4 EXTENSION: MULTIPLE QUERY TYPES")
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

    # Store results for all queries
    query_results = []

    # Run each query
    for i, test_query in enumerate(TEST_QUERIES, 1):
        query_id = test_query['id']
        question = test_query['question']
        complexity = test_query['complexity']

        print("=" * 70)
        print(f"QUERY {i}/3: {query_id.upper()}")
        print(f"Question: {question}")
        print(f"Complexity: {complexity}")
        print("=" * 70)
        print()

        # Condition A: WITHOUT guide
        print("-" * 70)
        print("CONDITION A: WITHOUT GUIDE (Baseline)")
        print("-" * 70)

        lm.history = []
        start = datetime.now()

        try:
            result_no_guide = run_query_without_guide(question, ont, lm)
            elapsed_no = (datetime.now() - start).total_seconds()
            metrics_no = extract_metrics(lm)

            print(f"✓ Completed in {elapsed_no:.1f}s")
            print(f"  LM calls: {metrics_no['lm_calls']}")
            print(f"  Tokens: {metrics_no['total_tokens']:,}")
            print(f"  Cost: ${metrics_no['cost_usd']:.4f}")
            print(f"  SPARQL: {result_no_guide.sparql_query[:80]}...")

            result_no = {
                'success': True,
                'elapsed_seconds': elapsed_no,
                'sparql': result_no_guide.sparql_query,
                'explanation': result_no_guide.explanation,
                **metrics_no
            }

        except Exception as e:
            print(f"✗ Failed: {e}")
            result_no = {
                'success': False,
                'elapsed_seconds': 0,
                'lm_calls': 0,
                'total_tokens': 0,
                'cost_usd': 0,
                'sparql': None,
                'explanation': None,
                'error': str(e)
            }

        print()

        # Condition B: WITH guide
        print("-" * 70)
        print("CONDITION B: WITH GUIDE")
        print("-" * 70)

        lm.history = []
        start = datetime.now()

        try:
            result_with_guide = run_query_with_guide(question, guide_summary, ont, lm)
            elapsed_with = (datetime.now() - start).total_seconds()
            metrics_with = extract_metrics(lm)

            print(f"✓ Completed in {elapsed_with:.1f}s")
            print(f"  LM calls: {metrics_with['lm_calls']}")
            print(f"  Tokens: {metrics_with['total_tokens']:,}")
            print(f"  Cost: ${metrics_with['cost_usd']:.4f}")
            print(f"  SPARQL: {result_with_guide.sparql_query[:80]}...")

            result_with = {
                'success': True,
                'elapsed_seconds': elapsed_with,
                'sparql': result_with_guide.sparql_query,
                'explanation': result_with_guide.explanation,
                **metrics_with
            }

        except Exception as e:
            print(f"✗ Failed: {e}")
            result_with = {
                'success': False,
                'elapsed_seconds': 0,
                'lm_calls': 0,
                'total_tokens': 0,
                'cost_usd': 0,
                'sparql': None,
                'explanation': None,
                'error': str(e)
            }

        print()

        # Per-query comparison
        if result_no['success'] and result_with['success']:
            print("-" * 70)
            print("COMPARISON")
            print("-" * 70)

            time_diff = result_with['elapsed_seconds'] - result_no['elapsed_seconds']
            time_pct = (time_diff / result_no['elapsed_seconds'] * 100) if result_no['elapsed_seconds'] > 0 else 0

            tokens_diff = result_with['total_tokens'] - result_no['total_tokens']
            tokens_pct = (tokens_diff / result_no['total_tokens'] * 100) if result_no['total_tokens'] > 0 else 0

            cost_diff = result_with['cost_usd'] - result_no['cost_usd']
            cost_pct = (cost_diff / result_no['cost_usd'] * 100) if result_no['cost_usd'] > 0 else 0

            calls_diff = result_with['lm_calls'] - result_no['lm_calls']

            print(f"Time: {result_no['elapsed_seconds']:.1f}s → {result_with['elapsed_seconds']:.1f}s "
                  f"({time_diff:+.1f}s, {time_pct:+.1f}%)")
            print(f"LM calls: {result_no['lm_calls']} → {result_with['lm_calls']} ({calls_diff:+d})")
            print(f"Tokens: {result_no['total_tokens']:,} → {result_with['total_tokens']:,} "
                  f"({tokens_diff:+,}, {tokens_pct:+.1f}%)")
            print(f"Cost: ${result_no['cost_usd']:.4f} → ${result_with['cost_usd']:.4f} "
                  f"(${cost_diff:+.4f}, {cost_pct:+.1f}%)")

        print()

        # Store results for this query
        query_results.append({
            'query_id': query_id,
            'question': question,
            'complexity': complexity,
            'condition_a_no_guide': result_no,
            'condition_b_with_guide': result_with
        })

    # Aggregate results
    print("=" * 70)
    print("AGGREGATE RESULTS")
    print("=" * 70)
    print()

    total_time_no = sum(q['condition_a_no_guide']['elapsed_seconds'] for q in query_results if q['condition_a_no_guide']['success'])
    total_time_with = sum(q['condition_b_with_guide']['elapsed_seconds'] for q in query_results if q['condition_b_with_guide']['success'])

    total_cost_no = sum(q['condition_a_no_guide']['cost_usd'] for q in query_results if q['condition_a_no_guide']['success'])
    total_cost_with = sum(q['condition_b_with_guide']['cost_usd'] for q in query_results if q['condition_b_with_guide']['success'])

    total_tokens_no = sum(q['condition_a_no_guide']['total_tokens'] for q in query_results if q['condition_a_no_guide']['success'])
    total_tokens_with = sum(q['condition_b_with_guide']['total_tokens'] for q in query_results if q['condition_b_with_guide']['success'])

    total_calls_no = sum(q['condition_a_no_guide']['lm_calls'] for q in query_results if q['condition_a_no_guide']['success'])
    total_calls_with = sum(q['condition_b_with_guide']['lm_calls'] for q in query_results if q['condition_b_with_guide']['success'])

    successful_queries = sum(1 for q in query_results if q['condition_a_no_guide']['success'] and q['condition_b_with_guide']['success'])

    print(f"Successful queries: {successful_queries}/{len(TEST_QUERIES)}")
    print()

    if successful_queries > 0:
        avg_time_no = total_time_no / successful_queries
        avg_time_with = total_time_with / successful_queries
        time_improvement = (avg_time_with - avg_time_no) / avg_time_no * 100 if avg_time_no > 0 else 0

        avg_cost_no = total_cost_no / successful_queries
        avg_cost_with = total_cost_with / successful_queries
        cost_improvement = (avg_cost_with - avg_cost_no) / avg_cost_no * 100 if avg_cost_no > 0 else 0

        avg_tokens_no = total_tokens_no / successful_queries
        avg_tokens_with = total_tokens_with / successful_queries
        token_improvement = (avg_tokens_with - avg_tokens_no) / avg_tokens_no * 100 if avg_tokens_no > 0 else 0

        avg_calls_no = total_calls_no / successful_queries
        avg_calls_with = total_calls_with / successful_queries

        print("TOTAL:")
        print(f"  Time: {total_time_no:.1f}s → {total_time_with:.1f}s ({total_time_with - total_time_no:+.1f}s)")
        print(f"  Cost: ${total_cost_no:.4f} → ${total_cost_with:.4f} (${total_cost_with - total_cost_no:+.4f})")
        print(f"  Tokens: {total_tokens_no:,} → {total_tokens_with:,} ({total_tokens_with - total_tokens_no:+,})")
        print(f"  LM calls: {total_calls_no} → {total_calls_with} ({total_calls_with - total_calls_no:+d})")
        print()

        print("AVERAGE PER QUERY:")
        print(f"  Time: {avg_time_no:.1f}s → {avg_time_with:.1f}s ({time_improvement:+.1f}%)")
        print(f"  Cost: ${avg_cost_no:.4f} → ${avg_cost_with:.4f} ({cost_improvement:+.1f}%)")
        print(f"  Tokens: {avg_tokens_no:,.0f} → {avg_tokens_with:,.0f} ({token_improvement:+.1f}%)")
        print(f"  LM calls: {avg_calls_no:.1f} → {avg_calls_with:.1f}")
        print()

        # Break-even analysis
        guide_cost = 0.2491  # E3-Retry
        savings_per_query = avg_cost_no - avg_cost_with

        print("BREAK-EVEN ANALYSIS:")
        print(f"  Guide creation cost: ${guide_cost:.4f}")
        print(f"  Savings per query: ${savings_per_query:.4f}")

        if savings_per_query > 0:
            break_even = guide_cost / savings_per_query
            print(f"  Break-even point: {break_even:.1f} queries")
        else:
            print(f"  No per-query savings (guide increased cost)")

    print()
    print("=" * 70)
    print("E4 EXTENSION COMPLETED")
    print("=" * 70)

    # Save results
    results = {
        'timestamp': datetime.now().isoformat(),
        'guide_summary_length': len(guide_summary),
        'guide_cost_usd': 0.2491,
        'queries': query_results,
        'aggregate': {
            'successful_queries': successful_queries,
            'total_queries': len(TEST_QUERIES),
            'total_time_no_guide': total_time_no,
            'total_time_with_guide': total_time_with,
            'total_cost_no_guide': total_cost_no,
            'total_cost_with_guide': total_cost_with,
            'total_tokens_no_guide': total_tokens_no,
            'total_tokens_with_guide': total_tokens_with,
            'total_calls_no_guide': total_calls_no,
            'total_calls_with_guide': total_calls_with,
            'avg_time_no_guide': avg_time_no if successful_queries > 0 else 0,
            'avg_time_with_guide': avg_time_with if successful_queries > 0 else 0,
            'avg_cost_no_guide': avg_cost_no if successful_queries > 0 else 0,
            'avg_cost_with_guide': avg_cost_with if successful_queries > 0 else 0,
            'avg_tokens_no_guide': avg_tokens_no if successful_queries > 0 else 0,
            'avg_tokens_with_guide': avg_tokens_with if successful_queries > 0 else 0,
            'savings_per_query': savings_per_query if successful_queries > 0 else 0,
            'break_even_queries': (0.2491 / savings_per_query) if (successful_queries > 0 and savings_per_query > 0) else None
        }
    }

    results_path = project_root / "experiments" / "ontology_exploration" / "e4_extension_results.json"
    with open(results_path, 'w') as f:
        json.dump(results, f, indent=2)

    print(f"Results saved to: {results_path}")


if __name__ == "__main__":
    main()
