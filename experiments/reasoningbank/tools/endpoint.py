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
