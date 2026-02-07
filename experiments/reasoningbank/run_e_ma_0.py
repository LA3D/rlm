#!/usr/bin/env python
"""E-MA-0 through E-MA-2: Baseline + Aligned Judge Evaluation.

Usage:
    # Step 0: Baseline
    python experiments/reasoningbank/run_e_ma_0.py

    # Step 1: With principles only
    python experiments/reasoningbank/run_e_ma_0.py \
        --judge-mem experiments/reasoningbank/seed/judge_principles.json

    # Step 2: With dual memory (principles + episodes)
    python experiments/reasoningbank/run_e_ma_0.py \
        --judge-mem experiments/reasoningbank/seed/judge_principles.json \
        --episodes experiments/reasoningbank/seed/judge_episodes.json

    # Compare all variants
    python experiments/reasoningbank/run_e_ma_0.py \
        --judge-mem experiments/reasoningbank/seed/judge_principles.json \
        --episodes experiments/reasoningbank/seed/judge_episodes.json \
        --compare -v
"""

import sys
sys.path.insert(0, '/Users/cvardema/dev/git/LA3D/rlm')

import json
import os
import argparse
from datetime import datetime

import dspy

from experiments.reasoningbank.prototype.run.memalign import (
    evaluate_judge, judge_baseline, judge_aligned, load_judge_mem, print_metrics,
)


