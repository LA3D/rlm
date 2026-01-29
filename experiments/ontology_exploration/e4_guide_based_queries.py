#!/usr/bin/env python3
"""E4: Guide-Based Query Construction

Hypothesis: Pre-built ontology guide (from E3-Retry) reduces query construction
cost and iterations while maintaining quality.

Validates the two-phase workflow:
- Phase 1: One-time exploration ($0.25) → Rich guide
- Phase 2: Many queries with guide (~$0.01-0.05 each)

Design:
- Condition A (Baseline): Query agent with NO guide (explores from scratch)
- Condition B (With Guide): Query agent WITH E3-Retry guide

Test Queries (increasing complexity):
1. Simple: "What activities can generate entities?"
2. Relationship: "How are agents related to activities?"
3. Semantic: "What is the difference between Generation and Derivation?"

Measures:
- Cost (tokens, $)
- Iterations (LM calls)
- Guide usage (does CoT reference guide?)
- Query correctness (valid SPARQL)
- Exploration overhead (how much ontology scanning)

Success Criteria:
- Guide references appear in reasoning
- Reduced exploration vs baseline
- Comparable/better query quality
- Cost savings (if >10 queries, amortizes guide cost)

Usage:
    source ~/uvws/.venv/bin/activate
    python experiments/ontology_exploration/e4_guide_based_queries.py
"""

import sys
import os
from pathlib import Path
from datetime import datetime
import json

# Add project root
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

if not os.environ.get("ANTHROPIC_API_KEY"):
    print("ERROR: Set ANTHROPIC_API_KEY")
    sys.exit(1)


# Test queries
TEST_QUERIES = [
    {
        'id': 'q1_simple',
        'query': 'What activities can generate entities?',
        'complexity': 'simple',
        'expected_sparql_pattern': 'prov:generated|prov:wasGeneratedBy',
        'description': 'Tests basic property lookup'
    },
    {
        'id': 'q2_relationship',
        'query': 'How are agents related to activities?',
        'complexity': 'relationship',
        'expected_sparql_pattern': 'prov:wasAssociatedWith|prov:qualifiedAssociation',
        'description': 'Tests multiple property exploration'
    },
    {
        'id': 'q3_semantic',
        'query': 'What is the difference between Generation and Derivation?',
        'complexity': 'semantic',
        'expected_sparql_pattern': 'prov:Generation|prov:Derivation',
        'description': 'Tests conceptual understanding'
    }
]


def run_query_with_guide(query_text: str, guide_content: dict, ont, lm, verbose=False):
    """Run query construction WITH guide."""
    import dspy
    from rdflib import RDF, RDFS, OWL, Namespace
    from rlm_runtime.interpreter.namespace_interpreter import NamespaceCodeInterpreter

    # Define signature for query construction
    class QueryConstructionSig(dspy.Signature):
        """Construct a SPARQL query to answer a question about an ontology.

        You have access to:
        - `ont`: The loaded rdflib Graph
        - `guide`: Pre-built ontology guide with semantic categories, use cases, query patterns
        - RDF, RDFS, OWL namespaces
        """

        question: str = dspy.InputField(desc="The question to answer")
        guide: str = dspy.InputField(desc="Pre-built ontology guide (JSON)")
        ont: object = dspy.InputField(desc="The loaded rdflib Graph object")

        sparql_query: str = dspy.OutputField(desc="SPARQL query that answers the question")
        explanation: str = dspy.OutputField(desc="Explanation of how the query works")

    # Create interpreter
    interpreter = NamespaceCodeInterpreter(result_truncation_limit=5000)

    # Tools
    tools = {
        'RDF': RDF,
        'RDFS': RDFS,
        'OWL': OWL,
        'Namespace': Namespace,
    }

    # Create RLM
    rlm = dspy.RLM(
        QueryConstructionSig,
        max_iterations=10,
        max_llm_calls=8,
        verbose=verbose,
        interpreter=interpreter,
        tools=tools,
    )

    # Prepare guide as JSON string
    guide_json = json.dumps(guide_content, indent=2)

    # Run
    result = rlm(question=query_text, guide=guide_json, ont=ont)

    return result


