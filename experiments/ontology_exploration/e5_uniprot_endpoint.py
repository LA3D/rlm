#!/usr/bin/env python3
"""E5: UniProt with Real SPARQL Endpoint Execution

Tests the two-phase workflow on UniProt ontology (larger, more complex) and
validates generated queries against the actual UniProt SPARQL endpoint.

This extends E4 by:
1. Testing on larger ontology (UniProt core.ttl)
2. Executing SPARQL against real endpoint
3. Validating query correctness via result validation
"""

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
from rlm_runtime.tools.sparql_tools import make_sparql_tools
from sparqlx import SPARQLWrapper

# UniProt SPARQL endpoint
UNIPROT_ENDPOINT = "https://sparql.uniprot.org/sparql/"

# Test queries for UniProt ontology
TEST_QUERIES = [
    {
        'id': 'simple_schema',
        'question': "What are the main classes in the UniProt core ontology?",
        'complexity': 'Simple - schema exploration (should use local ontology only)',
        'expected_approach': 'Local ontology exploration, no remote queries needed'
    },
    {
        'id': 'relationship_schema',
        'question': "What property connects Protein to Taxon in the UniProt schema?",
        'complexity': 'Relationship - schema navigation (should use local ontology only)',
        'expected_approach': 'Local ontology to find property, no remote queries needed'
    },
    {
        'id': 'instance_data',
        'question': "Show me 5 example proteins from the UniProt database with their names.",
        'complexity': 'Instance data - requires remote query (should query endpoint with LIMIT)',
        'expected_approach': 'Remote query with explicit LIMIT to avoid timeout'
    }
]


def create_guide_summary(guide: dict) -> str:
    """Extract concise summary from full guide."""
    summary_parts = []

    # Overview
    if 'ontology_overview' in guide:
        ov = guide['ontology_overview']
        summary_parts.append(f"{ov['name']}: {ov['purpose']}")

    # Core classes from first category
    if 'semantic_categories' in guide and len(guide['semantic_categories']) > 0:
        core = guide['semantic_categories'][0]
        summary_parts.append(f"\nCore Classes: {', '.join([c['name'] for c in core['classes'][:5]])}")

    # Key properties
    if 'properties' in guide and 'object_properties' in guide['properties']:
        props = guide['properties']['object_properties'][:8]
        summary_parts.append("\nKey Properties:")
        for p in props:
            summary_parts.append(f"- {p['name']}: {p['description'][:80] if p.get('description') else 'Links entities'}")

    # Query patterns
    if 'query_patterns' in guide:
        summary_parts.append(f"\nCommon Patterns: {len(guide['query_patterns'])} templates available")
        for qp in guide['query_patterns'][:2]:
            summary_parts.append(f"- {qp['name']}: {qp['description'][:60]}")

    return '\n'.join(summary_parts)


def execute_sparql_query(sparql: str, endpoint: str = UNIPROT_ENDPOINT) -> dict:
    """Execute SPARQL query against endpoint and return results."""
    try:
        wrapper = SPARQLWrapper(sparql_endpoint=endpoint)

        # Query with convert=True to get Python dicts with RDFLib objects
        result = wrapper.query(sparql, convert=True)

        return {
            'success': True,
            'result_count': len(result) if isinstance(result, list) else 0,
            'results': result[:5] if isinstance(result, list) else None,  # First 5 for inspection
            'error': None
        }
    except Exception as e:
        return {
            'success': False,
            'result_count': 0,
            'results': None,
            'error': str(e)
        }


