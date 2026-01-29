#!/usr/bin/env python3
"""E5 Debug: Step-by-step debugging of UniProt endpoint experiment"""

import sys
import os
from pathlib import Path
from datetime import datetime
import json

project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

import dspy
from rdflib import Graph, RDF, RDFS, OWL, Namespace
from rlm_runtime.interpreter.namespace_interpreter import NamespaceCodeInterpreter
from sparqlx import SPARQLWrapper

UNIPROT_ENDPOINT = "https://sparql.uniprot.org/sparql/"

def test_step_1_load_ontology():
    """Step 1: Load UniProt ontology"""
    print("\n" + "=" * 70)
    print("STEP 1: LOAD ONTOLOGY")
    print("=" * 70)

    ontology_path = project_root / "ontology" / "uniprot" / "core.ttl"
    print(f"Loading from: {ontology_path}")

    start = datetime.now()
    ont = Graph()
    ont.parse(ontology_path)
    elapsed = (datetime.now() - start).total_seconds()

    print(f"✓ Loaded {len(ont)} triples in {elapsed:.2f}s")

    # Sample some triples
    print("\nSample triples:")
    for i, (s, p, o) in enumerate(ont):
        if i >= 3:
            break
        print(f"  {s} {p} {o}")

    return ont


def test_step_2_configure_dspy():
    """Step 2: Configure DSPy"""
    print("\n" + "=" * 70)
    print("STEP 2: CONFIGURE DSPY")
    print("=" * 70)

    lm = dspy.LM("anthropic/claude-sonnet-4-5-20250929", max_tokens=4096, cache=False)
    dspy.configure(lm=lm)

    print(f"✓ DSPy configured with model: {lm.model}")
    print(f"  Cache disabled: {not lm.cache}")

    return lm


def test_step_3_simple_query(ont, lm):
    """Step 3: Test simple query construction WITHOUT guide"""
    print("\n" + "=" * 70)
    print("STEP 3: SIMPLE QUERY CONSTRUCTION (NO GUIDE)")
    print("=" * 70)

    class QuerySig(dspy.Signature):
        """Construct SPARQL query by exploring ontology."""
        question: str = dspy.InputField()
        ont: object = dspy.InputField(desc="rdflib Graph")

        sparql_query: str = dspy.OutputField()
        explanation: str = dspy.OutputField()

    interpreter = NamespaceCodeInterpreter(result_truncation_limit=5000)
    tools = {'RDF': RDF, 'RDFS': RDFS, 'OWL': OWL, 'Namespace': Namespace}

    rlm = dspy.RLM(QuerySig, max_iterations=10, max_llm_calls=8, verbose=True,
                   interpreter=interpreter, tools=tools)

    question = "What are the main classes in the UniProt core ontology?"
    print(f"Question: {question}")
    print("\nRunning RLM (verbose mode)...\n")

    lm.history = []
    start = datetime.now()

    try:
        result = rlm(question=question, ont=ont)
        elapsed = (datetime.now() - start).total_seconds()

        print(f"\n✓ Query constructed in {elapsed:.1f}s")
        print(f"  LM calls: {len(lm.history)}")

        print(f"\nGenerated SPARQL:")
        print("-" * 70)
        print(result.sparql_query)
        print("-" * 70)

        print(f"\nExplanation:")
        print(result.explanation[:200] + "..." if len(result.explanation) > 200 else result.explanation)

        return result.sparql_query

    except Exception as e:
        print(f"\n✗ Query construction failed: {e}")
        import traceback
        traceback.print_exc()
        return None


def test_step_4_endpoint_execution(sparql):
    """Step 4: Test endpoint execution"""
    print("\n" + "=" * 70)
    print("STEP 4: ENDPOINT EXECUTION")
    print("=" * 70)

    if not sparql:
        print("⊘ No SPARQL query to test")
        return None

    print(f"Endpoint: {UNIPROT_ENDPOINT}")
    print(f"\nExecuting query...")

    try:
        wrapper = SPARQLWrapper(sparql_endpoint=UNIPROT_ENDPOINT)

        start = datetime.now()
        result = wrapper.query(sparql, convert=True)
        elapsed = (datetime.now() - start).total_seconds()

        result_count = len(result) if isinstance(result, list) else 0

        print(f"✓ Query executed in {elapsed:.2f}s")
        print(f"  Result count: {result_count}")

        if isinstance(result, list) and len(result) > 0:
            print(f"\nFirst result:")
            print(f"  {result[0]}")

        return result

    except Exception as e:
        print(f"✗ Query execution failed: {e}")
        import traceback
        traceback.print_exc()
        return None


