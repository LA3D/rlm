#!/usr/bin/env python
"""RLM Evaluation CLI.

Usage:
    python -m evals.cli run [PATTERN]
    python -m evals.cli list
    python -m evals.cli report [RESULTS_DIR]

Examples:
    # Run all tasks
    python -m evals.cli run

    # Run entity discovery tasks
    python -m evals.cli run 'entity_discovery/*'

    # Run with 3 trials
    python -m evals.cli run --trials 3

    # List available tasks
    python -m evals.cli list

    # Generate report from results
    python -m evals.cli report evals/results
"""

import argparse
import sys
from pathlib import Path
from datetime import datetime
import json

# Add parent to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from evals.runners.task_runner import TaskRunner, save_result, EvalResult


def find_tasks(pattern: str = '*') -> list[Path]:
    """Find task files matching pattern."""
    evals_dir = Path(__file__).parent
    tasks_dir = evals_dir / 'tasks'

    # Handle patterns like 'entity_discovery/*' or '*'
    if '/' in pattern:
        category, task_pattern = pattern.split('/', 1)
        # Support nested categories (e.g., 'uniprot/*' should match 'uniprot/**/X.yaml')
        if '/' in task_pattern:
            search_pattern = f'{category}/{task_pattern}.yaml'
        else:
            search_pattern = f'{category}/**/{task_pattern}.yaml'
    else:
        search_pattern = f'**/{pattern}.yaml'

    tasks = list(tasks_dir.glob(search_pattern))
    return sorted(tasks)


def run_command(args):
    """Run eval tasks."""
    tasks = find_tasks(args.pattern)

    if not tasks:
        print(f"No tasks found matching pattern: {args.pattern}")
        return 1

    print(f"Found {len(tasks)} tasks")
    print("-" * 50)

    # Configure runner with backend choice
    config = {'use_dspy': args.dspy}
    runner = TaskRunner(config=config)
    results = []
    output_dir = Path(args.output)

    if args.dspy:
        print("Using DSPy backend")
    else:
        print("Using claudette backend")

    for task_path in tasks:
        tasks_dir = Path(__file__).parent / 'tasks'
        print(f"\nRunning: {task_path.relative_to(tasks_dir)}")

        try:
            result = runner.run_task(task_path, num_trials=args.trials)
            results.append(result)

            # Print summary
            print(f"  pass@{result.total_trials}: {result.pass_at_k:.1%}")
            print(f"  pass^{result.total_trials}: {result.pass_power_k:.1%}")
            print(f"  Passed: {result.passed_trials}/{result.total_trials}")
            print(f"  Avg iterations: {result.avg_iterations:.1f}")

            # Save result
            save_result(result, output_dir)

        except Exception as e:
            print(f"  ERROR: {e}")

    # Print overall summary
    print("\n" + "=" * 50)
    print("SUMMARY")
    print("=" * 50)

    total_trials = sum(r.total_trials for r in results)
    total_passed = sum(r.passed_trials for r in results)
    avg_pass_rate = total_passed / total_trials if total_trials > 0 else 0

    print(f"Tasks run: {len(results)}")
    print(f"Total trials: {total_trials}")
    print(f"Total passed: {total_passed}")
    print(f"Overall pass rate: {avg_pass_rate:.1%}")

    # Check pass threshold
    if args.min_pass_rate:
        if avg_pass_rate < args.min_pass_rate:
            print(f"\nFAILED: Pass rate {avg_pass_rate:.1%} < required {args.min_pass_rate:.1%}")
            return 1

    return 0


def list_command(args):
    """List available eval tasks."""
    tasks = find_tasks('*')
    tasks_dir = Path(__file__).parent / 'tasks'

    print(f"Found {len(tasks)} tasks:\n")

    current_category = None
    for task_path in tasks:
        rel = task_path.relative_to(tasks_dir)
        category = rel.parent.as_posix()

        if category != current_category:
            print(f"\n{category}/")
            current_category = category

        print(f"  {task_path.stem}")

    return 0


def report_command(args):
    """Generate report from results."""
    results_dir = Path(args.results_dir)

    if not results_dir.exists():
        print(f"Results directory not found: {results_dir}")
        return 1

    # Find all result JSON files
    result_files = list(results_dir.glob('*.json'))

    if not result_files:
        print("No result files found")
        return 1

    print(f"Found {len(result_files)} result files\n")
    print("=" * 60)
    print("EVAL REPORT")
    print("=" * 60)

    # Aggregate by category
    by_category = {}

    for result_file in result_files:
        try:
            with open(result_file) as f:
                data = json.load(f)

            task_id = data.get('task_id', result_file.stem)
            category = task_id.split('_')[0] if '_' in task_id else 'unknown'

            if category not in by_category:
                by_category[category] = []

            by_category[category].append({
                'task_id': task_id,
                'pass_at_k': data.get('pass_at_k', 0),
                'pass_power_k': data.get('pass_power_k', 0),
                'passed': data.get('passed_trials', 0),
                'total': data.get('total_trials', 0),
                'avg_iterations': data.get('avg_iterations', 0)
            })

        except Exception as e:
            print(f"Warning: Could not read {result_file}: {e}")

    # Print by category
    for category, results in sorted(by_category.items()):
        print(f"\n{category.upper()}")
        print("-" * 40)

        for r in results:
            status = "PASS" if r['passed'] == r['total'] else "FAIL"
            print(f"  [{status}] {r['task_id']}: {r['passed']}/{r['total']} ({r['pass_at_k']:.0%})")

        # Category summary
        total = sum(r['total'] for r in results)
        passed = sum(r['passed'] for r in results)
        print(f"  Category: {passed}/{total} ({passed/total:.0%})" if total > 0 else "")

    # Overall summary
    all_total = sum(sum(r['total'] for r in results) for results in by_category.values())
    all_passed = sum(sum(r['passed'] for r in results) for results in by_category.values())

    print("\n" + "=" * 60)
    print(f"OVERALL: {all_passed}/{all_total} ({all_passed/all_total:.1%})" if all_total > 0 else "No results")

    return 0


def main():
    parser = argparse.ArgumentParser(
        description='RLM Evaluation CLI',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__
    )

    subparsers = parser.add_subparsers(dest='command', help='Commands')

    # Run command
    run_parser = subparsers.add_parser('run', help='Run eval tasks')
    run_parser.add_argument('pattern', nargs='?', default='*',
                           help='Task pattern (e.g., "entity_discovery/*")')
    run_parser.add_argument('--trials', '-t', type=int, default=None,
                           help='Override number of trials')
    run_parser.add_argument('--output', '-o', default='evals/results',
                           help='Output directory for results')
    run_parser.add_argument('--min-pass-rate', type=float, default=None,
                           help='Minimum pass rate to succeed (0.0-1.0)')
    run_parser.add_argument('--dspy', action='store_true',
                           help='Use DSPy backend instead of claudette')

    # List command
    list_parser = subparsers.add_parser('list', help='List available tasks')

    # Report command
    report_parser = subparsers.add_parser('report', help='Generate report')
    report_parser.add_argument('results_dir', nargs='?', default='evals/results',
                              help='Results directory')

    args = parser.parse_args()

    if args.command == 'run':
        return run_command(args)
    elif args.command == 'list':
        return list_command(args)
    elif args.command == 'report':
        return report_command(args)
    else:
        parser.print_help()
        return 0


if __name__ == '__main__':
    sys.exit(main())