def main():
    parser = argparse.ArgumentParser(
        description='E-MA-0/1/2: Evaluate judge accuracy with expert verdicts')
    parser.add_argument('--eval-tasks',
                        default='experiments/reasoningbank/tasks/judge_eval_tasks.json',
                        help='Path to evaluation tasks JSON')
    parser.add_argument('--judge-mem', metavar='FILE',
                        help='Path to judge principles JSON (Step 1+)')
    parser.add_argument('--episodes', metavar='FILE',
                        help='Path to judge episodes JSON (Step 2)')
    parser.add_argument('--output-dir', default='experiments/reasoningbank/results',
                        help='Output directory for metrics')
    parser.add_argument('--verbose', '-v', action='store_true')
    parser.add_argument('--compare', action='store_true',
                        help='Run baseline + aligned and compare')
    parser.add_argument('--model', default='anthropic/claude-sonnet-4-5-20250929',
                        help='LM model to use for judge')

    args = parser.parse_args()

    # Load evaluation tasks
    with open(args.eval_tasks) as f:
        eval_tasks = json.load(f)
    print(f"Loaded {len(eval_tasks)} evaluation tasks from {args.eval_tasks}")

    # Configure DSPy
    lm = dspy.LM(args.model, temperature=0.0)
    dspy.configure(lm=lm)
    print(f"Model: {args.model}")

    all_results = {}
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')

    # --- Baseline (E-MA-0) ---
    if args.compare or not args.judge_mem:
        print("\n" + "="*60)
        print("E-MA-0: Baseline Judge (no alignment)")
        print("="*60)
        baseline_metrics = evaluate_judge(
            judge_fn=judge_baseline,
            eval_tasks=eval_tasks,
            verbose=args.verbose,
        )
        print_metrics(baseline_metrics, "Baseline")
        all_results['baseline'] = baseline_metrics

        # Save baseline
        out_dir = os.path.join(args.output_dir, 'e_ma_0')
        os.makedirs(out_dir, exist_ok=True)
        with open(os.path.join(out_dir, 'baseline_metrics.json'), 'w') as f:
            json.dump({
                'experiment': 'E-MA-0',
                'timestamp': timestamp,
                'model': args.model,
                'metrics': baseline_metrics,
            }, f, indent=2)
        print(f"  Saved to {out_dir}/baseline_metrics.json")

    # --- Principles Only (E-MA-1) ---
    if args.judge_mem:
        judge_mem_principles = load_judge_mem(principles_path=args.judge_mem)
        n_principles = len([i for i in judge_mem_principles.all() if i.src == 'principle'])

        if args.compare or not args.episodes:
            print("\n" + "="*60)
            print(f"E-MA-1: Aligned Judge (principles only, {n_principles} principles)")
            print("="*60)
            aligned_fn = lambda task, answer, sparql: judge_aligned(
                task, answer, sparql, judge_mem_principles, verbose=args.verbose
            )
            principles_metrics = evaluate_judge(
                judge_fn=aligned_fn,
                eval_tasks=eval_tasks,
                verbose=args.verbose,
            )
            print_metrics(principles_metrics, "Principles Only")
            all_results['principles_only'] = principles_metrics

            # Save
            out_dir = os.path.join(args.output_dir, 'e_ma_1')
            os.makedirs(out_dir, exist_ok=True)
            with open(os.path.join(out_dir, 'principles_only_metrics.json'), 'w') as f:
                json.dump({
                    'experiment': 'E-MA-1',
                    'timestamp': timestamp,
                    'model': args.model,
                    'n_principles': n_principles,
                    'metrics': principles_metrics,
                }, f, indent=2)
            print(f"  Saved to {out_dir}/principles_only_metrics.json")

    # --- Dual Memory (E-MA-2) ---
    if args.judge_mem and args.episodes:
        judge_mem_full = load_judge_mem(
            principles_path=args.judge_mem,
            episodes_path=args.episodes,
        )
        n_episodes = len([i for i in judge_mem_full.all() if i.src == 'episode'])

        print("\n" + "="*60)
        print(f"E-MA-2: Aligned Judge (dual memory, {n_principles} principles + {n_episodes} episodes)")
        print("="*60)
        dual_fn = lambda task, answer, sparql: judge_aligned(
            task, answer, sparql, judge_mem_full, verbose=args.verbose
        )
        dual_metrics = evaluate_judge(
            judge_fn=dual_fn,
            eval_tasks=eval_tasks,
            verbose=args.verbose,
        )
        print_metrics(dual_metrics, "Dual Memory")
        all_results['dual_memory'] = dual_metrics

        # Save
        out_dir = os.path.join(args.output_dir, 'e_ma_2')
        os.makedirs(out_dir, exist_ok=True)
        with open(os.path.join(out_dir, 'dual_memory_metrics.json'), 'w') as f:
            json.dump({
                'experiment': 'E-MA-2',
                'timestamp': timestamp,
                'model': args.model,
                'n_principles': n_principles,
                'n_episodes': n_episodes,
                'metrics': dual_metrics,
            }, f, indent=2)
        print(f"  Saved to {out_dir}/dual_memory_metrics.json")

    # --- Comparison Summary ---
    if len(all_results) > 1:
        print("\n" + "="*60)
        print("COMPARISON SUMMARY")
        print("="*60)
        print(f"{'Variant':<20} {'Accuracy':>8} {'Precision':>9} {'Recall':>6} {'F1':>6}")
        print("-"*55)
        for name, m in all_results.items():
            print(f"{name:<20} {m['accuracy']:>8.1%} {m['precision']:>9.1%} "
                  f"{m['recall']:>6.1%} {m['f1']:>6.1%}")

        # Show per-task flips
        if 'baseline' in all_results and len(all_results) > 1:
            last_key = list(all_results.keys())[-1]
            baseline_details = all_results['baseline']['details']
            aligned_details = all_results[last_key]['details']

            flips = []
            for b, a in zip(baseline_details, aligned_details):
                if b['predicted'] != a['predicted']:
                    direction = 'correct' if a['predicted'] == a['expected'] else 'regressed'
                    flips.append(f"  {b['task_id']}: {b['verdict']}->{a['verdict']} ({direction})")

            if flips:
                print(f"\nVerdict flips (baseline -> {last_key}):")
                for flip in flips:
                    print(flip)
            else:
                print("\nNo verdict flips between baseline and aligned.")


if __name__ == '__main__':
    main()
