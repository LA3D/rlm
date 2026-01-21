"""Bounded tool surface wrappers for remote SPARQL queries.

Wraps rlm.sparql_handles and rlm.dataset functions with enforced limits and LLM-friendly docstrings.
"""

from typing import Callable
from rlm.sparql_handles import sparql_query, res_sample
from rlm.dataset import res_head, res_where, res_group, res_distinct


def make_sparql_query_tool(endpoint: str, ns: dict, max_results: int = 100, timeout: float = 30.0) -> Callable:
    """Create a bounded sparql_query tool for the given endpoint.

    Args:
        endpoint: SPARQL endpoint URL
        ns: Namespace dict where results will be stored
        max_results: Maximum results to return (default 100)
        timeout: Query timeout in seconds (default 30.0)

    Returns:
        Callable tool function with signature: sparql_query(query, name='res')
        Results are stored as SPARQLResultHandle in the namespace.
    """

    def sparql_query_tool(query: str, name: str = 'res') -> str:
        """Execute SPARQL query on remote endpoint and store result handle.

        Use this to query remote SPARQL endpoints (e.g., UniProt, Wikidata).
        The result is stored as a handle - use res_head(), res_sample(), or other
        view functions to inspect the contents.

        Args:
            query: SPARQL query string (SELECT, CONSTRUCT, DESCRIBE, or ASK)
            name: Variable name to store the result handle (default 'res')

        Returns:
            Summary string describing the result (e.g., "SELECT result with 50 rows...")

        Example:
            result = sparql_query('''
                PREFIX up: <http://purl.uniprot.org/core/>
                SELECT ?protein ?name WHERE {
                    ?protein a up:Protein ;
                             up:recommendedName/up:fullName ?name .
                } LIMIT 10
            ''', name='proteins')
            # Result stored in 'proteins' variable
            # Use res_head(proteins) to view first rows

        Note:
            - For SELECT queries, LIMIT is automatically injected if missing
            - Results are bounded by max_results parameter
            - Use the result handle with view functions (res_head, res_sample, etc.)
        """
        return sparql_query(
            query=query,
            endpoint=endpoint,
            max_results=max_results,
            name=name,
            ns=ns,
            timeout=timeout
        )

    return sparql_query_tool


def make_res_head_tool(ns: dict) -> Callable:
    """Create a bounded res_head tool for viewing result handles.

    Args:
        ns: Namespace dict containing result handles

    Returns:
        Callable tool function with signature: res_head(result, n=10)
        Returns first N rows from a result handle.
    """

    def res_head_tool(result_name: str, n: int = 10) -> list:
        """Get first N rows from a result handle.

        Use this to quickly inspect the beginning of query results.

        Args:
            result_name: Name of result handle variable in namespace
            n: Number of rows to return (default 10)

        Returns:
            List of first N rows (dicts for SELECT, triples for CONSTRUCT)

        Example:
            # After running sparql_query(..., name='proteins')
            first_rows = res_head('proteins', n=5)
            for row in first_rows:
                print(row)
        """
        if result_name not in ns:
            raise ValueError(f"Result handle '{result_name}' not found in namespace")
        result = ns[result_name]
        # Extract rows from SPARQLResultHandle if needed
        if hasattr(result, 'rows'):
            result = result.rows
        return res_head(result, n=n)

    return res_head_tool


def make_res_sample_tool(ns: dict) -> Callable:
    """Create a bounded res_sample tool for viewing result handles.

    Args:
        ns: Namespace dict containing result handles

    Returns:
        Callable tool function with signature: res_sample(result, n=10, seed=None)
        Returns random sample of N rows from a result handle.
    """

    def res_sample_tool(result_name: str, n: int = 10, seed: int = None) -> list:
        """Get random sample of N rows from a result handle.

        Use this to get a representative sample of query results without bias
        toward the beginning of the result set.

        Args:
            result_name: Name of result handle variable in namespace
            n: Number of rows to sample (default 10)
            seed: Optional random seed for reproducibility

        Returns:
            List of N randomly sampled rows

        Example:
            # After running sparql_query(..., name='proteins')
            sample_rows = res_sample('proteins', n=10)
            for row in sample_rows:
                print(row)
        """
        if result_name not in ns:
            raise ValueError(f"Result handle '{result_name}' not found in namespace")
        result = ns[result_name]
        # res_sample already handles SPARQLResultHandle internally
        return res_sample(result, n=n, seed=seed)

    return res_sample_tool


