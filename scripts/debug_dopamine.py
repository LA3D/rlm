#!/usr/bin/env python3
"""Debug script to capture raw API responses for dopamine task."""

import sys
sys.path.insert(0, '.')

import dspy
from rlm_runtime.tools import make_sparql_tools, make_ontology_tools
from rlm.ontology import GraphMeta
from rdflib import Graph
import anthropic
import os

# Monkey-patch Anthropic client to log raw responses
original_create = anthropic.Anthropic.messages.create

def logging_create(self, **kwargs):
    print("\n" + "="*80)
    print("OUTGOING API REQUEST:")
    print(f"Model: {kwargs.get('model')}")
    print(f"Max tokens: {kwargs.get('max_tokens')}")
    print(f"Messages: {len(kwargs.get('messages', []))} messages")
    print("="*80)

    response = original_create(**kwargs)

    print("\n" + "="*80)
    print("INCOMING API RESPONSE:")
    print(f"Stop reason: {response.stop_reason}")
    print(f"Usage: {response.usage}")
    print(f"Content blocks: {len(response.content)}")
    if response.content:
        for i, block in enumerate(response.content):
            print(f"\nBlock {i}:")
            print(f"  Type: {block.type}")
            if hasattr(block, 'text'):
                print(f"  Text ({len(block.text)} chars): {block.text[:500]}")
    print("="*80 + "\n")

    return response

anthropic.Anthropic.messages.create = logging_create

# Now run the actual task
print("Loading UniProt ontology...")
g = Graph()
g.parse('ontology/uniprot/core.ttl', format='turtle')
meta = GraphMeta.from_graph(g, 'uniprot_core')

ns = {'uniprot_core_meta': meta}

# Build tools
sparql_tools = make_sparql_tools(
    endpoint='https://sparql.uniprot.org/sparql/',
    ns=ns,
    max_results=100,
    timeout=30.0
)

onto_tools = make_ontology_tools(meta, ns)
tools = {**sparql_tools, **onto_tools}

context = f"""You are constructing and executing SPARQL queries.
Use progressive disclosure: inspect schema first, then run bounded queries.

## Loaded ontology summaries:
Graph 'uniprot_core': {meta.stats()['total_triples']} triples

## SPARQL endpoint: https://sparql.uniprot.org/sparql/
"""

query = "Find reviewed proteins catalyzing reactions involving dopamine-like molecules, with natural variants related to a disease."

print(f"\nRunning query: {query}\n")

from rlm_runtime.engine.dspy_rlm import run_dspy_rlm_with_tools

try:
    result = run_dspy_rlm_with_tools(
        query=query,
        context=context,
        tools=tools,
        ns=ns,
        max_iterations=3,  # Just 3 iterations for debugging
        verbose=True
    )
    print(f"\n✅ Success! Answer: {result.answer[:200]}...")
except Exception as e:
    print(f"\n❌ Error: {e}")
    import traceback
    traceback.print_exc()
