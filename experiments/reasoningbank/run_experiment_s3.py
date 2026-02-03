#!/usr/bin/env python
"""
Experiment S3: Prompt Perturbation Effect

Tests whether different prompt perturbation strategies create meaningful
trajectory diversity in LLM reasoning paths.

Design:
- 5 representative tasks (2 simple, 2 moderate, 1 complex)
- k=5 rollouts per task
- 4 perturbation strategies: none, prefix, thinking, rephrase
- Total: 5 tasks × 5 rollouts × 4 strategies = 100 runs

Metrics:
- Trajectory Vendi Score (effective unique trajectories)
- Mean pairwise Jaccard similarity
- Mean edit distance
- Forking points
- Sampling efficiency
- Success rate (perturbations shouldn't hurt performance)

Expected outcome: Perturbation strategies should increase diversity without
hurting success rate.
"""

import sys
import os
import json
from pathlib import Path
from datetime import datetime

sys.path.insert(0, '/Users/cvardema/dev/git/LA3D/rlm')

from experiments.reasoningbank.run.phase1_uniprot import run_stochastic_uniprot
from experiments.reasoningbank.metrics.diversity import (
    compute_diversity_report,
    effective_trajectory_count,
)
from experiments.reasoningbank.metrics.visualize import (
    plot_diversity_summary,
    plot_similarity_heatmap,
)

from experiments.reasoningbank.core.mem import MemStore
from experiments.reasoningbank.ctx.builder import Cfg, Layer


def load_tasks(tasks_file: str) -> list[dict]:
    """Load tasks from JSON file."""
    with open(tasks_file, 'r') as f:
        return json.load(f)


def select_representative_tasks(all_tasks: list[dict], n: int = 5) -> list[dict]:
    """Select representative tasks covering different complexity levels."""
    # Categorize by complexity
    simple = [t for t in all_tasks if t.get('complexity') == 'simple']
    moderate = [t for t in all_tasks if t.get('complexity') == 'moderate']

    # Select: 2 simple, 3 moderate
    selected = []

    if len(simple) >= 2:
        selected.extend(simple[:2])
    else:
        selected.extend(simple)

    remaining = n - len(selected)
    if len(moderate) >= remaining:
        selected.extend(moderate[:remaining])
    else:
        selected.extend(moderate)
        # Fill remaining with simple tasks if needed
        if len(selected) < n:
            selected.extend(simple[2:2+(n-len(selected))])

    return selected[:n]


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


