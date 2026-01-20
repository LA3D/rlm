"""Backend abstraction for RLM execution.

Provides a common interface for different RLM backends (DSPy, claudette).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol, Any, runtime_checkable


@dataclass
class RLMResult:
    """Base result class for RLM execution.

    Attributes:
        answer: Natural language answer to the query
        trajectory: List of execution steps
        iteration_count: Number of iterations taken
        converged: Whether execution converged successfully
        metadata: Additional backend-specific metadata
    """

    answer: str
    trajectory: list[dict]
    iteration_count: int
    converged: bool
    metadata: dict[str, Any]

    def __post_init__(self):
        if self.trajectory is None:
            self.trajectory = []
        if self.metadata is None:
            self.metadata = {}


@runtime_checkable
class RLMBackend(Protocol):
    """Protocol for RLM execution backends.

    Backends must implement the run() method to execute queries
    and return structured results.
    """

    def run(
        self,
        query: str,
        context: str,
        *,
        max_iterations: int = 8,
        max_llm_calls: int = 16,
        verbose: bool = False,
        **kwargs: Any,
    ) -> RLMResult:
        """Execute RLM query with bounded tools.

        Args:
            query: User question to answer
            context: Context string (ontology summary, instructions, etc.)
            max_iterations: Maximum RLM iterations
            max_llm_calls: Maximum LLM calls
            verbose: Whether to print execution trace
            **kwargs: Backend-specific parameters

        Returns:
            RLMResult with answer, trajectory, and metadata

        Raises:
            ValueError: If required parameters are missing
            RuntimeError: If execution fails
        """
        ...


def is_rlm_backend(obj: Any) -> bool:
    """Check if an object implements the RLMBackend protocol.

    Args:
        obj: Object to check

    Returns:
        True if obj implements RLMBackend protocol
    """
    return isinstance(obj, RLMBackend)
