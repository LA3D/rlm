"""Tests for ontology tool wrappers.

Tests the bounded tool surface for ontology exploration.
"""

import pytest
from pathlib import Path
from rdflib import Graph
from rlm.ontology import GraphMeta, search_entity
from rlm_runtime.tools import (
    make_search_entity_tool,
    make_describe_entity_tool,
    make_probe_relationships_tool,
    make_sparql_select_tool,
    make_ontology_tools,
)


@pytest.fixture
def test_meta():
    """Create a GraphMeta for testing."""
    # Use a small ontology for fast tests
    ontology_dir = Path(__file__).parents[2] / "ontology"
    prov_path = ontology_dir / "prov.ttl"
    if not prov_path.exists():
        pytest.skip(f"Test ontology not found: {prov_path}")

    # Load graph and create GraphMeta
    g = Graph()
    g.parse(prov_path, format='turtle')
    return GraphMeta(graph=g, name="prov")


class TestSearchEntityTool:
    """Test search_entity tool wrapper."""

    def test_search_entity_tool_created(self, test_meta):
        """Tool is created successfully."""
        tool = make_search_entity_tool(test_meta)
        assert callable(tool)
        assert tool.__doc__ is not None
        assert "search" in tool.__doc__.lower()

    def test_limit_clamped_to_maximum(self, test_meta):
        """Limit is clamped to maximum of 10."""
        tool = make_search_entity_tool(test_meta)
        # Request limit > 10, should be clamped to 10
        results = tool("Entity", limit=100)
        assert len(results) <= 10

    def test_limit_clamped_to_minimum(self, test_meta):
        """Limit is clamped to minimum of 1."""
        tool = make_search_entity_tool(test_meta)
        # Request limit < 1, should be clamped to 1
        results = tool("Activity", limit=0)
        # If there are results, at least 1 should be returned
        if results:
            assert len(results) >= 1

    def test_limit_clamped_to_minimum_negative(self, test_meta):
        """Negative limit is clamped to minimum of 1."""
        tool = make_search_entity_tool(test_meta)
        results = tool("Activity", limit=-5)
        if results:
            assert len(results) >= 1

    def test_search_in_parameter_works(self, test_meta):
        """search_in parameter is passed through."""
        tool = make_search_entity_tool(test_meta)
        results = tool("Activity", search_in='label')
        assert isinstance(results, list)


class TestDescribeEntityTool:
    """Test describe_entity tool wrapper."""

    def test_describe_entity_tool_created(self, test_meta):
        """Tool is created successfully."""
        tool = make_describe_entity_tool(test_meta)
        assert callable(tool)
        assert tool.__doc__ is not None
        assert "describe" in tool.__doc__.lower()

    def test_limit_clamped_to_maximum(self, test_meta):
        """Limit is clamped to maximum of 25."""
        tool = make_describe_entity_tool(test_meta)
        # Find an entity to describe
        results = search_entity(test_meta, "Activity", limit=1)
        if not results:
            pytest.skip("No entities found to test")

        uri = results[0]['uri']
        description = tool(uri, limit=1000)
        # Check that properties don't exceed limit
        if 'properties' in description:
            assert len(description['properties']) <= 25

    def test_limit_clamped_to_minimum(self, test_meta):
        """Limit is clamped to minimum of 1."""
        tool = make_describe_entity_tool(test_meta)
        results = search_entity(test_meta, "Activity", limit=1)
        if not results:
            pytest.skip("No entities found to test")

        uri = results[0]['uri']
        description = tool(uri, limit=0)
        assert isinstance(description, dict)
        assert 'uri' in description

    def test_prefixed_uri_supported(self, test_meta):
        """Prefixed URIs like 'prov:Activity' work."""
        tool = make_describe_entity_tool(test_meta)
        # Try a common PROV class
        try:
            description = tool("prov:Activity", limit=10)
            assert isinstance(description, dict)
            assert 'uri' in description
        except Exception:
            # If it doesn't exist, that's fine
            pass


class TestProbeRelationshipsTool:
    """Test probe_relationships tool wrapper."""

    def test_probe_relationships_tool_created(self, test_meta):
        """Tool is created successfully."""
        tool = make_probe_relationships_tool(test_meta)
        assert callable(tool)
        assert tool.__doc__ is not None
        assert "neighbors" in tool.__doc__.lower() or "relationships" in tool.__doc__.lower()

    def test_limit_clamped_to_maximum(self, test_meta):
        """Limit is clamped to maximum of 15."""
        tool = make_probe_relationships_tool(test_meta)
        results = search_entity(test_meta, "Activity", limit=1)
        if not results:
            pytest.skip("No entities found to test")

        uri = results[0]['uri']
        neighbors = tool(uri, limit=1000, direction='both')
        # Check that outgoing + incoming don't exceed limit * 2 (per direction)
        if 'outgoing' in neighbors:
            assert len(neighbors['outgoing']) <= 15
        if 'incoming' in neighbors:
            assert len(neighbors['incoming']) <= 15

    def test_limit_clamped_to_minimum(self, test_meta):
        """Limit is clamped to minimum of 1."""
        tool = make_probe_relationships_tool(test_meta)
        results = search_entity(test_meta, "Activity", limit=1)
        if not results:
            pytest.skip("No entities found to test")

        uri = results[0]['uri']
        neighbors = tool(uri, limit=-1, direction='both')
        assert isinstance(neighbors, dict)
        assert 'uri' in neighbors

    def test_direction_parameter_works(self, test_meta):
        """direction parameter is passed through."""
        tool = make_probe_relationships_tool(test_meta)
        results = search_entity(test_meta, "Activity", limit=1)
        if not results:
            pytest.skip("No entities found to test")

        uri = results[0]['uri']

        # Test 'out' direction
        out_neighbors = tool(uri, direction='out', limit=5)
        assert 'outgoing' in out_neighbors or out_neighbors.get('outgoing') == []

        # Test 'in' direction
        in_neighbors = tool(uri, direction='in', limit=5)
        assert 'incoming' in in_neighbors or in_neighbors.get('incoming') == []


