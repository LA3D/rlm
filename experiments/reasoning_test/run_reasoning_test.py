#!/usr/bin/env python3
"""Test RLM with reasoning-intensive UniProt queries.

Based on UniProt SPARQL examples, testing queries that require:
- Multi-hop reasoning (protein → annotation → entity)
- Spatial reasoning (sequence positions, overlaps)
- GO term hierarchy navigation
- Multiple entity type coordination

Usage:
    source ~/uvws/.venv/bin/activate
    python test_uniprot_reasoning.py
"""

import sys
import os
import json
from pathlib import Path
from datetime import datetime

sys.path.insert(0, str(Path(__file__).parent))


# Test queries organized by complexity level
REASONING_QUERIES = [
    {
        "id": "L3-1",
        "level": "L3-multi-entity",
        "query": "Find reviewed human proteins with kinase activity",
        "ontology": "ontology/uniprot/core.ttl",
        "complexity": "Multi-entity: Protein + Organism + GO classification + Review status",
        "reference_sparql": """
            PREFIX GO: <http://purl.obolibrary.org/obo/GO_>
            PREFIX up: <http://purl.uniprot.org/core/>
            PREFIX taxon: <http://purl.uniprot.org/taxonomy/>

            SELECT ?protein
            WHERE {
                ?protein a up:Protein ;
                         up:reviewed true ;
                         up:organism taxon:9606 ;
                         up:classifiedWith|(up:classifiedWith/rdfs:subClassOf) GO:0016301 .
            }
            LIMIT 10
        """,
        "reasoning_needed": [
            "Understand 'kinase activity' maps to GO:0016301",
            "Understand 'reviewed' means up:reviewed true (Swiss-Prot)",
            "Understand 'human' means taxon:9606",
            "Understand GO term hierarchy (classifiedWith + subclasses)"
        ],
        "expected_delegation": "Possibly: 'What GO term represents kinase activity?'"
    },
    {
        "id": "L3-2",
        "level": "L3-annotation",
        "query": "What diseases involve enzymes located in mitochondria?",
        "ontology": "ontology/uniprot/core.ttl",
        "complexity": "Multi-hop: Protein → Disease annotation + Subcellular location → Mitochondrion",
        "reference_sparql": """
            PREFIX up: <http://purl.uniprot.org/core/>
            PREFIX taxon: <http://purl.uniprot.org/taxonomy/>

            SELECT DISTINCT ?disease
            WHERE {
                ?protein a up:Protein ;
                         up:organism taxon:9606 ;
                         up:annotation ?disease_annotation, ?subcellularLocation .

                # Must be enzyme
                { ?protein up:enzyme [] }
                UNION
                { ?protein up:annotation/a up:Catalytic_Activity_Annotation }

                # Has disease annotation
                ?disease_annotation a up:Disease_Annotation ;
                                   up:disease ?disease .

                # Located in mitochondrion
                ?subcellularLocation a up:Subcellular_Location_Annotation ;
                                    up:locatedIn ?location .
                ?location up:cellularComponent ?component .
                ?component up:partOf* <http://purl.uniprot.org/locations/173> .
            }
            LIMIT 10
        """,
        "reasoning_needed": [
            "Understand 'enzyme' can be checked via up:enzyme OR Catalytic_Activity_Annotation",
            "Understand 'mitochondria' maps to location 173",
            "Coordinate two annotation types (disease + location)",
            "Handle transitive partOf* for cellular component hierarchy"
        ],
        "expected_delegation": "Possibly: 'What location URI represents mitochondria?'"
    },
    {
        "id": "L4-1",
        "level": "L4-spatial",
        "query": "Find diseases caused by natural variants in enzyme active sites",
        "ontology": "ontology/uniprot/core.ttl",
        "complexity": "Spatial reasoning: Check if variant position overlaps active site position",
        "reference_sparql": """
            PREFIX up: <http://purl.uniprot.org/core/>
            PREFIX taxon: <http://purl.uniprot.org/taxonomy/>
            PREFIX faldo: <http://biohackathon.org/resource/faldo#>
            PREFIX skos: <http://www.w3.org/2004/02/skos/core#>

            SELECT DISTINCT ?disease
            WHERE {
                ?protein a up:Protein ;
                         up:organism taxon:9606 ;
                         up:annotation ?disease_annotation, ?active_site_annotation, ?natural_variant_annotation .

                # Must be enzyme
                { ?protein up:enzyme [] }
                UNION
                { ?protein up:annotation/a up:Catalytic_Activity_Annotation }

                # Disease annotation
                ?disease_annotation a up:Disease_Annotation ;
                                   up:disease ?disease .

                # Active site position
                ?active_site_annotation a up:Active_Site_Annotation ;
                                       up:range ?active_site_range .
                ?active_site_range faldo:begin ?active_site_begin .
                ?active_site_begin faldo:position ?active_site_position ;
                                  faldo:reference ?sequence .

                # Natural variant position (related to disease)
                ?natural_variant_annotation a up:Natural_Variant_Annotation ;
                                           up:range ?natural_variant_range ;
                                           skos:related ?disease .
                ?natural_variant_range faldo:begin ?natural_variant_begin ;
                                      faldo:end ?natural_variant_end .
                ?natural_variant_begin faldo:position ?natural_variant_begin_position .
                ?natural_variant_end faldo:position ?natural_variant_end_position ;
                                    faldo:reference ?sequence .

                # Check overlap: variant position includes active site
                FILTER(?natural_variant_begin_position <= ?active_site_position
                       && ?active_site_position <= ?natural_variant_end_position)
            }
            LIMIT 10
        """,
        "reasoning_needed": [
            "Understand 'active site' is a sequence annotation with position",
            "Understand 'natural variant' is an annotation with begin/end positions",
            "Understand 'caused by' means variant skos:related disease",
            "Perform spatial reasoning: check if variant overlaps active site",
            "Use FALDO ontology for sequence positions"
        ],
        "expected_delegation": [
            "Possibly: 'How do I check if a sequence range overlaps a position?'",
            "Possibly: 'What annotation types represent active sites?'",
            "Possibly: 'How are variants linked to diseases?'"
        ]
    },
    {
        "id": "L3-3",
        "level": "L3-comparison",
        "query": "How do human proteins differ from mouse proteins in terms of annotation types?",
        "ontology": "ontology/uniprot/core.ttl",
        "complexity": "Aggregation across organisms + annotation type analysis",
        "reasoning_needed": [
            "Query two different organisms (taxon:9606, taxon:10090)",
            "Group annotations by type for each organism",
            "Compare counts or presence across organisms",
            "Synthesize differences"
        ],
        "expected_delegation": "Possibly: 'What are the most important annotation types to compare?'"
    },
    {
        "id": "L4-2",
        "level": "L4-integration",
        "query": "Find human proteins that have both disease associations and drug targets, and are membrane-bound",
        "ontology": "ontology/uniprot/core.ttl",
        "complexity": "Multi-constraint coordination: 3 annotation types + organism filter",
        "reasoning_needed": [
            "Coordinate three different annotation types",
            "Understand 'drug target' annotation representation",
            "Understand 'membrane-bound' subcellular location",
            "Ensure all conditions on same protein"
        ],
        "expected_delegation": [
            "Possibly: 'What annotation type represents drug targets?'",
            "Possibly: 'What location URIs represent membrane-bound?'"
        ]
    }
]


