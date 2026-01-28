#!/usr/bin/env python3
"""Small E-RC-001 test to verify verification feedback appears in trajectories.

Runs just 2 tasks with minimal iterations to save tokens.
"""

import os
import sys
import json
from pathlib import Path
from datetime import datetime
from typing import Optional
from dataclasses import dataclass, asdict

# Add project root to path
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

# Check for API key
if not os.environ.get("ANTHROPIC_API_KEY"):
    print("ERROR: Set ANTHROPIC_API_KEY environment variable", file=sys.stderr)
    sys.exit(1)


@dataclass
class TestTask:
    """A test task for the experiment."""
    id: str
    query: str
    expected_level: int
    ontology: str = "uniprot"
    description: Optional[str] = None


@dataclass
class TaskResult:
    """Result from running a task."""
    task_id: str
    condition: str
    converged: bool
    iteration_count: int
    answer: str
    sparql: Optional[str]
    verification_feedback_found: bool  # NEW: Track if feedback appeared
    verification_examples: list  # NEW: Sample feedback lines


# Just 2 simple tasks to minimize tokens
TEST_TASKS = [
    TestTask(
        id="L1-protein-lookup",
        query="What is the Protein class?",
        expected_level=1,
        description="Simple class lookup"
    ),
    TestTask(
        id="L2-property-lookup",
        query="What properties connect proteins to annotations?",
        expected_level=2,
        description="Property relationship query"
    ),
]


def run_task_with_rlm(task: TestTask, verbose: bool = False) -> TaskResult:
    """Run a single task using DSPy RLM with verification enabled.

    Args:
        task: TestTask to run
        verbose: Whether to print verbose output

    Returns:
        TaskResult with execution details
    """
    from rlm_runtime.engine.dspy_rlm import run_dspy_rlm

    ontology_path = project_root / f"ontology/{task.ontology}/core.ttl"
    if not ontology_path.exists():
        raise FileNotFoundError(f"Ontology not found: {ontology_path}")

    print(f"    Running: {task.query}")

    result = run_dspy_rlm(
        task.query,
        ontology_path,
        max_iterations=3,  # Keep short to save tokens
        verbose=verbose,
        memory_backend=None,  # No memory for simplicity
        retrieve_memories=0,
        enable_verification=True,  # CRITICAL: Enable verification
    )

    # Check trajectory for verification feedback
    verification_found = False
    verification_examples = []

    for i, step in enumerate(result.trajectory, 1):
        if not isinstance(step, dict):
            continue

        output = step.get('output', '')
        code = step.get('code', '')

        # Check if this step has SPARQL and verification
        has_sparql = 'sparql_select' in code or 'sparql_query' in code
        has_verification = '## Verification' in output

        if has_verification:
            verification_found = True
            # Extract a few lines as examples
            lines = output.split('\n')
            for j, line in enumerate(lines):
                if '## Verification' in line:
                    # Get next few non-empty lines
                    for k in range(j, min(j+10, len(lines))):
                        if lines[k].strip():
                            verification_examples.append(lines[k].strip())
                            if len(verification_examples) >= 5:
                                break
                    break

        if verbose:
            print(f"      Iteration {i}: SPARQL={has_sparql}, Verification={has_verification}")

    return TaskResult(
        task_id=task.id,
        condition="verification-enabled",
        converged=result.converged,
        iteration_count=result.iteration_count,
        answer=result.answer[:200] + "..." if len(result.answer) > 200 else result.answer,
        sparql=result.sparql,
        verification_feedback_found=verification_found,
        verification_examples=verification_examples[:5],  # Keep first 5 lines
    )


def run_small_test(verbose: bool = False):
    """Run small verification test."""
    print("=" * 70)
    print("SMALL E-RC-001 TEST: Verification Feedback in Trajectories")
    print("=" * 70)
    print(f"\nRunning {len(TEST_TASKS)} tasks with verification enabled")
    print("Max iterations: 3 per task (to save tokens)\n")

    results = []

    for i, task in enumerate(TEST_TASKS, 1):
        print(f"\n[{i}/{len(TEST_TASKS)}] {task.id}")
        try:
            result = run_task_with_rlm(task, verbose=verbose)
            results.append(result)

            status = "✓" if result.converged else "✗"
            verification_status = "✓" if result.verification_feedback_found else "✗"

            print(f"    {status} Converged: {result.converged}")
            print(f"    {verification_status} Verification feedback: {result.verification_feedback_found}")
            print(f"       Iterations: {result.iteration_count}")

        except Exception as e:
            print(f"    ✗ ERROR: {e}")
            results.append(TaskResult(
                task_id=task.id,
                condition="verification-enabled",
                converged=False,
                iteration_count=0,
                answer=f"ERROR: {e}",
                sparql=None,
                verification_feedback_found=False,
                verification_examples=[],
            ))

    # Summary
    print("\n" + "=" * 70)
    print("RESULTS SUMMARY")
    print("=" * 70)

    total = len(results)
    converged = sum(1 for r in results if r.converged)
    with_verification = sum(1 for r in results if r.verification_feedback_found)

    print(f"\nConvergence: {converged}/{total} ({100*converged/total:.0f}%)")
    print(f"Verification feedback found: {with_verification}/{total} ({100*with_verification/total:.0f}%)")

    # Show verification examples
    print("\n" + "=" * 70)
    print("VERIFICATION FEEDBACK EXAMPLES")
    print("=" * 70)

    for result in results:
        print(f"\n### {result.task_id} ###")
        if result.verification_feedback_found:
            print("✓ Verification feedback found:")
            for line in result.verification_examples:
                print(f"  {line}")
        else:
            print("✗ No verification feedback found")

    # Validate
    print("\n" + "=" * 70)
    if with_verification == total:
        print("✓ SUCCESS: All tasks have verification feedback!")
        print("=" * 70)
        return True
    else:
        print(f"⚠ PARTIAL: Only {with_verification}/{total} tasks have verification feedback")
        print("=" * 70)
        return False


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--verbose", action="store_true", help="Verbose output")
    args = parser.parse_args()

    success = run_small_test(verbose=args.verbose)
    sys.exit(0 if success else 1)
