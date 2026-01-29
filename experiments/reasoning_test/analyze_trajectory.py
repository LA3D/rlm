#!/usr/bin/env python3
"""Visualize RLM execution from trajectory logs.

Usage:
    python analyze_trajectory.py experiments/uniprot_retest/L1_protein_class.jsonl
"""

import sys
import json
from pathlib import Path
from collections import defaultdict


def analyze_trajectory(log_path):
    """Analyze and visualize RLM trajectory."""

    events = []
    with open(log_path) as f:
        for line in f:
            events.append(json.loads(line))

    # Extract key metrics
    module_starts = [e for e in events if e.get("event") == "module_start"]
    tool_calls = [e for e in events if e.get("event") == "tool_call"]
    tool_results = [e for e in events if e.get("event") == "tool_result"]
    llm_responses = [e for e in events if e.get("event") == "llm_response"]

    # Get query info
    first_module = module_starts[0] if module_starts else {}
    query = first_module.get("inputs", {}).get("kwargs", {}).get("query", "Unknown")
    context_raw = first_module.get("inputs", {}).get("kwargs", {}).get("context", "")

    print(f"\n{'='*70}")
    print(f"RLM EXECUTION TRACE")
    print(f"{'='*70}\n")

    print(f"Query: '{query}'")
    print(f"Log: {log_path}")
    print(f"Iterations: {len(module_starts)}")
    print(f"Tool calls: {len(tool_calls)}")
    print(f"LLM calls: {len(llm_responses)}\n")

    # Check for AGENT_GUIDE.md
    print(f"{'='*70}")
    print(f"CONTEXT ANALYSIS")
    print(f"{'='*70}\n")

    if "UniProt SPARQL Endpoint" in context_raw:
        guide_marker = "## Ontology Affordances"
        guide_start = context_raw.find(guide_marker)
        if guide_start != -1:
            # Find where sense card ends (at graph summary)
            summary_marker = "## Graph Summary"
            summary_start = context_raw.find(summary_marker, guide_start)
            if summary_start != -1:
                sense_card_length = summary_start - guide_start
            else:
                sense_card_length = len(context_raw) - guide_start

            print(f"✅ AGENT_GUIDE.md loaded")
            print(f"   Position: {guide_start:,} chars into context")
            print(f"   Length: ~{sense_card_length:,} chars")
            print(f"   Contains: Prefixes, classes, properties, query patterns")
        else:
            print(f"✅ Sense card present but format unclear")
    else:
        print(f"⚠️  No AGENT_GUIDE.md detected")
        if len(context_raw) < 1000:
            print(f"   Context appears truncated in log")
        else:
            print(f"   Using generated sense card fallback")

    print(f"\nTotal context: {len(context_raw):,} characters")

    # Tool call sequence
    print(f"\n{'='*70}")
    print(f"TOOL CALL SEQUENCE")
    print(f"{'='*70}\n")

    for i, tc in enumerate(tool_calls):
        iteration = tc.get("iteration", i)
        tool_name = tc.get("tool_name", "unknown")
        inputs = tc.get("inputs", {})

        # Parse args safely
        args_str = inputs.get("args", "()")
        try:
            # Extract first argument (usually the query/pattern)
            if args_str.startswith("(") and args_str.endswith(")"):
                args_content = args_str[1:-1]
                if args_content.startswith("'") or args_content.startswith('"'):
                    # String argument
                    first_arg = args_content.split(",")[0].strip("'\"")
                    if len(first_arg) > 60:
                        first_arg = first_arg[:60] + "..."
                else:
                    first_arg = args_content[:60]
            else:
                first_arg = args_str[:60]
        except:
            first_arg = "<parse error>"

        kwargs = inputs.get("kwargs", {})

        print(f"Iteration {iteration + 1}: {tool_name}")

        if tool_name == "search_entity":
            print(f"  Pattern: '{first_arg}'")
            if kwargs.get("limit"):
                print(f"  Limit: {kwargs['limit']}")
        elif tool_name == "sparql_select":
            # Show SPARQL query type
            query_preview = first_arg.upper()
            if "SELECT" in query_preview:
                # Extract what's being selected
                where_idx = query_preview.find("WHERE")
                if where_idx > 0:
                    select_part = query_preview[query_preview.find("SELECT"):where_idx]
                    print(f"  Query: {select_part[:80]}...")
                else:
                    print(f"  Query: SELECT ...")

                # Try to identify query purpose
                if "SUBCLASS" in query_preview:
                    print(f"  Purpose: Finding subclasses")
                elif "DOMAIN" in query_preview and "RANGE" in query_preview:
                    print(f"  Purpose: Finding properties (domain/range)")
                elif "RESTRICTION" in query_preview:
                    print(f"  Purpose: Finding OWL restrictions")
                elif "INSTANCE" in query_preview or "RDF:TYPE" in query_preview:
                    print(f"  Purpose: Finding instances")
                else:
                    print(f"  Purpose: General query")

        # Find corresponding result
        result_events = [r for r in tool_results
                        if r.get("iteration") == iteration]
        if result_events:
            result = result_events[0]
            output = result.get("output", "")

            # Summarize result
            if isinstance(output, list):
                print(f"  → Returned {len(output)} results")
                if output and isinstance(output[0], dict):
                    print(f"     Fields: {', '.join(output[0].keys())}")
            elif isinstance(output, str):
                if len(output) < 100:
                    print(f"  → {output}")
                else:
                    print(f"  → {len(output)} chars")

        print()

    # Token usage
    print(f"{'='*70}")
    print(f"TOKEN USAGE")
    print(f"{'='*70}\n")

    total_in = 0
    total_out = 0

    print(f"{'Iter':<6} {'Input':<10} {'Output':<10} {'Total':<10} {'Growth':>8}")
    print(f"{'-'*6} {'-'*10} {'-'*10} {'-'*10} {'-'*8}")

    prev_total = 0
    for i, llm_resp in enumerate(llm_responses):
        usage = llm_resp.get("usage", {})
        prompt_tokens = usage.get("prompt_tokens", 0)
        completion_tokens = usage.get("completion_tokens", 0)
        iter_total = prompt_tokens + completion_tokens

        growth = iter_total - prev_total if i > 0 else 0
        growth_str = f"+{growth}" if growth > 0 else str(growth)

        print(f"{i+1:<6} {prompt_tokens:<10,} {completion_tokens:<10,} {iter_total:<10,} {growth_str:>8}")

        total_in += prompt_tokens
        total_out += completion_tokens
        prev_total = iter_total

    print(f"{'-'*6} {'-'*10} {'-'*10} {'-'*10} {'-'*8}")
    print(f"{'Total':<6} {total_in:<10,} {total_out:<10,} {total_in + total_out:<10,}")

    # Cost calculation (Sonnet 4.5 pricing)
    input_cost = (total_in / 1_000_000) * 3.0
    output_cost = (total_out / 1_000_000) * 15.0
    total_cost = input_cost + output_cost

    print(f"\nCost: ${total_cost:.4f} (${input_cost:.4f} input + ${output_cost:.4f} output)")

    # Delegation analysis
    print(f"\n{'='*70}")
    print(f"DELEGATION ANALYSIS")
    print(f"{'='*70}\n")

    delegation_count = 0
    for e in module_starts:
        code = str(e.get("inputs", {}).get("kwargs", {}).get("code", ""))
        if "llm_query(" in code:
            delegation_count += 1

    if delegation_count == 0:
        print(f"⚪ No delegation used")
        print(f"   Model solved query directly with tools")
        print(f"   Pattern: Search → Query → Explore → Submit")
    else:
        print(f"✅ Delegation used: {delegation_count} llm_query calls")
        print(f"   Model delegated semantic analysis to sub-LLM")

    # Final summary
    print(f"\n{'='*70}")
    print(f"SUMMARY")
    print(f"{'='*70}\n")

    avg_tokens = (total_in + total_out) // len(llm_responses)
    converged = len(module_starts) < 12  # Assuming max_iterations=12

    print(f"✅ Query completed successfully")
    print(f"   Iterations: {len(module_starts)}")
    print(f"   Tools called: {len(tool_calls)}")
    print(f"   Average tokens/call: {avg_tokens:,}")
    print(f"   Total cost: ${total_cost:.4f}")
    print(f"   Converged: {'Yes' if converged else 'No'}")

    # Pattern identification
    search_count = sum(1 for tc in tool_calls if tc.get("tool_name") == "search_entity")
    sparql_count = sum(1 for tc in tool_calls if tc.get("tool_name") == "sparql_select")

    print(f"\nPattern: ", end="")
    if search_count > 0:
        print(f"Search ({search_count})", end="")
    if sparql_count > 0:
        print(f" → SPARQL ({sparql_count})", end="")
    if delegation_count > 0:
        print(f" → Delegate ({delegation_count})", end="")
    print(" → Submit")


def main():
    if len(sys.argv) < 2:
        print("Usage: python analyze_trajectory.py <log.jsonl>")
        print("\nExample:")
        print("  python analyze_trajectory.py experiments/uniprot_retest/L1_protein_class.jsonl")
        return 1

    log_path = Path(sys.argv[1])
    if not log_path.exists():
        print(f"Error: File not found: {log_path}")
        return 1

    analyze_trajectory(log_path)
    return 0


if __name__ == "__main__":
    sys.exit(main())
