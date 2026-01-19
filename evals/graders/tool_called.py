"""Tool called grader - checks that specific tools were invoked."""

import re
from .base import BaseGrader, GradeResult


class ToolCalledGrader(BaseGrader):
    """Check that specific tools/functions were called during execution.

    Useful for regression tests to ensure core functionality is exercised.
    """

    grader_type: str = "tool_called"

    def __init__(
        self,
        required: list[str] = None,
        forbidden: list[str] = None
    ):
        """Initialize tool called grader.

        Args:
            required: List of tool names that MUST be called
            forbidden: List of tool names that must NOT be called
        """
        self.required = required or []
        self.forbidden = forbidden or []

    def grade(self, transcript: list, answer: str, task: dict = None) -> GradeResult:
        """Grade whether required tools were called."""
        codes = self._extract_code_blocks(transcript)
        all_code = "\n".join(codes)

        # Check required tools
        found_required = []
        missing_required = []

        for tool in self.required:
            # Match function calls like tool_name( or tool_name(arg
            pattern = rf'\b{re.escape(tool)}\s*\('
            if re.search(pattern, all_code):
                found_required.append(tool)
            else:
                missing_required.append(tool)

        # Check forbidden tools
        found_forbidden = []

        for tool in self.forbidden:
            pattern = rf'\b{re.escape(tool)}\s*\('
            if re.search(pattern, all_code):
                found_forbidden.append(tool)

        # Calculate pass/fail
        passed = (len(missing_required) == 0) and (len(found_forbidden) == 0)

        if self.required:
            score = len(found_required) / len(self.required)
        else:
            score = 1.0

        if found_forbidden:
            score = 0.0

        # Build reason
        reasons = []
        if missing_required:
            reasons.append(f"Missing required tools: {missing_required}")
        if found_forbidden:
            reasons.append(f"Called forbidden tools: {found_forbidden}")
        if not reasons:
            reasons.append(f"Called all {len(found_required)} required tools")

        return GradeResult(
            passed=passed,
            score=score,
            reason="; ".join(reasons),
            details={
                'found_required': found_required,
                'missing_required': missing_required,
                'found_forbidden': found_forbidden,
                'all_tools_called': self._extract_all_tools(all_code)
            }
        )

    def _extract_all_tools(self, code: str) -> list[str]:
        """Extract all function calls from code."""
        # Match function_name( patterns
        pattern = r'\b([a-z_][a-z0-9_]*)\s*\('
        matches = re.findall(pattern, code, re.IGNORECASE)

        # Filter out common Python builtins
        builtins = {'print', 'len', 'str', 'int', 'float', 'list', 'dict', 'set', 'range', 'type', 'isinstance'}
        return list(set(m for m in matches if m not in builtins))

    @classmethod
    def from_config(cls, config: dict) -> 'ToolCalledGrader':
        """Create from YAML config."""
        return cls(
            required=config.get('required', []),
            forbidden=config.get('forbidden', [])
        )
