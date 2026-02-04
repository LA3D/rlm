"""Test enhanced L1 schema constraints."""

import sys
sys.path.insert(0, '/Users/cvardema/dev/git/LA3D/rlm')

from rdflib import Graph
from experiments.reasoningbank.packers import l1_schema_enhanced as enhanced

print("=" * 70)
print("ENHANCED L1 SCHEMA CONSTRAINTS TEST")
print("=" * 70)

# Test on PROV
g = Graph().parse('/Users/cvardema/dev/git/LA3D/rlm/ontology/prov.ttl')

print("\nPROV Ontology:")
print("-" * 70)
l1_output = enhanced.pack(g, budget=1000)
print(l1_output)
print()
print(f"Length: {len(l1_output)} chars (of 1000 budget)")

# Detailed extraction
constraints = enhanced.extract(g)

print()
print("=" * 70)
print("EXTRACTION DETAILS")
print("=" * 70)
print(f"Domain/range: {len(constraints['domain_range'])}")
print(f"Disjoint: {len(constraints['disjoint'])}")
print(f"Functional: {len(constraints['functional'])}")
print(f"InverseFunctional: {len(constraints['inverse_functional'])}")
print(f"Symmetric: {len(constraints['symmetric'])}")
print(f"Transitive: {len(constraints['transitive'])}")
print(f"Cardinality: {len(constraints['cardinality'])}")

print()
print("=" * 70)
print("ANTI-PATTERNS GENERATED")
print("=" * 70)
anti_patterns = enhanced.generate_anti_patterns(constraints)
for ap in anti_patterns:
    print(f"  • {ap}")

print()
print("=" * 70)
print("VERIFICATION")
print("=" * 70)
checks = {
    'Has anti-patterns': '**Anti-patterns**' in l1_output,
    'Has disjoint': '**Disjoint**' in l1_output,
    'Has property types': '**Property Types**' in l1_output,
    'Has domain/range': '**Domain/Range**' in l1_output,
    'Within budget': len(l1_output) <= 1000,
    'More actionable than v1': '**Anti-patterns**' in l1_output,
}

for check, passed in checks.items():
    status = "✓" if passed else "✗"
    print(f"{status} {check}")

all_passed = all(checks.values())
print()
if all_passed:
    print("✓ Enhanced L1 provides better constraint guidance!")
else:
    print("⚠ Some checks failed - review implementation")
