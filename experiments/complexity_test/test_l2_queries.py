#!/usr/bin/env python3
"""Test L2 (property relationship) queries to see if delegation emerges.

L2 queries require understanding relationships between classes/properties,
which may trigger strategic delegation for disambiguation or validation.

Usage:
    source ~/uvws/.venv/bin/activate
    python experiments/complexity_test/test_l2_queries.py
"""

import sys
import os
import json
from pathlib import Path
from datetime import datetime

sys.path.insert(0, str(Path(__file__).parent.parent.parent))


# L2 Test Queries - Property Relationships
L2_QUERIES = [
    {
        "id": "L2-1",
        "query": "What properties connect Activity to Entity in this ontology?",
        "ontology": "ontology/prov.ttl",
        "complexity": "L2-relationships",
        "why_l2": "Requires identifying multiple properties, understanding domain/range, explaining relationships"
    },
    {
        "id": "L2-2",
        "query": "How do Agents associate with Activities? What properties are used?",
        "ontology": "ontology/prov.ttl",
        "complexity": "L2-relationships",
        "why_l2": "Requires exploring wasAssociatedWith and related properties, understanding association patterns"
    },
    {
        "id": "L2-3",
        "query": "What is the difference between wasGeneratedBy and wasAttributedTo?",
        "ontology": "ontology/prov.ttl",
        "complexity": "L2-comparison",
        "why_l2": "Requires comparing two properties, understanding subtle semantic differences, explaining usage"
    }
]


def analyze_run(log_path, run_info):
    """Analyze a single run from log."""
    if not Path(log_path).exists():
        return None

    # Token analysis
    total_input = 0
    total_output = 0
    llm_calls = 0

    # Delegation analysis
    llm_query_attempts = 0
    llm_query_calls = []

    # Iteration tracking
    iterations = []

    with open(log_path) as f:
        for line in f:
            try:
                event = json.loads(line)

                # Track tokens
                if event.get("event") == "llm_response":
                    usage = event.get("usage", {})
                    total_input += usage.get("prompt_tokens", 0)
                    total_output += usage.get("completion_tokens", 0)
                    llm_calls += 1

                # Track delegation attempts in code
                if event.get("event") == "module_start":
                    code = event.get("inputs", {}).get("code", "")
                    reasoning = event.get("inputs", {}).get("reasoning", "")

                    if code:
                        iterations.append({
                            "code": code[:200],  # First 200 chars
                            "reasoning": reasoning[:200],
                            "has_llm_query": "llm_query(" in code
                        })

                        if "llm_query(" in code:
                            llm_query_attempts += 1
                            # Extract the llm_query line
                            for line in code.split("\n"):
                                if "llm_query(" in line:
                                    llm_query_calls.append(line.strip()[:150])

            except:
                continue

    total_tokens = total_input + total_output
    cost = (total_input / 1_000_000) * 3.0 + (total_output / 1_000_000) * 15.0

    return {
        "tokens": {
            "input": total_input,
            "output": total_output,
            "total": total_tokens
        },
        "llm_calls": llm_calls,
        "cost": cost,
        "delegation": {
            "llm_query_attempts": llm_query_attempts,
            "llm_query_calls": llm_query_calls,
            "used_delegation": llm_query_attempts > 0
        },
        "iterations": len(iterations),
        "iteration_details": iterations
    }


