#!/usr/bin/env python3
"""Run meta-analysis on accumulated trial results.

Loads recent trial results, extracts cross-trajectory patterns,
and stores them as meta-analysis memories in ReasoningBank.

Usage:
    python scripts/run_meta_analysis.py [--db-path evals/memory.db] [--result-file <path>]
"""

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
import sys

# Add parent to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from rlm_runtime.memory import SQLiteMemoryBackend
from rlm_runtime.memory.extraction import extract_meta_patterns, judge_trajectory_dspy


def load_trial_results(result_file: str) -> list[dict]:
    """Load trial results from JSON file.

    Returns:
        List of trial dicts with structure needed for meta-analysis
    """
    with open(result_file, 'r') as f:
        data = json.load(f)

    # Extract task query
    task_query = data.get('task_query', '')

    # Extract trials (key is 'trial_results' not 'trials')
    trials = []
    for trial in data.get('trial_results', []):
        # Transform transcript into trajectory format
        # Transcript has: {iteration, response, code_blocks}
        # code_blocks is list of {code: str, result: {stdout, stderr}}
        # Trajectory needs: {code, output}
        transcript = trial.get('transcript', [])
        trajectory = []
        for entry in transcript:
            code_blocks = entry.get('code_blocks', [])
            if code_blocks:
                # Each code_block is a dict with 'code' and 'result' fields
                for block in code_blocks:
                    code = block.get('code', '')
                    result = block.get('result', {})
                    output = result.get('stdout', '') or result.get('stderr', '')

                    trajectory.append({
                        "code": code,
                        "output": output[:200] if output else ""  # Limit output length
                    })

        # Build judgment from grader results
        grader_results = trial.get('grader_results', {})
        passed = trial.get('passed', False)

        # Create judgment-like dict
        judgment = {
            "is_success": passed,
            "reason": f"Grader results: {grader_results}" if grader_results else "Unknown",
            "confidence": "high" if passed else "medium",
            "missing": [] if passed else ["grader details"]
        }

        trial_dict = {
            "task": task_query,
            "answer": trial.get('answer', ''),
            "trajectory": trajectory,
            "judgment": judgment,
            "iterations": trial.get('iterations', len(trajectory)),
            "evidence": trial.get('evidence', {}),
            "ontology_name": "uniprot"  # Infer from task
        }

        trials.append(trial_dict)

    return trials


def main():
    parser = argparse.ArgumentParser(
        description="Run meta-analysis on trial results"
    )
    parser.add_argument(
        '--db-path',
        default='evals/memory.db',
        help='Path to memory database (default: evals/memory.db)'
    )
    parser.add_argument(
        '--result-file',
        required=True,
        help='Path to trial results JSON file'
    )
    parser.add_argument(
        '--min-trajectories',
        type=int,
        default=3,
        help='Minimum trajectories for meta-analysis (default: 3)'
    )
    parser.add_argument(
        '--dry-run',
        action='store_true',
        help='Show what would be extracted without modifying database'
    )

    args = parser.parse_args()

    # Load trial results
    print(f"Loading trial results from {args.result_file}...")
    try:
        trials = load_trial_results(args.result_file)
    except FileNotFoundError:
        print(f"ERROR: Result file not found: {args.result_file}")
        return 1
    except Exception as e:
        print(f"ERROR loading results: {e}")
        return 1

    print(f"Loaded {len(trials)} trials")

    if len(trials) < args.min_trajectories:
        print(f"ERROR: Need at least {args.min_trajectories} trials for meta-analysis, got {len(trials)}")
        return 1

    # Display trial summary
    print("\nTrial Summary:")
    for i, t in enumerate(trials):
        outcome = "PASS" if t["judgment"]["is_success"] else "FAIL"
        print(f"  Trial {i}: {t['iterations']} iterations, {outcome}")

    # Run meta-analysis
    print(f"\nRunning meta-analysis on {len(trials)} trajectories...")
    try:
        meta_patterns = extract_meta_patterns(
            trials,
            min_trajectories=args.min_trajectories
        )
    except Exception as e:
        print(f"ERROR during meta-analysis: {e}")
        import traceback
        traceback.print_exc()
        return 1

    print(f"\nExtracted {len(meta_patterns)} meta-patterns:")
    for i, pattern in enumerate(meta_patterns, 1):
        print(f"\n{i}. {pattern.title}")
        print(f"   {pattern.description}")
        print(f"   Tags: {', '.join(pattern.tags)}")
        print(f"   Content preview: {pattern.content[:150]}...")

    if args.dry_run:
        print("\n[DRY RUN] Would add these to database, but not actually modifying.")
        return 0

    # Connect to database
    backend = SQLiteMemoryBackend(args.db_path)

    # Add meta-patterns
    print(f"\nAdding to {args.db_path}...")
    added = 0
    skipped = 0

    for pattern in meta_patterns:
        if backend.has_memory(pattern.memory_id):
            print(f"  SKIP: {pattern.title} (already exists)")
            skipped += 1
        else:
            backend.add_memory(pattern)
            print(f"  ADD:  {pattern.title}")
            added += 1

    print(f"\nSummary: Added {added}, Skipped {skipped}")

    # Show stats
    all_memories = backend.get_all_memories()
    by_source = {}
    for m in all_memories:
        by_source[m.source_type] = by_source.get(m.source_type, 0) + 1

    print(f"\nTotal memories in database: {len(all_memories)}")
    for source, count in sorted(by_source.items()):
        print(f"  {source}: {count}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
