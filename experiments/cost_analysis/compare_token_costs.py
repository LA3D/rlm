#!/usr/bin/env python3
"""Compare token costs: RLM vs ReAct.

Measures actual API token usage to understand cost tradeoffs.

Usage:
    source ~/uvws/.venv/bin/activate
    python experiments/cost_analysis/compare_token_costs.py
"""

import sys
import os
from pathlib import Path
from datetime import datetime
import json

sys.path.insert(0, str(Path(__file__).parent.parent.parent))


# Anthropic API pricing (as of 2025)
# https://www.anthropic.com/pricing
PRICING = {
    "claude-sonnet-4-5-20250929": {
        "input": 3.0,   # $ per 1M tokens
        "output": 15.0  # $ per 1M tokens
    },
    "claude-3-5-haiku-20241022": {
        "input": 0.25,   # $ per 1M tokens
        "output": 1.25   # $ per 1M tokens
    }
}


def calculate_cost(input_tokens, output_tokens, model):
    """Calculate cost in dollars."""
    if model not in PRICING:
        return 0.0

    input_cost = (input_tokens / 1_000_000) * PRICING[model]["input"]
    output_cost = (output_tokens / 1_000_000) * PRICING[model]["output"]
    return input_cost + output_cost


def analyze_dspy_trajectory(log_path):
    """Extract token usage from DSPy trajectory log."""
    if not Path(log_path).exists():
        return None

    total_input_tokens = 0
    total_output_tokens = 0
    iterations = 0
    llm_calls = []

    with open(log_path) as f:
        for line in f:
            try:
                event = json.loads(line)

                # Track LLM response events (have token usage)
                if event.get("event") == "llm_response":
                    usage = event.get("usage", {})
                    call_info = {
                        "input_tokens": usage.get("prompt_tokens", 0),
                        "output_tokens": usage.get("completion_tokens", 0),
                        "total_tokens": usage.get("total_tokens", 0),
                        "model": event.get("model", "unknown")
                    }
                    llm_calls.append(call_info)
                    total_input_tokens += call_info["input_tokens"]
                    total_output_tokens += call_info["output_tokens"]

                # Count iterations (RLM iterations are Predict module calls)
                if event.get("event") == "module_start" and event.get("module_name") == "Predict":
                    iterations += 1

            except json.JSONDecodeError:
                continue

    return {
        "total_input_tokens": total_input_tokens,
        "total_output_tokens": total_output_tokens,
        "total_tokens": total_input_tokens + total_output_tokens,
        "iterations": iterations,
        "llm_calls": llm_calls,
        "calls_per_iteration": len(llm_calls) / iterations if iterations > 0 else 0
    }


def run_rlm_test(query, ontology, max_iterations=8):
    """Run RLM test and return token usage."""
    from rlm_runtime.engine.dspy_rlm import run_dspy_rlm

    log_path = "experiments/cost_analysis/rlm_cost_test.jsonl"

    print(f"\n{'='*70}")
    print("RUNNING RLM TEST")
    print(f"{'='*70}")
    print(f"Query: {query}")
    print(f"Max iterations: {max_iterations}")

    import time
    start = time.time()

    result = run_dspy_rlm(
        query,
        ontology,
        max_iterations=max_iterations,
        max_llm_calls=max_iterations * 2,
        verbose=False,
        log_path=log_path,
        log_llm_calls=True  # CRITICAL: Log token usage
    )

    elapsed = time.time() - start

    # Analyze tokens
    token_stats = analyze_dspy_trajectory(log_path)

    if not token_stats:
        print("⚠️  Could not extract token stats from log")
        return None

    # Calculate costs
    # Assume all tokens are from main model (Sonnet 4.5)
    # In reality, some may be from sub-model (Haiku) but log doesn't distinguish
    main_model = "claude-sonnet-4-5-20250929"
    total_cost = calculate_cost(
        token_stats["total_input_tokens"],
        token_stats["total_output_tokens"],
        main_model
    )

    print(f"\n✅ RLM Complete")
    print(f"   Time: {elapsed:.1f}s")
    print(f"   Iterations: {result.iteration_count}")
    print(f"   Converged: {result.converged}")
    print(f"   Input tokens: {token_stats['total_input_tokens']:,}")
    print(f"   Output tokens: {token_stats['total_output_tokens']:,}")
    print(f"   Total tokens: {token_stats['total_tokens']:,}")
    print(f"   Cost: ${total_cost:.4f}")
    print(f"   Tokens/iteration: {token_stats['total_tokens'] / result.iteration_count:.0f}")

    return {
        "pattern": "RLM",
        "elapsed": elapsed,
        "iterations": result.iteration_count,
        "converged": result.converged,
        "input_tokens": token_stats["total_input_tokens"],
        "output_tokens": token_stats["total_output_tokens"],
        "total_tokens": token_stats["total_tokens"],
        "cost": total_cost,
        "tokens_per_iteration": token_stats["total_tokens"] / result.iteration_count,
        "answer_length": len(result.answer),
        "log_path": log_path
    }


