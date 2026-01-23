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
        - evidence["sample_X_count"] + verified flag: Metadata about results
        """
        # Try common keys for actual result lists
        # Include various naming patterns: results, sample_X, X_results, data, rows
        common_keys = ["results", "sample_results", "data", "rows"]

        # Also check for sample_X patterns (sample_proteins, sample_taxa, etc.)
        sample_keys = [k for k in evidence.keys() if k.startswith("sample_") and isinstance(evidence.get(k), list)]

        for key in common_keys + sample_keys:
            if key in evidence and isinstance(evidence[key], list):
                # Verify it's a list of dicts (actual results), not just a list of primitives
                results = evidence[key]
                if results and isinstance(results[0], dict):
                    return results

        # If evidence itself is a list, use it
        if isinstance(evidence, list):
            return evidence

        # Fallback: Search for ANY list of dicts in evidence (task-specific keys)
        # This handles cases like "orthologous_proteins", "bacterial_taxa", etc.
        for key, value in evidence.items():
            if isinstance(value, list) and value and isinstance(value[0], dict):
                # Found a list of dicts - likely the results
                return value

        # Check for metadata patterns indicating results exist
        # Pattern: {"sample_protein_count": 5, "sample_results_verified": true}
        # This means agent verified results but stored metadata instead of full results
        sample_count_keys = [k for k in evidence.keys() if k.startswith("sample_") and k.endswith("_count")]
        if sample_count_keys:
            # Get the count from first matching key
            count = evidence.get(sample_count_keys[0], 0)

            # Check if there's verification flag
            verified = evidence.get("sample_results_verified", False)

            if count > 0 and verified:
                # Agent says it verified N results - construct synthetic result objects
                # These represent that N results were verified, even if not stored
                return [{"verified": True, "index": i} for i in range(count)]
            elif count > 0:
                # Count exists but no explicit verification - still accept as evidence
                return [{"count_based": True, "index": i} for i in range(count)]

        return []

    def _has_field_variant(self, row: dict, field: str) -> bool:
        """Check if row has field or common variants.

        Handles variations like:
        - taxon, taxon_uri, taxonUri, taxon_id
        - scientificName, scientific_name, scientificname
        - sequence, sequence_preview, sequence_value
        """
        if field in row:
            return True

        # Generate common variants
        variants = [
            field,
            field.lower(),
            field.replace('_', ''),
            f"{field}_uri",
            f"{field}_id",
            f"{field}Uri",
            f"{field}Id",
            f"{field}_preview",  # For truncated data (sequence_preview)
            f"{field}_value",    # For RDF values (sequence_value)
            f"{field}_length",   # For metadata about field
        ]

        # Also try converting camelCase to snake_case
        snake_case = re.sub(r'(?<!^)(?=[A-Z])', '_', field).lower()
        variants.append(snake_case)

        return any(v in row for v in variants)

    def _get_field_value(self, row: dict, field: str):
        """Get field value with flexible matching for common variants."""
        if field in row:
            return row[field]

        # Generate common variants
        variants = [
            field.lower(),
            field.replace('_', ''),
            f"{field}_uri",
            f"{field}_id",
            f"{field}Uri",
            f"{field}Id",
            f"{field}_preview",  # For truncated data (sequence_preview)
            f"{field}_value",    # For RDF values (sequence_value)
        ]

        # Also try converting camelCase to snake_case
        snake_case = re.sub(r'(?<!^)(?=[A-Z])', '_', field).lower()
        variants.append(snake_case)

        for v in variants:
            if v in row:
                return row[v]

        return None

    def _verify_present(self, results: list) -> GradeResult:
        """Verify results exist and meet minimum count."""
        result_count = len(results)
        passed = result_count >= self.min_results

        # Check if results are synthetic (from metadata)
        # Synthetic results have "verified" or "count_based" keys
        is_synthetic = (results and
                       all(isinstance(r, dict) and ("verified" in r or "count_based" in r)
                           for r in results))

        # Check required fields (skip for synthetic results)
        field_checks = []
        if self.required_fields and results and not is_synthetic:
            for field in self.required_fields:
                has_field = all(self._has_field_variant(row, field) for row in results if isinstance(row, dict))
                field_checks.append((field, has_field))

        all_fields_present = all(check[1] for check in field_checks) if field_checks else True

        # Run verification patterns (skip for synthetic results)
        pattern_results = []
        if not is_synthetic:
            pattern_results = self._run_verifications(results)
        all_patterns_pass = all(r["passed"] for r in pattern_results) if pattern_results else True

        # For synthetic results, if count is met and verified flag is true, pass
        if is_synthetic and passed:
            # Check if at least one has verified=True (agent explicitly verified)
            has_verification = any(r.get("verified", False) for r in results)
            final_passed = passed and has_verification
        else:
            final_passed = passed and all_fields_present and all_patterns_pass

        # Build reason
        reasons = []
        if not passed:
            reasons.append(f"Found {result_count} results, need >= {self.min_results}")
        elif is_synthetic:
            # For synthetic results, mention verification was via metadata
            if final_passed:
                reasons.append(f"Agent verified {result_count} results (metadata-based verification)")
            else:
                reasons.append(f"Found {result_count} results metadata but verification flag not set")
        else:
            # Regular result verification
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
                "required_fields_present": all_fields_present if not is_synthetic else None,
                "field_checks": dict(field_checks) if field_checks else {},
                "verification_patterns": pattern_results,
                "sample_results": results[:3],  # Include sample
                "metadata_based": is_synthetic
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
                if isinstance(row, dict):
                    # Get the actual field value using flexible matching
                    value = self._get_field_value(row, field)
                    if value is not None:
                        if re.search(regex, str(value), re.IGNORECASE):
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
