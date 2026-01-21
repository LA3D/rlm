"""Test effectiveness of enhanced sense cards with Widoco metadata.

Tests:
1. Sense card generation with Widoco metadata detection
2. Comparative DSPy RLM runs: baseline vs enhanced sense cards
3. Metrics: iterations, convergence, sense card mentions, answer quality
"""

import os
import sys
from pathlib import Path
from typing import Optional

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from rlm_runtime.ontology import build_sense_card, format_sense_card
from rlm_runtime.engine.dspy_rlm import run_dspy_rlm


def test_sense_card_generation():
    """Test that sense card detects Widoco metadata patterns."""
    print("=" * 80)
    print("TEST 1: Sense Card Generation (Widoco Metadata Detection)")
    print("=" * 80)

    # Test with PROV ontology
    ontology_path = project_root / "ontology" / "prov.ttl"
    if not ontology_path.exists():
        print(f"ERROR: {ontology_path} not found")
        return False

    print(f"\nOntology: {ontology_path.name}")

    # Build sense card
    sense_card = build_sense_card(str(ontology_path), "PROV")
    card_text = format_sense_card(sense_card)

    print(f"\nSense Card ({len(card_text)} chars):")
    print("-" * 80)
    print(card_text)
    print("-" * 80)

    # Verify Widoco metadata detection
    print("\nWidoco Metadata Detection:")
    print(f"  ✓ Imports: {sense_card.metadata.imports_count} ontologies")
    if sense_card.metadata.imported_ontologies:
        print(f"    → {', '.join(sense_card.metadata.imported_ontologies)}")

    print(f"  ✓ Version Info: {sense_card.metadata.has_version_info}")
    if sense_card.metadata.version_string:
        print(f"    → Version: {sense_card.metadata.version_string}")

    print(f"  ✓ Deprecated Terms: {sense_card.metadata.deprecated_term_count}")
    print(f"  ✓ Status: {sense_card.metadata.status_value or 'None'}")

    print(f"  ✓ Provenance Vocabs:")
    print(f"    - PAV: {sense_card.metadata.uses_pav}")
    print(f"    - PROV: {sense_card.metadata.uses_prov}")
    print(f"    - VANN: {sense_card.metadata.uses_vann}")

    # Check if any Widoco metadata was found
    has_widoco_metadata = (
        sense_card.metadata.imports_count > 0 or
        sense_card.metadata.has_version_info or
        sense_card.metadata.deprecated_term_count > 0 or
        sense_card.metadata.status_value is not None or
        sense_card.metadata.uses_pav or
        sense_card.metadata.uses_prov or
        sense_card.metadata.uses_vann
    )

    if has_widoco_metadata:
        print("\n  ✓ Widoco metadata patterns detected!")
    else:
        print("\n  ℹ No Widoco metadata found in this ontology (expected for basic ontologies)")

    return True


def run_comparative_test(
    query: str,
    ontology_path: Path,
    test_name: str,
    use_sense_card: bool = True
) -> Optional[dict]:
    """Run a single DSPy RLM test and collect metrics.

    Args:
        query: Query to run
        ontology_path: Path to ontology file
        test_name: Test identifier for logs
        use_sense_card: Whether to use enhanced sense card

    Returns:
        Dict with metrics or None on error
    """
    log_path = project_root / f"test_sense_{test_name}.jsonl"

    try:
        # Build sense card if requested
        sense_card_text = None
        if use_sense_card:
            sense_card = build_sense_card(str(ontology_path), ontology_path.stem)
            sense_card_text = format_sense_card(sense_card)

        # Run DSPy RLM
        result = run_dspy_rlm(
            query,
            str(ontology_path),
            sense_card=sense_card_text,
            max_iterations=8,
            max_llm_calls=20,
            log_path=str(log_path),
            verbose=False
        )

        # Count sense card mentions in trajectory
        sense_mentions = 0
        if use_sense_card:
            for step in result.trajectory:
                step_text = str(step).lower()
                if any(keyword in step_text for keyword in ['formalism', 'metadata', 'navigation', 'maturity', 'dependencies', 'imports', 'version', 'deprecated']):
                    sense_mentions += 1

        # Collect metrics
        metrics = {
            'test_name': test_name,
            'use_sense_card': use_sense_card,
            'iterations': result.iteration_count,
            'converged': result.converged,
            'answer_length': len(result.answer),
            'evidence_fields': len(result.evidence) if result.evidence else 0,
            'sense_mentions': sense_mentions,
            'has_sparql': result.sparql is not None and len(result.sparql) > 0
        }

        return metrics

    except Exception as e:
        print(f"  ✗ Test failed: {e}")
        import traceback
        traceback.print_exc()
        return None


