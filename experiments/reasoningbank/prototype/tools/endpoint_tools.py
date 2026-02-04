"""Endpoint discovery and exploration tools following RLM pattern.

Tools for agentic discovery of SPARQL endpoints:
1. Static discovery - from SHACL examples (federated_endpoints)
2. Dynamic discovery - from service descriptions (service_desc)

All tools follow RLM constraints:
- Return handles (Ref), not payloads
- Bounded returns with hard caps
- Source attribution in all returns
- DSPy RLM signatures: lambda args, kwargs:

Usage:
    from experiments.reasoningbank.prototype.tools.endpoint_tools import EndpointTools

    tools = EndpointTools()

    # Static discovery from SHACL examples
    ref = tools.federated_endpoints('ontology/uniprot')
    endpoints = tools.endpoints_list(ref.key, limit=10)

    # Dynamic discovery from service description
    sd_ref = tools.service_desc('https://sparql.uniprot.org/sparql/')
    graphs = tools.service_desc_graphs(sd_ref.key)
"""

from __future__ import annotations
from dataclasses import dataclass
from typing import Optional
import requests
from rdflib import Graph, Namespace

try:
    from experiments.reasoningbank.prototype.tools.discovery import (
        discover_endpoints, EndpointRegistry, EndpointMetadata
    )
except ModuleNotFoundError:
    import sys
    sys.path.insert(0, '/Users/cvardema/dev/git/LA3D/rlm')
    from experiments.reasoningbank.prototype.tools.discovery import (
        discover_endpoints, EndpointRegistry, EndpointMetadata
    )


# Service Description namespace
SD = Namespace('http://www.w3.org/ns/sparql-service-description#')


@dataclass
class Ref:
    """Handle for large data - REPL sees metadata, not payload."""
    key: str
    dtype: str      # 'registry', 'service_desc'
    rows: int       # item/triple count
    sz: int         # char count
    source: str     # URL or path for attribution

    def __repr__(self):
        return f"Ref({self.key!r}, {self.dtype!r}, {self.rows} items, {self.sz} chars from {self.source})"


