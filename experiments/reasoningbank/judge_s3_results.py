#!/usr/bin/env python
"""Re-run LM-as-judge on existing S3 trajectory results.

The S3 experiment's result aggregation crashed, so judgment data was lost.
The reprocessing script used convergence as a proxy.
This script re-runs the actual LLM judge on all S3 results.
"""

import sys
import os
import json
import glob
from collections import defaultdict

sys.path.insert(0, '/Users/cvardema/dev/git/LA3D/rlm')

import dspy
from experiments.reasoningbank.run.phase1 import judge
from experiments.reasoningbank.run.rlm_uniprot import Result, Metrics


def load_trajectory_events(log_path: str) -> list[dict]:
    """Load events from a trajectory JSONL file."""
    events = []
    try:
        with open(log_path) as f:
            for line in f:
                if line.strip():
                    events.append(json.loads(line))
    except Exception as e:
        print(f"  Warning: Could not load {log_path}: {e}")
    return events


def extract_result_from_trajectory(events: list[dict]) -> dict | None:
    """Extract answer, sparql, converged from trajectory events."""
    for event in events:
        if event.get('event_type') == 'run_complete':
            data = event.get('data', {})
            return {
                'converged': data.get('converged', False),
                'answer': data.get('answer_preview', ''),
                'sparql': data.get('sparql'),
                'iterations': data.get('iterations', 0),
            }
        elif event.get('event_type') == 'run_error':
            data = event.get('data', {})
            return {
                'converged': False,
                'answer': f"Error: {data.get('error', 'unknown')}",
                'sparql': None,
                'iterations': 0,
                'refusal_detected': data.get('refusal_detected', False),
            }
    return None


