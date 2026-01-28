#!/usr/bin/env python3
"""E-RC-001: Exemplar Impact Experiment using Enhanced DSPy RLM.

Tests whether reasoning chain exemplars improve SPARQL query construction
by comparing 4 conditions:
1. baseline: No exemplars, no schema (stats only)
2. schema: Schema in context, no exemplars
3. exemplar3: L1-L3 exemplars + curriculum retrieval
4. exemplar5: L1-L5 exemplars + curriculum retrieval

Based on PDDL-INSTRUCT paradigm (arXiv:2509.13351v1).
"""

import os
import sys
import json
import argparse
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
    thinking: Optional[str]
    verification: Optional[str]
    reflection: Optional[str]
    reasoning_quality: Optional[dict]


# Test tasks covering L1-L3
TEST_TASKS = [
    TestTask(
        id="L1-protein-lookup",
        query="What is the protein with accession P12345?",
        expected_level=1,
        description="Single entity retrieval by known accession"
    ),
    TestTask(
        id="L2-go-annotations",
        query="What are the GO annotations for insulin?",
        expected_level=2,
        description="Cross-reference query (Protein → GO terms)"
    ),
    TestTask(
        id="L3-reviewed-human",
        query="Find reviewed proteins in humans",
        expected_level=3,
        description="Filtering query with constraints"
    ),
]


def setup_condition_memory_backend(
    condition: str,
    exemplar_dir: Path,
    db_path: str = ":memory:"
) -> Optional[object]:
    """Setup memory backend based on experimental condition.

    Args:
        condition: 'baseline', 'schema', 'exemplar3', or 'exemplar5'
        exemplar_dir: Path to exemplar directory
        db_path: Database path (default: in-memory)

    Returns:
        SQLiteMemoryBackend or None (for baseline)
    """
    from rlm_runtime.memory.sqlite_backend import SQLiteMemoryBackend

    if condition == "baseline":
        # No memory backend
        return None

    if condition == "schema":
        # Empty backend (schema will be in context via sense card)
        return SQLiteMemoryBackend(db_path)

    # exemplar3 or exemplar5: Load exemplars
    backend = SQLiteMemoryBackend(db_path)

    if condition == "exemplar3":
        # Load L1-L3 exemplars
        pattern = "uniprot_l[123]*.md"
    elif condition == "exemplar5":
        # Load L1-L5 exemplars (when available)
        pattern = "*.md"
    else:
        raise ValueError(f"Unknown condition: {condition}")

    # Load exemplars
    from rlm_runtime.memory.exemplar_loader import load_exemplars_from_directory

    try:
        load_exemplars_from_directory(
            exemplar_dir,
            backend,
            ontology_name="uniprot",
            pattern=pattern
        )
        print(f"  Loaded exemplars with pattern: {pattern}")
    except Exception as e:
        print(f"  Warning: Could not load exemplars: {e}")

    return backend


def run_task_with_rlm(
    task: TestTask,
    condition: str,
    backend: Optional[object],
    verbose: bool = False
) -> TaskResult:
    """Run a task using run_dspy_rlm with specified condition.

    Args:
        task: TestTask to run
        condition: Experimental condition
        backend: Memory backend (or None)
        verbose: Whether to print trace

    Returns:
        TaskResult with execution details
    """
    from rlm_runtime.engine.dspy_rlm import run_dspy_rlm

    # Configure based on condition
    enable_verification = condition in ['exemplar3', 'exemplar5']
    enable_curriculum = condition in ['exemplar3', 'exemplar5']
    retrieve_memories = 3 if backend else 0

    ontology_path = project_root / f"ontology/{task.ontology}/core.ttl"
    if not ontology_path.exists():
        # Fallback: try root level
        ontology_path = project_root / f"ontology/{task.ontology}.ttl"

    if not ontology_path.exists():
        raise FileNotFoundError(f"Ontology not found: {ontology_path}")

    print(f"    Running: {task.query[:50]}...")

    result = run_dspy_rlm(
        task.query,
        ontology_path,
        max_iterations=8,
        verbose=verbose,
        memory_backend=backend,
        retrieve_memories=retrieve_memories,
        enable_verification=enable_verification,
        enable_curriculum_retrieval=enable_curriculum,
    )

    # Analyze reasoning quality
    reasoning_quality = None
    if result.thinking or result.verification or result.reflection:
        try:
            from experiments.reasoning_chain_validation.behavior_analysis import analyze_reasoning_trace

            combined = f"{result.thinking or ''}\n{result.verification or ''}\n{result.reflection or ''}"
            analysis = analyze_reasoning_trace(combined)
            reasoning_quality = {
                'state_tracking_score': analysis.state_tracking_score,
                'verification_score': analysis.verification_score,
                'reasoning_quality_score': analysis.reasoning_quality_score,
                'overall_score': analysis.overall_score,
            }
        except ImportError:
            pass

    return TaskResult(
        task_id=task.id,
        condition=condition,
        converged=result.converged,
        iteration_count=result.iteration_count,
        answer=result.answer,
        sparql=result.sparql,
        thinking=result.thinking,
        verification=result.verification,
        reflection=result.reflection,
        reasoning_quality=reasoning_quality,
    )