class EndpointTools:
    """RLM-friendly endpoint discovery and exploration tools."""

    def __init__(self):
        self._registries: dict[str, EndpointRegistry] = {}
        self._graphs: dict[str, Graph] = {}
        self._sources: dict[str, str] = {}
        self._counter = 0

    def _next_key(self, prefix: str) -> str:
        key = f"{prefix}_{self._counter}"
        self._counter += 1
        return key

    # =========================================================================
    # Static Discovery (from SHACL examples)
    # =========================================================================

    def federated_endpoints(self, ontology_path: str) -> Ref:
        """Discover federated endpoints from SHACL examples.

        Scans examples for SERVICE clauses, schema:target, FROM clauses.
        Returns handle to discovered endpoint registry.

        Args:
            ontology_path: Path to ontology directory (e.g., 'ontology/uniprot')

        Returns:
            Ref handle. Use endpoints_list() to inspect.
        """
        registry = discover_endpoints(ontology_path)

        key = self._next_key('registry')
        self._registries[key] = registry
        self._sources[key] = ontology_path

        # Count total endpoints
        total = len(registry.federated_endpoints)
        if registry.primary_endpoint:
            total += 1

        # Estimate size
        sz = len(str(registry.summary()))

        return Ref(key, 'registry', total, sz, ontology_path)

    def endpoints_list(self, ref_key: str, limit: int = 10) -> dict:
        """List discovered endpoints (bounded).

        Args:
            ref_key: Key from federated_endpoints()
            limit: Max endpoints to return (hard cap: 50)

        Returns:
            {source, count, primary, federated: [{name, url, example_count}]}
        """
        limit = min(limit, 50)  # Hard cap
        registry = self._registries.get(ref_key)
        if not registry:
            return {'error': f'Unknown registry: {ref_key}'}

        result = {
            'source': self._sources.get(ref_key, 'unknown'),
            'count': len(registry.federated_endpoints) + (1 if registry.primary_endpoint else 0),
            'primary': None,
            'federated': [],
        }

        if registry.primary_endpoint:
            result['primary'] = {
                'name': registry.primary_endpoint.name,
                'url': registry.primary_endpoint.url,
                'example_count': registry.primary_endpoint.example_count,
            }

        # Sort by example count and limit
        sorted_fed = sorted(
            registry.federated_endpoints.values(),
            key=lambda e: -e.example_count
        )[:limit]

        result['federated'] = [
            {
                'name': ep.name,
                'url': ep.url,
                'example_count': ep.example_count,
            }
            for ep in sorted_fed
        ]

        return result

    def endpoint_detail(self, ref_key: str, name: str) -> dict:
        """Get detailed info about a specific endpoint.

        Args:
            ref_key: Key from federated_endpoints()
            name: Endpoint name to look up

        Returns:
            {source, name, url, example_count, query_types, prefixes}
        """
        registry = self._registries.get(ref_key)
        if not registry:
            return {'error': f'Unknown registry: {ref_key}'}

        # Check primary
        if registry.primary_endpoint and registry.primary_endpoint.name == name:
            ep = registry.primary_endpoint
        else:
            # Find in federated
            ep = None
            for fed_ep in registry.federated_endpoints.values():
                if fed_ep.name == name:
                    ep = fed_ep
                    break

        if not ep:
            return {'error': f'Unknown endpoint: {name}'}

        return {
            'source': self._sources.get(ref_key, 'unknown'),
            'name': ep.name,
            'url': ep.url,
            'example_count': ep.example_count,
            'query_types': list(ep.query_types),
            'prefixes': dict(list(ep.prefixes.items())[:20]),  # Bounded
        }

    def data_graphs(self, ref_key: str, limit: int = 20) -> dict:
        """List data graphs discovered from FROM clauses.

        Args:
            ref_key: Key from federated_endpoints()
            limit: Max graphs to return (hard cap: 50)

        Returns:
            {source, count, graphs: [uri]}
        """
        limit = min(limit, 50)
        registry = self._registries.get(ref_key)
        if not registry:
            return {'error': f'Unknown registry: {ref_key}'}

        return {
            'source': self._sources.get(ref_key, 'unknown'),
            'count': len(registry.data_graphs),
            'graphs': registry.data_graphs[:limit],
        }

    # =========================================================================
    # Dynamic Discovery (from Service Description)
    # =========================================================================

    def service_desc(self, url: str, timeout: int = 30) -> Ref:
        """Fetch endpoint service description via GET.

        GET {url}
        Accept: text/turtle, application/rdf+xml

        Args:
            url: SPARQL endpoint URL
            timeout: Request timeout in seconds

        Returns:
            Ref handle. Use service_desc_* tools to inspect.
        """
        try:
            resp = requests.get(
                url,
                headers={'Accept': 'text/turtle, application/rdf+xml;q=0.9'},
                timeout=timeout
            )
            resp.raise_for_status()

            # Try parsing as turtle first, then RDF/XML
            g = Graph()
            try:
                g.parse(data=resp.text, format='turtle')
            except Exception:
                g.parse(data=resp.text, format='xml')

            key = self._next_key('sd')
            self._graphs[key] = g
            self._sources[key] = url

            return Ref(key, 'service_desc', len(g), len(resp.text), url)

        except requests.RequestException as e:
            # Return error ref
            key = self._next_key('sd_error')
            self._sources[key] = url
            return Ref(key, 'error', 0, 0, f"Failed: {e}")

    def service_desc_stats(self, ref_key: str) -> dict:
        """Get stats about service description.

        Returns:
            {source, triples, namespaces}
        """
        g = self._graphs.get(ref_key)
        if not g:
            return {'error': f'Unknown service description: {ref_key}'}

        return {
            'source': self._sources.get(ref_key, 'unknown'),
            'triples': len(g),
            'namespaces': {p: str(n) for p, n in list(g.namespaces())[:15]},
        }

    def service_desc_graphs(self, ref_key: str, limit: int = 20) -> dict:
        """List named graphs from service description.

        Args:
            ref_key: Key from service_desc()
            limit: Max graphs to return (hard cap: 50)

        Returns:
            {source, count, graphs: [uri]}
        """
        limit = min(limit, 50)
        g = self._graphs.get(ref_key)
        if not g:
            return {'error': f'Unknown service description: {ref_key}'}

        # Query for named graphs
        graphs = []
        for ng in g.objects(None, SD.namedGraph):
            name = g.value(ng, SD.name)
            if name:
                graphs.append(str(name))

        return {
            'source': self._sources.get(ref_key, 'unknown'),
            'count': len(graphs),
            'graphs': graphs[:limit],
        }

    def service_desc_features(self, ref_key: str, limit: int = 20) -> dict:
        """List supported features from service description.

        Args:
            ref_key: Key from service_desc()
            limit: Max features to return (hard cap: 50)

        Returns:
            {source, count, features: [name]}
        """
        limit = min(limit, 50)
        g = self._graphs.get(ref_key)
        if not g:
            return {'error': f'Unknown service description: {ref_key}'}

        features = []
        for f in g.objects(None, SD.feature):
            # Extract local name from URI
            name = str(f).split('#')[-1].split('/')[-1]
            features.append(name)

        return {
            'source': self._sources.get(ref_key, 'unknown'),
            'count': len(features),
            'features': features[:limit],
        }

    def service_desc_sample(self, ref_key: str, n: int = 10) -> dict:
        """Sample triples from service description.

        Args:
            ref_key: Key from service_desc()
            n: Number of triples to sample (hard cap: 20)

        Returns:
            {source, count, triples: [str]}
        """
        n = min(n, 20)
        g = self._graphs.get(ref_key)
        if not g:
            return {'error': f'Unknown service description: {ref_key}'}

        triples = [
            f"{s} {p} {o}"
            for s, p, o in list(g)[:n]
        ]

        return {
            'source': self._sources.get(ref_key, 'unknown'),
            'count': len(g),
            'triples': triples,
        }

    # =========================================================================
    # DSPy RLM Interface
    # =========================================================================

    def as_dspy_tools(self) -> dict:
        """Return DSPy RLM compatible tool dict.

        All tools use signature: lambda args, kwargs: ...
        """
        def _get_arg(args, kwargs, idx, name, default):
            if isinstance(args, list) and len(args) > idx:
                return args[idx]
            if isinstance(args, (str, int)) and idx == 0:
                return args
            return kwargs.get(name, default)

        return {
            # Static discovery
            'federated_endpoints': lambda args, kwargs: self.federated_endpoints(
                _get_arg(args, kwargs, 0, 'ontology_path', '')
            ),
            'endpoints_list': lambda args, kwargs: self.endpoints_list(
                _get_arg(args, kwargs, 0, 'ref_key', ''),
                _get_arg(args, kwargs, 1, 'limit', 10)
            ),
            'endpoint_detail': lambda args, kwargs: self.endpoint_detail(
                _get_arg(args, kwargs, 0, 'ref_key', ''),
                _get_arg(args, kwargs, 1, 'name', '')
            ),
            'data_graphs': lambda args, kwargs: self.data_graphs(
                _get_arg(args, kwargs, 0, 'ref_key', ''),
                _get_arg(args, kwargs, 1, 'limit', 20)
            ),
            # Dynamic discovery
            'service_desc': lambda args, kwargs: self.service_desc(
                _get_arg(args, kwargs, 0, 'url', ''),
                _get_arg(args, kwargs, 1, 'timeout', 30)
            ),
            'service_desc_stats': lambda args, kwargs: self.service_desc_stats(
                _get_arg(args, kwargs, 0, 'ref_key', '')
            ),
            'service_desc_graphs': lambda args, kwargs: self.service_desc_graphs(
                _get_arg(args, kwargs, 0, 'ref_key', ''),
                _get_arg(args, kwargs, 1, 'limit', 20)
            ),
            'service_desc_features': lambda args, kwargs: self.service_desc_features(
                _get_arg(args, kwargs, 0, 'ref_key', ''),
                _get_arg(args, kwargs, 1, 'limit', 20)
            ),
            'service_desc_sample': lambda args, kwargs: self.service_desc_sample(
                _get_arg(args, kwargs, 0, 'ref_key', ''),
                _get_arg(args, kwargs, 1, 'n', 10)
            ),
        }


