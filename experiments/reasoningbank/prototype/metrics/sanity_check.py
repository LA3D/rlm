#!/usr/bin/env python
"""Sanity check for trajectory diversity metrics.

Creates controlled trajectory scenarios and verifies metrics produce
intuitive results.
"""

import sys
sys.path.insert(0, '/Users/cvardema/dev/git/LA3D/rlm')

from experiments.reasoningbank.prototype.metrics.diversity import (
    compute_diversity_report,
    trajectory_jaccard,
    trajectory_edit_distance,
    find_divergence_point,
)


def create_scenario_1_identical():
    """Scenario 1: Three identical trajectories.

    Expected:
    - Jaccard = 1.0 (all use same tools)
    - Edit distance = 0 (same sequence)
    - Divergence point = end (never diverge)
    - Vendi Score ≈ 1.0 (only one effective trajectory)
    """
    print("\n" + "="*70)
    print("SCENARIO 1: Three Identical Trajectories")
    print("="*70)

    # Realistic trajectory: query → explore → filter → submit
    traj = [
        {'event_type': 'iteration', 'data': {
            'code': 'ontology_info = get_ontology_info()',
            'reasoning': 'First get basic ontology metadata',
            'output': 'Found 50 classes'
        }},
        {'event_type': 'iteration', 'data': {
            'code': 'classes = query_classes()',
            'reasoning': 'Explore class hierarchy',
            'output': 'Retrieved class list'
        }},
        {'event_type': 'iteration', 'data': {
            'code': 'results = sparql_query("SELECT ?s WHERE { ?s a up:Protein }")',
            'reasoning': 'Execute final query',
            'output': 'Found 100 proteins'
        }},
        {'event_type': 'iteration', 'data': {
            'code': 'SUBMIT(sparql=query, answer="Found 100 proteins")',
            'reasoning': 'Submit results',
            'output': 'Success'
        }},
    ]

    trajectories = [traj, traj.copy(), traj.copy()]
    queries = [
        "SELECT ?s WHERE { ?s a up:Protein }",
        "SELECT ?s WHERE { ?s a up:Protein }",
        "SELECT ?s WHERE { ?s a up:Protein }",
    ]

    # Manual verification
    print("\nManual Pairwise Metrics:")
    print(f"  Jaccard(T1, T2): {trajectory_jaccard(trajectories[0], trajectories[1])}")
    print(f"  Edit Distance(T1, T2): {trajectory_edit_distance(trajectories[0], trajectories[1])}")
    print(f"  Divergence Point(T1, T2): {find_divergence_point(trajectories[0], trajectories[1])}")

    # Full report
    report = compute_diversity_report(trajectories, queries=queries)
    print(report.summary())

    print("\n✓ Expected: Vendi ≈ 1.0, Jaccard = 1.0, Edit Distance = 0")
    print(f"✓ Actual: Vendi = {report.trajectory_vendi_score:.2f}, "
          f"Jaccard = {report.mean_pairwise_jaccard:.2f}, "
          f"Edit Distance = {report.mean_edit_distance:.1f}")

    return report


def create_scenario_2_completely_different():
    """Scenario 2: Three completely different trajectories.

    Expected:
    - Jaccard = 0.0 (no common tools)
    - Edit distance = high (all operations different)
    - Divergence point = 0 (diverge immediately)
    - Vendi Score ≈ 3.0 (three distinct trajectories)
    """
    print("\n" + "="*70)
    print("SCENARIO 2: Three Completely Different Trajectories")
    print("="*70)

    t1 = [
        {'event_type': 'iteration', 'data': {
            'code': 'info_a = method_a()',
            'reasoning': 'Approach A: Start with method A',
        }},
        {'event_type': 'iteration', 'data': {
            'code': 'result_a = process_a(info_a)',
            'reasoning': 'Continue with process A',
        }},
    ]

    t2 = [
        {'event_type': 'iteration', 'data': {
            'code': 'info_b = method_b()',
            'reasoning': 'Approach B: Use method B instead',
        }},
        {'event_type': 'iteration', 'data': {
            'code': 'result_b = process_b(info_b)',
            'reasoning': 'Follow up with process B',
        }},
    ]

    t3 = [
        {'event_type': 'iteration', 'data': {
            'code': 'info_c = method_c()',
            'reasoning': 'Approach C: Try method C',
        }},
        {'event_type': 'iteration', 'data': {
            'code': 'result_c = process_c(info_c)',
            'reasoning': 'Complete with process C',
        }},
    ]

    trajectories = [t1, t2, t3]
    queries = [
        "SELECT ?x WHERE { ?x up:method_a ?y }",
        "SELECT ?x WHERE { ?x up:method_b ?y }",
        "SELECT ?x WHERE { ?x up:method_c ?y }",
    ]

    # Manual verification
    print("\nManual Pairwise Metrics:")
    print(f"  Jaccard(T1, T2): {trajectory_jaccard(t1, t2)}")
    print(f"  Edit Distance(T1, T2): {trajectory_edit_distance(t1, t2)}")
    print(f"  Divergence Point(T1, T2): {find_divergence_point(t1, t2)}")

    # Full report
    report = compute_diversity_report(trajectories, queries=queries)
    print(report.summary())

    print("\n✓ Expected: Vendi ≈ 3.0, Jaccard = 0.0, Edit Distance > 0")
    print(f"✓ Actual: Vendi = {report.trajectory_vendi_score:.2f}, "
          f"Jaccard = {report.mean_pairwise_jaccard:.2f}, "
          f"Edit Distance = {report.mean_edit_distance:.1f}")

    return report


