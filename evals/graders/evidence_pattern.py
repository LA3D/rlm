"""Evidence pattern grader - checks for expected function calls/outputs."""

import re
from .base import BaseGrader, GradeResult


class EvidencePatternGrader(BaseGrader):
    """Check that required evidence patterns appear in transcript.

    Validates that the agent used appropriate tools and got expected outputs.
    """

    grader_type: str = "evidence_pattern"

    def __init__(self, required: list[dict] = None):
        """Initialize evidence pattern grader.

        Args:
            required: List of required patterns
                [{"function": "search_entity|describe_entity", "contains": "Activity"}]
        """
        self.required = required or []

    def grade(self, transcript: list, answer: str, task: dict = None) -> GradeResult:
        """Grade whether required evidence patterns appear."""
        codes = self._extract_code_blocks(transcript)
        outputs = self._extract_code_outputs(transcript)

        all_code = "\n".join(codes)
        all_output = "\n".join(outputs)

        found_patterns = []
        missing_patterns = []

        for pattern in self.required:
            if self._pattern_matched(pattern, all_code, all_output):
                found_patterns.append(pattern)
            else:
                missing_patterns.append(pattern)

        if self.required:
            score = len(found_patterns) / len(self.required)
        else:
            score = 1.0

        passed = len(missing_patterns) == 0

        if passed:
            reason = f"Found all {len(found_patterns)} required patterns"
        else:
            reason = f"Missing patterns: {[p.get('function', p) for p in missing_patterns]}"

        return GradeResult(
            passed=passed,
            score=score,
            reason=reason,
            details={
                'found': found_patterns,
                'missing': missing_patterns,
                'total_required': len(self.required)
            }
        )

    def _pattern_matched(self, pattern: dict, code: str, output: str) -> bool:
        """Check if a single pattern is matched."""
        # Check function call
        function_pattern = pattern.get('function', '')
        if function_pattern:
            # Support OR patterns like "search_entity|describe_entity"
            functions = function_pattern.split('|')
            function_found = any(f in code for f in functions)
            if not function_found:
                return False

        # Check output contains
        contains_pattern = pattern.get('contains', '')
        if contains_pattern:
            if contains_pattern.lower() not in output.lower():
                return False

        # Check output matches regex
        regex_pattern = pattern.get('regex', '')
        if regex_pattern:
            if not re.search(regex_pattern, output, re.IGNORECASE):
                return False

        return True

    @classmethod
    def from_config(cls, config: dict) -> 'EvidencePatternGrader':
        """Create from YAML config."""
        return cls(required=config.get('required', []))
