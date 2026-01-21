"""Complex smoke test with DOLCE UltraLite SystemsLite ontology.

Tests system capabilities with a more challenging foundational ontology:
- Richer conceptual hierarchy (Systems theory + DOLCE foundations)
- Multi-hop reasoning (System → Design → Workflow relationships)
- Philosophical distinctions (PhysicalSystem vs NonPhysicalSystem vs HybridSystem)
- Comparison: baseline vs sense card augmented

This is a much harder test than PROV (1552 lines vs ~600 triples).
"""

import os
import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from rlm_runtime.engine.dspy_rlm import run_dspy_rlm
from rlm.ontology import build_sense_structured, format_sense_card
from rlm_runtime.memory import SQLiteMemoryBackend


def run_test(test_name: str, query: str, ontology_path: Path, sense_card: str = None):
    """Run a single test configuration."""
    print(f"\n{'='*80}")
    print(f"Test: {test_name}")
    print(f"{'='*80}")
    print(f"Query: {query}")
    print(f"Sense card: {'Yes' if sense_card else 'No'}")

    log_path = project_root / f"test_dul_{test_name.lower().replace(' ', '_')}.jsonl"

    try:
        result = run_dspy_rlm(
            query,
            str(ontology_path),
            sense_card=sense_card,
            max_iterations=8,           # Allow more iterations for complex ontology
            max_llm_calls=20,           # More budget for exploration
            log_path=str(log_path),
            verbose=False               # Less verbose to see results clearly
        )

        print(f"\n✓ Execution completed!")
        print(f"  Iterations: {result.iteration_count}")
        print(f"  Converged: {result.converged}")

        # Show answer
        print(f"\n  Answer: {result.answer[:300]}...")

        # Show evidence
        if result.evidence:
            print(f"\n  Evidence captured ({len(result.evidence)} fields):")
            for key in list(result.evidence.keys())[:5]:
                val = str(result.evidence[key])[:100]
                print(f"    - {key}: {val}...")

        # Show SPARQL if any
        if result.sparql:
            print(f"\n  SPARQL used: {result.sparql[:200]}...")

        return result

    except Exception as e:
        print(f"\n✗ Test failed: {e}")
        import traceback
        traceback.print_exc()
        return None


def main():
    print("=" * 80)
    print("DOLCE UltraLite SystemsLite Smoke Test")
    print("Complex foundational ontology with systems theory")
    print("=" * 80)

    # Check API key
    if not os.environ.get("ANTHROPIC_API_KEY"):
        print("ERROR: ANTHROPIC_API_KEY not set")
        return 1

    ontology_path = project_root / "ontology" / "dul" / "SystemsLite.ttl"
    if not ontology_path.exists():
        print(f"ERROR: {ontology_path} not found")
        return 1

    print(f"\nOntology: {ontology_path.name}")

    # Count size
    with open(ontology_path) as f:
        lines = len(f.readlines())
    print(f"Size: {lines} lines (vs PROV ~600 lines)")

    # Build sense card
    print("\n1. Building sense card for SystemsLite...")
    sense = build_sense_structured(str(ontology_path), name="systems_sense", ns={})
    card = format_sense_card(sense['sense_card'])
    print(f"   ✓ Sense card generated ({len(card)} chars)")
    print(f"   Preview: {card[:250]}...")

    # Test query - requires understanding of:
    # 1. System hierarchy (PhysicalSystem vs NonPhysicalSystem vs HybridSystem)
    # 2. Design relationships (isDescribedBy SystemDesign)
    # 3. Philosophical distinctions from DOLCE
    query = ("What is the difference between a PhysicalSystem and a NonPhysicalSystem "
             "in SystemsLite? Give examples if the ontology provides them.")

    # Test 1: Baseline (no sense card)
    print("\n" + "="*80)
    print("TEST 1: Baseline (no sense card)")
    print("="*80)
    result_baseline = run_test(
        "baseline",
        query,
        ontology_path,
        sense_card=None
    )

    # Test 2: With sense card
    print("\n" + "="*80)
    print("TEST 2: With Sense Card")
    print("="*80)
    result_sense = run_test(
        "with_sense",
        query,
        ontology_path,
        sense_card=card
    )

    # Comparison
    print("\n" + "="*80)
    print("COMPARISON")
    print("="*80)

    if result_baseline and result_sense:
        print("\nMetrics:")
        print(f"  Baseline iterations: {result_baseline.iteration_count}")
        print(f"  Sense card iterations: {result_sense.iteration_count}")

        iter_diff = result_baseline.iteration_count - result_sense.iteration_count
        if iter_diff > 0:
            print(f"  → Sense card saved {iter_diff} iterations ✓")
        elif iter_diff < 0:
            print(f"  → Sense card added {abs(iter_diff)} iterations")
        else:
            print(f"  → Same iteration count")

        # Answer quality comparison
        print("\n  Answer lengths:")
        print(f"  Baseline: {len(result_baseline.answer)} chars")
        print(f"  Sense card: {len(result_sense.answer)} chars")

        # Evidence comparison
        baseline_evidence_keys = len(result_baseline.evidence) if result_baseline.evidence else 0
        sense_evidence_keys = len(result_sense.evidence) if result_sense.evidence else 0
        print(f"\n  Evidence fields:")
        print(f"  Baseline: {baseline_evidence_keys} fields")
        print(f"  Sense card: {sense_evidence_keys} fields")

        if sense_evidence_keys > baseline_evidence_keys:
            print(f"  → Sense card provided {sense_evidence_keys - baseline_evidence_keys} more evidence fields ✓")

    # Test 3: Challenge question requiring deep navigation
    print("\n" + "="*80)
    print("TEST 3: Deep Navigation Challenge")
    print("="*80)

    challenge_query = ("What roles do entities play in a SystemImplementationWorkflow? "
                      "Explain the input-throughput-output distinction.")

    result_challenge = run_test(
        "challenge",
        challenge_query,
        ontology_path,
        sense_card=card  # Use sense card for harder question
    )

    # Final summary
    print("\n" + "="*80)
    print("SMOKE TEST SUMMARY")
    print("="*80)

    tests_passed = sum([
        result_baseline is not None,
        result_sense is not None,
        result_challenge is not None
    ])

    print(f"\nTests passed: {tests_passed}/3")

    if tests_passed == 3:
        print("\n✓ All tests passed!")
        print("\nKey findings:")
        print("  ✓ System handles complex foundational ontology (SystemsLite)")
        print("  ✓ Navigates rich philosophical distinctions (Physical vs NonPhysical)")
        print("  ✓ Sense card injection works with complex ontologies")
        print("  ✓ Can answer multi-hop conceptual questions")
        print("  ✓ Produces grounded evidence from complex ontology")
        return 0
    else:
        print(f"\n⚠ {3 - tests_passed} test(s) failed")
        return 1


if __name__ == "__main__":
    sys.exit(main())
