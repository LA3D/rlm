#!/usr/bin/env python
"""E-MA-6: ALHF Routing (Multi-Component Feedback).

Tests whether expert feedback can be routed to both judge memory AND agent
memory components, and whether the compound effect exceeds individual effects.

Protocol:
    1. Start with E-MA-2 judge memory (5 principles + 6 episodes)
    2. Create fresh agent memory (L2 seed store)
    3. Run 10 tasks through full pipeline:
       a. Agent "produces" SPARQL (simulated from test data)
       b. Judge evaluates with aligned memory
       c. Identify errors
    4. For each error: route expert feedback via FeedbackRouter
       - Check: does feedback reach judge memory (principle)?
       - Check: does feedback reach agent memory (constraint/seed)?
    5. Re-evaluate with updated memories
    6. Report: compound improvement > individual improvements?

Usage:
    python experiments/reasoningbank/run_e_ma_6.py -v
"""

import sys
sys.path.insert(0, '/Users/cvardema/dev/git/LA3D/rlm')

import json
import os
from datetime import datetime

import dspy

from experiments.reasoningbank.prototype.core.mem import MemStore, Item
from experiments.reasoningbank.prototype.run.memalign import (
    evaluate_judge, judge_aligned, load_judge_mem, route_and_store,
    print_metrics,
)


