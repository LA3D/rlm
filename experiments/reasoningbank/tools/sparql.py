"""SPARQL tools following ReasoningBank constraints.

Key design principles (from rlm_notes.md):
1. Return serializable handle dicts, not Ref objects - survives DSPy sandbox serialization
2. Bounded returns - all tools enforce caps
3. No stdout bloat - return dicts/JSON, don't print
4. Two-phase retrieval - stats/search first, get content on demand
5. DSPy RLM signature - `lambda args, kwargs:` for tool wrappers

Handle dict format: {'key': str, 'dtype': str, 'size': int, 'rows': int, 'preview': str, 'source': str}
Use sparql_peek(result['key']) to inspect handle contents.

Usage:
    from experiments.reasoningbank.tools.sparql import SPARQLTools
    from experiments.reasoningbank.tools.endpoint import EndpointConfig

    # Create endpoint config (or use discovery.registry_to_endpoint_config)
    config = EndpointConfig(url='https://sparql.uniprot.org/sparql/', name='UniProt')
    tools = SPARQLTools(config)

    # For DSPy RLM integration:
    tool_dict = tools.as_dspy_tools()
"""

from __future__ import annotations
import re
from dataclasses import dataclass
from typing import Any, Union
from urllib.parse import urlencode
from urllib.request import Request, urlopen
from urllib.error import URLError, HTTPError
import json

# Import endpoint config (with fallback for standalone use)
try:
    from experiments.reasoningbank.tools.endpoint import EndpointConfig
except ImportError:
    EndpointConfig = None


@dataclass
class Ref:
    """Handle for large SPARQL results - REPL sees metadata, not payload."""
    key: str
    dtype: str      # 'results', 'schema', 'describe'
    sz: int         # char count
    rows: int       # row count (for results)
    prev: str       # first 120 chars of formatted output
    source: str = ""  # endpoint name for attribution

    def __repr__(self):
        src = f" from {self.source}" if self.source else ""
        return f"Ref({self.key!r}, {self.dtype}, {self.rows} rows, {self.sz} chars{src})"

    def to_handle(self) -> dict:
        """Convert to serializable handle dict for DSPy sandbox."""
        return {
            'key': self.key,
            'dtype': self.dtype,
            'size': self.sz,
            'rows': self.rows,
            'preview': self.prev,
            'source': self.source,
        }


class ResultStore:
    """In-memory storage for SPARQL results within a single run."""

    def __init__(self, source: str = ""):
        self._results: dict[str, Any] = {}
        self._counter = 0
        self._source = source

    def put(self, data: Any, dtype: str, preview: str = "") -> Ref:
        """Store data, return handle."""
        k = f"{dtype}_{self._counter}"
        self._counter += 1
        self._results[k] = data

        # Calculate size based on type
        if isinstance(data, list):
            sz = sum(len(str(row)) for row in data)
            rows = len(data)
        elif isinstance(data, str):
            sz = len(data)
            rows = data.count('\n') + 1
        else:
            sz = len(str(data))
            rows = 1

        return Ref(k, dtype, sz, rows, preview[:120], self._source)

    def get(self, k: str) -> Any:
        """Get full data by key."""
        return self._results.get(k)

    def peek(self, k: str, n: int = 5) -> list:
        """Get first n rows."""
        data = self._results.get(k)
        if isinstance(data, list):
            return data[:n]
        return [data] if data else []

    def slice(self, k: str, start: int, end: int) -> list:
        """Get rows [start:end] (capped at 100)."""
        data = self._results.get(k)
        if not isinstance(data, list):
            return [data] if data else []
        end = min(end, start + 100)  # Hard cap matches default_limit
        return data[start:end]

    def stats(self, k: str) -> dict:
        """Get metadata about stored result."""
        data = self._results.get(k)
        if data is None:
            return {'error': 'not found'}
        if isinstance(data, list):
            return {
                'rows': len(data),
                'cols': list(data[0].keys()) if data and isinstance(data[0], dict) else [],
                'sz': sum(len(str(row)) for row in data),
                'source': self._source,
            }
        return {'sz': len(str(data)), 'type': type(data).__name__, 'source': self._source}


