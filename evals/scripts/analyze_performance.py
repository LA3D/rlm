#!/usr/bin/env python3
"""Comprehensive performance analysis combining timing and token usage.

Analyzes trajectory JSONL logs to provide:
- Time breakdown (LLM vs tools vs overhead)
- Token usage (per call and total)
- Cost estimates
- Efficiency metrics

Usage:
    python evals/scripts/analyze_performance.py trajectory.jsonl
"""

import json
import sys
from pathlib import Path
from datetime import datetime
from collections import defaultdict
from typing import List, Dict, Any


def parse_timestamp(ts_str: str) -> datetime:
    """Parse ISO 8601 timestamp string."""
    if ts_str.endswith('Z'):
        ts_str = ts_str[:-1] + '+00:00'
    return datetime.fromisoformat(ts_str)


def compute_duration(start_ts: str, end_ts: str) -> float:
    """Compute duration in seconds between two timestamps."""
    start = parse_timestamp(start_ts)
    end = parse_timestamp(end_ts)
    return (end - start).total_seconds()


def analyze_trajectory(jsonl_path: Path) -> Dict[str, Any]:
    """Analyze trajectory with timing and token usage."""
    events = []
    with open(jsonl_path) as f:
        for line in f:
            if line.strip():
                events.append(json.loads(line))

    if not events:
        return {"error": "No events found"}

    # Track start/end pairs
    tool_starts = {}
    lm_starts = {}

    # Timing breakdowns
    tool_durations = []
    lm_durations = []
    sparql_durations = []

    # Token usage
    lm_token_usage = []

    # Session timing
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

                if 'sparql' in start_event.get('tool_name', '').lower():
                    sparql_durations.append(duration)

        elif event_type in ('lm_call', 'llm_call'):
            call_id = event.get('call_id')
            lm_starts[call_id] = event

        elif event_type in ('lm_response', 'llm_response'):
            call_id = event.get('call_id')
            if call_id in lm_starts:
                start_event = lm_starts[call_id]
                duration = compute_duration(start_event['timestamp'], timestamp)

                # Get token usage
                usage = event.get('usage', {})

                lm_durations.append({
                    'duration': duration,
                    'module': start_event.get('module_name', 'unknown'),
                    'usage': usage
                })

                if usage:
                    lm_token_usage.append(usage)

    # Compute totals
    total_duration = None
    if session_start and session_end:
        total_duration = compute_duration(session_start, session_end)

    total_tool_time = sum(d['duration'] for d in tool_durations)
    total_lm_time = sum(d['duration'] for d in lm_durations)
    total_sparql_time = sum(sparql_durations)

    # Token statistics
    token_stats = {}
    if lm_token_usage:
        token_stats = {
            'total_prompt_tokens': sum(u['prompt_tokens'] for u in lm_token_usage),
            'total_completion_tokens': sum(u['completion_tokens'] for u in lm_token_usage),
            'total_tokens': sum(u['total_tokens'] for u in lm_token_usage),
            'avg_prompt_tokens': sum(u['prompt_tokens'] for u in lm_token_usage) / len(lm_token_usage),
            'avg_completion_tokens': sum(u['completion_tokens'] for u in lm_token_usage) / len(lm_token_usage),
            'avg_total_tokens': sum(u['total_tokens'] for u in lm_token_usage) / len(lm_token_usage),
            'max_prompt_tokens': max(u['prompt_tokens'] for u in lm_token_usage),
            'min_prompt_tokens': min(u['prompt_tokens'] for u in lm_token_usage),
        }

    return {
        'total_duration': total_duration,
        'total_tool_time': total_tool_time,
        'total_lm_time': total_lm_time,
        'total_sparql_time': total_sparql_time,
        'tool_count': len(tool_durations),
        'lm_count': len(lm_durations),
        'sparql_count': len(sparql_durations),
        'avg_tool_duration': total_tool_time / len(tool_durations) if tool_durations else 0,
        'avg_lm_duration': total_lm_time / len(lm_durations) if lm_durations else 0,
        'avg_sparql_duration': total_sparql_time / len(sparql_durations) if sparql_durations else 0,
        'token_stats': token_stats,
        'tool_durations': tool_durations,
        'lm_durations': lm_durations,
    }


