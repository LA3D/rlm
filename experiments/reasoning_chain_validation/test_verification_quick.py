#!/usr/bin/env python3
"""Quick test to validate verification feedback is working.

Uses PROV ontology (smaller than UniProt) with a simple query to minimize tokens.
"""

import os
import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

# Check for API key
if not os.environ.get("ANTHROPIC_API_KEY"):
    print("ERROR: Set ANTHROPIC_API_KEY environment variable", file=sys.stderr)
    sys.exit(1)


def test_verification_feedback():
    """Test that verification feedback appears in output."""
    from rlm_runtime.engine.dspy_rlm import run_dspy_rlm

    print("=" * 60)
    print("TESTING VERIFICATION FEEDBACK")
    print("=" * 60)

    # Use PROV ontology (smaller, faster)
    ontology_path = project_root / "ontology/prov.ttl"

    # Simple query that should trigger SPARQL execution
    query = "What is the Activity class used for?"

    print(f"\nQuery: {query}")
    print(f"Ontology: {ontology_path}")
    print(f"Verification: ENABLED")
    print("\nRunning with verification feedback enabled...")
    print("-" * 60)

    result = run_dspy_rlm(
        query,
        ontology_path,
        max_iterations=3,  # Keep it short
        verbose=True,
        enable_verification=True,  # Enable verification feedback
        memory_backend=None,  # No memory to keep it simple
    )

    print("\n" + "=" * 60)
    print("RESULTS")
    print("=" * 60)

    print(f"\nConverged: {result.converged}")
    print(f"Iterations: {result.iteration_count}")
    print(f"\nAnswer: {result.answer[:200]}...")

    # Check if verification feedback appeared
    print("\n" + "=" * 60)
    print("CHECKING FOR VERIFICATION FEEDBACK")
    print("=" * 60)

    # Look through trajectory for verification feedback markers
    verification_found = False
    feedback_examples = []

    print(f"\nTrajectory has {len(result.trajectory)} steps")
    if result.trajectory:
        print(f"Trajectory structure: {type(result.trajectory[0])}")
        if isinstance(result.trajectory[0], dict):
            print(f"Keys: {list(result.trajectory[0].keys())}")

    for i, step in enumerate(result.trajectory, 1):
        # Handle dict structure
        if isinstance(step, dict):
            output = step.get('output', '') or step.get('result', '') or str(step)
        else:
            output = str(step)

        # Check for verification feedback markers
        if any(marker in output for marker in [
            "## Verification",
            "Domain/Range",
            "Constraint",
            "✓", "✗", "⚠"
        ]):
            verification_found = True
            # Extract a sample
            lines = output.split('\n')
            for j, line in enumerate(lines):
                if 'verification' in line.lower() or '✓' in line or '✗' in line:
                    feedback_examples.append(f"Iteration {i}: {line.strip()}")
                    if j + 1 < len(lines):
                        feedback_examples.append(f"           {lines[j+1].strip()}")
                    break

    if verification_found:
        print("✓ VERIFICATION FEEDBACK FOUND")
        print("\nExamples:")
        for example in feedback_examples[:5]:
            print(f"  {example}")
    else:
        print("✗ NO VERIFICATION FEEDBACK FOUND")
        print("\nThis could mean:")
        print("  1. No SPARQL queries were executed (check trajectory)")
        print("  2. Verification feedback injection failed")
        print("  3. Agent used different tool names")

    # Show first code block to see if SPARQL was called
    print("\n" + "=" * 60)
    print("FIRST STEP (checking for SPARQL calls)")
    print("=" * 60)
    if result.trajectory:
        step = result.trajectory[0]
        if isinstance(step, dict):
            print("\nStep contents:")
            for key, value in list(step.items())[:5]:
                print(f"  {key}: {str(value)[:200]}...")
        else:
            print(f"\nStep: {str(step)[:500]}")

    return verification_found


if __name__ == "__main__":
    success = test_verification_feedback()
    sys.exit(0 if success else 1)
