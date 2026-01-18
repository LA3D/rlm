"""Unit tests for SPARQL Handles module.

Tests SPARQLResultHandle, res_sample, and view function polymorphism.
"""

import pytest
from rdflib import Graph, Namespace, Literal
import random

from rlm.sparql_handles import SPARQLResultHandle, res_sample
from rlm.dataset import res_head, res_where, res_group, res_distinct, ResultTable


class TestSPARQLResultHandle:
    """Unit tests for SPARQLResultHandle class."""

    def test_select_result_handle_creation(self, select_result_handle):
        """SELECT handle created with correct attributes."""
        handle = select_result_handle

        assert handle.result_type == 'select'
        assert isinstance(handle.rows, list)
        assert len(handle.rows) == 3
        assert handle.columns == ['name', 'age']
        assert handle.total_rows == 3
        assert handle.endpoint == 'local'

    def test_ask_result_handle_creation(self, ask_result_handle):
        """ASK handle created with boolean result."""
        handle = ask_result_handle

        assert handle.result_type == 'ask'
        assert isinstance(handle.rows, bool)
        assert handle.rows is True
        assert handle.endpoint == 'local'

    def test_construct_result_handle_creation(self, construct_result_handle):
        """CONSTRUCT handle created with Graph."""
        handle = construct_result_handle

        assert handle.result_type == 'construct'
        assert isinstance(handle.rows, Graph)
        assert handle.triple_count == 2
        assert len(handle.rows) == 2

    def test_describe_result_handle_creation(self):
        """DESCRIBE handle created with Graph."""
        g = Graph()
        EX = Namespace("http://example.org/")
        g.add((EX.Alice, EX.name, Literal("Alice")))

        handle = SPARQLResultHandle(
            rows=g,
            result_type='describe',
            query='DESCRIBE <http://example.org/Alice>',
            endpoint='local',
            triple_count=1
        )

        assert handle.result_type == 'describe'
        assert isinstance(handle.rows, Graph)
        assert handle.triple_count == 1

    def test_handle_summary_format(self, select_result_handle, ask_result_handle, construct_result_handle):
        """summary() returns appropriate bounded description."""
        # SELECT summary
        select_summary = select_result_handle.summary()
        assert "SELECT" in select_summary
        assert "3 rows" in select_summary
        assert "name" in select_summary
        assert "age" in select_summary

        # ASK summary
        ask_summary = ask_result_handle.summary()
        assert "ASK" in ask_summary
        assert "True" in ask_summary

        # CONSTRUCT summary
        construct_summary = construct_result_handle.summary()
        assert "CONSTRUCT" in construct_summary.upper()
        assert "2 triples" in construct_summary

    def test_handle_len(self, select_result_handle, ask_result_handle, construct_result_handle):
        """__len__ returns correct count."""
        assert len(select_result_handle) == 3
        assert len(ask_result_handle) == 1  # ASK returns 1
        assert len(construct_result_handle) == 2

    def test_handle_iter(self, select_result_handle, construct_result_handle):
        """__iter__ makes handle iterable."""
        # Iterate SELECT rows
        count = 0
        for row in select_result_handle:
            assert isinstance(row, dict)
            count += 1
        assert count == 3

        # Iterate CONSTRUCT triples
        count = 0
        for triple in construct_result_handle:
            assert len(triple) == 3  # (s, p, o)
            count += 1
        assert count == 2

    def test_handle_repr(self, select_result_handle):
        """__repr__ includes summary."""
        repr_str = repr(select_result_handle)
        assert "SPARQLResultHandle" in repr_str
        assert "SELECT" in repr_str


class TestResultSampling:
    """Unit tests for res_sample function."""

    def test_res_sample_with_list(self):
        """res_sample() works with plain list."""
        data = list(range(100))

        sample = res_sample(data, n=10, seed=42)

        assert isinstance(sample, list)
        assert len(sample) == 10
        assert all(x in data for x in sample)

    def test_res_sample_with_handle(self, select_result_handle):
        """res_sample() works with SPARQLResultHandle."""
        # Sample 2 from 3 rows
        sample = res_sample(select_result_handle, n=2, seed=42)

        assert isinstance(sample, list)
        assert len(sample) == 2
        assert all(isinstance(row, dict) for row in sample)

    def test_res_sample_with_seed_reproducibility(self):
        """res_sample() with same seed produces same results."""
        data = list(range(100))

        sample1 = res_sample(data, n=10, seed=42)
        sample2 = res_sample(data, n=10, seed=42)

        assert sample1 == sample2

    def test_res_sample_small_result_no_sampling(self):
        """res_sample() returns all if n >= len."""
        data = [1, 2, 3]

        sample = res_sample(data, n=10, seed=42)

        assert len(sample) == 3  # All returned
        assert sample == data or set(sample) == set(data)

    def test_res_sample_graph_results(self, construct_result_handle):
        """res_sample() works with graph handles."""
        # Sample 1 from 2 triples
        sample = res_sample(construct_result_handle, n=1, seed=42)

        assert isinstance(sample, list)
        assert len(sample) == 1
        assert len(sample[0]) == 3  # Triple (s, p, o)

    def test_res_sample_handle_with_result_table(self):
        """res_sample() works with ResultTable."""
        # Create ResultTable
        rows = [
            {'name': 'Alice', 'age': 25},
            {'name': 'Bob', 'age': 30},
            {'name': 'Charlie', 'age': 35},
            {'name': 'Dave', 'age': 40}
        ]
        table = ResultTable(rows=rows, columns=['name', 'age'], query='', total_rows=len(rows))

        sample = res_sample(table, n=2, seed=42)

        assert isinstance(sample, list)
        assert len(sample) == 2


