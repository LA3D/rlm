"""Claudette backend wrapper for RLM execution.

Wraps the existing claudette-backed rlm_run function to implement the RLMBackend protocol.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from .backend import RLMResult
from rlm.core import rlm_run


class ClaudetteBackend:
    """Claudette-backed RLM implementation.

    Wraps rlm.core.rlm_run to provide a backend-agnostic interface.

    Attributes:
        ontology_path: Path to ontology file (for GraphMeta creation)
        namespace: Persistent namespace for REPL execution
    """

    def __init__(self, ontology_path: str | Path, namespace: dict | None = None):
        """Initialize Claudette backend.

        Args:
            ontology_path: Path to ontology file
            namespace: Optional namespace dict (created if None)
        """
        self.ontology_path = Path(ontology_path)
        self.namespace = namespace or {}

    def run(
        self,
        query: str,
        context: str,
        *,
        max_iterations: int = 8,
        max_llm_calls: int = 16,  # Not used by claudette backend
        verbose: bool = False,
        model: str = "claude-sonnet-4-5",
        **kwargs: Any,
    ) -> RLMResult:
        """Execute RLM query using claudette backend.

        Args:
            query: User question to answer
            context: Context string (ontology summary, instructions, etc.)
            max_iterations: Maximum RLM iterations
            max_llm_calls: Maximum LLM calls (ignored by claudette backend)
            verbose: Whether to print execution trace
            model: Claude model to use
            **kwargs: Additional parameters passed to rlm_run

        Returns:
            RLMResult with answer, trajectory, and metadata

        Raises:
            ValueError: If required parameters are missing
            RuntimeError: If execution fails
        """
        # Execute rlm_run
        answer, iterations, final_ns = rlm_run(
            query=query,
            context=context,
            ns=self.namespace,
            model=model,
            max_iters=max_iterations,
            verbose=verbose,
            **kwargs,
        )

        # Update namespace
        self.namespace.update(final_ns)

        # Convert iterations to trajectory dicts
        # RLMIteration has code_blocks (list of CodeBlock), not flat code/output
        trajectory = []
        for iteration in iterations:
            # Extract code and output from each code block
            for cb in iteration.code_blocks:
                code_str = cb.code if hasattr(cb, 'code') else str(cb)
                output_str = ""
                if hasattr(cb, 'result') and cb.result:
                    # REPLResult has stdout attribute
                    output_str = cb.result.stdout if hasattr(cb.result, 'stdout') else str(cb.result)

                trajectory.append({
                    "code": code_str,
                    "output": output_str,
                })

        # Check convergence (converged if not at max iterations or if has valid answer)
        converged = len(iterations) < max_iterations or (answer and answer.strip())

        return RLMResult(
            answer=answer,
            trajectory=trajectory,
            iteration_count=len(iterations),
            converged=converged,
            metadata={
                "backend": "claudette",
                "model": model,
                "ontology": str(self.ontology_path),
            },
        )
