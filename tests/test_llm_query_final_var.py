"""Test FINAL_VAR with llm_query() results - replicates progressive disclosure scenario."""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from rlm.core import rlm_run

print("="*80)
print("TEST: Using llm_query() result with FINAL_VAR")
print("="*80)
print()

# Replicate the progressive disclosure scenario more closely
context = """You have a sub-LLM available via llm_query().
Use it to analyze something and return the result."""

query = """Use llm_query to answer 'What is 2+2?' and store the result in a variable called 'math_answer'.
Then return that variable using FINAL_VAR."""

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

# Detailed iteration breakdown
for i, it in enumerate(iterations):
    print(f"{'='*80}")
    print(f"ITERATION {i}")
    print(f"{'='*80}")

    print(f"\nResponse:")
    print(it.response[:500])
    if len(it.response) > 500:
        print("...")

    print(f"\nCode blocks executed: {len(it.code_blocks)}")
    for j, cb in enumerate(it.code_blocks):
        print(f"\n  --- Code Block {j} ---")
        print(f"  Code:")
        print(f"  {cb.code}")
        if cb.result:
            if cb.result.stdout:
                print(f"\n  Stdout:")
                print(f"  {cb.result.stdout[:300]}")
            if cb.result.stderr:
                print(f"\n  Stderr:")
                print(f"  {cb.result.stderr[:300]}")

    print(f"\nFinal answer extracted: {it.final_answer}")
    print()

print("="*80)
print("Final namespace state:")
print("="*80)
relevant_vars = [k for k in ns.keys() if not k.startswith('_') and k not in ['context', 'llm_query', 'llm_query_batched']]
for var in sorted(relevant_vars):
    val = ns[var]
    if isinstance(val, str):
        print(f"  {var}: (str, {len(val)} chars) = '{val[:100]}...'")
    else:
        print(f"  {var}: {type(val).__name__}")
print()

print("="*80)
print("RESULT:")
print("="*80)
if answer:
    print(f"✓ Test PASSED")
    print(f"  Final answer: {answer}")
else:
    print(f"✗ Test FAILED - No answer returned after {len(iterations)} iterations")

    # Debug: check what variables exist
    if 'math_answer' in ns:
        print(f"  Variable 'math_answer' EXISTS in namespace: {ns['math_answer'][:100]}")
        print(f"  This suggests FINAL_VAR lookup failed even though variable exists!")
    else:
        print(f"  Variable 'math_answer' does NOT exist in namespace")
        print(f"  Available variables: {relevant_vars}")
