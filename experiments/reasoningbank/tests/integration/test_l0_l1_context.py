"""Test L0+L1 layers together in full context."""

import sys
sys.path.insert(0, '/Users/cvardema/dev/git/LA3D/rlm')

from rdflib import Graph
from experiments.reasoningbank.prototype.ctx.builder import Builder, Cfg, Layer

print("=" * 70)
print("L0+L1 CONTEXT TEST")
print("=" * 70)

# Load PROV ontology
g = Graph().parse('/Users/cvardema/dev/git/LA3D/rlm/ontology/prov.ttl')

# Configure with L0+L1 enabled
cfg = Cfg(
    l0=Layer(on=True, budget=600),
    l1=Layer(on=True, budget=1000),
    l2=Layer(on=False, budget=0),
    l3=Layer(on=False, budget=0),
)

# Build context
builder = Builder(cfg)
task = "What is Activity?"
ctx = builder.build(g, task, mem=None)

print("\nTask: What is Activity?")
print()
print("Generated Context (L0+L1):")
print("-" * 70)
print(ctx)
print()
print("-" * 70)
print(f"Total context length: {len(ctx)} chars")
print()

# Verify structure
print("=" * 70)
print("VERIFICATION CHECKS")
print("=" * 70)

checks = {
    'Has L0 content': '**Size**' in ctx or '**W3C PROV' in ctx,
    'Has L1 content': '**Schema Constraints**' in ctx or '**Anti-patterns**' in ctx,
    'Has metadata': '**Imports**' in ctx or '**Namespaces**' in ctx,
    'Has anti-patterns': '**Anti-patterns**' in ctx,
    'Has disjoint info': '**Disjoint**' in ctx or 'disjoint' in ctx.lower(),
    'Has domain/range': '**Domain/Range**' in ctx or '→' in ctx,
    'Reasonable length': 1000 <= len(ctx) <= 2000,  # L0(~500) + L1(~900) = ~1400
    'Well formatted': ctx.count('**') >= 4,  # Multiple sections
}

for check, passed in checks.items():
    status = "✓" if passed else "✗"
    print(f"{status} {check}")

all_passed = all(checks.values())

print()
print("=" * 70)
if all_passed:
    print("✓ L0+L1 CONTEXT LOOKS GOOD - Ready for RLM!")
    print()
    print("Context provides:")
    print("  • Metadata (size, imports, namespaces, conventions)")
    print("  • Constraints (anti-patterns, disjoint, domain/range)")
    print("  • Actionable guidance for query construction")
else:
    print("⚠ SOME CHECKS FAILED - Review context generation")

print("=" * 70)

# Show breakdown
print()
print("Context Breakdown:")
print(f"  L0 (metadata):     ~{ctx.find('**Schema Constraints**') if '**Schema Constraints**' in ctx else len(ctx)} chars")
print(f"  L1 (constraints):  ~{len(ctx) - ctx.find('**Schema Constraints**') if '**Schema Constraints**' in ctx else 0} chars")
print(f"  Total:             {len(ctx)} chars")
print(f"  Budget used:       {len(ctx)}/1600 ({100*len(ctx)//1600}%)")
