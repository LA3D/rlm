#!/usr/bin/env python
"""Analyze E9a UniProt results: iteration counts, memory impact, procedure effectiveness."""

import sys
sys.path.insert(0, '/Users/cvardema/dev/git/LA3D/rlm')

import re
import json
from pathlib import Path

def extract_iterations_from_log(log_file):
    """Extract iteration counts from log file."""
    # Since we don't have verbose RLM output, we'll need to parse differently
    # For now, return empty list - we'll need trajectory files or other mechanism
    return []

def compare_runs():
    """Compare Run 1 (cold) vs Run 2 (warm)."""

    print('=' * 70)
    print('E9a-UniProt: Memory Accumulation Analysis')
    print('=' * 70)
    print()

    # Check if both runs completed
    run1_log = Path('experiments/reasoningbank/results/e9a_uniprot_run1.log')
    run2_log = Path('experiments/reasoningbank/results/e9a_uniprot_run2.log')

    if not run1_log.exists():
        print('ERROR: Run 1 log not found')
        return

    if not run2_log.exists():
        print('ERROR: Run 2 log not found (still running?)')
        return

    # Parse logs
    print('Parsing logs...')

    run1_content = run1_log.read_text()
    run2_content = run2_log.read_text()

    # Extract summary info
    tasks = ['protein_lookup', 'protein_properties', 'annotation_types']

    print()
    print('Task Results:')
    print('-' * 70)
    print(f"{'Task':25} {'Run 1':10} {'Run 2':10} {'Change':10}")
    print('-' * 70)

    for task in tasks:
        r1_status = '✓' if f'Task: {task}' in run1_content else '?'
        r2_status = '✓' if f'Task: {task}' in run2_content else '?'

        # Try to extract judgment
        r1_judgment = 'Success' if f'[success] Extracted:' in run1_content else 'Unknown'
        r2_judgment = 'Success' if f'[success] Extracted:' in run2_content else 'Unknown'

        print(f"{task:25} {r1_status:10} {r2_status:10}")

    print()

    # Load memory files to see what was accumulated
    run1_mem = json.loads(Path('experiments/reasoningbank/results/e9a_uniprot_run1.json').read_text())
    run2_mem = json.loads(Path('experiments/reasoningbank/results/e9a_uniprot_run2.json').read_text())

    print(f'Memory accumulation:')
    print(f'  Run 1: {len(run1_mem)} procedures')
    print(f'  Run 2: {len(run2_mem)} procedures')
    print(f'  New procedures extracted: {len(run2_mem) - len(run1_mem)}')
    print()

    # Show new procedures
    if len(run2_mem) > len(run1_mem):
        print('New procedures in Run 2:')
        for i in range(len(run1_mem), len(run2_mem)):
            proc = run2_mem[i]
            print(f"  [{proc['src']}] {proc['title']}")

    print()
    print('=' * 70)
    print('Next Steps:')
    print('=' * 70)
    print('1. Check trajectory files for iteration counts')
    print('2. Analyze if procedure #2 caused slowdown in protein_properties')
    print('3. Compare context sizes between runs')
    print('4. Look for signs of over-exploration or confusion')

if __name__ == '__main__':
    compare_runs()