# Expert feedback for ALHF routing test.
# Each entry simulates expert review of a judge/agent error.
# Feedback is designed to be routable to multiple components.
ROUTING_TASKS = [
    {
        'id': 'alhf_1_taxonomy_graph',
        'query': 'List all taxa in the UniProt taxonomy database',
        'agent_sparql': 'SELECT ?taxon WHERE { ?taxon a up:Taxon . }',
        'agent_answer': 'Found taxa using class membership.',
        'expert_verdict': False,
        'expert_reason': 'Missing FROM clause for taxonomy named graph.',
        'expert_feedback': (
            'The query is missing a FROM clause. UniProt stores taxonomy data in '
            'a named graph at <http://sparql.uniprot.org/taxonomy>. Without the '
            'FROM clause, the query hits the default graph and may return '
            'incomplete or incorrect results. The agent should always include '
            'FROM <http://sparql.uniprot.org/taxonomy> when querying taxonomy data.'
        ),
        'expected_routing': {
            'judge': True,   # Judge should learn to check FROM clauses
            'agent': True,   # Agent should learn to include FROM for taxonomy
        },
    },
    {
        'id': 'alhf_2_type_constraint',
        'query': "Find the protein with mnemonic 'BRCA1_HUMAN'",
        'agent_sparql': "SELECT ?entry WHERE { ?entry up:mnemonic 'BRCA1_HUMAN' . }",
        'agent_answer': 'Found entry by mnemonic.',
        'expert_verdict': False,
        'expert_reason': 'Missing type constraint on protein entity.',
        'expert_feedback': (
            'The query lacks a type constraint. When looking up specific proteins '
            'by mnemonic, always include ?protein a up:Protein to ensure you '
            'match protein entities and not other resource types. This is a '
            'query construction best practice for entity-specific lookups.'
        ),
        'expected_routing': {
            'judge': True,   # Judge should check for type constraints
            'agent': True,   # Agent should always add type constraints
        },
    },
    {
        'id': 'alhf_3_canonical_pattern',
        'query': 'List reviewed and unreviewed proteins',
        'agent_sparql': (
            'SELECT ?protein ?status WHERE { '
            '{ ?protein a up:Reviewed_Protein . BIND("reviewed" AS ?status) } '
            'UNION { ?protein a up:Protein . '
            'FILTER NOT EXISTS { ?protein a up:Reviewed_Protein } '
            'BIND("unreviewed" AS ?status) } }'
        ),
        'agent_answer': 'Listed proteins with class-based review status.',
        'expert_verdict': False,
        'expert_reason': 'Non-canonical pattern. Use up:reviewed property.',
        'expert_feedback': (
            'This uses a non-canonical pattern. UniProt provides a direct '
            'up:reviewed property that returns boolean review status. The '
            'canonical query is: SELECT ?protein ?reviewed WHERE { ?protein a '
            'up:Protein ; up:reviewed ?reviewed }. The UNION + FILTER NOT EXISTS '
            'approach is overly complex. Always prefer simple property-based '
            'patterns documented in the ontology.'
        ),
        'expected_routing': {
            'judge': True,   # Judge should prefer canonical patterns
            'agent': True,   # Agent should use simpler patterns
        },
    },
    {
        'id': 'alhf_4_correct_query',
        'query': 'Find entries integrated on 2010-11-30',
        'agent_sparql': (
            "SELECT ?entry WHERE { ?entry a up:Protein . "
            "?entry up:created '2010-11-30'^^xsd:date . }"
        ),
        'agent_answer': 'Found entries by integration date.',
        'expert_verdict': True,
        'expert_reason': 'Correct. up:created is the integration date property.',
        'expert_feedback': (
            'This is correct. The judge should know that up:created represents '
            'the integration date in UniProt, not the creation date. No changes '
            'needed to the agent query.'
        ),
        'expected_routing': {
            'judge': True,   # Judge needs terminology clarification
            'agent': False,  # Agent query is fine
        },
    },
    {
        'id': 'alhf_5_projection',
        'query': 'Find organisms and their host species',
        'agent_sparql': 'SELECT ?taxon WHERE { ?taxon up:host ?host . }',
        'agent_answer': 'Found taxa with host relationships.',
        'expert_verdict': False,
        'expert_reason': 'Incomplete projection - missing ?host variable.',
        'expert_feedback': (
            'The query only projects ?taxon but the task asks for BOTH organisms '
            'AND their hosts. The SELECT clause must include ?host to return the '
            'complete answer. The agent should always check that all requested '
            'information appears in the SELECT projection.'
        ),
        'expected_routing': {
            'judge': True,   # Judge should check projection completeness
            'agent': True,   # Agent should verify SELECT covers task
        },
    },
    {
        'id': 'alhf_6_disease_format',
        'query': 'List proteins and their associated diseases',
        'agent_sparql': (
            'SELECT ?protein ?diseaseName WHERE { '
            '?protein a up:Protein . '
            '?protein up:annotation ?ann . '
            '?ann a up:Disease_Annotation . '
            '?ann up:disease ?disease . '
            '?disease skos:prefLabel ?diseaseName . }'
        ),
        'agent_answer': 'Listed proteins with disease names.',
        'expert_verdict': False,
        'expert_reason': 'Returns disease names instead of URIs. Missing type constraint.',
        'expert_feedback': (
            'The query returns disease names (strings via skos:prefLabel) instead '
            'of disease URIs. It also lacks a type constraint (?disease a '
            'up:Disease). The expected pattern returns the disease entity URI, '
            'not its label. The agent should return entity URIs unless the task '
            'specifically asks for names/labels.'
        ),
        'expected_routing': {
            'judge': True,   # Judge should check return format
            'agent': True,   # Agent should prefer URIs over labels
        },
    },
    {
        'id': 'alhf_7_correct_hierarchy',
        'query': 'Select all bacterial taxa in the UniProt taxonomy',
        'agent_sparql': (
            'SELECT ?taxon WHERE { '
            '?taxon a up:Taxon . '
            '?taxon rdfs:subClassOf+ <http://purl.uniprot.org/taxonomy/2> . }'
        ),
        'agent_answer': 'Found bacteria using taxonomy hierarchy.',
        'expert_verdict': True,
        'expert_reason': 'Correct. Uses default graph for core taxonomy relationships.',
        'expert_feedback': (
            'This is correct. The rdfs:subClassOf relationships for taxonomy '
            'are in the default graph and do NOT require a FROM clause. The FROM '
            '<http://sparql.uniprot.org/taxonomy> is only needed when querying '
            'taxonomy-specific properties like scientific names. The judge '
            'should NOT apply the FROM clause principle to rdfs:subClassOf queries.'
        ),
        'expected_routing': {
            'judge': True,   # Judge needs to refine FROM clause scope
            'agent': False,  # Agent query is fine
        },
    },
    {
        'id': 'alhf_8_gene_name',
        'query': 'Find the recommended gene name for protein A4_HUMAN',
        'agent_sparql': (
            "SELECT ?geneName WHERE { "
            "?protein up:mnemonic 'A4_HUMAN' . "
            "?protein up:encodedBy ?gene . "
            "?gene skos:prefLabel ?geneName . }"
        ),
        'agent_answer': 'Found gene name via encodedBy.',
        'expert_verdict': False,
        'expert_reason': 'Missing type constraints on both protein and gene.',
        'expert_feedback': (
            'Missing type constraints. Should have ?protein a up:Protein and '
            '?gene a up:Gene. Also, the recommended gene name uses the '
            'up:recommendedName / up:fullName path through the gene entity, '
            'not skos:prefLabel. The agent should learn the canonical gene name '
            'retrieval pattern from UniProt examples.'
        ),
        'expected_routing': {
            'judge': True,   # Judge should check type constraints
            'agent': True,   # Agent should learn gene name pattern
        },
    },
    {
        'id': 'alhf_9_annotation_pattern',
        'query': 'Find proteins with catalytic activity annotations',
        'agent_sparql': (
            'SELECT ?protein ?activity WHERE { '
            '?protein up:annotation ?ann . '
            '?ann a up:Catalytic_Activity_Annotation . '
            '?ann rdfs:comment ?activity . }'
        ),
        'agent_answer': 'Found catalytic activity annotations.',
        'expert_verdict': False,
        'expert_reason': 'Missing protein type constraint. Activity should use catalyticActivity property.',
        'expert_feedback': (
            'Two issues: (1) Missing ?protein a up:Protein type constraint. '
            '(2) Catalytic activity details are accessed via '
            'up:catalyticActivity / up:catalyzedReaction, not rdfs:comment. '
            'The agent should consult the ontology for correct annotation '
            'property paths rather than guessing common predicates.'
        ),
        'expected_routing': {
            'judge': True,   # Judge should verify property paths
            'agent': True,   # Agent should check ontology for properties
        },
    },
    {
        'id': 'alhf_10_subcellular_location',
        'query': 'Find proteins located in the nucleus',
        'agent_sparql': (
            "SELECT ?protein WHERE { "
            "?protein a up:Protein . "
            "?protein up:annotation ?ann . "
            "?ann a up:Subcellular_Location_Annotation . "
            "?ann up:locatedIn ?location . "
            "?location up:cellularComponent <http://purl.uniprot.org/locations/191> . }"
        ),
        'agent_answer': 'Found proteins with nuclear localization.',
        'expert_verdict': True,
        'expert_reason': 'Correct pattern for subcellular location query.',
        'expert_feedback': (
            'This is a correct query. The agent properly includes the protein '
            'type constraint, follows the annotation pattern correctly, and uses '
            'the proper URI for nucleus. No changes needed.'
        ),
        'expected_routing': {
            'judge': False,  # No judge learning needed
            'agent': False,  # Agent query is fine
        },
    },
]