def print_analysis(analysis: Dict[str, Any], verbose: bool = False):
    """Print comprehensive performance analysis."""
    if 'error' in analysis:
        print(f"Error: {analysis['error']}")
        return

    print("=" * 70)
    print("PERFORMANCE ANALYSIS")
    print("=" * 70)

    total = analysis['total_duration']
    tool_time = analysis['total_tool_time']
    lm_time = analysis['total_lm_time']
    sparql_time = analysis['total_sparql_time']

    # === TIMING BREAKDOWN ===
    print("\n" + "="*70)
    print("TIMING BREAKDOWN")
    print("="*70)

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

    # === TOKEN USAGE ===
    if analysis['token_stats']:
        print("\n" + "="*70)
        print("TOKEN USAGE")
        print("="*70)

        stats = analysis['token_stats']

        print(f"\nTotal Tokens:")
        print(f"  Prompt tokens:     {stats['total_prompt_tokens']:>8,}")
        print(f"  Completion tokens: {stats['total_completion_tokens']:>8,}")
        print(f"  Total tokens:      {stats['total_tokens']:>8,}")

        print(f"\nAverage per LLM call:")
        print(f"  Prompt tokens:     {stats['avg_prompt_tokens']:>8.0f}")
        print(f"  Completion tokens: {stats['avg_completion_tokens']:>8.0f}")
        print(f"  Total tokens:      {stats['avg_total_tokens']:>8.0f}")

        print(f"\nPrompt token range:")
        print(f"  Min: {stats['min_prompt_tokens']:>6,} tokens")
        print(f"  Max: {stats['max_prompt_tokens']:>6,} tokens")

        # === EFFICIENCY METRICS ===
        print("\n" + "="*70)
        print("EFFICIENCY METRICS")
        print("="*70)

        if total and analysis['lm_count'] > 0:
            tokens_per_second = stats['total_tokens'] / lm_time
            seconds_per_1k_tokens = lm_time / (stats['total_tokens'] / 1000)

            print(f"\nLLM Throughput:")
            print(f"  Tokens per second:        {tokens_per_second:>6.1f}")
            print(f"  Seconds per 1K tokens:    {seconds_per_1k_tokens:>6.2f}s")
            print(f"  Average call time:        {analysis['avg_lm_duration']:>6.2f}s")
            print(f"  Average tokens per call:  {stats['avg_total_tokens']:>6.0f}")

            # Cost estimates (Claude Sonnet 4.5 pricing)
            # $3 per million input tokens, $15 per million output tokens
            input_cost = (stats['total_prompt_tokens'] / 1_000_000) * 3.0
            output_cost = (stats['total_completion_tokens'] / 1_000_000) * 15.0
            total_cost = input_cost + output_cost

            print(f"\nEstimated Cost (Claude Sonnet 4.5):")
            print(f"  Input:  ${input_cost:.4f}")
            print(f"  Output: ${output_cost:.4f}")
            print(f"  Total:  ${total_cost:.4f}")

    # === DETAILED BREAKDOWN ===
    if verbose:
        print("\n" + "="*70)
        print("DETAILED LLM CALL BREAKDOWN")
        print("="*70)
        for i, call in enumerate(analysis['lm_durations']):
            usage = call.get('usage', {})
            print(f"\nCall {i+1}:")
            print(f"  Duration:          {call['duration']:.2f}s")
            if usage:
                print(f"  Prompt tokens:     {usage['prompt_tokens']:,}")
                print(f"  Completion tokens: {usage['completion_tokens']:,}")
                print(f"  Total tokens:      {usage['total_tokens']:,}")


def main():
    if len(sys.argv) < 2:
        print("Usage: python analyze_performance.py <trajectory.jsonl>")
        sys.exit(1)

    input_path = Path(sys.argv[1])
    verbose = '--verbose' in sys.argv or '-v' in sys.argv

    if not input_path.exists():
        print(f"Error: File not found: {input_path}")
        sys.exit(1)

    analysis = analyze_trajectory(input_path)
    print(f"\nAnalyzing: {input_path}\n")
    print_analysis(analysis, verbose=verbose)


if __name__ == '__main__':
    main()