def run_query_without_guide(query_text: str, ont, lm, verbose=False):
    """Run query construction WITHOUT guide (baseline)."""
    import dspy
    from rdflib import RDF, RDFS, OWL, Namespace
    from rlm_runtime.interpreter.namespace_interpreter import NamespaceCodeInterpreter

    # Define signature for query construction (no guide)
    class QueryConstructionSig(dspy.Signature):
        """Construct a SPARQL query to answer a question about an ontology.

        You have access to:
        - `ont`: The loaded rdflib Graph
        - RDF, RDFS, OWL namespaces

        Explore the ontology to understand its structure, then construct the query.
        """

        question: str = dspy.InputField(desc="The question to answer")
        ont: object = dspy.InputField(desc="The loaded rdflib Graph object")

        sparql_query: str = dspy.OutputField(desc="SPARQL query that answers the question")
        explanation: str = dspy.OutputField(desc="Explanation of how the query works")

    # Create interpreter
    interpreter = NamespaceCodeInterpreter(result_truncation_limit=5000)

    # Tools
    tools = {
        'RDF': RDF,
        'RDFS': RDFS,
        'OWL': OWL,
        'Namespace': Namespace,
    }

    # Create RLM
    rlm = dspy.RLM(
        QueryConstructionSig,
        max_iterations=10,
        max_llm_calls=8,
        verbose=verbose,
        interpreter=interpreter,
        tools=tools,
    )

    # Run
    result = rlm(question=query_text, ont=ont)

    return result


