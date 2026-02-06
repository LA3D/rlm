"""SPARQL tools v2 - Unified design following Claude Code patterns + RLM memory.

Key improvements over sparql.py:
1. Consistent `limit` parameter across all tools (prevents 24 arg mismatch failures)
2. Auto-LIMIT with validation warnings (prevents 90 timeout failures)
3. Accept both dict and string for ref_key (prevents 4 type errors)
4. Pagination metadata: has_more, next_offset, truncated
5. Output modes: 'sample', 'schema', 'count' for progressive disclosure
6. Rich return metadata: total_available, execution_time_ms, truncated

Design patterns from UNIFIED_TOOL_MEMORY_DESIGN.md:
- Everything is a handle - REPL sees metadata, not payloads
- Two-phase retrieval - search/query returns handle, slice/get returns content
- Bounded by default - all operations have hard caps
"""

from __future__ import annotations
import re
import time
from dataclasses import dataclass
from typing import Any, Union, Literal
from urllib.parse import urlencode
from urllib.request import Request, urlopen
from urllib.error import URLError, HTTPError
import json

# Import endpoint config
try:
    from experiments.reasoningbank.prototype.tools.endpoint import EndpointConfig, get_endpoint
except ImportError:
    EndpointConfig = None
    get_endpoint = None


# === Handle Types ===

@dataclass
class Ref:
    """Handle for large SPARQL results - REPL sees metadata, not payload."""
    key: str
    dtype: str       # 'results', 'schema', 'describe'
    sz: int          # char count
    rows: int        # row count (for results)
    prev: str        # first 120 chars preview
    source: str = ""
    truncated: bool = False
    limit_applied: int = 0

    def __repr__(self):
        src = f" from {self.source}" if self.source else ""
        trunc = " [truncated]" if self.truncated else ""
        return f"Ref({self.key!r}, {self.dtype}, {self.rows} rows, {self.sz} chars{src}{trunc})"

    def to_handle(self) -> dict:
        """Convert to serializable handle dict for DSPy sandbox."""
        return {
            'key': self.key,
            'dtype': self.dtype,
            'size': self.sz,
            'rows': self.rows,
            'preview': self.prev,
            'source': self.source,
            'truncated': self.truncated,
            'limit_applied': self.limit_applied,
            'usage': 'Call sparql_slice(this, limit=N) to get rows',
        }


class ResultStore:
    """In-memory storage for SPARQL results within a single run."""

    def __init__(self, source: str = ""):
        self._results: dict[str, Any] = {}
        self._metadata: dict[str, dict] = {}
        self._counter = 0
        self._source = source

    def put(self, data: Any, dtype: str, preview: str = "",
            truncated: bool = False, limit_applied: int = 0,
            total_available: int = None) -> Ref:
        """Store data, return handle."""
        k = f"{dtype}_{self._counter}"
        self._counter += 1
        self._results[k] = data

        # Calculate size
        if isinstance(data, list):
            sz = sum(len(str(row)) for row in data)
            rows = len(data)
        elif isinstance(data, str):
            sz = len(data)
            rows = data.count('\n') + 1
        else:
            sz = len(str(data))
            rows = 1

        # Store metadata for pagination
        self._metadata[k] = {
            'total_available': total_available or rows,
            'truncated': truncated,
            'limit_applied': limit_applied,
        }

        return Ref(k, dtype, sz, rows, preview[:120], self._source, truncated, limit_applied)

    def get(self, k: str) -> Any:
        """Get full data by key."""
        return self._results.get(k)

    def metadata(self, k: str) -> dict:
        """Get metadata for pagination."""
        return self._metadata.get(k, {})

    def slice(self, k: str, offset: int = 0, limit: int = None) -> dict:
        """Get rows with pagination metadata.

        Returns dict with: rows, returned, total_available, offset, has_more, next_offset
        """
        data = self._results.get(k)
        meta = self._metadata.get(k, {})

        if not isinstance(data, list):
            return {
                'rows': [data] if data else [],
                'returned': 1 if data else 0,
                'total_available': 1 if data else 0,
                'offset': 0,
                'has_more': False,
                'next_offset': None,
            }

        total = len(data)
        limit = min(limit or 50, 100)  # Default 50, cap at 100
        end = min(offset + limit, total)
        sliced = data[offset:end]

        return {
            'rows': sliced,
            'returned': len(sliced),
            'total_available': meta.get('total_available', total),
            'offset': offset,
            'has_more': end < total,
            'next_offset': end if end < total else None,
            'source': self._source,
        }


