#!/usr/bin/env python3
"""Quick test of SPARQL tool-based query construction"""

import sys
from pathlib import Path

project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

import dspy
from rdflib import Graph, RDF, RDFS, OWL, Namespace
from rlm_runtime.interpreter.namespace_interpreter import NamespaceCodeInterpreter
from rlm_runtime.tools.sparql_tools import make_sparql_tools

UNIPROT_ENDPOINT = "https://sparql.uniprot.org/sparql/"

def main():
    print("Loading UniProt ontology...")
    ontology_path = project_root / "ontology" / "uniprot" / "core.ttl"
    ont = Graph()
    ont.parse(ontology_path)
    print(f"✓ Loaded {len(ont)} triples\n")

    # Configure DSPy
    lm = dspy.LM("anthropic/claude-sonnet-4-5-20250929", max_tokens=4096, cache=False)
    dspy.configure(lm=lm)

    # Define signature
    class QuerySig(dspy.Signature):
        """Answer question by querying the UniProt SPARQL endpoint.

        You have access to:
        - ont: Local ontology graph (schema/structure)
        - sparql_query(query, name='res'): Execute query, returns summary, stores result handle
        - res_head(result_name, n=10): View first N rows
        - res_sample(result_name, n=10): Random sample of N rows

        IMPORTANT:
        - The local ontology (ont) contains SCHEMA (classes, properties, structure)
        - The remote endpoint contains INSTANCE DATA (millions of proteins, organisms, etc.)
        - Use ont to understand schema, then query endpoint for specific data
        - ALWAYS include LIMIT in your SELECT queries to avoid timeouts
        - Result handles are stored by name - use res_head('result_name') to inspect
        """
        question: str = dspy.InputField()
        ont: object = dspy.InputField(desc="Local ontology graph (schema)")

        answer: str = dspy.OutputField()
        queries_executed: str = dspy.OutputField()

    # Create namespace and tools
    ns = {}
    sparql_tools = make_sparql_tools(
        endpoint=UNIPROT_ENDPOINT,
        ns=ns,
        max_results=100,
        timeout=30.0
    )

    interpreter = NamespaceCodeInterpreter(result_truncation_limit=5000)

    tools = {
        'RDF': RDF,
        'RDFS': RDFS,
        'OWL': OWL,
        'Namespace': Namespace,
        **sparql_tools
    }

    rlm = dspy.RLM(QuerySig, max_iterations=10, max_llm_calls=10, verbose=True,
                   interpreter=interpreter, tools=tools)

    # Test query
    question = "What are the main classes in the UniProt core ontology?"

    print("=" * 70)
    print(f"QUESTION: {question}")
    print("=" * 70)
    print()

    result = rlm(question=question, ont=ont)

    print("\n" + "=" * 70)
    print("RESULT")
    print("=" * 70)
    print(f"\nAnswer:\n{result.answer}")
    print(f"\nQueries executed:\n{result.queries_executed}")

    # Check namespace
    result_handles = [k for k in ns.keys() if not k.startswith('_')]
    print(f"\nResult handles in namespace: {result_handles}")

    print("\n✓ Test completed successfully!")


if __name__ == "__main__":
    main()
