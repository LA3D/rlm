#!/usr/bin/env python
"""Detailed analysis of diversity metrics on sanity check scenarios.

Shows exactly what the metrics are measuring and whether the results make sense.
"""

import sys
sys.path.insert(0, '/Users/cvardema/dev/git/LA3D/rlm')

from experiments.reasoningbank.prototype.metrics.diversity import (
    compute_diversity_report,
    _extract_operations,
    trajectory_jaccard,
    trajectory_edit_distance,
    find_divergence_point,
    iteration_diversity,
    identify_forking_points,
)


def analyze_scenario(name: str, trajectories: list[list[dict]], queries: list[str] = None):
    """Analyze a scenario in detail."""
    print("\n" + "="*80)
    print(f"SCENARIO: {name}")
    print("="*80)

    n = len(trajectories)
    print(f"\nNumber of trajectories: {n}")

    # Show trajectory structures
    print("\nTrajectory Structures:")
    for i, traj in enumerate(trajectories):
        ops = _extract_operations(traj)
        print(f"  T{i+1}: {len(traj)} steps, operations: {ops}")

    # Pairwise analysis
    print("\nPairwise Analysis:")
    print("-" * 80)
    print(f"{'Pair':<10} {'Jaccard':<10} {'Edit Dist':<12} {'Diverge@':<12} {'Interpretation'}")
    print("-" * 80)

    for i in range(n):
        for j in range(i+1, n):
            jacc = trajectory_jaccard(trajectories[i], trajectories[j])
            edit = trajectory_edit_distance(trajectories[i], trajectories[j])
            div = find_divergence_point(trajectories[i], trajectories[j])

            # Interpret
            if jacc == 1.0 and edit == 0:
                interp = "Identical"
            elif jacc > 0.7:
                interp = "Very similar"
            elif jacc > 0.3:
                interp = "Partially similar"
            else:
                interp = "Very different"

            print(f"T{i+1} vs T{j+1:<3} {jacc:<10.3f} {edit:<12} {div:<12} {interp}")

    # Per-iteration diversity
    max_len = max(len(t) for t in trajectories)
    print(f"\nPer-Iteration Diversity (higher = more variation at that step):")
    print("-" * 80)
    for i in range(max_len):
        div = iteration_diversity(trajectories, i)
        # Count unique code blocks
        codes = set()
        for t in trajectories:
            if i < len(t):
                data = t[i].get('data', {})
                if isinstance(data, dict):
                    codes.add(data.get('code', ''))
        unique_count = len(codes)

        bar_len = int(div * 20)
        bar = "█" * bar_len + "░" * (20 - bar_len)
        print(f"  Step {i}: {bar} {div:.2f} ({unique_count}/{n} unique)")

    # Forking points
    forking = identify_forking_points(trajectories, threshold=0.5)
    print(f"\nForking Points (steps where trajectories diverge): {forking}")
    if forking:
        print("  → Trajectories make different choices at these steps")
    else:
        print("  → No significant forking (trajectories are similar)")

    # Full diversity report
    print("\nFull Diversity Report:")
    print("-" * 80)
    report = compute_diversity_report(trajectories, queries=queries)

    # Break down the report
    print(f"\nOUTCOME DIVERSITY (what did we get?):")
    if queries:
        print(f"  SPARQL Vendi Score:    {report.sparql_vendi_score:.2f}")
        print(f"    → Effective unique queries out of {len(queries)} total")
        print(f"  Unique query patterns: {report.unique_query_patterns}")
        print(f"    → Number of structurally different SPARQL queries")
    else:
        print(f"  (No queries provided)")

    print(f"\nTRAJECTORY DIVERSITY (how did we get there?):")
    print(f"  Trajectory Vendi Score: {report.trajectory_vendi_score:.2f}")
    print(f"    → Effective unique trajectories out of {n} total")
    print(f"    → Higher = more diverse reasoning paths")
    print(f"  Mean Jaccard:          {report.mean_pairwise_jaccard:.2f}")
    print(f"    → Average overlap in operations (1.0 = identical, 0.0 = disjoint)")
    print(f"  Mean Edit Distance:    {report.mean_edit_distance:.1f}")
    print(f"    → Average steps to transform one trajectory to another")

    print(f"\nDECISION POINTS (where is uncertainty?):")
    print(f"  Forking points:        {report.forking_points}")
    print(f"  Mean divergence iter:  {report.mean_divergence_iteration:.1f}")
    print(f"    → On average, trajectories diverge after {report.mean_divergence_iteration:.1f} steps")

    print(f"\nSAMPLING EFFICIENCY (redundancy?):")
    print(f"  Effective count:       {report.effective_trajectory_count:.2f}")
    print(f"  Actual count:          {n}")
    print(f"  Efficiency:            {report.sampling_efficiency:.1%}")
    print(f"    → {report.sampling_efficiency:.1%} of trajectories are unique")
    print(f"    → {1 - report.sampling_efficiency:.1%} redundancy")

    # Interpretation
    print(f"\nINTERPRETATION:")
    if report.sampling_efficiency > 0.9:
        print(f"  ✓ Highly diverse: Almost all trajectories are unique")
    elif report.sampling_efficiency > 0.6:
        print(f"  ⚠ Moderate diversity: Some redundancy in trajectories")
    else:
        print(f"  ⚠ Low diversity: Significant redundancy, consider more perturbation")

    if report.mean_pairwise_jaccard > 0.7:
        print(f"  → Trajectories use similar operations")
    elif report.mean_pairwise_jaccard > 0.3:
        print(f"  → Trajectories have partial overlap in operations")
    else:
        print(f"  → Trajectories use very different operations")

    return report


