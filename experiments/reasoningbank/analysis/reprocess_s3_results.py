#!/usr/bin/env python
"""
Reprocess S3 experiment results from trajectory logs.

The original run had a KeyError bug that prevented proper aggregation.
This script reads the trajectory logs and regenerates the results JSON
and summary report.
"""

import sys
import os
import json
from pathlib import Path
from datetime import datetime

sys.path.insert(0, '/Users/cvardema/dev/git/LA3D/rlm')

from experiments.reasoningbank.metrics.diversity import (
    compute_diversity_report,
    load_trajectory,
)


def load_trajectory_log(log_path: str) -> list[dict]:
    """Load trajectory events from JSONL log file."""
    trajectory = []

    if not os.path.exists(log_path):
        return trajectory

    with open(log_path, 'r') as f:
        for line in f:
            if line.strip():
                event = json.loads(line)
                # Extract iteration events with code/reasoning
                if event.get('event_type') == 'iteration':
                    trajectory.append(event)

    return trajectory


def extract_result_from_log(log_path: str) -> dict:
    """Extract converged status, answer, sparql from log file."""
    result = {
        'converged': False,
        'answer': None,
        'sparql': None,
        'judgment': {'success': False},
        'iters': 0,
    }

    if not os.path.exists(log_path):
        return result

    with open(log_path, 'r') as f:
        for line in f:
            if line.strip():
                event = json.loads(line)

                if event.get('event_type') == 'run_complete':
                    data = event.get('data', {})
                    result['converged'] = data.get('converged', False)
                    result['answer'] = data.get('answer_preview', '')
                    result['sparql'] = data.get('sparql', '')
                    result['iters'] = data.get('iterations', 0)
                    # Assume success if converged (no actual judgment in logs)
                    result['judgment'] = {'success': result['converged']}

    return result


def compute_stochastic_metrics(rollouts: list[dict]) -> dict:
    """Compute Pass@1, Best-of-N, Pass@k from rollout results."""
    judgments = [r['judgment']['success'] for r in rollouts]
    n_success = sum(judgments)
    n_total = len(judgments)

    return {
        'pass_1': judgments[0] if judgments else False,
        'best_of_n': any(judgments),
        'pass_k': n_success / n_total if n_total > 0 else 0.0,
        'n_success': n_success,
        'n_total': n_total,
    }


def reprocess_task_strategy(log_dir: str, task_id: str, k: int = 5) -> dict:
    """Reprocess results for a single task/strategy combination."""
    rollouts = []

    for rollout_idx in range(1, k + 1):  # 1-indexed rollout numbering
        log_path = os.path.join(log_dir, f'{task_id}_rollout{rollout_idx}.jsonl')
        result = extract_result_from_log(log_path)
        result['log_path'] = log_path
        rollouts.append(result)

    # Compute stochastic metrics
    metrics = compute_stochastic_metrics(rollouts)

    # Load trajectories for diversity metrics
    trajectories = []
    queries = []
    for rollout in rollouts:
        log_path = rollout.get('log_path')
        if log_path and os.path.exists(log_path):
            traj = load_trajectory(log_path)
            trajectories.append(traj)
        if rollout.get('sparql'):
            queries.append(rollout['sparql'])

    # Compute diversity metrics
    diversity = None
    if len(trajectories) >= 2:
        try:
            report = compute_diversity_report(trajectories, queries=queries)
            diversity = {
                'trajectory_vendi': report.trajectory_vendi_score,
                'sparql_vendi': report.sparql_vendi_score,
                'mean_jaccard': report.mean_pairwise_jaccard,
                'mean_edit_distance': report.mean_edit_distance,
                'sampling_efficiency': report.sampling_efficiency,
                'effective_count': report.effective_trajectory_count,
            }
        except Exception as e:
            print(f"    Warning: Could not compute diversity: {e}")

    return {
        'rollouts': rollouts,
        'metrics': metrics,
        'diversity': diversity,
        'num_trajectories': len(trajectories),
    }


