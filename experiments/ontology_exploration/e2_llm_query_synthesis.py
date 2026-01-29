#!/usr/bin/env python3
"""E2: llm_query Synthesis - Does explicit guidance trigger llm_query usage?

Hypothesis: With guidance to use llm_query for synthesis, the model will use it
more strategically to understand ontology semantics.

Setup:
- Load PROV ontology (same as E1)
- Add explicit guidance: "Use llm_query() to synthesize understanding"
- Track llm_query usage

Measure:
- Number of llm_query calls
- What prompts are sent to llm_query?
- Does synthesis improve vs E1?
- Cost comparison

Usage:
    source ~/uvws/.venv/bin/activate
    python experiments/ontology_exploration/e2_llm_query_synthesis.py
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


def run_e2():
    """Run E2: llm_query Synthesis experiment."""
    import dspy
    from rdflib import Graph, RDF, RDFS, OWL, Namespace

    print("\n" + "=" * 70)
    print("E2: LLM_QUERY SYNTHESIS")
    print("=" * 70)
    print(f"Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print()

    # Load PROV ontology
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
    lm = dspy.LM("anthropic/claude-sonnet-4-5-20250929", max_tokens=4096)
    dspy.configure(lm=lm)

    # Define simple signature - pass graph as input
    class ExplorationSig(dspy.Signature):
        """Explore an ontology and describe its structure.

        You have access to `ont` (an rdflib Graph) and rdflib namespaces (RDF, RDFS, OWL).
        Write Python code to explore: ont.triples(), ont.subjects(), ont.objects(), ont.value().
        """

        ont: object = dspy.InputField(desc="The loaded rdflib Graph object")
        rdf_imports: str = dspy.InputField(desc="Available rdflib imports info")

        exploration_notes: str = dspy.OutputField(
            desc="What you discovered about the ontology through exploration"
        )
        domain_summary: str = dspy.OutputField(
            desc="What is this ontology about? Main concepts and purpose."
        )

    # Create interpreter
    from rlm_runtime.interpreter.namespace_interpreter import NamespaceCodeInterpreter

    interpreter = NamespaceCodeInterpreter(
        result_truncation_limit=10000
    )

    # Create RLM with tools that provide rdflib access
    # Pass rdflib classes as tools so they're available in namespace
    tools = {
        'RDF': RDF,
        'RDFS': RDFS,
        'OWL': OWL,
        'Graph': Graph,
        'Namespace': Namespace,
    }

    rlm = dspy.RLM(
        ExplorationSig,
        max_iterations=10,
        max_llm_calls=5,
        verbose=True,
        interpreter=interpreter,
        tools=tools,
    )

    print("-" * 70)
    print("Running exploration...")
    print("-" * 70)
    print()

    # Prepare inputs
    rdf_imports_info = """## Your Task
Explore this ontology and describe what you find:
1. How many triples? What namespaces are used?
2. What classes are defined? What are their labels?
3. What properties exist? What do they connect?
4. How do classes relate (subclass hierarchy)?

## Available in Namespace
- RDF, RDFS, OWL - Standard rdflib namespaces (e.g., RDF.type, RDFS.label, OWL.Class)
- Graph, Namespace - rdflib classes

## Common Patterns
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

# Get all namespaces
for prefix, ns in ont.namespaces():
    print(f"  {prefix}: {ns}")
