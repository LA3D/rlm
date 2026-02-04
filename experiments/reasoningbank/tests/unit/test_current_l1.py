"""Test current L1 output to understand baseline."""

import sys
sys.path.insert(0, '/Users/cvardema/dev/git/LA3D/rlm')

from rdflib import Graph
from experiments.reasoningbank.prototype.packers import l1_schema

print("=" * 70)
print("CURRENT L1 SCHEMA CONSTRAINTS")
print("=" * 70)

# Test on PROV
g = Graph().parse('/Users/cvardema/dev/git/LA3D/rlm/ontology/prov.ttl')
l1_output = l1_schema.pack(g, budget=1000)

print("\nPROV Ontology:")
print("-" * 70)
print(l1_output)
print()
print(f"Length: {len(l1_output)} chars (of 1000 budget)")

# Check what we're getting
constraints = l1_schema.extract(g)
print()
print("=" * 70)
print("EXTRACTION ANALYSIS")
print("=" * 70)
print(f"Domain/range constraints: {len(constraints['domain_range'])}")
print(f"Disjoint pairs: {len(constraints['disjoint'])}")
print(f"Functional properties: {len(constraints['functional'])}")

print()
print("Sample domain/range (first 5):")
for p, d, r in constraints['domain_range'][:5]:
    print(f"  {p}: {d} → {r}")

print()
print("Disjoint classes:")
for a, b in constraints['disjoint'][:5]:
    print(f"  {a} ⊥ {b}")

print()
print("=" * 70)
print("WHAT'S MISSING FOR QUERY CONSTRUCTION?")
print("=" * 70)
print("""
Current L1 provides:
✓ Domain/range (property signatures)
✓ Disjoint classes
✓ Functional properties

Should add:
⚠ Anti-patterns (common mistakes to avoid)
  - "Don't mix Activity and Entity in same query (disjoint)"
  - "Always specify rdf:type for class queries"

⚠ Cardinality constraints
  - "Activity requires exactly 1 startedAtTime (if present)"
  - "Entity can have 0 or more wasAttributedTo"

⚠ Property characteristics
  - Symmetric, Transitive, InverseFunctional
  - Helps with query optimization

⚠ Required vs Optional patterns
  - Which properties are commonly used together?
  - Which are mutually exclusive?
""")
