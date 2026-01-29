#!/usr/bin/env python3
"""Quick test to verify delegation guidance triggers llm_query usage.

This runs a single L3 query and checks if llm_query is called.

Usage:
    source ~/uvws/.venv/bin/activate
    python experiments/reasoning_test/test_delegation.py
"""

import sys
import os
from pathlib import Path
from datetime import datetime

# Add project root to path
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

# Verify API key
if not os.environ.get("ANTHROPIC_API_KEY"):
    print("ERROR: Set ANTHROPIC_API_KEY environment variable")
    sys.exit(1)


def run_delegation_test():
    """Run L3-1 query and check for llm_query usage."""
    import dspy
    from rlm_runtime.engine.dspy_rlm import run_dspy_rlm_with_tools
    from rlm_runtime.tools.sparql_tools import make_sparql_tools

    print("\n" + "=" * 70)
    print("DELEGATION TEST: Does llm_query get used with guidance?")
    print("=" * 70)
    print(f"Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print()

    # Read AGENT_GUIDE for context
    guide_path = Path("ontology/uniprot/AGENT_GUIDE.md")
    if guide_path.exists():
        context = guide_path.read_text()
        print(f"✓ Loaded AGENT_GUIDE.md ({len(context):,} chars)")
    else:
        print("WARNING: No AGENT_GUIDE.md found")
        context = "UniProt ontology endpoint: https://sparql.uniprot.org/sparql"

    # Create tools
    ns = {}
    tools = make_sparql_tools(
        endpoint="https://sparql.uniprot.org/sparql",
        ns=ns,
        max_results=100
    )
    print(f"✓ Created {len(tools)} tools: {list(tools.keys())}")

    # Test query (L3-1)
    query = "Find reviewed human proteins with kinase activity"
    print()
    print(f"Query: {query}")
    print(f"Complexity: Multi-entity (Protein + Organism + GO + Review status)")
    print()
    print("-" * 70)
    print("Running RLM with delegation guidance...")
    print("-" * 70)
    print()

    # Run with trajectory logging
    log_path = Path("experiments/reasoning_test/delegation_test.jsonl")

    start_time = datetime.now()
    result = run_dspy_rlm_with_tools(
        query,
        context=context,
        tools=tools,
        ontology_name="uniprot",
        ns=ns,
        max_iterations=15,
        max_llm_calls=30,
        verbose=True,
        log_path=str(log_path),
        log_llm_calls=True
    )
    elapsed = (datetime.now() - start_time).total_seconds()

    # Analyze results
    print()
    print("=" * 70)
    print("RESULTS")
    print("=" * 70)
    print(f"Time: {elapsed:.1f}s")
    print(f"Iterations: {result.iteration_count}")
    print(f"Converged: {result.converged}")
    print()

    # Check for llm_query in trajectory
    delegation_count = 0
    search_count = 0
    sparql_count = 0

    if result.trajectory:
        for step in result.trajectory:
            code = step.get("code", "")
            if "llm_query" in code:
                delegation_count += 1
            if "search_entity" in code:
                search_count += code.count("search_entity")
            if "sparql_select" in code:
                sparql_count += code.count("sparql_select")

    print(f"Tool usage:")
    print(f"  - llm_query calls: {delegation_count}")
    print(f"  - search_entity calls: {search_count}")
    print(f"  - sparql_select calls: {sparql_count}")
    print()

    if delegation_count > 0:
        print("✅ SUCCESS: llm_query was used for delegation!")
    else:
        print("⚪ No delegation: Model used tool-first pattern")

    # Calculate cost estimate
    # Rough estimate: $0.003 per 1K input tokens, $0.015 per 1K output tokens
    # We don't have exact token counts, but can estimate from iterations
    estimated_cost = result.iteration_count * 0.03  # ~$0.03 per iteration average
    print(f"\nEstimated cost: ${estimated_cost:.2f}")

    print()
    print("-" * 70)
    print("Answer preview:")
    print("-" * 70)
    print(result.answer[:500] if result.answer else "(no answer)")
    print()

    print(f"Log saved to: {log_path}")

    return delegation_count > 0


if __name__ == "__main__":
    success = run_delegation_test()
    sys.exit(0 if success else 1)
