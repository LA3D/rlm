"""Protocol assertion helpers for RLM tests.

These functions validate RLM protocol invariants:
- Code blocks are present and executed
- Convergence via FINAL/FINAL_VAR (not max_iters fallback)
- REPL outputs are bounded (no full graph dumps)
- Answers are grounded in REPL output
- Expected tools are called
"""

import re
from typing import List, Any, Union
from dataclasses import dataclass


@dataclass
class CodeBlock:
    """Normalized code block structure."""
    code: str
    result: Any = None


@dataclass
class CodeBlockResult:
    """Normalized code block result."""
    stdout: str


@dataclass
class Iteration:
    """Normalized iteration structure compatible with both backends."""
    code_blocks: List[CodeBlock]
    final_answer: str = None


def normalize_claudette_trajectory(iterations: List[Any]) -> List[Iteration]:
    """Convert claudette RLMIteration objects to normalized format.

    Args:
        iterations: List of RLMIteration objects from claudette backend

    Returns:
        List of normalized Iteration objects
    """
    # Already in expected format, but wrap for consistency
    return iterations


def normalize_dspy_trajectory(trajectory: List[dict]) -> List[Iteration]:
    """Convert DSPy trajectory (list of dicts) to normalized format.

    DSPy trajectories are lists of dicts with 'code' and 'output' keys.

    Args:
        trajectory: List of trajectory step dicts from DSPy backend

    Returns:
        List of normalized Iteration objects
    """
    normalized = []

    for step in trajectory:
        code = step.get('code', '')
        output = step.get('output', '')

        # Create a code block with result
        cb = CodeBlock(
            code=code,
            result=CodeBlockResult(stdout=str(output)) if output else None
        )

        # Each step is treated as an iteration
        normalized.append(Iteration(
            code_blocks=[cb],
            final_answer=None  # DSPy doesn't mark final in trajectory
        ))

    return normalized


def normalize_trajectory(trajectory: Union[List[Any], List[dict]]) -> List[Iteration]:
    """Auto-detect and normalize trajectory format.

    Args:
        trajectory: Trajectory from either backend

    Returns:
        List of normalized Iteration objects
    """
    if not trajectory:
        return []

    # Check first element to determine format
    first = trajectory[0]

    if isinstance(first, dict):
        # DSPy format
        return normalize_dspy_trajectory(trajectory)
    else:
        # Claudette format (RLMIteration objects)
        return normalize_claudette_trajectory(trajectory)



def assert_code_blocks_present(iterations: Union[List[Any], List[dict]], min_blocks: int = 1) -> None:
    """Assert that code blocks were executed (RLM protocol requirement).

    Args:
        iterations: List of iterations (auto-normalized from either backend)
        min_blocks: Minimum total code blocks across all iterations

    Raises:
        AssertionError: If fewer than min_blocks code blocks are present
    """
    iterations = normalize_trajectory(iterations)

    total_blocks = sum(len(iter.code_blocks) for iter in iterations)
    assert total_blocks >= min_blocks, (
        f"Expected at least {min_blocks} code blocks, found {total_blocks}. "
        f"RLM protocol requires REPL usage for exploration."
    )

    # Verify at least some code blocks were actually executed
    executed_blocks = sum(
        1 for iter in iterations
        for cb in iter.code_blocks
        if cb.result is not None
    )
    assert executed_blocks > 0, (
        f"Found {total_blocks} code blocks but none were executed. "
        f"Code blocks must have non-None results."
    )


def assert_converged_properly(answer: str, iterations: Union[List[Any], List[dict]]) -> None:
    """Assert convergence via FINAL_VAR/FINAL (not max_iters fallback).

    Proper convergence means the model explicitly returned FINAL(...) or FINAL_VAR(...),
    rather than hitting the max_iters limit and falling back to a synthesized answer.

    Args:
        answer: The final answer string
        iterations: List of iterations (auto-normalized from either backend)

    Raises:
        AssertionError: If answer is a fallback (starts with "[Max iterations]")
    """
    iterations = normalize_trajectory(iterations)

    assert not answer.startswith("[Max iterations]"), (
        f"RLM did not converge properly. Answer is a fallback: {answer[:100]}..."
    )

    # DSPy backend doesn't mark final_answer in trajectory, so skip that check
    # The presence of a non-empty answer is sufficient for DSPy


