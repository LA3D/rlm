#!/usr/bin/env python3
"""Generate AGENT_GUIDE.md for an ontology using scratchpad approach.

This script uses the scratchpad model (original rlm/core.py design) to generate
comprehensive agent guides through:
- Persistent namespace with rich metadata
- Direct function calls (no tool wrappers)
- Sub-LLM analysis via llm_query()
- Incremental assembly

Usage:
    python scripts/generate_agent_guide.py ontology/prov.ttl
    python scripts/generate_agent_guide.py ontology/dul/DUL.ttl --output ontology/dul/AGENT_GUIDE.md
"""

import os
import sys
import argparse
from pathlib import Path
from datetime import datetime
from functools import partial

# Enable unbuffered output
sys.stdout.reconfigure(line_buffering=True)
sys.stderr.reconfigure(line_buffering=True)

# Ensure we're in the project root
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

# Check API key
if not os.environ.get("ANTHROPIC_API_KEY"):
    print("ERROR: Set ANTHROPIC_API_KEY environment variable", flush=True)
    sys.exit(1)


def generate_agent_guide(ontology_path: str, output_path: str = None, ontology_name: str = None) -> str:
    """Generate AGENT_GUIDE.md via scratchpad model.

    Args:
        ontology_path: Path to ontology file (.ttl, .rdf, .owl)
        output_path: Where to save the guide (default: same dir as ontology)
        ontology_name: Short name for ontology (default: filename stem)

    Returns:
        Path to generated guide
    """
    from claudette import Chat, contents
    from rdflib import Graph
    from rlm.ontology import GraphMeta, search_entity as _search_entity
    import re

    ontology_path = Path(ontology_path)
    if not ontology_path.exists():
        raise FileNotFoundError(f"Ontology not found: {ontology_path}")

    # Determine ontology name
    if ontology_name is None:
        ontology_name = ontology_path.stem

    # Determine output path
    if output_path is None:
        if ontology_path.parent.is_dir() and ontology_path.parent.name != "ontology":
            # e.g., ontology/dul/DUL.ttl -> ontology/dul/AGENT_GUIDE.md
            output_path = ontology_path.parent / "AGENT_GUIDE.md"
        else:
            # e.g., ontology/prov.ttl -> ontology/prov/AGENT_GUIDE.md
            output_dir = ontology_path.parent / ontology_name
            output_dir.mkdir(exist_ok=True)
            output_path = output_dir / "AGENT_GUIDE.md"
    else:
        output_path = Path(output_path)

    print(f"Generating AGENT_GUIDE.md for {ontology_name}")
    print(f"  Source: {ontology_path}")
    print(f"  Output: {output_path}")

    # Load ontology
    print("Loading ontology...")
    g = Graph()
    g.parse(ontology_path)
    meta = GraphMeta(graph=g, name=ontology_name)
    print(f"  Loaded {len(g)} triples")

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

        try:
            result_set = meta.graph.query(query)
        except Exception as e:
            return f"Query error: {e}"

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

    # System prompt (adapted from experiments/agent_guide_generation/agent_guide_scratchpad.py)
    system_prompt = f"""You are generating an AGENT_GUIDE.md for the {ontology_name} ontology using an interactive REPL environment.

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
print(f"Found {{len(classes)}} classes, {{len(props)}} properties")
```

**Step 2: Analyze with sub-LLM (2-3 iterations)**
```repl
# Use llm_query to analyze chunks
overview = llm_query(f"Based on these classes: {{classes[:10]}}, write a 2-sentence overview of what this ontology is for", "overview")
print(f"Overview: {{overview[:100]}}...")

core_classes = llm_query(f"From these classes: {{classes}}, identify the 3-5 most important core classes and explain when to use them", "core_classes")
```

**Step 3: Assemble guide (1 iteration)**
```repl
# Combine sections into markdown
guide_markdown = f'''# {{ontology_name.upper()}} Ontology Agent Guide

## Overview
{{overview}}

## Core Classes
{{core_classes}}

## Key Properties
{{key_properties}}

## Query Patterns
{{query_patterns}}

## Quick Reference
{{quick_ref}}
'''
print(f"Guide assembled: {{len(guide_markdown)}} chars")
```

**Step 4: FINISH - Use FINAL_VAR**
FINAL_VAR(guide_markdown)

IMPORTANT: You have a maximum of 10 iterations. Plan to:
- Iterations 1-2: Explore and gather data
- Iterations 3-6: Analyze with llm_query, build sections
- Iteration 7-9: Assemble final guide markdown
- Iteration 10: Call FINAL_VAR(guide_markdown)

Your goal is to generate an AGENT_GUIDE.md with these sections:
1. **Overview** - What the ontology is for (2-3 sentences)
2. **Core Classes** - Main classes with when/why to use them
3. **Key Properties** - Important properties with domain/range and usage patterns
4. **Query Patterns** - 3-5 practical SPARQL examples
5. **Important Considerations** - Gotchas, tips, anti-patterns
6. **Quick Reference** - Compact cheat sheet of most important URIs

When you execute code in ```repl``` blocks, results are stored in the namespace and persist across iterations.
You can reference variables from previous iterations.

BE EFFICIENT: Don't over-explore. Gather what you need, analyze it, assemble the guide, and FINISH with FINAL_VAR.
"""

    # Initial user prompt
    first_prompt = f"""Generate an AGENT_GUIDE.md for the {ontology_name} ontology.

ITERATION 1/10: Start by exploring the ontology structure.

Follow the workflow:
1. Check `ontology_stats` to understand size
2. Get classes and properties
3. Use llm_query() to analyze what you find
4. Build sections incrementally
5. Assemble final markdown
6. Call FINAL_VAR(guide_markdown) when done

Remember: You have 10 iterations total. Be strategic about exploration vs assembly."""

    # Execute REPL loop
    print("\nGenerating guide (this may take 2-3 minutes)...")
    chat = Chat(model='claude-sonnet-4-20250514', sp=system_prompt)

    max_iterations = 10
    iteration = 0
    final_output = None
    history_lines = []

    while iteration < max_iterations:
        iteration += 1
        print(f"  Iteration {iteration}/{max_iterations}")

        # Get response
        if iteration == 1:
            response = chat(first_prompt)
        else:
            # Provide lightweight history (truncated to avoid bloat)
            history_summary = "\n".join(history_lines[-20:])  # Last 20 lines
            response = chat(f"ITERATION {iteration}/{max_iterations}: Continue.\n\nRecent history:\n{history_summary}")

        # Extract and execute code blocks
        response_text = contents(response)

        # Look for FINAL_VAR call
        if 'FINAL_VAR(' in response_text:
            # Extract the variable passed to FINAL_VAR
            import re
            match = re.search(r'FINAL_VAR\(([^)]+)\)', response_text)
            if match:
                var_name = match.group(1).strip()
                if var_name in ns:
                    final_output = ns[var_name]
                    print(f"  ✓ Guide completed via FINAL_VAR({var_name})")
                    break

        # Execute code blocks
        code_blocks = re.findall(r'```(?:repl|python)\n(.*?)```', response_text, re.DOTALL)
        for code in code_blocks:
            try:
                # Capture output
                from io import StringIO
                import sys
                old_stdout = sys.stdout
                sys.stdout = captured_output = StringIO()

                # Execute in namespace
                exec(code, ns)

                # Restore stdout
                sys.stdout = old_stdout
                output = captured_output.getvalue()

                if output:
                    history_lines.append(f"[Iteration {iteration} output]: {output[:200]}")

            except Exception as e:
                sys.stdout = old_stdout
                history_lines.append(f"[Iteration {iteration} error]: {str(e)[:100]}")

        # Check if guide_markdown was created
        if 'guide_markdown' in ns and final_output is None:
            # Agent may have created guide without calling FINAL_VAR
            if iteration >= 8:  # Give them some leeway
                final_output = ns['guide_markdown']
                print(f"  ✓ Guide found in namespace (guide_markdown)")
                break

    if final_output is None:
        raise RuntimeError("Failed to generate guide - agent did not produce final output")

    # Write output
    print(f"\nSaving guide to {output_path}")
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(final_output)

    print(f"✓ Generated {len(final_output)} character guide in {iteration} iterations")
    return str(output_path)


def main():
    parser = argparse.ArgumentParser(
        description="Generate AGENT_GUIDE.md for an ontology",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python scripts/generate_agent_guide.py ontology/prov.ttl
  python scripts/generate_agent_guide.py ontology/dul/DUL.ttl --name dul
  python scripts/generate_agent_guide.py ontology/prov.ttl --output custom/path/guide.md
        """
    )
    parser.add_argument('ontology', help='Path to ontology file (.ttl, .rdf, .owl)')
    parser.add_argument('--output', '-o', help='Output path for AGENT_GUIDE.md')
    parser.add_argument('--name', '-n', help='Short name for ontology (default: filename stem)')

    args = parser.parse_args()

    try:
        guide_path = generate_agent_guide(args.ontology, args.output, args.name)
        print(f"\n✓ Success! Guide saved to: {guide_path}")
    except Exception as e:
        print(f"\n✗ Error: {e}", file=sys.stderr)
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == '__main__':
    main()
