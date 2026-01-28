#!/usr/bin/env python3
"""Inspect the trajectory to see verification feedback in detail."""

import os
import sys
from pathlib import Path

project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

if not os.environ.get("ANTHROPIC_API_KEY"):
    sys.exit(1)

from rlm_runtime.engine.dspy_rlm import run_dspy_rlm

print("="*80)
print("TRAJECTORY INSPECTION: Verification Feedback Detail")
print("="*80)

# Run a single task
result = run_dspy_rlm(
    "What is the Protein class?",
    project_root / "ontology/uniprot/core.ttl",
    max_iterations=3,
    verbose=False,
    enable_verification=True
)

print(f"\nTask completed: {result.iteration_count} iterations, converged={result.converged}")
print(f"Trajectory has {len(result.trajectory)} steps\n")

# Examine each step
for i, step in enumerate(result.trajectory, 1):
    print("="*80)
    print(f"ITERATION {i}")
    print("="*80)

    code = step.get('code', '')
    output = step.get('output', '')
    reasoning = step.get('reasoning', '')

    # Check for SPARQL
    has_sparql = 'sparql_select' in code.lower() or 'sparql_query' in code.lower()
    has_verification = '## Verification' in output

    print(f"\nReasoning ({len(reasoning)} chars):")
    print(reasoning[:300])
    if len(reasoning) > 300:
        print("  ...")

    print(f"\nCode ({len(code)} chars):")
    print(code[:300])
    if len(code) > 300:
        print("  ...")

    print(f"\nOutput ({len(output)} chars):")
    print(f"  Has SPARQL call: {has_sparql}")
    print(f"  Has verification: {has_verification}")

    if has_verification:
        # Extract and display verification section
        print("\n  ✓ VERIFICATION FEEDBACK FOUND:")
        print("  " + "-"*76)
        lines = output.split('\n')
        in_verification = False
        line_count = 0
        for line in lines:
            if '## Verification' in line:
                in_verification = True
            if in_verification:
                print(f"  {line}")
                line_count += 1
                if line_count > 15:  # Show first 15 lines of feedback
                    print("  ...")
                    break
        print("  " + "-"*76)
    else:
        # Show output sample
        print("\n  Output sample:")
        for line in output.split('\n')[:5]:
            print(f"    {line}")
        if output.count('\n') > 5:
            print("    ...")

print("\n" + "="*80)
print("SUMMARY")
print("="*80)

steps_with_sparql = sum(1 for s in result.trajectory if 'sparql' in s.get('code', '').lower())
steps_with_verification = sum(1 for s in result.trajectory if '## Verification' in s.get('output', ''))

print(f"\nTotal iterations: {len(result.trajectory)}")
print(f"Steps with SPARQL: {steps_with_sparql}")
print(f"Steps with verification feedback: {steps_with_verification}")

if steps_with_verification > 0:
    print(f"\n✓ Verification feedback successfully appears in trajectory!")
    print(f"  Feedback injection rate: {steps_with_verification}/{steps_with_sparql} SPARQL steps")
else:
    print(f"\n✗ No verification feedback found")
