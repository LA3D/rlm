#!/usr/bin/env python3
"""Migrate legacy flat results/ directory to experiments/ structure.

This script helps backfill E001 and E002 by organizing existing results
into the new experiment directory structure.

Usage:
    python evals/scripts/migrate_to_experiments.py
"""

import json
import shutil
from pathlib import Path
from datetime import datetime

# Cutoff timestamp: Think-Act-Verify-Reflect commit at 2026-01-22 21:52 UTC
CUTOFF_TIMESTAMP = "2026-01-22T21-52"

# Git commits
E001_COMMIT = "03d298b4"  # Before reasoning fields
E002_COMMIT = "9efd8204"  # Think-Act-Verify-Reflect

def parse_timestamp(filename: str) -> str:
    """Extract timestamp from result filename."""
    # Format: task_id_{timestamp}Z.json
    parts = filename.split('_')
    # Last part is {timestamp}Z.json
    timestamp = parts[-1].replace('Z.json', '').replace('.json', '')
    return timestamp

def classify_result(result_path: Path) -> dict:
    """Classify a result file into experiment/cohort."""
    timestamp = parse_timestamp(result_path.name)

    with open(result_path) as f:
        data = json.load(f)

    task_id = data.get('task_id', '')

    # Check if has thinking fields (indicates E002 Rung 1 with full implementation)
    has_thinking = False
    if 'trial_results' in data and data['trial_results']:
        trial = data['trial_results'][0]
        has_thinking = 'thinking' in trial and bool(trial.get('thinking'))

    # Classify
    if timestamp < CUTOFF_TIMESTAMP:
        experiment = "E001_baseline_before_reasoning"
        cohort = "baseline"
        git_commit = E001_COMMIT
    elif has_thinking:
        experiment = "E002_rung1_think_act_verify_reflect"
        cohort = "rung1_reasoning_fields"
        git_commit = E002_COMMIT
    else:
        experiment = "E002_rung1_think_act_verify_reflect"
        cohort = "incomplete"  # Signature changed but task_runner didn't capture fields
        git_commit = E002_COMMIT

    return {
        'experiment': experiment,
        'cohort': cohort,
        'git_commit': git_commit,
        'task_id': task_id,
        'timestamp': timestamp,
        'has_thinking': has_thinking,
        'data': data
    }

def migrate():
    """Migrate all results to experiment structure."""
    results_dir = Path('evals/results')
    experiments_dir = Path('evals/experiments')

    if not results_dir.exists():
        print("No results/ directory found")
        return

    # Find all result files
    result_files = list(results_dir.glob('*.json'))
    print(f"Found {len(result_files)} result files")

    # Classify all results
    classified = {}
    for result_path in result_files:
        info = classify_result(result_path)
        key = (info['experiment'], info['cohort'])

        if key not in classified:
            classified[key] = []
        classified[key].append({
            'source': result_path,
            'info': info
        })

    # Print classification summary
    print("\nClassification:")
    for (experiment, cohort), results in sorted(classified.items()):
        print(f"  {experiment}/{cohort}: {len(results)} files")

    # Migrate files
    print("\nMigrating...")
    for (experiment, cohort), results in sorted(classified.items()):
        dest_dir = experiments_dir / experiment / 'cohorts' / cohort / 'results'
        dest_dir.mkdir(parents=True, exist_ok=True)

        for item in results:
            source = item['source']
            dest = dest_dir / source.name

            # Copy file
            shutil.copy2(source, dest)
            # Use string formatting instead of relative_to
            print(f"  ✓ {source.name} → {dest}")

    print("\n✅ Migration complete!")
    print(f"\nNext steps:")
    print("1. Review migrated files in experiments/")
    print("2. Create experiment.yaml for E001 and E002")
    print("3. Run aggregation to create summary.json for each cohort")
    print("4. Write ANALYSIS.md for each experiment")

if __name__ == '__main__':
    migrate()
