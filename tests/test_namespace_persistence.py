"""Test that variables persist across RLM iterations."""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from rlm.core import rlm_run

print("="*80)
print("TEST: Variable persistence across iterations")
print("="*80)
print()

# Simple test case: Create a variable in iteration 1, use it in iteration 2
context = "This is a simple test context."

query = """Create a variable called 'my_result' with the value 'Success!'
and then return it using FINAL_VAR in a later iteration."""

answer, iterations, ns = rlm_run(
    query,
    context,
    ns={},
    max_iters=10
)

print(f"Query: {query}")
print(f"Answer: {answer}")
print(f"Total iterations: {len(iterations)}")
print()

# Show what happened in each iteration
for i, it in enumerate(iterations):
    print(f"--- Iteration {i} ---")
    print(f"Response (first 200 chars): {it.response[:200]}")
    print(f"Code blocks: {len(it.code_blocks)}")

    if it.code_blocks:
        for j, cb in enumerate(it.code_blocks):
            print(f"  Block {j} code (first 100 chars): {cb.code[:100]}")
            if cb.result and cb.result.stdout:
                print(f"  Block {j} stdout: {cb.result.stdout[:100]}")

    print(f"Final answer in iteration: {it.final_answer}")
    print()

print("="*80)
print("Namespace variables at end:")
print("="*80)
relevant_vars = [k for k in ns.keys() if not k.startswith('_') and k not in ['context', 'llm_query', 'llm_query_batched']]
for var in sorted(relevant_vars):
    val = ns[var]
    if isinstance(val, str):
        print(f"  {var}: '{val[:100]}...' ({len(val)} chars)")
    else:
        print(f"  {var}: {type(val).__name__}")
print()

print("="*80)
print("RESULT:")
print("="*80)
if answer:
    print(f"✓ Test PASSED - Got answer: {answer}")
else:
    print(f"✗ Test FAILED - No answer returned")
    print(f"  This suggests variables aren't being found when FINAL_VAR is called")
