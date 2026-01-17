"""Minimal test replicating the exact progressive disclosure scenario."""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from rlm.core import rlm_run
from rlm.ontology import setup_ontology_context

print("="*80)
print("MINIMAL PROGRESSIVE DISCLOSURE TEST")
print("="*80)
print()

ns = {}
setup_ontology_context('ontology/prov.ttl', ns, name='prov')

# Exact same context as the failing test
context = f"""PROV Ontology: {len(ns['prov_meta'].classes)} classes, {len(ns['prov_meta'].properties)} properties
Available tools: search_by_label, describe_entity, graph_stats"""

# Exact same query
query = """Find all classes related to 'influence' in the PROV ontology
and explain their relationships."""

print(f"Context: {context}")
print(f"Query: {query}")
print()

answer, iterations, ns = rlm_run(
    query,
    context,
    ns=ns,
    max_iters=5
)

print("="*80)
print("RESULTS")
print("="*80)
print(f"Total iterations: {len(iterations)}")
print(f"Converged: {answer is not None}")
if answer:
    print(f"Answer (first 200 chars): {answer[:200]}...")
else:
    print("Answer: None (did not converge)")
print()

# Check the last iteration
if len(iterations) > 0:
    last_iter = iterations[-1]
    print("="*80)
    print(f"LAST ITERATION ({len(iterations)-1})")
    print("="*80)
    print(f"Response (last 500 chars):")
    print(last_iter.response[-500:])
    print()

    print(f"Final answer extracted: {last_iter.final_answer}")
    print()

# Check namespace state
print("="*80)
print("NAMESPACE STATE")
print("="*80)
relevant_vars = [k for k in ns.keys() if not k.startswith('_') and k not in
                 ['context', 'llm_query', 'llm_query_batched', 'prov', 'prov_meta',
                  'search_by_label', 'describe_entity', 'graph_stats']]
print(f"Variables created: {relevant_vars}")
for var in sorted(relevant_vars):
    val = ns[var]
    if isinstance(val, str) and len(val) > 100:
        print(f"  {var}: (str, {len(val)} chars)")
    elif isinstance(val, str):
        print(f"  {var}: '{val}'")
    elif isinstance(val, (list, dict)):
        print(f"  {var}: {type(val).__name__} with {len(val)} items")
    else:
        print(f"  {var}: {type(val).__name__}")
print()

# Detailed analysis if it didn't converge
if answer is None:
    print("="*80)
    print("FAILURE ANALYSIS")
    print("="*80)

    # Check each iteration for FINAL_VAR attempts
    for i, it in enumerate(iterations):
        if 'FINAL_VAR' in it.response or 'FINAL(' in it.response:
            print(f"\nIteration {i}: Found FINAL pattern in response")
            # Extract the FINAL line
            for line in it.response.split('\n'):
                if 'FINAL' in line:
                    print(f"  Line: {line.strip()}")

                    # Extract variable name if FINAL_VAR
                    if 'FINAL_VAR' in line:
                        import re
                        match = re.search(r'FINAL_VAR\((.*?)\)', line)
                        if match:
                            var_name = match.group(1).strip().strip('"').strip("'")
                            if var_name in ns:
                                print(f"  ✓ Variable '{var_name}' EXISTS in namespace")
                            else:
                                print(f"  ✗ Variable '{var_name}' NOT FOUND in namespace")
                                print(f"    Available: {[v for v in relevant_vars if 'final' in v.lower() or 'answer' in v.lower()]}")

print()
print("="*80)
if answer:
    print("✓ TEST PASSED")
else:
    print("✗ TEST FAILED - Did not converge in 5 iterations")
print("="*80)
