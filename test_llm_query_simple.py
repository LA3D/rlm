#!/usr/bin/env python3
"""Simple test with detailed trajectory analysis.

Improved version with:
1. Environment check (uv)
2. Better debugging output
3. Detailed code block analysis
4. Clear model behavior explanation

Usage:
    source ~/uvws/.venv/bin/activate
    python test_llm_query_simple.py
"""

import os
import sys
import json
from pathlib import Path
from datetime import datetime

# Add project root
sys.path.insert(0, str(Path(__file__).parent))


def check_environment():
    """Check that we're in the right environment."""
    print("=" * 70)
    print("ENVIRONMENT CHECK")
    print("=" * 70)

    # Check virtual env
    venv = os.environ.get('VIRTUAL_ENV', '')
    if 'uvws' in venv:
        print(f"✅ Using uv environment: {venv}")
    else:
        print(f"⚠️  Not in uvws environment!")
        print(f"   Current: {venv if venv else 'No venv active'}")
        print(f"\n   Run: source ~/uvws/.venv/bin/activate")
        return False

    # Check API key
    api_key = os.environ.get('ANTHROPIC_API_KEY', '')
    if api_key:
        print(f"✅ ANTHROPIC_API_KEY set ({api_key[:10]}...)")
    else:
        print(f"❌ ANTHROPIC_API_KEY not set")
        return False

    # Check imports
    try:
        from rlm_runtime.engine.dspy_rlm import run_dspy_rlm
        from rlm_runtime.tools.delegation_tools import make_llm_query_tool
        print(f"✅ Imports working")
    except ImportError as e:
        print(f"❌ Import error: {e}")
        return False

    return True


def run_test_query():
    """Run a single test query with trajectory logging."""
    print("\n" + "=" * 70)
    print("RUNNING TEST QUERY")
    print("=" * 70)

    from rlm_runtime.engine.dspy_rlm import run_dspy_rlm

    query = "What is Activity in this ontology?"
    ontology = "ontology/prov.ttl"

    if not Path(ontology).exists():
        print(f"❌ Ontology not found: {ontology}")
        print(f"\nAvailable ontologies:")
        for ont in sorted(Path("ontology").glob("*.ttl"))[:5]:
            print(f"   - {ont}")
        return None

    log_path = "test_llm_query_trajectory.jsonl"
    print(f"\nConfiguration:")
    print(f"  Query: {query}")
    print(f"  Ontology: {ontology}")
    print(f"  Log: {log_path}")
    print(f"  Max iterations: 6")

    print(f"\n{'─' * 70}")
    print("EXECUTING...")
    print(f"{'─' * 70}\n")

    try:
        import time
        start = time.time()

        result = run_dspy_rlm(
            query,
            ontology,
            max_iterations=6,
            verbose=True,  # This will show iteration-by-iteration progress
            log_path=log_path
        )

        elapsed = time.time() - start

        print(f"\n{'─' * 70}")
        print("EXECUTION COMPLETE")
        print(f"{'─' * 70}")
        print(f"✅ Time: {elapsed:.1f}s")
        print(f"✅ Iterations: {result.iteration_count}")
        print(f"✅ Converged: {result.converged}")
        print(f"✅ Answer length: {len(result.answer)} chars")

        return {
            "result": result,
            "log_path": log_path,
            "elapsed": elapsed
        }

    except Exception as e:
        print(f"\n❌ Execution failed: {e}")
        import traceback
        traceback.print_exc()
        return None


