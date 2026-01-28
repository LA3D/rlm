#!/usr/bin/env python3
"""Simple test to show verification feedback in action."""

import os
import sys
from pathlib import Path

project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

if not os.environ.get("ANTHROPIC_API_KEY"):
    print("ERROR: Set ANTHROPIC_API_KEY")
    sys.exit(1)

from rlm_runtime.engine.dspy_rlm import run_dspy_rlm

print("Testing verification feedback with PROV ontology")
print("=" * 70)

result = run_dspy_rlm(
    "What is the Activity class?",
    project_root / "ontology/prov.ttl",
    max_iterations=2,
    verbose=False,  # Less noise
    enable_verification=True
)

print(f"\nResult: Converged={result.converged}, Iterations={result.iteration_count}")
print("\n" + "=" * 70)
print("CHECKING EACH ITERATION FOR VERIFICATION FEEDBACK")
print("=" * 70)

for i, step in enumerate(result.trajectory, 1):
    print(f"\n### ITERATION {i} ###")
    output = step.get('output', '')

    # Check if verification feedback is present
    if '## Verification' in output:
        print("✓ VERIFICATION FEEDBACK FOUND!")
        # Extract just the verification section
        lines = output.split('\n')
        in_verification = False
        for line in lines:
            if '## Verification' in line:
                in_verification = True
            if in_verification:
                print(line)
                if line.strip() == '' and in_verification:
                    # End after first blank line after header
                    break
    else:
        print("No verification feedback in this iteration")
        # Show if SPARQL was called
        if 'sparql_select' in step.get('code', ''):
            print("  (but SPARQL was called)")
            # Show last 300 chars of output
            print(f"  Output tail: ...{output[-300:]}")