def run_e_ma_6(
    principles_path: str,
    episodes_path: str,
    output_dir: str,
    verbose: bool = False,
):
    """Run E-MA-6: ALHF routing experiment."""

    # Load initial judge memory (E-MA-2 state)
    judge_mem = load_judge_mem(
        principles_path=principles_path,
        episodes_path=episodes_path,
    )
    n_judge_initial = len(judge_mem.all())

    # Create fresh agent memory
    agent_mem = MemStore()
    n_agent_initial = 0

    print(f"Initial judge memory: {n_judge_initial} items")
    print(f"Initial agent memory: {n_agent_initial} items")
    print(f"Routing tasks: {len(ROUTING_TASKS)}")

    # Step 1: Run aligned judge on all tasks (before routing)
    print("\n" + "=" * 60)
    print("Step 1: Judge Evaluation BEFORE Routing")
    print("=" * 60)

    before_fn = lambda task, answer, sparql: judge_aligned(
        task, answer, sparql, judge_mem, verbose=verbose
    )
    before_metrics = evaluate_judge(before_fn, ROUTING_TASKS, verbose=verbose)
    print_metrics(before_metrics, "Before ALHF Routing")

    # Step 2: Route feedback for all errors
    print("\n" + "=" * 60)
    print("Step 2: Routing Expert Feedback via FeedbackRouter")
    print("=" * 60)

    routing_results = []
    n_routed_judge = 0
    n_routed_agent = 0
    n_routed_both = 0
    n_correct_routing = 0

    for detail, task_data in zip(before_metrics['details'], ROUTING_TASKS):
        task_id = task_data['id']
        feedback = task_data['expert_feedback']
        expected_routing = task_data['expected_routing']

        print(f"\n  Task: {task_id}")
        print(f"    Verdict: {detail['verdict']} "
              f"(predicted={detail['predicted']}, expected={detail['expected']})")

        # Route ALL feedback, not just errors (to test routing quality)
        result = route_and_store(
            feedback=feedback,
            task_context={
                'task': task_data['query'],
                'agent_sparql': task_data.get('agent_sparql', ''),
            },
            judge_mem=judge_mem,
            agent_mem=agent_mem,
            verbose=verbose,
        )

        # Check routing accuracy
        judge_routed = len(result['judge_items']) > 0
        agent_routed = len(result['agent_items']) > 0

        if judge_routed:
            n_routed_judge += 1
        if agent_routed:
            n_routed_agent += 1
        if judge_routed and agent_routed:
            n_routed_both += 1

        # Check if routing matches expectations
        judge_correct = judge_routed == expected_routing['judge']
        agent_correct = agent_routed == expected_routing['agent']
        both_correct = judge_correct and agent_correct
        if both_correct:
            n_correct_routing += 1

        routing_mark = 'OK' if both_correct else 'MISMATCH'
        print(f"    [{routing_mark}] Routing: judge={judge_routed} "
              f"(expect={expected_routing['judge']}), "
              f"agent={agent_routed} "
              f"(expect={expected_routing['agent']})")

        if result['routing'].get('judge_principle'):
            jp = result['routing']['judge_principle']
            print(f"    Judge principle: {jp[:80]}...")
        if result['routing'].get('agent_constraint'):
            ac = result['routing']['agent_constraint']
            print(f"    Agent constraint: {ac[:80]}...")
        if result['routing'].get('agent_seed'):
            aseed = result['routing']['agent_seed']
            print(f"    Agent seed: {aseed[:80]}...")

        routing_results.append({
            'task_id': task_id,
            'verdict': detail['verdict'],
            'judge_routed': judge_routed,
            'agent_routed': agent_routed,
            'expected_judge': expected_routing['judge'],
            'expected_agent': expected_routing['agent'],
            'routing_correct': both_correct,
            'routing': result['routing'],
            'n_judge_items': len(result['judge_items']),
            'n_agent_items': len(result['agent_items']),
        })

    # Memory growth report
    n_judge_final = len(judge_mem.all())
    n_agent_final = len(agent_mem.all())
    print(f"\n  Routing summary:")
    print(f"    Routed to judge: {n_routed_judge}/{len(ROUTING_TASKS)}")
    print(f"    Routed to agent: {n_routed_agent}/{len(ROUTING_TASKS)}")
    print(f"    Routed to both:  {n_routed_both}/{len(ROUTING_TASKS)}")
    print(f"    Correct routing: {n_correct_routing}/{len(ROUTING_TASKS)} "
          f"({n_correct_routing/len(ROUTING_TASKS):.0%})")
    print(f"    Judge memory: {n_judge_initial} -> {n_judge_final} "
          f"(+{n_judge_final - n_judge_initial})")
    print(f"    Agent memory: {n_agent_initial} -> {n_agent_final} "
          f"(+{n_agent_final - n_agent_initial})")

    # Step 3: Re-evaluate with updated judge memory
    print("\n" + "=" * 60)
    print("Step 3: Judge Evaluation AFTER Routing")
    print("=" * 60)

    after_fn = lambda task, answer, sparql: judge_aligned(
        task, answer, sparql, judge_mem, verbose=verbose
    )
    after_metrics = evaluate_judge(after_fn, ROUTING_TASKS, verbose=verbose)
    print_metrics(after_metrics, "After ALHF Routing")

    # Step 4: Comparison and compound effect
    print("\n" + "=" * 60)
    print("COMPARISON: Before vs After ALHF Routing")
    print("=" * 60)
    print(f"  {'Metric':<12} {'Before':>8} {'After':>8} {'Delta':>8}")
    print(f"  {'-'*40}")
    for metric in ['accuracy', 'precision', 'recall', 'f1']:
        before_val = before_metrics[metric]
        after_val = after_metrics[metric]
        delta = after_val - before_val
        sign = '+' if delta >= 0 else ''
        print(f"  {metric:<12} {before_val:>7.1%} {after_val:>7.1%} {sign}{delta:>6.1%}")

    # Show verdict flips
    flips = []
    for b, a in zip(before_metrics['details'], after_metrics['details']):
        if b['predicted'] != a['predicted']:
            direction = 'fixed' if a['predicted'] == a['expected'] else 'regressed'
            flips.append({
                'task_id': b['task_id'],
                'before': b['verdict'],
                'after': a['verdict'],
                'direction': direction,
            })

    if flips:
        print(f"\n  Verdict flips:")
        for f in flips:
            mark = 'OK' if f['direction'] == 'fixed' else 'WRONG'
            print(f"    [{mark}] {f['task_id']}: "
                  f"{f['before']} -> {f['after']} ({f['direction']})")
    else:
        print(f"\n  No verdict flips.")

    # Agent memory contents
    print("\n" + "=" * 60)
    print("AGENT MEMORY (routed items)")
    print("=" * 60)
    for item in agent_mem.all():
        print(f"  [{item.src}] {item.title}")
        print(f"    {item.content[:100]}...")

    # Success criteria
    print("\n" + "=" * 60)
    print("SUCCESS CRITERIA")
    print("=" * 60)
    routing_accuracy = n_correct_routing / len(ROUTING_TASKS)
    criteria = {
        'Routing accuracy >= 70%': routing_accuracy >= 0.70,
        'Feedback reaches both components': n_routed_both >= 3,
        'Judge accuracy improved or maintained': (
            after_metrics['accuracy'] >= before_metrics['accuracy']
        ),
        'Agent memory populated': n_agent_final > 0,
        'Memory bounded (judge < 25, agent < 15)': (
            n_judge_final < 25 and n_agent_final < 15
        ),
    }
    for name, passed in criteria.items():
        mark = 'PASS' if passed else 'FAIL'
        print(f"  [{mark}] {name}")

    # Save results
    os.makedirs(output_dir, exist_ok=True)
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')

    report = {
        'experiment': 'E-MA-6',
        'timestamp': timestamp,
        'before_metrics': before_metrics,
        'after_metrics': after_metrics,
        'routing_summary': {
            'total_tasks': len(ROUTING_TASKS),
            'routed_judge': n_routed_judge,
            'routed_agent': n_routed_agent,
            'routed_both': n_routed_both,
            'routing_accuracy': routing_accuracy,
        },
        'memory_growth': {
            'judge_before': n_judge_initial,
            'judge_after': n_judge_final,
            'agent_before': n_agent_initial,
            'agent_after': n_agent_final,
        },
        'verdict_flips': flips,
        'per_task_routing': routing_results,
        'criteria': {k: v for k, v in criteria.items()},
    }

    with open(os.path.join(output_dir, 'alhf_routing_report.json'), 'w') as f:
        json.dump(report, f, indent=2, default=str)

    # Save final memories
    judge_mem.save(os.path.join(output_dir, 'judge_memory_after_alhf.json'))
    agent_mem.save(os.path.join(output_dir, 'agent_memory_after_alhf.json'))

    print(f"\nResults saved to {output_dir}/")
    return report


if __name__ == '__main__':
    import argparse

    parser = argparse.ArgumentParser(
        description='E-MA-6: ALHF Routing (Multi-Component Feedback)')
    parser.add_argument('--principles',
                        default='experiments/reasoningbank/seed/judge_principles.json')
    parser.add_argument('--episodes',
                        default='experiments/reasoningbank/seed/judge_episodes.json')
    parser.add_argument('--output-dir',
                        default='experiments/reasoningbank/results/e_ma_6')
    parser.add_argument('--verbose', '-v', action='store_true')
    parser.add_argument('--model', default='anthropic/claude-sonnet-4-5-20250929')

    args = parser.parse_args()

    lm = dspy.LM(args.model, temperature=0.0)
    dspy.configure(lm=lm)

    run_e_ma_6(
        principles_path=args.principles,
        episodes_path=args.episodes,
        output_dir=args.output_dir,
        verbose=args.verbose,
    )
