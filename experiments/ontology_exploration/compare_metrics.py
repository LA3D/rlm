#!/usr/bin/env python3
"""Compare metrics across ontology exploration experiments.

Reads all e*_metrics.json files and displays side-by-side comparison.

Usage:
    python experiments/ontology_exploration/compare_metrics.py
"""

import json
import sys
from pathlib import Path
from typing import List, Dict

project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))


def load_metrics() -> List[Dict]:
    """Load all experiment metrics JSON files."""
    metrics_dir = Path(__file__).parent
    metrics_files = sorted(metrics_dir.glob("e*_metrics.json"))

    metrics = []
    for path in metrics_files:
        with open(path) as f:
            data = json.load(f)
            data['_file'] = path.name
            metrics.append(data)

    return metrics


def format_number(n, decimals=0):
    """Format number with commas."""
    if decimals == 0:
        return f"{int(n):,}"
    else:
        return f"{n:,.{decimals}f}"


def format_cost(cost):
    """Format cost in dollars."""
    return f"${cost:.4f}"


def format_delta(current, baseline, format_fn=None, show_percent=True):
    """Format delta vs baseline."""
    if baseline == 0:
        return "N/A"

    delta = current - baseline
    pct = (delta / baseline) * 100

    if format_fn:
        delta_str = format_fn(abs(delta))
    else:
        delta_str = f"{abs(delta)}"

    sign = "+" if delta > 0 else "-" if delta < 0 else "="

    if show_percent:
        return f"{sign}{delta_str} ({pct:+.1f}%)"
    else:
        return f"{sign}{delta_str}"


def print_comparison(metrics: List[Dict]):
    """Print side-by-side comparison table."""
    if not metrics:
        print("No metrics found.")
        return

    print("\n" + "=" * 100)
    print("EXPERIMENT METRICS COMPARISON")
    print("=" * 100)
    print()

    # Header
    experiments = [m['experiment'] for m in metrics]
    print(f"{'Metric':<30}", end="")
    for exp in experiments:
        print(f"{exp:<20}", end="")
    print()
    print("-" * 100)

    # Ontology
    print(f"{'Ontology':<30}", end="")
    for m in metrics:
        print(f"{m.get('ontology', 'N/A'):<20}", end="")
    print()

    print(f"{'Ontology Size (triples)':<30}", end="")
    for m in metrics:
        size = m.get('ontology_size', 0)
        print(f"{format_number(size):<20}", end="")
    print()

    print()

    # Performance
    print("--- Performance ---")
    print(f"{'Elapsed Time (seconds)':<30}", end="")
    baseline_time = metrics[0].get('elapsed_seconds', 0)
    for i, m in enumerate(metrics):
        time = m.get('elapsed_seconds', 0)
        if i == 0:
            print(f"{time:.1f}s{'':<13}", end="")
        else:
            delta = format_delta(time, baseline_time, lambda x: f"{x:.1f}s")
            print(f"{time:.1f}s {delta:<8}", end="")
    print()

    print(f"{'LM Calls':<30}", end="")
    baseline_calls = metrics[0].get('lm_calls', 0)
    for i, m in enumerate(metrics):
        calls = m.get('lm_calls', 0)
        if i == 0:
            print(f"{calls:<20}", end="")
        else:
            delta = format_delta(calls, baseline_calls, format_number, show_percent=True)
            print(f"{calls} {delta:<12}", end="")
    print()

    print()

    # Tokens
    print("--- Token Usage ---")
    print(f"{'Input Tokens':<30}", end="")
    baseline_input = metrics[0].get('input_tokens', 0)
    for i, m in enumerate(metrics):
        tokens = m.get('input_tokens', 0)
        if i == 0:
            print(f"{format_number(tokens):<20}", end="")
        else:
            delta = format_delta(tokens, baseline_input, format_number, show_percent=True)
            print(f"{format_number(tokens)} {delta:<8}", end="")
    print()

    print(f"{'Output Tokens':<30}", end="")
    baseline_output = metrics[0].get('output_tokens', 0)
    for i, m in enumerate(metrics):
        tokens = m.get('output_tokens', 0)
        if i == 0:
            print(f"{format_number(tokens):<20}", end="")
        else:
            delta = format_delta(tokens, baseline_output, format_number, show_percent=True)
            print(f"{format_number(tokens)} {delta:<8}", end="")
    print()

    print(f"{'Total Tokens':<30}", end="")
    baseline_total = metrics[0].get('total_tokens', 0)
    for i, m in enumerate(metrics):
        tokens = m.get('total_tokens', 0)
        if i == 0:
            print(f"{format_number(tokens):<20}", end="")
        else:
            delta = format_delta(tokens, baseline_total, format_number, show_percent=True)
            print(f"{format_number(tokens)} {delta:<8}", end="")
    print()

    print()

    # Cost
    print("--- Cost ---")
    print(f"{'Estimated Cost (USD)':<30}", end="")
    baseline_cost = metrics[0].get('estimated_cost_usd', 0)
    for i, m in enumerate(metrics):
        cost = m.get('estimated_cost_usd', 0)
        if i == 0:
            print(f"{format_cost(cost):<20}", end="")
        else:
            delta = format_delta(cost, baseline_cost, format_cost, show_percent=True)
            print(f"{format_cost(cost)} {delta:<8}", end="")
    print()

    print()

    # Output Quality
    print("--- Output Quality ---")
    print(f"{'Variables Created':<30}", end="")
    for m in metrics:
        count = m.get('variables_created', 0)
        print(f"{count:<20}", end="")
    print()

    print(f"{'Exploration Notes (chars)':<30}", end="")
    for m in metrics:
        length = m.get('exploration_notes_length', 0)
        print(f"{format_number(length):<20}", end="")
    print()

    print(f"{'Domain Summary (chars)':<30}", end="")
    for m in metrics:
        length = m.get('domain_summary_length', 0)
        print(f"{format_number(length):<20}", end="")
    print()

    # Additional experiment-specific metrics
    if any('llm_query_calls' in m for m in metrics):
        print()
        print("--- llm_query Usage ---")
        print(f"{'llm_query Calls':<30}", end="")
        for m in metrics:
            calls = m.get('llm_query_calls', 0)
            print(f"{calls:<20}", end="")
        print()

    if any('guide_quality_score' in m for m in metrics):
        print()
        print("--- Guide Quality ---")
        print(f"{'Guide Quality Score':<30}", end="")
        for m in metrics:
            score = m.get('guide_quality_score', 0)
            print(f"{score:.2f}<20", end="")
        print()

    print()
    print("=" * 100)
    print()


