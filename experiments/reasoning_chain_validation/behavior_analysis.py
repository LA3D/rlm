"""Behavior Analysis for Reasoning Chain Validation

This module provides functions to analyze reasoning traces for
PDDL-INSTRUCT style behavior indicators.

The key insight from PDDL-INSTRUCT: LLMs can leverage symbolic structures
when reasoning is decomposed into verifiable logical steps with explicit
state tracking.
"""

import re
from dataclasses import dataclass
from typing import Optional


@dataclass
class BehaviorAnalysis:
    """Analysis of reasoning behavior indicators."""

    # State tracking indicators
    explicit_state_references: bool  # References to "state", "discovered", "known"
    state_progression: bool  # State grows/changes through reasoning
    state_regression_detected: bool  # State goes backward (bad)

    # Verification indicators
    precondition_checking: bool  # Checks constraints before actions
    postcondition_verification: bool  # Verifies results after actions
    domain_range_checking: bool  # Explicitly checks domain/range

    # Reasoning quality indicators
    step_by_step_structure: bool  # Clear step markers (1, 2, 3 or Step 1, etc)
    explicit_reasoning: bool  # "because", "therefore", "since"
    anti_pattern_awareness: bool  # Mentions what NOT to do

    # Overall scores
    state_tracking_score: float  # 0-1
    verification_score: float  # 0-1
    reasoning_quality_score: float  # 0-1
    overall_score: float  # 0-1

    # Classification
    classification: str  # "good", "adequate", "poor"


def analyze_reasoning_trace(trace: str) -> BehaviorAnalysis:
    """Analyze a reasoning trace for PDDL-INSTRUCT style behavior.

    Args:
        trace: The full reasoning output from the LLM

    Returns:
        BehaviorAnalysis with all indicators
    """
    trace_lower = trace.lower()

    # State tracking indicators
    state_keywords = ["state", "discovered", "known classes", "known properties",
                      "classes_discovered", "properties_discovered", "state before", "state after"]
    explicit_state_references = any(kw in trace_lower for kw in state_keywords)

    # Check for state progression (mentions of updating/adding to state)
    progression_keywords = ["added", "discovered", "found", "now have", "updated state"]
    state_progression = any(kw in trace_lower for kw in progression_keywords)

    # Check for state regression (going backward)
    regression_keywords = ["forgot", "lost", "removed from state", "starting over"]
    state_regression_detected = any(kw in trace_lower for kw in regression_keywords)

    # Verification indicators
    precondition_keywords = ["before", "first check", "verify that", "ensure that", "precondition"]
    precondition_checking = any(kw in trace_lower for kw in precondition_keywords)

    postcondition_keywords = ["verification", "verified", "confirmed", "result shows",
                              "as expected", "matches expected"]
    postcondition_verification = any(kw in trace_lower for kw in postcondition_keywords)

    domain_range_keywords = ["domain", "range", "constraint", "domain is", "range is",
                            "domain:", "range:"]
    domain_range_checking = any(kw in trace_lower for kw in domain_range_keywords)

    # Reasoning quality indicators
    # Check for step markers
    step_patterns = [
        r"step\s*\d",
        r"\d\.\s+\w",
        r"first,",
        r"second,",
        r"third,",
        r"finally,",
        r"\*\*step",
        r"### step"
    ]
    step_by_step_structure = any(re.search(p, trace_lower) for p in step_patterns)

    reasoning_keywords = ["because", "therefore", "since", "this means", "so we",
                          "reasoning:", "this is because"]
    explicit_reasoning = any(kw in trace_lower for kw in reasoning_keywords)

    anti_pattern_keywords = ["anti-pattern", "don't", "do not", "avoid", "wrong",
                            "incorrect", "mistake", "shouldn't"]
    anti_pattern_awareness = any(kw in trace_lower for kw in anti_pattern_keywords)

    # Compute scores
    state_tracking_score = (
        (1.0 if explicit_state_references else 0.0) +
        (1.0 if state_progression else 0.0) +
        (0.0 if state_regression_detected else 1.0)
    ) / 3.0

    verification_score = (
        (1.0 if precondition_checking else 0.0) +
        (1.0 if postcondition_verification else 0.0) +
        (1.0 if domain_range_checking else 0.0)
    ) / 3.0

    reasoning_quality_score = (
        (1.0 if step_by_step_structure else 0.0) +
        (1.0 if explicit_reasoning else 0.0) +
        (1.0 if anti_pattern_awareness else 0.0)
    ) / 3.0

    overall_score = (state_tracking_score + verification_score + reasoning_quality_score) / 3.0

    # Classify
    if overall_score >= 0.7:
        classification = "good"
    elif overall_score >= 0.4:
        classification = "adequate"
    else:
        classification = "poor"

    return BehaviorAnalysis(
        explicit_state_references=explicit_state_references,
        state_progression=state_progression,
        state_regression_detected=state_regression_detected,
        precondition_checking=precondition_checking,
        postcondition_verification=postcondition_verification,
        domain_range_checking=domain_range_checking,
        step_by_step_structure=step_by_step_structure,
        explicit_reasoning=explicit_reasoning,
        anti_pattern_awareness=anti_pattern_awareness,
        state_tracking_score=state_tracking_score,
        verification_score=verification_score,
        reasoning_quality_score=reasoning_quality_score,
        overall_score=overall_score,
        classification=classification
    )