def create_guide(ont, lm):
    """Create ontology guide (E3-Retry style with full prompt)."""
    class StructuredExplorationSig(dspy.Signature):
        """Explore an ontology and produce a structured JSON guide.

        You have access to `ont` (an rdflib Graph) and rdflib namespaces (RDF, RDFS, OWL).
        Write Python code to explore: ont.triples(), ont.subjects(), ont.objects(), ont.value().
        """
        ont: object = dspy.InputField(desc="The loaded rdflib Graph object")
        rdf_imports: str = dspy.InputField(desc="Available rdflib imports info")

        guide_json: str = dspy.OutputField(desc="Structured JSON guide following the schema in the task description")

    # Detailed prompt matching E3-Retry
    rdf_imports_info = """## Your Task

Explore this ontology and produce a STRUCTURED JSON GUIDE that captures:
1. What exists (classes, properties, hierarchies)
2. Why it matters (semantic importance, use cases)
3. How to query it (patterns, templates)

## Available in Namespace
- RDF, RDFS, OWL - Standard rdflib namespaces (e.g., RDF.type, RDFS.label, OWL.Class)
- Graph, Namespace - rdflib classes

## Common Exploration Patterns
```python
# Count triples
print(f"Triples: {len(ont)}")

# Find all classes
classes = list(ont.subjects(RDF.type, OWL.Class))
print(f"Found {len(classes)} classes")

# Get label for a URI
for c in classes[:5]:
    label = ont.value(c, RDFS.label)
    print(f"  {c}: {label}")

# Get superclasses
for parent in ont.objects(some_class, RDFS.subClassOf):
    print(f"  parent: {parent}")

# Get properties with domain/range
for prop in ont.subjects(RDF.type, OWL.ObjectProperty):
    domain = ont.value(prop, RDFS.domain)
    range_val = ont.value(prop, RDFS.range)
```

## REQUIRED JSON Schema

Your output MUST be valid JSON following this schema:

```json
{
  "ontology_name": "Human-readable name",
  "namespace": "Primary namespace URI",
  "domain_purpose": "1-2 sentence summary of what this ontology models",

  "key_classes": [
    {
      "uri": "Full URI from ontology",
      "label": "Human-readable label",
      "comment": "Description if available",
      "why_important": "Explain WHY this class matters for understanding the domain"
    }
  ],

  "key_properties": [
    {
      "uri": "Full URI from ontology",
      "label": "Human-readable label",
      "domain": "Domain class URI or label",
      "range": "Range class URI or label",
      "why_important": "Explain what relationships this property enables"
    }
  ],

  "design_patterns": [
    {
      "pattern_name": "Name of the design pattern",
      "description": "What is this pattern and why is it used?",
      "example_classes": ["List of class URIs demonstrating this pattern"],
      "example_properties": ["List of property URIs demonstrating this pattern"]
    }
  ],

  "query_patterns": [
    {
      "use_case": "What kind of question does this pattern answer?",
      "pattern_type": "e.g., 'find instances', 'traverse hierarchy', 'follow relationship'",
      "sparql_template": "SPARQL query with ?variables for key elements",
      "explanation": "How and when to use this pattern"
    }
  ],

  "semantic_insights": [
    "Key insight 1 about how concepts relate",
    "Key insight 2 about domain modeling choices",
    "Key insight 3 about intended usage"
  ]
}
```

## IMPORTANT: Explicit Semantic Reasoning

For each "why_important" field, you MUST explain:
- WHY this element matters for understanding the domain
- WHAT role it plays in the conceptual model
- HOW it connects to other concepts

Do NOT just describe structure - explain SEMANTICS.

## Validation

After creating the JSON, validate that:
- All URIs exist in the ontology
- JSON is valid (use json.loads() to test)
- All required fields are present
- Semantic explanations are meaningful (not just structural descriptions)
"""

    interpreter = NamespaceCodeInterpreter(result_truncation_limit=15000)  # Match E3-Retry
    tools = {'RDF': RDF, 'RDFS': RDFS, 'OWL': OWL, 'Namespace': Namespace, 'Graph': Graph}

    # Match E3-Retry configuration: 20 iterations, 30 LM calls, verbose=True
    rlm = dspy.RLM(StructuredExplorationSig, max_iterations=20, max_llm_calls=30, verbose=True,
                   interpreter=interpreter, tools=tools)

    result = rlm(ont=ont, rdf_imports=rdf_imports_info)
    return result


