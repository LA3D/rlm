"""Pattern comparison experiment: RLM vs ReAct with scratchpad features.

Compares execution patterns (dspy.RLM, dspy.ReAct) with shared scratchpad
infrastructure (rich sense cards, truncation, verification, memory).
"""

import os
import json
import time
from pathlib import Path
from datetime import datetime
from dataclasses import dataclass, asdict
from typing import Literal

# Ensure API key
if not os.environ.get("ANTHROPIC_API_KEY"):
    raise ValueError("Set ANTHROPIC_API_KEY environment variable")


@dataclass
class TestTask:
    """Test task with curriculum level."""
    query: str
    level: Literal["L1", "L2", "L3", "L4", "L5"]
    description: str


# Test tasks across curriculum levels
TEST_TASKS = [
    # L1: Simple entity discovery
    TestTask(
        query="What is the Protein class?",
        level="L1",
        description="Basic entity discovery"
    ),
    TestTask(
        query="What is Activity in this ontology?",
        level="L1",
        description="Basic class lookup"
    ),
    # L2: Property exploration
    TestTask(
        query="What properties connect proteins to annotations?",
        level="L2",
        description="Property relationships"
    ),
    TestTask(
        query="What properties does Activity have?",
        level="L2",
        description="Property inspection"
    ),
    # L3: Multi-hop queries
    TestTask(
        query="Find proteins with disease associations and their EC numbers",
        level="L3",
        description="Multi-property query"
    ),
    # L4: Complex filtering
    TestTask(
        query="Find kinase proteins in humans with their GO annotations",
        level="L4",
        description="Complex filtering with text matching"
    ),
    # L5: Aggregation and comparison
    TestTask(
        query="Compare protein counts across taxonomic families",
        level="L5",
        description="Aggregation query"
    ),
]


@dataclass
class PatternResult:
    """Result from running a pattern on a task."""
    pattern: str
    task_query: str
    task_level: str
    converged: bool
    iteration_count: int
    elapsed_seconds: float
    answer: str
    sparql: str | None
    evidence: dict
    error: str | None = None


def run_comparison_experiment(
    ontology: str = "uniprot",
    ontology_path: str = "ontology/uniprot/core.ttl",
    patterns: list[str] = None,
    tasks: list[TestTask] = None,
    output_dir: str = "experiments/pattern_comparison/results",
    verbose: bool = True,
) -> dict:
    """Compare execution patterns with shared scratchpad features.

    Args:
        ontology: Ontology name (e.g., "uniprot", "prov")
        ontology_path: Path to ontology file
        patterns: List of patterns to test ("dspy_rlm", "dspy_react")
        tasks: List of test tasks (defaults to TEST_TASKS)
        output_dir: Where to save results
        verbose: Print progress

    Returns:
        Dict with results and summary statistics
    """
    from rlm_runtime.engine.dspy_rlm import run_dspy_rlm
    from rlm_runtime.engine.dspy_react import run_dspy_react

    if patterns is None:
        patterns = ["dspy_rlm", "dspy_react"]

    if tasks is None:
        tasks = TEST_TASKS

    RUNNERS = {
        "dspy_rlm": run_dspy_rlm,
        "dspy_react": run_dspy_react,
    }

    # Common config (all patterns use same scratchpad features)
    common_config = {
        "result_truncation_limit": 10000,  # Daytona default
        "enable_verification": True,       # CoT feedback
        "require_agent_guide": False,      # Allow fallback if no AGENT_GUIDE
        "max_iterations": 8,
        "verbose": False,
    }

    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

    results = []
    errors = []

    print(f"\n{'='*70}")
    print(f"Pattern Comparison: {ontology}")
    print(f"Patterns: {', '.join(patterns)}")
    print(f"Tasks: {len(tasks)} across levels {set(t.level for t in tasks)}")
    print(f"{'='*70}\n")

    for pattern in patterns:
        runner = RUNNERS[pattern]

        print(f"\n{'-'*70}")
        print(f"Pattern: {pattern.upper()}")
        print(f"{'-'*70}")

        for i, task in enumerate(tasks, 1):
            if verbose:
                print(f"\n[{i}/{len(tasks)}] {task.level}: {task.query}")

            start = time.time()
            error = None

            try:
                result = runner(
                    task.query,
                    ontology_path,
                    **common_config
                )

                elapsed = time.time() - start

                pattern_result = PatternResult(
                    pattern=pattern,
                    task_query=task.query,
                    task_level=task.level,
                    converged=result.converged,
                    iteration_count=result.iteration_count,
                    elapsed_seconds=elapsed,
                    answer=result.answer,
                    sparql=result.sparql,
                    evidence=result.evidence,
                )

                results.append(pattern_result)

                if verbose:
                    status = "✓" if result.converged else "✗"
                    print(f"  {status} Converged: {result.converged}")
                    print(f"  Iterations: {result.iteration_count}")
                    print(f"  Time: {elapsed:.1f}s")
                    print(f"  Answer: {result.answer[:100]}...")

            except Exception as e:
                elapsed = time.time() - start
                error = str(e)

                pattern_result = PatternResult(
                    pattern=pattern,
                    task_query=task.query,
                    task_level=task.level,
                    converged=False,
                    iteration_count=0,
                    elapsed_seconds=elapsed,
                    answer="",
                    sparql=None,
                    evidence={},
                    error=error,
                )

                results.append(pattern_result)
                errors.append({"pattern": pattern, "task": task.query, "error": error})

                if verbose:
                    print(f"  ✗ Error: {error}")

    # Generate summary statistics
    summary = generate_summary(results, patterns)

    # Save detailed results
    results_file = output_path / f"comparison_{ontology}_{timestamp}.json"
    with open(results_file, "w") as f:
        json.dump({
            "ontology": ontology,
            "ontology_path": ontology_path,
            "patterns": patterns,
            "config": common_config,
            "timestamp": timestamp,
            "results": [asdict(r) for r in results],
            "errors": errors,
            "summary": summary,
        }, f, indent=2)

    print(f"\n{'='*70}")
    print("Results Summary")
    print(f"{'='*70}")
    print_summary(summary)
    print(f"\nDetailed results saved to: {results_file}")

    return {
        "results": results,
        "summary": summary,
        "errors": errors,
    }


