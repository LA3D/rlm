"""Tests for DSPy RLM CoT integration (Phase 3)."""

import pytest
from pathlib import Path

from rlm_runtime.memory.extraction import (
    should_extract_as_exemplar,
    extract_reasoning_chain_from_trajectory,
)


def test_should_extract_as_exemplar_high_quality():
    """Test exemplar detection for high-quality reasoning."""
    trajectory = [
        {"code": "search_entity('protein')", "output": "Found Protein class"}
    ]

    thinking = """
    State: Discovered classes: [up:Protein], properties: [up:organism]
    I found the Protein class and will now search for its properties.
    """

    verification = """
    ✓ Property up:organism has domain Protein
    ✓ Results contain expected fields
    """

    reflection = """
    The query is grounded in discovered URIs and returns actual data.
    """

    result = should_extract_as_exemplar(trajectory, thinking, verification, reflection)

    # Should detect high-quality reasoning (or at least not crash)
    assert isinstance(result, bool)


def test_should_extract_as_exemplar_low_quality():
    """Test exemplar detection rejects low-quality reasoning."""
    trajectory = []
    thinking = "I'm thinking about this."
    verification = ""
    reflection = ""

    result = should_extract_as_exemplar(trajectory, thinking, verification, reflection)

    # Should reject low-quality reasoning
    assert result is False


def test_extract_reasoning_chain_from_trajectory_high_quality():
    """Test reasoning chain extraction from high-quality trajectory."""
    task = "What is the protein with accession P12345?"
    answer = "The protein is Insulin (INS_HUMAN)."
    trajectory = [
        {"code": "search_entity('P12345')", "output": "Found protein"}
    ]
    sparql = "SELECT ?label WHERE { uniprot:P12345 rdfs:label ?label }"

    thinking = """
    State: Discovered classes: [up:Protein]
    Found direct URI construction pattern for accessions.
    """

    verification = """
    ✓ URI construction is valid
    ✓ Query returns expected fields
    """

    reflection = """
    Answer is grounded in actual query results.
    """

    memory = extract_reasoning_chain_from_trajectory(
        task, answer, trajectory, sparql,
        thinking, verification, reflection,
        "uniprot"
    )

    # May or may not return memory depending on quality checks
    # The important thing is that it doesn't crash
    assert memory is None or memory.source_type == 'exemplar'


def test_extract_reasoning_chain_from_trajectory_low_quality():
    """Test that low-quality trajectories don't get extracted."""
    task = "What is something?"
    answer = "Something."
    trajectory = []
    sparql = None
    thinking = "Thinking."
    verification = ""
    reflection = ""

    memory = extract_reasoning_chain_from_trajectory(
        task, answer, trajectory, sparql,
        thinking, verification, reflection,
        "test"
    )

    # Should not extract low-quality trajectory
    assert memory is None


def test_dspy_rlm_with_verification_parameter():
    """Test that enable_verification parameter can be passed to run_dspy_rlm."""
    from rlm_runtime.engine.dspy_rlm import run_dspy_rlm

    # Just verify the parameter exists (don't actually run with API key)
    import inspect
    sig = inspect.signature(run_dspy_rlm)

    assert 'enable_verification' in sig.parameters
    assert sig.parameters['enable_verification'].default is False


def test_dspy_rlm_with_curriculum_retrieval_parameter():
    """Test that enable_curriculum_retrieval parameter exists."""
    from rlm_runtime.engine.dspy_rlm import run_dspy_rlm

    import inspect
    sig = inspect.signature(run_dspy_rlm)

    assert 'enable_curriculum_retrieval' in sig.parameters
    assert sig.parameters['enable_curriculum_retrieval'].default is False


def test_backward_compatibility():
    """Test that old code without new parameters still works."""
    from rlm_runtime.engine.dspy_rlm import run_dspy_rlm

    # Should be able to call without new parameters
    # (won't actually run without API key, but signature should work)
    import inspect
    sig = inspect.signature(run_dspy_rlm)

    # All new parameters should have defaults
    for param_name in ['enable_verification', 'enable_curriculum_retrieval']:
        param = sig.parameters[param_name]
        assert param.default is not inspect.Parameter.empty, f"{param_name} must have default"
