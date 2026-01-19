"""Base grader class for RLM evaluations."""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any


@dataclass
class GradeResult:
    """Result of grading a single trial."""
    passed: bool
    score: float = 1.0  # 0.0 to 1.0
    reason: str = ""
    details: dict = field(default_factory=dict)

    def __bool__(self):
        return self.passed


class BaseGrader(ABC):
    """Abstract base class for eval graders.

    Graders evaluate RLM trial outcomes and return GradeResult objects.
    Each grader focuses on one aspect of evaluation (groundedness,
    convergence, answer quality, etc.).
    """

    grader_type: str = "base"

    @abstractmethod
    def grade(
        self,
        transcript: list,
        answer: str,
        task: dict = None
    ) -> GradeResult:
        """Grade a single trial.

        Args:
            transcript: List of RLMIteration objects (or dicts)
            answer: Final answer from the RLM run
            task: Optional task definition for context

        Returns:
            GradeResult with pass/fail and details
        """
        pass

    @classmethod
    def from_config(cls, config: dict) -> 'BaseGrader':
        """Create grader from YAML config dict.

        Override in subclasses to handle specific config keys.
        """
        return cls()

    def _extract_code_outputs(self, transcript: list) -> list[str]:
        """Extract all REPL stdout outputs from transcript."""
        outputs = []
        for iteration in transcript:
            # Handle both RLMIteration objects and dicts
            code_blocks = iteration.get('code_blocks', []) if isinstance(iteration, dict) else getattr(iteration, 'code_blocks', [])

            for block in code_blocks:
                if isinstance(block, dict):
                    result = block.get('result', {})
                    stdout = result.get('stdout', '') if isinstance(result, dict) else ''
                else:
                    stdout = block.result.stdout if block.result else ''

                if stdout:
                    outputs.append(stdout)
        return outputs

    def _extract_code_blocks(self, transcript: list) -> list[str]:
        """Extract all code blocks from transcript."""
        codes = []
        for iteration in transcript:
            code_blocks = iteration.get('code_blocks', []) if isinstance(iteration, dict) else getattr(iteration, 'code_blocks', [])

            for block in code_blocks:
                if isinstance(block, dict):
                    code = block.get('code', '')
                else:
                    code = block.code

                if code:
                    codes.append(code)
        return codes

    def _extract_errors(self, transcript: list) -> list[str]:
        """Extract all stderr outputs from transcript."""
        errors = []
        for iteration in transcript:
            code_blocks = iteration.get('code_blocks', []) if isinstance(iteration, dict) else getattr(iteration, 'code_blocks', [])

            for block in code_blocks:
                if isinstance(block, dict):
                    result = block.get('result', {})
                    stderr = result.get('stderr', '') if isinstance(result, dict) else ''
                else:
                    stderr = block.result.stderr if block.result else ''

                if stderr:
                    errors.append(stderr)
        return errors