def run_query_with_guide(query_text: str, guide_summary: str, ont, endpoint: str, lm):
    """Run with guide summary using SPARQL tools."""
    class QuerySig(dspy.Signature):
        """Answer question by querying the UniProt SPARQL endpoint.

        You have access to:
        - ont: Local ontology graph (schema/structure)
        - sparql_query(): Execute queries against remote UniProt endpoint
        - res_head(), res_sample(), res_where(), etc.: Inspect results

        Use the local ontology to understand the schema, then query the endpoint.
        """
        question: str = dspy.InputField()
        guide: str = dspy.InputField(desc="Ontology guide summary")
        ont: object = dspy.InputField(desc="Local rdflib Graph (schema)")

        answer: str = dspy.OutputField(desc="Answer to the question")
        queries_executed: str = dspy.OutputField(desc="SPARQL queries that were executed")

    # Create namespace for RLM execution
    ns = {}

    # Create bounded SPARQL tools
    sparql_tools = make_sparql_tools(
        endpoint=endpoint,
        ns=ns,
        max_results=100,  # Auto-limit results
        timeout=30.0      # 30 second timeout
    )

    interpreter = NamespaceCodeInterpreter(result_truncation_limit=5000)

    # Add SPARQL tools + rdflib tools
    tools = {
        'RDF': RDF,
        'RDFS': RDFS,
        'OWL': OWL,
        'Namespace': Namespace,
        **sparql_tools  # sparql_query, res_head, res_sample, res_where, res_group, res_distinct
    }

    rlm = dspy.RLM(QuerySig, max_iterations=15, max_llm_calls=12, verbose=True,
                   interpreter=interpreter, tools=tools)

    result = rlm(question=query_text, guide=guide_summary, ont=ont)
    return result, ns


def run_query_without_guide(query_text: str, ont, endpoint: str, lm):
    """Run without guide (baseline) using SPARQL tools."""
    class QuerySig(dspy.Signature):
        """Answer question by querying the UniProt SPARQL endpoint.

        You have access to:
        - ont: Local ontology graph (schema/structure)
        - sparql_query(): Execute queries against remote UniProt endpoint
        - res_head(), res_sample(), res_where(), etc.: Inspect results

        Explore the local ontology to understand the schema, then query the endpoint.
        """
        question: str = dspy.InputField()
        ont: object = dspy.InputField(desc="Local rdflib Graph (schema)")

        answer: str = dspy.OutputField(desc="Answer to the question")
        queries_executed: str = dspy.OutputField(desc="SPARQL queries that were executed")

    # Create namespace for RLM execution
    ns = {}

    # Create bounded SPARQL tools
    sparql_tools = make_sparql_tools(
        endpoint=endpoint,
        ns=ns,
        max_results=100,  # Auto-limit results
        timeout=30.0      # 30 second timeout
    )

    interpreter = NamespaceCodeInterpreter(result_truncation_limit=5000)

    # Add SPARQL tools + rdflib tools
    tools = {
        'RDF': RDF,
        'RDFS': RDFS,
        'OWL': OWL,
        'Namespace': Namespace,
        **sparql_tools  # sparql_query, res_head, res_sample, res_where, res_group, res_distinct
    }

    rlm = dspy.RLM(QuerySig, max_iterations=15, max_llm_calls=12, verbose=True,
                   interpreter=interpreter, tools=tools)

    result = rlm(question=query_text, ont=ont)
    return result, ns


def extract_metrics(lm):
    """Extract metrics from LM history."""
    calls = len(lm.history)
    input_tokens = 0
    output_tokens = 0
    for call in lm.history:
        if isinstance(call, dict) and 'usage' in call:
            usage = call['usage']
            input_tokens += usage.get('prompt_tokens', 0)
            output_tokens += usage.get('completion_tokens', 0)

    tokens = input_tokens + output_tokens
    cost = (input_tokens / 1_000_000 * 3.0 + output_tokens / 1_000_000 * 15.0)

    return {
        'lm_calls': calls,
        'input_tokens': input_tokens,
        'output_tokens': output_tokens,
        'total_tokens': tokens,
        'cost_usd': cost
    }


