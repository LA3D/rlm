#!/usr/bin/env python
"""Test that llm_query tool is now available and working."""

import sys
import os
sys.path.insert(0, '/Users/cvardema/dev/git/LA3D/rlm')

import dspy
from experiments.reasoningbank.prototype.tools.sparql import create_tools

# Configure DSPy with sub_lm
if not os.environ.get('ANTHROPIC_API_KEY'):
    raise ValueError("Set ANTHROPIC_API_KEY environment variable")

# Main LM
lm = dspy.LM('anthropic/claude-sonnet-4-5-20250929', api_key=os.environ['ANTHROPIC_API_KEY'])
dspy.configure(lm=lm)

# Sub LM (for llm_query)
sub_lm = dspy.LM('anthropic/claude-haiku-4-5-20251001', api_key=os.environ['ANTHROPIC_API_KEY'])
dspy.settings.sub_lm = sub_lm

# Create SPARQL tools
sparql_tools = create_tools('uniprot')
tools = sparql_tools.as_dspy_tools()

print("=" * 80)
print("Testing llm_query tool")
print("=" * 80)

# Check that llm_query is in the tools
print(f"\nAvailable tools ({len(tools)}):")
for tool_name in sorted(tools.keys()):
    print(f"  - {tool_name}")

print(f"\nllm_query available: {'llm_query' in tools}")

if 'llm_query' not in tools:
    print("\n❌ FAILED: llm_query not in tools")
    sys.exit(1)

# Test calling llm_query
print("\n" + "=" * 80)
print("Testing llm_query call")
print("=" * 80)

prompt = "In UniProt RDF, what predicate is used to represent the mnemonic (entry name) of a protein?"

try:
    result = tools['llm_query'](prompt, None)
    print(f"\nPrompt: {prompt}")
    print(f"\nResponse: {result}")
    print(f"\nResponse type: {type(result)}")
    print(f"\nResponse length: {len(result)} chars")

    if isinstance(result, str) and len(result) > 0 and 'error' not in result.lower():
        print("\n✅ SUCCESS: llm_query working correctly")
    else:
        print("\n⚠ WARNING: llm_query returned unexpected result")
        sys.exit(1)

except Exception as e:
    print(f"\n❌ ERROR: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)