# =============================================================================
# Test function
# =============================================================================

def test_endpoint_tools():
    """Test endpoint discovery tools."""
    print("Testing EndpointTools...\n")

    tools = EndpointTools()

    # Test static discovery
    print("=== Static Discovery ===")
    ref = tools.federated_endpoints('ontology/uniprot')
    print(f"Discovered: {ref}")

    endpoints = tools.endpoints_list(ref.key, limit=5)
    print(f"Primary: {endpoints.get('primary')}")
    print(f"Federated ({endpoints['count']} total):")
    for ep in endpoints['federated']:
        print(f"  - {ep['name']}: {ep['example_count']} examples")

    graphs = tools.data_graphs(ref.key, limit=5)
    print(f"Data graphs: {graphs['count']} total")

    # Test dynamic discovery
    print("\n=== Dynamic Discovery ===")
    sd_ref = tools.service_desc('https://sparql.uniprot.org/sparql/')
    print(f"Service description: {sd_ref}")

    if sd_ref.dtype != 'error':
        stats = tools.service_desc_stats(sd_ref.key)
        print(f"Stats: {stats['triples']} triples")

        features = tools.service_desc_features(sd_ref.key)
        print(f"Features: {features['features']}")

        named_graphs = tools.service_desc_graphs(sd_ref.key)
        print(f"Named graphs: {named_graphs['count']}")

    # Test DSPy interface
    print("\n=== DSPy Interface ===")
    dspy_tools = tools.as_dspy_tools()
    print(f"Tools: {list(dspy_tools.keys())}")

    # Test with DSPy calling convention
    ref2 = dspy_tools['federated_endpoints']('ontology/uniprot', {})
    print(f"DSPy call: {ref2}")

    print("\n✓ All tests passed")


if __name__ == '__main__':
    test_endpoint_tools()
