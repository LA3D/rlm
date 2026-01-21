"""Bounded tool surface wrappers for ontology exploration.

Wraps rlm.ontology functions with enforced limits and docstrings for LLM consumption.
"""

from .ontology_tools import (
    make_search_entity_tool,
    make_describe_entity_tool,
    make_probe_relationships_tool,
    make_sparql_select_tool,
    make_ontology_tools,
)

from .sparql_tools import (
    make_sparql_query_tool,
    make_res_head_tool,
    make_res_sample_tool,
    make_res_where_tool,
    make_res_group_tool,
    make_res_distinct_tool,
    make_sparql_tools,
)

__all__ = [
    "make_search_entity_tool",
    "make_describe_entity_tool",
    "make_probe_relationships_tool",
    "make_sparql_select_tool",
    "make_ontology_tools",
    "make_sparql_query_tool",
    "make_res_head_tool",
    "make_res_sample_tool",
    "make_res_where_tool",
    "make_res_group_tool",
    "make_res_distinct_tool",
    "make_sparql_tools",
]
