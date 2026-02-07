#!/usr/bin/env python
"""E-MA-5: MaTTS Integration (Cross-Trajectory Comparison).

Tests whether aligned judgment improves Best-of-N trajectory selection.
Uses synthetic trajectory sets to compare AlignedTrajectoryComparator
(with judge memory) against simple selection (lowest iteration count).

Protocol:
    1. For each of 5 tasks, create synthetic trajectory sets (k=3 rollouts)
       - Each set has 1 correct + 2 flawed SPARQL queries
    2. Run AlignedTrajectoryComparator with judge memory
    3. Compare: does aligned comparator pick the correct trajectory?
    4. Compare to baseline: pick lowest iteration count (MaTTS default)

Usage:
    python experiments/reasoningbank/run_e_ma_5.py -v
"""

import sys
sys.path.insert(0, '/Users/cvardema/dev/git/LA3D/rlm')

import json
import os
from datetime import datetime

import dspy

from experiments.reasoningbank.prototype.run.memalign import (
    load_judge_mem, compare_trajectories, select_for_expert_review,
    print_metrics,
)


# Synthetic trajectory sets: each has 3 rollouts for a task.
# ground_truth_index marks which rollout has the correct SPARQL.
TRAJECTORY_SETS = [
    {
        'task': 'Select all taxa from the UniProt taxonomy',
        'ground_truth_index': 2,
        'rollouts': [
            {
                'sparql': 'SELECT DISTINCT ?taxon WHERE { ?taxon a up:Taxon . }',
                'answer': 'Found taxa using class membership.',
                'iters': 4,
            },
            {
                'sparql': 'SELECT ?taxon WHERE { ?taxon a up:Taxon . } LIMIT 100',
                'answer': 'Found first 100 taxa.',
                'iters': 3,
            },
            {
                'sparql': 'SELECT ?taxon FROM <http://sparql.uniprot.org/taxonomy> WHERE { ?taxon a up:Taxon . }',
                'answer': 'Found all taxa from taxonomy named graph.',
                'iters': 7,
            },
        ],
    },
    {
        'task': "Select the UniProtKB entry with the mnemonic 'A4_HUMAN'",
        'ground_truth_index': 1,
        'rollouts': [
            {
                'sparql': "SELECT ?entry WHERE { ?entry up:mnemonic 'A4_HUMAN' . }",
                'answer': 'Found entry by mnemonic.',
                'iters': 3,
            },
            {
                'sparql': "SELECT ?protein WHERE { ?protein a up:Protein . ?protein up:mnemonic 'A4_HUMAN' }",
                'answer': 'Found protein with mnemonic A4_HUMAN with type constraint.',
                'iters': 6,
            },
            {
                'sparql': "SELECT ?entry WHERE { ?entry rdfs:label 'A4_HUMAN' . }",
                'answer': 'Found entry by label.',
                'iters': 5,
            },
        ],
    },
    {
        'task': 'List all UniProtKB proteins and if they are reviewed (Swiss-Prot) or unreviewed (TrEMBL)',
        'ground_truth_index': 0,
        'rollouts': [
            {
                'sparql': 'SELECT ?protein ?reviewed WHERE { ?protein a up:Protein . ?protein up:reviewed ?reviewed . }',
                'answer': 'Listed proteins with review status using up:reviewed property.',
                'iters': 5,
            },
            {
                'sparql': 'SELECT ?protein ?status WHERE { { ?protein a up:Reviewed_Protein . BIND("reviewed" AS ?status) } UNION { ?protein a up:Protein . FILTER NOT EXISTS { ?protein a up:Reviewed_Protein } BIND("unreviewed" AS ?status) } }',
                'answer': 'Listed proteins with class-based review classification.',
                'iters': 9,
            },
            {
                'sparql': 'SELECT ?protein WHERE { ?protein a up:Protein . }',
                'answer': 'Listed all proteins.',
                'iters': 3,
            },
        ],
    },
    {
        'task': 'Find taxon records that are known to have part of their life cycle in other organisms',
        'ground_truth_index': 1,
        'rollouts': [
            {
                'sparql': 'SELECT DISTINCT ?taxon WHERE { ?taxon a up:Taxon . ?taxon up:host ?host . }',
                'answer': 'Found taxa with host relationships.',
                'iters': 4,
            },
            {
                'sparql': 'SELECT ?virus ?host WHERE { ?virus up:host ?host . }',
                'answer': 'Found organisms and their hosts using up:host.',
                'iters': 6,
            },
            {
                'sparql': 'SELECT ?taxon WHERE { ?taxon up:host ?host . } LIMIT 50',
                'answer': 'Found first 50 taxa with hosts.',
                'iters': 3,
            },
        ],
    },
    {
        'task': 'List all UniProtKB proteins and the diseases are annotated to be related.',
        'ground_truth_index': 2,
        'rollouts': [
            {
                'sparql': 'SELECT ?protein ?diseaseName WHERE { ?protein a up:Protein . ?protein up:annotation ?ann . ?ann a up:Disease_Annotation . ?ann up:disease ?disease . ?disease skos:prefLabel ?diseaseName . }',
                'answer': 'Listed proteins with disease names via skos:prefLabel.',
                'iters': 5,
            },
            {
                'sparql': 'SELECT ?protein WHERE { ?protein up:annotation ?ann . ?ann a up:Disease_Annotation . }',
                'answer': 'Found proteins with disease annotations.',
                'iters': 3,
            },
            {
                'sparql': 'SELECT ?protein ?disease WHERE { ?protein a up:Protein ; up:annotation ?annotation . ?annotation a up:Disease_Annotation ; up:disease ?disease . ?disease a up:Disease . }',
                'answer': 'Listed proteins and disease entities with proper type constraints.',
                'iters': 8,
            },
        ],
    },
]