# Default prefixes (used if no EndpointConfig provided)
DEFAULT_PREFIXES = """
PREFIX rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#>
PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
PREFIX owl: <http://www.w3.org/2002/07/owl#>
PREFIX xsd: <http://www.w3.org/2001/XMLSchema#>
PREFIX skos: <http://www.w3.org/2004/02/skos/core#>
"""


class SPARQLTools:
    """RLM-friendly SPARQL tools with bounded returns.

    All tools return handles (Ref) or bounded dicts, never raw payloads.
    Results include source attribution for proper provenance.

    Args:
        config: EndpointConfig or URL string
        timeout: Request timeout in seconds (overrides config if provided)
        default_limit: Default LIMIT for queries (overrides config if provided)
    """

    def __init__(
        self,
        config: Union['EndpointConfig', str],
        timeout: int = None,
        default_limit: int = None
    ):
        # Handle both EndpointConfig and raw URL
        if isinstance(config, str):
            # Backwards compatible: raw URL
            self.endpoint = config.rstrip('/')
            self.name = "SPARQL Endpoint"
            self.authority = ""
            self._prefixes = DEFAULT_PREFIXES
            self.timeout = timeout or 30
            self.default_limit = default_limit or 100
            self._config = None
        else:
            # EndpointConfig
            self._config = config
            self.endpoint = config.url.rstrip('/')
            self.name = config.name
            self.authority = config.authority
            self._prefixes = config.prefix_block() if config.prefixes else DEFAULT_PREFIXES
            self.timeout = timeout or config.timeout
            self.default_limit = default_limit or config.default_limit

        self.store = ResultStore(source=self.name)

    def _execute(self, query: str, limit: int = None) -> list[dict]:
        """Execute SPARQL query, return list of result dicts."""
        # Add LIMIT if not present
        limit = limit or self.default_limit
        if 'LIMIT' not in query.upper():
            query = query.rstrip().rstrip(';') + f"\nLIMIT {limit}"

        # Prepare request
        headers = {
            'Accept': 'application/sparql-results+json',
            'User-Agent': 'RLM-ReasoningBank/1.0 (Research Query Interface)'
        }
        data = urlencode({'query': query}).encode('utf-8')

        try:
            req = Request(self.endpoint, data=data, headers=headers, method='POST')
            with urlopen(req, timeout=self.timeout) as resp:
                result = json.loads(resp.read().decode('utf-8'))
        except (URLError, HTTPError) as e:
            return [{'error': str(e), 'source': self.name}]
        except json.JSONDecodeError as e:
            return [{'error': f'JSON parse error: {e}', 'source': self.name}]

        # Parse SPARQL JSON results
        bindings = result.get('results', {}).get('bindings', [])
        rows = []
        for b in bindings:
            row = {}
            for var, val in b.items():
                row[var] = val.get('value', '')
            rows.append(row)

        return rows

    # === Bounded Tool API ===

    def sparql_query(self, query: str, limit: int = None) -> dict:
        """Execute SELECT query, return handle dict. Use sparql_peek(result['key']) to inspect.

        This tool queries the {name} database ({authority}).
        Results are database records from an authoritative source.
        """.format(name=self.name, authority=self.authority)
        limit = limit or self.default_limit

        # Always prepend default prefixes (they're harmless if already defined)
        # This ensures rdfs:, owl:, rdf: etc. are always available
        query = self._prefixes + '\n' + query

        rows = self._execute(query, limit=limit)

        # Generate preview
        if rows and 'error' not in rows[0]:
            preview = ', '.join(f"{k}={str(v)[:30]}" for k, v in list(rows[0].items())[:3])
        else:
            preview = str(rows[0]) if rows else "empty"

        return self.store.put(rows, 'results', preview).to_handle()

    def sparql_peek(self, ref_key: str | dict, n: int = 20) -> list[dict]:
        """Peek at first n rows of result (bounded to 50 max).

        Args:
            ref_key: Result key (string) OR full handle dict from sparql_query
            n: Number of rows to return (default 20, max 50)

        Example:
            result = sparql_query('SELECT ...')
            rows = sparql_peek(result)        # Pass handle directly
            rows = sparql_peek(result['key']) # Or extract key
        """
        # Accept full handle dict - extract 'key' field
        if isinstance(ref_key, dict) and 'key' in ref_key:
            ref_key = ref_key['key']
        n = min(n, 50)  # Hard cap
        return self.store.peek(ref_key, n)

    def sparql_slice(self, ref_key: str | dict, start: int, end: int) -> list[dict]:
        """Get rows [start:end] from result (capped at 100).

        Args:
            ref_key: Result key (string) OR full handle dict from sparql_query
            start: Start row index (default 0)
            end: End row index (default: endpoint default_limit, typically 100)

        Example:
            result = sparql_query('SELECT ...')
            rows = sparql_slice(result)          # Get all rows (up to 100)
            rows = sparql_slice(result, 10, 20)  # Get rows 10-20
        """
        # Accept full handle dict - extract 'key' field
        if isinstance(ref_key, dict) and 'key' in ref_key:
            ref_key = ref_key['key']
        return self.store.slice(ref_key, start, end)

    def sparql_stats(self, ref_key: str | dict) -> dict:
        """Get metadata about stored result including source attribution.

        Args:
            ref_key: Result key (string) OR full handle dict from sparql_query

        Example:
            result = sparql_query('SELECT ...')
            stats = sparql_stats(result)  # Pass handle directly
        """
        # Accept full handle dict - extract 'key' field
        if isinstance(ref_key, dict) and 'key' in ref_key:
            ref_key = ref_key['key']
        return self.store.stats(ref_key)

    def sparql_describe(self, uri: str, limit: int = 20) -> dict:
        """Describe a URI as handle dict. Use sparql_peek(result['key']) to inspect.

        Queries {name} for properties of the given URI.
        """.format(name=self.name)
        query = f"""
        {self._prefixes}
        SELECT ?p ?o WHERE {{
            <{uri}> ?p ?o .
        }}
        LIMIT {min(limit, 50)}
        """
        rows = self._execute(query, limit=limit)

        # Format as text with property-value pairs
        lines = [f"URI: {uri}", f"Source: {self.name}", ""]
        for row in rows:
            if 'error' in row:
                lines.append(f"Error: {row['error']}")
                break
            p = row.get('p', '')
            o = row.get('o', '')
            # Shorten predicate
            p_short = p.split('/')[-1].split('#')[-1]
            lines.append(f"{p_short}: {o[:100]}")

        content = '\n'.join(lines)
        preview = f"Description of {uri.split('/')[-1]} from {self.name}"
        return self.store.put(content, 'describe', preview).to_handle()

    # REMOVED: sparql_classes, sparql_properties, sparql_find, sparql_sample
    # These used hardcoded schema patterns that ignore the actual ontology.
    # The LLM should construct proper SPARQL using ontology context (L0/L1)
    # and execute via sparql_query.

    def sparql_count(self, query: str) -> dict:
        """Execute COUNT query, return single count value with attribution."""
        # Wrap in COUNT if not already
        if 'COUNT' not in query.upper():
            # Try to convert SELECT to COUNT
            match = re.search(r'SELECT\s+(.+?)\s+WHERE', query, re.IGNORECASE | re.DOTALL)
            if match:
                vars_part = match.group(1)
                first_var = re.search(r'\?(\w+)', vars_part)
                if first_var:
                    query = re.sub(
                        r'SELECT\s+.+?\s+WHERE',
                        f'SELECT (COUNT(DISTINCT ?{first_var.group(1)}) AS ?count) WHERE',
                        query,
                        flags=re.IGNORECASE | re.DOTALL
                    )

        # Always prepend default prefixes
        query = self._prefixes + '\n' + query

        rows = self._execute(query, limit=1)
        if rows and 'count' in rows[0]:
            return {'count': int(rows[0]['count']), 'source': self.name}
        elif rows and 'error' in rows[0]:
            return {'error': rows[0]['error'], 'source': self.name}
        return {'count': 0, 'source': self.name}

    def endpoint_info(self) -> dict:
        """Get endpoint metadata with authority information."""
        info = {
            'endpoint': self.endpoint,
            'name': self.name,
            'authority': self.authority,
            'default_limit': self.default_limit,
            'timeout': self.timeout,
            'prefixes': list(re.findall(r'PREFIX\s+(\w+):', self._prefixes)),
        }
        if self._config:
            info['domain'] = self._config.domain
        return info

    # === DSPy RLM Integration ===

    def as_dspy_tools(self) -> dict:
        """Return tool dict with DSPy RLM signatures.

        Tools can be called in two ways:
        1. DSPy RLM style: tool(args, kwargs) with two positional parameters
        2. Direct Python: tool() or tool(arg1, arg2) in REPL code

        All lambdas use default args=None, kwargs=None to support both patterns.
        All tools include source attribution in their returns.
        """
        def _get_arg(args, kwargs, idx=0, key=None, default=None):
            """Extract argument from various calling conventions."""
            if args is None:
                args = []
            if kwargs is None:
                kwargs = {}
            if isinstance(args, (list, tuple)) and len(args) > idx:
                return args[idx]
            if isinstance(args, str) and idx == 0:
                return args  # Single string argument
            if isinstance(args, int) and idx == 0:
                return args  # Single int argument
            if isinstance(args, dict) and idx == 0:
                return args  # Handle dict passed directly (e.g., sparql_peek(result))
            if key and isinstance(kwargs, dict):
                return kwargs.get(key, default)
            return default

        return {
            # Core query tools - LLM constructs SPARQL using ontology context
            'sparql_query': lambda args=None, kwargs=None: self.sparql_query(
                _get_arg(args, kwargs, 0, 'query', ''),
                _get_arg(args, kwargs, 1, 'limit', self.default_limit)
            ),
            'sparql_peek': lambda args=None, kwargs=None: self.sparql_peek(
                _get_arg(args, kwargs, 0, 'ref_key', ''),
                _get_arg(args, kwargs, 1, 'n', 20)  # Increased from 5 to show more results by default
            ),
            'sparql_slice': lambda args=None, kwargs=None: self.sparql_slice(
                _get_arg(args, kwargs, 0, 'ref_key', ''),
                _get_arg(args, kwargs, 1, 'start', 0),
                _get_arg(args, kwargs, 2, 'end', self.default_limit)  # Use endpoint default (100) not hardcoded 10
            ),
            'sparql_stats': lambda args=None, kwargs=None: self.sparql_stats(
                _get_arg(args, kwargs, 0, 'ref_key', '')
            ),
            'sparql_count': lambda args=None, kwargs=None: self.sparql_count(
                _get_arg(args, kwargs, 0, 'query', '')
            ),

            # URI inspection - user provides URI, we get properties
            'sparql_describe': lambda args=None, kwargs=None: self.sparql_describe(
                _get_arg(args, kwargs, 0, 'uri', ''),
                _get_arg(args, kwargs, 1, 'limit', 20)
            ),

            # Metadata
            'endpoint_info': lambda args=None, kwargs=None: self.endpoint_info(),
        }