def test_step_5_guide_creation(ont, lm):
    """Step 5: Test guide creation (E3-Retry style) with progress tracking"""
    print("\n" + "=" * 70)
    print("STEP 5: GUIDE CREATION (E3-RETRY STYLE)")
    print("=" * 70)
    print("WARNING: This may take several minutes and many LM calls")
    print("Press Ctrl+C to skip this step")
    print()

    input("Press Enter to continue or Ctrl+C to skip...")

    class GuideSig(dspy.Signature):
        """Explore ontology and create a structured guide."""
        ont: object = dspy.InputField(desc="rdflib Graph")

        guide: str = dspy.OutputField(desc="JSON guide with ontology_overview, semantic_categories, properties, query_patterns")
        summary: str = dspy.OutputField(desc="Brief summary of findings")

    interpreter = NamespaceCodeInterpreter(result_truncation_limit=5000)
    tools = {'RDF': RDF, 'RDFS': RDFS, 'OWL': OWL, 'Namespace': Namespace}

    rlm = dspy.RLM(GuideSig, max_iterations=15, max_llm_calls=15, verbose=True,
                   interpreter=interpreter, tools=tools)

    lm.history = []
    start = datetime.now()

    try:
        print("Creating guide (verbose mode)...\n")
        result = rlm(ont=ont)
        elapsed = (datetime.now() - start).total_seconds()

        print(f"\n✓ Guide created in {elapsed:.1f}s")
        print(f"  LM calls: {len(lm.history)}")

        # Count tokens
        input_tokens = 0
        output_tokens = 0
        for call in lm.history:
            if isinstance(call, dict) and 'usage' in call:
                usage = call['usage']
                input_tokens += usage.get('prompt_tokens', 0)
                output_tokens += usage.get('completion_tokens', 0)

        total_tokens = input_tokens + output_tokens
        cost = (input_tokens / 1_000_000 * 3.0 + output_tokens / 1_000_000 * 15.0)

        print(f"  Tokens: {total_tokens:,}")
        print(f"  Cost: ${cost:.4f}")

        # Try to parse guide
        try:
            guide = json.loads(result.guide)
            print(f"\n✓ Valid JSON guide")

            if 'ontology_overview' in guide:
                print(f"  Has ontology_overview: {guide['ontology_overview'].get('name', 'N/A')}")
            if 'semantic_categories' in guide:
                print(f"  Semantic categories: {len(guide['semantic_categories'])}")
            if 'properties' in guide:
                print(f"  Properties: {len(guide['properties'].get('object_properties', []))}")

            return guide

        except:
            print(f"\n⚠ Guide is not valid JSON")
            print(f"  Summary: {result.summary[:200]}")
            return None

    except KeyboardInterrupt:
        print("\n\n⊘ Guide creation interrupted by user")
        return None
    except Exception as e:
        print(f"\n✗ Guide creation failed: {e}")
        import traceback
        traceback.print_exc()
        return None


def main():
    print("\n" + "=" * 70)
    print("E5 DEBUG: STEP-BY-STEP TESTING")
    print("=" * 70)
    print(f"Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

    # Step 1: Load ontology
    ont = test_step_1_load_ontology()

    # Step 2: Configure DSPy
    lm = test_step_2_configure_dspy()

    # Step 3: Simple query construction
    sparql = test_step_3_simple_query(ont, lm)

    # Step 4: Endpoint execution
    if sparql:
        result = test_step_4_endpoint_execution(sparql)

    # Step 5: Guide creation (optional, can be skipped)
    try:
        guide = test_step_5_guide_creation(ont, lm)
    except KeyboardInterrupt:
        print("\n⊘ Skipped guide creation")
        guide = None

    print("\n" + "=" * 70)
    print("E5 DEBUG COMPLETED")
    print("=" * 70)


if __name__ == "__main__":
    main()