def run_react_test(query, ontology, max_iterations=8):
    """Run ReAct test and return token usage."""
    from rlm_runtime.engine.dspy_react import run_dspy_react

    log_path = "experiments/cost_analysis/react_cost_test.jsonl"

    print(f"\n{'='*70}")
    print("RUNNING REACT TEST")
    print(f"{'='*70}")
    print(f"Query: {query}")
    print(f"Max iterations: {max_iterations}")

    import time
    start = time.time()

    result = run_dspy_react(
        query,
        ontology,
        max_iterations=max_iterations,
        verbose=False,
        log_path=log_path,
        log_llm_calls=True  # CRITICAL: Log token usage
    )

    elapsed = time.time() - start

    # Analyze tokens
    token_stats = analyze_dspy_trajectory(log_path)

    if not token_stats:
        print("⚠️  Could not extract token stats from log")
        return None

    # Calculate costs (ReAct uses same model as RLM main)
    main_model = "claude-sonnet-4-5-20250929"
    total_cost = calculate_cost(
        token_stats["total_input_tokens"],
        token_stats["total_output_tokens"],
        main_model
    )

    print(f"\n✅ ReAct Complete")
    print(f"   Time: {elapsed:.1f}s")
    print(f"   Iterations: {result.iteration_count}")
    print(f"   Converged: {result.converged}")
    print(f"   Input tokens: {token_stats['total_input_tokens']:,}")
    print(f"   Output tokens: {token_stats['total_output_tokens']:,}")
    print(f"   Total tokens: {token_stats['total_tokens']:,}")
    print(f"   Cost: ${total_cost:.4f}")
    print(f"   Tokens/iteration: {token_stats['total_tokens'] / result.iteration_count:.0f}")

    return {
        "pattern": "ReAct",
        "elapsed": elapsed,
        "iterations": result.iteration_count,
        "converged": result.converged,
        "input_tokens": token_stats["total_input_tokens"],
        "output_tokens": token_stats["total_output_tokens"],
        "total_tokens": token_stats["total_tokens"],
        "cost": total_cost,
        "tokens_per_iteration": token_stats["total_tokens"] / result.iteration_count,
        "answer_length": len(result.answer),
        "log_path": log_path
    }


