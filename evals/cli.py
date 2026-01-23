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
from evals.runners.matrix_runner import MatrixRunner


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

    # Filter by reasoning level if specified (Rung 6)
    if args.reasoning_level:
        import yaml
        filtered_tasks = []
        for task_path in tasks:
            try:
                raw = yaml.safe_load(task_path.read_text())
                task = raw.get('task', raw) if isinstance(raw, dict) else raw
                if task.get('reasoning_level') == args.reasoning_level:
                    filtered_tasks.append(task_path)
            except Exception:
                pass  # Skip tasks that can't be parsed
        tasks = filtered_tasks
        print(f"Filtered to {len(tasks)} tasks with reasoning_level={args.reasoning_level}")

    if not tasks:
        print(f"No tasks found after filtering")
        return 1

    print(f"Found {len(tasks)} tasks")
    print("-" * 50)

    # Setup MLflow if requested (Rung 3)
    mlflow_active = False
    if args.mlflow:
        try:
            from rlm_runtime.logging.mlflow_integration import setup_mlflow_tracking
            mlflow_active, mlflow_run_id = setup_mlflow_tracking(
                experiment_name=args.mlflow_experiment or "RLM Eval Harness",
                run_name=f"eval-{datetime.now().strftime('%Y%m%d-%H%M%S')}",
                tracking_uri=args.mlflow_tracking_uri,
                log_compilation=False
            )
            if mlflow_active:
                print(f"MLflow tracking enabled: experiment='{args.mlflow_experiment or 'RLM Eval Harness'}'")
        except ImportError:
            print("Warning: MLflow not available, skipping tracking")
        except Exception as e:
            print(f"Warning: MLflow setup failed: {e}")

    # Configure runner with backend choice (DSPy is now default)
    config = {
        'use_dspy': not args.claudette,
        'enable_mlflow': mlflow_active,
        'mlflow_experiment': args.mlflow_experiment,
        'mlflow_tracking_uri': args.mlflow_tracking_uri,
        'enable_memory': args.enable_memory,
        'memory_db_path': args.memory_db
    }
    runner = TaskRunner(config=config)
    results = []
    output_dir = Path(args.output)

    if args.claudette:
        print("Using claudette backend (legacy)")
    else:
        print("Using DSPy backend")

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
            # End MLflow run if active
            if mlflow_active:
                try:
                    from rlm_runtime.logging.mlflow_integration import end_mlflow_run
                    end_mlflow_run()
                except Exception:
                    pass
            return 1

    # End MLflow run if active (Rung 3)
    if mlflow_active:
        try:
            from rlm_runtime.logging.mlflow_integration import end_mlflow_run
            end_mlflow_run()
        except Exception as e:
            print(f"Warning: Failed to end MLflow run: {e}")

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


def matrix_command(args):
    """Run matrix of tasks across ablation cohorts."""
    tasks = find_tasks(args.pattern)

    if not tasks:
        print(f"No tasks found matching pattern: {args.pattern}")
        return 1

    print(f"Found {len(tasks)} tasks")
    print(f"Cohorts: {', '.join(args.cohorts)}")
    print("-" * 50)

    # Create matrix runner
    runner = MatrixRunner(base_output_dir=args.output)

    # Run matrix
    try:
        summary = runner.run_matrix(
            task_paths=tasks,
            cohorts=args.cohorts,
            num_trials=args.trials,
            enable_mlflow=args.mlflow,
            mlflow_tracking_uri=args.mlflow_tracking_uri
        )

        # Print summary
        print(f"\nCohort Comparison:")
        for cohort_name, cohort_stats in summary['by_cohort'].items():
            print(f"  {cohort_name}:")
            print(f"    Pass rate: {cohort_stats['avg_pass_rate']:.1%}")
            print(f"    Avg iterations: {cohort_stats['avg_iterations']:.1f}")

        if summary['improvements']:
            print(f"\nImprovements:")
            for imp in summary['improvements']:
                print(f"  {imp['comparison']}: {imp['absolute_improvement']:+.1%} ({imp['relative_improvement']:+.1%} relative)")

        return 0

    except Exception as e:
        print(f"Error running matrix: {e}")
        import traceback
        traceback.print_exc()
        return 1