```

Print what you discover. Build understanding of what this ontology models.

## IMPORTANT: Use llm_query() for Semantic Synthesis

After exploring the ontology structure (classes, properties, hierarchies), use `llm_query()` to synthesize understanding:

```python
# Example: After collecting classes and properties
understanding = llm_query(f'''
Based on exploring this ontology, I found:
- {len(classes)} classes: {[labels for first 10]}
- {len(properties)} properties: {[labels for first 10]}
- Hierarchy patterns: {describe patterns}

Questions:
1. What is this ontology's main purpose and domain?
2. What are the key concepts and how do they relate?
3. What design patterns are used?
''')
```

llm_query() helps you understand SEMANTICS (what things mean), not just STRUCTURE (what exists).
Use it to synthesize insights after exploration."""

    # Run
    log_path = project_root / "experiments" / "ontology_exploration" / "e2_trajectory.jsonl"
    start_time = datetime.now()

    try:
        # Enable trajectory logging to file
        log_path.parent.mkdir(parents=True, exist_ok=True)
        log_file = open(log_path, 'w')

        def log_event(event_type: str, data: dict):
            """Log event to JSONL file."""
            import json
            event = {'timestamp': datetime.now().isoformat(), 'type': event_type, **data}
            log_file.write(json.dumps(event) + '\n')
            log_file.flush()

        log_event('experiment_start', {'experiment': 'e2_llm_query_synthesis', 'ontology': str(ontology_path)})

        # Track token usage via DSPy's history
        # DSPy stores LM call history in the LM object
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

        # DSPy LM keeps history in lm.history
        if hasattr(lm, 'history') and lm.history:
            lm_call_count = len(lm.history)
            for call in lm.history:
                # Each call might be a dict or object
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
        # $3 per million input tokens, $15 per million output tokens
        input_cost = (total_input_tokens / 1_000_000) * 3.0
        output_cost = (total_output_tokens / 1_000_000) * 15.0
        total_cost = input_cost + output_cost

        # Note: If token tracking failed (no history), use rough estimate
        if lm_call_count == 0 or total_input_tokens == 0:
            print("WARNING: Token tracking failed. Using rough estimate based on output length.")
            # Rough estimate: ~4 chars per token
            estimated_tokens = (len(result.exploration_notes or "") + len(result.domain_summary or "")) / 4
            total_input_tokens = int(estimated_tokens * 3)  # Input usually 3x output
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

        print("--- Exploration Notes ---")
        notes_preview = result.exploration_notes[:2000] if result.exploration_notes else "(none)"
        print(notes_preview)
        if result.exploration_notes and len(result.exploration_notes) > 2000:
            print(f"\n... ({len(result.exploration_notes) - 2000} more characters)")
        print()

        print("--- Domain Summary ---")
        summary_preview = result.domain_summary[:1000] if result.domain_summary else "(none)"
        print(summary_preview)
        if result.domain_summary and len(result.domain_summary) > 1000:
            print(f"\n... ({len(result.domain_summary) - 1000} more characters)")
        print()

        # Save full output to file for analysis
        output_path = project_root / "experiments" / "ontology_exploration" / "e2_output.txt"
        with open(output_path, 'w') as f:
            f.write("=== EXPLORATION NOTES ===\n\n")
            f.write(result.exploration_notes or "(none)")
            f.write("\n\n=== DOMAIN SUMMARY ===\n\n")
            f.write(result.domain_summary or "(none)")
        print(f"Full output saved to: {output_path}")

        # Analyze what happened
        print("--- Analysis ---")

        # Check for llm_query usage in the execution
        llm_query_calls = 0
        code_blocks = 0
        if hasattr(interpreter, '_globals'):
            # Filter out built-ins and tools
            excluded = {'ont', 'Graph', 'RDF', 'RDFS', 'OWL', 'Namespace', 'SUBMIT', 'FINAL', 'FINAL_VAR',
                       'rdf_imports', '__builtins__', 'print', 'llm_query', 'llm_query_batched'}
            discovered_vars = [k for k in interpreter._globals.keys() if k not in excluded]
            print(f"Variables created during exploration: {discovered_vars[:20]}")

            # Try to detect llm_query usage from variables or output
            if 'understanding' in discovered_vars or 'synthesis' in discovered_vars:
                print("Note: llm_query appears to have been used (found understanding/synthesis variables)")

        # Try to access execution history from result
        if hasattr(result, '_trace') or hasattr(result, 'history'):
            trace = getattr(result, '_trace', getattr(result, 'history', None))
            if trace:
                print(f"Execution trace available: {len(trace)} steps")

        # Save metrics to JSON
        import json

        # Count discovered variables
        num_vars = 0
        if hasattr(interpreter, '_globals'):
            excluded = {'ont', 'Graph', 'RDF', 'RDFS', 'OWL', 'Namespace', 'SUBMIT', 'FINAL', 'FINAL_VAR',
                       'rdf_imports', '__builtins__', 'print', 'llm_query', 'llm_query_batched'}
            discovered_vars = [k for k in interpreter._globals.keys() if k not in excluded]
            num_vars = len(discovered_vars)

        metrics = {
            'experiment': 'e2_llm_query_synthesis',
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
            'exploration_notes_length': len(result.exploration_notes) if result.exploration_notes else 0,
            'domain_summary_length': len(result.domain_summary) if result.domain_summary else 0,
            'llm_query_detected': ('understanding' in (discovered_vars if num_vars > 0 else [])),
        }

        metrics_path = project_root / "experiments" / "ontology_exploration" / "e2_metrics.json"
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
    success = run_e2()
    sys.exit(0 if success else 1)
