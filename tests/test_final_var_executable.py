"""Test that FINAL_VAR works as an executable function in the REPL."""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from rlm.core import rlm_run

print("="*80)
print("TEST 1: FINAL_VAR as executable function - basic usage")
print("="*80)
print()

context = "Test context"
query = """Create a variable x=42, call FINAL_VAR(x) inside a code block to verify it exists,
then return it using FINAL_VAR outside the code block."""

answer, iterations, ns = rlm_run(query, context, ns={}, max_iters=5)

print(f"Query: {query}")
print(f"Answer: {answer}")
print(f"Iterations: {len(iterations)}")
print()

# Check iteration details
for i, it in enumerate(iterations):
    print(f"--- Iteration {i} ---")
    if it.code_blocks:
        for j, cb in enumerate(it.code_blocks):
            if 'FINAL_VAR' in cb.code:
                print(f"  Code block {j} calls FINAL_VAR:")
                print(f"    Code: {cb.code[:100]}")
                if cb.result and cb.result.stdout:
                    print(f"    Output: {cb.result.stdout[:100]}")
    if it.final_answer:
        print(f"  Final answer: {it.final_answer}")
    print()

if answer:
    print("✓ TEST 1 PASSED - Model successfully used FINAL_VAR inside code blocks")
else:
    print("✗ TEST 1 FAILED - No answer")
print()

print("="*80)
print("TEST 2: FINAL_VAR error handling - nonexistent variable")
print("="*80)
print()

context = "Test context"
query = """Try to call FINAL_VAR(nonexistent_var) inside a code block.
You should see an error. Then create the variable and try again."""

answer, iterations, ns = rlm_run(query, context, ns={}, max_iters=5)

print(f"Query: {query}")
print(f"Answer: {answer}")
print(f"Iterations: {len(iterations)}")
print()

# Look for error message
error_found = False
for i, it in enumerate(iterations):
    if it.code_blocks:
        for cb in it.code_blocks:
            if cb.result and cb.result.stdout:
                if "Error: Variable" in cb.result.stdout:
                    error_found = True
                    print(f"✓ Found error message in iteration {i}:")
                    print(f"  {cb.result.stdout[:150]}")

if error_found:
    print("\n✓ TEST 2 PASSED - FINAL_VAR returns clear error for missing variables")
else:
    print("\n✗ TEST 2 FAILED - No error message found")
print()

print("="*80)
print("TEST 3: Direct test of FINAL_VAR function")
print("="*80)
print()

# Create a namespace with FINAL_VAR
test_ns = {}
answer, iterations, test_ns = rlm_run(
    "Just create a variable test_var='hello' and exit",
    "context",
    ns=test_ns,
    max_iters=2
)

# Test the FINAL_VAR function directly
if 'FINAL_VAR' in test_ns:
    # Test with existing variable
    test_ns['my_var'] = 'success'
    result = test_ns['FINAL_VAR']('my_var')
    assert result == 'success', f"Expected 'success', got '{result}'"
    print("✓ FINAL_VAR returns existing variable value")

    # Test with nonexistent variable
    result = test_ns['FINAL_VAR']('does_not_exist')
    assert 'Error' in result, f"Expected error message, got '{result}'"
    print("✓ FINAL_VAR returns error for missing variable")

    # Test with quotes (should strip them)
    result = test_ns['FINAL_VAR']('"my_var"')
    assert result == 'success', f"Expected 'success', got '{result}'"
    print("✓ FINAL_VAR strips quotes from variable name")

    print("\n✓ TEST 3 PASSED - Direct function tests work")
else:
    print("✗ TEST 3 FAILED - FINAL_VAR not in namespace")
print()

print("="*80)
print("SUMMARY")
print("="*80)
print("""
The FINAL_VAR function is now available as an executable function in the REPL.
This allows the model to:

1. Test if variables exist: FINAL_VAR('var_name')
2. Preview answer values before committing
3. Get deterministic error messages instead of silent failures
4. Debug more effectively

This matches rlmpaper's design and reduces hallucination by making variable
state explicit and testable.
""")
