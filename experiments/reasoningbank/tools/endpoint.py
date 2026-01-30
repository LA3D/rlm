"""SPARQL endpoint configuration structures.

This module provides EndpointConfig - a dataclass for endpoint metadata.
Endpoints are discovered dynamically via:
- discovery.py: Finds federated endpoints from SHACL examples
- Service description: GET on endpoint URL returns RDF describing capabilities

The agent discovers endpoint capabilities through tools, not pre-loaded context.
See IMPLEMENTATION_PLAN.md for the agentic discovery architecture.
"""

from dataclasses import dataclass, field


@dataclass
class EndpointConfig:
    """Metadata for a SPARQL endpoint.

    Used by SPARQLTools to configure query execution.
    Can be created from discovery.py's registry_to_endpoint_config().
    """
    # Connection
    url: str
    prefixes: dict[str, str] = field(default_factory=dict)

    # Identity
    name: str = ""
    authority: str = ""  # Who maintains this endpoint

    # Domain
    domain: str = ""  # What kind of knowledge

    # Operational
    timeout: int = 30
    default_limit: int = 100
    max_limit: int = 1000

    def prefix_block(self) -> str:
        """Generate SPARQL PREFIX declarations."""
        lines = []
        for prefix, uri in self.prefixes.items():
            lines.append(f"PREFIX {prefix}: <{uri}>")
        return '\n'.join(lines)


# Pre-configured endpoints
ENDPOINTS = {
    'uniprot': EndpointConfig(
        url='https://sparql.uniprot.org/sparql/',
        name='UniProt',
        authority='UniProt Consortium (EMBL-EBI, SIB, PIR)',
        domain='protein sequences and functional information',
        prefixes={
            'up': 'http://purl.uniprot.org/core/',
            'taxon': 'http://purl.uniprot.org/taxonomy/',
            'rdf': 'http://www.w3.org/1999/02/22-rdf-syntax-ns#',
            'rdfs': 'http://www.w3.org/2000/01/rdf-schema#',
            'owl': 'http://www.w3.org/2002/07/owl#',
            'skos': 'http://www.w3.org/2004/02/skos/core#',
        },
        default_limit=100,
        max_limit=1000,
        timeout=30,
    ),
    'wikidata': EndpointConfig(
        url='https://query.wikidata.org/sparql',
        name='Wikidata',
        authority='Wikimedia Foundation',
        domain='general knowledge',
        prefixes={
            'wd': 'http://www.wikidata.org/entity/',
            'wdt': 'http://www.wikidata.org/prop/direct/',
            'rdfs': 'http://www.w3.org/2000/01/rdf-schema#',
            'skos': 'http://www.w3.org/2004/02/skos/core#',
        },
        default_limit=100,
        max_limit=1000,
        timeout=30,
    ),
}


def get_endpoint(name: str) -> EndpointConfig:
    """Get pre-configured endpoint by name.

    Args:
        name: One of 'uniprot', 'wikidata'

    Returns:
        EndpointConfig for the specified endpoint

    Raises:
        KeyError: If endpoint name not recognized
    """
    if name not in ENDPOINTS:
        raise KeyError(f"Unknown endpoint: {name}. Available: {list(ENDPOINTS.keys())}")
    return ENDPOINTS[name]