def main():
    # Configure DSPy for judge (deterministic)
    if not os.environ.get('ANTHROPIC_API_KEY'):
        raise ValueError("Set ANTHROPIC_API_KEY environment variable")

    lm = dspy.LM('anthropic/claude-sonnet-4-5-20250929',
                  api_key=os.environ['ANTHROPIC_API_KEY'],
                  temperature=0.0)
    dspy.configure(lm=lm)

    # Load task definitions
    with open('experiments/reasoningbank/uniprot_subset_tasks.json') as f:
        tasks = json.load(f)
    task_map = {t['id']: t for t in tasks}

    # Find all S3 trajectory logs
    log_base = 'experiments/reasoningbank/results/s3_prompt_perturbation/logs'
    task_dirs = sorted(glob.glob(f'{log_base}/*/'))

    print(f"Found {len(task_dirs)} task directories")
    print("=" * 80)

    all_results = []
    judge_stats = defaultdict(int)

    for task_dir in task_dirs:
        task_id = os.path.basename(task_dir.rstrip('/'))
        task = task_map.get(task_id)
        if not task:
            print(f"\nSkipping {task_id}: not in task definitions")
            continue

        print(f"\nTask: {task_id}")
        print(f"  Query: {task['query']}")

        task_result = {
            'task_id': task_id,
            'query': task['query'],
            'strategy_results': {},
        }

        # Process each strategy
        strategy_dirs = sorted(glob.glob(f'{task_dir}*/'))
        for strategy_dir in strategy_dirs:
            strategy = os.path.basename(strategy_dir.rstrip('/'))

            # Find rollout logs
            rollout_files = sorted(glob.glob(f'{strategy_dir}*.jsonl'))
            if not rollout_files:
                print(f"  {strategy}: no rollout files found")
                continue

            print(f"  Strategy: {strategy} ({len(rollout_files)} rollouts)")

            rollout_judgments = []
            for rollout_file in rollout_files:
                events = load_trajectory_events(rollout_file)
                result_data = extract_result_from_trajectory(events)

                if result_data is None:
                    print(f"    {os.path.basename(rollout_file)}: no result found")
                    rollout_judgments.append({
                        'log_file': rollout_file,
                        'converged': False,
                        'judgment': {'success': False, 'reason': 'No result in trajectory log'},
                    })
                    judge_stats['no_result'] += 1
                    continue

                # Check for refusal
                if result_data.get('refusal_detected'):
                    j = {'success': False, 'reason': 'LLM refused (safety filter)'}
                    judge_stats['refused'] += 1
                elif not result_data['converged']:
                    j = {'success': False, 'reason': 'Did not converge'}
                    judge_stats['not_converged'] += 1
                else:
                    # Create a Result object for the judge
                    res = Result(
                        answer=result_data['answer'],
                        sparql=result_data['sparql'],
                        converged=True,
                        iters=result_data.get('iterations', 0),
                        leakage=Metrics(),
                        trace=[],
                        trajectory=[],
                    )

                    # Run LLM judge
                    j = judge(res, task['query'], verbose=False)
                    judge_stats['judged'] += 1

                status = '✓' if j['success'] else '✗'
                print(f"    {status} {os.path.basename(rollout_file)}: {j['reason'][:60]}")

                rollout_judgments.append({
                    'log_file': rollout_file,
                    'converged': result_data['converged'],
                    'answer': result_data.get('answer', '')[:200],
                    'sparql': result_data.get('sparql'),
                    'iterations': result_data.get('iterations', 0),
                    'judgment': j,
                })

            # Compute metrics for this strategy
            judgments = [r['judgment']['success'] for r in rollout_judgments]
            n_success = sum(judgments)
            n_total = len(judgments)

            strategy_metrics = {
                'pass_1': judgments[0] if judgments else False,
                'best_of_n': any(judgments),
                'pass_k': n_success / n_total if n_total > 0 else 0.0,
                'n_success': n_success,
                'n_total': n_total,
            }

            task_result['strategy_results'][strategy] = {
                'strategy': strategy,
                'metrics': strategy_metrics,
                'rollouts': rollout_judgments,
            }

            print(f"    Metrics: Pass@1={strategy_metrics['pass_1']}, "
                  f"Best-of-N={strategy_metrics['best_of_n']}, "
                  f"Pass@k={strategy_metrics['pass_k']:.2f} "
                  f"({n_success}/{n_total})")

        all_results.append(task_result)

    # Save results
    output_path = 'experiments/reasoningbank/results/s3_prompt_perturbation/s3_judged_results.json'
    with open(output_path, 'w') as f:
        json.dump({
            'experiment': 'S3 Prompt Perturbation (Re-judged)',
            'judge_model': 'claude-sonnet-4-5-20250929',
            'judge_temperature': 0.0,
            'judge_stats': dict(judge_stats),
            'task_results': all_results,
        }, f, indent=2)

    print(f"\n{'='*80}")
    print("JUDGMENT COMPLETE")
    print(f"{'='*80}")
    print(f"\nJudge stats:")
    for k, v in sorted(judge_stats.items()):
        print(f"  {k}: {v}")

    total = sum(judge_stats.values())
    print(f"  total: {total}")

    print(f"\nResults saved to: {output_path}")

    # Print aggregate summary
    print(f"\n{'='*80}")
    print("AGGREGATE METRICS")
    print(f"{'='*80}")

    strategy_agg = defaultdict(lambda: {'pass_1': [], 'best_of_n': [], 'pass_k': []})
    for task_result in all_results:
        for strategy, sr in task_result['strategy_results'].items():
            m = sr['metrics']
            strategy_agg[strategy]['pass_1'].append(m['pass_1'])
            strategy_agg[strategy]['best_of_n'].append(m['best_of_n'])
            strategy_agg[strategy]['pass_k'].append(m['pass_k'])

    print(f"\n{'Strategy':<12} {'Pass@1':>8} {'Best-of-N':>10} {'Pass@k':>8}")
    print("-" * 42)
    for strategy in ['none', 'prefix', 'thinking', 'rephrase']:
        if strategy in strategy_agg:
            agg = strategy_agg[strategy]
            p1 = sum(agg['pass_1']) / len(agg['pass_1']) if agg['pass_1'] else 0
            bon = sum(agg['best_of_n']) / len(agg['best_of_n']) if agg['best_of_n'] else 0
            pk = sum(agg['pass_k']) / len(agg['pass_k']) if agg['pass_k'] else 0
            print(f"{strategy:<12} {p1:>7.1%} {bon:>9.1%} {pk:>7.1%}")


if __name__ == '__main__':
    main()
