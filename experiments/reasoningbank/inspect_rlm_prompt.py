"""Inspect what prompt dspy.RLM actually generates for tool-aware tasks."""

import sys
sys.path.insert(0, '/Users/cvardema/dev/git/LA3D/rlm')

import os
import dspy

# Configure DSPy with trace logging
if not os.environ.get('ANTHROPIC_API_KEY'):
    raise ValueError("Set ANTHROPIC_API_KEY environment variable")

lm = dspy.LM('anthropic/claude-sonnet-4-20250514', api_key=os.environ['ANTHROPIC_API_KEY'])
dspy.configure(lm=lm)

# Define a simple tool with good documentation
def get_stats(ref_key: str) -> dict:
    """Get statistics about a graph reference.

    Args:
        ref_key: The reference key for the graph

    Returns:
        Dictionary with stats like triple count, classes, properties
    """
    return {'triples': 100, 'classes': 10, 'properties': 20}

# Create RLM instance
rlm = dspy.RLM(
    "context, question -> answer",
    max_iterations=2,
    max_llm_calls=3,
    tools={'get_stats': get_stats}
)

# Try to intercept the prompt by enabling verbose mode
print("=" * 70)
print("Inspecting RLM prompt generation")
print("=" * 70)

# Check if there's a way to see the compiled prompt
if hasattr(rlm, 'signature'):
    print("\nSignature:", rlm.signature)

if hasattr(rlm, '_signature'):
    print("\n_Signature:", rlm._signature)

if hasattr(rlm, 'tools'):
    print("\nTools registered:", rlm.tools)
    for name, tool in rlm.tools.items():
        print(f"  {name}:")
        print(f"    Type: {type(tool)}")
        print(f"    Callable: {callable(tool)}")
        if hasattr(tool, '__doc__'):
            print(f"    Doc: {tool.__doc__}")
        if hasattr(tool, '__annotations__'):
            print(f"    Annotations: {tool.__annotations__}")

# Try to see what gets sent to the LLM by running with minimal input
print("\n" + "=" * 70)
print("Running RLM to see actual behavior")
print("=" * 70)

# Enable DSPy's built-in tracing if available
import inspect

# Try to patch the LM call to see what's sent
original_call = lm.__call__

def traced_call(*args, **kwargs):
    print("\n[LM CALL]")
    if args:
        print(f"Messages: {args[0] if len(args) > 0 else 'none'}")
    if 'messages' in kwargs:
        msgs = kwargs['messages']
        for i, msg in enumerate(msgs):
            print(f"\nMessage {i}:")
            print(f"  Role: {msg.get('role', 'unknown')}")
            content = msg.get('content', '')
            if len(content) > 500:
                print(f"  Content: {content[:500]}...")
            else:
                print(f"  Content: {content}")
    return original_call(*args, **kwargs)

lm.__call__ = traced_call

try:
    result = rlm(
        context="A graph about activities.",
        question="What statistics are available for this graph?"
    )
    print("\n" + "=" * 70)
    print("Result:")
    print(result)
except Exception as e:
    print(f"\nError: {e}")
    import traceback
    traceback.print_exc()