def run_experiment_s3(
    output_dir: str = 'experiments/reasoningbank/results/s3_prompt_perturbation',
    k: int = 5,
    temperature: float = 0.7,
    use_seed: bool = False,
):
    """Run Experiment S3: Prompt Perturbation Effect."""

    print("=" * 80)
    print("EXPERIMENT S3: PROMPT PERTURBATION EFFECT")
    print("=" * 80)
    print(f"\nConfiguration:")
    print(f"  Rollouts per task (k): {k}")
    print(f"  Temperature: {temperature}")
    print(f"  Use explicit seeds: {use_seed}")
    print(f"  Output directory: {output_dir}")

    # Create output directory
    os.makedirs(output_dir, exist_ok=True)

    # Load tasks
    tasks_file = 'experiments/reasoningbank/uniprot_subset_tasks.json'
    all_tasks = load_tasks(tasks_file)
    selected_tasks = select_representative_tasks(all_tasks, n=5)

    print(f"\nSelected {len(selected_tasks)} tasks:")
    for i, task in enumerate(selected_tasks, 1):
        print(f"  {i}. [{task['complexity']:8s}] {task['id']}")

    # Perturbation strategies to test
    strategies = ['none', 'prefix', 'thinking', 'rephrase']

    print(f"\nPerturbation strategies: {', '.join(strategies)}")

    # Initialize memory store (empty for baseline)
    mem = MemStore()

    # Initialize results structure
    results = {
        'experiment': 's3_prompt_perturbation',
        'timestamp': datetime.now().isoformat(),
        'config': {
            'k': k,
            'temperature': temperature,
            'use_seed': use_seed,
            'tasks': [t['id'] for t in selected_tasks],
            'strategies': strategies,
        },
        'task_results': [],
    }

    # Run each task with each strategy
    for task_idx, task in enumerate(selected_tasks, 1):
        print(f"\n{'='*80}")
        print(f"Task {task_idx}/{len(selected_tasks)}: {task['id']}")
        print(f"{'='*80}")

        task_result = {
            'task_id': task['id'],
            'task_query': task['query'],
            'complexity': task['complexity'],
            'strategy_results': {},
        }

        for strategy in strategies:
            print(f"\n  Strategy: {strategy}")
            print(f"  {'-'*60}")

            # Create strategy-specific log directory
            log_dir = os.path.join(output_dir, 'logs', task['id'], strategy)
            os.makedirs(log_dir, exist_ok=True)

            # Run stochastic evaluation with this strategy
            # Configure layers: L0 (sense card) + L1 (meta-graph), no memory for baseline
            cfg = Cfg(
                l0=Layer(True, 600),   # Sense card
                l1=Layer(True, 1000),  # Meta-graph
                l2=Layer(False, 2000), # No memory
            )

            try:
                stoch_result = run_stochastic_uniprot(
                    task=task,
                    ont_path='ontology/uniprot',
                    cfg=cfg,
                    mem=mem,
                    k=k,
                    temperature=temperature,
                    endpoint='uniprot',
                    verbose=False,
                    log_dir=log_dir,
                    use_local_interpreter=True,
                    perturb=strategy,
                    use_seed=use_seed,
                    compute_diversity=True,
                )

                # Load trajectories from logs
                trajectories = []
                for rollout_idx in range(k):
                    log_path = os.path.join(log_dir, f'rollout_{rollout_idx}.jsonl')
                    traj = load_trajectory_log(log_path)
                    if traj:
                        trajectories.append(traj)

                # Compute diversity metrics
                if len(trajectories) >= 2:
                    queries = [r['sparql'] for r in stoch_result['rollouts'] if 'sparql' in r]
                    diversity = compute_diversity_report(trajectories, queries=queries)

                    # Generate visualizations
                    viz_dir = os.path.join(output_dir, 'visualizations', task['id'])
                    os.makedirs(viz_dir, exist_ok=True)

                    plot_diversity_summary(
                        trajectories,
                        queries=queries,
                        save_path=os.path.join(viz_dir, f'{strategy}_summary.png')
                    )

                    print(f"    ✓ Diversity metrics computed")
                    print(f"      Trajectory Vendi: {diversity.trajectory_vendi_score:.2f}")
                    print(f"      Sampling Efficiency: {diversity.sampling_efficiency:.1%}")
                    print(f"      Mean Jaccard: {diversity.mean_pairwise_jaccard:.2f}")
                else:
                    diversity = None
                    print(f"    ⚠ Not enough trajectories for diversity metrics")

                # Store results
                strategy_result = {
                    'strategy': strategy,
                    'pass_at_1': stoch_result['metrics']['pass_1'],
                    'best_of_n': stoch_result['metrics']['best_of_n'],
                    'pass_at_k': stoch_result['metrics']['pass_k'],
                    'n_success': stoch_result['metrics']['n_success'],
                    'n_total': stoch_result['metrics']['n_total'],
                    'num_trajectories': len(trajectories),
                    'diversity': {
                        'trajectory_vendi': diversity.trajectory_vendi_score if diversity else None,
                        'sparql_vendi': diversity.sparql_vendi_score if diversity else None,
                        'mean_jaccard': diversity.mean_pairwise_jaccard if diversity else None,
                        'mean_edit_distance': diversity.mean_edit_distance if diversity else None,
                        'sampling_efficiency': diversity.sampling_efficiency if diversity else None,
                        'effective_count': diversity.effective_trajectory_count if diversity else None,
                    } if diversity else None,
                    'rollouts': stoch_result['rollouts'],
                }

                task_result['strategy_results'][strategy] = strategy_result

                print(f"    ✓ Pass@1: {stoch_result['metrics']['pass_1']}")
                print(f"    ✓ Best-of-N: {stoch_result['metrics']['best_of_n']}")
                print(f"    ✓ Pass@k: {stoch_result['metrics']['pass_k']:.2f} ({stoch_result['metrics']['n_success']}/{stoch_result['metrics']['n_total']})")

            except Exception as e:
                print(f"    ✗ Error running strategy {strategy}: {e}")
                import traceback
                traceback.print_exc()
                task_result['strategy_results'][strategy] = {'error': str(e)}

        results['task_results'].append(task_result)

    # Save results
    results_file = os.path.join(output_dir, 's3_results.json')
    with open(results_file, 'w') as f:
        json.dump(results, f, indent=2)

    print(f"\n{'='*80}")
    print("EXPERIMENT COMPLETE")
    print(f"{'='*80}")
    print(f"\n✓ Results saved to: {results_file}")

    # Generate summary report
    generate_summary_report(results, output_dir)


