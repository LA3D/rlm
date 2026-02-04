"""Test L2 procedural memory layer correctness."""

import sys
sys.path.insert(0, '/Users/cvardema/dev/git/LA3D/rlm')

from experiments.reasoningbank.prototype.core.mem import MemStore, Item
from experiments.reasoningbank.prototype.packers import l2_mem

print("=" * 70)
print("L2 PROCEDURAL MEMORY TEST")
print("=" * 70)

# Create memory store with test items
mem = MemStore()

# Add success strategies
s1 = Item(
    id=Item.make_id("Use TYPE for class queries", "Always start..."),
    title="Use TYPE for class queries",
    desc="Start with rdf:type to find instances of a class.",
    content="Always start SPARQL queries with ?s rdf:type <Class> to find instances.",
    src="success",
    tags=["sparql", "type", "instances"]
)
s2 = Item(
    id=Item.make_id("Check subclass hierarchy", "When looking..."),
    title="Check subclass hierarchy",
    desc="Use rdfs:subClassOf to understand class relationships.",
    content="When looking for entities, check rdfs:subClassOf hierarchy first.",
    src="success",
    tags=["hierarchy", "subclass"]
)

# Add failure guardrails
f1 = Item(
    id=Item.make_id("Avoid SELECT *", "Never use SELECT *..."),
    title="Avoid SELECT *",
    desc="SELECT * returns too much data and is slow.",
    content="Never use SELECT * in production. Always specify variables.",
    src="failure",
    tags=["sparql", "performance"]
)

# Add seed (general strategy)
g1 = Item(
    id=Item.make_id("Explore before querying", "Before writing..."),
    title="Explore before querying",
    desc="Understand the ontology structure first.",
    content="Before writing complex queries, use g_classes() and g_props() to understand available types and properties.",
    src="seed",
    tags=["exploration", "ontology"]
)

for item in [s1, s2, f1, g1]:
    mem.add(item)

print(f"\nAdded {len(mem.all())} items to memory store")

# Test 1: Polarity filtering in search
print("\n" + "-" * 70)
print("TEST 1: Polarity filtering")
print("-" * 70)

all_hits = mem.search("sparql query class", k=10)
success_hits = mem.search("sparql query class", k=10, polarity='success')
failure_hits = mem.search("sparql query class", k=10, polarity='failure')
seed_hits = mem.search("sparql query class", k=10, polarity='seed')

print(f"All hits: {len(all_hits)}")
print(f"Success hits: {len(success_hits)}")
print(f"Failure hits: {len(failure_hits)}")
print(f"Seed hits: {len(seed_hits)}")

# Verify polarity filtering works
check1 = all(h['src'] == 'success' for h in success_hits)
check2 = all(h['src'] == 'failure' for h in failure_hits)
check3 = all(h['src'] == 'seed' for h in seed_hits)
print(f"\n✓ Success hits all have src='success': {check1}")
print(f"✓ Failure hits all have src='failure': {check2}")
print(f"✓ Seed hits all have src='seed': {check3}")

# Test 2: mem_quote() bounded excerpt
print("\n" + "-" * 70)
print("TEST 2: Bounded excerpt (mem_quote)")
print("-" * 70)

full_content = mem.get([s1.id])[0].content
quote_10 = mem.quote(s1.id, max_chars=10)
quote_50 = mem.quote(s1.id, max_chars=50)

print(f"Full content: {len(full_content)} chars")
print(f"Quote(10): '{quote_10}'")
print(f"Quote(50): '{quote_50}'")

check4 = len(quote_10) <= 13  # 10 + "..."
check5 = len(quote_50) <= 53  # 50 + "..."
print(f"\n✓ Quote(10) is bounded: {check4}")
print(f"✓ Quote(50) is bounded: {check5}")

# Test 3: L2 packer separates success/failure
print("\n" + "-" * 70)
print("TEST 3: L2 packer separates success/failure")
print("-" * 70)

items = mem.get([s1.id, s2.id, f1.id, g1.id], max_n=4)
packed = l2_mem.pack(items, budget=2000)

print("Packed output:")
print(packed[:500])
print(f"\nTotal length: {len(packed)} chars")

check6 = '**Strategies** (what works):' in packed
check7 = '**Guardrails** (what to avoid):' in packed
check8 = '**General Strategies**:' in packed
print(f"\n✓ Has Strategies section: {check6}")
print(f"✓ Has Guardrails section: {check7}")
print(f"✓ Has General Strategies section: {check8}")

# Test 4: pack_separate() alternative
print("\n" + "-" * 70)
print("TEST 4: pack_separate() for explicit k_success + k_failure")
print("-" * 70)

success_items = [s1, s2]
failure_items = [f1]
packed_sep = l2_mem.pack_separate(success_items, failure_items, budget=1000)

print("Packed (separate):")
print(packed_sep[:400])
print(f"\nTotal length: {len(packed_sep)} chars")

# Summary
print("\n" + "=" * 70)
print("VERIFICATION SUMMARY")
print("=" * 70)

checks = {
    'Polarity filter (success)': check1,
    'Polarity filter (failure)': check2,
    'Polarity filter (seed)': check3,
    'Quote bounded (10)': check4,
    'Quote bounded (50)': check5,
    'Packer has Strategies': check6,
    'Packer has Guardrails': check7,
    'Packer has General': check8,
}

for name, passed in checks.items():
    status = "✓" if passed else "✗"
    print(f"{status} {name}")

if all(checks.values()):
    print("\n✓ L2 PROCEDURAL MEMORY WORKS CORRECTLY")
else:
    print("\n✗ SOME CHECKS FAILED")

print("=" * 70)