def run_l2_query(query_info):
    """Run a single L2 query."""
    from rlm_runtime.engine.dspy_rlm import run_dspy_rlm

    query_id = query_info["id"]
    query = query_info["query"]
    ontology = query_info["ontology"]

    log_path = f"experiments/complexity_test/{query_id.lower()}_test.jsonl"

    print(f"\n{'='*70}")
    print(f"TEST: {query_id} ({query_info['complexity']})")
    print(f"{'='*70}")
    print(f"Query: {query}")
    print(f"Why L2: {query_info['why_l2']}")
    print(f"Ontology: {ontology}")
    print(f"\nRunning...")

    import time
    start = time.time()

    result = run_dspy_rlm(
        query,
        ontology,
        max_iterations=12,  # Increased budget
        max_llm_calls=20,
        verbose=False,
        log_path=log_path,
        log_llm_calls=True
    )

    elapsed = time.time() - start

    # Analyze
    analysis = analyze_run(log_path, query_info)

    print(f"\n{'─'*70}")
    print(f"RESULTS")
    print(f"{'─'*70}")
    print(f"Time: {elapsed:.1f}s")
    print(f"Iterations: {result.iteration_count} / 12")
    print(f"Converged: {result.converged}")
    print(f"Tokens: {analysis['tokens']['total']:,} (${analysis['cost']:.4f})")
    print(f"  Input: {analysis['tokens']['input']:,}")
    print(f"  Output: {analysis['tokens']['output']:,}")

    # Delegation analysis
    delegation = analysis['delegation']
    if delegation['used_delegation']:
        print(f"\n✅ DELEGATION USED!")
        print(f"  llm_query attempts: {delegation['llm_query_attempts']}")
        print(f"  Calls:")
        for call in delegation['llm_query_calls']:
            print(f"    → {call}")
    else:
        print(f"\n⚪ No delegation (solved directly)")

    print(f"\nAnswer length: {len(result.answer)} chars")
    print(f"Answer preview:")
    print(f"  {result.answer[:200]}...")

    return {
        "query_info": query_info,
        "execution": {
            "elapsed": elapsed,
            "iterations": result.iteration_count,
            "converged": result.converged,
            "answer": result.answer,
            "answer_length": len(result.answer)
        },
        "analysis": analysis,
        "log_path": log_path
    }


def compare_with_l1_baseline():
    """Compare L2 results with L1 baseline."""
    print(f"\n{'='*70}")
    print("COMPARISON: L2 vs L1 Baseline")
    print(f"{'='*70}")

    print(f"\nL1 Baseline (from previous tests):")
    print(f"  Query: 'What is Activity in this ontology?'")
    print(f"  Iterations: 5")
    print(f"  Cost: $0.089")
    print(f"  Delegation: 0 attempts")
    print(f"  Pattern: Search → Query → Analyze → Submit")

    print(f"\nL2 Results will show:")
    print(f"  - More iterations? (complexity requires more steps)")
    print(f"  - Delegation emerges? (semantic disambiguation needed)")
    print(f"  - Higher cost? (more LLM calls)")
    print(f"  - Different patterns? (relationship exploration)")


def summarize_results(results):
    """Summarize all L2 test results."""
    print(f"\n{'='*70}")
    print("L2 COMPLEXITY TEST SUMMARY")
    print(f"{'='*70}")

    total_tests = len(results)
    with_delegation = sum(1 for r in results if r['analysis']['delegation']['used_delegation'])
    avg_iterations = sum(r['execution']['iterations'] for r in results) / total_tests
    avg_cost = sum(r['analysis']['cost'] for r in results) / total_tests
    avg_tokens = sum(r['analysis']['tokens']['total'] for r in results) / total_tests

    print(f"\nOverall Stats:")
    print(f"  Tests run: {total_tests}")
    print(f"  Tests with delegation: {with_delegation} ({(with_delegation/total_tests)*100:.0f}%)")
    print(f"  Average iterations: {avg_iterations:.1f}")
    print(f"  Average cost: ${avg_cost:.4f}")
    print(f"  Average tokens: {avg_tokens:,.0f}")

    print(f"\n{'─'*70}")
    print("Individual Results:")
    print(f"{'─'*70}")

    for r in results:
        query_id = r['query_info']['id']
        iters = r['execution']['iterations']
        cost = r['analysis']['cost']
        delegation = "✅ Yes" if r['analysis']['delegation']['used_delegation'] else "⚪ No"
        attempts = r['analysis']['delegation']['llm_query_attempts']

        print(f"\n{query_id}: {r['query_info']['query'][:60]}...")
        print(f"  Iterations: {iters}/12")
        print(f"  Cost: ${cost:.4f}")
        print(f"  Delegation: {delegation} ({attempts} attempts)")
        print(f"  Converged: {r['execution']['converged']}")

    # Analysis
    print(f"\n{'='*70}")
    print("ANALYSIS")
    print(f"{'='*70}")

    if with_delegation > 0:
        print(f"\n✅ SUCCESS: Delegation emerged on L2 tasks!")
        print(f"   {with_delegation}/{total_tests} queries used llm_query")
        print(f"   L2 complexity triggers strategic delegation")
        print(f"   Model recognizes when semantic analysis helps")
    else:
        print(f"\n⚪ NO DELEGATION on L2 tasks")
        print(f"   Model solved all queries directly")
        print(f"   Possible reasons:")
        print(f"     1. Tasks still solvable without delegation")
        print(f"     2. PROV ontology structure is very clear")
        print(f"     3. Model optimizes for speed over delegation")

    # Cost comparison
    l1_cost = 0.089
    if avg_cost > l1_cost * 1.5:
        cost_diff_pct = ((avg_cost - l1_cost) / l1_cost) * 100
        print(f"\n💰 L2 is {cost_diff_pct:.0f}% more expensive than L1")
        print(f"   L1: ${l1_cost:.4f}")
        print(f"   L2: ${avg_cost:.4f}")
        print(f"   Difference: ${avg_cost - l1_cost:.4f}")
    else:
        print(f"\n💰 L2 cost comparable to L1")
        print(f"   L1: ${l1_cost:.4f}")
        print(f"   L2: ${avg_cost:.4f}")

    # Recommendations
    print(f"\n{'='*70}")
    print("RECOMMENDATIONS")
    print(f"{'='*70}")

    if with_delegation > 0:
        print(f"\n✅ L2 triggers delegation - this is valuable!")
        print(f"   Next: Test L3 to see if delegation increases")
        print(f"   Next: Compare quality with/without delegation")
        print(f"   Next: Measure delegation ROI (cost vs quality)")
    else:
        print(f"\n⚪ L2 doesn't trigger delegation")
        print(f"   Next: Test L3 (multi-hop) to see if complexity helps")
        print(f"   Consider: Ontology queries may not need delegation")
        print(f"   Consider: Tool-first pattern may be optimal")

    if avg_cost < 0.25:
        print(f"\n✅ L2 cost is acceptable (< $0.25/query)")
        print(f"   Still cheaper than ReAct baseline ($0.27)")
        print(f"   RLM remains cost-efficient on L2")