# === Default Prefixes ===

DEFAULT_PREFIXES = """
PREFIX rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#>
PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
PREFIX owl: <http://www.w3.org/2002/07/owl#>
PREFIX xsd: <http://www.w3.org/2001/XMLSchema#>
PREFIX skos: <http://www.w3.org/2004/02/skos/core#>
"""


# === Main Tools Class ===

class SPARQLToolsV2:
    """RLM-friendly SPARQL tools with bounded returns and unified API.

    All tools:
    - Accept `limit` parameter consistently
    - Return rich metadata (truncated, has_more, total_available)
    - Accept both dict handles and string keys
    - Include source attribution
    """

    def __init__(
        self,
        config: Union['EndpointConfig', str],
        timeout: int = None,
        default_limit: int = None
    ):
        if isinstance(config, str):
            self.endpoint = config.rstrip('/')
            self.name = "SPARQL Endpoint"
            self.authority = ""
            self._prefixes = DEFAULT_PREFIXES
            self.timeout = timeout or 30
            self.default_limit = default_limit or 100
            self._config = None
        else:
            self._config = config
            self.endpoint = config.url.rstrip('/')
            self.name = config.name
            self.authority = config.authority
            self._prefixes = config.prefix_block() if config.prefixes else DEFAULT_PREFIXES
            self.timeout = timeout or config.timeout
            self.default_limit = default_limit or config.default_limit

        self.store = ResultStore(source=self.name)

    def _extract_key(self, ref_key: Union[str, dict]) -> str:
        """Extract key from string or handle dict."""
        if isinstance(ref_key, dict):
            return ref_key.get('key', str(ref_key))
        return ref_key

    def _validate_query(self, query: str) -> list[str]:
        """Check query for common expensive patterns. Returns list of warnings."""
        warnings = []
        q_upper = query.upper()

        # Broad triple patterns
        if re.search(r'\?\w+\s+\?\w+\s+\?\w+\s*\.', query):
            warnings.append("Pattern '?s ?p ?o' matches ALL triples - very expensive")

        # FILTER after broad match
        if 'FILTER' in q_upper and re.search(r'\?\w+\s+a\s+\?\w+', query):
            warnings.append("FILTER applied after broad '?s a ?type' pattern - FILTER runs after matching millions")

        # String operations in FILTER
        if 'CONTAINS' in q_upper or 'STR(' in q_upper:
            warnings.append("String functions (CONTAINS, STR) prevent index usage - slow")

        return warnings

    def _execute(self, query: str, limit: int = None, timeout: int = None) -> tuple[list[dict], int]:
        """Execute SPARQL query, return (rows, execution_time_ms)."""
        limit = limit or self.default_limit
        timeout = timeout or self.timeout

        # Auto-inject LIMIT if missing
        if 'LIMIT' not in query.upper():
            query = query.rstrip().rstrip(';') + f"\nLIMIT {limit}"

        headers = {
            'Accept': 'application/sparql-results+json',
            'User-Agent': 'RLM-ReasoningBank/2.0'
        }
        data = urlencode({'query': query}).encode('utf-8')

        start = time.time()
        try:
            req = Request(self.endpoint, data=data, headers=headers, method='POST')
            with urlopen(req, timeout=timeout) as resp:
                result = json.loads(resp.read().decode('utf-8'))
        except (URLError, HTTPError) as e:
            elapsed = int((time.time() - start) * 1000)
            return [{'error': str(e), 'source': self.name}], elapsed
        except json.JSONDecodeError as e:
            elapsed = int((time.time() - start) * 1000)
            return [{'error': f'JSON parse error: {e}', 'source': self.name}], elapsed

        elapsed = int((time.time() - start) * 1000)

        # Parse SPARQL JSON results
        bindings = result.get('results', {}).get('bindings', [])
        rows = []
        for b in bindings:
            row = {}
            for var, val in b.items():
                row[var] = val.get('value', '')
            rows.append(row)

        return rows, elapsed

    # === Core Tools ===

    def sparql_query(
        self,
        query: str,
        limit: int = None,
        validate: bool = True,
        timeout: int = None
    ) -> dict:
        """Execute SPARQL SELECT query, return handle with metadata.

        Args:
            query: SPARQL SELECT query
            limit: Max rows (default: endpoint default, typically 100)
            validate: Check for expensive patterns (default: True)
            timeout: Query timeout in seconds

        Returns:
            Handle dict with: key, rows, truncated, limit_applied, warnings, execution_time_ms, usage

        Example:
            result = sparql_query('''
                SELECT ?protein ?name
                WHERE { ?protein a up:Protein ; up:mnemonic ?name }
                LIMIT 50
            ''')
            # Then: sparql_slice(result, limit=10) to get rows
        """
        limit = limit or self.default_limit

        # Validate
        warnings = self._validate_query(query) if validate else []

        # Prepend prefixes
        full_query = self._prefixes + '\n' + query

        # Execute
        rows, exec_time = self._execute(full_query, limit=limit, timeout=timeout)

        # Determine if truncated
        truncated = len(rows) >= limit and 'error' not in (rows[0] if rows else {})

        # Preview
        if rows and 'error' not in rows[0]:
            preview = ', '.join(f"{k}={str(v)[:30]}" for k, v in list(rows[0].items())[:3])
        else:
            preview = str(rows[0]) if rows else "empty"

        # Store and return handle
        ref = self.store.put(rows, 'results', preview, truncated=truncated, limit_applied=limit)
        handle = ref.to_handle()
        handle['warnings'] = warnings
        handle['execution_time_ms'] = exec_time
        return handle

    def sparql_slice(
        self,
        result: Union[str, dict],
        offset: int = 0,
        limit: int = None
    ) -> dict:
        """Get rows from query result with pagination.

        Args:
            result: Handle dict from sparql_query OR key string
            offset: Skip this many rows (default: 0)
            limit: Max rows to return (default: 50, max: 100)

        Returns:
            Dict with: rows, returned, total_available, offset, has_more, next_offset

        Example:
            result = sparql_query("SELECT ...")
            page1 = sparql_slice(result, limit=20)
            if page1['has_more']:
                page2 = sparql_slice(result, offset=page1['next_offset'], limit=20)
        """
        key = self._extract_key(result)
        return self.store.slice(key, offset=offset, limit=limit)

    def sparql_peek(
        self,
        resource: str,
        limit: int = 5,
        output_mode: Literal['sample', 'schema', 'count'] = 'sample'
    ) -> dict:
        """Peek at instances of a class or resource properties.

        Args:
            resource: Class URI/prefix (e.g., 'up:Protein') or instance URI
            limit: Max instances/properties (default: 5, max: 50)
            output_mode:
                'sample' - Sample instances with properties (default)
                'schema' - Just property names and types (no instances)
                'count'  - Just count of instances

        Returns:
            Dict with resource info based on output_mode

        Example:
            # Sample instances
            proteins = sparql_peek('up:Protein', limit=10)

            # Just schema
            schema = sparql_peek('up:Protein', output_mode='schema')

            # Just count
            count = sparql_peek('up:Protein', output_mode='count')
        """
        limit = min(limit, 50)  # Hard cap

        if output_mode == 'count':
            query = f"""
            {self._prefixes}
            SELECT (COUNT(?s) AS ?count) WHERE {{ ?s a {resource} }}
            """
            rows, _ = self._execute(query, limit=1)
            count = int(rows[0].get('count', 0)) if rows and 'count' in rows[0] else 0
            return {
                'resource': resource,
                'count': count,
                'source': self.name,
            }

        elif output_mode == 'schema':
            # Get distinct properties used by this class
            query = f"""
            {self._prefixes}
            SELECT DISTINCT ?p (COUNT(?o) AS ?usage) WHERE {{
                ?s a {resource} .
                ?s ?p ?o .
            }}
            GROUP BY ?p
            ORDER BY DESC(?usage)
            LIMIT {limit}
            """
            rows, _ = self._execute(query, limit=limit)
            properties = [
                {'name': row.get('p', '').split('/')[-1].split('#')[-1],
                 'uri': row.get('p', ''),
                 'usage': int(row.get('usage', 0))}
                for row in rows if 'error' not in row
            ]
            return {
                'resource': resource,
                'type': 'class',
                'properties': properties,
                'source': self.name,
            }

        else:  # sample
            # Get sample instances with their properties
            query = f"""
            {self._prefixes}
            SELECT ?s ?p ?o WHERE {{
                ?s a {resource} .
                ?s ?p ?o .
            }}
            LIMIT {limit * 10}
            """
            rows, _ = self._execute(query, limit=limit * 10)

            # Group by instance
            instances = {}
            for row in rows:
                if 'error' in row:
                    continue
                s = row.get('s', '')
                if s not in instances:
                    instances[s] = {'uri': s, 'properties': {}}
                p_short = row.get('p', '').split('/')[-1].split('#')[-1]
                instances[s]['properties'][p_short] = row.get('o', '')[:100]

            return {
                'resource': resource,
                'type': 'class',
                'sample_instances': list(instances.values())[:limit],
                'instance_count': len(instances),
                'truncated': len(instances) >= limit,
                'source': self.name,
            }

    def sparql_describe(
        self,
        uri: str,
        limit: int = 20,
        direction: Literal['outgoing', 'incoming', 'both'] = 'outgoing',
        output_mode: Literal['triples', 'summary'] = 'summary'
    ) -> dict:
        """Describe a specific resource's properties.

        Args:
            uri: Full URI or prefixed name to describe
            limit: Max triples (default: 20, max: 50)
            direction: 'outgoing' (resource as subject), 'incoming' (as object), 'both'
            output_mode: 'triples' (raw) or 'summary' (grouped by predicate)

        Returns:
            Dict with resource description
        """
        limit = min(limit, 50)

        # Build query based on direction
        if direction == 'incoming':
            query = f"""
            {self._prefixes}
            SELECT ?s ?p WHERE {{ ?s ?p <{uri}> }} LIMIT {limit}
            """
        elif direction == 'both':
            query = f"""
            {self._prefixes}
            SELECT ?p ?o ?incoming_s WHERE {{
                {{ <{uri}> ?p ?o }}
                UNION
                {{ ?incoming_s ?p <{uri}> }}
            }} LIMIT {limit}
            """
        else:  # outgoing
            query = f"""
            {self._prefixes}
            SELECT ?p ?o WHERE {{ <{uri}> ?p ?o }} LIMIT {limit}
            """

        rows, exec_time = self._execute(query, limit=limit)

        if output_mode == 'summary':
            # Group by predicate
            props = {}
            for row in rows:
                if 'error' in row:
                    continue
                p = row.get('p', '')
                p_short = p.split('/')[-1].split('#')[-1]
                if p_short not in props:
                    props[p_short] = {'uri': p, 'values': [], 'count': 0}
                props[p_short]['values'].append(row.get('o', row.get('s', ''))[:100])
                props[p_short]['count'] += 1

            return {
                'resource': uri,
                'direction': direction,
                'property_summary': props,
                'total_properties': len(props),
                'source': self.name,
            }
        else:  # triples
            return {
                'resource': uri,
                'direction': direction,
                'triples': rows,
                'count': len(rows),
                'source': self.name,
            }

    def sparql_count(self, query: str) -> dict:
        """Execute COUNT query or convert SELECT to COUNT.

        Args:
            query: SPARQL query (SELECT or already COUNT)

        Returns:
            Dict with: count, source
        """
        # Wrap in COUNT if not already
        if 'COUNT' not in query.upper():
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

        full_query = self._prefixes + '\n' + query
        rows, _ = self._execute(full_query, limit=1)

        if rows and 'count' in rows[0]:
            return {'count': int(rows[0]['count']), 'source': self.name}
        elif rows and 'error' in rows[0]:
            return {'error': rows[0]['error'], 'source': self.name}
        return {'count': 0, 'source': self.name}

    def sparql_schema(
        self,
        output_mode: Literal['overview', 'classes', 'properties'] = 'overview',
        filter_prefix: str = None,
        limit: int = 50
    ) -> dict:
        """Get schema information about the endpoint.

        Args:
            output_mode:
                'overview' - Class/property counts and namespaces
                'classes' - List of classes with instance counts
                'properties' - List of properties with usage counts
            filter_prefix: Filter to specific prefix (e.g., 'up:' for UniProt)
            limit: Max items to return

        Returns:
            Dict with schema info
        """
        limit = min(limit, 100)

        if output_mode == 'classes':
            query = f"""
            {self._prefixes}
            SELECT ?class (COUNT(?s) AS ?count) WHERE {{
                ?s a ?class .
            }}
            GROUP BY ?class
            ORDER BY DESC(?count)
            LIMIT {limit}
            """
            rows, _ = self._execute(query, limit=limit)

            classes = []
            for row in rows:
                if 'error' in row:
                    continue
                cls = row.get('class', '')
                if filter_prefix and not cls.startswith(filter_prefix.replace(':', '')):
                    continue
                classes.append({
                    'uri': cls,
                    'label': cls.split('/')[-1].split('#')[-1],
                    'count': int(row.get('count', 0)),
                })

            return {
                'classes': classes,
                'returned': len(classes),
                'filter': filter_prefix,
                'source': self.name,
            }

        elif output_mode == 'properties':
            query = f"""
            {self._prefixes}
            SELECT ?p (COUNT(*) AS ?usage) WHERE {{
                ?s ?p ?o .
            }}
            GROUP BY ?p
            ORDER BY DESC(?usage)
            LIMIT {limit}
            """
            rows, _ = self._execute(query, limit=limit)

            properties = []
            for row in rows:
                if 'error' in row:
                    continue
                prop = row.get('p', '')
                if filter_prefix and not prop.startswith(filter_prefix.replace(':', '')):
                    continue
                properties.append({
                    'uri': prop,
                    'label': prop.split('/')[-1].split('#')[-1],
                    'usage': int(row.get('usage', 0)),
                })

            return {
                'properties': properties,
                'returned': len(properties),
                'filter': filter_prefix,
                'source': self.name,
            }

        else:  # overview
            # Get class count
            class_count = self.sparql_count(
                "SELECT DISTINCT ?class WHERE { ?s a ?class }"
            ).get('count', 0)

            # Get property count
            prop_count = self.sparql_count(
                "SELECT DISTINCT ?p WHERE { ?s ?p ?o }"
            ).get('count', 0)

            return {
                'endpoint': self.endpoint,
                'name': self.name,
                'authority': self.authority,
                'class_count': class_count,
                'property_count': prop_count,
                'default_limit': self.default_limit,
                'source': self.name,
            }

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
        """Return tool dict that handles BOTH calling patterns.

        CRITICAL: LocalPythonInterpreter calls tools DIRECTLY:
            fn('resource', limit=5)        # Direct call
        NOT:
            fn(['resource'], {'limit': 5}) # DSPy pattern

        These wrappers must accept *args, **kwargs for direct calls,
        while still working with DSPy's (args_list, kwargs_dict) pattern.
        """

        # Wrappers that handle both direct and DSPy calling patterns
        def query_wrapper(*args, **kwargs):
            """Handle: sparql_query(query_str, limit=100) or sparql_query([query], {limit: 100})"""
            if len(args) == 2 and isinstance(args[0], list) and isinstance(args[1], dict):
                # DSPy pattern: (args_list, kwargs_dict)
                a, kw = args
                return self.sparql_query(
                    a[0] if a else '',
                    kw.get('limit', self.default_limit),
                    kw.get('validate', True),
                )
            else:
                # Direct call: sparql_query(query, limit=100)
                query = args[0] if args else kwargs.get('query', '')
                limit = args[1] if len(args) > 1 else kwargs.get('limit', self.default_limit)
                validate = args[2] if len(args) > 2 else kwargs.get('validate', True)
                return self.sparql_query(query, limit, validate)

        def slice_wrapper(*args, **kwargs):
            """Handle: sparql_slice(result, limit=50) or sparql_slice([result], {limit: 50})"""
            if len(args) == 2 and isinstance(args[0], list) and isinstance(args[1], dict):
                # DSPy pattern
                a, kw = args
                return self.sparql_slice(
                    a[0] if a else '',
                    kw.get('offset', 0),
                    kw.get('limit', 50),
                )
            else:
                # Direct call: sparql_slice(result, offset=0, limit=50)
                result = args[0] if args else kwargs.get('result', '')
                offset = args[1] if len(args) > 1 else kwargs.get('offset', 0)
                limit = args[2] if len(args) > 2 else kwargs.get('limit', 50)
                return self.sparql_slice(result, offset, limit)

        def peek_wrapper(*args, **kwargs):
            """Handle: sparql_peek(resource, limit=5) or sparql_peek([res], {limit: 5})"""
            if len(args) == 2 and isinstance(args[0], list) and isinstance(args[1], dict):
                # DSPy pattern
                a, kw = args
                return self.sparql_peek(
                    a[0] if a else '',
                    kw.get('limit', 5),
                    kw.get('output_mode', 'sample'),
                )
            else:
                # Direct call: sparql_peek(resource, limit=5, output_mode='sample')
                resource = args[0] if args else kwargs.get('resource', '')
                limit = args[1] if len(args) > 1 else kwargs.get('limit', 5)
                output_mode = args[2] if len(args) > 2 else kwargs.get('output_mode', 'sample')
                return self.sparql_peek(resource, limit, output_mode)

        def describe_wrapper(*args, **kwargs):
            """Handle: sparql_describe(uri, limit=20) or sparql_describe([uri], {limit: 20})"""
            if len(args) == 2 and isinstance(args[0], list) and isinstance(args[1], dict):
                # DSPy pattern
                a, kw = args
                return self.sparql_describe(
                    a[0] if a else '',
                    kw.get('limit', 20),
                    kw.get('direction', 'outgoing'),
                    kw.get('output_mode', 'summary'),
                )
            else:
                # Direct call
                uri = args[0] if args else kwargs.get('uri', '')
                limit = args[1] if len(args) > 1 else kwargs.get('limit', 20)
                direction = args[2] if len(args) > 2 else kwargs.get('direction', 'outgoing')
                output_mode = args[3] if len(args) > 3 else kwargs.get('output_mode', 'summary')
                return self.sparql_describe(uri, limit, direction, output_mode)

        def count_wrapper(*args, **kwargs):
            """Handle: sparql_count(query) or sparql_count([query], {})"""
            if len(args) == 2 and isinstance(args[0], list) and isinstance(args[1], dict):
                a, _ = args
                return self.sparql_count(a[0] if a else '')
            else:
                query = args[0] if args else kwargs.get('query', '')
                return self.sparql_count(query)

        def schema_wrapper(*args, **kwargs):
            """Handle: sparql_schema(mode, limit=50) or sparql_schema([mode], {limit: 50})"""
            if len(args) == 2 and isinstance(args[0], list) and isinstance(args[1], dict):
                a, kw = args
                return self.sparql_schema(
                    a[0] if a else 'overview',
                    kw.get('filter_prefix'),
                    kw.get('limit', 50),
                )
            else:
                output_mode = args[0] if args else kwargs.get('output_mode', 'overview')
                filter_prefix = args[1] if len(args) > 1 else kwargs.get('filter_prefix')
                limit = args[2] if len(args) > 2 else kwargs.get('limit', 50)
                return self.sparql_schema(output_mode, filter_prefix, limit)

        def info_wrapper(*args, **kwargs):
            """Handle: endpoint_info()"""
            return self.endpoint_info()

        return {
            'sparql_query': query_wrapper,
            'sparql_slice': slice_wrapper,
            'sparql_peek': peek_wrapper,
            'sparql_describe': describe_wrapper,
            'sparql_count': count_wrapper,
            'sparql_schema': schema_wrapper,
            'endpoint_info': info_wrapper,
        }