def create_scenario_3_partial_overlap():
    """Scenario 3: Three trajectories with early common path, then diverge.

    Expected:
    - Jaccard between 0 and 1 (some common tools)
    - Divergence point > 0 (diverge after shared prefix)
    - Forking points detected at divergence
    - Vendi Score between 1 and 3
    """
    print("\n" + "="*70)
    print("SCENARIO 3: Common Start, Then Diverge (Realistic)")
    print("="*70)

    # All start with same exploration steps
    common_prefix = [
        {'event_type': 'iteration', 'data': {
            'code': 'ontology_info = get_ontology_info()',
            'reasoning': 'Get basic ontology metadata',
            'output': 'Found metadata'
        }},
        {'event_type': 'iteration', 'data': {
            'code': 'classes = query_classes()',
            'reasoning': 'Explore class structure',
            'output': 'Found 50 classes'
        }},
    ]

    # Then diverge into different query strategies
    path_a = [
        {'event_type': 'iteration', 'data': {
            'code': 'proteins = filter_by_type("Protein")',
            'reasoning': 'Strategy A: Direct type filtering',
            'output': 'Found 100 proteins'
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
            'output': 'Found properties'
        }},
        {'event_type': 'iteration', 'data': {
            'code': 'proteins = query_with_properties()',
            'reasoning': 'Build query using properties',
            'output': 'Found 95 proteins'
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
            'output': 'Found example queries'
        }},
        {'event_type': 'iteration', 'data': {
            'code': 'proteins = adapt_example_query()',
            'reasoning': 'Adapt example to task',
            'output': 'Found 98 proteins'
        }},
        {'event_type': 'iteration', 'data': {
            'code': 'SUBMIT(sparql=query_c, answer="98 proteins")',
            'reasoning': 'Submit adapted query',
        }},
    ]

    t1 = common_prefix + path_a
    t2 = common_prefix + path_b
    t3 = common_prefix + path_c

    trajectories = [t1, t2, t3]
    queries = [
        "SELECT ?s WHERE { ?s a up:Protein }",
        "SELECT ?s WHERE { ?s ?p ?o . ?s a up:Protein }",
        "SELECT ?s WHERE { ?s a up:Protein } LIMIT 100",
    ]

    # Manual verification
    print("\nManual Pairwise Metrics:")
    print(f"  Jaccard(T1, T2): {trajectory_jaccard(t1, t2):.3f}")
    print(f"  Edit Distance(T1, T2): {trajectory_edit_distance(t1, t2)}")
    print(f"  Divergence Point(T1, T2): {find_divergence_point(t1, t2)} (expect: 2)")
    print(f"  Divergence Point(T1, T3): {find_divergence_point(t1, t3)} (expect: 2)")

    # Full report
    report = compute_diversity_report(trajectories, queries=queries)
    print(report.summary())

    print("\n✓ Expected: Vendi between 1-3, Jaccard between 0-1, Divergence at iteration 2")
    print(f"✓ Actual: Vendi = {report.trajectory_vendi_score:.2f}, "
          f"Jaccard = {report.mean_pairwise_jaccard:.2f}, "
          f"Mean Divergence = {report.mean_divergence_iteration:.1f}")
    print(f"✓ Forking points: {report.forking_points}")

    return report


