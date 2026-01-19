"""Answer contains grader - checks for expected keywords/phrases."""

import re
from .base import BaseGrader, GradeResult


class AnswerContainsGrader(BaseGrader):
    """Check that answer contains expected keywords or phrases.

    Simple but effective for checking factual accuracy.
    """

    grader_type: str = "answer_contains"

    def __init__(
        self,
        must_include: list[str] = None,
        must_exclude: list[str] = None,
        case_sensitive: bool = False
    ):
        """Initialize answer contains grader.

        Args:
            must_include: Keywords/phrases that MUST appear in answer
            must_exclude: Keywords/phrases that must NOT appear (hallucination check)
            case_sensitive: Whether to do case-sensitive matching
        """
        self.must_include = must_include or []
        self.must_exclude = must_exclude or []
        self.case_sensitive = case_sensitive

    def grade(self, transcript: list, answer: str, task: dict = None) -> GradeResult:
        """Grade whether answer contains required keywords."""
        if not answer:
            return GradeResult(
                passed=False,
                score=0.0,
                reason="No answer provided",
                details={'found': [], 'missing': self.must_include}
            )

        check_answer = answer if self.case_sensitive else answer.lower()

        # Check must_include
        found = []
        missing = []

        for keyword in self.must_include:
            check_keyword = keyword if self.case_sensitive else keyword.lower()
            if check_keyword in check_answer:
                found.append(keyword)
            else:
                missing.append(keyword)

        # Check must_exclude
        forbidden_found = []
        for keyword in self.must_exclude:
            check_keyword = keyword if self.case_sensitive else keyword.lower()
            if check_keyword in check_answer:
                forbidden_found.append(keyword)

        # Calculate score
        if self.must_include:
            inclusion_score = len(found) / len(self.must_include)
        else:
            inclusion_score = 1.0

        exclusion_passed = len(forbidden_found) == 0

        passed = len(missing) == 0 and exclusion_passed
        score = inclusion_score if exclusion_passed else 0.0

        # Build reason
        reasons = []
        if missing:
            reasons.append(f"Missing: {missing}")
        if forbidden_found:
            reasons.append(f"Contains forbidden: {forbidden_found}")
        if not reasons:
            reasons.append(f"Found all {len(found)} required keywords")

        return GradeResult(
            passed=passed,
            score=score,
            reason="; ".join(reasons),
            details={
                'found': found,
                'missing': missing,
                'forbidden_found': forbidden_found,
                'inclusion_score': inclusion_score
            }
        )

    @classmethod
    def from_config(cls, config: dict) -> 'AnswerContainsGrader':
        """Create from YAML config."""
        return cls(
            must_include=config.get('must_include', config.get('keywords', [])),
            must_exclude=config.get('must_exclude', []),
            case_sensitive=config.get('case_sensitive', False)
        )
