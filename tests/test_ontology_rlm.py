"""Test RLM integration with ontology module."""

from rlm.core import rlm_run
from rlm.ontology import setup_ontology_context

# Setup namespace with PROV ontology
ns = {}
setup_msg = setup_ontology_context('ontology/prov.ttl', ns, name='prov')
print(f"Setup: {setup_msg}")
print()

# Get context summary (not the full graph)
context = ns['prov_meta'].summary()
print(f"Context being passed to RLM:\n{context}")
print()

# Ask a question about the ontology
query = "What is the Activity class in the PROV ontology? Use search_by_label and describe_entity to explore."

print(f"Query: {query}")
print()

# Run RLM
answer, iterations, ns = rlm_run(
    query,
    context,
    ns=ns,
    max_iters=10
)

print(f"Answer: {answer}")
print(f"Iterations: {len(iterations)}")
print()

# Show what the model explored
for i, iteration in enumerate(iterations):
    print(f"--- Iteration {i} ---")
    if iteration.code_blocks:
        print(f"Code blocks executed: {len(iteration.code_blocks)}")
        for j, cb in enumerate(iteration.code_blocks):
            print(f"  Block {j}:")
            print(f"    Code: {cb.code[:100]}...")
            if cb.result.stdout:
                print(f"    Stdout: {cb.result.stdout[:200]}...")
            if cb.result.stderr:
                print(f"    Stderr: {cb.result.stderr[:200]}...")
    if iteration.final_answer:
        print(f"Final answer: {iteration.final_answer[:200]}...")
    print()