def run_experiment(
    conditions: list[str],
    tasks: list[TestTask],
    output_dir: Path,
    verbose: bool = False
):
    """Run E-RC-001 experiment across all conditions and tasks.

    Args:
        conditions: List of conditions to test
        tasks: List of test tasks
        output_dir: Directory to save results
        verbose: Whether to print traces
    """
    output_dir.mkdir(parents=True, exist_ok=True)

    exemplar_dir = Path("experiments/reasoning_chain_validation/exemplars")
    if not exemplar_dir.exists():
        print(f"Warning: Exemplar directory not found: {exemplar_dir}")
        print("Exemplar conditions will have no exemplars loaded.")

    # Track results
    all_results = []

    print(f"\n{'='*60}")
    print(f"E-RC-001: EXEMPLAR IMPACT EXPERIMENT")
    print(f"{'='*60}\n")

    for condition in conditions:
        print(f"Condition: {condition}")
        print(f"{'-'*60}")

        # Setup memory backend for this condition
        backend = setup_condition_memory_backend(
            condition,
            exemplar_dir,
            db_path=f":memory:"  # Use in-memory for experiments
        )

        # Run all tasks
        for task in tasks:
            try:
                result = run_task_with_rlm(task, condition, backend, verbose)
                all_results.append(result)

                # Print summary
                status = "✓" if result.converged else "✗"
                print(f"  {status} {task.id}: {result.iteration_count} iterations")

                if result.reasoning_quality:
                    print(f"     Quality: {result.reasoning_quality['overall_score']:.2f}")

            except Exception as e:
                print(f"  ✗ {task.id}: ERROR - {e}")
                if verbose:
                    import traceback
                    traceback.print_exc()

        print()

    # Save results
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    results_file = output_dir / f"rc_001_results_{timestamp}.json"

    with open(results_file, 'w') as f:
        json.dump([asdict(r) for r in all_results], f, indent=2)

    print(f"Results saved to: {results_file}")

    # Generate summary
    print(f"\n{'='*60}")
    print(f"SUMMARY")
    print(f"{'='*60}\n")

    for condition in conditions:
        condition_results = [r for r in all_results if r.condition == condition]

        converged = sum(1 for r in condition_results if r.converged)
        total = len(condition_results)
        avg_iterations = sum(r.iteration_count for r in condition_results) / total if total > 0 else 0

        quality_scores = [
            r.reasoning_quality['overall_score']
            for r in condition_results
            if r.reasoning_quality
        ]
        avg_quality = sum(quality_scores) / len(quality_scores) if quality_scores else 0

        print(f"{condition}:")
        if total > 0:
            print(f"  Convergence: {converged}/{total} ({converged/total*100:.1f}%)")
            print(f"  Avg iterations: {avg_iterations:.1f}")
            if quality_scores:
                print(f"  Avg reasoning quality: {avg_quality:.2f}")
        else:
            print(f"  No results")
        print()


def main():
    parser = argparse.ArgumentParser(
        description="Run E-RC-001: Exemplar Impact Experiment",
        formatter_class=argparse.RawDescriptionHelpFormatter
    )

    parser.add_argument(
        '--condition',
        choices=['baseline', 'schema', 'exemplar3', 'exemplar5', 'all'],
        default='all',
        help='Condition to run (default: all)'
    )

    parser.add_argument(
        '--output-dir',
        type=Path,
        default=Path('experiments/reasoning_chain_validation/results'),
        help='Output directory for results'
    )

    parser.add_argument(
        '--verbose',
        action='store_true',
        help='Print execution traces'
    )

    args = parser.parse_args()

    # Determine conditions to run
    if args.condition == 'all':
        conditions = ['baseline', 'schema', 'exemplar3', 'exemplar5']
    else:
        conditions = [args.condition]

    # Run experiment
    run_experiment(conditions, TEST_TASKS, args.output_dir, args.verbose)


if __name__ == '__main__':
    main()
