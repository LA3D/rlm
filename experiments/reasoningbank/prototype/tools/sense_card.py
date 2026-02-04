"""Build L0 sense cards from discovered endpoints.

L0 provides compact orientation metadata about available SPARQL endpoints,
discovered dynamically from examples rather than hardcoded.
"""

try:
    from experiments.reasoningbank.prototype.tools.discovery import EndpointRegistry
except ModuleNotFoundError:
    import sys
    sys.path.insert(0, '/Users/cvardema/dev/git/LA3D/rlm')
    from experiments.reasoningbank.prototype.tools.discovery import EndpointRegistry


def build_sense_card(registry: EndpointRegistry, budget: int = 800) -> str:
    """Build L0 sense card from discovered endpoints.

    Args:
        registry: Discovered endpoint registry
        budget: Character budget for the sense card

    Returns:
        Formatted sense card text
    """
    lines = []

    # Header
    if registry.primary_endpoint:
        lines.append(f"**Primary Endpoint**: {registry.primary_endpoint.name}")
        lines.append(f"**URL**: {registry.primary_endpoint.url}")
        lines.append(f"**Examples**: {registry.primary_endpoint.example_count} queries")
        lines.append(f"**Query types**: {', '.join(sorted(registry.primary_endpoint.query_types))}")

    # Federated endpoints
    if registry.federated_endpoints:
        lines.append(f"\n**Federated Endpoints** ({len(registry.federated_endpoints)}):")

        # Show top federated endpoints by usage
        sorted_endpoints = sorted(
            registry.federated_endpoints.values(),
            key=lambda e: -e.example_count
        )

        for ep in sorted_endpoints[:8]:  # Top 8
            lines.append(f"- {ep.name}: {ep.example_count} queries")

        if len(sorted_endpoints) > 8:
            remaining = len(sorted_endpoints) - 8
            lines.append(f"- ...and {remaining} more")

    # Data graphs
    if registry.data_graphs:
        lines.append(f"\n**Data Graphs** ({len(registry.data_graphs)}):")
        for graph in registry.data_graphs[:5]:
            # Shorten graph URIs
            short = graph.split('/')[-1] if '/' in graph else graph
            lines.append(f"- {short}")
        if len(registry.data_graphs) > 5:
            lines.append(f"- ...and {len(registry.data_graphs) - 5} more")

    # Discovered prefixes (from primary)
    if registry.primary_endpoint and registry.primary_endpoint.prefixes:
        lines.append(f"\n**Key Prefixes** ({len(registry.primary_endpoint.prefixes)}):")
        # Show most common/important prefixes
        common_prefixes = ['rdf', 'rdfs', 'owl', 'xsd', 'skos']
        shown = []
        for prefix in common_prefixes:
            if prefix in registry.primary_endpoint.prefixes:
                shown.append(prefix)
        # Add a few others
        for prefix in list(registry.primary_endpoint.prefixes.keys()):
            if prefix not in shown and len(shown) < 8:
                shown.append(prefix)
        lines.append(', '.join(shown))

    result = '\n'.join(lines)

    # Trim to budget if needed
    if len(result) > budget:
        result = result[:budget]
        # Try to end at a line break
        last_newline = result.rfind('\n')
        if last_newline > budget * 0.8:  # Within 20% of budget
            result = result[:last_newline]

    return result


def build_compact_sense_card(registry: EndpointRegistry, budget: int = 400) -> str:
    """Build ultra-compact sense card for tight budgets."""
    lines = []

    if registry.primary_endpoint:
        lines.append(f"{registry.primary_endpoint.name} ({registry.primary_endpoint.example_count} examples)")

    if registry.federated_endpoints:
        top_3 = sorted(registry.federated_endpoints.values(), key=lambda e: -e.example_count)[:3]
        fed_names = ', '.join(ep.name for ep in top_3)
        lines.append(f"Federated: {fed_names} (+{len(registry.federated_endpoints)-3} more)")

    result = ' | '.join(lines)
    return result[:budget]


# Test function
def test_sense_card():
    """Test sense card generation."""
    import sys
    sys.path.insert(0, '/Users/cvardema/dev/git/LA3D/rlm')

    from experiments.reasoningbank.prototype.tools.discovery import discover_endpoints

    print("Discovering endpoints...")
    registry = discover_endpoints("ontology/uniprot")

    print("\n" + "=" * 60)
    print("L0 SENSE CARD (800 char budget)")
    print("=" * 60)
    card = build_sense_card(registry, budget=800)
    print(card)
    print(f"\nSize: {len(card)} chars")

    print("\n" + "=" * 60)
    print("COMPACT SENSE CARD (400 char budget)")
    print("=" * 60)
    compact = build_compact_sense_card(registry, budget=400)
    print(compact)
    print(f"\nSize: {len(compact)} chars")


if __name__ == '__main__':
    test_sense_card()
