"""Experiment: Scratchpad approach for AGENT_GUIDE.md generation

This approach follows the original rlm/core.py design:
- Persistent namespace across iterations
- Direct function calls (no tool wrappers)
- Lightweight history (truncated)
- Agent builds up state in scratchpad
"""

import os
import json
from pathlib import Path
from datetime import datetime
from io import StringIO
import sys
import time

# Ensure API key is set
if not os.environ.get("ANTHROPIC_API_KEY"):
    raise ValueError("Set ANTHROPIC_API_KEY environment variable")


def approach_4_scratchpad(ontology_path: str, ontology_name: str) -> dict:
    """Generate AGENT_GUIDE via scratchpad model (original rlm/core.py style)."""
    from claudette import Chat, contents
    from functools import partial
    from rdflib import Graph
    from rlm.ontology import GraphMeta, search_entity as _search_entity
    import re

    # Load ontology
    g = Graph()
    g.parse(ontology_path)
    meta = GraphMeta(graph=g, name=ontology_name)

    # Create persistent namespace (scratchpad)
    ns = {}

    # Populate namespace with ontology data (Rails pattern - load upfront)
    ns['ontology_name'] = ontology_name
    ns['ontology_stats'] = meta.summary()
    ns['graph'] = meta.graph  # Direct access to graph
    ns['meta'] = meta  # Direct access to GraphMeta

    # Tool functions that work directly in namespace
    def search_entity(query: str, limit: int = 10):
        """Search for entities by label/IRI/localname."""
        results = _search_entity(meta, query, limit=min(10, max(1, limit)))
        return results

    def sparql_query(query: str):
        """Execute SPARQL query on ontology."""
        # Auto-inject LIMIT
        if 'LIMIT' not in query.upper():
            query = query.strip() + ' LIMIT 50'

        result_set = meta.graph.query(query)

        if not hasattr(result_set, 'vars'):
            return []

        results = [
            {str(var): str(row[i]) for i, var in enumerate(result_set.vars)}
            for row in result_set
        ]
        return results[:50]

    def get_classes(limit: int = 50):
        """Get all classes in ontology."""
        query = """
        PREFIX owl: <http://www.w3.org/2002/07/owl#>
        PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>

        SELECT ?class ?label ?comment WHERE {
            ?class a owl:Class .
            OPTIONAL { ?class rdfs:label ?label }
            OPTIONAL { ?class rdfs:comment ?comment }
        }
        """
        return sparql_query(query)[:limit]

    def get_properties(limit: int = 50):
        """Get all properties in ontology."""
        query = """
        PREFIX owl: <http://www.w3.org/2002/07/owl#>
        PREFIX rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#>
        PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>

        SELECT ?prop ?label ?domain ?range WHERE {
            { ?prop a owl:ObjectProperty }
            UNION
            { ?prop a owl:DatatypeProperty }
            UNION
            { ?prop a rdf:Property }
            OPTIONAL { ?prop rdfs:label ?label }
            OPTIONAL { ?prop rdfs:domain ?domain }
            OPTIONAL { ?prop rdfs:range ?range }
        }
        """
        return sparql_query(query)[:limit]

    def llm_query(prompt: str, name: str = 'llm_res', model: str = 'claude-sonnet-4-20250514'):
        """Query sub-LLM and store result in namespace."""
        result = contents(Chat(model)(prompt))
        ns[name] = result
        return result

    # Add functions to namespace
    ns['search_entity'] = search_entity
    ns['sparql_query'] = sparql_query
    ns['get_classes'] = get_classes
    ns['get_properties'] = get_properties
    ns['llm_query'] = partial(llm_query, model='claude-sonnet-4-20250514')

    # System prompt (adapted from rlm/core.py)
    system_prompt = """You are generating an AGENT_GUIDE.md for an ontology using an interactive REPL environment.

The REPL environment is initialized with:
1. Ontology metadata in the `ontology_name` and `ontology_stats` variables
2. Direct access to the ontology via `graph` (RDFLib Graph) and `meta` (GraphMeta)
3. Helper functions:
   - `search_entity(query, limit)` - Search for entities by name
   - `sparql_query(query)` - Execute SPARQL queries (auto-adds LIMIT 50)
   - `get_classes(limit)` - Get all classes with labels/comments
   - `get_properties(limit)` - Get all properties with domains/ranges
   - `llm_query(prompt, name)` - Query a sub-LLM for analysis/summarization
4. The ability to use `print()` to view outputs and build up your understanding

WORKFLOW - Follow this incremental assembly pattern:

**Step 1: Explore (1-2 iterations)**
```repl
# Get ontology structure
classes = get_classes(limit=20)
props = get_properties(limit=20)
print(f"Found {len(classes)} classes, {len(props)} properties")
```

**Step 2: Analyze with sub-LLM (2-3 iterations)**
```repl
# Use llm_query to analyze chunks
overview = llm_query(f"Based on these classes: {classes[:10]}, write a 2-sentence overview of what this ontology is for", "overview")
print(f"Overview: {overview[:100]}...")

core_classes = llm_query(f"From these classes: {classes}, identify the 3-5 most important core classes and explain when to use them", "core_classes")
```

**Step 3: Assemble guide (1 iteration)**
```repl
# Combine sections into markdown
guide_markdown = f'''# {ontology_name.upper()} Ontology Agent Guide

## Overview
{overview}

## Core Classes
{core_classes}

## Key Properties
{key_properties}

## Query Patterns
{query_patterns}

## Quick Reference
{quick_ref}
'''
print(f"Guide assembled: {len(guide_markdown)} chars")
```

**Step 4: FINISH - Use FINAL_VAR**
FINAL_VAR(guide_markdown)

IMPORTANT: You have a maximum of 8 iterations. Plan to:
- Iterations 1-2: Explore and gather data
- Iterations 3-5: Analyze with llm_query, build sections
- Iteration 6-7: Assemble final guide markdown
- Iteration 7-8: Call FINAL_VAR(guide_markdown)

Your goal is to generate an AGENT_GUIDE.md with these sections:
1. Overview - What the ontology is for (2-3 sentences)
2. Core Classes - Main classes with when/why to use them
3. Key Properties - Important properties with usage patterns
4. Query Patterns - 3-5 practical SPARQL examples
5. Important Considerations - Gotchas and tips
6. Quick Reference - Compact cheat sheet

When you execute code in ```repl``` blocks, results are stored in the namespace and persist across iterations.
You can reference variables from previous iterations.

BE EFFICIENT: Don't over-explore. Gather what you need, analyze it, assemble the guide, and FINISH with FINAL_VAR.
"""

    # Initial user prompt
    first_prompt = f"""Generate an AGENT_GUIDE.md for the {ontology_name} ontology.

ITERATION 1/8: Start by exploring the ontology structure.

Follow the workflow:
1. Check `ontology_stats` to understand size
2. Get classes and properties with get_classes() and get_properties()
3. Print what you found

Your next action:"""

    # Helper to execute code
    def exec_code(code: str):
        """Execute code in namespace and capture output."""
        stdout_capture = StringIO()
        stderr_capture = StringIO()
        old_stdout, old_stderr = sys.stdout, sys.stderr

        try:
            sys.stdout, sys.stderr = stdout_capture, stderr_capture
            exec(compile(code, '<repl>', 'exec'), ns)
            stderr_out = stderr_capture.getvalue()
        except Exception as e:
            stderr_out = stderr_capture.getvalue() + f"\n{type(e).__name__}: {e}"
        finally:
            sys.stdout, sys.stderr = old_stdout, old_stderr

        return stdout_capture.getvalue(), stderr_out

    # Helper to find code blocks
    def find_code_blocks(text: str):
        """Extract ```repl``` code blocks."""
        pattern = r"```repl\s*\n(.*?)\n```"
        return [match.group(1).strip() for match in re.finditer(pattern, text, re.DOTALL)]

    # Add FINAL_VAR to namespace so it can be called in code blocks
    def FINAL_VAR(var_or_value):
        """Mark completion with final value."""
        # Store in special variable
        ns['__FINAL_ANSWER__'] = var_or_value
        return var_or_value

    ns['FINAL_VAR'] = FINAL_VAR

    # Helper to find FINAL_VAR
    def find_final_var(text: str):
        """Extract FINAL_VAR(variable_name) or check namespace for __FINAL_ANSWER__."""
        # Check if FINAL_VAR was called in code (stored in __FINAL_ANSWER__)
        if '__FINAL_ANSWER__' in ns:
            return str(ns['__FINAL_ANSWER__'])

        # Check for FINAL_VAR in text
        match = re.search(r'FINAL_VAR\(([^)]+)\)', text)
        if match:
            var_name = match.group(1).strip().strip('"').strip("'")
            if var_name in ns:
                return str(ns[var_name])
        return None

    # Run loop
    chat = Chat('claude-sonnet-4-20250514', sp=system_prompt)
    max_iters = 8
    start_time = datetime.now()

    iterations = []

    for i in range(max_iters):
        # Get response with iteration-aware prompts
        if i == 0:
            prompt = first_prompt
        elif i <= 2:
            # Exploration phase
            prompt = f"""ITERATION {i+1}/8: Continue exploring.

Use get_classes() and get_properties() to gather data.
Store interesting findings in variables.

Your next action:"""
        elif i <= 5:
            # Analysis phase
            prompt = f"""ITERATION {i+1}/8: Analyze and build sections.

Use llm_query() to analyze the data you gathered and create guide sections:
- overview (2-3 sentences)
- core_classes (main classes with when/why to use)
- key_properties (important properties with usage patterns)
- query_patterns (SPARQL examples)

Your next action:"""
        else:
            # Assembly phase
            namespace_vars = [k for k in ns.keys() if not k.startswith('_') and k not in ['ontology_name', 'ontology_stats', 'graph', 'meta', 'search_entity', 'sparql_query', 'get_classes', 'get_properties', 'llm_query']]
            prompt = f"""ITERATION {i+1}/8: {'FINAL ITERATION - ' if i == max_iters - 1 else ''}Assemble and FINISH.

Variables in namespace: {namespace_vars}

NOW:
1. Combine your sections into a guide_markdown variable
2. Call FINAL_VAR(guide_markdown) to finish

Example:
```repl
guide_markdown = f'''# {ontology_name.upper()} Agent Guide
{{overview}}
{{core_classes}}
...
'''
FINAL_VAR(guide_markdown)
```

Your next action:"""

        response = contents(chat(prompt))

        # Execute code blocks
        code_blocks = find_code_blocks(response)
        outputs = []

        for code in code_blocks:
            stdout, stderr = exec_code(code)
            output = f"STDOUT:\n{stdout}\n\nSTDERR:\n{stderr}" if stderr else stdout
            outputs.append(output)

            # Add execution result to chat (truncated)
            truncated = output[:20000] if len(output) > 20000 else output
            chat.h.append({
                "role": "user",
                "content": f"Code executed:\n```python\n{code}\n```\n\nREPL output:\n{truncated}"
            })

        iterations.append({
            "iteration": i + 1,
            "response": response,
            "code_blocks": len(code_blocks),
            "namespace_vars": list(ns.keys())
        })

        # Check for FINAL_VAR
        final_answer = find_final_var(response)
        if final_answer:
            elapsed = (datetime.now() - start_time).total_seconds()
            return {
                "approach": "scratchpad",
                "ontology": ontology_name,
                "elapsed_seconds": elapsed,
                "iterations": i + 1,
                "namespace_vars": len([k for k in ns.keys() if not k.startswith('_')]),
                "guide": final_answer
            }

    # Fallback: try to construct guide from namespace variables
    elapsed = (datetime.now() - start_time).total_seconds()

    # Look for common variable names
    for var in ['guide_markdown', 'guide', 'final_guide', 'agent_guide', 'markdown', 'complete_guide', 'full_guide']:
        if var in ns and isinstance(ns[var], str) and len(str(ns[var])) > 500:
            return {
                "approach": "scratchpad",
                "ontology": ontology_name,
                "elapsed_seconds": elapsed,
                "iterations": max_iters,
                "namespace_vars": len([k for k in ns.keys() if not k.startswith('_')]),
                "guide": str(ns[var]),
                "fallback": f"Used {var} from namespace (FINAL_VAR not called)"
            }

    # Try to assemble from section variables
    sections = {}
    for var in ['overview', 'core_classes', 'key_properties', 'query_patterns', 'important_considerations', 'quick_reference']:
        if var in ns:
            sections[var] = str(ns[var])

    if len(sections) >= 3:
        # Assemble from sections
        assembled = f"# {ontology_name.upper()} Ontology Agent Guide\n\n"
        if 'overview' in sections:
            assembled += f"## Overview\n{sections['overview']}\n\n"
        if 'core_classes' in sections:
            assembled += f"## Core Classes\n{sections['core_classes']}\n\n"
        if 'key_properties' in sections:
            assembled += f"## Key Properties\n{sections['key_properties']}\n\n"
        if 'query_patterns' in sections:
            assembled += f"## Query Patterns\n{sections['query_patterns']}\n\n"
        if 'important_considerations' in sections:
            assembled += f"## Important Considerations\n{sections['important_considerations']}\n\n"
        if 'quick_reference' in sections:
            assembled += f"## Quick Reference\n{sections['quick_reference']}\n\n"

        return {
            "approach": "scratchpad",
            "ontology": ontology_name,
            "elapsed_seconds": elapsed,
            "iterations": max_iters,
            "namespace_vars": len([k for k in ns.keys() if not k.startswith('_')]),
            "guide": assembled,
            "fallback": f"Assembled from {len(sections)} section variables"
        }

    # Ultimate fallback
    return {
        "approach": "scratchpad",
        "ontology": ontology_name,
        "elapsed_seconds": elapsed,
        "iterations": max_iters,
        "namespace_vars": len([k for k in ns.keys() if not k.startswith('_')]),
        "guide": "[Max iterations] No complete guide generated",
        "error": "No FINAL_VAR found and no guide in namespace"
    }


