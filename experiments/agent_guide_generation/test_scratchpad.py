"""Quick test of Scratchpad approach on PROV ontology.

This tests the approach closest to the original rlm/core.py design:
- Persistent namespace
- Direct function calls
- Scratchpad model
"""

import os
import sys

# Ensure API key is set
if not os.environ.get("ANTHROPIC_API_KEY"):
    raise ValueError("Set ANTHROPIC_API_KEY environment variable")

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from experiments.agent_guide_scratchpad import run_scratchpad_experiment


if __name__ == "__main__":
    print("Testing Scratchpad approach on PROV ontology...")
    print("=" * 60)

    result = run_scratchpad_experiment("ontology/prov.ttl", "prov")

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
        print(f"Iterations: {result['iterations']}")
        print(f"Namespace vars: {result['namespace_vars']}")
    else:
        print("\n" + "=" * 60)
        print("FAILED")
        print("=" * 60)
        print(f"Error: {result['error']}")