def main():
    """Run L2 complexity tests."""
    print(f"\n{'='*70}")
    print("L2 COMPLEXITY TEST: Property Relationships")
    print(f"{'='*70}")
    print(f"Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

    if not os.environ.get("ANTHROPIC_API_KEY"):
        print("\n❌ ANTHROPIC_API_KEY not set")
        return 1

    # Create output directory
    Path("experiments/complexity_test").mkdir(parents=True, exist_ok=True)

    print(f"\nTest Plan:")
    print(f"  - {len(L2_QUERIES)} L2 queries (property relationships)")
    print(f"  - Budget: 12 iterations, 20 LLM calls")
    print(f"  - Goal: See if complexity triggers delegation")

    print(f"\nL2 Query Types:")
    for q in L2_QUERIES:
        print(f"  {q['id']}: {q['complexity']}")
        print(f"    → {q['query']}")

    # Show baseline for comparison
    compare_with_l1_baseline()

    # Run all L2 queries
    results = []
    for query_info in L2_QUERIES:
        result = run_l2_query(query_info)
        results.append(result)

    # Summarize
    summarize_results(results)

    # Save results
    output_file = f"experiments/complexity_test/l2_results_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    with open(output_file, 'w') as f:
        json.dump({
            "timestamp": datetime.now().isoformat(),
            "test_type": "L2_complexity",
            "results": results
        }, f, indent=2)

    print(f"\n📄 Results saved to: {output_file}")

    print(f"\n{'='*70}")
    print("NEXT STEPS")
    print(f"{'='*70}")
    print(f"\n1. Review delegation patterns:")
    print(f"   - Check logs for llm_query usage")
    print(f"   - Understand when/why delegation triggered")

    print(f"\n2. Compare answer quality:")
    print(f"   - Are L2 answers more detailed than L1?")
    print(f"   - Does delegation improve comprehensiveness?")

    print(f"\n3. If delegation emerged:")
    print(f"   - Test L3 (multi-hop) to see if it increases")
    print(f"   - Measure delegation ROI")

    print(f"\n4. If no delegation:")
    print(f"   - Test L3 anyway (higher complexity)")
    print(f"   - Consider: tool-first may be optimal for ontologies")

    return 0


if __name__ == "__main__":
    sys.exit(main())