def run_scratchpad_experiment(ontology_path: str, ontology_name: str, output_dir: str = "experiments/results"):
    """Run scratchpad approach and save results."""

    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

    print(f"\n{'='*60}")
    print(f"Approach 4: Scratchpad for {ontology_name}")
    print(f"{'='*60}")

    try:
        result = approach_4_scratchpad(ontology_path, ontology_name)

        # Save guide
        guide_path = output_path / f"{ontology_name}_AGENT_GUIDE_scratchpad_{timestamp}.md"
        guide_path.write_text(result["guide"])
        print(f"Saved: {guide_path}")
        print(f"Elapsed: {result['elapsed_seconds']:.1f}s")
        print(f"Iterations: {result['iterations']}")
        print(f"Namespace vars: {result['namespace_vars']}")
        if 'fallback' in result:
            print(f"Fallback: {result['fallback']}")
        if 'error' in result:
            print(f"Error: {result['error']}")

        # Save metadata
        metadata_path = output_path / f"{ontology_name}_scratchpad_metadata_{timestamp}.json"
        with open(metadata_path, "w") as f:
            metadata = {k: v for k, v in result.items() if k != "guide"}
            json.dump(metadata, f, indent=2)

        return result

    except Exception as e:
        print(f"Error in Scratchpad: {e}")
        import traceback
        traceback.print_exc()
        return {"error": str(e)}


if __name__ == "__main__":
    import sys

    # Default to PROV
    if len(sys.argv) > 1:
        ontology_name = sys.argv[1]
        ontology_path = sys.argv[2] if len(sys.argv) > 2 else f"ontology/{ontology_name}.ttl"
    else:
        ontology_name = "prov"
        ontology_path = "ontology/prov.ttl"

    print(f"Running Scratchpad experiment for: {ontology_name}")
    print(f"Ontology path: {ontology_path}")

    result = run_scratchpad_experiment(ontology_path, ontology_name)

    if "error" not in result:
        print(f"\n{'='*60}")
        print("Success!")
        print(f"Guide length: {len(result['guide'])} chars")
        print(f"{'='*60}")
