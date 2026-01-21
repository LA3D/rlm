"""Tests for SPARQL tool wrappers.

Tests the bounded tool surface for remote SPARQL queries.
"""

import pytest
from unittest.mock import Mock, patch, MagicMock
from rlm.sparql_handles import SPARQLResultHandle
from rlm_runtime.tools import (
    make_sparql_query_tool,
    make_res_head_tool,
    make_res_sample_tool,
    make_res_where_tool,
    make_res_group_tool,
    make_res_distinct_tool,
    make_sparql_tools,
)


@pytest.fixture
def mock_namespace():
    """Create a mock namespace with test result handles."""
    ns = {}

    # Mock SELECT result
    select_handle = SPARQLResultHandle(
        rows=[
            {'protein': 'P12345', 'name': 'Test Protein 1'},
            {'protein': 'P23456', 'name': 'Test Protein 2'},
            {'protein': 'P34567', 'name': 'Test Kinase 1'},
            {'protein': 'P45678', 'name': 'Test Kinase 2'},
            {'protein': 'P56789', 'name': 'Another Protein'},
        ],
        result_type='select',
        query='SELECT ?protein ?name WHERE {...}',
        endpoint='https://test.example.com/sparql',
        columns=['protein', 'name'],
        total_rows=5
    )
    ns['test_result'] = select_handle

    return ns


class TestSparqlQueryTool:
    """Test sparql_query tool wrapper."""

    @patch('rlm_runtime.tools.sparql_tools.sparql_query')
    def test_sparql_query_tool_created(self, mock_sparql_query):
        """Tool is created successfully."""
        ns = {}
        tool = make_sparql_query_tool(
            endpoint="https://test.example.com/sparql",
            ns=ns,
            max_results=100,
            timeout=30.0
        )
        assert callable(tool)
        assert tool.__doc__ is not None
        assert "SPARQL" in tool.__doc__

    @patch('rlm_runtime.tools.sparql_tools.sparql_query')
    def test_sparql_query_tool_executes_query(self, mock_sparql_query):
        """Tool executes query with correct parameters."""
        ns = {}
        endpoint = "https://test.example.com/sparql"
        mock_sparql_query.return_value = "SELECT result with 10 rows"

        tool = make_sparql_query_tool(
            endpoint=endpoint,
            ns=ns,
            max_results=100,
            timeout=30.0
        )

        query = "SELECT ?s ?p ?o WHERE { ?s ?p ?o }"
        result = tool(query, name='test_res')

        # Verify sparql_query was called with correct args
        mock_sparql_query.assert_called_once_with(
            query=query,
            endpoint=endpoint,
            max_results=100,
            name='test_res',
            ns=ns,
            timeout=30.0
        )

        assert result == "SELECT result with 10 rows"

    @patch('rlm_runtime.tools.sparql_tools.sparql_query')
    def test_sparql_query_tool_default_name(self, mock_sparql_query):
        """Tool uses default result name 'res'."""
        ns = {}
        mock_sparql_query.return_value = "SELECT result"

        tool = make_sparql_query_tool("https://test.example.com/sparql", ns)
        tool("SELECT ?s ?p ?o WHERE { ?s ?p ?o }")

        # Check that default name 'res' was used
        call_args = mock_sparql_query.call_args
        assert call_args.kwargs['name'] == 'res'


class TestResHeadTool:
    """Test res_head tool wrapper."""

    def test_res_head_tool_created(self, mock_namespace):
        """Tool is created successfully."""
        tool = make_res_head_tool(mock_namespace)
        assert callable(tool)
        assert tool.__doc__ is not None
        assert "first" in tool.__doc__.lower()

    def test_res_head_returns_first_n_rows(self, mock_namespace):
        """Tool returns first N rows."""
        tool = make_res_head_tool(mock_namespace)
        result = tool('test_result', n=3)

        assert len(result) == 3
        assert result[0]['protein'] == 'P12345'
        assert result[2]['protein'] == 'P34567'

    def test_res_head_default_n(self, mock_namespace):
        """Tool uses default n=10."""
        tool = make_res_head_tool(mock_namespace)
        result = tool('test_result')  # Default n=10

        # Should return all 5 rows (less than 10)
        assert len(result) == 5

    def test_res_head_missing_result_raises(self, mock_namespace):
        """Tool raises error if result not found."""
        tool = make_res_head_tool(mock_namespace)

        with pytest.raises(ValueError, match="not found"):
            tool('nonexistent_result')