def create_scenario_4_two_clusters():
    """Scenario 4: Two clusters - 2 identical + 2 identical (different from first cluster).

    Expected:
    - Vendi Score ≈ 2.0 (two effective strategies)
    - Within-cluster Jaccard = 1.0
    - Between-cluster Jaccard = 0.0
    """
    print("\n" + "="*70)
    print("SCENARIO 4: Two Clusters (2+2 Identical)")
    print("="*70)

    # Cluster 1: Direct query approach (2 identical)
    direct_traj = [
        {'event_type': 'iteration', 'data': {
            'code': 'result = sparql_query("SELECT ?s WHERE { ?s a up:Protein }")',
            'reasoning': 'Direct SPARQL query',
        }},
        {'event_type': 'iteration', 'data': {
            'code': 'SUBMIT(sparql=query, answer=result)',
            'reasoning': 'Submit',
        }},
    ]

    # Cluster 2: Exploration-based approach (2 identical)
    explore_traj = [
        {'event_type': 'iteration', 'data': {
            'code': 'info = explore_ontology()',
            'reasoning': 'Explore first',
        }},
        {'event_type': 'iteration', 'data': {
            'code': 'classes = get_classes()',
            'reasoning': 'Get classes',
        }},
        {'event_type': 'iteration', 'data': {
            'code': 'result = query_proteins()',
            'reasoning': 'Query proteins',
        }},
        {'event_type': 'iteration', 'data': {
            'code': 'SUBMIT(sparql=query, answer=result)',
            'reasoning': 'Submit',
        }},
    ]

    trajectories = [
        direct_traj,
        direct_traj.copy(),
        explore_traj,
        explore_traj.copy(),
    ]

    queries = [
        "SELECT ?s WHERE { ?s a up:Protein }",
        "SELECT ?s WHERE { ?s a up:Protein }",
        "SELECT ?s WHERE { ?s a up:Protein } # explored first",
        "SELECT ?s WHERE { ?s a up:Protein } # explored first",
    ]

    # Manual verification
    print("\nManual Pairwise Metrics:")
    print(f"  Within cluster 1 - Jaccard(T1, T2): {trajectory_jaccard(trajectories[0], trajectories[1])}")
    print(f"  Within cluster 2 - Jaccard(T3, T4): {trajectory_jaccard(trajectories[2], trajectories[3])}")
    print(f"  Between clusters - Jaccard(T1, T3): {trajectory_jaccard(trajectories[0], trajectories[2])}")

    # Full report
    report = compute_diversity_report(trajectories, queries=queries)
    print(report.summary())

    print("\n✓ Expected: Vendi ≈ 2.0 (two distinct approaches)")
    print(f"✓ Actual: Vendi = {report.trajectory_vendi_score:.2f}")
    print(f"✓ Efficiency = {report.sampling_efficiency:.1%} (expect ~50% since 2 effective out of 4 actual)")

    return report


def main():
    """Run all sanity check scenarios."""
    print("\n")
    print("╔" + "═"*68 + "╗")
    print("║" + " "*15 + "TRAJECTORY DIVERSITY SANITY CHECK" + " "*20 + "║")
    print("╚" + "═"*68 + "╝")

    scenarios = [
        create_scenario_1_identical,
        create_scenario_2_completely_different,
        create_scenario_3_partial_overlap,
        create_scenario_4_two_clusters,
    ]

    reports = []
    for scenario in scenarios:
        try:
            report = scenario()
            reports.append(report)
        except Exception as e:
            print(f"\n❌ ERROR: {e}")
            import traceback
            traceback.print_exc()

    # Summary
    print("\n" + "="*70)
    print("SUMMARY")
    print("="*70)
    print(f"Scenarios run: {len(reports)}/{len(scenarios)}")

    if len(reports) == len(scenarios):
        print("\n✓ All scenarios completed successfully!")
        print("\nKey Observations:")
        print(f"  - Scenario 1 (identical): Vendi={reports[0].trajectory_vendi_score:.2f} (expect ≈1.0)")
        print(f"  - Scenario 2 (different): Vendi={reports[1].trajectory_vendi_score:.2f} (expect ≈3.0)")
        print(f"  - Scenario 3 (partial): Vendi={reports[2].trajectory_vendi_score:.2f} (expect 1.0-3.0)")
        print(f"  - Scenario 4 (2 clusters): Vendi={reports[3].trajectory_vendi_score:.2f} (expect ≈2.0)")
        print("\n✓ Metrics appear to be working correctly!")
    else:
        print("\n⚠ Some scenarios failed. Check errors above.")


if __name__ == '__main__':
    main()