def analyze_command(args):
    """Generate structured analysis for Claude Code."""
    from evals.analysis import generate_summary, generate_cohort_comparison

    # Check if analyzing matrix results or regular results
    input_path = Path(args.input)

    if input_path.is_file() and input_path.name == 'matrix_summary.json':
        # Cohort comparison
        print("Analyzing matrix results...")
        result = generate_cohort_comparison(str(input_path))
    else:
        # Regular summary
        print(f"Analyzing results from: {input_path}")
        result = generate_summary(str(input_path), format=args.format)

    # Output
    if args.format == 'json':
        output = json.dumps(result, indent=2)
        print(output)

        # Save to file if requested
        if args.output:
            with open(args.output, 'w') as f:
                f.write(output)
            print(f"\nSaved to: {args.output}")
    else:
        # Markdown format
        print("\n" + "=" * 60)
        print("EVALUATION ANALYSIS")
        print("=" * 60)

        if 'error' in result:
            print(f"\nError: {result['error']}")
            return 1

        if 'cohorts_evaluated' in result:
            # Cohort comparison
            print("\n## Cohort Comparison")
            for item in result['performance_ranking']:
                print(f"  {item['cohort']}: {item['pass_rate']:.1%} pass rate, {item['avg_iterations']:.1f} avg iterations")

            if result.get('recommendations'):
                print("\n## Recommendations")
                for rec in result['recommendations']:
                    print(f"- {rec}")
        else:
            # Regular summary
            print(f"\nTotal tasks: {result['total_tasks']}")
            print(f"Overall pass rate: {result['overall_pass_rate']:.1%}")

            print("\n## By Category")
            for category, stats in result['by_category'].items():
                print(f"  {category}: {stats['pass_rate']:.1%} ({stats['passed']}/{stats['trials']})")

            if result.get('failing_tasks'):
                print("\n## Worst Performing Tasks")
                for task in result['failing_tasks'][:5]:
                    print(f"  {task['task_id']}: {task['pass_rate']:.1%}")

            if result.get('recommendations'):
                print("\n## Recommendations")
                for rec in result['recommendations']:
                    print(f"- {rec}")

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
    run_parser.add_argument('--claudette', action='store_true',
                           help='Use claudette backend (legacy, default is DSPy)')
    # MLflow integration (Rung 3)
    run_parser.add_argument('--mlflow', action='store_true',
                           help='Enable MLflow tracking for experiments')
    run_parser.add_argument('--mlflow-experiment', type=str, default=None,
                           help='MLflow experiment name (creates if not exists)')
    run_parser.add_argument('--mlflow-tracking-uri', type=str, default=None,
                           help='MLflow tracking URI (e.g., sqlite:///mlflow.db)')
    # Reasoning level filter (Rung 6)
    run_parser.add_argument('--reasoning-level', type=str, default=None,
                           help='Filter tasks by reasoning level (e.g., L3_materialized, L4_federation)')
    # Memory (ReasoningBank) integration
    run_parser.add_argument('--enable-memory', action='store_true',
                           help='Enable ReasoningBank procedural memory (learns from trajectories)')
    run_parser.add_argument('--memory-db', type=str, default='evals/memory.db',
                           help='Path to memory database (default: evals/memory.db)')

    # List command
    list_parser = subparsers.add_parser('list', help='List available tasks')

    # Matrix command (Rung 5)
    matrix_parser = subparsers.add_parser('matrix', help='Run ablation matrix across cohorts')
    matrix_parser.add_argument('pattern', nargs='?', default='*',
                              help='Task pattern (e.g., "uniprot/*")')
    matrix_parser.add_argument('--cohorts', '-c', nargs='+',
                              default=['baseline', 'structural', 'full'],
                              help='Cohort names to run (default: baseline structural full)')
    matrix_parser.add_argument('--trials', '-t', type=int, default=None,
                              help='Override number of trials')
    matrix_parser.add_argument('--output', '-o', default='evals/matrix_results',
                              help='Output directory for matrix results')
    matrix_parser.add_argument('--mlflow', action='store_true',
                              help='Enable MLflow tracking')
    matrix_parser.add_argument('--mlflow-tracking-uri', type=str, default=None,
                              help='MLflow tracking URI')

    # Analyze command (Rung 8)
    analyze_parser = subparsers.add_parser('analyze', help='Generate structured analysis for Claude Code')
    analyze_parser.add_argument('input', nargs='?', default='evals/results',
                               help='Results directory or matrix_summary.json path')
    analyze_parser.add_argument('--format', '-f', choices=['json', 'markdown'],
                               default='json', help='Output format')
    analyze_parser.add_argument('--output', '-o', type=str, default=None,
                               help='Save output to file')

    # Report command
    report_parser = subparsers.add_parser('report', help='Generate report')
    report_parser.add_argument('results_dir', nargs='?', default='evals/results',
                              help='Results directory')

    args = parser.parse_args()

    if args.command == 'run':
        return run_command(args)
    elif args.command == 'list':
        return list_command(args)
    elif args.command == 'matrix':
        return matrix_command(args)
    elif args.command == 'analyze':
        return analyze_command(args)
    elif args.command == 'report':
        return report_command(args)
    else:
        parser.print_help()
        return 0


if __name__ == '__main__':
    sys.exit(main())
