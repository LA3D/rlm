#!/usr/bin/env python3
"""E3: Structured Materialization - Does JSON schema force explicit reasoning?

Hypothesis: Structured output with explicit schema will force the model to:
1. Reason explicitly about WHY classes/properties matter
2. Separate "what exists" (structure) from "why it matters" (semantics)
3. Possibly trigger llm_query for sub-questions about importance

E1-E2-Large showed that neither guidance nor scale triggered llm_query.
E3 tests whether STRUCTURED OUTPUT FORMAT changes behavior.

Setup:
- Load PROV ontology (back to baseline for comparison)
- Ask for JSON output with explicit schema
- Require "why_important" fields that force semantic reasoning
- Include query_patterns with SPARQL templates

Measure:
- Does structured format trigger llm_query?
- Is output valid JSON?
- Are URIs grounded (exist in ontology)?
- Is semantic reasoning explicit?
- Cost vs E1/E2

Usage:
    source ~/uvws/.venv/bin/activate
    python experiments/ontology_exploration/e3_structured_materialization.py
"""

import sys
import os
from pathlib import Path
from datetime import datetime

# Add project root
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

if not os.environ.get("ANTHROPIC_API_KEY"):
    print("ERROR: Set ANTHROPIC_API_KEY")
    sys.exit(1)


