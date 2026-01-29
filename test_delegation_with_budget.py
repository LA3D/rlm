#!/usr/bin/env python3
"""Test RLM with increased iteration budget to allow delegation.

Compares:
1. RLM baseline (8 iters, tight budget)
2. RLM with budget (12 iters, loose budget)
3. Cost and delegation analysis

Usage:
    source ~/uvws/.venv/bin/activate
    python test_delegation_with_budget.py
"""

import sys
import os
import json
from pathlib import Path
from datetime import datetime

sys.path.insert(0, str(Path(__file__).parent))


def analyze_tokens(log_path):
    """Extract token usage from log."""
    if not Path(log_path).exists():
        return None

    total_input = 0
    total_output = 0
    calls = []
    llm_query_count = 0

    with open(log_path) as f:
        for line in f:
            try:
                event = json.loads(line)
                if event.get("event") == "llm_response":
                    usage = event.get("usage", {})
                    total_input += usage.get("prompt_tokens", 0)
                    total_output += usage.get("completion_tokens", 0)
                    calls.append(usage.get("total_tokens", 0))

                # Check for llm_query in code
                if event.get("event") == "module_start":
                    code = event.get("inputs", {}).get("code", "")
                    if "llm_query(" in code:
                        llm_query_count += 1
            except:
                continue

    total = total_input + total_output

    # Calculate cost (Sonnet 4.5 pricing)
    cost = (total_input / 1_000_000) * 3.0 + (total_output / 1_000_000) * 15.0

    return {
        "total_input": total_input,
        "total_output": total_output,
        "total_tokens": total,
        "llm_calls": len(calls),
        "cost": cost,
        "llm_query_attempts": llm_query_count
    }


def run_test(config_name, max_iterations, max_llm_calls):
    """Run RLM test with specified budget."""
    from rlm_runtime.engine.dspy_rlm import run_dspy_rlm

    query = "What is Activity in this ontology?"
    ontology = "ontology/prov.ttl"

    log_path = f"experiments/cost_analysis/{config_name}_test.jsonl"

    print(f"\n{'='*70}")
    print(f"TEST: {config_name}")
    print(f"{'='*70}")
    print(f"Query: {query}")
    print(f"Max iterations: {max_iterations}")
    print(f"Max LLM calls: {max_llm_calls}")
    print(f"Log: {log_path}")

    import time
    start = time.time()

    result = run_dspy_rlm(
        query,
        ontology,
        max_iterations=max_iterations,
        max_llm_calls=max_llm_calls,
        verbose=False,
        log_path=log_path,
        log_llm_calls=True
    )

    elapsed = time.time() - start

    # Analyze tokens
    token_stats = analyze_tokens(log_path)

    print(f"\n✅ Complete in {elapsed:.1f}s")
    print(f"   Iterations: {result.iteration_count}")
    print(f"   Converged: {result.converged}")
    print(f"   Input tokens: {token_stats['total_input']:,}")
    print(f"   Output tokens: {token_stats['total_output']:,}")
    print(f"   Total tokens: {token_stats['total_tokens']:,}")
    print(f"   LLM calls: {token_stats['llm_calls']}")
    print(f"   Cost: ${token_stats['cost']:.4f}")
    print(f"   llm_query attempts: {token_stats['llm_query_attempts']}")

    return {
        "config": config_name,
        "max_iterations": max_iterations,
        "max_llm_calls": max_llm_calls,
        "elapsed": elapsed,
        "iterations": result.iteration_count,
        "converged": result.converged,
        "answer_length": len(result.answer),
        "tokens": token_stats,
        "log_path": log_path
    }


