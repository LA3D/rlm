"""Dynamic SPARQL endpoint discovery from ontology files and examples.

Instead of hardcoding endpoint configurations, this module discovers them by:
1. Scanning example queries for schema:target, SERVICE clauses, FROM clauses
2. Extracting namespaces and prefixes from actual usage
3. Building EndpointConfig objects based on observed patterns

This aligns with RLM's progressive disclosure philosophy - learn about the
endpoints from how they're actually used, not from hardcoded metadata.

Usage:
    from experiments.reasoningbank.tools.discovery import discover_endpoints

    registry = discover_endpoints("ontology/uniprot")
    primary = registry.primary_endpoint
    federated = registry.federated_endpoints
"""

from dataclasses import dataclass, field
from pathlib import Path
from collections import defaultdict
import re
from typing import Optional

try:
    from experiments.reasoningbank.tools.uniprot_examples import load_examples, SPARQLExample
except ModuleNotFoundError:
    # Standalone execution
    import sys
    sys.path.insert(0, '/Users/cvardema/dev/git/LA3D/rlm')
    from experiments.reasoningbank.tools.uniprot_examples import load_examples, SPARQLExample


@dataclass
class EndpointMetadata:
    """Discovered metadata about a SPARQL endpoint."""
    url: str
    name: str                           # Inferred from domain
    example_count: int = 0              # How many examples use this endpoint
    query_types: set[str] = field(default_factory=set)  # SELECT, ASK, CONSTRUCT, etc.
    prefixes: dict[str, str] = field(default_factory=dict)  # Discovered prefixes
    is_primary: bool = False            # Primary vs federated
    is_federated: bool = False          # Used in SERVICE clauses
    sample_queries: list[str] = field(default_factory=list)  # Example query snippets

    def __repr__(self):
        role = "primary" if self.is_primary else "federated" if self.is_federated else "referenced"
        return f"EndpointMetadata({self.name!r}, {self.url}, {self.example_count} examples, {role})"


@dataclass
class EndpointRegistry:
    """Registry of discovered SPARQL endpoints and their metadata."""
    primary_endpoint: Optional[EndpointMetadata] = None
    federated_endpoints: dict[str, EndpointMetadata] = field(default_factory=dict)
    data_graphs: list[str] = field(default_factory=list)  # FROM clauses
    total_examples: int = 0

    def all_endpoints(self) -> list[EndpointMetadata]:
        """Get all endpoints (primary + federated)."""
        endpoints = []
        if self.primary_endpoint:
            endpoints.append(self.primary_endpoint)
        endpoints.extend(self.federated_endpoints.values())
        return endpoints

    def summary(self) -> str:
        """Human-readable summary of discovered endpoints."""
        lines = [f"Discovered {len(self.all_endpoints())} endpoints from {self.total_examples} examples:\n"]

        if self.primary_endpoint:
            lines.append(f"Primary: {self.primary_endpoint.name} ({self.primary_endpoint.example_count} examples)")

        if self.federated_endpoints:
            lines.append(f"\nFederated ({len(self.federated_endpoints)}):")
            for ep in sorted(self.federated_endpoints.values(), key=lambda e: -e.example_count):
                lines.append(f"  - {ep.name}: {ep.example_count} queries")

        if self.data_graphs:
            lines.append(f"\nData graphs: {', '.join(self.data_graphs[:5])}")

        return '\n'.join(lines)


def extract_service_endpoints(query: str) -> list[str]:
    """Extract SERVICE endpoint URLs from a SPARQL query."""
    pattern = r'SERVICE\s+<(https?://[^>]+)>'
    return re.findall(pattern, query, re.IGNORECASE)


def extract_from_graphs(query: str) -> list[str]:
    """Extract FROM graph URLs from a SPARQL query."""
    pattern = r'FROM\s+<(https?://[^>]+)>'
    return re.findall(pattern, query, re.IGNORECASE)


def extract_prefixes(query: str) -> dict[str, str]:
    """Extract PREFIX declarations from a SPARQL query."""
    pattern = r'PREFIX\s+(\w+):\s+<([^>]+)>'
    matches = re.findall(pattern, query, re.IGNORECASE)
    return dict(matches)


def extract_query_type(query: str) -> str:
    """Extract query type (SELECT, ASK, CONSTRUCT, DESCRIBE)."""
    for qtype in ['SELECT', 'ASK', 'CONSTRUCT', 'DESCRIBE']:
        if re.search(rf'\b{qtype}\b', query, re.IGNORECASE):
            return qtype
    return 'UNKNOWN'


def infer_endpoint_name(url: str) -> str:
    """Infer a human-readable name from endpoint URL."""
    # Extract domain
    domain_match = re.search(r'https?://(?:www\.|sparql\.)?([^/]+)', url)
    if not domain_match:
        return url

    domain = domain_match.group(1)

    # Known mappings
    mappings = {
        'uniprot.org': 'UniProt',
        'query.wikidata.org': 'Wikidata',
        'sparql.rhea-db.org': 'Rhea',
        'bgee.org': 'Bgee',
        'omabrowser.org': 'OMA Browser',
        'orthodb.org': 'OrthoDB',
        'glyconnect.expasy.org': 'GlyConnect',
        'identifiers.org': 'Identifiers.org',
        'bioregistry.io': 'Bioregistry',
        'allie.dbcls.jp': 'Allie',
        'cordis.europa.eu': 'CORDIS',
        'data.epo.org': 'EPO',
        'elixir-czech.cz': 'IDSM',
        'dbpedia.org': 'DBpedia',
        'wikipathways.org': 'WikiPathways',
    }

    for key, name in mappings.items():
        if key in domain:
            return name

    # Fallback: capitalize first part of domain
    parts = domain.split('.')
    return parts[0].capitalize()


