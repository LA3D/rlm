"""Outcome verification grader - checks actual results, not execution path.

Follows Anthropic's guidance: "Grade outcomes, not paths."
Instead of checking if specific SPARQL patterns were used, verify that
the actual results satisfy the task requirements.
"""

import re
from .base import BaseGrader, GradeResult


class OutcomeVerificationGrader(BaseGrader):
    """Verify agent produced correct outcomes, regardless of path taken.

    This grader checks what the agent achieved (results, state changes),
    not how it achieved it (specific tool sequences or query patterns).

    Example: For "find bacterial taxa", check if results ARE bacteria,
    not whether the query used rdfs:subClassOf vs rdfs:subClassOf+.
    """

    grader_type: str = "outcome_verification"

    def __init__(
        self,
        result_type: str = "present",  # present, absent, contains, count
        min_results: int = 1,
        max_results: int = None,
        required_fields: list[str] = None,
        verification_patterns: list[dict] = None
    ):
        """Initialize outcome verifier.

        Args:
            result_type: Type of verification
                - "present": Results must exist (any non-empty result)
                - "absent": Results must be empty/none
                - "contains": Results must contain specific values
                - "count": Result count must be in range
            min_results: Minimum number of results (for "present"/"count")
            max_results: Maximum number of results (for "count")
            required_fields: Fields that must be present in result rows
            verification_patterns: List of dicts with verification rules
                [{"field": "taxon", "pattern": "taxonomy/", "matches": "all|any"}]
        """
        self.result_type = result_type
        self.min_results = min_results
        self.max_results = max_results
        self.required_fields = required_fields or []
        self.verification_patterns = verification_patterns or []

    def grade(self, transcript: list, answer: str, task: dict = None) -> GradeResult:
        """Grade based on actual outcomes in evidence/results.

        Extracts results from evidence dict and verifies they meet requirements.
        """
        # Extract evidence from transcript
        evidence = self._extract_evidence(transcript)

        if not evidence:
            return GradeResult(
                passed=False,
                score=0.0,
                reason="No evidence/results found in transcript",
                details={"found_evidence": False}
            )

        # Extract results (look for common patterns)
        results = self._extract_results(evidence)

        # Verify based on result_type
        if self.result_type == "present":
            return self._verify_present(results)
        elif self.result_type == "absent":
            return self._verify_absent(results)
        elif self.result_type == "contains":
            return self._verify_contains(results)
        elif self.result_type == "count":
            return self._verify_count(results)
        else:
            return GradeResult(
                passed=False,
                score=0.0,
                reason=f"Unknown result_type: {self.result_type}",
                details={}
            )

    def _extract_evidence(self, transcript: list) -> dict:
        """Extract evidence dict from transcript.

        Looks for evidence in DSPy result objects.
        """
        # Try to find evidence in transcript
        for item in transcript:
            if isinstance(item, dict):
                if "evidence" in item:
                    return item["evidence"]
                # Also check in nested structures
                for key, value in item.items():
                    if isinstance(value, dict) and "evidence" in value:
                        return value["evidence"]

        return {}

    def _extract_results(self, evidence: dict) -> list[dict]:
        """Extract result rows from evidence dict.

        Common patterns:
        - evidence["results"]: List of result dicts
        - evidence["sample_results"]: Sample of results
        - evidence["data"]: Result data
        """
        # Try common keys
        for key in ["results", "sample_results", "data", "rows"]:
            if key in evidence and isinstance(evidence[key], list):
                return evidence[key]

        # If evidence itself is a list, use it
        if isinstance(evidence, list):
            return evidence

        return []

    def _verify_present(self, results: list) -> GradeResult:
        """Verify results exist and meet minimum count."""
        result_count = len(results)
        passed = result_count >= self.min_results

        # Check required fields
        field_checks = []
        if self.required_fields and results:
            for field in self.required_fields:
                has_field = all(field in row for row in results if isinstance(row, dict))
                field_checks.append((field, has_field))

        all_fields_present = all(check[1] for check in field_checks) if field_checks else True

        # Run verification patterns
        pattern_results = self._run_verifications(results)
        all_patterns_pass = all(r["passed"] for r in pattern_results)

        final_passed = passed and all_fields_present and all_patterns_pass

        # Build reason
        reasons = []
        if not passed:
            reasons.append(f"Found {result_count} results, need >= {self.min_results}")
        if not all_fields_present:
            missing = [f for f, ok in field_checks if not ok]
            reasons.append(f"Missing required fields: {missing}")
        if not all_patterns_pass:
            failed = [r["rule"] for r in pattern_results if not r["passed"]]
            reasons.append(f"Verification failed: {failed}")

        if not reasons:
            reasons.append(f"Found {result_count} results with required properties")

        return GradeResult(
            passed=final_passed,
            score=1.0 if final_passed else 0.0,
            reason="; ".join(reasons),
            details={
                "result_count": result_count,
                "required_fields_present": all_fields_present,
                "field_checks": dict(field_checks),
                "verification_patterns": pattern_results,
                "sample_results": results[:3]  # Include sample
            }
        )

    def _verify_absent(self, results: list) -> GradeResult:
        """Verify no results were returned."""
        passed = len(results) == 0
        return GradeResult(
            passed=passed,
            score=1.0 if passed else 0.0,
            reason="No results found (as expected)" if passed else f"Found {len(results)} results, expected none",
            details={"result_count": len(results)}
        )

    def _verify_contains(self, results: list) -> GradeResult:
        """Verify results contain specific values."""
        # Run verification patterns
        pattern_results = self._run_verifications(results)
        passed = all(r["passed"] for r in pattern_results)

        return GradeResult(
            passed=passed,
            score=1.0 if passed else 0.0,
            reason="All verification patterns matched" if passed else "Some patterns did not match",
            details={
                "result_count": len(results),
                "verification_patterns": pattern_results
            }
        )

    def _verify_count(self, results: list) -> GradeResult:
        """Verify result count is in range."""
        count = len(results)
        passed = count >= self.min_results
        if self.max_results is not None:
            passed = passed and count <= self.max_results

        reason = f"Found {count} results"
        if self.max_results is not None:
            reason += f" (expected {self.min_results}-{self.max_results})"
        else:
            reason += f" (expected >= {self.min_results})"

        return GradeResult(
            passed=passed,
            score=1.0 if passed else 0.0,
            reason=reason,
            details={"result_count": count}
        )

    def _run_verifications(self, results: list) -> list[dict]:
        """Run verification patterns on results."""
        pattern_results = []

        for pattern in self.verification_patterns:
            field = pattern.get("field")
            regex = pattern.get("pattern")
            match_type = pattern.get("matches", "any")  # any or all

            if not field or not regex:
                continue

            matches = []
            for row in results:
                if isinstance(row, dict) and field in row:
                    value = str(row[field])
                    if re.search(regex, value, re.IGNORECASE):
                        matches.append(True)
                    else:
                        matches.append(False)

            # Evaluate based on match_type
            if match_type == "all":
                passed = len(matches) > 0 and all(matches)
            else:  # any
                passed = any(matches)

            pattern_results.append({
                "rule": f"{field} matches /{regex}/",
                "passed": passed,
                "match_count": sum(matches),
                "total_checked": len(matches)
            })

        return pattern_results

    @classmethod
    def from_config(cls, config: dict) -> 'OutcomeVerificationGrader':
        """Create from YAML config."""
        return cls(
            result_type=config.get("result_type", "present"),
            min_results=config.get("min_results", 1),
            max_results=config.get("max_results"),
            required_fields=config.get("required_fields", []),
            verification_patterns=config.get("verification_patterns", [])
        )