def baseline_select(rollouts: list[dict]) -> int:
    """Baseline MaTTS selection: pick lowest iteration count."""
    return min(range(len(rollouts)), key=lambda i: rollouts[i]['iters'])


def run_e_ma_5(
    principles_path: str,
    episodes_path: str,
    output_dir: str,
    verbose: bool = False,
):
    """Run E-MA-5: MaTTS trajectory comparison experiment."""

    # Load judge memory
    judge_mem = load_judge_mem(
        principles_path=principles_path,
        episodes_path=episodes_path,
    )
    print(f"Judge memory: {len(judge_mem.all())} items")
    print(f"Trajectory sets: {len(TRAJECTORY_SETS)}")

    aligned_correct = 0
    baseline_correct = 0
    results = []

    for i, tset in enumerate(TRAJECTORY_SETS):
        task = tset['task']
        gt_idx = tset['ground_truth_index']
        rollouts = tset['rollouts']

        print(f"\n{'='*60}")
        print(f"Task {i+1}: {task[:70]}...")
        print(f"  Ground truth trajectory: #{gt_idx}")
        print(f"{'='*60}")

        # Show rollouts
        for j, r in enumerate(rollouts):
            mark = '*' if j == gt_idx else ' '
            print(f"  {mark} Trajectory {j} ({r['iters']} iters): "
                  f"{r['sparql'][:80]}...")

        # Baseline selection (lowest iters)
        baseline_idx = baseline_select(rollouts)
        baseline_ok = baseline_idx == gt_idx
        baseline_correct += int(baseline_ok)
        mark = 'OK' if baseline_ok else 'WRONG'
        print(f"\n  [{mark}] Baseline picks: #{baseline_idx} "
              f"({rollouts[baseline_idx]['iters']} iters)")

        # Aligned selection (with judge memory)
        comparison = compare_trajectories(
            task=task,
            trajectories=rollouts,
            judge_mem=judge_mem,
            verbose=verbose,
        )
        aligned_idx = comparison['best_index']
        aligned_ok = aligned_idx == gt_idx
        aligned_correct += int(aligned_ok)
        mark = 'OK' if aligned_ok else 'WRONG'
        print(f"  [{mark}] Aligned picks: #{aligned_idx}")
        print(f"    Reason: {comparison['ranking_reason'][:120]}...")

        # Expert review selection
        judgments = [{'success': True, 'reason': 'mock'} for _ in rollouts]
        candidates = select_for_expert_review(rollouts, judgments)

        results.append({
            'task': task,
            'ground_truth_index': gt_idx,
            'baseline_pick': baseline_idx,
            'baseline_correct': baseline_ok,
            'aligned_pick': aligned_idx,
            'aligned_correct': aligned_ok,
            'aligned_reason': comparison['ranking_reason'],
            'review_candidates': len(candidates),
        })

    # Summary
    n = len(TRAJECTORY_SETS)
    print("\n" + "=" * 60)
    print("COMPARISON SUMMARY")
    print("=" * 60)
    print(f"  {'Method':<20} {'Correct':>8} {'Accuracy':>8}")
    print(f"  {'-'*40}")
    print(f"  {'Baseline (min-iter)':<20} {baseline_correct:>5}/{n} "
          f"{baseline_correct/n:>7.1%}")
    print(f"  {'Aligned (w/ memory)':<20} {aligned_correct:>5}/{n} "
          f"{aligned_correct/n:>7.1%}")

    improvement = aligned_correct - baseline_correct
    if improvement > 0:
        print(f"\n  Aligned is better by {improvement} task(s)")
    elif improvement == 0:
        print(f"\n  Both methods perform equally")
    else:
        print(f"\n  Baseline is better by {-improvement} task(s)")

    # Success criteria
    print("\n" + "=" * 60)
    print("SUCCESS CRITERIA")
    print("=" * 60)
    criteria = {
        'Aligned >= Baseline accuracy': aligned_correct >= baseline_correct,
        'Aligned accuracy >= 60%': aligned_correct / n >= 0.6,
    }
    for name, passed in criteria.items():
        mark = 'PASS' if passed else 'FAIL'
        print(f"  [{mark}] {name}")

    # Save results
    os.makedirs(output_dir, exist_ok=True)
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')

    with open(os.path.join(output_dir, 'matts_comparison.json'), 'w') as f:
        json.dump({
            'experiment': 'E-MA-5',
            'timestamp': timestamp,
            'baseline_accuracy': baseline_correct / n,
            'aligned_accuracy': aligned_correct / n,
            'improvement': improvement,
            'per_task': results,
            'criteria': {k: v for k, v in criteria.items()},
        }, f, indent=2, default=str)

    print(f"\nResults saved to {output_dir}/")


if __name__ == '__main__':
    import argparse

    parser = argparse.ArgumentParser(
        description='E-MA-5: MaTTS Trajectory Comparison')
    parser.add_argument('--principles',
                        default='experiments/reasoningbank/seed/judge_principles.json')
    parser.add_argument('--episodes',
                        default='experiments/reasoningbank/seed/judge_episodes.json')
    parser.add_argument('--output-dir',
                        default='experiments/reasoningbank/results/e_ma_5')
    parser.add_argument('--verbose', '-v', action='store_true')
    parser.add_argument('--model', default='anthropic/claude-sonnet-4-5-20250929')

    args = parser.parse_args()

    lm = dspy.LM(args.model, temperature=0.0)
    dspy.configure(lm=lm)

    run_e_ma_5(
        principles_path=args.principles,
        episodes_path=args.episodes,
        output_dir=args.output_dir,
        verbose=args.verbose,
    )
