"""Matrix runner for ablation experiments across feature cohorts."""

import json
from datetime import datetime
from pathlib import Path
from typing import Optional

from ..ablation_config import AblationConfig
from .task_runner import TaskRunner, EvalResult, save_result


class MatrixRunner:
    """Run same tasks across multiple ablation cohorts for comparison.

    Enables systematic evaluation of which sense card features improve
    query construction performance.
    """

    def __init__(self, base_output_dir: str = 'evals/matrix_results'):
        """Initialize matrix runner.

        Args:
            base_output_dir: Base directory for matrix results
        """
        self.base_output_dir = Path(base_output_dir)

    def run_matrix(
        self,
        task_paths: list[Path],
        cohorts: list[str],
        num_trials: Optional[int] = None,
        enable_mlflow: bool = False,
        mlflow_tracking_uri: Optional[str] = None
    ) -> dict:
        """Run tasks across multiple ablation cohorts.

        Args:
            task_paths: List of task file paths to run
            cohorts: List of cohort names (e.g., ['baseline', 'structural', 'full'])
            num_trials: Optional override for number of trials per task
            enable_mlflow: Whether to enable MLflow tracking
            mlflow_tracking_uri: Optional MLflow tracking URI

        Returns:
            Summary dict with cross-cohort comparison
        """
        # Create output directory structure
        self.base_output_dir.mkdir(parents=True, exist_ok=True)

        # Store results by cohort
        cohort_results = {}

        for cohort_name in cohorts:
            print(f"\n{'=' * 60}")
            print(f"Running cohort: {cohort_name}")
            print(f"{'=' * 60}\n")

            # Create ablation config
            try:
                ablation_config = AblationConfig.from_preset(cohort_name)
            except ValueError as e:
                print(f"Error: {e}")
                continue

            # Create cohort output directory
            cohort_dir = self.base_output_dir / cohort_name
            cohort_dir.mkdir(exist_ok=True)

            # Configure runner
            runner_config = {
                'use_dspy': True,  # Always use DSPy for matrix runs
                'ablation_config': ablation_config,
                'enable_mlflow': enable_mlflow,
                'mlflow_experiment': f"Matrix-{cohort_name}",
                'mlflow_tracking_uri': mlflow_tracking_uri
            }
            runner = TaskRunner(config=runner_config)

            # Run tasks
            cohort_task_results = []
            for task_path in task_paths:
                tasks_dir = Path(__file__).parent.parent / 'tasks'
                print(f"  Running: {task_path.relative_to(tasks_dir)}")

                try:
                    result = runner.run_task(task_path, num_trials=num_trials)
                    cohort_task_results.append(result)

                    # Save result
                    save_result(result, cohort_dir)

                    # Print summary
                    print(f"    pass@{result.total_trials}: {result.pass_at_k:.1%}")
                    print(f"    Avg iterations: {result.avg_iterations:.1f}")

                except Exception as e:
                    print(f"    ERROR: {e}")

            cohort_results[cohort_name] = cohort_task_results

        # Generate cross-cohort comparison
        summary = self._generate_matrix_summary(cohort_results)

        # Save summary
        summary_path = self.base_output_dir / 'matrix_summary.json'
        with open(summary_path, 'w') as f:
            json.dump(summary, f, indent=2)

        print(f"\n{'=' * 60}")
        print("Matrix Summary")
        print(f"{'=' * 60}")
        print(f"Saved to: {summary_path}")

        return summary

    def _generate_matrix_summary(self, cohort_results: dict[str, list[EvalResult]]) -> dict:
        """Generate cross-cohort comparison summary.

        Args:
            cohort_results: Dict mapping cohort names to list of EvalResults

        Returns:
            Summary dict with comparison metrics
        """
        summary = {
            'generated_at': datetime.utcnow().isoformat() + 'Z',
            'cohorts': list(cohort_results.keys()),
            'task_count': len(next(iter(cohort_results.values()))) if cohort_results else 0,
            'by_cohort': {},
            'by_task': {},
            'improvements': []
        }

        # Aggregate by cohort
        for cohort_name, results in cohort_results.items():
            if not results:
                continue

            total_trials = sum(r.total_trials for r in results)
            total_passed = sum(r.passed_trials for r in results)
            avg_pass_rate = total_passed / total_trials if total_trials > 0 else 0
            avg_iterations = sum(r.avg_iterations for r in results) / len(results)
            avg_groundedness = sum(r.avg_groundedness for r in results) / len(results)

            summary['by_cohort'][cohort_name] = {
                'task_count': len(results),
                'total_trials': total_trials,
                'total_passed': total_passed,
                'avg_pass_rate': avg_pass_rate,
                'avg_iterations': avg_iterations,
                'avg_groundedness': avg_groundedness
            }

        # Cross-cohort comparison by task
        if cohort_results:
            # Get task list from first cohort
            first_cohort_results = next(iter(cohort_results.values()))
            for idx, result in enumerate(first_cohort_results):
                task_id = result.task_id

                task_comparison = {
                    'task_id': task_id,
                    'task_query': result.task_query,
                    'by_cohort': {}
                }

                # Compare across cohorts
                for cohort_name, results in cohort_results.items():
                    if idx < len(results):
                        r = results[idx]
                        task_comparison['by_cohort'][cohort_name] = {
                            'pass_at_k': r.pass_at_k,
                            'pass_power_k': r.pass_power_k,
                            'avg_iterations': r.avg_iterations,
                            'passed_trials': r.passed_trials,
                            'total_trials': r.total_trials
                        }

                summary['by_task'][task_id] = task_comparison

        # Identify improvements (full vs baseline)
        if 'baseline' in summary['by_cohort'] and 'full' in summary['by_cohort']:
            baseline_rate = summary['by_cohort']['baseline']['avg_pass_rate']
            full_rate = summary['by_cohort']['full']['avg_pass_rate']
            improvement = full_rate - baseline_rate

            summary['improvements'].append({
                'comparison': 'full vs baseline',
                'baseline_pass_rate': baseline_rate,
                'full_pass_rate': full_rate,
                'absolute_improvement': improvement,
                'relative_improvement': improvement / baseline_rate if baseline_rate > 0 else 0
            })

        return summary
