"""Layer Cake Context Builder - Primary experimental control surface.

Assembles context from enabled layers (L0-L3), each with explicit budget.
This is where experiments toggle which knowledge representations help.
"""

import sys
sys.path.insert(0, '/Users/cvardema/dev/git/LA3D/rlm')

from dataclasses import dataclass, field
from rdflib import Graph
from experiments.reasoningbank.core.blob import Store, Ref
from experiments.reasoningbank.core.mem import MemStore
from experiments.reasoningbank.core import graph as G
from experiments.reasoningbank.packers import l0_sense, l1_schema, l2_mem, l3_guide
from experiments.reasoningbank.ctx.cache import build_with_cache

@dataclass
class Layer:
    "Layer configuration: enabled + budget."
    on: bool = False
    budget: int = 0

@dataclass
class Cfg:
    "Context configuration - toggles for layer cake."
    l0: Layer = field(default_factory=lambda: Layer(False, 600))
    l1: Layer = field(default_factory=lambda: Layer(False, 1000))
    l2: Layer = field(default_factory=lambda: Layer(False, 2000))
    l3: Layer = field(default_factory=lambda: Layer(False, 1000))
    guide_text: str = ""  # Full guide for L3

class Builder:
    "Assembles layer cake context for injection."
    def __init__(self, cfg:Cfg): self.cfg = cfg

    def build(self, g: Graph, task: str, mem: MemStore = None, g_path: str = None) -> str:
        """Build context string from enabled layers.

        Args:
            g: RDF graph
            task: Query string (for L2 retrieval)
            mem: Memory store (for L2)
            g_path: Optional path to graph file (enables L0/L1 caching)

        Returns:
            Assembled context string
        """
        parts = []

        # L0/L1 with optional caching
        if self.cfg.l0.on:
            if g_path:
                parts.append(build_with_cache(g_path, 'l0', self.cfg.l0.budget, l0_sense.pack))
            else:
                parts.append(l0_sense.pack(g, self.cfg.l0.budget))

        if self.cfg.l1.on:
            if g_path:
                parts.append(build_with_cache(g_path, 'l1', self.cfg.l1.budget, l1_schema.pack))
            else:
                parts.append(l1_schema.pack(g, self.cfg.l1.budget))

        if self.cfg.l2.on and mem:
            # Top-K success + top-K failure retrieval
            k_success, k_failure = 2, 1  # Configurable defaults
            success_hits = mem.search(task, k=k_success, polarity='success')
            failure_hits = mem.search(task, k=k_failure, polarity='failure')
            seed_hits = mem.search(task, k=1, polarity='seed')  # General strategies
            all_ids = [h['id'] for h in success_hits + failure_hits + seed_hits]
            if all_ids:
                items = mem.get(all_ids, max_n=len(all_ids))  # Allow all retrieved
                parts.append(l2_mem.pack(items, self.cfg.l2.budget))
        if self.cfg.l3.on and self.cfg.guide_text:
            parts.append(l3_guide.pack(self.cfg.guide_text, self.cfg.l3.budget))
        return '\n\n'.join(parts)

    def tools(self, store: Store, g_path: str, mem: MemStore = None) -> dict:
        "Build tool dict for dspy.RLM. Includes graph, context, and memory tools."
        # Set module globals
        G._store = store

        # Load graph and store in module
        g = Graph().parse(g_path)
        ref = store.put(g_path, 'graph')
        G._graphs[ref.key] = g

        return make_tools(store, ref, mem)


def _unwrap_key(val):
    """Unwrap list-wrapped keys like ['results_7'] -> 'results_7'."""
    if isinstance(val, list) and len(val) == 1:
        return val[0]
    return val