def compare_results(rlm_result, react_result):
    """Print comparison table."""
    print(f"\n{'='*70}")
    print("COST COMPARISON: RLM vs ReAct")
    print(f"{'='*70}")

    if not rlm_result or not react_result:
        print("⚠️  Missing results, cannot compare")
        return

    # Comparison table
    print(f"\n{'Metric':<25} {'RLM':<20} {'ReAct':<20} {'Winner':<15}")
    print("-" * 80)

    # Speed
    speed_diff = ((rlm_result['elapsed'] - react_result['elapsed']) / react_result['elapsed']) * 100
    speed_winner = "ReAct" if react_result['elapsed'] < rlm_result['elapsed'] else "RLM"
    print(f"{'Time (seconds)':<25} {rlm_result['elapsed']:<20.1f} {react_result['elapsed']:<20.1f} {speed_winner:<15}")

    # Iterations
    iter_winner = "RLM" if rlm_result['iterations'] < react_result['iterations'] else "ReAct"
    print(f"{'Iterations':<25} {rlm_result['iterations']:<20} {react_result['iterations']:<20} {iter_winner:<15}")

    # Tokens
    if react_result['total_tokens'] > 0:
        token_diff = ((rlm_result['total_tokens'] - react_result['total_tokens']) / react_result['total_tokens']) * 100
    else:
        token_diff = 0
    token_winner = "RLM" if rlm_result['total_tokens'] < react_result['total_tokens'] else "ReAct"
    print(f"{'Total tokens':<25} {rlm_result['total_tokens']:<20,} {react_result['total_tokens']:<20,} {token_winner:<15}")

    # Input tokens
    print(f"{'  Input tokens':<25} {rlm_result['input_tokens']:<20,} {react_result['input_tokens']:<20,}")

    # Output tokens
    print(f"{'  Output tokens':<25} {rlm_result['output_tokens']:<20,} {react_result['output_tokens']:<20,}")

    # Cost
    if react_result['cost'] > 0:
        cost_diff = ((rlm_result['cost'] - react_result['cost']) / react_result['cost']) * 100
    else:
        cost_diff = 0
    cost_winner = "RLM" if rlm_result['cost'] < react_result['cost'] else "ReAct"
    print(f"{'Cost (USD)':<25} ${rlm_result['cost']:<19.4f} ${react_result['cost']:<19.4f} {cost_winner:<15}")

    # Tokens per iteration
    tpi_winner = "RLM" if rlm_result['tokens_per_iteration'] < react_result['tokens_per_iteration'] else "ReAct"
    print(f"{'Tokens/iteration':<25} {rlm_result['tokens_per_iteration']:<20,.0f} {react_result['tokens_per_iteration']:<20,.0f} {tpi_winner:<15}")

    # Answer length
    print(f"{'Answer length':<25} {rlm_result['answer_length']:<20} {react_result['answer_length']:<20}")

    # Analysis
    print(f"\n{'='*70}")
    print("ANALYSIS")
    print(f"{'='*70}")

    print(f"\n🏆 Speed: {speed_winner} is {abs(speed_diff):.1f}% {'faster' if speed_diff > 0 else 'slower'}")
    print(f"🏆 Iterations: {iter_winner} uses {abs(rlm_result['iterations'] - react_result['iterations'])} {'fewer' if iter_winner == 'RLM' else 'more'} iterations")
    print(f"🏆 Tokens: {token_winner} uses {abs(token_diff):.1f}% {'fewer' if token_winner == 'RLM' else 'more'} tokens")
    print(f"💰 Cost: {cost_winner} is {abs(cost_diff):.1f}% {'cheaper' if cost_winner == 'RLM' else 'more expensive'}")

    # Key insights
    print(f"\n{'='*70}")
    print("KEY INSIGHTS")
    print(f"{'='*70}")

    # RLM characteristics
    print(f"\n📊 RLM Pattern:")
    print(f"   - {rlm_result['iterations']} iterations × {rlm_result['tokens_per_iteration']:.0f} tokens/iter")
    print(f"   - Code generation: ~{rlm_result['output_tokens'] / rlm_result['iterations']:.0f} output tokens/iter")
    print(f"   - Context growth: ~{rlm_result['input_tokens'] / rlm_result['iterations']:.0f} input tokens/iter")

    # ReAct characteristics
    print(f"\n📊 ReAct Pattern:")
    print(f"   - {react_result['iterations']} iterations × {react_result['tokens_per_iteration']:.0f} tokens/iter")
    print(f"   - Thought generation: ~{react_result['output_tokens'] / react_result['iterations']:.0f} output tokens/iter")
    print(f"   - Context growth: ~{react_result['input_tokens'] / react_result['iterations']:.0f} input tokens/iter")

    # Efficiency
    print(f"\n⚡ Efficiency:")
    if rlm_result['tokens_per_iteration'] < react_result['tokens_per_iteration']:
        print(f"   ✅ RLM is more token-efficient per iteration")
        print(f"      ({rlm_result['tokens_per_iteration']:.0f} vs {react_result['tokens_per_iteration']:.0f} tokens/iter)")
    else:
        print(f"   ✅ ReAct is more token-efficient per iteration")
        print(f"      ({react_result['tokens_per_iteration']:.0f} vs {rlm_result['tokens_per_iteration']:.0f} tokens/iter)")

    if rlm_result['iterations'] < react_result['iterations']:
        print(f"   ✅ RLM uses fewer iterations overall")
        print(f"      ({rlm_result['iterations']} vs {react_result['iterations']} iterations)")
    else:
        print(f"   ✅ ReAct uses fewer iterations overall")
        print(f"      ({react_result['iterations']} vs {rlm_result['iterations']} iterations)")

    # Cost breakdown
    print(f"\n💵 Cost Breakdown:")
    print(f"   RLM: ${rlm_result['cost']:.4f} = ${rlm_result['cost'] / rlm_result['iterations']:.5f}/iteration")
    print(f"   ReAct: ${react_result['cost']:.4f} = ${react_result['cost'] / react_result['iterations']:.5f}/iteration")

    # Projection for scale
    print(f"\n📈 Cost at Scale (1000 queries):")
    print(f"   RLM: ${rlm_result['cost'] * 1000:.2f}")
    print(f"   ReAct: ${react_result['cost'] * 1000:.2f}")
    savings = abs(rlm_result['cost'] - react_result['cost']) * 1000
    print(f"   Savings: ${savings:.2f} ({'RLM' if cost_winner == 'RLM' else 'ReAct'} cheaper)")


