#!/usr/bin/env python3
"""
Run a focused validation of v2 tools on high-failure tasks.

This runs a small subset of trajectories with both v1 and v2 tools
to validate the fixes before committing to a full S3 re-run.

Estimated time: ~10-15 minutes (vs 3 hours for full S3)
"""

import sys
import json
from pathlib import Path
from datetime import datetime

sys.path.insert(0, '/Users/cvardema/dev/git/LA3D/rlm')

from experiments.reasoningbank.prototype.run.rlm_uniprot import run_uniprot
from experiments.reasoningbank.prototype.ctx.builder import Cfg, Layer

# Configuration
ONTOLOGY_PATH = "/Users/cvardema/dev/git/LA3D/rlm/ontology/uniprot"
OUTPUT_DIR = Path(__file__).parent / "results" / "v2_validation"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

# High-failure tasks from S3 analysis
TASKS = {
    '2_bacteria_taxa': {
        'question': 'Select all bacterial taxa and their scientific names',
        's3_failures': 40,
    },
    '121_proteins_diseases': {
        'question': 'List proteins and the diseases they are linked to',
        's3_failures': 51,
    },
}

# Default context config
CFG = Cfg(
    l0=Layer(on=True, budget=600),
    l1=Layer(on=True, budget=400),
    l2=Layer(on=False, budget=600),
    l3=Layer(on=False, budget=200),
    guide_text=""
)


def run_comparison(task_name: str, question: str, rollouts: int = 2):
    """Run a task with both v1 and v2 tools, compare results."""
    results = {
        'task': task_name,
        'question': question,
        'v1_results': [],
        'v2_results': [],
    }

    for rollout_id in range(1, rollouts + 1):
        print(f"\n{'='*60}")
        print(f"Task: {task_name}, Rollout: {rollout_id}")
        print(f"{'='*60}")

        # Run with V1 tools
        print(f"\n--- V1 Tools ---")
        log_path_v1 = OUTPUT_DIR / f"{task_name}_v1_rollout{rollout_id}.jsonl"
        try:
            r1 = run_uniprot(
                task=question,
                ont_path=ONTOLOGY_PATH,
                cfg=CFG,
                max_iters=8,
                max_calls=20,
                temperature=0.3,  # Some stochasticity
                verbose=True,
                log_path=str(log_path_v1),
                use_local_interpreter=True,
                use_v2_tools=False,  # V1 tools
                rollout_id=rollout_id,
            )
            v1_result = {
                'converged': r1.converged,
                'iters': r1.iters,
                'has_sparql': r1.sparql is not None,
                'answer_len': len(r1.answer) if r1.answer else 0,
                'tool_failures': count_tool_failures(log_path_v1),
            }
        except Exception as e:
            v1_result = {'error': str(e)}
        results['v1_results'].append(v1_result)

        # Run with V2 tools
        print(f"\n--- V2 Tools ---")
        log_path_v2 = OUTPUT_DIR / f"{task_name}_v2_rollout{rollout_id}.jsonl"
        try:
            r2 = run_uniprot(
                task=question,
                ont_path=ONTOLOGY_PATH,
                cfg=CFG,
                max_iters=8,
                max_calls=20,
                temperature=0.3,
                verbose=True,
                log_path=str(log_path_v2),
                use_local_interpreter=True,
                use_v2_tools=True,  # V2 tools
                rollout_id=rollout_id,
            )
            v2_result = {
                'converged': r2.converged,
                'iters': r2.iters,
                'has_sparql': r2.sparql is not None,
                'answer_len': len(r2.answer) if r2.answer else 0,
                'tool_failures': count_tool_failures(log_path_v2),
            }
        except Exception as e:
            v2_result = {'error': str(e)}
        results['v2_results'].append(v2_result)

    return results


def count_tool_failures(log_path: Path) -> dict:
    """Count tool failures from a trajectory log."""
    failures = {'total': 0, 'by_type': {}}
    if not log_path.exists():
        return failures

    with open(log_path) as f:
        for line in f:
            event = json.loads(line)
            if event.get('event_type') == 'tool_result':
                error = event.get('data', {}).get('error')
                if error:
                    failures['total'] += 1
                    # Categorize
                    if 'timeout' in error.lower():
                        err_type = 'timeout'
                    elif 'argument' in error.lower():
                        err_type = 'argument_mismatch'
                    elif 'type' in error.lower():
                        err_type = 'type_error'
                    else:
                        err_type = 'other'
                    failures['by_type'][err_type] = failures['by_type'].get(err_type, 0) + 1

    return failures


def print_comparison(all_results: list):
    """Print comparison summary."""
    print("\n" + "=" * 70)
    print("VALIDATION SUMMARY")
    print("=" * 70)

    total_v1_failures = 0
    total_v2_failures = 0

    for task_results in all_results:
        print(f"\n{task_results['task']}:")
        print(f"  Question: {task_results['question'][:50]}...")

        v1_failures = sum(r.get('tool_failures', {}).get('total', 0) for r in task_results['v1_results'])
        v2_failures = sum(r.get('tool_failures', {}).get('total', 0) for r in task_results['v2_results'])
        total_v1_failures += v1_failures
        total_v2_failures += v2_failures

        v1_converged = sum(1 for r in task_results['v1_results'] if r.get('converged'))
        v2_converged = sum(1 for r in task_results['v2_results'] if r.get('converged'))

        print(f"  V1: {v1_failures} tool failures, {v1_converged}/{len(task_results['v1_results'])} converged")
        print(f"  V2: {v2_failures} tool failures, {v2_converged}/{len(task_results['v2_results'])} converged")

        if v2_failures < v1_failures:
            improvement = ((v1_failures - v2_failures) / v1_failures * 100) if v1_failures > 0 else 0
            print(f"  ✅ V2 reduces failures by {improvement:.0f}%")

    print("\n" + "-" * 70)
    print(f"TOTAL V1 failures: {total_v1_failures}")
    print(f"TOTAL V2 failures: {total_v2_failures}")
    if total_v1_failures > 0:
        reduction = ((total_v1_failures - total_v2_failures) / total_v1_failures * 100)
        print(f"Reduction: {reduction:.0f}%")
    print("=" * 70)


def main():
    print("=" * 70)
    print("V2 TOOL VALIDATION - Subset Test")
    print("=" * 70)
    print(f"Started: {datetime.now().isoformat()}")
    print(f"Tasks: {list(TASKS.keys())}")
    print(f"Rollouts per task: 2")
    print(f"Output dir: {OUTPUT_DIR}")

    all_results = []

    for task_name, task_info in TASKS.items():
        results = run_comparison(
            task_name=task_name,
            question=task_info['question'],
            rollouts=2,  # Quick test: 2 rollouts each
        )
        all_results.append(results)

        # Save intermediate results
        with open(OUTPUT_DIR / f"{task_name}_comparison.json", 'w') as f:
            json.dump(results, f, indent=2)

    # Print summary
    print_comparison(all_results)

    # Save full results
    with open(OUTPUT_DIR / "validation_summary.json", 'w') as f:
        json.dump(all_results, f, indent=2)

    print(f"\nResults saved to: {OUTPUT_DIR}")
    print(f"Finished: {datetime.now().isoformat()}")


if __name__ == "__main__":
    main()