def analyze_tokens(log_path):
    """Extract token usage and delegation attempts from log."""
    if not Path(log_path).exists():
        return None

    total_input = 0
    total_output = 0
    llm_calls = 0
    llm_query_attempts = 0
    delegation_prompts = []

    with open(log_path) as f:
        for line in f:
            try:
                event = json.loads(line)

                # Track tokens
                if event.get("event") == "llm_response":
                    usage = event.get("usage", {})
                    total_input += usage.get("prompt_tokens", 0)
                    total_output += usage.get("completion_tokens", 0)
                    llm_calls += 1

                # Track delegation attempts
                if event.get("event") == "module_start":
                    code = event.get("inputs", {}).get("code", "")
                    reasoning = event.get("inputs", {}).get("reasoning", "")

                    if "llm_query(" in code:
                        llm_query_attempts += 1
                        # Extract delegation prompt
                        for line in code.split("\n"):
                            if "llm_query(" in line:
                                delegation_prompts.append(line.strip()[:200])
            except:
                continue

    total_tokens = total_input + total_output
    cost = (total_input / 1_000_000) * 3.0 + (total_output / 1_000_000) * 15.0

    return {
        "total_input": total_input,
        "total_output": total_output,
        "total_tokens": total_tokens,
        "llm_calls": llm_calls,
        "cost": cost,
        "llm_query_attempts": llm_query_attempts,
        "delegation_prompts": delegation_prompts,
        "used_delegation": llm_query_attempts > 0
    }


