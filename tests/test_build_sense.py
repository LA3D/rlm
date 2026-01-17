"""Test build_sense function with PROV ontology."""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from rlm.ontology import build_sense

# Test with PROV ontology
ns = {}
result = build_sense('ontology/prov.ttl', name='prov_sense', ns=ns)
print(f"Result: {result}")
print()

# Inspect the sense document
sense = ns['prov_sense']
print("="*60)
print("PROV ONTOLOGY SENSE DOCUMENT")
print("="*60)
print(f"Ontology: {sense.ont}")
print(f"Stats: {sense.stats}")
print(f"URI Pattern: {sense.uri_pattern}")
print()

print(f"Root Classes ({len(sense.roots)}):")
for i, root in enumerate(sense.roots[:5], 1):
    print(f"  {i}. {root}")
print()

print(f"Hierarchy Branches ({len(sense.hier)}):")
for branch, children in list(sense.hier.items())[:3]:
    print(f"  {branch}:")
    for child, grandchildren in list(children.items())[:2]:
        print(f"    - {child} ({len(grandchildren)} subclasses)")
print()

print(f"Top Properties ({len(sense.top_props)}):")
for i, (prop, dom, rng) in enumerate(sense.top_props[:5], 1):
    print(f"  {i}. {prop}")
    if dom or rng:
        print(f"     Domain: {dom or 'N/A'}, Range: {rng or 'N/A'}")
print()

print(f"Property Characteristics ({len(sense.prop_chars)}):")
for prop, chars in list(sense.prop_chars.items())[:5]:
    prop_label = prop.split('#')[-1] if '#' in prop else prop.split('/')[-1]
    print(f"  {prop_label}: {', '.join(chars)}")
print()

print("="*60)
print("LLM-GENERATED SUMMARY")
print("="*60)
print(sense.summary)
print()

# Verify structure
assert 'ont' in sense
assert 'stats' in sense
assert 'hier' in sense
assert 'summary' in sense
assert len(sense.stats) > 0
print("✓ All structure checks passed")
