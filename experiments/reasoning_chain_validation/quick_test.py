#!/usr/bin/env python3
"""Quick test to validate reasoning chain experiment setup.

This runs a minimal test comparing baseline vs exemplar3 on 1 task.
Use this to verify the experiment infrastructure before running the full suite.

Usage:
    python quick_test.py
"""

import os
import sys

# Ensure API key
if not os.environ.get("ANTHROPIC_API_KEY"):
    print("Error: Set ANTHROPIC_API_KEY environment variable")
    sys.exit(1)

from rc_001_exemplar_impact import (
    run_task,
    TestTask,
    analyze_behavior
)


def quick_test():
    """Run minimal test to validate setup."""

    print("=" * 60)
    print("QUICK TEST: Reasoning Chain Validation Setup")
    print("=" * 60)

    # Single test task
    task = TestTask(
        id="quick-test",
        level=2,
        question="What are the GO annotations for insulin?",
        expected_patterns=["up:GO_Annotation", "insulin"],
        anti_patterns=[]
    )

    conditions = ["baseline", "exemplar3"]

    results = []
    for condition in conditions:
        print(f"\nRunning: {condition.upper()}")
        print("-" * 40)

        result = run_task(condition, task)
        results.append(result)

        print(f"Passed: {result.passed}")
        print(f"Behavior score: {result.behavior_indicators['score']:.2f}")
        print(f"Query preview: {result.generated_query[:100]}...")

    # Compare
    print("\n" + "=" * 60)
    print("COMPARISON")
    print("=" * 60)

    for result in results:
        indicators = result.behavior_indicators
        print(f"\n{result.condition.upper()}:")
        print(f"  Pass: {result.passed}")
        print(f"  Overall score: {indicators['score']:.2f}")
        print(f"  State tracking: {indicators.get('explicit_state_tracking', False)}")
        print(f"  Verification: {indicators.get('verification_present', False)}")
        print(f"  Anti-pattern awareness: {indicators.get('anti_pattern_mention', False)}")

    # Verdict
    print("\n" + "=" * 60)
    print("VERDICT")
    print("=" * 60)

    baseline_score = results[0].behavior_indicators['score']
    exemplar_score = results[1].behavior_indicators['score']

    if exemplar_score > baseline_score:
        print(f"Exemplar shows improvement: {baseline_score:.2f} -> {exemplar_score:.2f}")
        print("This suggests reasoning chains are worth investigating!")
    elif exemplar_score == baseline_score:
        print(f"No difference detected: both at {baseline_score:.2f}")
        print("May need more exemplars or different tasks.")
    else:
        print(f"Baseline performed better: {baseline_score:.2f} vs {exemplar_score:.2f}")
        print("Unexpected - check exemplar quality.")

    print("\nQuick test complete. Run full experiment with:")
    print("  python rc_001_exemplar_impact.py")


if __name__ == "__main__":
    quick_test()
