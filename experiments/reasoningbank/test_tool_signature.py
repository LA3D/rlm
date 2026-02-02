"""Test DSPy RLM tool calling convention."""

import sys
sys.path.insert(0, '/Users/cvardema/dev/git/LA3D/rlm')

import os
import dspy

if not os.environ.get('ANTHROPIC_API_KEY'):
    raise ValueError("Set ANTHROPIC_API_KEY environment variable")

lm = dspy.LM('anthropic/claude-sonnet-4-5-20250929', api_key=os.environ['ANTHROPIC_API_KEY'])
dspy.configure(lm=lm)

# Test three different signatures
def inspect_signature1(*args, **kwargs):
    """Signature 1: *args, **kwargs"""
    return f"S1: args={args}, kwargs={kwargs}"

def inspect_signature2(args, kwargs):
    """Signature 2: args, kwargs (positional)"""
    return f"S2: args={args}, kwargs={kwargs}"

def inspect_signature3(args, **kwargs):
    """Signature 3: args (positional), **kwargs"""
    return f"S3: args={args}, kwargs={kwargs}"

print("Testing tool signatures with DSPy RLM...")
print("=" * 70)

# Test signature 1
print("\nTest 1: lambda *args, **kwargs")
rlm1 = dspy.RLM(
    "instruction -> result",
    max_iterations=2,
    max_llm_calls=3,
    tools={'inspect': inspect_signature1}
)

try:
    res1 = rlm1(instruction="Call inspect with argument 'test'")
    print(f"Success: {res1.result}")
except Exception as e:
    print(f"Error: {e}")

# Test signature 2
print("\nTest 2: lambda args, kwargs")
rlm2 = dspy.RLM(
    "instruction -> result",
    max_iterations=2,
    max_llm_calls=3,
    tools={'inspect': inspect_signature2}
)

try:
    res2 = rlm2(instruction="Call inspect with argument 'test'")
    print(f"Success: {res2.result}")
except Exception as e:
    print(f"Error: {e}")

# Test signature 3
print("\nTest 3: lambda args, **kwargs")
rlm3 = dspy.RLM(
    "instruction -> result",
    max_iterations=2,
    max_llm_calls=3,
    tools={'inspect': inspect_signature3}
)

try:
    res3 = rlm3(instruction="Call inspect with argument 'test'")
    print(f"Success: {res3.result}")
except Exception as e:
    print(f"Error: {e}")

print("\n" + "=" * 70)
print("CONCLUSION:")
print("The signature that works with DSPy RLM is the one that succeeds above.")