def generate_summary(results: list[PatternResult], patterns: list[str]) -> dict:
    """Generate summary statistics from results."""
    summary = {}

    for pattern in patterns:
        pattern_results = [r for r in results if r.pattern == pattern]

        if not pattern_results:
            continue

        converged = [r for r in pattern_results if r.converged]
        failed = [r for r in pattern_results if not r.converged]

        summary[pattern] = {
            "total_tasks": len(pattern_results),
            "converged": len(converged),
            "failed": len(failed),
            "convergence_rate": len(converged) / len(pattern_results) if pattern_results else 0,
            "avg_iterations": sum(r.iteration_count for r in converged) / len(converged) if converged else 0,
            "avg_time": sum(r.elapsed_seconds for r in pattern_results) / len(pattern_results),
            "total_time": sum(r.elapsed_seconds for r in pattern_results),
            # By level
            "by_level": {},
        }

        # Breakdown by curriculum level
        for level in ["L1", "L2", "L3", "L4", "L5"]:
            level_results = [r for r in pattern_results if r.task_level == level]
            if level_results:
                level_converged = [r for r in level_results if r.converged]
                summary[pattern]["by_level"][level] = {
                    "total": len(level_results),
                    "converged": len(level_converged),
                    "rate": len(level_converged) / len(level_results) if level_results else 0,
                }

    return summary


def print_summary(summary: dict):
    """Print summary table."""
    print("\nOverall Performance:")
    print(f"{'Pattern':<15} | {'Conv':<6} | {'Iters':<6} | {'Time':<8} | {'Rate':<6}")
    print("-" * 70)

    for pattern, stats in summary.items():
        conv_str = f"{stats['converged']}/{stats['total_tasks']}"
        iters_str = f"{stats['avg_iterations']:.1f}"
        time_str = f"{stats['avg_time']:.1f}s"
        rate_str = f"{stats['convergence_rate']:.0%}"

        print(f"{pattern:<15} | {conv_str:<6} | {iters_str:<6} | {time_str:<8} | {rate_str:<6}")

    print("\nBy Curriculum Level:")
    for pattern, stats in summary.items():
        print(f"\n{pattern.upper()}:")
        for level, level_stats in stats["by_level"].items():
            conv_str = f"{level_stats['converged']}/{level_stats['total']}"
            rate_str = f"{level_stats['rate']:.0%}"
            print(f"  {level}: {conv_str:<6} ({rate_str})")


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Compare execution patterns")
    parser.add_argument("--ontology", default="uniprot", help="Ontology name")
    parser.add_argument("--ontology-path", default="ontology/uniprot/core.ttl", help="Path to ontology file")
    parser.add_argument("--patterns", nargs="+", default=["dspy_rlm", "dspy_react"], help="Patterns to test")
    parser.add_argument("--tasks", type=int, help="Number of tasks (defaults to all)")
    parser.add_argument("--output-dir", default="experiments/pattern_comparison/results", help="Output directory")
    parser.add_argument("--verbose", action="store_true", help="Verbose output")

    args = parser.parse_args()

    # Limit tasks if specified
    tasks = TEST_TASKS[:args.tasks] if args.tasks else TEST_TASKS

    result = run_comparison_experiment(
        ontology=args.ontology,
        ontology_path=args.ontology_path,
        patterns=args.patterns,
        tasks=tasks,
        output_dir=args.output_dir,
        verbose=args.verbose,
    )

    # Print winner
    print("\n" + "="*70)
    summary = result["summary"]
    if len(summary) > 1:
        winner = max(summary.items(), key=lambda x: (x[1]["convergence_rate"], -x[1]["avg_time"]))
        print(f"Winner: {winner[0]} (best convergence + efficiency)")
    print("="*70)