def run_test(query_info, max_iterations=15):
    """Run RLM test with reasoning query."""
    from rlm_runtime.engine.dspy_rlm import run_dspy_rlm

    query_id = query_info["id"]
    query = query_info["query"]
    ontology = query_info["ontology"]

    log_path = f"experiments/reasoning_test/{query_id.lower()}_test.jsonl"

    print(f"\n{'='*70}")
    print(f"TEST: {query_id} ({query_info['level']})")
    print(f"{'='*70}")
    print(f"Query: {query}")
    print(f"Complexity: {query_info['complexity']}")
    print(f"Budget: {max_iterations} iterations")

    if "reasoning_needed" in query_info:
        print(f"\nReasoning challenges:")
        for r in query_info["reasoning_needed"]:
            print(f"  - {r}")

    import time
    start = time.time()

    result = run_dspy_rlm(
        query,
        ontology,
        max_iterations=max_iterations,
        max_llm_calls=max_iterations * 2,
        verbose=False,
        log_path=log_path,
        log_llm_calls=True
    )

    elapsed = time.time() - start

    # Analyze
    token_stats = analyze_tokens(log_path)

    print(f"\n✅ Complete in {elapsed:.1f}s")
    print(f"   Iterations: {result.iteration_count} / {max_iterations}")
    print(f"   Converged: {result.converged}")
    print(f"   Tokens: {token_stats['total_tokens']:,}")
    print(f"   Cost: ${token_stats['cost']:.4f}")
    print(f"   LLM calls: {token_stats['llm_calls']}")

    # Delegation analysis
    if token_stats['used_delegation']:
        print(f"\n✅ DELEGATION USED!")
        print(f"   llm_query attempts: {token_stats['llm_query_attempts']}")
        print(f"   Delegation prompts:")
        for prompt in token_stats['delegation_prompts']:
            print(f"     → {prompt}")
    else:
        print(f"\n⚪ No delegation (solved directly)")

    print(f"\n   Answer length: {len(result.answer)} chars")
    print(f"   Answer preview:")
    preview = result.answer[:300].replace('\n', ' ')
    print(f"     {preview}...")

    return {
        "query_info": query_info,
        "execution": {
            "elapsed": elapsed,
            "iterations": result.iteration_count,
            "converged": result.converged,
            "answer": result.answer,
            "answer_length": len(result.answer)
        },
        "analysis": token_stats,
        "log_path": log_path
    }


