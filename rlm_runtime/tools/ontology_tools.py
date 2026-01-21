"""Bounded tool surface wrappers for ontology exploration.

Wraps rlm.ontology functions with enforced limits and LLM-friendly docstrings.
"""

import re
from typing import Callable
from rlm.ontology import GraphMeta, search_entity, describe_entity, probe_relationships


def _inject_limit_select(query: str, limit: int) -> tuple[str, bool]:
    """Inject LIMIT clause into SELECT query if not present.

    Args:
        query: SPARQL query string
        limit: Limit value to inject

    Returns:
        Tuple of (modified_query, was_injected)
        - modified_query: Query with LIMIT added if it was missing
        - was_injected: True if LIMIT was added, False if already present
    """
    q = query.strip()
    q_upper = q.upper()
    if "SELECT" not in q_upper:
        return q, False
    if re.search(r"\bLIMIT\s+\d+\b", q_upper):
        return q, False
    # LIMIT must come after ORDER BY in SPARQL, so just append at the end
    return q.rstrip() + f" LIMIT {int(limit)}", True


def make_search_entity_tool(meta: GraphMeta) -> Callable:
    """Create a bounded search_entity tool for the given GraphMeta.

    Args:
        meta: GraphMeta instance to search

    Returns:
        Callable tool function with signature: search_entity(query, limit=5, search_in='all')
        Limit is clamped to [1, 10] for safety.
    """

    def search_entity_tool(query: str, limit: int = 5, search_in: str = 'all') -> list:
        """Search for entities by label, IRI, or localname.

        Use this to find entities in the ontology that match your search terms.
        Returns matching URIs with labels and match type.

        Args:
            query: Search string (case-insensitive substring match)
            limit: Maximum results to return (1-10, default 5)
            search_in: Where to search - 'label', 'iri', 'localname', or 'all' (default)

        Returns:
            List of dicts: [{'uri': str, 'label': str, 'match_type': str}, ...]

        Example:
            results = search_entity('Activity', limit=5)
            for r in results:
                print(f"{r['label']} ({r['uri']})")
        """
        # Clamp limit to safe bounds
        clamped_limit = max(1, min(10, limit))
        return search_entity(meta, query, limit=clamped_limit, search_in=search_in)

    return search_entity_tool


def make_describe_entity_tool(meta: GraphMeta) -> Callable:
    """Create a bounded describe_entity tool for the given GraphMeta.

    Args:
        meta: GraphMeta instance containing entities

    Returns:
        Callable tool function with signature: describe_entity(uri, limit=15)
        Limit is clamped to [1, 25] for safety.
    """

    def describe_entity_tool(uri: str, limit: int = 15) -> dict:
        """Get entity description with types and outgoing relationships.

        Use this to inspect a specific entity's structure, types, and relationships.
        Supports prefixed URIs like 'prov:Activity' or full URIs.

        Args:
            uri: URI of entity to describe (supports prefixed forms like 'prov:Activity')
            limit: Max number of outgoing triples to sample (1-25, default 15)

        Returns:
            Dict with:
                - 'uri': str - Entity URI
                - 'label': str - Human-readable label
                - 'types': list[str] - RDF types of entity
                - 'comment': str | None - rdfs:comment value if present
                - 'outgoing_sample': list[tuple] - Sample outgoing triples as (predicate, object) pairs

        Example:
            info = describe_entity('prov:Activity', limit=10)
            print(info['label'])
            for predicate, obj in info['outgoing_sample']:
                print(f"  {predicate} -> {obj}")
        """
        # Clamp limit to safe bounds
        clamped_limit = max(1, min(25, limit))
        return describe_entity(meta, uri, limit=clamped_limit)

    return describe_entity_tool


