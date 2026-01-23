#!/usr/bin/env python3
"""Profile timing breakdown from trajectory JSONL logs.

Analyzes where time is spent during RLM execution:
- Time per iteration
- Time in LLM calls vs tool execution
- Time in SPARQL queries vs other tools
- Idle time between events

Usage:
    python evals/scripts/profile_timing.py trajectory.jsonl
    python evals/scripts/profile_timing.py evals/experiments/E002*/cohorts/*/results/*.json --extract-trajectory
"""

import json
import sys
from pathlib import Path
from datetime import datetime
from collections import defaultdict
from typing import List, Dict, Any


def parse_timestamp(ts_str: str) -> datetime:
    """Parse ISO 8601 timestamp string."""
    # Handle different timestamp formats
    if ts_str.endswith('Z'):
        ts_str = ts_str[:-1] + '+00:00'
    return datetime.fromisoformat(ts_str)


def compute_duration(start_ts: str, end_ts: str) -> float:
    """Compute duration in seconds between two timestamps."""
    start = parse_timestamp(start_ts)
    end = parse_timestamp(end_ts)
    return (end - start).total_seconds()


def analyze_trajectory_jsonl(jsonl_path: Path) -> Dict[str, Any]:
    """Analyze timing from trajectory JSONL file.

    Args:
        jsonl_path: Path to trajectory.jsonl file

    Returns:
        Dictionary with timing analysis
    """
    events = []
    with open(jsonl_path) as f:
        for line in f:
            if line.strip():
                events.append(json.loads(line))

    if not events:
        return {"error": "No events found"}

    # Track start/end pairs
    tool_starts = {}  # call_id -> event
    lm_starts = {}

    # Timing breakdowns
    tool_durations = []
    lm_durations = []
    sparql_durations = []
    iteration_times = defaultdict(list)  # iteration -> [events]

    session_start = None
    session_end = None

    for event in events:
        event_type = event.get('event')
        timestamp = event.get('timestamp')

        if event_type == 'session_start':
            session_start = timestamp
        elif event_type == 'session_end':
            session_end = timestamp

        elif event_type == 'tool_call':
            call_id = event.get('call_id')
            tool_starts[call_id] = event

        elif event_type == 'tool_result':
            call_id = event.get('call_id')
            if call_id in tool_starts:
                start_event = tool_starts[call_id]
                duration = compute_duration(start_event['timestamp'], timestamp)
                tool_durations.append({
                    'tool': start_event.get('tool_name', 'unknown'),
                    'duration': duration,
                    'iteration': start_event.get('iteration')
                })

                # Track SPARQL calls separately
                if 'sparql' in start_event.get('tool_name', '').lower():
                    sparql_durations.append(duration)

                # Track by iteration
                iteration = start_event.get('iteration', 0)
                iteration_times[iteration].append({
                    'type': 'tool',
                    'duration': duration,
                    'timestamp': timestamp
                })

        elif event_type == 'lm_call':
            call_id = event.get('call_id')
            lm_starts[call_id] = event

        elif event_type == 'lm_response':
            call_id = event.get('call_id')
            if call_id in lm_starts:
                start_event = lm_starts[call_id]
                duration = compute_duration(start_event['timestamp'], timestamp)
                lm_durations.append({
                    'duration': duration,
                    'module': start_event.get('module_name', 'unknown')
                })

                # Track by iteration (approximate)
                # LM calls don't have iteration, so use latest tool iteration
                latest_iter = max(iteration_times.keys()) if iteration_times else 0
                iteration_times[latest_iter].append({
                    'type': 'lm',
                    'duration': duration,
                    'timestamp': timestamp
                })

    # Compute total duration
    total_duration = None
    if session_start and session_end:
        total_duration = compute_duration(session_start, session_end)

    # Aggregate statistics
    total_tool_time = sum(d['duration'] for d in tool_durations)
    total_lm_time = sum(d['duration'] for d in lm_durations)
    total_sparql_time = sum(sparql_durations)

    tool_count = len(tool_durations)
    lm_count = len(lm_durations)

    # Per-iteration breakdown
    iteration_breakdown = []
    for iteration in sorted(iteration_times.keys()):
        events_in_iter = iteration_times[iteration]
        iter_duration = sum(e['duration'] for e in events_in_iter)
        tool_time = sum(e['duration'] for e in events_in_iter if e['type'] == 'tool')
        lm_time = sum(e['duration'] for e in events_in_iter if e['type'] == 'lm')

        iteration_breakdown.append({
            'iteration': iteration,
            'total_duration': iter_duration,
            'tool_time': tool_time,
            'lm_time': lm_time,
            'event_count': len(events_in_iter)
        })

    return {
        'total_duration': total_duration,
        'total_tool_time': total_tool_time,
        'total_lm_time': total_lm_time,
        'total_sparql_time': total_sparql_time,
        'tool_count': tool_count,
        'lm_count': lm_count,
        'sparql_count': len(sparql_durations),
        'avg_tool_duration': total_tool_time / tool_count if tool_count > 0 else 0,
        'avg_lm_duration': total_lm_time / lm_count if lm_count > 0 else 0,
        'avg_sparql_duration': total_sparql_time / len(sparql_durations) if sparql_durations else 0,
        'iteration_breakdown': iteration_breakdown,
        'tool_durations': tool_durations,
        'lm_durations': lm_durations,
    }