def main():
    """Run cost comparison."""
    print(f"\n{'='*70}")
    print("TOKEN COST ANALYSIS: RLM vs ReAct")
    print(f"{'='*70}")
    print(f"Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

    # Check environment
    if not os.environ.get("ANTHROPIC_API_KEY"):
        print("\n❌ ANTHROPIC_API_KEY not set")
        return 1

    # Create output directory
    Path("experiments/cost_analysis").mkdir(parents=True, exist_ok=True)

    # Test configuration
    query = "What is Activity in this ontology?"
    ontology = "ontology/prov.ttl"
    max_iterations = 8

    print(f"\nTest Configuration:")
    print(f"  Query: {query}")
    print(f"  Ontology: {ontology}")
    print(f"  Max iterations: {max_iterations}")
    print(f"  Models:")
    print(f"    - Main: Claude Sonnet 4.5 (${PRICING['claude-sonnet-4-5-20250929']['output']}/M output)")
    print(f"    - Sub: Claude Haiku (${PRICING['claude-3-5-haiku-20241022']['output']}/M output)")

    # Run tests
    rlm_result = run_rlm_test(query, ontology, max_iterations)
    react_result = run_react_test(query, ontology, max_iterations)

    # Compare
    compare_results(rlm_result, react_result)

    # Save results
    output_file = f"experiments/cost_analysis/comparison_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    with open(output_file, 'w') as f:
        json.dump({
            "timestamp": datetime.now().isoformat(),
            "query": query,
            "ontology": ontology,
            "max_iterations": max_iterations,
            "rlm": rlm_result,
            "react": react_result
        }, f, indent=2)

    print(f"\n📄 Results saved to: {output_file}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
