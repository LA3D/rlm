"""Quick test of DSPy ReAct approach on PROV ontology.

This is a minimal test to verify the DSPy ReAct implementation works
before running the full comparison.
"""

import os
import sys

# Ensure API key is set
if not os.environ.get("ANTHROPIC_API_KEY"):
    raise ValueError("Set ANTHROPIC_API_KEY environment variable")

# Add parent directory to path so we can import the experiment module
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from experiments.agent_guide_dspy_react import run_react_experiment


if __name__ == "__main__":
    print("Testing DSPy ReAct approach on PROV ontology...")
    print("=" * 60)

    result = run_react_experiment("ontology/prov.ttl", "prov")

    if "error" not in result:
        print("\n" + "=" * 60)
        print("SUCCESS!")
        print("=" * 60)
        print(f"\nGuide preview (first 500 chars):")
        print("-" * 60)
        print(result["guide"][:500])
        print("...")
        print("-" * 60)
        print(f"\nFull guide length: {len(result['guide'])} chars")
        print(f"Elapsed time: {result['elapsed_seconds']:.1f}s")
        print(f"Tool calls: {result.get('tool_calls', 'unknown')}")
    else:
        print("\n" + "=" * 60)
        print("FAILED")
        print("=" * 60)
        print(f"Error: {result['error']}")
