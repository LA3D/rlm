#!/usr/bin/env python
"""Test diversity metrics with realistic trajectory log structure."""

import sys
sys.path.insert(0, '/Users/cvardema/dev/git/LA3D/rlm')

from experiments.reasoningbank.prototype.metrics.diversity import (
    compute_diversity_report,
    trajectory_jaccard,
    trajectory_edit_distance,
    _extract_operations,
)


def test_realistic_trajectory_logs():
    """Test with actual run_uniprot trajectory log structure."""
    print("="*70)
    print("REALISTIC TRAJECTORY LOG TEST")
    print("="*70)

    # Trajectory 1: Direct query approach
    t1 = [
        {
            'event_type': 'iteration',
            'data': {
                'code': 'info = get_ontology_info()',
                'reasoning': 'Get ontology metadata',
                'output': 'Found 50 classes'
            }
        },
        {
            'event_type': 'iteration',
            'data': {
                'code': 'result = sparql_query("SELECT ?s WHERE { ?s a up:Protein }")',
                'reasoning': 'Execute query',
                'output': 'Found 100 proteins'
            }
        },
        {
            'event_type': 'iteration',
            'data': {
                'code': 'SUBMIT(sparql=query, answer=result)',
                'reasoning': 'Submit answer',
                'output': 'Success'
            }
        },
    ]

    # Trajectory 2: Same approach (should be high similarity)
    t2 = [
        {
            'event_type': 'iteration',
            'data': {
                'code': 'info = get_ontology_info()',
                'reasoning': 'Get ontology metadata first',
                'output': 'Found 50 classes'
            }
        },
        {
            'event_type': 'iteration',
            'data': {
                'code': 'result = sparql_query("SELECT ?s WHERE { ?s a up:Protein }")',
                'reasoning': 'Run SPARQL query',
                'output': 'Found 100 proteins'
            }
        },
        {
            'event_type': 'iteration',
            'data': {
                'code': 'SUBMIT(sparql=query, answer=result)',
                'reasoning': 'Submit final answer',
                'output': 'Success'
            }
        },
    ]

    # Trajectory 3: Different approach (should be low similarity)
    t3 = [
        {
            'event_type': 'iteration',
            'data': {
                'code': 'classes = query_classes()',
                'reasoning': 'Explore class hierarchy',
                'output': 'Found classes'
            }
        },
        {
            'event_type': 'iteration',
            'data': {
                'code': 'props = get_properties()',
                'reasoning': 'Get property list',
                'output': 'Found properties'
            }
        },
        {
            'event_type': 'iteration',
            'data': {
                'code': 'examples = get_shacl_examples()',
                'reasoning': 'Find SHACL examples',
                'output': 'Found examples'
            }
        },
        {
            'event_type': 'iteration',
            'data': {
                'code': 'result = execute_adapted_query()',
                'reasoning': 'Execute adapted query',
                'output': 'Found proteins'
            }
        },
        {
            'event_type': 'iteration',
            'data': {
                'code': 'SUBMIT(sparql=adapted_query, answer=result)',
                'reasoning': 'Submit',
                'output': 'Success'
            }
        },
    ]

    print("\nExtracted Operations:")
    print(f"  T1: {_extract_operations(t1)}")
    print(f"  T2: {_extract_operations(t2)}")
    print(f"  T3: {_extract_operations(t3)}")

    print("\nPairwise Metrics:")
    print(f"  Jaccard(T1, T2): {trajectory_jaccard(t1, t2):.3f} (expect: high, ~1.0)")
    print(f"  Jaccard(T1, T3): {trajectory_jaccard(t1, t3):.3f} (expect: low, ~0.2)")
    print(f"  Jaccard(T2, T3): {trajectory_jaccard(t2, t3):.3f} (expect: low, ~0.2)")

    print(f"\n  Edit Distance(T1, T2): {trajectory_edit_distance(t1, t2)} (expect: low, ~0)")
    print(f"  Edit Distance(T1, T3): {trajectory_edit_distance(t1, t3)} (expect: high, ~3+)")
    print(f"  Edit Distance(T2, T3): {trajectory_edit_distance(t2, t3)} (expect: high, ~3+)")

    # Full diversity report
    trajectories = [t1, t2, t3]
    queries = [
        "SELECT ?s WHERE { ?s a up:Protein }",
        "SELECT ?s WHERE { ?s a up:Protein }",
        "SELECT DISTINCT ?s WHERE { ?s a up:Protein . ?s ?p ?o } LIMIT 100",
    ]

    report = compute_diversity_report(trajectories, queries=queries)
    print(report.summary())

    # Validation
    print("\n" + "="*70)
    print("VALIDATION")
    print("="*70)

    checks = [
        ("T1 vs T2 high similarity", trajectory_jaccard(t1, t2) > 0.8, "✓"),
        ("T1 vs T3 low similarity", trajectory_jaccard(t1, t3) < 0.5, "✓"),
        ("Mean Jaccard between 0-1", 0 <= report.mean_pairwise_jaccard <= 1, "✓"),
        ("Vendi Score >= 1", report.trajectory_vendi_score >= 1.0, "✓"),
        ("Vendi Score <= n", report.trajectory_vendi_score <= len(trajectories), "✓"),
        ("Efficiency between 0-1", 0 <= report.sampling_efficiency <= 1, "✓"),
    ]

    all_pass = True
    for check_name, result, symbol in checks:
        status = symbol if result else "✗"
        print(f"{status} {check_name}: {result}")
        if not result:
            all_pass = False

    if all_pass:
        print("\n✓ All validation checks passed!")
        print("✓ Metrics are working correctly with realistic trajectory logs!")
    else:
        print("\n⚠ Some validation checks failed")

    return all_pass


if __name__ == '__main__':
    success = test_realistic_trajectory_logs()
    sys.exit(0 if success else 1)