class TestViewPolymorphism:
    """Tests for view functions working with Handle/ResultTable/list."""

    def test_res_head_with_handle(self, select_result_handle):
        """res_head() works with SPARQLResultHandle.rows."""
        # Get first 2 rows
        result = res_head(select_result_handle.rows, n=2)

        assert isinstance(result, list)
        assert len(result) == 2
        assert result[0]['name'] == 'Alice'

    def test_res_head_with_result_table(self):
        """res_head() works with ResultTable."""
        rows = [{'a': 1}, {'a': 2}, {'a': 3}]
        table = ResultTable(rows=rows, columns=['a'], query='', total_rows=len(rows))

        result = res_head(table, n=2)

        assert len(result) == 2
        assert result[0]['a'] == 1

    def test_res_head_with_plain_list(self):
        """res_head() works with plain list."""
        data = [1, 2, 3, 4, 5]

        result = res_head(data, n=3)

        assert result == [1, 2, 3]

    def test_res_where_with_handle(self, select_result_handle):
        """res_where() filters handle rows."""
        # Filter age >= 30 (using actual API: column, pattern/value)
        result = res_where(select_result_handle.rows, column='age', value='30')

        # Should match exact value '30'
        assert len(result) >= 1
        assert all(str(row['age']) == '30' for row in result)

    def test_res_where_with_result_table(self):
        """res_where() filters ResultTable."""
        rows = [{'x': 1}, {'x': 2}, {'x': 3}]
        table = ResultTable(rows=rows, columns=['x'], query='', total_rows=len(rows))

        # Use pattern to match values > 1
        result = res_where(table, column='x', pattern=r'^[23]$')

        assert len(result) == 2

    def test_res_group_with_handle(self, select_result_handle):
        """res_group() groups handle rows."""
        # Group by age (returns list of (value, count) tuples)
        groups = res_group(select_result_handle.rows, column='age')

        assert isinstance(groups, list)
        assert len(groups) == 3
        # Each person has unique age, so each should have count=1
        assert all(count == 1 for value, count in groups)

    def test_res_group_with_result_table(self):
        """res_group() groups ResultTable."""
        rows = [
            {'category': 'A', 'value': 1},
            {'category': 'B', 'value': 2},
            {'category': 'A', 'value': 3}
        ]
        table = ResultTable(rows=rows, columns=['category', 'value'], query='', total_rows=len(rows))

        # Returns list of (value, count) tuples
        groups = res_group(table, column='category')

        assert len(groups) == 2
        # Should be [('A', 2), ('B', 1)] or similar order
        groups_dict = dict(groups)
        assert groups_dict['A'] == 2
        assert groups_dict['B'] == 1

    def test_res_distinct_with_handle(self):
        """res_distinct() removes duplicates from handle."""
        rows = [
            {'name': 'Alice'},
            {'name': 'Bob'},
            {'name': 'Alice'}  # Duplicate
        ]
        handle = SPARQLResultHandle(
            rows=rows,
            result_type='select',
            query='SELECT ?name WHERE { ?s ?p ?o }',
            endpoint='local',
            columns=['name'],
            total_rows=3
        )

        # Distinct by name (returns list of distinct values)
        result = res_distinct(handle.rows, column='name')

        assert len(result) == 2  # Alice and Bob
        assert set(result) == {'Alice', 'Bob'}


class TestHandleMetadata:
    """Tests for metadata fields in SPARQLResultHandle."""

    def test_timestamp_generated(self, select_result_handle):
        """Handle has timestamp in ISO format."""
        assert select_result_handle.timestamp is not None
        assert 'T' in select_result_handle.timestamp
        assert 'Z' in select_result_handle.timestamp

    def test_query_stored(self, select_result_handle):
        """Original query stored in handle."""
        assert select_result_handle.query is not None
        assert 'SELECT' in select_result_handle.query

    def test_endpoint_stored(self, select_result_handle):
        """Endpoint stored in handle."""
        assert select_result_handle.endpoint == 'local'


class TestEdgeCases:
    """Tests for edge cases and error conditions."""

    def test_empty_select_result(self):
        """Handle with empty SELECT result."""
        handle = SPARQLResultHandle(
            rows=[],
            result_type='select',
            query='SELECT ?s WHERE { ?s ?p ?o }',
            endpoint='local',
            columns=[],
            total_rows=0
        )

        assert len(handle) == 0
        assert handle.summary() == "SELECT: 0 rows, columns=[]"

    def test_empty_graph_result(self):
        """Handle with empty CONSTRUCT result."""
        g = Graph()

        handle = SPARQLResultHandle(
            rows=g,
            result_type='construct',
            query='CONSTRUCT { ?s ?p ?o } WHERE { ?s ?p ?o }',
            endpoint='local',
            triple_count=0
        )

        assert len(handle) == 0
        assert handle.triple_count == 0

    def test_ask_false_result(self):
        """Handle with ASK returning False."""
        handle = SPARQLResultHandle(
            rows=False,
            result_type='ask',
            query='ASK { ?s ?p ?o }',
            endpoint='local'
        )

        assert handle.rows is False
        assert "False" in handle.summary()

    def test_res_sample_with_k_zero(self):
        """res_sample() with n=0 returns empty list."""
        data = [1, 2, 3]

        sample = res_sample(data, n=0, seed=42)

        assert sample == []

    def test_res_head_with_n_zero(self):
        """res_head() with n=0 returns empty list."""
        data = [1, 2, 3]

        result = res_head(data, n=0)

        assert result == []

    def test_res_where_no_matches(self):
        """res_where() with no matches returns empty list."""
        data = [{'x': 1}, {'x': 2}, {'x': 3}]

        # Pattern that doesn't match any values
        result = res_where(data, column='x', pattern=r'^99$')

        assert result == []
