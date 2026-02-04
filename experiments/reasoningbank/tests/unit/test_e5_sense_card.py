"""Simulate E5 sense card generation to see output format."""

import json
from pathlib import Path

# Load the E5 UniProt guide
guide_path = Path("/Users/cvardema/dev/git/LA3D/rlm/experiments/ontology_exploration/e5_uniprot_guide.json")
with open(guide_path) as f:
    guide = json.load(f)

# Apply the E5 create_guide_summary function
def create_guide_summary(guide: dict) -> str:
    """Extract concise summary from full guide."""
    summary_parts = []

    # Overview
    if 'ontology_overview' in guide:
        ov = guide['ontology_overview']
        summary_parts.append(f"{ov['name']}: {ov['purpose']}")

    # Core classes from first category
    if 'semantic_categories' in guide and len(guide['semantic_categories']) > 0:
        core = guide['semantic_categories'][0]
        summary_parts.append(f"\nCore Classes: {', '.join([c['name'] for c in core['classes'][:5]])}")

    # Key properties
    if 'properties' in guide and 'object_properties' in guide['properties']:
        props = guide['properties']['object_properties'][:8]
        summary_parts.append("\nKey Properties:")
        for p in props:
            summary_parts.append(f"- {p['name']}: {p['description'][:80] if p.get('description') else 'Links entities'}")

    # Query patterns
    if 'query_patterns' in guide:
        summary_parts.append(f"\nCommon Patterns: {len(guide['query_patterns'])} templates available")
        for qp in guide['query_patterns'][:2]:
            summary_parts.append(f"- {qp['name']}: {qp['description'][:60]}")

    return '\n'.join(summary_parts)

summary = create_guide_summary(guide)

print("=" * 70)
print("E5 SENSE CARD OUTPUT")
print("=" * 70)
print(summary)
print()
print("=" * 70)
print(f"Total length: {len(summary)} characters")
print("=" * 70)
