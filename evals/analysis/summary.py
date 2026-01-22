"""Summary generation for eval results - optimized for LLM analysis."""

import json
from pathlib import Path
from collections import defaultdict
from typing import Optional


def generate_summary(results_dir: str, format: str = 'json') -> dict:
    """Generate structured summary of eval results for Claude Code analysis.

    Args:
        results_dir: Directory containing result JSON files
        format: Output format ('json' or 'markdown')

    Returns:
        Summary dict with aggregated metrics and recommendations
    """
    results_dir = Path(results_dir)

    if not results_dir.exists():
        return {'error': f'Results directory not found: {results_dir}'}

    # Load all result files
    result_files = list(results_dir.glob('*.json'))

    if not result_files:
        return {'error': 'No result files found'}

    results = []
    for result_file in result_files:
        try:
            with open(result_file) as f:
                data = json.load(f)
                results.append(data)
        except Exception as e:
            print(f"Warning: Could not read {result_file}: {e}")

    # Aggregate metrics
    summary = _aggregate_metrics(results)

    # Add recommendations
    summary['recommendations'] = _generate_recommendations(summary)

    return summary


def _aggregate_metrics(results: list[dict]) -> dict:
    """Aggregate metrics across all results."""
    total_tasks = len(results)
    total_trials = sum(r.get('total_trials', 0) for r in results)
    total_passed = sum(r.get('passed_trials', 0) for r in results)
    overall_pass_rate = total_passed / total_trials if total_trials > 0 else 0

    # Aggregate by category
    by_category = defaultdict(lambda: {'tasks': 0, 'trials': 0, 'passed': 0, 'iterations': []})

    for r in results:
        task_id = r.get('task_id', '')
        category = task_id.split('_')[0] if '_' in task_id else task_id.split('/')[0]

        by_category[category]['tasks'] += 1
        by_category[category]['trials'] += r.get('total_trials', 0)
        by_category[category]['passed'] += r.get('passed_trials', 0)
        by_category[category]['iterations'].append(r.get('avg_iterations', 0))

    # Calculate category pass rates
    for category, stats in by_category.items():
        stats['pass_rate'] = stats['passed'] / stats['trials'] if stats['trials'] > 0 else 0
        stats['avg_iterations'] = sum(stats['iterations']) / len(stats['iterations']) if stats['iterations'] else 0
        del stats['iterations']  # Remove raw list

    # Aggregate by reasoning level (if present)
    by_reasoning_level = defaultdict(lambda: {'tasks': 0, 'trials': 0, 'passed': 0})

    for r in results:
        # Check trial results for reasoning_level (if captured)
        trial_results = r.get('trial_results', [])
        if trial_results and isinstance(trial_results, list):
            # Try to infer from task_id pattern
            task_id = r.get('task_id', '')
            if 'L3_' in task_id or 'L4_' in task_id or 'L5_' in task_id or 'L6_' in task_id:
                level = task_id.split('_')[-1] if '_' in task_id else 'unknown'
                by_reasoning_level[level]['tasks'] += 1
                by_reasoning_level[level]['trials'] += r.get('total_trials', 0)
                by_reasoning_level[level]['passed'] += r.get('passed_trials', 0)

    for level, stats in by_reasoning_level.items():
        stats['pass_rate'] = stats['passed'] / stats['trials'] if stats['trials'] > 0 else 0

    # Identify failing tasks
    failing_tasks = []
    for r in results:
        if r.get('passed_trials', 0) < r.get('total_trials', 1):
            failing_tasks.append({
                'task_id': r.get('task_id'),
                'pass_rate': r.get('pass_at_k', 0),
                'avg_iterations': r.get('avg_iterations', 0),
                'query': r.get('task_query', '')[:100]  # Truncate
            })

    # Sort failing tasks by pass rate
    failing_tasks.sort(key=lambda x: x['pass_rate'])

    return {
        'total_tasks': total_tasks,
        'total_trials': total_trials,
        'total_passed': total_passed,
        'overall_pass_rate': overall_pass_rate,
        'by_category': dict(by_category),
        'by_reasoning_level': dict(by_reasoning_level) if by_reasoning_level else None,
        'failing_tasks': failing_tasks[:10],  # Top 10 worst
        'worst_categories': _identify_worst_categories(by_category)
    }


def _identify_worst_categories(by_category: dict) -> list[dict]:
    """Identify categories with lowest pass rates."""
    categories = []
    for name, stats in by_category.items():
        categories.append({
            'category': name,
            'pass_rate': stats['pass_rate'],
            'task_count': stats['tasks']
        })

    # Sort by pass rate
    categories.sort(key=lambda x: x['pass_rate'])
    return categories[:5]  # Bottom 5


