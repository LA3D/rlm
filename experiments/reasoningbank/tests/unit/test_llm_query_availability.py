#!/usr/bin/env python
"""Test if llm_query is available in LocalPythonInterpreter environment."""

import sys
import os
sys.path.insert(0, '/Users/cvardema/dev/git/LA3D/rlm')

import dspy
from experiments.reasoningbank.tools.local_interpreter import LocalPythonInterpreter
from experiments.reasoningbank.tools.sparql import create_tools

# Configure DSPy
if not os.environ.get('ANTHROPIC_API_KEY'):
    raise ValueError("Set ANTHROPIC_API_KEY environment variable")

lm = dspy.LM('anthropic/claude-sonnet-4-5-20250929', api_key=os.environ['ANTHROPIC_API_KEY'])
dspy.configure(lm=lm)

sub_lm = dspy.LM('anthropic/claude-haiku-4-5-20251001', api_key=os.environ['ANTHROPIC_API_KEY'])

# Create SPARQL tools
sparql_tools = create_tools('uniprot')
tools = sparql_tools.as_dspy_tools()

print("=" * 80)
print("Testing llm_query availability in different environments")
print("=" * 80)

# Test 1: Check if llm_query is in tools dict
print("\n1. Is llm_query in SPARQL tools dict?")
print(f"   {'llm_query' in tools}")
if 'llm_query' in tools:
    print(f"   (We added it ourselves)")

# Test 2: Create LocalPythonInterpreter WITHOUT sub_lm
print("\n2. Creating LocalPythonInterpreter WITHOUT sub_lm...")
interpreter_no_sub = LocalPythonInterpreter(
    tools=tools,
    output_fields=[{'name': 'sparql'}, {'name': 'answer'}]
)

print(f"   Namespace keys: {sorted(interpreter_no_sub.namespace.keys())}")
print(f"   Is llm_query in namespace? {'llm_query' in interpreter_no_sub.namespace}")

# Test 2b: Create LocalPythonInterpreter WITH sub_lm
print("\n2b. Creating LocalPythonInterpreter WITH sub_lm...")
interpreter = LocalPythonInterpreter(
    tools=tools,
    output_fields=[{'name': 'sparql'}, {'name': 'answer'}],
    sub_lm=sub_lm  # Pass sub_lm
)

print(f"    Namespace keys: {sorted(interpreter.namespace.keys())}")
print(f"    Is llm_query in namespace? {'llm_query' in interpreter.namespace}")
print(f"    Is llm_query_batched in namespace? {'llm_query_batched' in interpreter.namespace}")

# Test 3: Try to create RLM with LocalPythonInterpreter and sub_lm
print("\n3. Creating DSPy RLM with LocalPythonInterpreter and sub_lm...")
try:
    rlm = dspy.RLM(
        "context, question -> sparql, answer",
        max_iterations=3,
        max_llm_calls=10,
        tools=tools,
        sub_lm=sub_lm,
        interpreter=interpreter,
    )
    print("   ✅ RLM created successfully")

    # Check if RLM adds llm_query to interpreter namespace
    print(f"\n4. After RLM creation, is llm_query in interpreter namespace?")
    print(f"   {' llm_query' in interpreter.namespace}")

    if 'llm_query' in interpreter.namespace:
        print(f"   ✅ DSPy RLM added llm_query to interpreter")
    else:
        print(f"   ❌ DSPy RLM did NOT add llm_query to interpreter")

except ValueError as e:
    if 'conflicts with built-in' in str(e):
        print(f"   ❌ ERROR: {e}")
        print(f"\n   This means:")
        print(f"   - DSPy RLM has llm_query as a built-in")
        print(f"   - We cannot add llm_query to tools when using default interpreter")
        print(f"   - But with LocalPythonInterpreter, llm_query might not be available!")
    else:
        raise

# Test 4: Full integration test with sub_lm passed to LocalPythonInterpreter
print("\n5. Full integration test (tools without llm_query, LocalPython with sub_lm)...")
tools_no_llm = {k: v for k, v in tools.items() if k != 'llm_query'}
interpreter2 = LocalPythonInterpreter(
    tools=tools_no_llm,
    output_fields=[{'name': 'sparql'}, {'name': 'answer'}],
    sub_lm=sub_lm  # THIS is the key fix!
)

print(f"   LocalPythonInterpreter namespace has llm_query: {'llm_query' in interpreter2.namespace}")

try:
    rlm2 = dspy.RLM(
        "context, question -> sparql, answer",
        max_iterations=3,
        max_llm_calls=10,
        tools=tools_no_llm,
        sub_lm=sub_lm,
        interpreter=interpreter2,
    )
    print("   ✅ RLM created successfully")
    print(f"   Is llm_query in interpreter namespace? {'llm_query' in interpreter2.namespace}")

    if 'llm_query' in interpreter2.namespace:
        print(f"   ✅ SUCCESS: llm_query is available to agents!")
    else:
        print(f"   ❌ FAILED: llm_query is NOT available!")

except Exception as e:
    print(f"   ❌ ERROR: {e}")
