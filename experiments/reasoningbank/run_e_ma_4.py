#!/usr/bin/env python
"""E-MA-4: Memory Scaling (Accumulation Test).

Tests whether judge accuracy improves as feedback accumulates over batches.

Protocol:
    1. Start with E-MA-2 judge memory (5 principles + 6 episodes)
    2. Run judge on 20 NEW annotated tasks (judge_scaling_tasks.json)
    3. Process in batches of 5:
       - Batch 1 (tasks 1-5): Judge -> expert corrects errors -> extract -> accumulate
       - Batch 2 (tasks 6-10): Judge with accumulated memory -> correct -> accumulate
       - Batch 3 (tasks 11-15): Judge -> correct -> accumulate
       - Batch 4 (tasks 16-20): Judge -> measure only (test set, no correction)
    4. Report accuracy curve across batches

Usage:
    python experiments/reasoningbank/run_e_ma_4.py -v
"""

import sys
sys.path.insert(0, '/Users/cvardema/dev/git/LA3D/rlm')

import json
import os
from datetime import datetime

import dspy

from experiments.reasoningbank.prototype.core.mem import MemStore
from experiments.reasoningbank.prototype.run.memalign import (
    evaluate_judge, judge_aligned, load_judge_mem, ingest_feedback,
    print_metrics,
)


def run_scaling_experiment(
    judge_mem: MemStore,
    tasks: list[dict],
    batch_size: int = 5,
    n_batches: int = 4,
    verbose: bool = False,
) -> dict:
    """Run memory scaling experiment across batches.

    For batches 1 through n_batches-1: judge, collect errors, ingest feedback.
    For the final batch: judge only (test set, no correction).

    Args:
        judge_mem: Initial judge memory (principles + episodes)
        tasks: List of annotated tasks with expert_verdict
        batch_size: Tasks per batch
        n_batches: Number of batches
        verbose: Print details

    Returns:
        dict with per-batch metrics and scaling curve data
    """
    total_needed = batch_size * n_batches
    if len(tasks) < total_needed:
        print(f"Warning: only {len(tasks)} tasks available, need {total_needed}")
    tasks = tasks[:total_needed]

    batches = [tasks[i*batch_size:(i+1)*batch_size] for i in range(n_batches)]
    batch_results = []
    memory_sizes = [len(judge_mem.all())]

    for batch_idx, batch_tasks in enumerate(batches):
        is_test_batch = (batch_idx == n_batches - 1)
        batch_label = f"Batch {batch_idx + 1}/{n_batches}" + (" (TEST)" if is_test_batch else "")

        print(f"\n{'='*60}")
        print(f"{batch_label}: {len(batch_tasks)} tasks, memory={len(judge_mem.all())} items")
        print(f"{'='*60}")

        # Judge all tasks in this batch
        judge_fn = lambda task, answer, sparql: judge_aligned(
            task, answer, sparql, judge_mem, verbose=verbose
        )
        metrics = evaluate_judge(
            judge_fn=judge_fn,
            eval_tasks=batch_tasks,
            verbose=verbose,
        )
        print_metrics(metrics, batch_label)

        # For training batches: ingest feedback from errors
        n_ingested = 0
        if not is_test_batch:
            for detail, task_data in zip(metrics['details'], batch_tasks):
                if detail['predicted'] != detail['expected']:
                    # Error found - ingest expert correction
                    expert_reason = task_data.get('expert_reason', '')
                    if not expert_reason:
                        expert_reason = (
                            f"Judge said {detail['predicted']}, "
                            f"correct is {detail['expected']}"
                        )

                    items = ingest_feedback(
                        task=task_data['query'],
                        agent_sparql=task_data.get('agent_sparql', ''),
                        judge_verdict=detail['predicted'],
                        expert_verdict=detail['expected'],
                        expert_reason=expert_reason,
                        judge_mem=judge_mem,
                        verbose=verbose,
                    )
                    n_ingested += len(items)

            print(f"  Ingested {n_ingested} items from "
                  f"{metrics['total'] - metrics['correct']} errors")

        batch_results.append({
            'batch_idx': batch_idx,
            'label': batch_label,
            'n_tasks': len(batch_tasks),
            'metrics': metrics,
            'n_ingested': n_ingested,
            'memory_size_after': len(judge_mem.all()),
            'is_test': is_test_batch,
        })
        memory_sizes.append(len(judge_mem.all()))

    # Build scaling curve
    accuracies = [b['metrics']['accuracy'] for b in batch_results]
    scaling_curve = {
        'batch_accuracies': accuracies,
        'memory_sizes': memory_sizes,
        'monotonic': all(
            accuracies[i] <= accuracies[i+1]
            for i in range(len(accuracies)-1)
        ),
        'test_accuracy': accuracies[-1] if batch_results else 0.0,
        'improvement': (
            accuracies[-1] - accuracies[0] if len(accuracies) > 1 else 0.0
        ),
    }

    return {
        'batch_results': batch_results,
        'scaling_curve': scaling_curve,
        'final_memory_size': len(judge_mem.all()),
    }