# Convenience functions
def create_tools(endpoint_name: str) -> SPARQLTools:
    """Create SPARQLTools from pre-configured endpoint name.

    Args:
        endpoint_name: One of 'uniprot', 'wikidata', 'dbpedia', 'mesh'

    Returns:
        Configured SPARQLTools instance
    """
    from experiments.reasoningbank.tools.endpoint import get_endpoint
    config = get_endpoint(endpoint_name)
    return SPARQLTools(config)


def test_endpoint(endpoint_name: str = "uniprot"):
    """Quick test of SPARQL endpoint connectivity."""
    tools = create_tools(endpoint_name)

    print(f"Testing {tools.name} ({tools.endpoint})")

    # Get endpoint info
    info = tools.endpoint_info()
    print(f"Authority: {info['authority']}")

    # Test simple query - now returns dict handle
    handle = tools.sparql_query("SELECT ?s WHERE { ?s a owl:Class } LIMIT 5")
    print(f"Query returned: {handle}")
    assert isinstance(handle, dict), "Should return dict handle"
    assert 'key' in handle, "Handle should have 'key'"

    # Peek at results using handle['key']
    rows = tools.sparql_peek(handle['key'], 3)
    print(f"First 3 rows: {rows}")

    return tools


if __name__ == '__main__':
    import sys
    endpoint = sys.argv[1] if len(sys.argv) > 1 else "uniprot"
    test_endpoint(endpoint)