def discover_endpoints(
    ontology_dir: str | Path,
    examples_subdir: str = "examples",
    max_sample_queries: int = 3
) -> EndpointRegistry:
    """Discover SPARQL endpoints from ontology examples.

    Args:
        ontology_dir: Path to ontology directory (e.g., "ontology/uniprot")
        examples_subdir: Subdirectory containing examples (default: "examples")
        max_sample_queries: Max sample queries to store per endpoint

    Returns:
        EndpointRegistry with discovered endpoints and metadata
    """
    ontology_dir = Path(ontology_dir)
    examples_dir = ontology_dir / examples_subdir

    if not examples_dir.exists():
        return EndpointRegistry()

    # Load examples (handles both TTL and RQ formats)
    examples = []

    # Try to load SHACL-annotated examples (TTL format)
    for subdir in examples_dir.iterdir():
        if subdir.is_dir():
            examples.extend(load_examples(subdir))

    # Also try loading from the examples directory itself
    examples.extend(load_examples(examples_dir))

    if not examples:
        return EndpointRegistry()

    # Initialize registry
    registry = EndpointRegistry(total_examples=len(examples))
    endpoint_data = defaultdict(lambda: EndpointMetadata(url="", name=""))

    # Analyze each example
    for example in examples:
        query = example.query

        # Extract primary endpoint from schema:target
        if example.target and example.target not in endpoint_data:
            endpoint_data[example.target].url = example.target
            endpoint_data[example.target].name = infer_endpoint_name(example.target)
            endpoint_data[example.target].is_primary = True

        if example.target:
            endpoint_data[example.target].example_count += 1
            endpoint_data[example.target].query_types.add(extract_query_type(query))

            # Store sample query
            if len(endpoint_data[example.target].sample_queries) < max_sample_queries:
                snippet = query[:200].replace('\n', ' ')
                endpoint_data[example.target].sample_queries.append(snippet)

        # Extract federated endpoints (SERVICE clauses)
        service_urls = extract_service_endpoints(query)
        for url in service_urls:
            if url not in endpoint_data:
                endpoint_data[url].url = url
                endpoint_data[url].name = infer_endpoint_name(url)
            endpoint_data[url].is_federated = True
            endpoint_data[url].example_count += 1
            endpoint_data[url].query_types.add(extract_query_type(query))

        # Extract data graphs (FROM clauses)
        graphs = extract_from_graphs(query)
        for graph in graphs:
            if graph not in registry.data_graphs:
                registry.data_graphs.append(graph)

        # Extract prefixes
        prefixes = extract_prefixes(query)
        if example.target:
            endpoint_data[example.target].prefixes.update(prefixes)
        for url in service_urls:
            endpoint_data[url].prefixes.update(prefixes)

    # Populate registry
    for url, metadata in endpoint_data.items():
        if metadata.is_primary:
            # Find the primary endpoint (most examples)
            if not registry.primary_endpoint or metadata.example_count > registry.primary_endpoint.example_count:
                registry.primary_endpoint = metadata

        if metadata.is_federated:
            registry.federated_endpoints[url] = metadata

    return registry


def registry_to_endpoint_config(metadata: EndpointMetadata):
    """Convert discovered EndpointMetadata to EndpointConfig for SPARQLTools."""
    from experiments.reasoningbank.tools.endpoint import EndpointConfig

    # Infer domain description from name
    domain_descriptions = {
        'UniProt': 'Protein sequences, functional annotation, and biological knowledge',
        'Rhea': 'Biochemical reactions and enzyme-catalyzed transformations',
        'Bgee': 'Gene expression data across species and anatomical structures',
        'OMA Browser': 'Orthology and evolutionary relationships between genes',
        'OrthoDB': 'Hierarchical catalog of orthologs across species',
        'Wikidata': 'General structured knowledge across all domains',
        'GlyConnect': 'Glycomics data and glycan structures',
        'Identifiers.org': 'Resolution and mapping of biological identifiers',
        'Bioregistry': 'Registry of biological databases and nomenclatures',
        'Allie': 'Abbreviations and their long forms in biomedical literature',
    }

    return EndpointConfig(
        url=metadata.url,
        name=metadata.name,
        authority=f"Discovered from {metadata.example_count} examples",
        domain=domain_descriptions.get(metadata.name, f"{metadata.name} knowledge base"),
        prefixes=metadata.prefixes,
    )


# Convenience function for testing
def test_discovery(ontology_dir: str = "ontology/uniprot"):
    """Test endpoint discovery on an ontology directory."""
    print(f"Discovering endpoints in {ontology_dir}...")
    registry = discover_endpoints(ontology_dir)
    print(registry.summary())

    if registry.primary_endpoint:
        print(f"\nPrimary endpoint prefixes ({len(registry.primary_endpoint.prefixes)}):")
        for prefix, uri in list(registry.primary_endpoint.prefixes.items())[:10]:
            print(f"  {prefix}: {uri}")

    return registry


if __name__ == '__main__':
    test_discovery()