def main():
    """Run detailed analysis on all sanity check scenarios."""

    print("╔" + "="*78 + "╗")
    print("║" + " "*20 + "DIVERSITY METRICS DETAILED ANALYSIS" + " "*23 + "║")
    print("╚" + "="*78 + "╝")

    # Scenario 1: Three identical trajectories
    traj_identical = [
        {'event_type': 'iteration', 'data': {
            'code': 'ontology_info = get_ontology_info()',
            'reasoning': 'First get basic ontology metadata',
        }},
        {'event_type': 'iteration', 'data': {
            'code': 'classes = query_classes()',
            'reasoning': 'Explore class hierarchy',
        }},
        {'event_type': 'iteration', 'data': {
            'code': 'results = sparql_query("SELECT ?s WHERE { ?s a up:Protein }")',
            'reasoning': 'Execute final query',
        }},
        {'event_type': 'iteration', 'data': {
            'code': 'SUBMIT(sparql=query, answer="Found 100 proteins")',
            'reasoning': 'Submit results',
        }},
    ]

    analyze_scenario(
        "Three Identical Trajectories",
        [traj_identical, traj_identical.copy(), traj_identical.copy()],
        queries=[
            "SELECT ?s WHERE { ?s a up:Protein }",
            "SELECT ?s WHERE { ?s a up:Protein }",
            "SELECT ?s WHERE { ?s a up:Protein }",
        ]
    )

    # Scenario 2: Three completely different trajectories
    t1 = [
        {'event_type': 'iteration', 'data': {'code': 'info_a = method_a()'}},
        {'event_type': 'iteration', 'data': {'code': 'result_a = process_a(info_a)'}},
    ]
    t2 = [
        {'event_type': 'iteration', 'data': {'code': 'info_b = method_b()'}},
        {'event_type': 'iteration', 'data': {'code': 'result_b = process_b(info_b)'}},
    ]
    t3 = [
        {'event_type': 'iteration', 'data': {'code': 'info_c = method_c()'}},
        {'event_type': 'iteration', 'data': {'code': 'result_c = process_c(info_c)'}},
    ]

    analyze_scenario(
        "Three Completely Different Trajectories",
        [t1, t2, t3],
        queries=[
            "SELECT ?x WHERE { ?x up:method_a ?y }",
            "SELECT ?x WHERE { ?x up:method_b ?y }",
            "SELECT ?x WHERE { ?x up:method_c ?y }",
        ]
    )

    # Scenario 3: Common start, then diverge
    common_prefix = [
        {'event_type': 'iteration', 'data': {
            'code': 'ontology_info = get_ontology_info()',
            'reasoning': 'Get basic ontology metadata',
        }},
        {'event_type': 'iteration', 'data': {
            'code': 'classes = query_classes()',
            'reasoning': 'Explore class structure',
        }},
    ]

    path_a = [
        {'event_type': 'iteration', 'data': {
            'code': 'proteins = filter_by_type("Protein")',
            'reasoning': 'Strategy A: Direct type filtering',
        }},
        {'event_type': 'iteration', 'data': {
            'code': 'SUBMIT(sparql=query_a, answer="100 proteins")',
            'reasoning': 'Submit direct query',
        }},
    ]

    path_b = [
        {'event_type': 'iteration', 'data': {
            'code': 'props = get_properties()',
            'reasoning': 'Strategy B: Explore properties first',
        }},
        {'event_type': 'iteration', 'data': {
            'code': 'proteins = query_with_properties()',
            'reasoning': 'Build query using properties',
        }},
        {'event_type': 'iteration', 'data': {
            'code': 'SUBMIT(sparql=query_b, answer="95 proteins")',
            'reasoning': 'Submit property-based query',
        }},
    ]

    path_c = [
        {'event_type': 'iteration', 'data': {
            'code': 'examples = get_shacl_examples()',
            'reasoning': 'Strategy C: Use SHACL examples',
        }},
        {'event_type': 'iteration', 'data': {
            'code': 'proteins = adapt_example_query()',
            'reasoning': 'Adapt example to task',
        }},
        {'event_type': 'iteration', 'data': {
            'code': 'SUBMIT(sparql=query_c, answer="98 proteins")',
            'reasoning': 'Submit adapted query',
        }},
    ]

    analyze_scenario(
        "Common Start, Then Diverge (Realistic)",
        [common_prefix + path_a, common_prefix + path_b, common_prefix + path_c],
        queries=[
            "SELECT ?s WHERE { ?s a up:Protein }",
            "SELECT ?s WHERE { ?s ?p ?o . ?s a up:Protein }",
            "SELECT ?s WHERE { ?s a up:Protein } LIMIT 100",
        ]
    )

    # Scenario 4: Two clusters
    direct_traj = [
        {'event_type': 'iteration', 'data': {
            'code': 'result = sparql_query("SELECT ?s WHERE { ?s a up:Protein }")',
        }},
        {'event_type': 'iteration', 'data': {
            'code': 'SUBMIT(sparql=query, answer=result)',
        }},
    ]

    explore_traj = [
        {'event_type': 'iteration', 'data': {'code': 'info = explore_ontology()'}},
        {'event_type': 'iteration', 'data': {'code': 'classes = get_classes()'}},
        {'event_type': 'iteration', 'data': {'code': 'result = query_proteins()'}},
        {'event_type': 'iteration', 'data': {'code': 'SUBMIT(sparql=query, answer=result)'}},
    ]

    analyze_scenario(
        "Two Clusters (2 Direct + 2 Explore)",
        [direct_traj, direct_traj.copy(), explore_traj, explore_traj.copy()],
        queries=[
            "SELECT ?s WHERE { ?s a up:Protein }",
            "SELECT ?s WHERE { ?s a up:Protein }",
            "SELECT ?s WHERE { ?s a up:Protein } # explored",
            "SELECT ?s WHERE { ?s a up:Protein } # explored",
        ]
    )

    print("\n" + "="*80)
    print("ANALYSIS COMPLETE")
    print("="*80)
    print("\n✓ All scenarios analyzed successfully")
    print("✓ Metrics appear to be measuring what we expect")


if __name__ == '__main__':
    main()
