"""Test full layer cake (L0+L1+L2+L3) together."""

import sys
sys.path.insert(0, '/Users/cvardema/dev/git/LA3D/rlm')

from rdflib import Graph
from experiments.reasoningbank.prototype.ctx.builder import Builder, Cfg, Layer
from experiments.reasoningbank.prototype.core.mem import MemStore, Item

print("=" * 70)
print("FULL LAYER CAKE TEST (L0+L1+L2+L3)")
print("=" * 70)

# Load PROV ontology
g = Graph().parse('/Users/cvardema/dev/git/LA3D/rlm/ontology/prov.ttl')

# Create memory store with test items
mem = MemStore()
mem.add(Item(
    id=Item.make_id("Use rdf:type for classes", "Start with type..."),
    title="Use rdf:type for classes",
    desc="Always start with rdf:type to find class instances.",
    content="When searching for entities of a specific class, start your SPARQL query with ?s rdf:type <ClassURI>.",
    src="success",
    tags=["sparql", "type", "class"]
))
mem.add(Item(
    id=Item.make_id("Check properties first", "Use g_props..."),
    title="Check properties first",
    desc="Use g_props() to see available properties before querying.",
    content="Before writing complex SPARQL, call g_props() to understand what properties are available in the ontology.",
    src="success",
    tags=["exploration", "properties"]
))
mem.add(Item(
    id=Item.make_id("Avoid unbounded queries", "Don't use SELECT *..."),
    title="Avoid unbounded queries",
    desc="SELECT * can return too much data.",
    content="Never use SELECT * without a LIMIT clause. Always specify which variables you need.",
    src="failure",
    tags=["sparql", "performance"]
))

# Example guide text (like from E3 materialization)
guide_text = """# PROV Ontology Guide

## Overview
The W3C PROV ontology defines provenance information. Core classes: Entity, Activity, Agent.

## Key Properties
- wasGeneratedBy: Entity -> Activity
- used: Activity -> Entity
- wasAttributedTo: Entity -> Agent

## Common Patterns
1. Find entities by type: SELECT ?e WHERE { ?e rdf:type prov:Entity }
2. Follow provenance: SELECT * WHERE { ?e prov:wasGeneratedBy ?a . ?a prov:used ?input }
"""

# Configure full layer cake
cfg = Cfg(
    l0=Layer(on=True, budget=600),
    l1=Layer(on=True, budget=1000),
    l2=Layer(on=True, budget=2000),
    l3=Layer(on=True, budget=1000),
    guide_text=guide_text
)

# Build context
builder = Builder(cfg)
task = "How do I query for class instances using SPARQL?"  # Query that matches our memory items
ctx = builder.build(g, task, mem)

print("\nTask:", task)
print()
print("Generated Context (L0+L1+L2+L3):")
print("-" * 70)
print(ctx)
print()
print("-" * 70)
print(f"Total context length: {len(ctx)} chars")
print()

# Verify structure
print("=" * 70)
print("LAYER PRESENCE CHECKS")
print("=" * 70)

checks = {
    'L0 - Ont-Sense': any(marker in ctx for marker in ['**Size**', '**W3C PROV', '**Namespaces**']),
    'L1 - Schema Constraints': '**Schema Constraints**' in ctx,
    'L1 - Anti-patterns': '**Anti-patterns**' in ctx,
    'L1 - Disjoint': '**Disjoint**' in ctx or 'disjoint' in ctx.lower(),
    'L1 - Domain/Range': '**Domain/Range**' in ctx or '→' in ctx,
    'L2 - Procedural Memory': any(marker in ctx for marker in ['**Strategies**', '**Guardrails**', '**Relevant Procedures**']),
    'L2 - Success strategies': '**Strategies**' in ctx and 'Use rdf:type for classes' in ctx,
    'L2 - Failure guardrails': '**Guardrails**' in ctx and 'Avoid unbounded queries' in ctx,
    'L3 - Guide': '# PROV Ontology Guide' in ctx or 'wasGeneratedBy' in ctx,
}

for check, passed in checks.items():
    status = "✓" if passed else "✗"
    print(f"{status} {check}")

# Budget check
print("\n" + "=" * 70)
print("BUDGET ANALYSIS")
print("=" * 70)

total_budget = cfg.l0.budget + cfg.l1.budget + cfg.l2.budget + cfg.l3.budget
budget_usage = len(ctx) / total_budget * 100

print(f"L0 budget: {cfg.l0.budget} chars")
print(f"L1 budget: {cfg.l1.budget} chars")
print(f"L2 budget: {cfg.l2.budget} chars")
print(f"L3 budget: {cfg.l3.budget} chars")
print(f"Total budget: {total_budget} chars")
print(f"Actual context: {len(ctx)} chars ({budget_usage:.1f}%)")

budget_ok = len(ctx) <= total_budget
print(f"\n{'✓' if budget_ok else '✗'} Context within total budget")

# Rough layer size estimation
print("\n" + "=" * 70)
print("LAYER SIZE ESTIMATES")
print("=" * 70)

# Find approximate boundaries
l0_end = ctx.find('**Schema Constraints**') if '**Schema Constraints**' in ctx else len(ctx)
l1_end = ctx.find('**Strategies**') if '**Strategies**' in ctx else (ctx.find('**Relevant Procedures**') if '**Relevant Procedures**' in ctx else l0_end)
l2_end = ctx.find('# PROV Ontology Guide') if '# PROV Ontology Guide' in ctx else l1_end

l0_size = l0_end
l1_size = l1_end - l0_end if l1_end > l0_end else 0
l2_size = l2_end - l1_end if l2_end > l1_end else 0
l3_size = len(ctx) - l2_end if l2_end < len(ctx) else 0

print(f"L0 (Ont-Sense):     ~{l0_size:4d} chars ({l0_size/cfg.l0.budget*100:5.1f}% of budget)")
print(f"L1 (Constraints):   ~{l1_size:4d} chars ({l1_size/cfg.l1.budget*100:5.1f}% of budget)")
print(f"L2 (Memories):      ~{l2_size:4d} chars ({l2_size/cfg.l2.budget*100:5.1f}% of budget)")
print(f"L3 (Guide):         ~{l3_size:4d} chars ({l3_size/cfg.l3.budget*100:5.1f}% of budget)")

# Summary
print("\n" + "=" * 70)
print("SUMMARY")
print("=" * 70)

all_passed = all(checks.values()) and budget_ok

if all_passed:
    print("✓ FULL LAYER CAKE WORKS CORRECTLY")
    print()
    print("All layers present:")
    print("  • L0: Ontology sense card with metadata")
    print("  • L1: Schema constraints with anti-patterns")
    print("  • L2: Procedural memory with success/failure separation")
    print("  • L3: Compressed guide summary")
    print()
    print("Context is ready for RLM execution!")
else:
    print("✗ SOME CHECKS FAILED - Review layer integration")

print("=" * 70)
