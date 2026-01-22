"""Affordance utilization grader - measures use of provided ontology metadata."""

import re
from .base import BaseGrader, GradeResult


class AffordanceUtilizationGrader(BaseGrader):
    """Measure whether agent uses provided ontology affordances.

    Tracks:
    - Utilization rate: URIs/predicates from sense card appearing in SPARQL
    - Hallucination rate: URIs in SPARQL not in ontology
    - Grounding quality: Evidence contains ontology URIs

    This grader requires access to the ontology metadata (sense card) to
    determine which affordances were provided.
    """

    grader_type: str = "affordance_utilization"

    def __init__(
        self,
        min_utilization_rate: float = 0.3,
        max_hallucination_rate: float = 0.1,
        require_evidence_grounding: bool = True
    ):
        """Initialize affordance utilization grader.

        Args:
            min_utilization_rate: Minimum fraction of provided URIs that should appear
            max_hallucination_rate: Maximum fraction of URIs that can be hallucinated
            require_evidence_grounding: Whether evidence must contain ontology URIs
        """
        self.min_utilization_rate = min_utilization_rate
        self.max_hallucination_rate = max_hallucination_rate
        self.require_evidence_grounding = require_evidence_grounding

    def grade(self, transcript: list, answer: str, task: dict = None) -> GradeResult:
        """Grade affordance utilization.

        Args:
            transcript: Execution transcript with code blocks
            answer: Final answer
            task: Task definition with ontology context

        Returns:
            GradeResult with utilization metrics
        """
        # Extract SPARQL query from transcript
        sparql_query = self._extract_sparql_query(transcript)

        if not sparql_query:
            return GradeResult(
                passed=False,
                score=0.0,
                reason="No SPARQL query found",
                details={"found_query": False}
            )

        # Extract evidence if available
        evidence = self._extract_evidence(transcript)

        # Get ontology URIs from task context
        provided_uris = self._get_provided_uris(task)

        # Extract URIs from SPARQL query
        query_uris = self._extract_uris_from_sparql(sparql_query)

        # Calculate utilization rate
        utilized_uris = query_uris.intersection(provided_uris)
        utilization_rate = len(utilized_uris) / len(provided_uris) if provided_uris else 0

        # Calculate hallucination rate (URIs in query not in ontology)
        hallucinated_uris = query_uris - provided_uris
        hallucination_rate = len(hallucinated_uris) / len(query_uris) if query_uris else 0

        # Check evidence grounding
        evidence_grounded = False
        if evidence:
            evidence_str = str(evidence).lower()
            # Check if evidence contains ontology URIs
            evidence_grounded = any(uri.lower() in evidence_str for uri in provided_uris)

        # Calculate score
        score = 0.0
        failures = []

        # Utilization check
        if utilization_rate >= self.min_utilization_rate:
            score += 0.4
        else:
            failures.append(f"Low utilization: {utilization_rate:.1%} < {self.min_utilization_rate:.1%}")

        # Hallucination check
        if hallucination_rate <= self.max_hallucination_rate:
            score += 0.4
        else:
            failures.append(f"High hallucination: {hallucination_rate:.1%} > {self.max_hallucination_rate:.1%}")

        # Evidence grounding check
        if self.require_evidence_grounding:
            if evidence_grounded:
                score += 0.2
            else:
                failures.append("Evidence not grounded in ontology URIs")
        else:
            score += 0.2  # Bonus if not required

        passed = len(failures) == 0

        # Build reason
        if passed:
            reason = f"Good affordance usage: {utilization_rate:.1%} utilization, {hallucination_rate:.1%} hallucination"
        else:
            reason = "; ".join(failures)

        return GradeResult(
            passed=passed,
            score=score,
            reason=reason,
            details={
                "utilization_rate": utilization_rate,
                "hallucination_rate": hallucination_rate,
                "evidence_grounded": evidence_grounded,
                "provided_uri_count": len(provided_uris),
                "query_uri_count": len(query_uris),
                "utilized_uri_count": len(utilized_uris),
                "hallucinated_uri_count": len(hallucinated_uris),
                "utilized_uris": list(utilized_uris)[:10],  # Sample
                "hallucinated_uris": list(hallucinated_uris)[:10]  # Sample
            }
        )

    def _extract_sparql_query(self, transcript: list) -> str:
        """Extract SPARQL query from transcript."""
        queries = []

        # Extract from code blocks
        code_blocks = self._extract_code_blocks(transcript)
        for code in code_blocks:
            if any(kw in code.upper() for kw in ["SELECT", "CONSTRUCT", "ASK", "DESCRIBE"]):
                queries.append(code)

        # Return longest query
        return max(queries, key=len) if queries else ""

    def _extract_evidence(self, transcript: list) -> dict:
        """Extract evidence dict from transcript outputs."""
        # Look for Python dicts in outputs that might be evidence
        outputs = self._extract_code_outputs(transcript)

        for output in outputs:
            # Try to find dict-like structures
            if '{' in output and '}' in output:
                try:
                    import ast
                    # Try to parse as Python literal
                    parsed = ast.literal_eval(output)
                    if isinstance(parsed, dict):
                        return parsed
                except:
                    pass

        return {}

    def _get_provided_uris(self, task: dict) -> set[str]:
        """Extract URIs that were provided in sense card/context.

        Args:
            task: Task definition with context

        Returns:
            Set of URI strings that were made available to the agent
        """
        uris = set()

        if not task:
            return uris

        # Get ontologies from task context
        ctx = task.get('context', {}) or {}
        ontologies = ctx.get('ontologies', []) or []

        for onto in ontologies:
            source = onto.get('source', '')
            if source:
                # Load ontology and extract URIs
                try:
                    from rdflib import Graph, RDF, RDFS, OWL, URIRef
                    from pathlib import Path

                    if not Path(source).exists():
                        continue

                    g = Graph()
                    g.parse(source)

                    # Extract class URIs
                    for s in g.subjects(RDF.type, OWL.Class):
                        if isinstance(s, URIRef):
                            uris.add(str(s))

                    # Extract property URIs
                    for s in g.subjects(RDF.type, OWL.ObjectProperty):
                        if isinstance(s, URIRef):
                            uris.add(str(s))

                    for s in g.subjects(RDF.type, OWL.DatatypeProperty):
                        if isinstance(s, URIRef):
                            uris.add(str(s))

                    # Extract common predicates
                    common_preds = [RDFS.label, RDFS.comment, RDFS.subClassOf,
                                   RDFS.domain, RDFS.range]
                    for pred in common_preds:
                        uris.add(str(pred))

                except Exception:
                    pass  # Skip if can't load

        return uris

    def _extract_uris_from_sparql(self, sparql: str) -> set[str]:
        """Extract URIs from SPARQL query.

        Args:
            sparql: SPARQL query string

        Returns:
            Set of full URI strings found in query
        """
        uris = set()

        # Pattern for full URIs in angle brackets
        full_uri_pattern = r'<(https?://[^>]+)>'
        uris.update(re.findall(full_uri_pattern, sparql))

        # Pattern for prefixed names (e.g., rdfs:label)
        # These are harder to resolve without the prefix definitions,
        # so we'll just extract them as-is for now
        prefixed_pattern = r'\b([a-zA-Z_][\w]*):([a-zA-Z_][\w]*)\b'
        prefixed_names = re.findall(prefixed_pattern, sparql)

        # Add common expanded forms
        common_prefixes = {
            'rdfs': 'http://www.w3.org/2000/01/rdf-schema#',
            'rdf': 'http://www.w3.org/1999/02/22-rdf-syntax-ns#',
            'owl': 'http://www.w3.org/2002/07/owl#',
            'skos': 'http://www.w3.org/2004/02/skos/core#',
            'dcterms': 'http://purl.org/dc/terms/',
            'foaf': 'http://xmlns.com/foaf/0.1/',
            'up': 'http://purl.uniprot.org/core/'
        }

        for prefix, localname in prefixed_names:
            if prefix in common_prefixes:
                uris.add(f"{common_prefixes[prefix]}{localname}")

        return uris

    @classmethod
    def from_config(cls, config: dict) -> 'AffordanceUtilizationGrader':
        """Create from YAML config."""
        return cls(
            min_utilization_rate=config.get('min_utilization_rate', 0.3),
            max_hallucination_rate=config.get('max_hallucination_rate', 0.1),
            require_evidence_grounding=config.get('require_evidence_grounding', True)
        )