class TestResSampleTool:
    """Test res_sample tool wrapper."""

    def test_res_sample_tool_created(self, mock_namespace):
        """Tool is created successfully."""
        tool = make_res_sample_tool(mock_namespace)
        assert callable(tool)
        assert tool.__doc__ is not None
        assert "sample" in tool.__doc__.lower()

    def test_res_sample_returns_n_rows(self, mock_namespace):
        """Tool returns N sampled rows."""
        tool = make_res_sample_tool(mock_namespace)
        result = tool('test_result', n=3, seed=42)  # Use seed for reproducibility

        assert len(result) == 3
        # Verify they're actual rows from the result
        for row in result:
            assert 'protein' in row
            assert 'name' in row

    def test_res_sample_with_seed_reproducible(self, mock_namespace):
        """Tool with same seed produces same results."""
        tool = make_res_sample_tool(mock_namespace)

        result1 = tool('test_result', n=3, seed=42)
        result2 = tool('test_result', n=3, seed=42)

        assert result1 == result2

    def test_res_sample_missing_result_raises(self, mock_namespace):
        """Tool raises error if result not found."""
        tool = make_res_sample_tool(mock_namespace)

        with pytest.raises(ValueError, match="not found"):
            tool('nonexistent_result')


class TestResWhereTool:
    """Test res_where tool wrapper."""

    def test_res_where_tool_created(self, mock_namespace):
        """Tool is created successfully."""
        tool = make_res_where_tool(mock_namespace)
        assert callable(tool)
        assert tool.__doc__ is not None
        assert "filter" in tool.__doc__.lower()

    def test_res_where_pattern_match(self, mock_namespace):
        """Tool filters by regex pattern."""
        tool = make_res_where_tool(mock_namespace)
        result = tool('test_result', 'name', pattern='Kinase')

        assert len(result) == 2
        assert all('Kinase' in row['name'] for row in result)

    def test_res_where_exact_value(self, mock_namespace):
        """Tool filters by exact value."""
        tool = make_res_where_tool(mock_namespace)
        result = tool('test_result', 'protein', value='P12345')

        assert len(result) == 1
        assert result[0]['protein'] == 'P12345'

    def test_res_where_limit(self, mock_namespace):
        """Tool respects limit parameter."""
        tool = make_res_where_tool(mock_namespace)
        # All rows contain 'Test' or 'Another', but limit to 3
        result = tool('test_result', 'name', pattern='.*', limit=3)

        assert len(result) <= 3

    def test_res_where_missing_result_raises(self, mock_namespace):
        """Tool raises error if result not found."""
        tool = make_res_where_tool(mock_namespace)

        with pytest.raises(ValueError, match="not found"):
            tool('nonexistent_result', 'name', pattern='test')