def compare_traces(traces: list[tuple[str, str]]) -> dict:
    """Compare multiple traces and return comparison summary.

    Args:
        traces: List of (name, trace_text) tuples

    Returns:
        Comparison dict with analysis for each and ranking
    """
    analyses = {}
    for name, trace in traces:
        analyses[name] = analyze_reasoning_trace(trace)

    # Rank by overall score
    ranked = sorted(analyses.items(), key=lambda x: x[1].overall_score, reverse=True)

    return {
        "analyses": {name: _analysis_to_dict(a) for name, a in analyses.items()},
        "ranking": [name for name, _ in ranked],
        "best": ranked[0][0] if ranked else None,
        "score_range": {
            "min": min(a.overall_score for a in analyses.values()),
            "max": max(a.overall_score for a in analyses.values()),
            "spread": max(a.overall_score for a in analyses.values()) - min(a.overall_score for a in analyses.values())
        }
    }


def _analysis_to_dict(analysis: BehaviorAnalysis) -> dict:
    """Convert BehaviorAnalysis to dict for JSON serialization."""
    return {
        "indicators": {
            "explicit_state_references": analysis.explicit_state_references,
            "state_progression": analysis.state_progression,
            "state_regression_detected": analysis.state_regression_detected,
            "precondition_checking": analysis.precondition_checking,
            "postcondition_verification": analysis.postcondition_verification,
            "domain_range_checking": analysis.domain_range_checking,
            "step_by_step_structure": analysis.step_by_step_structure,
            "explicit_reasoning": analysis.explicit_reasoning,
            "anti_pattern_awareness": analysis.anti_pattern_awareness,
        },
        "scores": {
            "state_tracking": analysis.state_tracking_score,
            "verification": analysis.verification_score,
            "reasoning_quality": analysis.reasoning_quality_score,
            "overall": analysis.overall_score,
        },
        "classification": analysis.classification
    }


# Example usage and self-test
if __name__ == "__main__":
    # Good trace example
    good_trace = """
    ### Step 1: Identify concepts

    **State before**: classes_discovered: [], properties_discovered: []

    I need to find proteins with GO annotations. Let me search for the relevant classes.

    **Action**: Search for "protein" and "annotation" classes

    **Result**: Found up:Protein and up:GO_Annotation

    **State after**: classes_discovered: [up:Protein, up:GO_Annotation]

    ### Step 2: Find connecting property

    Before constructing a join, I need to verify the domain/range constraints.

    The up:annotation property has:
    - Domain: up:Protein
    - Range: up:Annotation

    This means I can use: ?protein up:annotation ?ann

    **Verification**: Domain/range check passed

    ### Step 3: Construct query

    I should avoid the anti-pattern of using up:classifiedWith directly on proteins,
    because it's a property of annotations, not proteins.

    ```sparql
    SELECT ?protein WHERE {
      ?protein up:annotation ?ann .
      ?ann a up:GO_Annotation .
    }
    ```

    **Verification**: Query uses correct property path, confirmed results match expected types.
    """

    # Poor trace example
    poor_trace = """
    I'll write a query to find proteins with GO annotations.

    ```sparql
    SELECT ?protein WHERE {
      ?protein a up:Protein .
      ?protein rdfs:label ?label .
      FILTER(CONTAINS(?label, "kinase"))
    }
    ```

    This should work.
    """

    print("Analyzing good trace:")
    good_analysis = analyze_reasoning_trace(good_trace)
    print(f"  Overall score: {good_analysis.overall_score:.2f}")
    print(f"  Classification: {good_analysis.classification}")
    print(f"  State tracking: {good_analysis.state_tracking_score:.2f}")
    print(f"  Verification: {good_analysis.verification_score:.2f}")
    print(f"  Reasoning quality: {good_analysis.reasoning_quality_score:.2f}")

    print("\nAnalyzing poor trace:")
    poor_analysis = analyze_reasoning_trace(poor_trace)
    print(f"  Overall score: {poor_analysis.overall_score:.2f}")
    print(f"  Classification: {poor_analysis.classification}")
    print(f"  State tracking: {poor_analysis.state_tracking_score:.2f}")
    print(f"  Verification: {poor_analysis.verification_score:.2f}")
    print(f"  Reasoning quality: {poor_analysis.reasoning_quality_score:.2f}")

    print("\nComparison:")
    comparison = compare_traces([("good", good_trace), ("poor", poor_trace)])
    print(f"  Ranking: {comparison['ranking']}")
    print(f"  Score spread: {comparison['score_range']['spread']:.2f}")