def make_res_where_tool(ns: dict) -> Callable:
    """Create a bounded res_where tool for filtering result handles.

    Args:
        ns: Namespace dict containing result handles

    Returns:
        Callable tool function with signature: res_where(result, column, pattern=None, value=None, limit=100)
        Returns filtered rows matching pattern or value.
    """

    def res_where_tool(result_name: str, column: str, pattern: str = None, value: str = None, limit: int = 100) -> list:
        """Filter result rows by column value or regex pattern.

        Use this to find specific rows matching criteria in your results.

        Args:
            result_name: Name of result handle variable in namespace
            column: Column name to filter on
            pattern: Optional regex pattern to match (case-insensitive)
            value: Optional exact value to match
            limit: Maximum matching rows to return (default 100)

        Returns:
            List of matching rows

        Example:
            # Find all proteins with "kinase" in name
            kinases = res_where('proteins', 'name', pattern='kinase', limit=20)

            # Find exact match
            specific = res_where('proteins', 'id', value='P12345')

        Note:
            Either pattern or value should be provided, not both.
        """
        if result_name not in ns:
            raise ValueError(f"Result handle '{result_name}' not found in namespace")
        result = ns[result_name]
        return res_where(result, column=column, pattern=pattern, value=value, limit=limit)

    return res_where_tool


def make_res_group_tool(ns: dict) -> Callable:
    """Create a bounded res_group tool for grouping result handles.

    Args:
        ns: Namespace dict containing result handles

    Returns:
        Callable tool function with signature: res_group(result, column, limit=20)
        Returns counts grouped by column value.
    """

    def res_group_tool(result_name: str, column: str, limit: int = 20) -> list:
        """Get counts grouped by column value.

        Use this to understand the distribution of values in a column.

        Args:
            result_name: Name of result handle variable in namespace
            column: Column to group by
            limit: Maximum groups to return (default 20)

        Returns:
            List of (value, count) tuples, sorted by count descending

        Example:
            # Count proteins by organism
            organism_counts = res_group('proteins', 'organism', limit=10)
            for organism, count in organism_counts:
                print(f"{organism}: {count} proteins")
        """
        if result_name not in ns:
            raise ValueError(f"Result handle '{result_name}' not found in namespace")
        result = ns[result_name]
        return res_group(result, column=column, limit=limit)

    return res_group_tool


def make_res_distinct_tool(ns: dict) -> Callable:
    """Create a bounded res_distinct tool for getting unique values.

    Args:
        ns: Namespace dict containing result handles

    Returns:
        Callable tool function with signature: res_distinct(result, column, limit=50)
        Returns distinct values in a column.
    """

    def res_distinct_tool(result_name: str, column: str, limit: int = 50) -> list:
        """Get distinct values in a column.

        Use this to see what unique values exist in a column.

        Args:
            result_name: Name of result handle variable in namespace
            column: Column to get distinct values from
            limit: Maximum distinct values to return (default 50)

        Returns:
            Sorted list of distinct values

        Example:
            # Get all unique organisms in results
            organisms = res_distinct('proteins', 'organism', limit=30)
            for org in organisms:
                print(org)
        """
        if result_name not in ns:
            raise ValueError(f"Result handle '{result_name}' not found in namespace")
        result = ns[result_name]
        return res_distinct(result, column=column, limit=limit)

    return res_distinct_tool


def make_sparql_tools(endpoint: str, ns: dict, max_results: int = 100, timeout: float = 30.0) -> dict[str, Callable]:
    """Create all bounded SPARQL tools for the given endpoint.

    Convenience function to create all tool wrappers at once.

    Args:
        endpoint: SPARQL endpoint URL
        ns: Namespace dict where results will be stored
        max_results: Maximum results to return from queries (default 100)
        timeout: Query timeout in seconds (default 30.0)

    Returns:
        Dict mapping tool names to tool functions:
            - 'sparql_query': Execute SPARQL queries on remote endpoint
            - 'res_head': Get first N rows from result
            - 'res_sample': Get random sample of N rows
            - 'res_where': Filter rows by column value/pattern
            - 'res_group': Group and count by column
            - 'res_distinct': Get distinct values in column

    Example:
        tools = make_sparql_tools(
            endpoint="https://sparql.uniprot.org/sparql",
            ns=my_namespace,
            max_results=100
        )
        # tools['sparql_query'] is ready to use
    """
    return {
        'sparql_query': make_sparql_query_tool(endpoint, ns, max_results, timeout),
        'res_head': make_res_head_tool(ns),
        'res_sample': make_res_sample_tool(ns),
        'res_where': make_res_where_tool(ns),
        'res_group': make_res_group_tool(ns),
        'res_distinct': make_res_distinct_tool(ns),
    }