def _generate_recommendations(summary: dict) -> list[str]:
    """Generate actionable recommendations based on summary.

    Args:
        summary: Aggregated summary dict

    Returns:
        List of recommendation strings
    """
    recommendations = []

    # Check overall pass rate
    pass_rate = summary['overall_pass_rate']
    if pass_rate < 0.5:
        recommendations.append(
            f"Overall pass rate is low ({pass_rate:.1%}). Consider: "
            f"(1) improving sense card affordances, "
            f"(2) adding SPARQL templates, "
            f"(3) enabling ReasoningBank memory"
        )

    # Check worst categories
    worst_categories = summary.get('worst_categories', [])
    if worst_categories:
        worst = worst_categories[0]
        if worst['pass_rate'] < 0.3:
            recommendations.append(
                f"Category '{worst['category']}' has very low pass rate ({worst['pass_rate']:.1%}). "
                f"Investigate: task complexity, reasoning requirements, or missing tools."
            )

    # Check reasoning level failures (if available)
    by_reasoning = summary.get('by_reasoning_level')
    if by_reasoning:
        for level, stats in by_reasoning.items():
            if stats['pass_rate'] < 0.2:
                recommendations.append(
                    f"Reasoning level '{level}' failures suggest capability gap. "
                    f"Consider: new tool for this reasoning type, or task redesign."
                )

    # Check iteration counts
    high_iteration_categories = []
    for category, stats in summary['by_category'].items():
        if stats['avg_iterations'] > 12:
            high_iteration_categories.append(f"{category} ({stats['avg_iterations']:.1f} iters)")

    if high_iteration_categories:
        recommendations.append(
            f"High iteration counts in: {', '.join(high_iteration_categories)}. "
            f"Consider: more direct affordances or SPARQL templates."
        )

    if not recommendations:
        recommendations.append("Performance looks good! Consider ablation experiments to identify critical features.")

    return recommendations


def generate_cohort_comparison(matrix_summary_path: str) -> dict:
    """Generate comparison analysis from matrix run results.

    Args:
        matrix_summary_path: Path to matrix_summary.json file

    Returns:
        Comparison dict with feature impact analysis
    """
    try:
        with open(matrix_summary_path) as f:
            matrix_summary = json.load(f)
    except Exception as e:
        return {'error': f'Could not load matrix summary: {e}'}

    cohorts = matrix_summary.get('cohorts', [])
    by_cohort = matrix_summary.get('by_cohort', {})
    improvements = matrix_summary.get('improvements', [])

    # Build comparison
    comparison = {
        'cohorts_evaluated': cohorts,
        'performance_ranking': [],
        'feature_impact': {},
        'recommendations': []
    }

    # Rank cohorts by pass rate
    for cohort, stats in by_cohort.items():
        comparison['performance_ranking'].append({
            'cohort': cohort,
            'pass_rate': stats['avg_pass_rate'],
            'avg_iterations': stats['avg_iterations']
        })

    comparison['performance_ranking'].sort(key=lambda x: x['pass_rate'], reverse=True)

    # Analyze feature impact
    if 'baseline' in by_cohort and 'full' in by_cohort:
        baseline_rate = by_cohort['baseline']['avg_pass_rate']
        full_rate = by_cohort['full']['avg_pass_rate']

        comparison['feature_impact']['all_features'] = {
            'baseline_rate': baseline_rate,
            'full_rate': full_rate,
            'absolute_improvement': full_rate - baseline_rate,
            'relative_improvement': (full_rate - baseline_rate) / baseline_rate if baseline_rate > 0 else 0
        }

        # Generate recommendations
        if full_rate - baseline_rate > 0.2:
            comparison['recommendations'].append(
                "Significant improvement with full features (+{:.1%}). "
                "Sense card affordances are highly valuable.".format(full_rate - baseline_rate)
            )
        elif full_rate - baseline_rate < 0.05:
            comparison['recommendations'].append(
                "Minimal improvement with full features (+{:.1%}). "
                "Consider: (1) affordances may not match task needs, "
                "(2) agent may not be using provided information effectively.".format(full_rate - baseline_rate)
            )

    # Check for intermediate cohorts
    if 'minimal' in by_cohort and 'structural' in by_cohort:
        minimal_rate = by_cohort['minimal']['avg_pass_rate']
        structural_rate = by_cohort['structural']['avg_pass_rate']

        if structural_rate - minimal_rate > 0.1:
            comparison['recommendations'].append(
                "Structural features (hierarchy, domain/range) provide significant value (+{:.1%}).".format(
                    structural_rate - minimal_rate
                )
            )

    return comparison
