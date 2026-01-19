"""Check if tools are working correctly and LLM is calling them properly."""

from rlm.ontology import setup_ontology_context

# Setup
ns = {}
setup_ontology_context('ontology/prov.ttl', ns, name='prov')

print("="*80)
print("AVAILABLE TOOLS IN NAMESPACE:")
print("="*80)
tools = [k for k in ns.keys() if callable(ns[k]) and k.startswith('prov_')]
for tool in tools:
    print(f"  - {tool}")
print()

print("="*80)
print("TESTING TOOL BEHAVIOR - What LLM should get:")
print("="*80)

# Test 1: What the LLM tried in iteration 2
print("\n1. prov_describe_entity('prov:Activity'):")
print("-" * 40)
result1 = ns['prov_describe_entity']('prov:Activity')
print(result1)

# Test 2: Try with full URI
print("\n2. prov_describe_entity('http://www.w3.org/ns/prov#Activity'):")
print("-" * 40)
result2 = ns['prov_describe_entity']('http://www.w3.org/ns/prov#Activity')
print(result2)

# Test 3: Search by label
print("\n3. prov_search_by_label('Activity'):")
print("-" * 40)
result3 = ns['prov_search_by_label']('Activity')
print(result3[:5] if len(result3) > 5 else result3)  # First 5 results

# Test 4: Try without prov: prefix
print("\n4. prov_describe_entity('Activity'):")
print("-" * 40)
result4 = ns['prov_describe_entity']('Activity')
print(result4)

print("\n" + "="*80)
print("ANALYSIS:")
print("="*80)

# Check if describe_entity is working
if result2 and result2.get('comment'):
    print("✓ prov_describe_entity() WORKS with full URI")
else:
    print("✗ prov_describe_entity() returns empty even with full URI")

if result1 == result2:
    print("✓ prov:Activity and full URI return same result")
else:
    print("⚠️  prov:Activity and full URI return DIFFERENT results")
    print(f"   prov:Activity → {result1}")
    print(f"   Full URI → {result2}")

# Check what search_by_label returns
if result3 and len(result3) > 0:
    print(f"✓ prov_search_by_label() returns {len(result3)} results")
    print(f"   First result: {result3[0]}")
else:
    print("✗ prov_search_by_label() returns empty")

print("\n" + "="*80)
print("WHAT THE LLM SHOULD DO:")
print("="*80)

# Recommended sequence
print("\nOption 1 (Direct):")
print("  1. result = prov_describe_entity('http://www.w3.org/ns/prov#Activity')")
print("  2. FINAL(result['comment'])")

print("\nOption 2 (Search then describe):")
print("  1. results = prov_search_by_label('Activity')")
print("  2. uri = results[0][0]  # Get first URI")
print("  3. info = prov_describe_entity(uri)")
print("  4. FINAL(info['comment'])")

print("\nWhat LLM actually did:")
print("  1. ✓ prov_describe_entity('prov:Activity') - CORRECT call")
print("  2. ✗ Got empty result - WHY?")
print("  3. ✓ Tried prov_search_by_label('Activity') - CORRECT fallback")
print("  4. ✗ Ran out of iterations before synthesis")
