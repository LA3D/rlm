"""SPARQL Query Guard — Validates queries before execution.

Rejects known-bad patterns that cause timeouts on large endpoints
(e.g. UniProt/QLever with 232B triples and PSO/POS index only).

Returns structured rejection with explanation and suggested alternative.
"""

import re
from dataclasses import dataclass, field


@dataclass
class GuardResult:
    """Result of query validation."""
    ok: bool
    reason: str = ""
    suggestion: str = ""
    pattern: str = ""  # Which bad pattern matched

    def to_dict(self) -> dict:
        if self.ok:
            return {'ok': True}
        return {
            'ok': False,
            'error': self.reason,
            'suggestion': self.suggestion,
            'pattern': self.pattern,
        }


@dataclass
class EndpointProfile:
    """Describes endpoint characteristics for query validation.

    This is the enforcement knob — different endpoints have different
    constraints based on their index structure and dataset size.
    """
    name: str
    triple_count: int = 0            # 0 = unknown/small
    has_text_index: bool = False      # QLever text index for CONTAINS
    has_spo_index: bool = True        # Can handle unbound predicates
    safe_type_threshold: int = 100_000  # Max instances for data-scan patterns
    max_unbound_predicate_ok: bool = True  # Can do ?s ?p ?o efficiently

    @classmethod
    def local(cls) -> 'EndpointProfile':
        """Profile for local ontology files — permissive."""
        return cls(name='local', has_spo_index=True, max_unbound_predicate_ok=True)

    @classmethod
    def uniprot(cls) -> 'EndpointProfile':
        """Profile for UniProt QLever — restrictive."""
        return cls(
            name='uniprot',
            triple_count=232_000_000_000,
            has_text_index=False,
            has_spo_index=False,  # Only PSO/POS
            safe_type_threshold=100_000,
            max_unbound_predicate_ok=False,
        )

    @classmethod
    def wikidata(cls) -> 'EndpointProfile':
        """Profile for Wikidata — moderate restrictions."""
        return cls(
            name='wikidata',
            triple_count=17_000_000_000,
            has_text_index=True,
            has_spo_index=True,
            safe_type_threshold=1_000_000,
            max_unbound_predicate_ok=False,  # Still too large for GROUP BY ?p
        )


# === Pattern Detection ===

# Regex patterns for dangerous SPARQL constructs
_UNBOUND_PRED_SCAN = re.compile(
    r'\?\w+\s+\?\w+\s+\?\w+',  # ?s ?p ?o with all variables
    re.IGNORECASE
)

_GROUP_BY_PRED = re.compile(
    r'GROUP\s+BY\s+\?\w+.*$',  # GROUP BY on a variable (often ?p)
    re.IGNORECASE | re.MULTILINE
)

_FILTER_CONTAINS_STR = re.compile(
    r'FILTER\s*\(\s*CONTAINS\s*\(\s*(?:LCASE\s*\(\s*)?STR\s*\(\s*\?\w+\s*\)',
    re.IGNORECASE
)

_FILTER_REGEX_STR = re.compile(
    r'FILTER\s*\(\s*(?:REGEX|regex)\s*\(\s*(?:LCASE\s*\(\s*)?STR\s*\(\s*\?\w+\s*\)',
    re.IGNORECASE
)

# Ontology-scoped type constraints that make queries safe
_ONTOLOGY_TYPE_CONSTRAINTS = {
    'owl:ObjectProperty', 'owl:DatatypeProperty', 'owl:AnnotationProperty',
    'owl:Class', 'rdfs:Class', 'owl:Ontology', 'owl:Restriction',
    'owl:NamedIndividual',
    # Common ontology predicates that scope to schema
    'rdfs:subClassOf', 'rdfs:subPropertyOf', 'rdfs:domain', 'rdfs:range',
    'owl:equivalentClass', 'owl:disjointWith', 'owl:inverseOf',
}


def _is_ontology_scoped(query: str) -> bool:
    """Check if query is scoped to ontology-level types/predicates."""
    q = query.lower()
    for constraint in _ONTOLOGY_TYPE_CONSTRAINTS:
        if constraint.lower() in q:
            return True
    return False


def _has_bound_subject(query: str) -> bool:
    """Check if query has a specific URI as subject (not a variable)."""
    # Look for <http://...> ?p ?o pattern — subject is bound
    return bool(re.search(r'<https?://[^>]+>\s+\?\w+\s+\?\w+', query))


def _has_type_constraint(query: str) -> bool:
    """Check if query constrains subjects with rdf:type or 'a'."""
    q = query.lower()
    # Check for ?s a <Type> or ?s rdf:type <Type>
    return bool(re.search(r'\?\w+\s+(?:a|rdf:type)\s+', q))


def _extract_type_from_query(query: str) -> str | None:
    """Extract the type URI from a type constraint."""
    m = re.search(r'\?\w+\s+(?:a|rdf:type)\s+(\S+)', query)
    return m.group(1) if m else None


# === Validation Rules ===

