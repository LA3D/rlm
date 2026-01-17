#!/usr/bin/env python3
"""Simple test: RLM using memory operations.

This is the minimal test to verify RLM can use dataset memory.
Requires ANTHROPIC_API_KEY environment variable.

Usage:
    python test_rlm_memory_simple.py
"""

from rlm.core import rlm_run
from rlm.dataset import setup_dataset_context


def main():
    print("="*70)
    print(" Testing RLM with Dataset Memory")
    print("="*70)

    # Setup namespace with dataset memory
    ns = {}
    setup_dataset_context(ns)
    print(f"\n✓ Dataset created (session: {ns['ds_meta'].session_id})")

    # Define context that explains memory operations
    context = """
IMPORTANT: You must use ```repl code blocks to execute Python.

Available memory operations:
- mem_add(subject, predicate, object, source='agent', reason='...')
- mem_query(sparql_query, limit=100)

Example:
```repl
mem_add('http://ex.org/alice', 'http://ex.org/age', '30')
results = mem_query('SELECT ?s ?p ?o WHERE { ?s ?p ?o }')
print(results)
```
"""

    # Simple task - explicit about using REPL
    query = """
Write ```repl code to:
1. Call mem_add('http://example.org/alice', 'http://example.org/age', '30')
2. Call mem_add('http://example.org/bob', 'http://example.org/age', '25')
3. Call mem_query to find everyone with age property
4. Print the results and tell me what you found
"""

    print(f"\nQuery: {query}")
    print("\n" + "-"*70)
    print("Running RLM (calling Claude API)...")
    print("-"*70)

    # Run RLM
    answer, iterations, ns = rlm_run(
        query=query,
        context=context,
        ns=ns,
        max_iters=5
    )

    # Show results
    print("\n" + "="*70)
    print(f"ANSWER: {answer}")
    print("="*70)

    # Verify memory was used
    ds_meta = ns['ds_meta']
    print(f"\nMemory Statistics:")
    print(f"  Triples stored: {len(ds_meta.mem)}")
    print(f"  Provenance events: {len(ds_meta.prov)}")
    print(f"  Iterations used: {len(iterations)}")

    # Show memory contents
    print(f"\nMemory Contents ({len(ds_meta.mem)} triples):")
    for s, p, o in ds_meta.mem.triples((None, None, None)):
        print(f"  {s}")
        print(f"    {p} -> {o}")

    # Check if RLM actually used memory operations
    print(f"\nCode Execution Analysis:")
    used_mem_add = False
    used_mem_query = False

    for i, iteration in enumerate(iterations):
        print(f"\n  Iteration {i}:")
        for j, block in enumerate(iteration.code_blocks):
            if 'mem_add' in block.code:
                used_mem_add = True
                print(f"    Block {j}: Used mem_add ✓")
            if 'mem_query' in block.code:
                used_mem_query = True
                print(f"    Block {j}: Used mem_query ✓")

    print(f"\nVerification:")
    if used_mem_add:
        print("  ✓ RLM called mem_add()")
    else:
        print("  ✗ RLM did NOT call mem_add()")

    if used_mem_query:
        print("  ✓ RLM called mem_query()")
    else:
        print("  ✗ RLM did NOT call mem_query()")

    if len(ds_meta.mem) >= 2:
        print("  ✓ Memory has expected facts")
    else:
        print(f"  ✗ Memory only has {len(ds_meta.mem)} triples (expected 2+)")

    if len(ds_meta.prov) > 0:
        print("  ✓ Provenance was recorded")
    else:
        print("  ✗ No provenance recorded")

    # Overall result
    success = (used_mem_add and used_mem_query and
               len(ds_meta.mem) >= 2 and len(ds_meta.prov) > 0)

    print("\n" + "="*70)
    if success:
        print(" ✓ SUCCESS: RLM correctly used dataset memory!")
    else:
        print(" ✗ ISSUE: Some checks failed (see above)")
    print("="*70)

    return success


if __name__ == '__main__':
    import sys
    try:
        success = main()
        sys.exit(0 if success else 1)
    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
