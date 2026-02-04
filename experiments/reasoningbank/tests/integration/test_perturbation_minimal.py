#!/usr/bin/env python
"""Minimal test: Run 1 task with 2 strategies (none vs prefix) to verify setup."""

import sys
import json
import argparse
sys.path.insert(0, '/Users/cvardema/dev/git/LA3D/rlm')

from experiments.reasoningbank.run.phase1_uniprot import run_stochastic_uniprot
from experiments.reasoningbank.core.mem import MemStore
from experiments.reasoningbank.ctx.builder import Cfg, Layer

def main(use_seed=False):
    print("=" * 80)
    print("MINIMAL PERTURBATION TEST")
    print("=" * 80)
    print("\nConfiguration:")
    print("  Task: 4_uniprot_mnemonic_id (simple)")
    print("  Rollouts: k=2")
    print("  Strategies: none, prefix")
    print("  Temperature: 0.7")
    print(f"  Use explicit seeds: {use_seed}")
    print()

    # Load task
    with open('experiments/reasoningbank/uniprot_subset_tasks.json', 'r') as f:
        tasks = json.load(f)

    # Select simple task
    task = [t for t in tasks if t['id'] == '4_uniprot_mnemonic_id'][0]

    print(f"Task query: {task['query']}")
    print()

    # Initialize memory store
    mem = MemStore()

    strategies = ['none', 'prefix']

    for strategy in strategies:
        print(f"\n{'='*60}")
        print(f"Strategy: {strategy}")
        print(f"{'='*60}")

        # Configure layers: L0 (sense card) + L1 (meta-graph)
        cfg = Cfg(
            l0=Layer(True, 600),   # Sense card
            l1=Layer(True, 1000),  # Meta-graph
            l2=Layer(False, 2000), # No memory for baseline
        )

        try:
            result = run_stochastic_uniprot(
                task=task,
                ont_path='ontology/uniprot',
                cfg=cfg,
                mem=mem,
                k=2,
                temperature=0.7,
                endpoint='uniprot',
                verbose=True,
                log_dir=f'experiments/reasoningbank/results/minimal_test_{("seed" if use_seed else "noseed")}/{strategy}',
                use_local_interpreter=True,
                perturb=strategy,
                use_seed=use_seed,
                compute_diversity=True,
            )

            print(f"\n✓ Strategy '{strategy}' completed")
            print(f"  Pass@1: {result['metrics']['pass_1']:.1%}")
            print(f"  Best-of-N: {result['metrics']['best_of_n']:.1%}")

            if 'diversity' in result and result['diversity']:
                div = result['diversity']
                print(f"  Trajectory Vendi: {div['trajectory_vendi_score']:.2f}")
                print(f"  Sampling Efficiency: {div['sampling_efficiency']:.1%}")
                print(f"  Mean Jaccard: {div['mean_pairwise_jaccard']:.3f}")

        except Exception as e:
            print(f"\n✗ Strategy '{strategy}' failed: {e}")
            import traceback
            traceback.print_exc()

    print(f"\n{'='*80}")
    print("TEST COMPLETE")
    print(f"{'='*80}")


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Minimal perturbation test')
    parser.add_argument('--use-seed', action='store_true',
                        help='Use explicit different seeds per rollout')
    args = parser.parse_args()

    main(use_seed=args.use_seed)