def main():
    import argparse

    parser = argparse.ArgumentParser(
        description='E-MA-4: Memory Scaling Experiment')
    parser.add_argument('--principles',
                        default='experiments/reasoningbank/seed/judge_principles.json')
    parser.add_argument('--episodes',
                        default='experiments/reasoningbank/seed/judge_episodes.json')
    parser.add_argument('--scaling-tasks',
                        default='experiments/reasoningbank/tasks/judge_scaling_tasks.json',
                        help='Path to annotated scaling tasks')
    parser.add_argument('--batch-size', type=int, default=5)
    parser.add_argument('--n-batches', type=int, default=4)
    parser.add_argument('--output-dir',
                        default='experiments/reasoningbank/results/e_ma_4')
    parser.add_argument('--verbose', '-v', action='store_true')
    parser.add_argument('--model', default='anthropic/claude-sonnet-4-5-20250929')

    args = parser.parse_args()

    # Configure DSPy
    lm = dspy.LM(args.model, temperature=0.0)
    dspy.configure(lm=lm)

    # Load initial judge memory (E-MA-2 state)
    judge_mem = load_judge_mem(
        principles_path=args.principles,
        episodes_path=args.episodes,
    )
    print(f"Initial judge memory: {len(judge_mem.all())} items")

    # Load annotated tasks
    with open(args.scaling_tasks) as f:
        tasks = json.load(f)

    # Verify tasks have expert verdicts
    has_verdicts = all(t.get('expert_verdict') is not None for t in tasks)
    total_needed = args.batch_size * args.n_batches
    print(f"Loaded {len(tasks)} annotated tasks "
          f"(need {total_needed} for {args.n_batches} batches of {args.batch_size})")
    if not has_verdicts:
        print("ERROR: Tasks missing expert_verdict. Use judge_scaling_tasks.json.")
        return

    n_correct = sum(1 for t in tasks if t['expert_verdict'])
    n_incorrect = sum(1 for t in tasks if not t['expert_verdict'])
    print(f"  Distribution: {n_correct} correct ({n_correct/len(tasks):.0%}), "
          f"{n_incorrect} incorrect ({n_incorrect/len(tasks):.0%})")

    # Run experiment
    results = run_scaling_experiment(
        judge_mem=judge_mem,
        tasks=tasks,
        batch_size=args.batch_size,
        n_batches=args.n_batches,
        verbose=args.verbose,
    )

    # Print summary
    print("\n" + "=" * 60)
    print("SCALING CURVE SUMMARY")
    print("=" * 60)
    curve = results['scaling_curve']
    print(f"{'Batch':<20} {'Accuracy':>8} {'Memory':>8} {'Ingested':>8}")
    print("-" * 50)
    for b in results['batch_results']:
        label = "TEST" if b['is_test'] else "train"
        print(f"  Batch {b['batch_idx']+1} ({label})"
              f"     {b['metrics']['accuracy']:>7.1%}"
              f"     {b['memory_size_after']:>5}"
              f"     {b['n_ingested']:>5}")

    print(f"\n  Monotonic improvement: {curve['monotonic']}")
    print(f"  Total improvement: {curve['improvement']:+.1%}")
    print(f"  Final memory size: {results['final_memory_size']} items")

    # Success criteria
    print("\n" + "=" * 60)
    print("SUCCESS CRITERIA")
    print("=" * 60)
    criteria = {
        'Test accuracy >= 75%': curve['test_accuracy'] >= 0.75,
        'Accuracy improved over batches': curve['improvement'] > 0,
        'Memory bounded (< 30 items)': results['final_memory_size'] < 30,
    }
    for name, passed in criteria.items():
        mark = 'PASS' if passed else 'FAIL'
        print(f"  [{mark}] {name}")

    # Save results
    os.makedirs(args.output_dir, exist_ok=True)
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')

    with open(os.path.join(args.output_dir, 'scaling_curve.json'), 'w') as f:
        json.dump({
            'experiment': 'E-MA-4',
            'timestamp': timestamp,
            'config': {
                'batch_size': args.batch_size,
                'n_batches': args.n_batches,
                'model': args.model,
            },
            'scaling_curve': curve,
            'batch_summaries': [
                {
                    'batch': b['batch_idx'],
                    'label': b['label'],
                    'accuracy': b['metrics']['accuracy'],
                    'precision': b['metrics']['precision'],
                    'recall': b['metrics']['recall'],
                    'f1': b['metrics']['f1'],
                    'n_ingested': b['n_ingested'],
                    'memory_size': b['memory_size_after'],
                    'is_test': b['is_test'],
                }
                for b in results['batch_results']
            ],
            'criteria': {k: v for k, v in criteria.items()},
        }, f, indent=2)

    judge_mem.save(os.path.join(args.output_dir, 'judge_memory_final.json'))
    print(f"\nResults saved to {args.output_dir}/")


if __name__ == '__main__':
    main()