def generate_summary_report(results: dict, output_dir: str):
    """Generate summary report comparing strategies."""

    report_path = os.path.join(output_dir, 's3_summary_report.md')

    with open(report_path, 'w') as f:
        f.write("# Experiment S3: Prompt Perturbation Effect - Summary Report\n\n")
        f.write(f"**Date**: {results['timestamp']}\n\n")

        f.write("## Configuration\n\n")
        f.write(f"- Rollouts per task (k): {results['config']['k']}\n")
        f.write(f"- Temperature: {results['config']['temperature']}\n")
        f.write(f"- Explicit seeds: {results['config']['use_seed']}\n")
        f.write(f"- Tasks: {len(results['config']['tasks'])}\n")
        f.write(f"- Strategies: {', '.join(results['config']['strategies'])}\n\n")

        f.write("## Tasks\n\n")
        for task_result in results['task_results']:
            f.write(f"- `{task_result['task_id']}` [{task_result['complexity']}]\n")
        f.write("\n")

        f.write("## Results by Strategy\n\n")

        strategies = results['config']['strategies']

        # Aggregate metrics across tasks
        strategy_aggregates = {s: {
            'pass_at_1': [],
            'best_of_n': [],
            'trajectory_vendi': [],
            'sampling_efficiency': [],
            'mean_jaccard': [],
        } for s in strategies}

        for task_result in results['task_results']:
            for strategy in strategies:
                if strategy in task_result['strategy_results']:
                    sr = task_result['strategy_results'][strategy]
                    if 'error' not in sr:
                        strategy_aggregates[strategy]['pass_at_1'].append(sr['pass_at_1'])
                        strategy_aggregates[strategy]['best_of_n'].append(sr['best_of_n'])

                        if sr['diversity']:
                            if sr['diversity']['trajectory_vendi'] is not None:
                                strategy_aggregates[strategy]['trajectory_vendi'].append(
                                    sr['diversity']['trajectory_vendi']
                                )
                            if sr['diversity']['sampling_efficiency'] is not None:
                                strategy_aggregates[strategy]['sampling_efficiency'].append(
                                    sr['diversity']['sampling_efficiency']
                                )
                            if sr['diversity']['mean_jaccard'] is not None:
                                strategy_aggregates[strategy]['mean_jaccard'].append(
                                    sr['diversity']['mean_jaccard']
                                )

        # Write summary table
        f.write("### Performance Metrics\n\n")
        f.write("| Strategy | Pass@1 | Best-of-N | Trajectory Vendi | Efficiency | Mean Jaccard |\n")
        f.write("|----------|--------|-----------|------------------|------------|-------------|\n")

        for strategy in strategies:
            agg = strategy_aggregates[strategy]
            pass1 = sum(agg['pass_at_1']) / len(agg['pass_at_1']) if agg['pass_at_1'] else 0
            bestn = sum(agg['best_of_n']) / len(agg['best_of_n']) if agg['best_of_n'] else 0
            vendi = sum(agg['trajectory_vendi']) / len(agg['trajectory_vendi']) if agg['trajectory_vendi'] else 0
            eff = sum(agg['sampling_efficiency']) / len(agg['sampling_efficiency']) if agg['sampling_efficiency'] else 0
            jacc = sum(agg['mean_jaccard']) / len(agg['mean_jaccard']) if agg['mean_jaccard'] else 0

            f.write(f"| {strategy:8s} | {pass1:.1%} | {bestn:.1%} | {vendi:6.2f} | {eff:5.1%} | {jacc:.3f} |\n")

        f.write("\n")

        f.write("### Interpretation\n\n")

        # Find best strategy for diversity
        best_vendi_strategy = max(
            strategies,
            key=lambda s: sum(strategy_aggregates[s]['trajectory_vendi']) / len(strategy_aggregates[s]['trajectory_vendi'])
            if strategy_aggregates[s]['trajectory_vendi'] else 0
        )

        best_eff_strategy = max(
            strategies,
            key=lambda s: sum(strategy_aggregates[s]['sampling_efficiency']) / len(strategy_aggregates[s]['sampling_efficiency'])
            if strategy_aggregates[s]['sampling_efficiency'] else 0
        )

        f.write(f"**Best for trajectory diversity**: `{best_vendi_strategy}` "
                f"(highest Trajectory Vendi Score)\n\n")
        f.write(f"**Best for sampling efficiency**: `{best_eff_strategy}` "
                f"(highest ratio of unique trajectories)\n\n")

        # Check if perturbations hurt performance
        none_pass1 = sum(strategy_aggregates['none']['pass_at_1']) / len(strategy_aggregates['none']['pass_at_1']) if strategy_aggregates['none']['pass_at_1'] else 0

        f.write("**Performance impact**:\n")
        for strategy in [s for s in strategies if s != 'none']:
            strat_pass1 = sum(strategy_aggregates[strategy]['pass_at_1']) / len(strategy_aggregates[strategy]['pass_at_1']) if strategy_aggregates[strategy]['pass_at_1'] else 0
            impact = strat_pass1 - none_pass1
            symbol = "✓" if impact >= -0.05 else "⚠"
            f.write(f"- {symbol} `{strategy}`: {impact:+.1%} vs baseline\n")

        f.write("\n")

        f.write("### Detailed Results by Task\n\n")

        for task_result in results['task_results']:
            f.write(f"#### {task_result['task_id']} [{task_result['complexity']}]\n\n")
            f.write(f"*{task_result['task_query']}*\n\n")

            f.write("| Strategy | Pass@1 | Best-of-N | Traj Vendi | Efficiency |\n")
            f.write("|----------|--------|-----------|------------|------------|\n")

            for strategy in strategies:
                if strategy in task_result['strategy_results']:
                    sr = task_result['strategy_results'][strategy]
                    if 'error' in sr:
                        f.write(f"| {strategy:8s} | ERROR | ERROR | ERROR | ERROR |\n")
                    else:
                        vendi = sr['diversity']['trajectory_vendi'] if sr['diversity'] else 0
                        eff = sr['diversity']['sampling_efficiency'] if sr['diversity'] else 0
                        f.write(f"| {strategy:8s} | {sr['pass_at_1']:.1%} | {sr['best_of_n']:.1%} | "
                                f"{vendi:5.2f} | {eff:5.1%} |\n")

            f.write("\n")

    print(f"✓ Summary report saved to: {report_path}")


if __name__ == '__main__':
    import argparse

    parser = argparse.ArgumentParser(description='Run Experiment S3: Prompt Perturbation Effect')
    parser.add_argument('--output-dir', default='experiments/reasoningbank/results/s3_prompt_perturbation',
                        help='Output directory for results')
    parser.add_argument('--k', type=int, default=5,
                        help='Number of rollouts per task per strategy')
    parser.add_argument('--temperature', type=float, default=0.7,
                        help='Sampling temperature')
    parser.add_argument('--use-seed', action='store_true',
                        help='Use explicit different seeds per rollout')

    args = parser.parse_args()

    run_experiment_s3(
        output_dir=args.output_dir,
        k=args.k,
        temperature=args.temperature,
        use_seed=args.use_seed,
    )
