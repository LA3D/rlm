#!/usr/bin/env python
"""Generate example visualizations for diversity metrics demo."""

import sys
sys.path.insert(0, '/Users/cvardema/dev/git/LA3D/rlm')

from experiments.reasoningbank.metrics.visualize import visualize_scenario


def main():
    """Generate visualizations for example scenarios."""

    print("\n" + "="*70)
    print("GENERATING DIVERSITY METRIC VISUALIZATIONS")
    print("="*70)

    output_dir = 'experiments/reasoningbank/results/diversity_viz'

    # Scenario 1: Three identical trajectories
    traj_identical = [
        {'event_type': 'iteration', 'data': {
            'code': 'ontology_info = get_ontology_info()',
            'reasoning': 'Get ontology metadata',
        }},
        {'event_type': 'iteration', 'data': {
            'code': 'classes = query_classes()',
            'reasoning': 'Explore classes',
        }},
        {'event_type': 'iteration', 'data': {
            'code': 'results = sparql_query("SELECT ?s WHERE { ?s a up:Protein }")',
            'reasoning': 'Execute query',
        }},
        {'event_type': 'iteration', 'data': {
            'code': 'SUBMIT(sparql=query, answer="100 proteins")',
            'reasoning': 'Submit',
        }},
    ]

    visualize_scenario(
        "Scenario 1 - Identical Trajectories",
        [traj_identical, traj_identical.copy(), traj_identical.copy()],
        queries=["SELECT ?s WHERE { ?s a up:Protein }"] * 3,
        output_dir=output_dir
    )

    # Scenario 2: Three completely different
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

    visualize_scenario(
        "Scenario 2 - Completely Different",
        [t1, t2, t3],
        queries=[
            "SELECT ?x WHERE { ?x up:method_a ?y }",
            "SELECT ?x WHERE { ?x up:method_b ?y }",
            "SELECT ?x WHERE { ?x up:method_c ?y }",
        ],
        output_dir=output_dir
    )

    # Scenario 3: Common start, then diverge (most realistic)
    common_prefix = [
        {'event_type': 'iteration', 'data': {
            'code': 'ontology_info = get_ontology_info()',
            'reasoning': 'Get metadata',
        }},
        {'event_type': 'iteration', 'data': {
            'code': 'classes = query_classes()',
            'reasoning': 'Explore structure',
        }},
    ]

    path_a = [
        {'event_type': 'iteration', 'data': {
            'code': 'proteins = filter_by_type("Protein")',
            'reasoning': 'Direct filtering',
        }},
        {'event_type': 'iteration', 'data': {
            'code': 'SUBMIT(sparql=query_a, answer="100 proteins")',
            'reasoning': 'Submit',
        }},
    ]

    path_b = [
        {'event_type': 'iteration', 'data': {
            'code': 'props = get_properties()',
            'reasoning': 'Explore properties',
        }},
        {'event_type': 'iteration', 'data': {
            'code': 'proteins = query_with_properties()',
            'reasoning': 'Build query',
        }},
        {'event_type': 'iteration', 'data': {
            'code': 'SUBMIT(sparql=query_b, answer="95 proteins")',
            'reasoning': 'Submit',
        }},
    ]

    path_c = [
        {'event_type': 'iteration', 'data': {
            'code': 'examples = get_shacl_examples()',
            'reasoning': 'Use examples',
        }},
        {'event_type': 'iteration', 'data': {
            'code': 'proteins = adapt_example_query()',
            'reasoning': 'Adapt example',
        }},
        {'event_type': 'iteration', 'data': {
            'code': 'SUBMIT(sparql=query_c, answer="98 proteins")',
            'reasoning': 'Submit',
        }},
    ]

    visualize_scenario(
        "Scenario 3 - Common Then Diverge",
        [common_prefix + path_a, common_prefix + path_b, common_prefix + path_c],
        queries=[
            "SELECT ?s WHERE { ?s a up:Protein }",
            "SELECT ?s WHERE { ?s ?p ?o . ?s a up:Protein }",
            "SELECT ?s WHERE { ?s a up:Protein } LIMIT 100",
        ],
        output_dir=output_dir
    )

    print("\n" + "="*70)
    print("COMPLETE")
    print("="*70)
    print(f"\n✓ All visualizations saved to: {output_dir}/")
    print("\nGenerated files:")
    print("  - *_summary.png       - Comprehensive dashboard (recommended)")
    print("  - *_similarity.png    - Pairwise similarity heatmap")
    print("  - *_iterations.png    - Per-iteration diversity")
    print("  - *_flows.png         - Trajectory flow diagram")
    print("  - *_convergence.png   - Diversity vs. sample size")


if __name__ == '__main__':
    main()