def main():
    """Run reasoning complexity tests."""
    print(f"\n{'='*70}")
    print("UNIPROT REASONING TEST: Multi-hop & Spatial Queries")
    print(f"{'='*70}")
    print(f"Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

    if not os.environ.get("ANTHROPIC_API_KEY"):
        print("\n❌ ANTHROPIC_API_KEY not set")
        return 1

    # Create output directory
    Path("experiments/reasoning_test").mkdir(parents=True, exist_ok=True)

    print(f"\nTest Plan:")
    print(f"  - {len(REASONING_QUERIES)} reasoning queries (L3-L4 complexity)")
    print(f"  - Budget: 15 iterations, 30 LLM calls")
    print(f"  - Goal: See if complexity triggers delegation")

    print(f"\nQuery Overview:")
    for q in REASONING_QUERIES:
        print(f"\n  {q['id']} ({q['level']}): {q['query']}")
        print(f"    Complexity: {q['complexity']}")

    # Skip confirmation in non-interactive mode
    print(f"\n{'='*70}")
    print("Starting tests (5-10 minutes each)...")

    # Run tests
    results = []
    for i, query_info in enumerate(REASONING_QUERIES):
        print(f"\n\n{'#'*70}")
        print(f"# TEST {i+1}/{len(REASONING_QUERIES)}")
        print(f"{'#'*70}")

        result = run_test(query_info, max_iterations=15)
        results.append(result)

    # Summary
    print(f"\n{'='*70}")
    print("REASONING TEST SUMMARY")
    print(f"{'='*70}")

    total_delegation = sum(r['analysis']['llm_query_attempts'] for r in results)
    avg_cost = sum(r['analysis']['cost'] for r in results) / len(results)
    avg_iters = sum(r['execution']['iterations'] for r in results) / len(results)
    with_delegation = sum(1 for r in results if r['analysis']['used_delegation'])

    print(f"\nOverall:")
    print(f"  Tests run: {len(results)}")
    print(f"  Tests with delegation: {with_delegation} ({(with_delegation/len(results))*100:.0f}%)")
    print(f"  Total llm_query attempts: {total_delegation}")
    print(f"  Average iterations: {avg_iters:.1f}")
    print(f"  Average cost: ${avg_cost:.4f}")

    print(f"\n{'─'*70}")
    print("Individual Results:")
    print(f"{'─'*70}")

    for r in results:
        query_id = r['query_info']['id']
        level = r['query_info']['level']
        iters = r['execution']['iterations']
        cost = r['analysis']['cost']
        delegation = "✅ Yes" if r['analysis']['used_delegation'] else "⚪ No"
        attempts = r['analysis']['llm_query_attempts']

        print(f"\n{query_id} ({level}):")
        print(f"  Query: {r['query_info']['query']}")
        print(f"  Iterations: {iters}/15")
        print(f"  Cost: ${cost:.4f}")
        print(f"  Delegation: {delegation} ({attempts} attempts)")
        print(f"  Converged: {r['execution']['converged']}")

    # Analysis
    print(f"\n{'='*70}")
    print("ANALYSIS")
    print(f"{'='*70}")

    if with_delegation > 0:
        print(f"\n✅ SUCCESS: Delegation emerged on reasoning tasks!")
        print(f"   {with_delegation}/{len(results)} queries used llm_query")
        print(f"   Reasoning complexity triggers strategic delegation")

        # Show which levels triggered delegation
        l3_with_del = sum(1 for r in results
                          if 'L3' in r['query_info']['level']
                          and r['analysis']['used_delegation'])
        l4_with_del = sum(1 for r in results
                          if 'L4' in r['query_info']['level']
                          and r['analysis']['used_delegation'])

        if l3_with_del > 0:
            print(f"\n   L3 queries: {l3_with_del} used delegation")
        if l4_with_del > 0:
            print(f"   L4 queries: {l4_with_del} used delegation")
    else:
        print(f"\n⚪ NO DELEGATION on reasoning tasks")
        print(f"   Model solved all queries directly")
        print(f"   Possible reasons:")
        print(f"     1. AGENT_GUIDE.md provides sufficient patterns")
        print(f"     2. Model constructs complex queries without sub-LLM help")
        print(f"     3. Reasoning is explicit enough (not semantic ambiguity)")

    # Cost comparison
    print(f"\n{'='*70}")
    print("COST ANALYSIS")
    print(f"{'='*70}")

    print(f"\nAverage cost by level:")
    l3_costs = [r['analysis']['cost'] for r in results if 'L3' in r['query_info']['level']]
    l4_costs = [r['analysis']['cost'] for r in results if 'L4' in r['query_info']['level']]

    if l3_costs:
        print(f"  L3 average: ${sum(l3_costs)/len(l3_costs):.4f}")
    if l4_costs:
        print(f"  L4 average: ${sum(l4_costs)/len(l4_costs):.4f}")

    print(f"\nComparison to baselines:")
    print(f"  L1-L2 baseline: $0.12")
    print(f"  L3-L4 average: ${avg_cost:.4f}")
    cost_increase = ((avg_cost - 0.12) / 0.12) * 100
    print(f"  Increase: {cost_increase:+.0f}%")

    # Save results
    output_file = f"experiments/reasoning_test/results_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    with open(output_file, 'w') as f:
        json.dump({
            "timestamp": datetime.now().isoformat(),
            "test_type": "L3-L4_reasoning",
            "ontology": "uniprot/core.ttl",
            "results": results
        }, f, indent=2)

    print(f"\n📄 Results saved to: {output_file}")

    # Recommendations
    print(f"\n{'='*70}")
    print("RECOMMENDATIONS")
    print(f"{'='*70}")

    if with_delegation > 0:
        print(f"\n✅ Delegation emerges on complex queries")
        print(f"   - Document delegation patterns")
        print(f"   - Measure delegation ROI (cost vs quality)")
        print(f"   - Consider delegation tuning")
    else:
        print(f"\n⚪ Tool-first pattern handles reasoning tasks")
        print(f"   - AGENT_GUIDE.md provides sufficient scaffolding")
        print(f"   - Direct SPARQL construction works for L3-L4")
        print(f"   - Consider pattern library expansion")

    if avg_cost < 0.25:
        print(f"\n✅ Cost remains acceptable (< $0.25/query)")
        print(f"   - Still cheaper than ReAct baseline ($0.27)")
        print(f"   - Ready for production L3-L4 queries")
    else:
        print(f"\n⚠️  Cost approaching baseline")
        print(f"   - Review if complexity requires delegation")
        print(f"   - Consider query simplification")

    return 0


if __name__ == "__main__":
    sys.exit(main())