def print_analysis(analysis: Dict[str, Any], verbose: bool = False):
    """Print timing analysis in human-readable format."""
    if 'error' in analysis:
        print(f"Error: {analysis['error']}")
        return

    print("=" * 60)
    print("TIMING ANALYSIS")
    print("=" * 60)

    total = analysis['total_duration']
    tool_time = analysis['total_tool_time']
    lm_time = analysis['total_lm_time']
    sparql_time = analysis['total_sparql_time']

    if total:
        print(f"\nTotal Duration: {total:.1f}s ({total/60:.1f} minutes)")
        print(f"\nBreakdown:")
        print(f"  LLM Calls:       {lm_time:6.1f}s ({lm_time/total*100:5.1f}%)")
        print(f"  Tool Execution:  {tool_time:6.1f}s ({tool_time/total*100:5.1f}%)")
        print(f"    - SPARQL:      {sparql_time:6.1f}s ({sparql_time/total*100:5.1f}%)")
        print(f"    - Other tools: {tool_time-sparql_time:6.1f}s ({(tool_time-sparql_time)/total*100:5.1f}%)")

        accounted = lm_time + tool_time
        unaccounted = total - accounted
        if unaccounted > 0:
            print(f"  Unaccounted:     {unaccounted:6.1f}s ({unaccounted/total*100:5.1f}%) [overhead/idle]")

    print(f"\nCounts:")
    print(f"  LLM Calls:    {analysis['lm_count']}")
    print(f"  Tool Calls:   {analysis['tool_count']}")
    print(f"  SPARQL Calls: {analysis['sparql_count']}")

    print(f"\nAverages:")
    print(f"  Per LLM Call:    {analysis['avg_lm_duration']:.2f}s")
    print(f"  Per Tool Call:   {analysis['avg_tool_duration']:.2f}s")
    print(f"  Per SPARQL Call: {analysis['avg_sparql_duration']:.2f}s")

    # Iteration breakdown
    if analysis['iteration_breakdown']:
        print(f"\nPer-Iteration Breakdown:")
        print(f"  {'Iter':<6} {'Total':<8} {'LLM':<8} {'Tools':<8} {'Events':<8}")
        print(f"  {'-'*6} {'-'*8} {'-'*8} {'-'*8} {'-'*8}")
        for iter_info in analysis['iteration_breakdown']:
            print(f"  {iter_info['iteration']:<6} "
                  f"{iter_info['total_duration']:>7.1f}s "
                  f"{iter_info['lm_time']:>7.1f}s "
                  f"{iter_info['tool_time']:>7.1f}s "
                  f"{iter_info['event_count']:>8}")

    if verbose:
        print(f"\nDetailed Tool Timing:")
        for tool_info in analysis['tool_durations']:
            print(f"  [{tool_info['iteration']:2}] {tool_info['tool']:<30} {tool_info['duration']:6.2f}s")


def extract_trajectory_from_result(result_path: Path) -> Path | None:
    """Extract trajectory JSONL path from result JSON file."""
    with open(result_path) as f:
        data = json.load(f)

    # Check if trial_results has trajectory data
    if 'trial_results' not in data or not data['trial_results']:
        return None

    trial = data['trial_results'][0]
    if 'trajectory' in trial and trial['trajectory']:
        # Write trajectory to temp file
        temp_path = result_path.parent / f"{result_path.stem}_trajectory.jsonl"
        # ... would need to write trajectory events to JSONL
        # For now, return None if not already JSONL
        return None

    return None


def main():
    if len(sys.argv) < 2:
        print("Usage: python profile_timing.py <trajectory.jsonl>")
        print("   or: python profile_timing.py <result.json> --extract-trajectory")
        sys.exit(1)

    input_path = Path(sys.argv[1])
    verbose = '--verbose' in sys.argv or '-v' in sys.argv

    if input_path.suffix == '.jsonl':
        analysis = analyze_trajectory_jsonl(input_path)
        print(f"\nAnalyzing: {input_path}")
        print_analysis(analysis, verbose=verbose)
    elif input_path.suffix == '.json':
        # Try to extract trajectory from result JSON
        traj_path = extract_trajectory_from_result(input_path)
        if traj_path:
            analysis = analyze_trajectory_jsonl(traj_path)
            print(f"\nAnalyzing: {input_path}")
            print_analysis(analysis, verbose=verbose)
        else:
            print(f"Error: Could not extract trajectory from {input_path}")
            print("Trajectory data not found in result JSON")
    else:
        print(f"Error: Unsupported file type: {input_path.suffix}")
        print("Expected .jsonl or .json")


if __name__ == '__main__':
    main()