def _handle_dspy_convention(first_param, second_param, defaults: dict) -> dict:
    """Handle DSPy tool calling convention where needed.

    DSPy may call tools as: tool(['value'], {'param': value})
    This function detects and unwraps that pattern.

    Args:
        first_param: First parameter value (might be list-wrapped)
        second_param: Second parameter value (might be kwargs dict)
        defaults: Dict of {param_name: default_value}

    Returns:
        Dict of resolved parameter values
    """
    result = dict(defaults)
    param_names = list(defaults.keys())

    # Check if this looks like DSPy convention: (list, dict)
    if isinstance(first_param, list) and isinstance(second_param, dict):
        # DSPy convention: first_param is list of values, second_param is kwargs dict
        values = first_param
        kwargs = second_param

        # Map list values to parameter names
        for i, val in enumerate(values):
            if i < len(param_names):
                key_name = param_names[i]
                result[key_name] = _unwrap_key(val) if key_name in ('key', 'id') else val

        # Override with kwargs dict
        for k, v in kwargs.items():
            if k in result:
                result[k] = _unwrap_key(v) if k in ('key', 'id') else v
    else:
        # Normal calling: use first_param as first value, second_param as second value
        if first_param is not None and len(param_names) > 0:
            key_name = param_names[0]
            result[key_name] = _unwrap_key(first_param) if key_name in ('key', 'id') else first_param

        if second_param is not None and len(param_names) > 1:
            key_name = param_names[1]
            result[key_name] = _unwrap_key(second_param) if key_name in ('key', 'id') else second_param

    return result


