"""SPARQL structural grader - checks query operator usage."""

from .base import BaseGrader, GradeResult


class SparqlStructuralGrader(BaseGrader):
    """Check SPARQL query uses required structural operators.

    Validates structural patterns like:
    - GRAPH clauses for multi-graph queries
    - SERVICE clauses for federation
    - Property paths (transitive closure operators like +, *)
    - Required triple patterns

    This grader operates on the captured SPARQL query from the trial result.
    """

    grader_type: str = "sparql_structural"

    def __init__(
        self,
        requires_graph: bool = False,
        requires_service: list[str] = None,
        forbids_closure: list[str] = None,
        required_patterns: list[str] = None,
        optional_patterns: list[str] = None,
    ):
        """Initialize SPARQL structural grader.

        Args:
            requires_graph: Whether query must contain GRAPH clause
            requires_service: List of SERVICE endpoints that must be used
            forbids_closure: List of property path patterns that must NOT appear
                           (e.g., ["rdfs:subClassOf+"] for materialized hierarchies)
            required_patterns: List of patterns that must appear in query
                             (e.g., ["up:reviewed true", "FILTER", "OPTIONAL"])
            optional_patterns: List of patterns that earn bonus points if present
        """
        self.requires_graph = requires_graph
        self.requires_service = requires_service or []
        self.forbids_closure = forbids_closure or []
        self.required_patterns = required_patterns or []
        self.optional_patterns = optional_patterns or []

    def grade(self, transcript: list, answer: str, task: dict = None) -> GradeResult:
        """Grade SPARQL structural compliance.

        Args:
            transcript: Execution transcript (may contain query in code blocks)
            answer: Final answer (unused for structural grading)
            task: Task definition (unused for structural grading)

        Returns:
            GradeResult with structural compliance check
        """
        # Extract SPARQL query from transcript
        sparql_query = self._extract_sparql_query(transcript)

        if not sparql_query:
            return GradeResult(
                passed=False,
                score=0.0,
                reason="No SPARQL query found in transcript",
                details={"found_query": False}
            )

        # Normalize query (uppercase keywords, remove extra whitespace)
        query_normalized = " ".join(sparql_query.upper().split())

        # Check requirements
        failures = []
        checks = {}

        # Check GRAPH requirement
        if self.requires_graph:
            has_graph = "GRAPH" in query_normalized
            checks["has_graph"] = has_graph
            if not has_graph:
                failures.append("Missing required GRAPH clause")

        # Check SERVICE requirements
        if self.requires_service:
            missing_services = []
            for service in self.requires_service:
                service_normalized = service.upper()
                if service_normalized not in query_normalized:
                    missing_services.append(service)
            checks["service_usage"] = {
                "required": self.requires_service,
                "missing": missing_services
            }
            if missing_services:
                failures.append(f"Missing required SERVICE endpoints: {', '.join(missing_services)}")

        # Check forbidden patterns
        if self.forbids_closure:
            found_forbidden = []
            for pattern in self.forbids_closure:
                # Remove whitespace from pattern for matching
                pattern_normalized = pattern.replace(" ", "").upper()
                query_no_spaces = sparql_query.replace(" ", "").upper()
                if pattern_normalized in query_no_spaces:
                    found_forbidden.append(pattern)
            checks["forbidden_patterns"] = {
                "forbidden": self.forbids_closure,
                "found": found_forbidden
            }
            if found_forbidden:
                failures.append(f"Query contains forbidden patterns: {', '.join(found_forbidden)}")

        # Check required patterns
        if self.required_patterns:
            missing_patterns = []
            for pattern in self.required_patterns:
                pattern_normalized = pattern.upper()
                if pattern_normalized not in query_normalized:
                    missing_patterns.append(pattern)
            checks["required_patterns"] = {
                "required": self.required_patterns,
                "missing": missing_patterns
            }
            if missing_patterns:
                failures.append(f"Missing required patterns: {', '.join(missing_patterns)}")

        # Check optional patterns (bonus points)
        optional_found = []
        if self.optional_patterns:
            for pattern in self.optional_patterns:
                pattern_normalized = pattern.upper()
                if pattern_normalized in query_normalized:
                    optional_found.append(pattern)
            checks["optional_patterns"] = {
                "optional": self.optional_patterns,
                "found": optional_found
            }

        # Calculate score
        passed = len(failures) == 0
        if passed:
            # Base score 1.0, bonus up to 0.2 for optional patterns
            bonus = len(optional_found) / max(len(self.optional_patterns), 1) * 0.2 if self.optional_patterns else 0
            score = min(1.0 + bonus, 1.2)
        else:
            score = 0.0

        # Build reason
        if passed:
            reason = "All structural requirements met"
            if optional_found:
                reason += f" (bonus: {', '.join(optional_found)})"
        else:
            reason = "; ".join(failures)

        return GradeResult(
            passed=passed,
            score=score,
            reason=reason,
            details={
                "sparql_query": sparql_query[:500],  # Truncate for readability
                "checks": checks,
                "optional_found": optional_found
            }
        )

    def _extract_sparql_query(self, transcript: list) -> str:
        """Extract SPARQL query from transcript.

        Looks for:
        1. Code blocks containing SELECT/CONSTRUCT/ASK/DESCRIBE
        2. Tool calls like sparql_query(...) or sparql_select(...)
        """
        queries = []

        # Extract from code blocks
        code_blocks = self._extract_code_blocks(transcript)
        for code in code_blocks:
            # Look for SPARQL keywords
            if any(kw in code.upper() for kw in ["SELECT", "CONSTRUCT", "ASK", "DESCRIBE"]):
                queries.append(code)

        # Also check outputs for result patterns
        outputs = self._extract_code_outputs(transcript)
        for output in outputs:
            if any(kw in output.upper() for kw in ["SELECT", "CONSTRUCT", "ASK", "DESCRIBE"]):
                queries.append(output)

        # Return the longest query found (likely the most complete)
        return max(queries, key=len) if queries else ""

    @classmethod
    def from_config(cls, config: dict) -> 'SparqlStructuralGrader':
        """Create from YAML config."""
        return cls(
            requires_graph=config.get('requires_graph', False),
            requires_service=config.get('requires_service', []),
            forbids_closure=config.get('forbids_closure', []),
            required_patterns=config.get('required_patterns', []),
            optional_patterns=config.get('optional_patterns', [])
        )
