"""Verify that l0_sense.py replacement works correctly."""

import sys
sys.path.insert(0, '/Users/cvardema/dev/git/LA3D/rlm')

from rdflib import Graph
from experiments.reasoningbank.packers import l0_sense

print("=" * 70)
print("VERIFYING ENHANCED L0_SENSE.PY")
print("=" * 70)

# Test with PROV
g = Graph().parse('/Users/cvardema/dev/git/LA3D/rlm/ontology/prov.ttl')
sense_card = l0_sense.pack(g, budget=600)

print("\nPROV Sense Card:")
print("-" * 70)
print(sense_card)
print()
print(f"Length: {len(sense_card)} chars")
print()

# Verify key features are present
checks = {
    'Has title': '**W3C PROV' in sense_card,
    'Has size stats': '**Size**:' in sense_card,
    'Has imports': '**Imports**:' in sense_card,
    'Has namespaces': '**Namespaces**:' in sense_card,
    'Has label convention': '**Labels**:' in sense_card,
    'Within budget': len(sense_card) <= 600,
}

print("=" * 70)
print("VERIFICATION CHECKS")
print("=" * 70)
for check, passed in checks.items():
    status = "✓" if passed else "✗"
    print(f"{status} {check}")

all_passed = all(checks.values())
print()
print("=" * 70)
if all_passed:
    print("✓ ALL CHECKS PASSED - Enhanced L0 working correctly!")
else:
    print("✗ SOME CHECKS FAILED - Review implementation")
print("=" * 70)
