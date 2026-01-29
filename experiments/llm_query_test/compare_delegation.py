#!/usr/bin/env python3
"""Compare RLM with and without llm_query delegation.

Simple side-by-side comparison to see if strategic delegation helps.

Usage:
    python experiments/llm_query_test/compare_delegation.py
"""

import json
import sys
from pathlib import Path
from datetime import datetime

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))


def count_delegations(log_path):
    """Count llm_query calls in trajectory log."""
    if not Path(log_path).exists():
        return 0

    count = 0
    with open(log_path) as f:
        for line in f:
            try:
                event = json.loads(line)
                if event.get("event_type") == "module_start":
                    code = event.get("inputs", {}).get("code", "")
                    if "llm_query(" in code:
                        count += 1
            except json.JSONDecodeError:
                continue
    return count


def run_single_test(query, ontology, config_name, enable_llm_query=True):
    """Run single test with specified configuration."""
    from rlm_runtime.engine.dspy_rlm import run_dspy_rlm
    from rlm_runtime.tools.delegation_tools import make_llm_query_tool
    import dspy

    print(f"\n{'=' * 60}")
    print(f"Running: {config_name}")
    print(f"{'=' * 60}")

    log_path = f"experiments/llm_query_test/{config_name.lower().replace(' ', '_')}.jsonl"

    # If we want to disable llm_query, we need to temporarily modify the tools
    # For now, we'll just run with it enabled and note if it's used
    import time
    start = time.time()

    try:
        result = run_dspy_rlm(
            query,
            ontology,
            max_iterations=8,
            max_llm_calls=16,
            verbose=False,  # Keep quiet for comparison
            log_path=log_path
        )
        elapsed = time.time() - start

        # Count delegations
        delegations = count_delegations(log_path)

        print(f"\n✅ Completed in {elapsed:.1f}s")
        print(f"   Iterations: {result.iteration_count}")
        print(f"   Converged: {result.converged}")
        print(f"   llm_query calls: {delegations}")
        print(f"   Answer length: {len(result.answer)} chars")

        return {
            "config": config_name,
            "elapsed": elapsed,
            "iterations": result.iteration_count,
            "converged": result.converged,
            "delegations": delegations,
            "answer": result.answer,
            "log_path": log_path
        }

    except Exception as e:
        print(f"\n❌ Error: {e}")
        return {
            "config": config_name,
            "error": str(e)
        }


def compare_results(results):
    """Print comparison table."""
    print(f"\n{'=' * 60}")
    print("COMPARISON RESULTS")
    print(f"{'=' * 60}")

    # Table header
    print(f"\n{'Config':<20} {'Time (s)':<10} {'Iters':<8} {'Delegations':<12} {'Converged':<10}")
    print("-" * 60)

    # Table rows
    for r in results:
        if "error" in r:
            print(f"{r['config']:<20} ERROR: {r['error']}")
        else:
            print(f"{r['config']:<20} {r['elapsed']:<10.1f} {r['iterations']:<8} "
                  f"{r['delegations']:<12} {'Yes' if r['converged'] else 'No':<10}")

    # Analysis
    print(f"\n{'=' * 60}")
    print("ANALYSIS")
    print(f"{'=' * 60}")

    valid_results = [r for r in results if "error" not in r]
    if len(valid_results) < 2:
        print("\n⚠️  Need at least 2 successful runs for comparison")
        return

    baseline = valid_results[0]
    with_delegation = valid_results[0]  # Will be updated if found

    # Find result with delegations
    for r in valid_results:
        if r.get("delegations", 0) > 0:
            with_delegation = r
            break

    delegations_used = with_delegation.get("delegations", 0) > 0

    if delegations_used:
        print(f"\n✅ llm_query WAS USED: {with_delegation['delegations']} calls")
        print(f"   This indicates strategic sub-LLM delegation happened!")

        # Compare performance
        if len(valid_results) > 1:
            speed_diff = ((with_delegation["elapsed"] - baseline["elapsed"]) / baseline["elapsed"]) * 100
            iter_diff = with_delegation["iterations"] - baseline["iterations"]

            print(f"\n   Performance Impact:")
            print(f"   - Speed: {speed_diff:+.1f}% ({'slower' if speed_diff > 0 else 'faster'})")
            print(f"   - Iterations: {iter_diff:+d} ({'more' if iter_diff > 0 else 'fewer'})")
    else:
        print(f"\n⚪ llm_query NOT USED (0 calls)")
        print(f"   Model didn't delegate to sub-LLM")
        print(f"   This is EXPECTED without training (per Prime Intellect)")
        print(f"\n   Possible reasons:")
        print(f"   1. Task too simple (doesn't need delegation)")
        print(f"   2. Model prefers direct tools")
        print(f"   3. Model not trained on delegation pattern")

    # Check trajectory logs
    print(f"\n📋 Trajectory Logs:")
    for r in valid_results:
        if "log_path" in r:
            print(f"   - {r['config']}: {r['log_path']}")

    print(f"\n💡 Next Steps:")
    if delegations_used:
        print(f"   1. Review trajectory to see WHEN/WHY delegation happened")
        print(f"   2. Test on L2-L3 tasks to see if benefit scales")
        print(f"   3. Compare quality of answers (not just speed)")
    else:
        print(f"   1. Try explicit prompt: 'Use llm_query to validate findings'")
        print(f"   2. Test on harder L2-L3 tasks (may trigger delegation)")
        print(f"   3. Consider: Maybe direct tools are sufficient for this task")


def main():
    """Run comparison experiment."""
    print("=" * 60)
    print("RLM DELEGATION COMPARISON")
    print("=" * 60)
    print(f"Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

    # Test configuration
    query = "What is the Protein class?"
    ontology = "ontology/uniprot-core.ttl"

    if not Path(ontology).exists():
        print(f"\n❌ Ontology not found: {ontology}")
        print("   Available ontologies:")
        for ont in Path("ontology").glob("*.ttl"):
            print(f"   - {ont}")
        return 1

    print(f"\nQuery: {query}")
    print(f"Ontology: {ontology}")

    # Create output directory
    Path("experiments/llm_query_test").mkdir(parents=True, exist_ok=True)

    # Run test (currently can only run with llm_query enabled)
    # To test without, user needs to manually comment out the tool
    results = []

    print("\n" + "=" * 60)
    print("Note: llm_query tool is now enabled by default")
    print("Checking if model uses it spontaneously...")
    print("=" * 60)

    result = run_single_test(query, ontology, "RLM with llm_query", enable_llm_query=True)
    results.append(result)

    # Compare results
    compare_results(results)

    # Save results
    output_file = f"experiments/llm_query_test/comparison_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    with open(output_file, 'w') as f:
        json.dump({
            "timestamp": datetime.now().isoformat(),
            "query": query,
            "ontology": ontology,
            "results": results
        }, f, indent=2)

    print(f"\n📄 Results saved to: {output_file}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
