#!/usr/bin/env python
"""
Comprehensive trajectory analysis for S3 experiment.

Analyzes all 100 trajectories to extract:
- Iteration counts
- Judgment quality (LM-as-judge)
- Tool usage patterns
- Memory extraction/storage
- Success/failure modes
"""

import json
import sys
import os
from pathlib import Path
from collections import defaultdict, Counter
from dataclasses import dataclass, field
import statistics

sys.path.insert(0, '/Users/cvardema/dev/git/LA3D/rlm')


@dataclass
class TrajectoryStats:
    """Statistics for a single trajectory."""
    task_id: str
    strategy: str
    rollout: int
    converged: bool
    iterations: int
    total_calls: int = 0
    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_cost: float = 0.0

    # Tool usage
    tools_used: list = field(default_factory=list)
    tool_counts: dict = field(default_factory=dict)

    # Iteration data
    iteration_data: list = field(default_factory=list)

    # Final output
    has_sparql: bool = False
    sparql: str = ""
    answer: str = ""

    # Judgment (if available)
    judgment_success: bool = False
    judgment_reason: str = ""

    # Memory
    memory_extracted: int = 0
    memory_stored: int = 0


def load_trajectory(log_path: str) -> TrajectoryStats:
    """Load and analyze a single trajectory log."""

    if not os.path.exists(log_path):
        return None

    # Parse task_id, strategy, rollout from path
    # Path format: .../logs/{task_id}/{strategy}/{task_id}_rollout{N}.jsonl
    parts = log_path.split('/')
    task_id = parts[-3]
    strategy = parts[-2]
    filename = parts[-1]
    rollout = int(filename.split('rollout')[1].replace('.jsonl', ''))

    stats = TrajectoryStats(
        task_id=task_id,
        strategy=strategy,
        rollout=rollout,
        converged=False,
        iterations=0,
    )

    iteration_events = []
    tool_sequence = []

    with open(log_path, 'r') as f:
        for line in f:
            if not line.strip():
                continue

            event = json.loads(line)
            event_type = event.get('event_type')
            data = event.get('data', {})

            if event_type == 'run_start':
                # Run configuration
                pass

            elif event_type == 'tool_call':
                tool_name = data.get('tool', 'unknown')
                tool_sequence.append(tool_name)

            elif event_type == 'iteration':
                iteration_events.append(data)

            elif event_type == 'run_complete':
                stats.converged = data.get('converged', False)
                stats.iterations = data.get('iterations', 0)
                stats.has_sparql = data.get('has_sparql', False)
                stats.sparql = data.get('sparql', '')
                stats.answer = data.get('answer_preview', '')

                lm_usage = data.get('lm_usage', {})
                stats.total_calls = lm_usage.get('total_calls', 0)
                stats.prompt_tokens = lm_usage.get('prompt_tokens', 0)
                stats.completion_tokens = lm_usage.get('completion_tokens', 0)
                stats.total_cost = lm_usage.get('total_cost', 0.0)

            elif event_type == 'judgment':
                stats.judgment_success = data.get('success', False)
                stats.judgment_reason = data.get('reason', '')

            elif event_type == 'memory_extracted':
                stats.memory_extracted = data.get('count', 0)

            elif event_type == 'memory_stored':
                stats.memory_stored = data.get('count', 0)

    stats.tools_used = tool_sequence
    stats.tool_counts = Counter(tool_sequence)
    stats.iteration_data = iteration_events

    return stats


def analyze_all_trajectories(results_dir: str) -> dict:
    """Analyze all trajectories in S3 experiment."""

    logs_dir = os.path.join(results_dir, 'logs')

    all_stats = []

    # Walk through all trajectory files
    for task_dir in os.listdir(logs_dir):
        task_path = os.path.join(logs_dir, task_dir)
        if not os.path.isdir(task_path):
            continue

        for strategy_dir in os.listdir(task_path):
            strategy_path = os.path.join(task_path, strategy_dir)
            if not os.path.isdir(strategy_path):
                continue

            for log_file in os.listdir(strategy_path):
                if not log_file.endswith('.jsonl'):
                    continue

                log_path = os.path.join(strategy_path, log_file)
                stats = load_trajectory(log_path)

                if stats:
                    all_stats.append(stats)

    print(f"Loaded {len(all_stats)} trajectories")

    # Aggregate statistics
    analysis = {
        'total_trajectories': len(all_stats),
        'by_task': defaultdict(list),
        'by_strategy': defaultdict(list),
        'by_task_strategy': defaultdict(lambda: defaultdict(list)),
    }

    for stats in all_stats:
        analysis['by_task'][stats.task_id].append(stats)
        analysis['by_strategy'][stats.strategy].append(stats)
        analysis['by_task_strategy'][stats.task_id][stats.strategy].append(stats)

    return analysis, all_stats