def reprocess_s3_experiment(
    results_dir: str = 'experiments/reasoningbank/results/s3_prompt_perturbation',
    tasks_file: str = 'experiments/reasoningbank/uniprot_subset_tasks.json',
):
    """Reprocess S3 experiment from trajectory logs."""

    print("=" * 80)
    print("REPROCESSING S3 EXPERIMENT RESULTS")
    print("=" * 80)

    # Load task definitions
    with open(tasks_file, 'r') as f:
        all_tasks = json.load(f)

    task_map = {t['id']: t for t in all_tasks}

    # Expected task order from original run
    task_ids = [
        '1_select_all_taxa_used_in_uniprot',
        '4_uniprot_mnemonic_id',
        '2_bacteria_taxa_and_their_scientific_name',
        '121_proteins_and_diseases_linked',
        '30_merged_loci',
    ]

    strategies = ['none', 'prefix', 'thinking', 'rephrase']

    # Initialize results structure
    results = {
        'experiment': 's3_prompt_perturbation',
        'timestamp': datetime.now().isoformat(),
        'config': {
            'k': 5,
            'temperature': 0.7,
            'use_seed': False,
            'tasks': task_ids,
            'strategies': strategies,
        },
        'task_results': [],
    }

    # Process each task
    for task_id in task_ids:
        print(f"\nProcessing task: {task_id}")

        task = task_map.get(task_id)
        if not task:
            print(f"  Warning: Task {task_id} not found in tasks file")
            continue

        task_result = {
            'task_id': task_id,
            'task_query': task['query'],
            'complexity': task['complexity'],
            'strategy_results': {},
        }

        # Process each strategy
        for strategy in strategies:
            log_dir = os.path.join(results_dir, 'logs', task_id, strategy)

            if not os.path.exists(log_dir):
                print(f"  {strategy}: Log directory not found")
                task_result['strategy_results'][strategy] = {'error': 'Log directory not found'}
                continue

            try:
                strategy_result = reprocess_task_strategy(log_dir, task_id, k=5)

                # Add strategy name
                strategy_result['strategy'] = strategy

                # Convert to storage format
                task_result['strategy_results'][strategy] = {
                    'strategy': strategy,
                    'pass_at_1': strategy_result['metrics']['pass_1'],
                    'best_of_n': strategy_result['metrics']['best_of_n'],
                    'pass_at_k': strategy_result['metrics']['pass_k'],
                    'n_success': strategy_result['metrics']['n_success'],
                    'n_total': strategy_result['metrics']['n_total'],
                    'num_trajectories': strategy_result['num_trajectories'],
                    'diversity': strategy_result['diversity'],
                    'rollouts': strategy_result['rollouts'],
                }

                metrics = strategy_result['metrics']
                diversity = strategy_result['diversity']

                print(f"  {strategy:8s}: Pass@1={metrics['pass_1']}, Best-of-N={metrics['best_of_n']}, Pass@k={metrics['pass_k']:.2f}", end='')
                if diversity:
                    print(f", Vendi={diversity['trajectory_vendi']:.2f}, Eff={diversity['sampling_efficiency']:.1%}")
                else:
                    print()

            except Exception as e:
                print(f"  {strategy}: Error - {e}")
                import traceback
                traceback.print_exc()
                task_result['strategy_results'][strategy] = {'error': str(e)}

        results['task_results'].append(task_result)

    # Save results (convert numpy types to Python types for JSON serialization)
    def convert_numpy_types(obj):
        """Recursively convert numpy types to Python types."""
        import numpy as np
        if isinstance(obj, dict):
            return {k: convert_numpy_types(v) for k, v in obj.items()}
        elif isinstance(obj, list):
            return [convert_numpy_types(v) for v in obj]
        elif isinstance(obj, (np.integer, np.floating)):
            return float(obj)
        else:
            return obj

    results = convert_numpy_types(results)

    results_file = os.path.join(results_dir, 's3_results_reprocessed.json')
    with open(results_file, 'w') as f:
        json.dump(results, f, indent=2)

    print(f"\n{'='*80}")
    print("REPROCESSING COMPLETE")
    print(f"{'='*80}")
    print(f"\n✓ Results saved to: {results_file}")

    # Generate summary report
    from experiments.reasoningbank.run_experiment_s3 import generate_summary_report
    generate_summary_report(results, results_dir)

    return results


if __name__ == '__main__':
    reprocess_s3_experiment()