def run_e4():
    """Run E4: Guide-Based Query Construction experiment."""
    import dspy
    from rdflib import Graph

    print("\n" + "=" * 70)
    print("E4: GUIDE-BASED QUERY CONSTRUCTION")
    print("=" * 70)
    print(f"Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print()

    # Load PROV ontology
    ontology_path = project_root / "ontology" / "prov.ttl"
    if not ontology_path.exists():
        print(f"ERROR: Ontology not found at {ontology_path}")
        sys.exit(1)

    print(f"Loading ontology: {ontology_path}")
    ont = Graph()
    ont.parse(ontology_path)
    print(f"Loaded {len(ont)} triples")
    print()

    # Load guide from E3-Retry
    guide_path = project_root / "experiments" / "ontology_exploration" / "e3_retry_guide.json"
    if not guide_path.exists():
        print(f"ERROR: Guide not found at {guide_path}")
        sys.exit(1)

    print(f"Loading guide: {guide_path}")
    with open(guide_path, 'r') as f:
        guide = json.load(f)
    print(f"Guide loaded: {len(guide.get('semantic_categories', []))} categories, "
          f"{len(guide.get('use_cases', []))} use cases, "
          f"{len(guide.get('query_patterns', []))} patterns")
    print()

    # Configure DSPy
    lm = dspy.LM("anthropic/claude-sonnet-4-5-20250929", max_tokens=4096)
    dspy.configure(lm=lm)

    # Results storage
    all_results = []

    # Run experiments
    for query_def in TEST_QUERIES:
        query_id = query_def['id']
        query_text = query_def['query']

        print("=" * 70)
        print(f"QUERY: {query_text}")
        print(f"ID: {query_id} | Complexity: {query_def['complexity']}")
        print("=" * 70)
        print()

        # Condition A: Without guide (Baseline)
        print("-" * 70)
        print("CONDITION A: WITHOUT GUIDE (Baseline)")
        print("-" * 70)

        start_time = datetime.now()
        lm.history = []  # Reset history

        try:
            result_no_guide = run_query_without_guide(query_text, ont, lm, verbose=True)
            elapsed_no_guide = (datetime.now() - start_time).total_seconds()

            # Extract metrics
            lm_calls_no_guide = len(lm.history)
            input_tokens_no_guide = sum(call.get('usage', {}).get('input_tokens', 0)
                                       for call in lm.history if isinstance(call, dict))
            output_tokens_no_guide = sum(call.get('usage', {}).get('output_tokens', 0)
                                        for call in lm.history if isinstance(call, dict))
            cost_no_guide = (input_tokens_no_guide / 1_000_000 * 3.0 +
                           output_tokens_no_guide / 1_000_000 * 15.0)

            print(f"\n✓ Completed in {elapsed_no_guide:.1f}s")
            print(f"  LM calls: {lm_calls_no_guide}")
            print(f"  Tokens: {input_tokens_no_guide + output_tokens_no_guide:,}")
            print(f"  Cost: ${cost_no_guide:.4f}")
            print(f"  SPARQL: {result_no_guide.sparql_query[:100]}...")

        except Exception as e:
            print(f"✗ Failed: {e}")
            result_no_guide = None
            elapsed_no_guide = 0
            lm_calls_no_guide = 0
            input_tokens_no_guide = 0
            output_tokens_no_guide = 0
            cost_no_guide = 0

        print()

        # Condition B: With guide
        print("-" * 70)
        print("CONDITION B: WITH GUIDE")
        print("-" * 70)

        start_time = datetime.now()
        lm.history = []  # Reset history

        try:
            result_with_guide = run_query_with_guide(query_text, guide, ont, lm, verbose=True)
            elapsed_with_guide = (datetime.now() - start_time).total_seconds()

            # Extract metrics
            lm_calls_with_guide = len(lm.history)
            input_tokens_with_guide = sum(call.get('usage', {}).get('input_tokens', 0)
                                         for call in lm.history if isinstance(call, dict))
            output_tokens_with_guide = sum(call.get('usage', {}).get('output_tokens', 0)
                                          for call in lm.history if isinstance(call, dict))
            cost_with_guide = (input_tokens_with_guide / 1_000_000 * 3.0 +
                             output_tokens_with_guide / 1_000_000 * 15.0)

            print(f"\n✓ Completed in {elapsed_with_guide:.1f}s")
            print(f"  LM calls: {lm_calls_with_guide}")
            print(f"  Tokens: {input_tokens_with_guide + output_tokens_with_guide:,}")
            print(f"  Cost: ${cost_with_guide:.4f}")
            print(f"  SPARQL: {result_with_guide.sparql_query[:100]}...")

        except Exception as e:
            print(f"✗ Failed: {e}")
            result_with_guide = None
            elapsed_with_guide = 0
            lm_calls_with_guide = 0
            input_tokens_with_guide = 0
            output_tokens_with_guide = 0
            cost_with_guide = 0

        print()

        # Compare
        print("-" * 70)
        print("COMPARISON")
        print("-" * 70)

        if result_no_guide and result_with_guide:
            time_diff = elapsed_with_guide - elapsed_no_guide
            time_pct = (time_diff / elapsed_no_guide * 100) if elapsed_no_guide > 0 else 0

            calls_diff = lm_calls_with_guide - lm_calls_no_guide
            calls_pct = (calls_diff / lm_calls_no_guide * 100) if lm_calls_no_guide > 0 else 0

            tokens_no_guide = input_tokens_no_guide + output_tokens_no_guide
            tokens_with_guide = input_tokens_with_guide + output_tokens_with_guide
            tokens_diff = tokens_with_guide - tokens_no_guide
            tokens_pct = (tokens_diff / tokens_no_guide * 100) if tokens_no_guide > 0 else 0

            cost_diff = cost_with_guide - cost_no_guide
            cost_pct = (cost_diff / cost_no_guide * 100) if cost_no_guide > 0 else 0

            print(f"Time: {elapsed_no_guide:.1f}s → {elapsed_with_guide:.1f}s ({time_diff:+.1f}s, {time_pct:+.1f}%)")
            print(f"LM calls: {lm_calls_no_guide} → {lm_calls_with_guide} ({calls_diff:+d}, {calls_pct:+.1f}%)")
            print(f"Tokens: {tokens_no_guide:,} → {tokens_with_guide:,} ({tokens_diff:+,}, {tokens_pct:+.1f}%)")
            print(f"Cost: ${cost_no_guide:.4f} → ${cost_with_guide:.4f} (${cost_diff:+.4f}, {cost_pct:+.1f}%)")

            # Check for guide references (basic heuristic)
            guide_referenced = False
            if hasattr(result_with_guide, 'explanation'):
                explanation_lower = result_with_guide.explanation.lower()
                guide_keywords = ['guide', 'use case', 'category', 'pattern']
                guide_referenced = any(kw in explanation_lower for kw in guide_keywords)

            print(f"Guide referenced: {'✓ Yes' if guide_referenced else '✗ No'}")
        else:
            print("Cannot compare - one or both conditions failed")

        print()

        # Store results
        result_data = {
            'query_id': query_id,
            'query_text': query_text,
            'complexity': query_def['complexity'],
            'timestamp': datetime.now().isoformat(),
            'condition_a_no_guide': {
                'success': result_no_guide is not None,
                'elapsed_seconds': elapsed_no_guide,
                'lm_calls': lm_calls_no_guide,
                'input_tokens': input_tokens_no_guide,
                'output_tokens': output_tokens_no_guide,
                'total_tokens': input_tokens_no_guide + output_tokens_no_guide,
                'cost_usd': cost_no_guide,
                'sparql_query': result_no_guide.sparql_query if result_no_guide else None,
                'explanation': result_no_guide.explanation if result_no_guide else None
            },
            'condition_b_with_guide': {
                'success': result_with_guide is not None,
                'elapsed_seconds': elapsed_with_guide,
                'lm_calls': lm_calls_with_guide,
                'input_tokens': input_tokens_with_guide,
                'output_tokens': output_tokens_with_guide,
                'total_tokens': input_tokens_with_guide + output_tokens_with_guide,
                'cost_usd': cost_with_guide,
                'sparql_query': result_with_guide.sparql_query if result_with_guide else None,
                'explanation': result_with_guide.explanation if result_with_guide else None,
                'guide_referenced': guide_referenced if (result_no_guide and result_with_guide) else None
            },
            'comparison': {
                'time_diff_seconds': elapsed_with_guide - elapsed_no_guide if (result_no_guide and result_with_guide) else None,
                'calls_diff': lm_calls_with_guide - lm_calls_no_guide if (result_no_guide and result_with_guide) else None,
                'tokens_diff': (input_tokens_with_guide + output_tokens_with_guide) - (input_tokens_no_guide + output_tokens_no_guide) if (result_no_guide and result_with_guide) else None,
                'cost_diff_usd': cost_with_guide - cost_no_guide if (result_no_guide and result_with_guide) else None
            }
        }

        all_results.append(result_data)

    # Save all results
    results_path = project_root / "experiments" / "ontology_exploration" / "e4_results.json"
    with open(results_path, 'w') as f:
        json.dump(all_results, f, indent=2)

    print("=" * 70)
    print("EXPERIMENT COMPLETE")
    print("=" * 70)
    print(f"Results saved to: {results_path}")
    print()

    # Summary statistics
    print("=" * 70)
    print("SUMMARY")
    print("=" * 70)

    total_cost_no_guide = sum(r['condition_a_no_guide']['cost_usd'] for r in all_results)
    total_cost_with_guide = sum(r['condition_b_with_guide']['cost_usd'] for r in all_results)

    print(f"Total cost (no guide): ${total_cost_no_guide:.4f}")
    print(f"Total cost (with guide): ${total_cost_with_guide:.4f}")
    print(f"Difference: ${total_cost_with_guide - total_cost_no_guide:+.4f}")

    if total_cost_no_guide > 0:
        print(f"Percentage change: {(total_cost_with_guide - total_cost_no_guide) / total_cost_no_guide * 100:+.1f}%")

    # Break-even analysis
    guide_creation_cost = 0.2491  # E3-Retry cost
    cost_per_query_savings = (total_cost_no_guide - total_cost_with_guide) / len(TEST_QUERIES)

    if cost_per_query_savings > 0:
        break_even_queries = guide_creation_cost / cost_per_query_savings
        print(f"\nBreak-even analysis:")
        print(f"  Guide creation cost: ${guide_creation_cost:.4f}")
        print(f"  Savings per query: ${cost_per_query_savings:.4f}")
        print(f"  Break-even at: {break_even_queries:.1f} queries")
    else:
        print(f"\nGuide did not reduce per-query cost")

    print()

    return True


if __name__ == "__main__":
    success = run_e4()
    sys.exit(0 if success else 1)