def run_e3():
    """Run E3: Structured Materialization experiment."""
    import dspy
    from rdflib import Graph, RDF, RDFS, OWL, Namespace
    import json

    print("\n" + "=" * 70)
    print("E3: STRUCTURED MATERIALIZATION")
    print("=" * 70)
    print(f"Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print()

    # Load PROV ontology (same as E1/E2 for comparison)
    ontology_path = project_root / "ontology" / "prov.ttl"
    if not ontology_path.exists():
        print(f"ERROR: Ontology not found at {ontology_path}")
        sys.exit(1)

    print(f"Loading ontology: {ontology_path}")
    ont = Graph()
    ont.parse(ontology_path)
    print(f"Loaded {len(ont)} triples")
    print()

    # Configure DSPy
    lm = dspy.LM("anthropic/claude-sonnet-4-5-20250929", max_tokens=8192)  # Increased for JSON
    dspy.configure(lm=lm)

    # Define signature with JSON output
    class StructuredExplorationSig(dspy.Signature):
        """Explore an ontology and produce a structured JSON guide.

        You have access to `ont` (an rdflib Graph) and rdflib namespaces (RDF, RDFS, OWL).
        Write Python code to explore: ont.triples(), ont.subjects(), ont.objects(), ont.value().
        """

        ont: object = dspy.InputField(desc="The loaded rdflib Graph object")
        rdf_imports: str = dspy.InputField(desc="Available rdflib imports info")

        guide_json: str = dspy.OutputField(
            desc="Structured JSON guide following the schema in the task description"
        )

    # Create interpreter
    from rlm_runtime.interpreter.namespace_interpreter import NamespaceCodeInterpreter

    interpreter = NamespaceCodeInterpreter(
        result_truncation_limit=15000  # Allow larger outputs for JSON
    )

    # Create RLM with tools that provide rdflib access
    tools = {
        'RDF': RDF,
        'RDFS': RDFS,
        'OWL': OWL,
        'Graph': Graph,
        'Namespace': Namespace,
    }

    rlm = dspy.RLM(
        StructuredExplorationSig,
        max_iterations=12,  # Allow more iterations for structured output
        max_llm_calls=6,
        verbose=True,
        interpreter=interpreter,
        tools=tools,
    )

    print("-" * 70)
    print("Running exploration...")
    print("-" * 70)
    print()

    # Prepare inputs with structured schema
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

## Optional: Use llm_query() for Semantic Analysis

If you find yourself needing to reason about WHY something matters or HOW concepts relate,
you can use llm_query() to help analyze semantic importance:

```python
# After collecting classes
importance = llm_query(f'''
I found these key classes: {class_names}
Analyze their semantic importance:
1. Which are core/foundational vs. supporting?
2. What domain concepts do they represent?
3. Why would these matter for querying?
''')
```

## Validation

After creating the JSON, validate that:
- All URIs exist in the ontology
- JSON is valid (use json.loads() to test)
- All required fields are present
- Semantic explanations are meaningful (not just structural descriptions)
"""

    # Run
    log_path = project_root / "experiments" / "ontology_exploration" / "e3_trajectory.jsonl"
    start_time = datetime.now()

    try:
        # Enable trajectory logging to file
        log_path.parent.mkdir(parents=True, exist_ok=True)
        log_file = open(log_path, 'w')

        def log_event(event_type: str, data: dict):
            """Log event to JSONL file."""
            event = {'timestamp': datetime.now().isoformat(), 'type': event_type, **data}
            log_file.write(json.dumps(event) + '\n')
            log_file.flush()

        log_event('experiment_start', {'experiment': 'e3_structured_materialization', 'ontology': str(ontology_path)})

        # Track token usage via DSPy's history
        result = rlm(ont=ont, rdf_imports=rdf_imports_info)
        elapsed = (datetime.now() - start_time).total_seconds()

        # Extract iteration count from result if available
        iteration_count = 0
        if hasattr(result, '_iterations'):
            iteration_count = result._iterations
        elif hasattr(result, 'completions') and result.completions:
            iteration_count = len(result.completions)

        log_event('experiment_end', {
            'elapsed_seconds': elapsed,
            'iterations': iteration_count
        })
        log_file.close()

        # Extract token usage from DSPy LM history
        total_input_tokens = 0
        total_output_tokens = 0
        lm_call_count = 0

        if hasattr(lm, 'history') and lm.history:
            lm_call_count = len(lm.history)
            for call in lm.history:
                if isinstance(call, dict):
                    usage = call.get('usage', {})
                    if isinstance(usage, dict):
                        total_input_tokens += usage.get('input_tokens', 0)
                        total_output_tokens += usage.get('output_tokens', 0)
                    else:
                        total_input_tokens += getattr(usage, 'input_tokens', 0)
                        total_output_tokens += getattr(usage, 'output_tokens', 0)
                elif hasattr(call, 'usage'):
                    usage = call.usage
                    total_input_tokens += getattr(usage, 'input_tokens', 0)
                    total_output_tokens += getattr(usage, 'output_tokens', 0)

        # Cost estimation (Sonnet 4.5 pricing)
        input_cost = (total_input_tokens / 1_000_000) * 3.0
        output_cost = (total_output_tokens / 1_000_000) * 15.0
        total_cost = input_cost + output_cost

        if lm_call_count == 0 or total_input_tokens == 0:
            print("WARNING: Token tracking failed. Using rough estimate based on output length.")
            estimated_tokens = len(result.guide_json or "") / 4
            total_input_tokens = int(estimated_tokens * 3)
            total_output_tokens = int(estimated_tokens)
            input_cost = (total_input_tokens / 1_000_000) * 3.0
            output_cost = (total_output_tokens / 1_000_000) * 15.0
            total_cost = input_cost + output_cost

        print()
        print("=" * 70)
        print("RESULTS")
        print("=" * 70)
        print(f"Time: {elapsed:.1f}s")
        print()

        print("--- Metrics ---")
        print(f"Iterations: {iteration_count if iteration_count > 0 else 'unknown'}")
        print(f"LM calls: {lm_call_count}")
        print(f"Input tokens: {total_input_tokens:,}")
        print(f"Output tokens: {total_output_tokens:,}")
        print(f"Total tokens: {total_input_tokens + total_output_tokens:,}")
        print(f"Estimated cost: ${total_cost:.4f}")
        if (total_input_tokens + total_output_tokens) > 0:
            print(f"Cost per token: ${total_cost / (total_input_tokens + total_output_tokens) * 1000:.6f}/K tokens")
        print()

        # Validate JSON
        print("--- JSON Validation ---")
        json_valid = False
        parsed_json = None
        try:
            parsed_json = json.loads(result.guide_json)
            json_valid = True
            print("✓ Valid JSON")
            print(f"  Keys: {list(parsed_json.keys())}")

            # Count elements
            if 'key_classes' in parsed_json:
                print(f"  Key classes: {len(parsed_json['key_classes'])}")
            if 'key_properties' in parsed_json:
                print(f"  Key properties: {len(parsed_json['key_properties'])}")
            if 'design_patterns' in parsed_json:
                print(f"  Design patterns: {len(parsed_json['design_patterns'])}")
            if 'query_patterns' in parsed_json:
                print(f"  Query patterns: {len(parsed_json['query_patterns'])}")

        except json.JSONDecodeError as e:
            print(f"✗ Invalid JSON: {e}")
            print(f"  Output length: {len(result.guide_json)} chars")
        print()

        # URI Grounding Validation (if JSON is valid)
        grounding_stats = {}
        if json_valid and parsed_json:
            print("--- URI Grounding Validation ---")

            # Collect all URIs from ontology
            ont_uris = set()
            for s, p, o in ont:
                ont_uris.add(str(s))
                ont_uris.add(str(p))
                if hasattr(o, '__str__') and str(o).startswith('http'):
                    ont_uris.add(str(o))

            print(f"Ontology contains {len(ont_uris)} unique URIs")

            # Check key_classes URIs
            if 'key_classes' in parsed_json:
                class_uris = [c.get('uri') for c in parsed_json['key_classes'] if 'uri' in c]
                valid_class_uris = [uri for uri in class_uris if uri in ont_uris]
                grounding_stats['key_classes_total'] = len(class_uris)
                grounding_stats['key_classes_valid'] = len(valid_class_uris)
                pct = (len(valid_class_uris) / len(class_uris) * 100) if class_uris else 0
                print(f"  Key classes: {len(valid_class_uris)}/{len(class_uris)} URIs valid ({pct:.1f}%)")

            # Check key_properties URIs
            if 'key_properties' in parsed_json:
                prop_uris = [p.get('uri') for p in parsed_json['key_properties'] if 'uri' in p]
                valid_prop_uris = [uri for uri in prop_uris if uri in ont_uris]
                grounding_stats['key_properties_total'] = len(prop_uris)
                grounding_stats['key_properties_valid'] = len(valid_prop_uris)
                pct = (len(valid_prop_uris) / len(prop_uris) * 100) if prop_uris else 0
                print(f"  Key properties: {len(valid_prop_uris)}/{len(prop_uris)} URIs valid ({pct:.1f}%)")

            # Check design_patterns URIs
            if 'design_patterns' in parsed_json:
                pattern_class_uris = []
                pattern_prop_uris = []
                for pattern in parsed_json['design_patterns']:
                    pattern_class_uris.extend(pattern.get('example_classes', []))
                    pattern_prop_uris.extend(pattern.get('example_properties', []))

                valid_pattern_class_uris = [uri for uri in pattern_class_uris if uri in ont_uris]
                valid_pattern_prop_uris = [uri for uri in pattern_prop_uris if uri in ont_uris]
                grounding_stats['pattern_classes_total'] = len(pattern_class_uris)
                grounding_stats['pattern_classes_valid'] = len(valid_pattern_class_uris)
                grounding_stats['pattern_properties_total'] = len(pattern_prop_uris)
                grounding_stats['pattern_properties_valid'] = len(valid_pattern_prop_uris)

                if pattern_class_uris:
                    pct = len(valid_pattern_class_uris) / len(pattern_class_uris) * 100
                    print(f"  Pattern example classes: {len(valid_pattern_class_uris)}/{len(pattern_class_uris)} valid ({pct:.1f}%)")
                if pattern_prop_uris:
                    pct = len(valid_pattern_prop_uris) / len(pattern_prop_uris) * 100
                    print(f"  Pattern example properties: {len(valid_pattern_prop_uris)}/{len(pattern_prop_uris)} valid ({pct:.1f}%)")

            # Overall grounding
            total_uris = sum([grounding_stats.get('key_classes_total', 0),
                            grounding_stats.get('key_properties_total', 0),
                            grounding_stats.get('pattern_classes_total', 0),
                            grounding_stats.get('pattern_properties_total', 0)])
            valid_uris = sum([grounding_stats.get('key_classes_valid', 0),
                            grounding_stats.get('key_properties_valid', 0),
                            grounding_stats.get('pattern_classes_valid', 0),
                            grounding_stats.get('pattern_properties_valid', 0)])
            if total_uris > 0:
                overall_pct = valid_uris / total_uris * 100
                print(f"\n  Overall URI grounding: {valid_uris}/{total_uris} ({overall_pct:.1f}%)")
                grounding_stats['overall_valid_pct'] = overall_pct
        print()

        # Preview output
        print("--- Guide JSON (first 2000 chars) ---")
        json_preview = result.guide_json[:2000] if result.guide_json else "(none)"
        print(json_preview)
        if result.guide_json and len(result.guide_json) > 2000:
            print(f"\n... ({len(result.guide_json) - 2000} more characters)")
        print()

        # Save full output to file
        output_path = project_root / "experiments" / "ontology_exploration" / "e3_output.json"
        with open(output_path, 'w') as f:
            f.write(result.guide_json or "{}")
        print(f"Full JSON saved to: {output_path}")

        # Save pretty-printed version if valid
        if json_valid and parsed_json:
            pretty_path = project_root / "experiments" / "ontology_exploration" / "e3_output_pretty.json"
            with open(pretty_path, 'w') as f:
                json.dump(parsed_json, f, indent=2)
            print(f"Pretty-printed JSON saved to: {pretty_path}")

        # Analyze what happened
        print("\n--- Analysis ---")

        # Check for llm_query usage
        if hasattr(interpreter, '_globals'):
            excluded = {'ont', 'Graph', 'RDF', 'RDFS', 'OWL', 'Namespace', 'SUBMIT', 'FINAL', 'FINAL_VAR',
                       'rdf_imports', '__builtins__', 'print', 'llm_query', 'llm_query_batched'}
            discovered_vars = [k for k in interpreter._globals.keys() if k not in excluded]
            print(f"Variables created during exploration: {len(discovered_vars)}")
            print(f"  Sample: {discovered_vars[:10]}")

            if 'understanding' in discovered_vars or 'synthesis' in discovered_vars or 'importance' in discovered_vars:
                print("Note: llm_query appears to have been used (found understanding/synthesis/importance variables)")

        # Save metrics to JSON
        num_vars = 0
        llm_query_detected = False
        if hasattr(interpreter, '_globals'):
            excluded = {'ont', 'Graph', 'RDF', 'RDFS', 'OWL', 'Namespace', 'SUBMIT', 'FINAL', 'FINAL_VAR',
                       'rdf_imports', '__builtins__', 'print', 'llm_query', 'llm_query_batched'}
            discovered_vars = [k for k in interpreter._globals.keys() if k not in excluded]
            num_vars = len(discovered_vars)
            llm_query_detected = any(v in discovered_vars for v in ['understanding', 'synthesis', 'importance'])

        metrics = {
            'experiment': 'e3_structured_materialization',
            'timestamp': datetime.now().isoformat(),
            'ontology': 'prov.ttl',
            'ontology_size': len(ont),
            'elapsed_seconds': elapsed,
            'iterations': iteration_count,
            'lm_calls': lm_call_count,
            'input_tokens': total_input_tokens,
            'output_tokens': total_output_tokens,
            'total_tokens': total_input_tokens + total_output_tokens,
            'estimated_cost_usd': total_cost,
            'token_tracking_method': 'dspy_history' if (lm_call_count > 0 and total_input_tokens > 0) else 'estimated',
            'variables_created': num_vars,
            'guide_json_length': len(result.guide_json) if result.guide_json else 0,
            'json_valid': json_valid,
            'llm_query_detected': llm_query_detected,
            'grounding_stats': grounding_stats,
        }

        metrics_path = project_root / "experiments" / "ontology_exploration" / "e3_metrics.json"
        metrics_path.parent.mkdir(parents=True, exist_ok=True)
        with open(metrics_path, 'w') as f:
            json.dump(metrics, f, indent=2)

        print()
        print(f"Metrics saved to: {metrics_path}")

        return True

    except Exception as e:
        print(f"ERROR: {e}")
        import traceback
        traceback.print_exc()
        return False


if __name__ == "__main__":
    success = run_e3()
    sys.exit(0 if success else 1)
