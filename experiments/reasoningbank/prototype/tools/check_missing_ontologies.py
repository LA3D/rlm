"""Check which ontologies we're missing for discovered endpoints.

Compares discovered federated endpoints against available ontology files
and reports what's missing.
"""

import sys
from pathlib import Path

sys.path.insert(0, '/Users/cvardema/dev/git/LA3D/rlm')

from experiments.reasoningbank.prototype.tools.endpoint_tools import EndpointTools


def check_missing_ontologies():
    """Check which ontologies are missing."""
    tools = EndpointTools()

    # Discover endpoints from UniProt examples
    ref = tools.federated_endpoints('ontology/uniprot')
    endpoints = tools.endpoints_list(ref.key, limit=50)

    # Get list of available ontology directories
    ontology_dir = Path('ontology')
    available = {d.name.lower() for d in ontology_dir.iterdir() if d.is_dir()}

    print("=" * 70)
    print("DISCOVERED ENDPOINTS vs AVAILABLE ONTOLOGIES")
    print("=" * 70)

    # Check primary
    if endpoints.get('primary'):
        ep = endpoints['primary']
        name = ep['name'].lower()
        print(f"\nPrimary: {ep['name']} ({ep['example_count']} examples)")
        print(f"  URL: {ep['url']}")
        if name in available:
            print(f"  ✓ Have ontology/{name}/")
        else:
            print(f"  ✗ MISSING ontology/{name}/")

    # Check federated
    print(f"\nFederated ({len(endpoints['federated'])} endpoints):")
    missing = []

    for ep in endpoints['federated']:
        name = ep['name']
        name_lower = name.lower().replace('-', '').replace(' ', '')

        # Check various name variations
        found = False
        for avail in available:
            if (name_lower in avail or
                avail in name_lower or
                name.lower() in avail):
                found = True
                break

        status = "✓" if found else "✗"
        print(f"  {status} {name}: {ep['example_count']} examples")
        print(f"      {ep['url']}")

        if not found:
            missing.append(ep)

    # Summary
    print("\n" + "=" * 70)
    print(f"Summary: {len(missing)} ontologies missing")
    print("=" * 70)

    if missing:
        print("\nMissing ontologies:")
        for ep in missing:
            print(f"  - {ep['name']}: {ep['url']}")

    return missing


if __name__ == '__main__':
    missing = check_missing_ontologies()
