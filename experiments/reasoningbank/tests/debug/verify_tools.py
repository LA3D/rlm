"""Verify how dspy.RLM handles tool descriptions and docstrings.

Minimal experiment to understand tool discovery mechanism.
"""

import sys
sys.path.insert(0, '/Users/cvardema/dev/git/LA3D/rlm')

import os
import dspy

# Configure DSPy
if not os.environ.get('ANTHROPIC_API_KEY'):
    raise ValueError("Set ANTHROPIC_API_KEY environment variable")

lm = dspy.LM('anthropic/claude-sonnet-4-5-20250929', api_key=os.environ['ANTHROPIC_API_KEY'])
dspy.configure(lm=lm)

# Test 1: Tool with proper docstring and type hints
def get_number(n: int) -> int:
    """Get a specific number.

    Args:
        n: The number to return

    Returns:
        The same number that was provided
    """
    print(f"  [TOOL CALLED] get_number({n})")
    return n

# Test 2: Lambda with no docstring (like our current implementation)
bare_lambda = lambda *args, **kwargs: "lambda result"

# Test 3: Lambda with attempted docstring attachment
lambda_with_doc = lambda *args, **kwargs: "lambda with doc"
lambda_with_doc.__doc__ = "Lambda function with attached docstring."

print("=" * 70)
print("TOOL VERIFICATION EXPERIMENT")
print("=" * 70)

print("\nTest 1: Proper function with docstring")
print(f"  Name: {get_number.__name__}")
print(f"  Doc: {get_number.__doc__}")
print(f"  Annotations: {get_number.__annotations__}")

print("\nTest 2: Bare lambda")
print(f"  Name: {bare_lambda.__name__}")
print(f"  Doc: {bare_lambda.__doc__}")
print(f"  Annotations: {bare_lambda.__annotations__}")

print("\nTest 3: Lambda with attached doc")
print(f"  Name: {lambda_with_doc.__name__}")
print(f"  Doc: {lambda_with_doc.__doc__}")
print(f"  Annotations: {lambda_with_doc.__annotations__}")

print("\n" + "=" * 70)
print("Running RLM with proper tool")
print("=" * 70)

rlm_proper = dspy.RLM(
    "question -> answer",
    max_iterations=3,
    max_llm_calls=5,
    tools={'get_number': get_number}
)

try:
    result = rlm_proper(question="Use the get_number tool to get the number 42")
    print(f"\nResult: {result}")
except Exception as e:
    print(f"\nError: {e}")

print("\n" + "=" * 70)
print("Running RLM with bare lambda")
print("=" * 70)

rlm_lambda = dspy.RLM(
    "question -> answer",
    max_iterations=3,
    max_llm_calls=5,
    tools={'bare_lambda': bare_lambda}
)

try:
    result = rlm_lambda(question="Use the bare_lambda tool")
    print(f"\nResult: {result}")
except Exception as e:
    print(f"\nError: {e}")

print("\n" + "=" * 70)
print("Running RLM with lambda + doc")
print("=" * 70)

rlm_lambda_doc = dspy.RLM(
    "question -> answer",
    max_iterations=3,
    max_llm_calls=5,
    tools={'lambda_with_doc': lambda_with_doc}
)

try:
    result = rlm_lambda_doc(question="Use the lambda_with_doc tool")
    print(f"\nResult: {result}")
except Exception as e:
    print(f"\nError: {e}")

print("\n" + "=" * 70)
print("VERIFICATION COMPLETE")
print("=" * 70)