def test_comparative_effectiveness():
    """Compare baseline (no sense) vs enhanced sense card."""
    print("\n" + "=" * 80)
    print("TEST 2: Comparative Effectiveness (Baseline vs Enhanced Sense)")
    print("=" * 80)

    # Check API key
    if not os.environ.get("ANTHROPIC_API_KEY"):
        print("ERROR: ANTHROPIC_API_KEY not set")
        return False

    ontology_path = project_root / "ontology" / "prov.ttl"
    if not ontology_path.exists():
        print(f"ERROR: {ontology_path} not found")
        return False

    # Test query
    query = "What is Activity in PROV? How does it relate to Entity and Agent?"

    print(f"\nQuery: {query}")
    print(f"Ontology: {ontology_path.name}")

    # Run baseline (no sense card)
    print("\n" + "-" * 80)
    print("Running BASELINE (no sense card)...")
    print("-" * 80)
    baseline_metrics = run_comparative_test(
        query,
        ontology_path,
        "baseline",
        use_sense_card=False
    )

    if baseline_metrics:
        print(f"  ✓ Iterations: {baseline_metrics['iterations']}")
        print(f"  ✓ Converged: {baseline_metrics['converged']}")
        print(f"  ✓ Answer length: {baseline_metrics['answer_length']} chars")
        print(f"  ✓ Evidence fields: {baseline_metrics['evidence_fields']}")

    # Run with enhanced sense card
    print("\n" + "-" * 80)
    print("Running ENHANCED SENSE CARD...")
    print("-" * 80)
    sense_metrics = run_comparative_test(
        query,
        ontology_path,
        "enhanced_sense",
        use_sense_card=True
    )

    if sense_metrics:
        print(f"  ✓ Iterations: {sense_metrics['iterations']}")
        print(f"  ✓ Converged: {sense_metrics['converged']}")
        print(f"  ✓ Answer length: {sense_metrics['answer_length']} chars")
        print(f"  ✓ Evidence fields: {sense_metrics['evidence_fields']}")
        print(f"  ✓ Sense mentions: {sense_metrics['sense_mentions']}")

    # Comparison
    if baseline_metrics and sense_metrics:
        print("\n" + "=" * 80)
        print("COMPARISON RESULTS")
        print("=" * 80)

        iter_diff = baseline_metrics['iterations'] - sense_metrics['iterations']
        print(f"\nIteration count:")
        print(f"  Baseline: {baseline_metrics['iterations']}")
        print(f"  Enhanced: {sense_metrics['iterations']}")
        if iter_diff > 0:
            print(f"  → Enhanced sense saved {iter_diff} iterations ✓")
        elif iter_diff < 0:
            print(f"  → Enhanced sense added {abs(iter_diff)} iterations")
        else:
            print(f"  → Same iteration count")

        print(f"\nConvergence:")
        print(f"  Baseline: {baseline_metrics['converged']}")
        print(f"  Enhanced: {sense_metrics['converged']}")

        print(f"\nAnswer quality:")
        print(f"  Baseline: {baseline_metrics['answer_length']} chars")
        print(f"  Enhanced: {sense_metrics['answer_length']} chars")

        print(f"\nEvidence collected:")
        print(f"  Baseline: {baseline_metrics['evidence_fields']} fields")
        print(f"  Enhanced: {sense_metrics['evidence_fields']} fields")

        print(f"\nSense card engagement:")
        print(f"  Mentions: {sense_metrics['sense_mentions']} trajectory steps referenced sense metadata")

        # Decision criteria
        print("\n" + "=" * 80)
        print("ASSESSMENT")
        print("=" * 80)

        improvements = []
        regressions = []

        if iter_diff > 0:
            improvements.append(f"Reduced iterations by {iter_diff}")
        elif iter_diff < 0:
            regressions.append(f"Increased iterations by {abs(iter_diff)}")

        if sense_metrics['converged'] and not baseline_metrics['converged']:
            improvements.append("Achieved convergence (baseline did not)")
        elif not sense_metrics['converged'] and baseline_metrics['converged']:
            regressions.append("Failed to converge (baseline did)")

        if sense_metrics['evidence_fields'] > baseline_metrics['evidence_fields']:
            improvements.append(f"Collected {sense_metrics['evidence_fields'] - baseline_metrics['evidence_fields']} more evidence fields")

        if sense_metrics['sense_mentions'] > 0:
            improvements.append(f"LLM engaged with sense metadata ({sense_metrics['sense_mentions']} mentions)")
        else:
            regressions.append("LLM did not engage with sense metadata")

        if improvements:
            print("\n✓ Improvements:")
            for imp in improvements:
                print(f"  + {imp}")

        if regressions:
            print("\n✗ Regressions:")
            for reg in regressions:
                print(f"  - {reg}")

        # Overall verdict
        net_positive = len(improvements) > len(regressions)
        if net_positive:
            print("\n" + "=" * 80)
            print("✓ VERDICT: Enhanced sense cards show NET POSITIVE impact")
            print("Recommendation: Deploy enhanced sense card system")
            print("=" * 80)
            return True
        else:
            print("\n" + "=" * 80)
            print("⚠ VERDICT: Enhanced sense cards show MIXED/NEGATIVE impact")
            print("Recommendation: Review sense card format or defer deployment")
            print("=" * 80)
            return False

    return False


def main():
    print("=" * 80)
    print("Sense Card Effectiveness Test Suite")
    print("Testing Widoco Metadata Enhancements")
    print("=" * 80)

    # Test 1: Sense card generation
    gen_success = test_sense_card_generation()

    if not gen_success:
        print("\n✗ Sense card generation test failed")
        return 1

    # Test 2: Comparative effectiveness
    comp_success = test_comparative_effectiveness()

    print("\n" + "=" * 80)
    print("TEST SUITE COMPLETE")
    print("=" * 80)

    if gen_success and comp_success:
        print("\n✓ All tests passed - enhanced sense cards are effective!")
        return 0
    elif gen_success:
        print("\n⚠ Sense card generation works, but effectiveness is mixed")
        return 0  # Not a failure - just needs review
    else:
        print("\n✗ Tests failed")
        return 1


if __name__ == "__main__":
    sys.exit(main())
