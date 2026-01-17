"""Debug progressive disclosure test to see where it's getting stuck."""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from rlm.core import rlm_run
from rlm.ontology import setup_ontology_context

ns = {}
setup_ontology_context('ontology/prov.ttl', ns, name='prov')

# Start with minimal context - just stats
context = f"""PROV Ontology: {len(ns['prov_meta'].classes)} classes, {len(ns['prov_meta'].properties)} properties
Available tools: search_by_label, describe_entity, graph_stats"""

query = """Find all classes related to 'influence' in the PROV ontology
and explain their relationships."""

answer, iterations, ns = rlm_run(
    query,
    context,
    ns=ns,
    max_iters=5
)

print(f"Query: {query}")
print(f"Final Answer: {answer}")
print(f"Total Iterations: {len(iterations)}")
print()

for i, it in enumerate(iterations):
    print(f"{'='*70}")
    print(f"ITERATION {i}")
    print(f"{'='*70}")

    print(f"\n--- USER PROMPT (first 200 chars) ---")
    print(it.prompt[:200] if isinstance(it.prompt, str) else str(it.prompt)[:200])

    print(f"\n--- RESPONSE (first 500 chars) ---")
    print(it.response[:500])

    print(f"\n--- CODE BLOCKS ({len(it.code_blocks)}) ---")
    for j, cb in enumerate(it.code_blocks):
        print(f"\nBlock {j}:")
        print(f"Code:\n{cb.code}")
        if cb.result:
            print(f"\nStdout: {cb.result.stdout[:300] if cb.result.stdout else 'None'}")
            print(f"Stderr: {cb.result.stderr[:200] if cb.result.stderr else 'None'}")

    print(f"\n--- FINAL ANSWER ---")
    print(f"{it.final_answer}")
    print()