class TestResGroupTool:
    """Test res_group tool wrapper."""

    def test_res_group_tool_created(self, mock_namespace):
        """Tool is created successfully."""
        tool = make_res_group_tool(mock_namespace)
        assert callable(tool)
        assert tool.__doc__ is not None
        assert "group" in tool.__doc__.lower()

    def test_res_group_counts_values(self, mock_namespace):
        """Tool groups and counts column values."""
        # Add duplicate proteins to test grouping
        ns = mock_namespace
        ns['test_result'].rows.extend([
            {'protein': 'P12345', 'name': 'Duplicate 1'},
            {'protein': 'P12345', 'name': 'Duplicate 2'},
        ])

        tool = make_res_group_tool(ns)
        result = tool('test_result', 'protein', limit=10)

        # Result should be list of (value, count) tuples
        assert isinstance(result, list)
        assert len(result) > 0

        # Find P12345 which should have count of 3
        p12345_count = next((count for val, count in result if val == 'P12345'), None)
        assert p12345_count == 3

    def test_res_group_respects_limit(self, mock_namespace):
        """Tool respects limit parameter."""
        tool = make_res_group_tool(mock_namespace)
        result = tool('test_result', 'protein', limit=2)

        assert len(result) <= 2

    def test_res_group_missing_result_raises(self, mock_namespace):
        """Tool raises error if result not found."""
        tool = make_res_group_tool(mock_namespace)

        with pytest.raises(ValueError, match="not found"):
            tool('nonexistent_result', 'protein')


class TestResDistinctTool:
    """Test res_distinct tool wrapper."""

    def test_res_distinct_tool_created(self, mock_namespace):
        """Tool is created successfully."""
        tool = make_res_distinct_tool(mock_namespace)
        assert callable(tool)
        assert tool.__doc__ is not None
        assert "distinct" in tool.__doc__.lower()

    def test_res_distinct_returns_unique_values(self, mock_namespace):
        """Tool returns distinct values."""
        tool = make_res_distinct_tool(mock_namespace)
        result = tool('test_result', 'protein', limit=10)

        # Should return unique protein values
        assert len(result) == 5  # 5 distinct proteins
        assert len(set(result)) == len(result)  # All unique

    def test_res_distinct_sorted(self, mock_namespace):
        """Tool returns sorted values."""
        tool = make_res_distinct_tool(mock_namespace)
        result = tool('test_result', 'protein', limit=10)

        # Should be sorted
        assert result == sorted(result)

    def test_res_distinct_respects_limit(self, mock_namespace):
        """Tool respects limit parameter."""
        tool = make_res_distinct_tool(mock_namespace)
        result = tool('test_result', 'protein', limit=3)

        assert len(result) <= 3

    def test_res_distinct_missing_result_raises(self, mock_namespace):
        """Tool raises error if result not found."""
        tool = make_res_distinct_tool(mock_namespace)

        with pytest.raises(ValueError, match="not found"):
            tool('nonexistent_result', 'protein')


class TestMakeSparqlTools:
    """Test convenience factory for all SPARQL tools."""

    @patch('rlm_runtime.tools.sparql_tools.sparql_query')
    def test_make_sparql_tools_creates_all_tools(self, mock_sparql_query):
        """Factory creates all expected tools."""
        ns = {}
        tools = make_sparql_tools(
            endpoint="https://test.example.com/sparql",
            ns=ns,
            max_results=100,
            timeout=30.0
        )

        # Verify all expected tools are present
        assert 'sparql_query' in tools
        assert 'res_head' in tools
        assert 'res_sample' in tools
        assert 'res_where' in tools
        assert 'res_group' in tools
        assert 'res_distinct' in tools

        # Verify they're all callable
        for tool_name, tool in tools.items():
            assert callable(tool), f"{tool_name} is not callable"

    @patch('rlm_runtime.tools.sparql_tools.sparql_query')
    def test_make_sparql_tools_configures_query_tool(self, mock_sparql_query):
        """Factory configures sparql_query tool with correct parameters."""
        ns = {}
        endpoint = "https://test.example.com/sparql"
        mock_sparql_query.return_value = "result"

        tools = make_sparql_tools(
            endpoint=endpoint,
            ns=ns,
            max_results=50,
            timeout=15.0
        )

        # Execute a query
        tools['sparql_query']("SELECT * WHERE { ?s ?p ?o }")

        # Verify parameters were passed correctly
        call_args = mock_sparql_query.call_args
        assert call_args.kwargs['endpoint'] == endpoint
        assert call_args.kwargs['max_results'] == 50
        assert call_args.kwargs['timeout'] == 15.0