def make_tools(store: Store, graph_ref: Ref, mem: MemStore = None) -> dict:
    """Create tool functions with explicit parameter signatures.

    Tools use explicit named parameters (not *args/**kw) because DSPy sandbox
    strips the * and ** from variadic parameters, breaking function calls.
    """

    # --- Graph Tools ---

    def g_stats():
        """Get graph statistics: triple count, class count, property count, namespaces.

        Returns: dict with keys 'triples', 'classes', 'props', 'ns'

        Example: stats = g_stats()
        """
        return G.g_stats(graph_ref)

    def g_classes(limit=50):
        """Get list of OWL class URIs in the graph.

        Args:
            limit: Maximum number of classes to return (default 50)

        Returns: List of class URI strings (can be sliced, iterated)

        Example:
            classes = g_classes()
            print(classes[:10])  # First 10 classes
            classes = g_classes(20)  # Get 20 classes
        """
        # Handle DSPy convention: g_classes([50], {}) or g_classes([50])
        if isinstance(limit, list) and len(limit) >= 1:
            limit = limit[0] if not isinstance(limit[0], dict) else 50
        return G.g_classes_list(graph_ref, limit)

    def g_props(limit=50):
        """Get list of OWL property URIs in the graph.

        Args:
            limit: Maximum number of properties to return (default 50)

        Returns: List of property URI strings (can be sliced, iterated)

        Example:
            props = g_props()
            print(props[:10])  # First 10 properties
        """
        # Handle DSPy convention
        if isinstance(limit, list) and len(limit) >= 1:
            limit = limit[0] if not isinstance(limit[0], dict) else 50
        return G.g_props_list(graph_ref, limit)

    def g_query(q='', limit=100):
        """Execute SPARQL query and return results as handle.

        Args:
            q: SPARQL query string
            limit: Maximum results (default 100)

        Returns:
            Handle dict: {'key': 'results_N', 'dtype': 'results', 'sz': int, 'prev': str}

        Usage:
            result = g_query('SELECT ?s WHERE { ?s a owl:Class } LIMIT 10')

            # Option 1: Pass handle directly to ctx_peek (preferred)
            print(ctx_peek(result))

            # Option 2: Extract key explicitly
            print(ctx_peek(result['key'], 500))

            # Check result size before reading
            stats = ctx_stats(result)
            print(f"Result has {stats['lines']} lines")
        """
        # Handle DSPy convention: g_query(['SELECT...'], {'limit': 50})
        if isinstance(q, list):
            if len(q) >= 1 and isinstance(q[0], str):
                q = q[0]
            else:
                q = ''
        if isinstance(limit, dict):
            limit = limit.get('limit', 100)
        return G.g_query(graph_ref, q, limit)

    def g_sample(n=10):
        """Get sample triples from the graph as text.

        Args:
            n: Number of triples to sample (default 10)

        Returns: String with sample triples, one per line

        Example: print(g_sample(5))
        """
        # Handle DSPy convention
        if isinstance(n, list) and len(n) >= 1:
            n = n[0] if not isinstance(n[0], dict) else 10
        return G.g_sample(graph_ref, n)

    def g_describe(uri='', limit=20):
        """Describe a specific URI - get all triples where URI is subject.

        Args:
            uri: The URI to describe
            limit: Maximum triples to return (default 20)

        Returns: String with property-value pairs

        Example: print(g_describe('http://www.w3.org/ns/prov#Activity'))
        """
        # Handle DSPy convention: g_describe(['uri'], {'limit': 10})
        if isinstance(uri, list):
            if len(uri) >= 1 and isinstance(uri[0], str):
                uri = uri[0]
            else:
                uri = ''
        if isinstance(limit, dict):
            limit = limit.get('limit', 20)
        return G.g_describe(graph_ref, uri, limit)

    # --- Context Tools (for inspecting handles) ---

    def ctx_peek(key='', n=200):
        """Peek at first n characters of a stored result.

        Args:
            key: The result key (string) OR the full handle dict from g_query
            n: Number of characters to show (default 200)

        Returns: String preview of the content

        Example:
            result = g_query('SELECT...')
            print(ctx_peek(result))       # Pass handle directly
            print(ctx_peek(result['key'], 500))  # Or extract key
        """
        # Accept full handle dict - extract 'key' field
        if isinstance(key, dict) and 'key' in key:
            key = key['key']
        # Handle DSPy convention: ctx_peek(['key'], {'n': 500})
        if isinstance(key, list):
            if len(key) >= 1 and isinstance(key[0], str):
                key = key[0]
            elif len(key) >= 1 and isinstance(key[0], dict) and 'key' in key[0]:
                key = key[0]['key']  # Handle [{'key': '...', ...}]
            else:
                key = ''
        if isinstance(n, dict):
            n = n.get('n', 200)
        k = _unwrap_key(key)
        if not k:
            return {'error': 'missing key - pass the key from a query result'}
        return store.peek(k, n)

    def ctx_slice(key='', start=0, end=100):
        """Get a slice of stored content by character position.

        Args:
            key: The result key (string) OR the full handle dict from g_query
            start: Start character index (default 0)
            end: End character index (default 100)

        Returns: String slice of the content

        Example:
            result = g_query('SELECT...')
            print(ctx_slice(result, 0, 500))  # Pass handle directly
            print(ctx_slice(result['key'], 0, 500))  # Or extract key
        """
        # Accept full handle dict - extract 'key' field
        if isinstance(key, dict) and 'key' in key:
            key = key['key']
        # Handle DSPy convention: ctx_slice(['key'], {'start': 0, 'end': 500})
        if isinstance(key, list):
            if len(key) >= 1 and isinstance(key[0], str):
                key = key[0]
            elif len(key) >= 1 and isinstance(key[0], dict) and 'key' in key[0]:
                key = key[0]['key']  # Handle [{'key': '...', ...}]
            else:
                key = ''
        if isinstance(start, dict):
            kwargs = start
            start = kwargs.get('start', 0)
            end = kwargs.get('end', 100)
        k = _unwrap_key(key)
        if not k:
            return {'error': 'missing key - pass the key from a query result'}
        return store.slice(k, start, end)

    def ctx_stats(key=''):
        """Get statistics about stored content.

        Args:
            key: The result key (string) OR the full handle dict from g_query

        Returns: Dict with 'sz' (size) and 'lines' (line count)

        Example:
            result = g_query('SELECT...')
            stats = ctx_stats(result)       # Pass handle directly
            stats = ctx_stats(result['key'])  # Or extract key
        """
        # Accept full handle dict - extract 'key' field
        if isinstance(key, dict) and 'key' in key:
            key = key['key']
        # Handle DSPy convention: ctx_stats(['key'], {})
        if isinstance(key, list):
            if len(key) >= 1 and isinstance(key[0], str):
                key = key[0]
            elif len(key) >= 1 and isinstance(key[0], dict) and 'key' in key[0]:
                key = key[0]['key']  # Handle [{'key': '...', ...}]
            else:
                key = ''
        k = _unwrap_key(key)
        if not k:
            return {'error': 'missing key - pass the key from a query result'}
        return store.stats(k)

    tools = {
        'g_stats': g_stats,
        'g_classes': g_classes,
        'g_props': g_props,
        'g_query': g_query,
        'g_sample': g_sample,
        'g_describe': g_describe,
        'ctx_peek': ctx_peek,
        'ctx_slice': ctx_slice,
        'ctx_stats': ctx_stats,
    }

    # --- Memory Tools (if memory store provided) ---

    if mem:
        def mem_search(q='', k=6, polarity=None):
            """Search procedural memory for relevant strategies.

            Args:
                q: Search query string
                k: Number of results (default 6)
                polarity: Filter by 'success', 'failure', or None for all

            Returns: List of {id, title, desc, src} dicts (not full content)

            Example:
                hits = mem_search('SPARQL query patterns')
                for h in hits: print(h['title'])
            """
            # Handle DSPy convention: mem_search(['query'], {'k': 3})
            if isinstance(q, list):
                if len(q) >= 1 and isinstance(q[0], str):
                    q = q[0]
                else:
                    q = ''
            if isinstance(k, dict):
                kwargs = k
                k = kwargs.get('k', 6)
                polarity = kwargs.get('polarity', polarity)
            return mem.search(q, k, polarity)

        def mem_get(ids=None, max_n=3, max_chars=1000):
            """Get full content of memory items by ID.

            Args:
                ids: List of item IDs to retrieve
                max_n: Maximum items to return (default 3, hard cap)
                max_chars: Truncate content to this length (default 1000)

            Returns: List of full item dicts with content

            Example:
                hits = mem_search('query patterns')
                items = mem_get([h['id'] for h in hits[:2]])
            """
            # Handle DSPy convention: mem_get([['id1', 'id2']], {'max_n': 2})
            if ids is None:
                ids = []
            if isinstance(ids, list) and len(ids) == 1 and isinstance(ids[0], list):
                ids = ids[0]  # Unwrap nested list from DSPy
            if isinstance(max_n, dict):
                kwargs = max_n
                max_n = kwargs.get('max_n', 3)
                max_chars = kwargs.get('max_chars', 1000)

            id_list = ids
            if not isinstance(id_list, list):
                id_list = [id_list] if id_list else []

            items = mem.get(id_list, max_n)
            mc = max_chars
            return [
                {
                    'id': o.id,
                    'title': o.title,
                    'desc': o.desc,
                    'content': o.content[:mc] + ('...' if len(o.content) > mc else ''),
                    'src': o.src
                }
                for o in items
            ]

        def mem_quote(id='', max_chars=500):
            """Get a bounded excerpt from a specific memory item.

            Args:
                id: Item ID
                max_chars: Maximum characters (default 500)

            Returns: String excerpt of the item content

            Example: print(mem_quote('abc123', 200))
            """
            # Handle DSPy convention: mem_quote(['id'], {'max_chars': 200})
            if isinstance(id, list):
                if len(id) >= 1 and isinstance(id[0], str):
                    id = id[0]
                else:
                    id = ''
            if isinstance(max_chars, dict):
                max_chars = max_chars.get('max_chars', 500)
            return mem.quote(id, max_chars)

        tools.update({
            'mem_search': mem_search,
            'mem_get': mem_get,
            'mem_quote': mem_quote,
        })

    return tools
