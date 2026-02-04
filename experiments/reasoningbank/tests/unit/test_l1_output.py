"""Check what L1 schema layer actually produces."""

import sys
sys.path.insert(0, '/Users/cvardema/dev/git/LA3D/rlm')

from rdflib import Graph
from experiments.reasoningbank.prototype.packers import l1_schema

# Load PROV ontology
g = Graph().parse('/Users/cvardema/dev/git/LA3D/rlm/ontology/prov.ttl')

# Generate L1 schema constraints
schema_constraints = l1_schema.pack(g, budget=1000)

print("=" * 70)
print("REASONINGBANK L1 SCHEMA CONSTRAINTS (Current)")
print("=" * 70)
print(schema_constraints)
print()
print("=" * 70)
print(f"Total length: {len(schema_constraints)} characters")
print("=" * 70)