def main():
    print("\n" + "=" * 70)
    print("E5: UNIPROT WITH REAL SPARQL ENDPOINT")
    print("=" * 70)
    print(f"Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")

    # Load UniProt ontology
    print("Loading UniProt core ontology...")
    ontology_path = project_root / "ontology" / "uniprot" / "core.ttl"
    ont = Graph()
    ont.parse(ontology_path)
    print(f"✓ Loaded {len(ont)} triples\n")

    # Configure DSPy (match E3-Retry: 8192 tokens for JSON output)
    lm = dspy.LM("anthropic/claude-sonnet-4-5-20250929", max_tokens=8192, cache=False)
    dspy.configure(lm=lm)

    # Phase 1: Load or create guide
    print("=" * 70)
    print("PHASE 1: GUIDE LOADING/CREATION")
    print("=" * 70)
    print()

    guide_cache_path = project_root / "experiments" / "ontology_exploration" / "e5_uniprot_guide_cache.json"

    # Check for cached guide
    if guide_cache_path.exists():
        print(f"Found cached guide at: {guide_cache_path}")
        try:
            with open(guide_cache_path, 'r') as f:
                cached_data = json.load(f)

            guide = cached_data.get('guide', {})
            guide_summary = create_guide_summary(guide) if guide else ""
            guide_valid = bool(guide)

            print(f"✓ Loaded cached guide")
            print(f"  Created: {cached_data.get('timestamp', 'unknown')}")
            print(f"  Cost: ${cached_data.get('cost_usd', 0):.4f}")
            print(f"  Valid JSON: {guide_valid}")
            if guide_valid:
                print(f"  Summary length: {len(guide_summary)} chars")

            guide_creation_success = True
            elapsed_guide = 0
            metrics_guide = {'lm_calls': 0, 'total_tokens': 0, 'cost_usd': cached_data.get('cost_usd', 0)}

            print("\n  To create a fresh guide, delete the cache file and re-run.")

        except Exception as e:
            print(f"✗ Failed to load cached guide: {e}")
            print("  Will create new guide...")
            guide_cache_path = None  # Force creation

    # Create guide if no cache or cache load failed
    if not guide_cache_path or not guide_cache_path.exists():
        print("No cached guide found. Creating new guide...")
        print("(This is expensive - guide will be cached for future runs)\n")

        lm.history = []
        start = datetime.now()

        try:
            guide_result = create_guide(ont, lm)
            elapsed_guide = (datetime.now() - start).total_seconds()
            metrics_guide = extract_metrics(lm)

            # Parse guide JSON
            try:
                guide = json.loads(guide_result.guide_json)
                guide_summary = create_guide_summary(guide)
                guide_valid = True
            except Exception as e:
                print(f"  ⚠ JSON parsing failed: {e}")
                guide = {}
                guide_summary = ""
                guide_valid = False

            print(f"✓ Guide created in {elapsed_guide:.1f}s")
            print(f"  LM calls: {metrics_guide['lm_calls']}")
            print(f"  Tokens: {metrics_guide['total_tokens']:,}")
            print(f"  Cost: ${metrics_guide['cost_usd']:.4f}")
            print(f"  Valid JSON: {guide_valid}")
            if guide_valid:
                print(f"  Summary length: {len(guide_summary)} chars")

            guide_creation_success = True

            # Cache the guide for future runs
            if guide_valid:
                cache_data = {
                    'timestamp': datetime.now().isoformat(),
                    'ontology': 'UniProt core',
                    'ontology_triples': len(ont),
                    'guide': guide,
                    'cost_usd': metrics_guide['cost_usd'],
                    'elapsed_seconds': elapsed_guide,
                    'lm_calls': metrics_guide['lm_calls']
                }
                with open(guide_cache_path, 'w') as f:
                    json.dump(cache_data, f, indent=2)
                print(f"\n  Guide cached to: {guide_cache_path}")

        except Exception as e:
            print(f"✗ Guide creation failed: {e}")
            guide_creation_success = False
            guide_summary = None
            elapsed_guide = 0
            metrics_guide = {'lm_calls': 0, 'total_tokens': 0, 'cost_usd': 0}

    print()

    # Phase 2: Query construction with endpoint validation
    print("=" * 70)
    print("PHASE 2: QUERY CONSTRUCTION + ENDPOINT VALIDATION")
    print("=" * 70)
    print()

    query_results = []

    for i, test_query in enumerate(TEST_QUERIES, 1):
        query_id = test_query['id']
        question = test_query['question']
        complexity = test_query['complexity']

        print("=" * 70)
        print(f"QUERY {i}/3: {query_id.upper()}")
        print(f"Question: {question}")
        print(f"Complexity: {complexity}")
        print("=" * 70)
        print()

        # Condition A: WITHOUT guide
        print("-" * 70)
        print("CONDITION A: WITHOUT GUIDE")
        print("-" * 70)

        lm.history = []
        start = datetime.now()

        try:
            result_no_guide, ns_no = run_query_without_guide(question, ont, UNIPROT_ENDPOINT, lm)
            elapsed_no = (datetime.now() - start).total_seconds()
            metrics_no = extract_metrics(lm)

            print(f"\n✓ Completed in {elapsed_no:.1f}s")
            print(f"  LM calls: {metrics_no['lm_calls']}")
            print(f"  Tokens: {metrics_no['total_tokens']:,}")
            print(f"  Cost: ${metrics_no['cost_usd']:.4f}")
            print(f"\n  Answer: {result_no_guide.answer[:200]}..." if len(result_no_guide.answer) > 200 else f"\n  Answer: {result_no_guide.answer}")
            print(f"\n  Queries executed:\n{result_no_guide.queries_executed}")

            # Check what results are in namespace
            result_handles = [k for k in ns_no.keys() if not k.startswith('_')]
            print(f"\n  Result handles created: {result_handles}")

            result_no = {
                'success': True,
                'elapsed_seconds': elapsed_no,
                'answer': result_no_guide.answer,
                'queries_executed': result_no_guide.queries_executed,
                'result_handles': result_handles,
                **metrics_no
            }

        except Exception as e:
            print(f"✗ Failed: {e}")
            import traceback
            traceback.print_exc()

            result_no = {
                'success': False,
                'elapsed_seconds': 0,
                'lm_calls': 0,
                'total_tokens': 0,
                'cost_usd': 0,
                'answer': None,
                'queries_executed': None,
                'error': str(e)
            }

        print()

        # Condition B: WITH guide
        if guide_creation_success and guide_summary:
            print("-" * 70)
            print("CONDITION B: WITH GUIDE")
            print("-" * 70)

            lm.history = []
            start = datetime.now()

            try:
                result_with_guide, ns_with = run_query_with_guide(question, guide_summary, ont, UNIPROT_ENDPOINT, lm)
                elapsed_with = (datetime.now() - start).total_seconds()
                metrics_with = extract_metrics(lm)

                print(f"\n✓ Completed in {elapsed_with:.1f}s")
                print(f"  LM calls: {metrics_with['lm_calls']}")
                print(f"  Tokens: {metrics_with['total_tokens']:,}")
                print(f"  Cost: ${metrics_with['cost_usd']:.4f}")
                print(f"\n  Answer: {result_with_guide.answer[:200]}..." if len(result_with_guide.answer) > 200 else f"\n  Answer: {result_with_guide.answer}")
                print(f"\n  Queries executed:\n{result_with_guide.queries_executed}")

                # Check what results are in namespace
                result_handles = [k for k in ns_with.keys() if not k.startswith('_')]
                print(f"\n  Result handles created: {result_handles}")

                result_with = {
                    'success': True,
                    'elapsed_seconds': elapsed_with,
                    'answer': result_with_guide.answer,
                    'queries_executed': result_with_guide.queries_executed,
                    'result_handles': result_handles,
                    **metrics_with
                }

            except Exception as e:
                print(f"✗ Failed: {e}")
                import traceback
                traceback.print_exc()

                result_with = {
                    'success': False,
                    'elapsed_seconds': 0,
                    'lm_calls': 0,
                    'total_tokens': 0,
                    'cost_usd': 0,
                    'answer': None,
                    'queries_executed': None,
                    'error': str(e)
                }

            print()

            # Comparison
            if result_no['success'] and result_with['success']:
                print("-" * 70)
                print("COMPARISON")
                print("-" * 70)

                time_diff = result_with['elapsed_seconds'] - result_no['elapsed_seconds']
                time_pct = (time_diff / result_no['elapsed_seconds'] * 100) if result_no['elapsed_seconds'] > 0 else 0

                tokens_diff = result_with['total_tokens'] - result_no['total_tokens']
                tokens_pct = (tokens_diff / result_no['total_tokens'] * 100) if result_no['total_tokens'] > 0 else 0

                cost_diff = result_with['cost_usd'] - result_no['cost_usd']
                cost_pct = (cost_diff / result_no['cost_usd'] * 100) if result_no['cost_usd'] > 0 else 0

                calls_diff = result_with['lm_calls'] - result_no['lm_calls']

                print(f"Time: {result_no['elapsed_seconds']:.1f}s → {result_with['elapsed_seconds']:.1f}s "
                      f"({time_diff:+.1f}s, {time_pct:+.1f}%)")
                print(f"LM calls: {result_no['lm_calls']} → {result_with['lm_calls']} ({calls_diff:+d})")
                print(f"Tokens: {result_no['total_tokens']:,} → {result_with['total_tokens']:,} "
                      f"({tokens_diff:+,}, {tokens_pct:+.1f}%)")
                print(f"Cost: ${result_no['cost_usd']:.4f} → ${result_with['cost_usd']:.4f} "
                      f"(${cost_diff:+.4f}, {cost_pct:+.1f}%)")

        else:
            print("⊘ Skipping Condition B (guide not available)")
            result_with = None

        print()

        # Store results
        query_results.append({
            'query_id': query_id,
            'question': question,
            'complexity': complexity,
            'condition_a_no_guide': result_no,
            'condition_b_with_guide': result_with
        })

    # Summary
    print("=" * 70)
    print("E5 SUMMARY")
    print("=" * 70)
    print()

    print(f"Guide creation: {'✓' if guide_creation_success else '✗'}")
    if guide_creation_success:
        print(f"  Cost: ${metrics_guide['cost_usd']:.4f}")
        print(f"  Time: {elapsed_guide:.1f}s")
        print(f"  LM calls: {metrics_guide['lm_calls']}")
    print()

    successful_queries_no = sum(1 for q in query_results if q['condition_a_no_guide']['success'])

    print(f"Queries without guide:")
    print(f"  Completed: {successful_queries_no}/{len(TEST_QUERIES)}")

    if guide_creation_success and guide_summary:
        successful_queries_with = sum(1 for q in query_results if q['condition_b_with_guide'] and q['condition_b_with_guide']['success'])

        print(f"\nQueries with guide:")
        print(f"  Completed: {successful_queries_with}/{len(TEST_QUERIES)}")

    print()
    print("=" * 70)
    print("E5 COMPLETED")
    print("=" * 70)

    # Save results
    results = {
        'timestamp': datetime.now().isoformat(),
        'ontology': 'UniProt core',
        'ontology_triples': len(ont),
        'endpoint': UNIPROT_ENDPOINT,
        'guide_creation': {
            'success': guide_creation_success,
            'elapsed_seconds': elapsed_guide,
            **metrics_guide
        } if guide_creation_success else {'success': False},
        'queries': query_results
    }

    results_path = project_root / "experiments" / "ontology_exploration" / "e5_uniprot_results.json"
    with open(results_path, 'w') as f:
        json.dump(results, f, indent=2)

    print(f"Results saved to: {results_path}")

    # Save guide if created
    if guide_creation_success and guide_valid:
        guide_path = project_root / "experiments" / "ontology_exploration" / "e5_uniprot_guide.json"
        with open(guide_path, 'w') as f:
            json.dump(guide, f, indent=2)
        print(f"Guide saved to: {guide_path}")


if __name__ == "__main__":
    main()
