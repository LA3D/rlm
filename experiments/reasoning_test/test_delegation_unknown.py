#!/usr/bin/env python3
"""Test delegation with a concept NOT in AGENT_GUIDE.md.

This tests whether llm_query is used for concept discovery (not just verification).

Usage:
    source ~/uvws/.venv/bin/activate
    python experiments/reasoning_test/test_delegation_unknown.py
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


def run_unknown_concept_test():
    """Test query with concept NOT in AGENT_GUIDE.md."""
    import dspy
    from rlm_runtime.engine.dspy_rlm import run_dspy_rlm_with_tools
    from rlm_runtime.tools.sparql_tools import make_sparql_tools

    print("\n" + "=" * 70)
    print("UNKNOWN CONCEPT TEST: Does llm_query get used for discovery?")
    print("=" * 70)
    print(f"Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print()

    # Read AGENT_GUIDE for context
    guide_path = Path("ontology/uniprot/AGENT_GUIDE.md")
    if guide_path.exists():
        context = guide_path.read_text()
        print(f"✓ Loaded AGENT_GUIDE.md ({len(context):,} chars)")

        # Verify "apoptosis" is NOT in the guide (or is minimal)
        apoptosis_count = context.lower().count("apoptosis")
        go_0006915_count = context.count("GO:0006915")
        print(f"  - 'apoptosis' occurrences: {apoptosis_count}")
        print(f"  - 'GO:0006915' occurrences: {go_0006915_count}")
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
    print(f"✓ Created {len(tools)} tools")

    # Test query with concept likely NOT in AGENT_GUIDE.md
    # Apoptosis is GO:0006915 but this is unlikely to be in examples
    query = "Find human proteins involved in apoptosis"
    print()
    print(f"Query: {query}")
    print(f"Expected: Model should delegate to llm_query to find GO term for apoptosis")
    print(f"GO term: GO:0006915 (programmed cell death)")
    print()
    print("-" * 70)
    print("Running RLM...")
    print("-" * 70)
    print()

    # Run with trajectory logging
    log_path = Path("experiments/reasoning_test/delegation_unknown_test.jsonl")

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
                # Check if it's for GO term discovery
                if "apoptosis" in code.lower() or "go term" in code.lower() or "go:" in code.lower():
                    print(f"  → llm_query used for concept discovery!")
            if "search_entity" in code:
                search_count += code.count("search_entity")
            if "sparql_select" in code or "sparql_query" in code:
                sparql_count += 1

    print(f"Tool usage:")
    print(f"  - llm_query calls: {delegation_count}")
    print(f"  - search calls: {search_count}")
    print(f"  - sparql calls: {sparql_count}")
    print()

    if delegation_count > 0:
        print("✅ llm_query was used!")
        if search_count == 0:
            print("   → Pure delegation pattern (no search)")
        else:
            print(f"   → Mixed pattern ({search_count} search + {delegation_count} delegation)")
    else:
        if search_count > 0:
            print(f"⚪ No delegation: Brute-force search pattern ({search_count} searches)")
        else:
            print("⚪ No delegation or search (found in context?)")

    # Check if correct GO term was found
    sparql = result.sparql or ""
    answer = result.answer or ""
    if "GO:0006915" in sparql or "GO:0006915" in answer or "0006915" in sparql:
        print("✅ Found correct GO term (GO:0006915)")
    else:
        print("⚠ GO:0006915 not found in output - may have used different approach")

    print()
    print("-" * 70)
    print("Answer preview:")
    print("-" * 70)
    print(result.answer[:500] if result.answer else "(no answer)")
    print()

    print(f"Log saved to: {log_path}")

    return delegation_count > 0


if __name__ == "__main__":
    success = run_unknown_concept_test()
    sys.exit(0 if success else 1)