def _check_unbound_predicate_scan(query: str, profile: EndpointProfile) -> GuardResult | None:
    """Reject ?s ?p ?o GROUP BY ?p on endpoints without SPO index."""
    if profile.max_unbound_predicate_ok:
        return None

    if not _UNBOUND_PRED_SCAN.search(query):
        return None

    # Safe if ontology-scoped
    if _is_ontology_scoped(query):
        return None

    # Safe if subject is a specific URI
    if _has_bound_subject(query):
        return None

    # Check for GROUP BY on a predicate variable
    if _GROUP_BY_PRED.search(query):
        return GuardResult(
            ok=False,
            pattern='unbound_predicate_group_by',
            reason=(
                f"Query groups by an unbound predicate on {profile.name} "
                f"({profile.triple_count:,} triples). This requires a full dataset scan "
                f"and will timeout. The endpoint has PSO/POS index only — predicates must be bound."
            ),
            suggestion=(
                "To discover predicates, describe a sample instance instead:\n"
                "  SELECT DISTINCT ?p ?o WHERE { <specific_URI> ?p ?o } LIMIT 30\n"
                "Or query the ontology schema:\n"
                "  SELECT ?p WHERE { ?p a owl:ObjectProperty }"
            ),
        )

    # Unbound predicate without GROUP BY — still dangerous if no type constraint
    if not _has_type_constraint(query):
        return GuardResult(
            ok=False,
            pattern='unbound_predicate_no_type',
            reason=(
                f"Query has unbound predicate (?s ?p ?o) without type constraint on {profile.name}. "
                f"This scans the entire dataset ({profile.triple_count:,} triples)."
            ),
            suggestion=(
                "Add a type constraint: ?s a <SpecificType> . ?s ?p ?o\n"
                "Or describe a known instance: <specific_URI> ?p ?o LIMIT 30"
            ),
        )

    return None


def _check_filter_contains_on_data(query: str, profile: EndpointProfile) -> GuardResult | None:
    """Reject FILTER(CONTAINS(STR(?var), ...)) on non-ontology queries."""
    if profile.has_text_index:
        return None

    has_contains = _FILTER_CONTAINS_STR.search(query)
    has_regex = _FILTER_REGEX_STR.search(query)

    if not has_contains and not has_regex:
        return None

    # Safe if ontology-scoped (searching property URIs, not data)
    if _is_ontology_scoped(query):
        return None

    filter_type = "FILTER(CONTAINS(STR(...)))" if has_contains else "FILTER(REGEX(STR(...)))"

    return GuardResult(
        ok=False,
        pattern='filter_contains_data',
        reason=(
            f"{filter_type} on data variables requires scanning all matching triples. "
            f"On {profile.name} ({profile.triple_count:,} triples) with no text index, "
            f"this will timeout."
        ),
        suggestion=(
            "Search the ontology schema instead:\n"
            "  SELECT ?prop WHERE {\n"
            "    ?prop a owl:ObjectProperty .\n"
            "    FILTER(CONTAINS(LCASE(STR(?prop)), 'your_term'))\n"
            "  }\n"
            "Or use known predicates from the context/ontology."
        ),
    )


def _check_distinct_predicates_on_large_class(query: str, profile: EndpointProfile) -> GuardResult | None:
    """Reject SELECT DISTINCT ?p WHERE { ?s a <LargeClass> . ?s ?p ?o }."""
    if profile.max_unbound_predicate_ok:
        return None

    # Pattern: has type constraint + unbound predicate + DISTINCT
    if not _has_type_constraint(query):
        return None
    if not _UNBOUND_PRED_SCAN.search(query):
        return None
    if _is_ontology_scoped(query):
        return None
    if _has_bound_subject(query):
        return None

    q_upper = query.upper()
    if 'DISTINCT' not in q_upper and 'GROUP BY' not in q_upper:
        return None

    type_uri = _extract_type_from_query(query)
    type_name = type_uri or "the class"

    return GuardResult(
        ok=False,
        pattern='distinct_predicates_large_class',
        reason=(
            f"Discovering predicates of {type_name} by scanning all its instances "
            f"is too expensive on {profile.name}. Large classes may have billions of triples."
        ),
        suggestion=(
            f"Describe a single instance of {type_name} instead:\n"
            f"  SELECT ?instance WHERE {{ ?instance a {type_uri} }} LIMIT 1\n"
            f"Then: SELECT DISTINCT ?p WHERE {{ <that_instance> ?p ?o }} LIMIT 30\n"
            f"Or query domain/range from the ontology:\n"
            f"  SELECT ?prop WHERE {{ ?prop rdfs:domain {type_uri} }}"
        ),
    )


# === Main Entry Point ===

_RULES = [
    _check_unbound_predicate_scan,
    _check_filter_contains_on_data,
    _check_distinct_predicates_on_large_class,
]


def validate(query: str, profile: EndpointProfile) -> GuardResult:
    """Validate a SPARQL query against endpoint-specific safety rules.

    Args:
        query: SPARQL query string
        profile: Endpoint characteristics

    Returns:
        GuardResult with ok=True if safe, or ok=False with reason/suggestion
    """
    for rule in _RULES:
        result = rule(query, profile)
        if result is not None:
            return result
    return GuardResult(ok=True)