def analyze_trajectory_detailed(log_path):
    """Detailed analysis of what the model actually did."""
    print("\n" + "=" * 70)
    print("DETAILED TRAJECTORY ANALYSIS")
    print("=" * 70)

    if not Path(log_path).exists():
        print(f"❌ Log file not found: {log_path}")
        return

    # Parse all events
    events = []
    with open(log_path) as f:
        for line in f:
            try:
                events.append(json.loads(line))
            except json.JSONDecodeError:
                continue

    if not events:
        print("❌ No events found in log")
        return

    print(f"✅ Loaded {len(events)} events from trajectory log")

    # Extract code blocks with iteration tracking
    iterations = []
    current_iter = None

    for event in events:
        if event.get("event_type") == "module_start":
            code = event.get("inputs", {}).get("code", "")
            reasoning = event.get("inputs", {}).get("reasoning", "")

            if code:
                current_iter = {
                    "code": code,
                    "reasoning": reasoning,
                    "has_llm_query": "llm_query(" in code,
                    "timestamp": event.get("timestamp", "")
                }
        elif event.get("event_type") == "module_end" and current_iter:
            output = event.get("outputs", {}).get("output", "")
            current_iter["output"] = output[:500]  # Truncate
            iterations.append(current_iter)
            current_iter = None

    # Summary stats
    total_iters = len(iterations)
    iters_with_llm_query = sum(1 for it in iterations if it["has_llm_query"])

    print(f"\n{'─' * 70}")
    print("SUMMARY")
    print(f"{'─' * 70}")
    print(f"Total iterations: {total_iters}")
    print(f"Iterations with llm_query: {iters_with_llm_query}")

    if iters_with_llm_query > 0:
        print(f"\n✅ llm_query WAS USED! ({iters_with_llm_query} times)")
        print(f"   → Strategic delegation is working!")
    else:
        print(f"\n⚪ llm_query NOT USED")
        print(f"   → Model didn't delegate (expected without training)")

    # Show each iteration in detail
    print(f"\n{'─' * 70}")
    print("ITERATION-BY-ITERATION BREAKDOWN")
    print(f"{'─' * 70}")

    for i, it in enumerate(iterations, 1):
        print(f"\n🔹 Iteration {i}")
        print(f"{'─' * 70}")

        # Show reasoning if available
        if it.get("reasoning"):
            print(f"Reasoning:")
            print(f"  {it['reasoning'][:200]}...")
            print()

        # Show code with highlighting
        print(f"Code Generated:")
        code_lines = it["code"].split("\n")
        for line in code_lines[:15]:  # First 15 lines
            if "llm_query" in line:
                print(f"  >>> {line}  ⭐ SUB-LLM DELEGATION")
            elif "search_entity" in line or "sparql_select" in line:
                print(f"  >>> {line}")
            elif line.strip() and not line.strip().startswith("#"):
                print(f"      {line}")

        if len(code_lines) > 15:
            print(f"      ... ({len(code_lines) - 15} more lines)")

        # Show output preview
        if it.get("output"):
            print(f"\nOutput Preview:")
            output_preview = it["output"][:200].replace("\n", " ")
            print(f"  {output_preview}...")

        print()

    # Analyze delegation patterns
    if iters_with_llm_query > 0:
        print(f"\n{'─' * 70}")
        print("DELEGATION PATTERN ANALYSIS")
        print(f"{'─' * 70}")

        for i, it in enumerate(iterations, 1):
            if it["has_llm_query"]:
                print(f"\n🎯 Delegation in Iteration {i}:")

                # Extract llm_query calls
                for line in it["code"].split("\n"):
                    if "llm_query" in line:
                        # Try to identify the pattern
                        line_lower = line.lower()
                        if any(kw in line_lower for kw in ["which", "what", "is"]):
                            pattern = "❓ Disambiguation/Question"
                        elif any(kw in line_lower for kw in ["correct", "valid", "check"]):
                            pattern = "✓ Validation"
                        elif any(kw in line_lower for kw in ["important", "relevant", "filter"]):
                            pattern = "🔍 Filtering"
                        elif any(kw in line_lower for kw in ["summarize", "synthesize", "explain"]):
                            pattern = "📝 Synthesis"
                        else:
                            pattern = "❔ Other"

                        print(f"   {pattern}")
                        print(f"   Code: {line.strip()[:80]}...")

    # Recommendations
    print(f"\n{'─' * 70}")
    print("RECOMMENDATIONS")
    print(f"{'─' * 70}")

    if iters_with_llm_query > 0:
        print("\n✅ Strategic delegation is working!")
        print("\n   Next steps:")
        print("   1. Test on L2-L3 complexity tasks")
        print("   2. Compare with ReAct baseline")
        print("   3. Measure quality improvement")
    else:
        print("\n⚪ Model didn't use delegation (this is EXPECTED)")
        print("\n   Per Prime Intellect research, models need:")
        print("   - RL training on delegation patterns")
        print("   - Explicit prompting")
        print("   - More complex tasks (L2-L3) to trigger use")
        print("\n   Try:")
        print('   1. Explicit prompt: "Use llm_query to validate findings"')
        print("   2. Test on harder L2-L3 tasks")
        print("   3. Compare performance anyway (baseline check)")


def save_summary(test_data):
    """Save a human-readable summary."""
    if not test_data:
        return

    summary_file = "test_llm_query_summary.txt"

    with open(summary_file, 'w') as f:
        f.write("=" * 70 + "\n")
        f.write("llm_query() INTEGRATION TEST SUMMARY\n")
        f.write("=" * 70 + "\n")
        f.write(f"Timestamp: {datetime.now().isoformat()}\n")
        f.write(f"Time: {test_data['elapsed']:.1f}s\n")
        f.write(f"Iterations: {test_data['result'].iteration_count}\n")
        f.write(f"Converged: {test_data['result'].converged}\n")
        f.write(f"\nTrajectory log: {test_data['log_path']}\n")
        f.write("\nAnswer:\n")
        f.write("-" * 70 + "\n")
        f.write(test_data['result'].answer)
        f.write("\n" + "-" * 70 + "\n")

    print(f"\n📄 Summary saved to: {summary_file}")


def main():
    """Run complete test with detailed analysis."""
    print("\n" + "=" * 70)
    print("llm_query() INTEGRATION TEST")
    print("=" * 70)
    print(f"Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

    # Check environment
    if not check_environment():
        print("\n❌ Environment check failed")
        print("\nMake sure to:")
        print("  1. source ~/uvws/.venv/bin/activate")
        print("  2. export ANTHROPIC_API_KEY=...")
        return 1

    # Run test
    test_data = run_test_query()
    if not test_data:
        print("\n❌ Test execution failed")
        return 1

    # Analyze trajectory
    analyze_trajectory_detailed(test_data["log_path"])

    # Save summary
    save_summary(test_data)

    print("\n" + "=" * 70)
    print("TEST COMPLETE")
    print("=" * 70)
    print("\nGenerated files:")
    print(f"  - {test_data['log_path']} (JSONL trajectory)")
    print(f"  - test_llm_query_summary.txt (human-readable summary)")
    print("\nYou can now:")
    print(f"  1. Review the trajectory: cat {test_data['log_path']}")
    print(f"  2. Read the summary: cat test_llm_query_summary.txt")
    print(f"  3. Compare with ReAct baseline")

    return 0


if __name__ == "__main__":
    sys.exit(main())