def assert_bounded_views(iterations: Union[List[Any], List[dict]], max_output_chars: int = 10000) -> None:
    """Assert REPL outputs are bounded (no full graph dumps).

    RLM should use progressive disclosure (e.g., search_by_label, describe_entity)
    rather than dumping entire graphs or large datasets.

    Args:
        iterations: List of iterations (auto-normalized from either backend)
        max_output_chars: Maximum characters in any single REPL output

    Raises:
        AssertionError: If any REPL output exceeds max_output_chars
    """
    iterations = normalize_trajectory(iterations)

    for i, iteration in enumerate(iterations):
        for j, cb in enumerate(iteration.code_blocks):
            if cb.result and cb.result.stdout:
                output_len = len(cb.result.stdout)
                assert output_len <= max_output_chars, (
                    f"Iteration {i+1}, code block {j+1}: "
                    f"REPL output too large ({output_len} chars > {max_output_chars}). "
                    f"This suggests full graph dump instead of bounded views. "
                    f"Output preview: {cb.result.stdout[:200]}..."
                )


def assert_grounded_answer(
    answer: str,
    iterations: Union[List[Any], List[dict]],
    min_score: float = 0.3
) -> None:
    """Assert answer entities appear in REPL output (groundedness check).

    Extracts candidate entities from the answer (capitalized words, URIs) and
    checks if they appear in the REPL outputs. This is a simple heuristic
    groundedness check.

    Args:
        answer: The final answer string
        iterations: List of iterations (auto-normalized from either backend)
        min_score: Minimum fraction of answer entities that must appear in REPL

    Raises:
        AssertionError: If fewer than min_score fraction of entities are grounded
    """
    iterations = normalize_trajectory(iterations)

    # Extract candidate entities from answer
    # Look for: URIs, capitalized words, quoted strings
    entities = set()

    # URIs (http://, https://, urn:, etc.)
    entities.update(re.findall(r'(?:http|https|urn):[^\s<>"{}|\\^`\[\]]+', answer))

    # Capitalized words (2+ chars, not sentence starts)
    words = re.findall(r'\b[A-Z][a-z]+(?:[A-Z][a-z]+)*\b', answer)
    entities.update(w for w in words if len(w) >= 2)

    # Quoted strings
    entities.update(re.findall(r'"([^"]{2,})"', answer))
    entities.update(re.findall(r"'([^']{2,})'", answer))

    if not entities:
        # Answer has no extractable entities, skip check
        return

    # Collect all REPL outputs
    repl_text = ""
    for iteration in iterations:
        for cb in iteration.code_blocks:
            if cb.result and cb.result.stdout:
                repl_text += cb.result.stdout + "\n"

    # Check how many entities appear in REPL output
    grounded_count = sum(1 for entity in entities if entity in repl_text)
    score = grounded_count / len(entities)

    assert score >= min_score, (
        f"Answer is not grounded in REPL output. "
        f"Only {grounded_count}/{len(entities)} entities found in REPL "
        f"(score={score:.2f} < {min_score}). "
        f"Entities: {sorted(entities)[:10]}... "
        f"This suggests hallucination or insufficient exploration."
    )


def assert_tool_called(
    iterations: Union[List[Any], List[dict]],
    function_pattern: str,
    at_least: int = 1
) -> None:
    """Assert expected tools were called.

    Args:
        iterations: List of iterations (auto-normalized from either backend)
        function_pattern: Regex pattern to match function names (e.g., "search_entity|describe_entity")
        at_least: Minimum number of times the pattern should match

    Raises:
        AssertionError: If pattern matches fewer than at_least times
    """
    iterations = normalize_trajectory(iterations)
    pattern = re.compile(function_pattern)

    # Count matches in code blocks
    matches = 0
    for iteration in iterations:
        for cb in iteration.code_blocks:
            if pattern.search(cb.code):
                matches += 1

    assert matches >= at_least, (
        f"Expected '{function_pattern}' to be called at least {at_least} times, "
        f"but found {matches} occurrences. "
        f"This suggests the RLM is not using expected tools."
    )