def print_summary(metrics: List[Dict]):
    """Print summary findings."""
    if not metrics or len(metrics) < 2:
        return

    print("SUMMARY")
    print("-" * 100)
    print()

    baseline = metrics[0]
    latest = metrics[-1]

    # Cost trend
    cost_change = latest['estimated_cost_usd'] - baseline['estimated_cost_usd']
    cost_pct = (cost_change / baseline['estimated_cost_usd']) * 100 if baseline['estimated_cost_usd'] > 0 else 0

    print(f"Cost trend: {baseline['experiment']} → {latest['experiment']}")
    print(f"  Baseline: {format_cost(baseline['estimated_cost_usd'])}")
    print(f"  Latest:   {format_cost(latest['estimated_cost_usd'])} ({cost_pct:+.1f}%)")
    print()

    # Token efficiency
    if baseline['total_tokens'] > 0 and latest['total_tokens'] > 0:
        baseline_eff = baseline['estimated_cost_usd'] / baseline['total_tokens'] * 1000
        latest_eff = latest['estimated_cost_usd'] / latest['total_tokens'] * 1000
        print(f"Cost per 1K tokens:")
        print(f"  Baseline: ${baseline_eff:.6f}")
        print(f"  Latest:   ${latest_eff:.6f}")
        print()

    # Output quality trend
    baseline_vars = baseline.get('variables_created', 0)
    latest_vars = latest.get('variables_created', 0)
    print(f"Variables created: {baseline_vars} → {latest_vars}")

    baseline_notes = baseline.get('exploration_notes_length', 0)
    latest_notes = latest.get('exploration_notes_length', 0)
    print(f"Exploration notes: {format_number(baseline_notes)} chars → {format_number(latest_notes)} chars")
    print()


def main():
    """Load and compare all experiment metrics."""
    metrics = load_metrics()

    if not metrics:
        print("No metrics files found in experiments/ontology_exploration/")
        print("Run experiments first to generate e*_metrics.json files.")
        return 1

    print(f"Found {len(metrics)} experiment(s) with metrics:")
    for m in metrics:
        print(f"  - {m['_file']}: {m['experiment']}")

    print_comparison(metrics)
    print_summary(metrics)

    return 0


if __name__ == "__main__":
    sys.exit(main())
