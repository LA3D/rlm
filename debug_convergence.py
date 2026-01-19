"""Debug script to understand non-convergence in quick_e2e test."""

from rlm.core import rlm_run
from rlm.ontology import setup_ontology_context

# Replicate the exact test scenario
ns = {}
setup_ontology_context('ontology/prov.ttl', ns, name='prov')

query = "What is prov:Activity?"
context = ns['prov_meta'].summary()

print("="*80)
print(f"QUERY: {query}")
print(f"CONTEXT LENGTH: {len(context)} chars")
print(f"MAX_ITERS: 3")
print("="*80)
print()

answer, iterations, ns = rlm_run(
    query,
    context,
    ns=ns,
    max_iters=3,
    verbose=False
)

print(f"FINAL ANSWER: {answer}")
print(f"TOTAL ITERATIONS: {len(iterations)}")
print()

for i, iteration in enumerate(iterations):
    print("="*80)
    print(f"ITERATION {i+1}")
    print("="*80)

    print(f"\nRESPONSE (first 500 chars):")
    print(iteration.response[:500])
    print("...")

    print(f"\nCODE BLOCKS EXECUTED: {len(iteration.code_blocks)}")
    for j, cb in enumerate(iteration.code_blocks):
        print(f"\n  Block {j+1}:")
        print(f"  Code: {cb.code[:200]}")
        if cb.result and cb.result.stdout:
            print(f"  Stdout: {cb.result.stdout[:300]}")

    print(f"\nFINAL ANSWER IN THIS ITERATION: {iteration.final_answer}")
    print()

print("="*80)
print("ANALYSIS:")
print("="*80)
print(f"Converged: {not answer.startswith('[Max iterations]')}")
print(f"Final answer was: {answer[:200]}")

# Check if any iteration had FINAL in response
for i, it in enumerate(iterations):
    if 'FINAL' in it.response:
        print(f"\nIteration {i+1} mentioned FINAL in response but didn't trigger convergence")
        print(f"Response around FINAL: {it.response[it.response.find('FINAL')-50:it.response.find('FINAL')+200]}")