def make_probe_relationships_tool(meta: GraphMeta) -> Callable:
    """Create a bounded probe_relationships tool for the given GraphMeta.

    Args:
        meta: GraphMeta instance containing entities

    Returns:
        Callable tool function with signature: probe_relationships(uri, predicate=None, direction='both', limit=10)
        Limit is clamped to [1, 15] for safety.
    """

    def probe_relationships_tool(
        uri: str,
        predicate: str = None,
        direction: str = 'both',
        limit: int = 10
    ) -> dict:
        """Get one-hop neighbors of an entity, optionally filtered by predicate.

        Use this to explore what entities are connected to a given URI.
        Shows incoming relationships, outgoing relationships, or both.

        Args:
            uri: URI of entity to probe (supports prefixed forms like 'prov:Activity')
            predicate: Optional predicate URI to filter by (supports prefixed forms)
            direction: 'out' (outgoing), 'in' (incoming), or 'both' (default)
            limit: Maximum neighbors to return per direction (1-15, default 10)

        Returns:
            Dict with:
                - 'uri': str - Entity URI
                - 'label': str - Entity label
                - 'outgoing': list[dict] - Outgoing relationships (if direction='out' or 'both')
                - 'incoming': list[dict] - Incoming relationships (if direction='in' or 'both')
                - Each relationship dict has: predicate, pred_label, object/subject, obj_label/subj_label

        Example:
            neighbors = probe_relationships('prov:Activity', direction='out', limit=5)
            for rel in neighbors['outgoing']:
                print(f"  {rel['pred_label']} -> {rel['obj_label']}")
        """
        # Clamp limit to safe bounds
        clamped_limit = max(1, min(15, limit))
        return probe_relationships(
            meta, uri, predicate=predicate, direction=direction, limit=clamped_limit
        )

    return probe_relationships_tool


def make_sparql_select_tool(meta: GraphMeta, max_limit: int = 100) -> Callable:
    """Create a bounded SPARQL SELECT tool for the given GraphMeta.

    Automatically injects LIMIT clause if missing to prevent unbounded queries.

    Args:
        meta: GraphMeta instance containing the graph
        max_limit: Maximum LIMIT value to inject (default 100)

    Returns:
        Callable tool function with signature: sparql_select(query)
        LIMIT will be automatically injected if missing.
    """

    def sparql_select_tool(query: str) -> list:
        """Execute a SPARQL SELECT query on the ontology.

        Use this to query the ontology when you need precise control over the query structure.
        LIMIT will be automatically added if missing to prevent unbounded queries.

        Args:
            query: SPARQL SELECT query string

        Returns:
            List of result bindings (dicts mapping variable names to values)

        Example:
            results = sparql_select('''
                PREFIX prov: <http://www.w3.org/ns/prov#>
                SELECT ?activity WHERE {
                    ?activity a prov:Activity .
                }
            ''')
            for row in results:
                print(row['activity'])

        Note:
            If your query doesn't include a LIMIT clause, one will be automatically
            added with a default value to ensure bounded execution.
        """
        # Inject LIMIT if missing
        modified_query, was_injected = _inject_limit_select(query, max_limit)

        # Execute query on the graph
        result_set = meta.graph.query(modified_query)

        # Convert to list of dicts
        if not hasattr(result_set, 'vars'):
            # Not a SELECT query, return empty list
            return []

        return [
            {str(var): str(row[i]) for i, var in enumerate(result_set.vars)}
            for row in result_set
        ]

    return sparql_select_tool


def make_ontology_tools(meta: GraphMeta, include_sparql: bool = True) -> dict[str, Callable]:
    """Create all bounded ontology tools for the given GraphMeta.

    Convenience function to create all tool wrappers at once.

    Args:
        meta: GraphMeta instance for the ontology
        include_sparql: Whether to include the sparql_select tool (default True)

    Returns:
        Dict mapping tool names to tool functions:
            - 'search_entity': Search for entities by label/IRI
            - 'describe_entity': Get bounded description of an entity
            - 'probe_relationships': Explore one-hop neighbors
            - 'sparql_select': Execute SPARQL SELECT queries (if include_sparql=True)
    """
    tools = {
        'search_entity': make_search_entity_tool(meta),
        'describe_entity': make_describe_entity_tool(meta),
        'probe_relationships': make_probe_relationships_tool(meta),
    }
    if include_sparql:
        tools['sparql_select'] = make_sparql_select_tool(meta)
    return tools
