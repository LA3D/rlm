"""Groundedness grader - checks if answer is supported by REPL evidence."""

import re
from .base import BaseGrader, GradeResult


class GroundednessGrader(BaseGrader):
    """Check that final answer is grounded in REPL observations.

    This is critical for research-style agents to prevent hallucination.
    An answer is grounded if its key claims appear in the REPL output.
    """

    grader_type: str = "groundedness"

    def __init__(
        self,
        required_evidence: list[dict] = None,
        min_groundedness_score: float = 0.5
    ):
        """Initialize groundedness grader.

        Args:
            required_evidence: List of patterns that must appear in transcript
                              [{"pattern": "regex", "source": "tool_name"}]
            min_groundedness_score: Minimum ratio of grounded claims (0.0-1.0)
        """
        self.required_evidence = required_evidence or []
        self.min_groundedness_score = min_groundedness_score

    def grade(self, transcript: list, answer: str, task: dict = None) -> GradeResult:
        """Grade groundedness of the answer.

        Checks:
        1. Required evidence patterns appear in transcript
        2. Key entities/URIs mentioned in answer appear in REPL output
        """
        if not answer or answer == "No answer provided":
            return GradeResult(
                passed=False,
                score=0.0,
                reason="No answer provided",
                details={'groundedness_score': 0.0}
            )

        # Collect all REPL outputs
        outputs = self._extract_code_outputs(transcript)
        all_output = "\n".join(outputs)

        # Check required evidence
        missing_evidence = []
        for evidence in self.required_evidence:
            pattern = evidence.get('pattern', '')
            if pattern and not re.search(pattern, all_output, re.IGNORECASE):
                missing_evidence.append(pattern)

        # Extract entities from answer (URIs, class names, etc.)
        answer_entities = self._extract_entities(answer)

        # Check how many answer entities appear in REPL output
        grounded_entities = []
        ungrounded_entities = []

        for entity in answer_entities:
            if self._entity_in_output(entity, all_output):
                grounded_entities.append(entity)
            else:
                ungrounded_entities.append(entity)

        # Calculate groundedness score
        if answer_entities:
            groundedness_score = len(grounded_entities) / len(answer_entities)
        else:
            # No extractable entities - check if answer references output
            groundedness_score = 1.0 if any(e in answer.lower() for e in ['found', 'result', 'shows']) else 0.5

        # Determine pass/fail
        passed = (
            len(missing_evidence) == 0 and
            groundedness_score >= self.min_groundedness_score
        )

        return GradeResult(
            passed=passed,
            score=groundedness_score,
            reason=self._build_reason(missing_evidence, ungrounded_entities, groundedness_score),
            details={
                'groundedness_score': groundedness_score,
                'grounded_entities': grounded_entities,
                'ungrounded_entities': ungrounded_entities,
                'missing_evidence': missing_evidence,
                'total_entities': len(answer_entities)
            }
        )

    def _extract_entities(self, text: str) -> list[str]:
        """Extract entity references from text."""
        entities = []

        # URIs
        uri_pattern = r'(?:https?://|urn:)[^\s<>\'"]+|<[^>]+>'
        entities.extend(re.findall(uri_pattern, text))

        # Prefixed names (prov:Activity, owl:Class, etc.)
        prefixed_pattern = r'\b[a-z]+:[A-Z][a-zA-Z0-9_]*\b'
        entities.extend(re.findall(prefixed_pattern, text))

        # CamelCase class names
        camel_pattern = r'\b[A-Z][a-z]+(?:[A-Z][a-z]+)+\b'
        entities.extend(re.findall(camel_pattern, text))

        return list(set(entities))

    def _entity_in_output(self, entity: str, output: str) -> bool:
        """Check if entity appears in REPL output."""
        # Direct match
        if entity.lower() in output.lower():
            return True

        # For prefixed names, check the local part
        if ':' in entity:
            local_part = entity.split(':')[-1]
            if local_part.lower() in output.lower():
                return True

        return False

    def _build_reason(
        self,
        missing_evidence: list,
        ungrounded: list,
        score: float
    ) -> str:
        """Build human-readable reason string."""
        reasons = []

        if missing_evidence:
            reasons.append(f"Missing required evidence: {missing_evidence}")

        if ungrounded:
            reasons.append(f"Ungrounded entities: {ungrounded[:3]}")

        if score < self.min_groundedness_score:
            reasons.append(f"Groundedness {score:.1%} < required {self.min_groundedness_score:.1%}")

        if not reasons:
            return f"Answer is well-grounded ({score:.1%})"

        return "; ".join(reasons)

    @classmethod
    def from_config(cls, config: dict) -> 'GroundednessGrader':
        """Create from YAML config."""
        return cls(
            required_evidence=config.get('required_evidence', []),
            min_groundedness_score=config.get('min_groundedness_score', 0.5)
        )