def compare_results(baseline, with_budget):
    """Compare baseline vs increased budget."""
    print(f"\n{'='*70}")
    print("COMPARISON: Baseline vs Increased Budget")
    print(f"{'='*70}")

    print(f"\n{'Metric':<25} {'Baseline (8)':<20} {'Budget (12)':<20} {'Change':<15}")
    print("-" * 80)

    # Speed
    speed_diff = with_budget['elapsed'] - baseline['elapsed']
    print(f"{'Time (seconds)':<25} {baseline['elapsed']:<20.1f} {with_budget['elapsed']:<20.1f} {speed_diff:+.1f}s")

    # Iterations
    iter_diff = with_budget['iterations'] - baseline['iterations']
    print(f"{'Iterations':<25} {baseline['iterations']:<20} {with_budget['iterations']:<20} {iter_diff:+d}")

    # Tokens
    baseline_tokens = baseline['tokens']['total_tokens']
    budget_tokens = with_budget['tokens']['total_tokens']
    token_diff_pct = ((budget_tokens - baseline_tokens) / baseline_tokens) * 100
    print(f"{'Total tokens':<25} {baseline_tokens:<20,} {budget_tokens:<20,} {token_diff_pct:+.1f}%")

    # Cost
    baseline_cost = baseline['tokens']['cost']
    budget_cost = with_budget['tokens']['cost']
    cost_diff = budget_cost - baseline_cost
    cost_diff_pct = ((budget_cost - baseline_cost) / baseline_cost) * 100
    print(f"{'Cost (USD)':<25} ${baseline_cost:<19.4f} ${budget_cost:<19.4f} ${cost_diff:+.4f} ({cost_diff_pct:+.1f}%)")

    # Delegation
    baseline_delegation = baseline['tokens']['llm_query_attempts']
    budget_delegation = with_budget['tokens']['llm_query_attempts']
    print(f"{'llm_query attempts':<25} {baseline_delegation:<20} {budget_delegation:<20} {budget_delegation - baseline_delegation:+d}")

    # Analysis
    print(f"\n{'='*70}")
    print("ANALYSIS")
    print(f"{'='*70}")

    if budget_delegation > baseline_delegation:
        print(f"\n✅ DELEGATION INCREASED!")
        print(f"   Baseline: {baseline_delegation} llm_query attempts")
        print(f"   Budget: {budget_delegation} llm_query attempts")
        print(f"   More room allowed model to attempt delegation")
    elif budget_delegation == baseline_delegation:
        print(f"\n⚪ NO CHANGE IN DELEGATION")
        print(f"   Both: {baseline_delegation} llm_query attempts")
        print(f"   Budget increase didn't trigger more delegation")
        if baseline_delegation == 0:
            print(f"   Model chose not to delegate (task too simple?)")

    if iter_diff > 0:
        print(f"\n📊 Used {iter_diff} more iterations with budget")
        if token_diff_pct < 50:
            print(f"   But only {token_diff_pct:.1f}% more tokens (efficient!)")
    else:
        print(f"\n📊 Same iterations used ({baseline['iterations']})")
        print(f"   Budget increase had no effect (converged early)")

    # Cost efficiency
    print(f"\n💰 Cost Impact:")
    if cost_diff_pct < 20:
        print(f"   ✅ Only {cost_diff_pct:.1f}% cost increase (acceptable!)")
        print(f"   Additional ${cost_diff:.4f}/query")
    elif cost_diff_pct < 50:
        print(f"   ⚠️  {cost_diff_pct:.1f}% cost increase (moderate)")
        print(f"   Additional ${cost_diff:.4f}/query")
    else:
        print(f"   ❌ {cost_diff_pct:.1f}% cost increase (significant!)")
        print(f"   Additional ${cost_diff:.4f}/query")

    # Quality check
    if with_budget['converged'] and baseline['converged']:
        print(f"\n✅ Both converged successfully")
        ans_diff = with_budget['answer_length'] - baseline['answer_length']
        if abs(ans_diff) < 100:
            print(f"   Similar answer lengths ({baseline['answer_length']} vs {with_budget['answer_length']})")
        else:
            print(f"   Different answer lengths ({baseline['answer_length']} vs {with_budget['answer_length']})")
            print(f"   Check logs to compare quality")

    # Recommendation
    print(f"\n{'='*70}")
    print("RECOMMENDATION")
    print(f"{'='*70}")

    if budget_delegation > 0 and cost_diff_pct < 20:
        print(f"\n✅ ADOPT INCREASED BUDGET")
        print(f"   Delegation attempts increased: {baseline_delegation} → {budget_delegation}")
        print(f"   Cost impact acceptable: +{cost_diff_pct:.1f}%")
        print(f"   Allows model strategic flexibility")
    elif cost_diff_pct < 10 and iter_diff <= 0:
        print(f"\n⚪ NEUTRAL (no harm, no benefit)")
        print(f"   No change in behavior")
        print(f"   Minimal cost impact: +{cost_diff_pct:.1f}%")
        print(f"   Safe to keep increased budget as headroom")
    else:
        print(f"\n⚪ UNCLEAR")
        print(f"   Need to check trajectory logs for delegation patterns")
        print(f"   Compare answer quality")
        print(f"   Test on L2-L3 complexity to see if budget helps")


def main():
    """Run comparison."""
    print(f"\n{'='*70}")
    print("TESTING: Increased Iteration Budget for Delegation")
    print(f"{'='*70}")
    print(f"Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

    if not os.environ.get("ANTHROPIC_API_KEY"):
        print("\n❌ ANTHROPIC_API_KEY not set")
        return 1

    Path("experiments/cost_analysis").mkdir(parents=True, exist_ok=True)

    print(f"\nHypothesis:")
    print(f"  - Baseline (8 iters): Model may run out of budget before delegation")
    print(f"  - Budget (12 iters): Model has room to complete delegation attempts")
    print(f"  - Expected: More llm_query usage, slight cost increase")

    # Test 1: Baseline (current)
    baseline = run_test("baseline", max_iterations=8, max_llm_calls=16)

    # Test 2: Increased budget
    with_budget = run_test("with_budget", max_iterations=12, max_llm_calls=20)

    # Compare
    compare_results(baseline, with_budget)

    # Save results
    output_file = f"experiments/cost_analysis/budget_comparison_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    with open(output_file, 'w') as f:
        json.dump({
            "timestamp": datetime.now().isoformat(),
            "baseline": baseline,
            "with_budget": with_budget
        }, f, indent=2)

    print(f"\n📄 Results saved to: {output_file}")

    print(f"\n{'='*70}")
    print("NEXT STEPS")
    print(f"{'='*70}")
    print(f"\n1. Check trajectory logs:")
    print(f"   grep 'llm_query' {baseline['log_path']}")
    print(f"   grep 'llm_query' {with_budget['log_path']}")
    print(f"\n2. Compare answers:")
    print(f"   Check if quality improved with budget")
    print(f"\n3. Test on L2-L3 tasks:")
    print(f"   See if delegation helps on complex queries")

    return 0


if __name__ == "__main__":
    sys.exit(main())