def print_iteration_analysis(all_stats: list):
    """Analyze iteration counts."""

    print("\n" + "=" * 80)
    print("ITERATION COUNT ANALYSIS")
    print("=" * 80)

    # Overall iteration stats
    iterations = [s.iterations for s in all_stats if s.converged]

    if iterations:
        print(f"\nConverged trajectories: {len(iterations)}/{len(all_stats)}")
        print(f"Iteration count:")
        print(f"  Mean: {statistics.mean(iterations):.1f}")
        print(f"  Median: {statistics.median(iterations):.1f}")
        print(f"  Min: {min(iterations)}")
        print(f"  Max: {max(iterations)}")
        print(f"  Stdev: {statistics.stdev(iterations):.1f}" if len(iterations) > 1 else "")

    # Iteration distribution
    iter_dist = Counter(iterations)
    print(f"\nIteration distribution:")
    for iters in sorted(iter_dist.keys()):
        count = iter_dist[iters]
        pct = count / len(iterations) * 100
        print(f"  {iters} iterations: {count:3d} trajectories ({pct:5.1f}%)")

    # By task
    print(f"\nIterations by task:")
    tasks = sorted(set(s.task_id for s in all_stats))
    for task_id in tasks:
        task_stats = [s for s in all_stats if s.task_id == task_id and s.converged]
        if task_stats:
            task_iters = [s.iterations for s in task_stats]
            print(f"  {task_id:45s}: {statistics.mean(task_iters):4.1f} ± {statistics.stdev(task_iters):3.1f}" if len(task_iters) > 1 else f"  {task_id:45s}: {statistics.mean(task_iters):4.1f}")

    # By strategy
    print(f"\nIterations by strategy:")
    strategies = ['none', 'prefix', 'thinking', 'rephrase']
    for strategy in strategies:
        strat_stats = [s for s in all_stats if s.strategy == strategy and s.converged]
        if strat_stats:
            strat_iters = [s.iterations for s in strat_stats]
            print(f"  {strategy:8s}: {statistics.mean(strat_iters):4.1f} ± {statistics.stdev(strat_iters):3.1f}" if len(strat_iters) > 1 else f"  {strategy:8s}: {statistics.mean(strat_iters):4.1f}")


def print_tool_usage_analysis(all_stats: list):
    """Analyze tool usage patterns."""

    print("\n" + "=" * 80)
    print("TOOL USAGE ANALYSIS")
    print("=" * 80)

    # Overall tool usage
    all_tools = []
    for s in all_stats:
        all_tools.extend(s.tools_used)

    tool_counts = Counter(all_tools)

    print(f"\nTotal tool calls: {len(all_tools)}")
    print(f"Unique tools: {len(tool_counts)}")
    print(f"\nTool frequency:")
    for tool, count in tool_counts.most_common():
        pct = count / len(all_tools) * 100
        print(f"  {tool:20s}: {count:4d} calls ({pct:5.1f}%)")

    # Common tool sequences
    print(f"\nCommon tool sequences (first 5 tools):")
    sequences = [tuple(s.tools_used[:5]) for s in all_stats if len(s.tools_used) >= 5]
    seq_counts = Counter(sequences)

    for seq, count in seq_counts.most_common(10):
        print(f"  {count:3d}x: {' → '.join(seq)}")