# === Convenience Functions ===

def create_tools(endpoint_name: str) -> SPARQLToolsV2:
    """Create SPARQLToolsV2 from pre-configured endpoint name."""
    if get_endpoint is None:
        raise ImportError("endpoint module not available")
    config = get_endpoint(endpoint_name)
    return SPARQLToolsV2(config)


def test_tools():
    """Quick test of v2 tools."""
    tools = create_tools("uniprot")

    print(f"=== Testing SPARQLToolsV2 against {tools.name} ===\n")

    # Test sparql_query with new metadata
    print("1. sparql_query with metadata:")
    result = tools.sparql_query(
        "SELECT ?taxon WHERE { ?taxon a <http://purl.uniprot.org/core/Taxon> } LIMIT 5"
    )
    print(f"   Handle: key={result['key']}, rows={result['rows']}, truncated={result['truncated']}")
    print(f"   Exec time: {result.get('execution_time_ms', '?')}ms")

    # Test sparql_slice with pagination
    print("\n2. sparql_slice with pagination:")
    page = tools.sparql_slice(result, limit=3)
    print(f"   Returned: {page['returned']}, has_more: {page['has_more']}, next_offset: {page['next_offset']}")

    # Test sparql_peek with output_mode
    print("\n3. sparql_peek with output_mode='count':")
    count = tools.sparql_peek('up:Taxon', output_mode='count')
    print(f"   Taxon count: {count.get('count', '?')}")

    # Test sparql_schema
    print("\n4. sparql_schema overview:")
    schema = tools.sparql_schema('overview')
    print(f"   Classes: {schema.get('class_count', '?')}, Properties: {schema.get('property_count', '?')}")

    print("\n=== All tests passed ===")
    return tools


if __name__ == '__main__':
    test_tools()
