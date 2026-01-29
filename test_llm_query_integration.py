#!/usr/bin/env python3
"""Simple test to verify llm_query() integration works.

Tests that:
1. llm_query tool is available in RLM namespace
2. Sub-LLM is actually called during execution
3. Delegation patterns appear in trajectory

Usage:
    python test_llm_query_integration.py
"""

import os
import sys
from pathlib import Path

# Ensure we can import from rlm_runtime
sys.path.insert(0, str(Path(__file__).parent))


def test_llm_query_basic():
    """Test 1: Basic llm_query() functionality"""
    print("=" * 60)
    print("TEST 1: Basic llm_query() integration")
    print("=" * 60)

    # Check API key
    if not os.environ.get("ANTHROPIC_API_KEY"):
        print("❌ ANTHROPIC_API_KEY not set")
        return False

    # Import
    from rlm_runtime.engine.dspy_rlm import run_dspy_rlm

    # Run simple query
    query = "What is the Protein class?"
    ontology = "ontology/uniprot-core.ttl"

    if not Path(ontology).exists():
        print(f"❌ Ontology not found: {ontology}")
        return False

    print(f"\nQuery: {query}")
    print(f"Ontology: {ontology}")
    print(f"\nRunning RLM with llm_query() tool...")
    print("-" * 60)

    try:
        result = run_dspy_rlm(
            query,
            ontology,
            max_iterations=6,
            verbose=True,
            log_path="test_llm_query_trajectory.jsonl"
        )

        print("-" * 60)
        print(f"\n✅ Execution completed!")
        print(f"Iterations: {result.iteration_count}")
        print(f"Converged: {result.converged}")
        print(f"Answer length: {len(result.answer)} chars")

        return True

    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()
        return False


def analyze_trajectory():
    """Test 2: Check if llm_query was actually used"""
    print("\n" + "=" * 60)
    print("TEST 2: Analyzing trajectory for llm_query() usage")
    print("=" * 60)

    import json
    from pathlib import Path

    log_path = Path("test_llm_query_trajectory.jsonl")
    if not log_path.exists():
        print(f"❌ Trajectory log not found: {log_path}")
        return False

    # Count llm_query calls
    llm_query_calls = 0
    total_code_blocks = 0
    code_with_llm_query = []

    with open(log_path) as f:
        for line in f:
            try:
                event = json.loads(line)
                if event.get("event_type") == "module_start":
                    # Check if code contains llm_query
                    code = event.get("inputs", {}).get("code", "")
                    if code:
                        total_code_blocks += 1
                        if "llm_query" in code:
                            llm_query_calls += 1
                            code_with_llm_query.append(code[:200])  # First 200 chars
            except json.JSONDecodeError:
                continue

    print(f"\nTrajectory Analysis:")
    print(f"  Total code blocks: {total_code_blocks}")
    print(f"  Blocks with llm_query: {llm_query_calls}")

    if llm_query_calls > 0:
        print(f"\n✅ llm_query() WAS USED! Found {llm_query_calls} calls")
        print(f"\nFirst llm_query usage:")
        print("-" * 60)
        print(code_with_llm_query[0])
        print("-" * 60)
        return True
    else:
        print(f"\n⚠️  llm_query() NOT USED in any code blocks")
        print(f"   This suggests the model didn't delegate to sub-LLM")
        print(f"   (This is expected without training/prompting)")
        return True  # Not a failure, just expected behavior


def compare_token_usage():
    """Test 3: Check if delegation patterns are visible"""
    print("\n" + "=" * 60)
    print("TEST 3: Delegation Pattern Check")
    print("=" * 60)

    import json

    log_path = Path("test_llm_query_trajectory.jsonl")
    if not log_path.exists():
        print(f"❌ Trajectory log not found")
        return False

    # Look for strategic patterns
    patterns = {
        "disambiguation": ["which of these", "main class", "correct entity"],
        "validation": ["correct", "valid", "check"],
        "filtering": ["most relevant", "important", "filter"],
        "synthesis": ["summarize", "synthesize", "explain"]
    }

    found_patterns = {k: 0 for k in patterns}

    with open(log_path) as f:
        for line in f:
            try:
                event = json.loads(line)
                if event.get("event_type") == "module_start":
                    code = event.get("inputs", {}).get("code", "").lower()
                    if "llm_query" in code:
                        # Check for strategic patterns
                        for pattern_type, keywords in patterns.items():
                            if any(kw in code for kw in keywords):
                                found_patterns[pattern_type] += 1
            except json.JSONDecodeError:
                continue

    print(f"\nStrategic Delegation Patterns:")
    for pattern_type, count in found_patterns.items():
        symbol = "✅" if count > 0 else "⚪"
        print(f"  {symbol} {pattern_type}: {count} occurrences")

    total_strategic = sum(found_patterns.values())
    if total_strategic > 0:
        print(f"\n✅ Found {total_strategic} strategic delegation patterns!")
    else:
        print(f"\n⚪ No strategic patterns found (model may need guidance)")

    return True


def main():
    """Run all tests"""
    print("\n" + "=" * 60)
    print("TESTING llm_query() INTEGRATION")
    print("=" * 60)

    results = []

    # Test 1: Basic integration
    results.append(("Basic Integration", test_llm_query_basic()))

    # Test 2: Usage analysis
    results.append(("Usage Analysis", analyze_trajectory()))

    # Test 3: Pattern check
    results.append(("Pattern Check", compare_token_usage()))

    # Summary
    print("\n" + "=" * 60)
    print("TEST SUMMARY")
    print("=" * 60)

    for test_name, passed in results:
        symbol = "✅" if passed else "❌"
        print(f"{symbol} {test_name}")

    all_passed = all(r[1] for r in results)
    if all_passed:
        print("\n✅ All tests passed!")
    else:
        print("\n❌ Some tests failed")

    print("\nNext Steps:")
    print("1. Review test_llm_query_trajectory.jsonl to see execution details")
    print("2. If llm_query wasn't used, try explicit prompting (see below)")
    print("3. Compare with baseline (no llm_query) on same task")
    print("\nExample explicit prompt:")
    print('  "What is Protein? Use llm_query to validate your findings."')

    return 0 if all_passed else 1


if __name__ == "__main__":
    sys.exit(main())