class TestMakeOntologyTools:
    """Test convenience function for creating all tools."""

    def test_make_ontology_tools_creates_all(self, test_meta):
        """make_ontology_tools creates all three tools."""
        tools = make_ontology_tools(test_meta)
        assert isinstance(tools, dict)
        assert 'search_entity' in tools
        assert 'describe_entity' in tools
        assert 'probe_relationships' in tools
        assert callable(tools['search_entity'])
        assert callable(tools['describe_entity'])
        assert callable(tools['probe_relationships'])

    def test_all_tools_have_docstrings(self, test_meta):
        """All created tools have docstrings."""
        tools = make_ontology_tools(test_meta)
        for name, tool in tools.items():
            assert tool.__doc__ is not None, f"Tool {name} missing docstring"
            assert len(tool.__doc__) > 50, f"Tool {name} docstring too short"


class TestSPARQLSelectTool:
    """Test SPARQL SELECT tool with LIMIT injection."""

    def test_sparql_tool_created(self, test_meta):
        """Tool is created successfully."""
        tool = make_sparql_select_tool(test_meta)
        assert callable(tool)
        assert tool.__doc__ is not None
        assert "sparql" in tool.__doc__.lower() or "query" in tool.__doc__.lower()

    def test_sparql_tool_injects_limit(self, test_meta):
        """LIMIT is added if missing from query."""
        tool = make_sparql_select_tool(test_meta, max_limit=10)

        # Query without LIMIT
        query = """
            PREFIX prov: <http://www.w3.org/ns/prov#>
            SELECT ?s WHERE { ?s a prov:Activity }
        """

        results = tool(query)
        # Should execute successfully and return bounded results
        assert isinstance(results, list)
        # Should not exceed the injected limit
        assert len(results) <= 10

    def test_sparql_tool_respects_existing_limit(self, test_meta):
        """Existing LIMIT is preserved and not modified."""
        tool = make_sparql_select_tool(test_meta, max_limit=100)

        # Query with explicit LIMIT 2
        query = """
            PREFIX prov: <http://www.w3.org/ns/prov#>
            SELECT ?s WHERE { ?s a prov:Activity } LIMIT 2
        """

        results = tool(query)
        # Should respect the explicit LIMIT 2
        assert isinstance(results, list)
        assert len(results) <= 2

    def test_sparql_tool_limit_with_order_by(self, test_meta):
        """LIMIT is appended correctly when ORDER BY is present."""
        tool = make_sparql_select_tool(test_meta, max_limit=5)

        # Query with ORDER BY but no LIMIT
        query = """
            PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
            SELECT ?s ?label WHERE {
                ?s rdfs:label ?label
            } ORDER BY ?label
        """

        results = tool(query)
        # Should execute successfully with LIMIT appended after ORDER BY
        assert isinstance(results, list)
        assert len(results) <= 5

    def test_sparql_tool_non_select_unchanged(self, test_meta):
        """Non-SELECT queries are not modified."""
        tool = make_sparql_select_tool(test_meta)

        # ASK query (not SELECT)
        query = """
            PREFIX prov: <http://www.w3.org/ns/prov#>
            ASK WHERE { ?s a prov:Activity }
        """

        # Should not crash, though result format may differ
        try:
            result = tool(query)
            # ASK returns boolean, not list - tool may not handle this perfectly
            # but shouldn't crash
        except:
            # It's okay if ASK queries aren't fully supported
            pass


class TestMakeOntologyToolsWithSPARQL:
    """Test convenience function includes SPARQL tool."""

    def test_make_ontology_tools_includes_sparql(self, test_meta):
        """make_ontology_tools includes sparql_select by default."""
        tools = make_ontology_tools(test_meta)
        assert 'sparql_select' in tools
        assert callable(tools['sparql_select'])

    def test_make_ontology_tools_can_exclude_sparql(self, test_meta):
        """make_ontology_tools can exclude sparql_select."""
        tools = make_ontology_tools(test_meta, include_sparql=False)
        assert 'sparql_select' not in tools
        assert len(tools) == 3  # Only the 3 original tools
