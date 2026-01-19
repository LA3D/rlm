"""Test with increased max_iters to see if convergence improves."""

from rlm.core import rlm_run
from rlm.ontology import setup_ontology_context

ns = {}
setup_ontology_context('ontology/prov.ttl', ns, name='prov')

query = "What is prov:Activity?"
context = ns['prov_meta'].summary()

print("="*80)
print(f"TESTING WITH max_iters=5 (instead of 3)")
print("="*80)
print()

answer, iterations, ns = rlm_run(
    query,
    context,
    ns=ns,
    max_iters=5,  # Increased from 3
    verbose=False
)

print(f"CONVERGED: {not answer.startswith('[Max iterations]')}")
print(f"TOTAL ITERATIONS USED: {len(iterations)}")
print(f"\nFINAL ANSWER:\n{answer[:500]}")
print()

# Show which iteration had FINAL
for i, it in enumerate(iterations):
    if it.final_answer:
        print(f"✓ Iteration {i+1} returned FINAL answer")
        break
else:
    print("✗ No iteration returned FINAL answer")
