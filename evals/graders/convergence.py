"""Convergence grader - checks that agent terminates properly."""

from .base import BaseGrader, GradeResult


class ConvergenceGrader(BaseGrader):
    """Check that agent converged within iteration limit.

    Convergence means:
    1. Agent produced a non-empty final answer
    2. Agent terminated within max_iterations
    """

    grader_type: str = "convergence"

    def __init__(self, max_iterations: int = 10):
        """Initialize convergence grader.

        Args:
            max_iterations: Maximum allowed iterations before failure
        """
        self.max_iterations = max_iterations

    def grade(self, transcript: list, answer: str, task: dict = None) -> GradeResult:
        """Grade convergence of the RLM run."""
        iteration_count = len(transcript)

        # Check for valid answer (handle None defensively)
        converged = bool(answer and isinstance(answer, str) and answer.strip() and answer != "No answer provided")

        # Check iteration limit
        within_limit = iteration_count <= self.max_iterations

        # Calculate efficiency score (fewer iterations = better)
        if converged and within_limit:
            efficiency = 1.0 - (iteration_count / self.max_iterations) * 0.5
        else:
            efficiency = 0.0

        passed = converged and within_limit

        # Build reason
        if not converged:
            reason = "Did not converge - no valid answer produced"
        elif not within_limit:
            reason = f"Exceeded iteration limit: {iteration_count} > {self.max_iterations}"
        else:
            reason = f"Converged in {iteration_count} iterations"

        return GradeResult(
            passed=passed,
            score=efficiency,
            reason=reason,
            details={
                'converged': converged,
                'iterations': iteration_count,
                'max_iterations': self.max_iterations,
                'within_limit': within_limit,
                'efficiency': efficiency
            }
        )

    @classmethod
    def from_config(cls, config: dict) -> 'ConvergenceGrader':
        """Create from YAML config."""
        return cls(max_iterations=config.get('max_iterations', 10))