def print_convergence_analysis(all_stats: list):
    """Analyze convergence patterns."""

    print("\n" + "=" * 80)
    print("CONVERGENCE ANALYSIS")
    print("=" * 80)

    converged = [s for s in all_stats if s.converged]
    failed = [s for s in all_stats if not s.converged]

    print(f"\nOverall:")
    print(f"  Converged: {len(converged)}/{len(all_stats)} ({len(converged)/len(all_stats)*100:.1f}%)")
    print(f"  Failed: {len(failed)}/{len(all_stats)} ({len(failed)/len(all_stats)*100:.1f}%)")

    # By task
    print(f"\nBy task:")
    tasks = sorted(set(s.task_id for s in all_stats))
    for task_id in tasks:
        task_stats = [s for s in all_stats if s.task_id == task_id]
        task_converged = sum(1 for s in task_stats if s.converged)
        print(f"  {task_id:45s}: {task_converged}/{len(task_stats)} ({task_converged/len(task_stats)*100:5.1f}%)")

    # By strategy
    print(f"\nBy strategy:")
    strategies = ['none', 'prefix', 'thinking', 'rephrase']
    for strategy in strategies:
        strat_stats = [s for s in all_stats if s.strategy == strategy]
        strat_converged = sum(1 for s in strat_stats if s.converged)
        print(f"  {strategy:8s}: {strat_converged}/{len(strat_stats)} ({strat_converged/len(strat_stats)*100:5.1f}%)")


def print_cost_analysis(all_stats: list):
    """Analyze API costs."""

    print("\n" + "=" * 80)
    print("COST ANALYSIS")
    print("=" * 80)

    total_cost = sum(s.total_cost for s in all_stats)
    total_tokens = sum(s.prompt_tokens + s.completion_tokens for s in all_stats)
    total_prompt = sum(s.prompt_tokens for s in all_stats)
    total_completion = sum(s.completion_tokens for s in all_stats)

    print(f"\nTotal cost: ${total_cost:.2f}")
    print(f"Total tokens: {total_tokens:,}")
    print(f"  Prompt tokens: {total_prompt:,}")
    print(f"  Completion tokens: {total_completion:,}")
    print(f"Average cost per trajectory: ${total_cost/len(all_stats):.4f}")

    # By task
    print(f"\nCost by task:")
    tasks = sorted(set(s.task_id for s in all_stats))
    for task_id in tasks:
        task_stats = [s for s in all_stats if s.task_id == task_id]
        task_cost = sum(s.total_cost for s in task_stats)
        print(f"  {task_id:45s}: ${task_cost:6.2f} ({len(task_stats)} trajectories)")


def print_memory_analysis(all_stats: list):
    """Analyze memory extraction/storage."""

    print("\n" + "=" * 80)
    print("MEMORY ANALYSIS")
    print("=" * 80)

    extracted = sum(s.memory_extracted for s in all_stats)
    stored = sum(s.memory_stored for s in all_stats)

    print(f"\nMemories extracted: {extracted}")
    print(f"Memories stored: {stored}")

    if extracted == 0 and stored == 0:
        print("\n⚠ No memory extraction or storage detected.")
        print("This was likely a baseline run without memory integration.")


def main():
    """Run comprehensive trajectory analysis."""

    results_dir = 'experiments/reasoningbank/results/s3_prompt_perturbation'

    print("=" * 80)
    print("S3 EXPERIMENT TRAJECTORY ANALYSIS")
    print("=" * 80)

    analysis, all_stats = analyze_all_trajectories(results_dir)

    print_iteration_analysis(all_stats)
    print_tool_usage_analysis(all_stats)
    print_convergence_analysis(all_stats)
    print_cost_analysis(all_stats)
    print_memory_analysis(all_stats)

    # Save detailed stats for further analysis
    output_file = os.path.join(results_dir, 'trajectory_analysis.json')

    stats_dicts = [
        {
            'task_id': s.task_id,
            'strategy': s.strategy,
            'rollout': s.rollout,
            'converged': s.converged,
            'iterations': s.iterations,
            'total_calls': s.total_calls,
            'total_cost': s.total_cost,
            'tools_used': s.tools_used,
            'tool_counts': dict(s.tool_counts),
            'has_sparql': s.has_sparql,
        }
        for s in all_stats
    ]

    with open(output_file, 'w') as f:
        json.dump({
            'total_trajectories': len(all_stats),
            'trajectories': stats_dicts,
        }, f, indent=2)

    print(f"\n{'='*80}")
    print(f"Detailed statistics saved to: {output_file}")
    print(f"{'='*80}")


if __name__ == '__main__':
    main()
