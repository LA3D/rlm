"""Experiment: Compare all three approaches for generating AGENT_GUIDE.md

Three approaches:
1. Direct LLM - Full ontology in single prompt
2. RLM-based - Iterative exploration with REPL recursion
3. DSPy ReAct - Tool-based exploration, structured but non-recursive

This combines all approaches and generates a comprehensive comparison.
"""

import os
import json
from pathlib import Path
from datetime import datetime

# Ensure API key is set
if not os.environ.get("ANTHROPIC_API_KEY"):
    raise ValueError("Set ANTHROPIC_API_KEY environment variable")


def load_ontology_content(path: str, max_chars: int = 50000) -> str:
    """Load ontology file content, truncated if needed."""
    content = Path(path).read_text()
    if len(content) > max_chars:
        content = content[:max_chars] + f"\n\n... [truncated, {len(content)} total chars]"
    return content


def approach_1_direct_llm(ontology_path: str, ontology_name: str) -> dict:
    """Generate AGENT_GUIDE via direct LLM instruction (single prompt)."""
    import anthropic

    client = anthropic.Anthropic()

    ontology_content = load_ontology_content(ontology_path)

    prompt = f"""You are generating an AGENT_GUIDE.md for an ontology. This guide helps AI agents
understand HOW to use this ontology, not just WHAT's in it.

## Ontology: {ontology_name}
## Content:
```turtle
{ontology_content}
```

Generate an AGENT_GUIDE.md with these sections:

1. **Overview** - What is this ontology for? (2-3 sentences)

2. **Core Classes** - List the main classes with:
   - Full URI
   - Human-readable description of what it represents
   - When/why an agent would use this class

3. **Key Properties** - List important properties with:
   - Full URI
   - Domain and range
   - Usage pattern (how to use it in SPARQL)

4. **Query Patterns** - 3-5 SPARQL query templates for common tasks:
   - Finding entities of a type
   - Following relationships
   - Common joins/patterns specific to this ontology

5. **Important Considerations** - Gotchas, tips, things an agent should know:
   - Is hierarchy materialized or computed?
   - What properties are most useful for navigation?
   - Any patterns that might be non-obvious?

6. **Quick Reference** - A compact cheat sheet of the most important URIs

CRITICAL: Only use URIs that actually appear in the ontology content above.
CRITICAL: Make query patterns syntactically valid SPARQL.
"""

    start_time = datetime.now()

    response = client.messages.create(
        model="claude-sonnet-4-20250514",
        max_tokens=4096,
        messages=[{"role": "user", "content": prompt}]
    )

    elapsed = (datetime.now() - start_time).total_seconds()

    guide_content = response.content[0].text

    return {
        "approach": "direct_llm",
        "ontology": ontology_name,
        "elapsed_seconds": elapsed,
        "input_tokens": response.usage.input_tokens,
        "output_tokens": response.usage.output_tokens,
        "guide": guide_content
    }


def approach_2_rlm_based(ontology_path: str, ontology_name: str) -> dict:
    """Generate AGENT_GUIDE via RLM iterative exploration."""
    import dspy
    from rdflib import Graph
    from rlm.ontology import GraphMeta
    from rlm_runtime.interpreter import NamespaceCodeInterpreter
    from rlm_runtime.tools.ontology_tools import make_search_entity_tool, make_sparql_select_tool

    # Configure DSPy
    dspy.configure(
        lm=dspy.LM("anthropic/claude-sonnet-4-20250514", temperature=0.2, max_tokens=4096, cache=False)
    )
    sub_lm = dspy.LM("anthropic/claude-3-5-haiku-20241022", temperature=0.2, max_tokens=2048, cache=False)

    # Load ontology
    g = Graph()
    g.parse(ontology_path)
    meta = GraphMeta(graph=g, name=ontology_name)

    # Create tools
    tools = {
        'search_entity': make_search_entity_tool(meta),
        'sparql_select': make_sparql_select_tool(meta)
    }

    # Define signature for guide generation
    class AgentGuideGenerator(dspy.Signature):
        """Generate an AGENT_GUIDE.md by exploring the ontology with tools.

        Explore the ontology systematically:
        1. Search for main classes and understand their purpose
        2. Find key properties and their domains/ranges
        3. Identify common patterns and relationships
        4. Generate practical SPARQL examples
        """

        ontology_name: str = dspy.InputField(desc="Name of the ontology")
        ontology_stats: str = dspy.InputField(desc="Basic stats about the ontology")

        agent_guide: str = dspy.OutputField(desc="Complete AGENT_GUIDE.md content in markdown format")

    # Create RLM
    rlm = dspy.RLM(
        AgentGuideGenerator,
        max_iterations=8,
        max_llm_calls=16,
        verbose=True,
        tools=tools,
        sub_lm=sub_lm,
        interpreter=NamespaceCodeInterpreter(),
    )

    # Run
    start_time = datetime.now()

    result = rlm(
        ontology_name=ontology_name,
        ontology_stats=meta.summary()
    )

    elapsed = (datetime.now() - start_time).total_seconds()

    return {
        "approach": "rlm_based",
        "ontology": ontology_name,
        "elapsed_seconds": elapsed,
        "iterations": len(getattr(result, 'trajectory', [])),
        "guide": result.agent_guide
    }


def approach_3_dspy_react(ontology_path: str, ontology_name: str) -> dict:
    """Generate AGENT_GUIDE via DSPy ReAct (tool-based, non-recursive)."""
    import dspy
    from rdflib import Graph
    from rlm.ontology import GraphMeta

    # Configure DSPy
    dspy.configure(
        lm=dspy.LM("anthropic/claude-sonnet-4-20250514", temperature=0.2, max_tokens=4096, cache=False)
    )

    # Load ontology
    g = Graph()
    g.parse(ontology_path)
    meta = GraphMeta(graph=g, name=ontology_name)

    # Create tool functions that DSPy ReAct can call
    def search_entity(query: str, limit: int = 10) -> str:
        """Search for entities by label, IRI, or localname.

        Args:
            query: Search string (case-insensitive)
            limit: Max results (1-10)

        Returns:
            JSON string of matching entities
        """
        from rlm.ontology import search_entity as _search
        results = _search(meta, query, limit=min(10, max(1, limit)))
        return json.dumps(results, indent=2)

    def sparql_query(query: str) -> str:
        """Execute SPARQL SELECT query on ontology.

        Args:
            query: SPARQL query string

        Returns:
            JSON string of result bindings
        """
        # Auto-inject LIMIT if missing
        if 'LIMIT' not in query.upper():
            query = query.strip() + ' LIMIT 50'

        result_set = meta.graph.query(query)

        if not hasattr(result_set, 'vars'):
            return "[]"

        results = [
            {str(var): str(row[i]) for i, var in enumerate(result_set.vars)}
            for row in result_set
        ]
        return json.dumps(results[:50], indent=2)  # Limit output

    def get_class_info(class_uri: str) -> str:
        """Get detailed info about a class.

        Args:
            class_uri: URI of the class (supports prefixed forms)

        Returns:
            JSON string with class info
        """
        from rlm.ontology import describe_entity
        info = describe_entity(meta, class_uri, limit=20)
        return json.dumps(info, indent=2)

    # Define signature for guide generation
    class AgentGuideGenerator(dspy.Signature):
        """Generate an AGENT_GUIDE.md by exploring the ontology with tools.

        You have access to tools:
        - search_entity(query, limit) - Find entities by name
        - sparql_query(query) - Execute SPARQL queries
        - get_class_info(class_uri) - Get details about a class

        Generate a comprehensive guide with:
        1. Overview - What the ontology is for
        2. Core Classes - Main classes with when/why to use them
        3. Key Properties - Important properties with usage patterns
        4. Query Patterns - Practical SPARQL examples
        5. Important Considerations - Gotchas and tips
        6. Quick Reference - Compact cheat sheet
        """

        ontology_name: str = dspy.InputField(desc="Name of the ontology")
        ontology_stats: str = dspy.InputField(desc="Basic statistics about the ontology")

        agent_guide: str = dspy.OutputField(desc="Complete AGENT_GUIDE.md in markdown format")

    # Create ReAct module with tools
    react = dspy.ReAct(
        AgentGuideGenerator,
        tools=[search_entity, sparql_query, get_class_info],
        max_iters=8
    )

    # Run
    start_time = datetime.now()

    result = react(
        ontology_name=ontology_name,
        ontology_stats=meta.summary()
    )

    elapsed = (datetime.now() - start_time).total_seconds()

    # Extract tool usage stats from result if available
    tool_calls = 0
    if hasattr(result, 'trajectory'):
        for step in result.trajectory:
            if hasattr(step, 'tool_calls'):
                tool_calls += len(step.tool_calls)

    return {
        "approach": "dspy_react",
        "ontology": ontology_name,
        "elapsed_seconds": elapsed,
        "tool_calls": tool_calls,
        "guide": result.agent_guide
    }


def run_all_approaches(ontology_path: str, ontology_name: str, output_dir: str = "experiments/results"):
    """Run all three approaches and save results."""

    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

    results = {
        "ontology": ontology_name,
        "ontology_path": ontology_path,
        "timestamp": timestamp,
        "approaches": {}
    }

    # Approach 1: Direct LLM
    print(f"\n{'='*60}")
    print(f"Approach 1: Direct LLM for {ontology_name}")
    print(f"{'='*60}")

    try:
        result1 = approach_1_direct_llm(ontology_path, ontology_name)
        results["approaches"]["direct_llm"] = result1

        # Save guide
        guide_path = output_path / f"{ontology_name}_AGENT_GUIDE_direct_{timestamp}.md"
        guide_path.write_text(result1["guide"])
        print(f"Saved: {guide_path}")
        print(f"Elapsed: {result1['elapsed_seconds']:.1f}s")
        print(f"Tokens: {result1['input_tokens']} in, {result1['output_tokens']} out")
    except Exception as e:
        print(f"Error in direct LLM: {e}")
        results["approaches"]["direct_llm"] = {"error": str(e)}

    # Approach 2: RLM-based
    print(f"\n{'='*60}")
    print(f"Approach 2: RLM-based for {ontology_name}")
    print(f"{'='*60}")

    try:
        result2 = approach_2_rlm_based(ontology_path, ontology_name)
        results["approaches"]["rlm_based"] = result2

        # Save guide
        guide_path = output_path / f"{ontology_name}_AGENT_GUIDE_rlm_{timestamp}.md"
        guide_path.write_text(result2["guide"])
        print(f"Saved: {guide_path}")
        print(f"Elapsed: {result2['elapsed_seconds']:.1f}s")
        print(f"Iterations: {result2['iterations']}")
    except Exception as e:
        print(f"Error in RLM: {e}")
        results["approaches"]["rlm_based"] = {"error": str(e)}

    # Approach 3: DSPy ReAct
    print(f"\n{'='*60}")
    print(f"Approach 3: DSPy ReAct for {ontology_name}")
    print(f"{'='*60}")

    try:
        result3 = approach_3_dspy_react(ontology_path, ontology_name)
        results["approaches"]["dspy_react"] = result3

        # Save guide
        guide_path = output_path / f"{ontology_name}_AGENT_GUIDE_react_{timestamp}.md"
        guide_path.write_text(result3["guide"])
        print(f"Saved: {guide_path}")
        print(f"Elapsed: {result3['elapsed_seconds']:.1f}s")
        print(f"Tool calls: {result3.get('tool_calls', 'unknown')}")
    except Exception as e:
        print(f"Error in DSPy ReAct: {e}")
        results["approaches"]["dspy_react"] = {"error": str(e)}

    # Save full results (without guide content to keep JSON small)
    results_path = output_path / f"{ontology_name}_all_comparison_{timestamp}.json"
    with open(results_path, "w") as f:
        results_summary = {
            **results,
            "approaches": {
                k: {kk: vv for kk, vv in v.items() if kk != "guide"}
                for k, v in results["approaches"].items()
            }
        }
        json.dump(results_summary, f, indent=2)
    print(f"\nResults saved: {results_path}")

    return results


def compare_all_guides(results: dict, ontology_name: str) -> str:
    """Use LLM to compare all three generated guides."""
    import anthropic

    client = anthropic.Anthropic()

    approaches = results["approaches"]

    # Build comparison prompt
    guide_texts = []
    for name, result in approaches.items():
        if "guide" in result:
            guide_texts.append(f"## {name.upper()}\n{result['guide'][:8000]}")

    if len(guide_texts) < 2:
        return "Not enough guides to compare (some approaches failed)"

    prompt = f"""Compare these AGENT_GUIDE.md documents for the {ontology_name} ontology.

{chr(10).join(guide_texts)}

Analyze:
1. **Completeness** - Which covers more of the ontology?
2. **Accuracy** - Which has correct URIs and patterns?
3. **Usefulness** - Which would be more helpful for an agent?
4. **Query Quality** - Which has better SPARQL examples?
5. **Affordances** - Which better explains HOW to use the ontology vs just WHAT's in it?
6. **Efficiency** - Compare time/tokens used (from metadata below)

Metadata:
{json.dumps({k: {kk: vv for kk, vv in v.items() if kk != "guide"} for k, v in approaches.items()}, indent=2)}

Provide a structured comparison and rank the approaches (1st, 2nd, 3rd) with reasoning.
"""

    response = client.messages.create(
        model="claude-sonnet-4-20250514",
        max_tokens=2000,
        messages=[{"role": "user", "content": prompt}]
    )

    return response.content[0].text


if __name__ == "__main__":
    import sys

    # Default to PROV
    if len(sys.argv) > 1:
        ontology_name = sys.argv[1]
        ontology_path = sys.argv[2] if len(sys.argv) > 2 else f"ontology/{ontology_name}.ttl"
    else:
        ontology_name = "prov"
        ontology_path = "ontology/prov.ttl"

    print(f"Running all approaches for: {ontology_name}")
    print(f"Ontology path: {ontology_path}")

    results = run_all_approaches(ontology_path, ontology_name)

    # Compare if we have at least 2 successful guides
    successful = sum(1 for v in results["approaches"].values() if "guide" in v)

    if successful >= 2:
        print(f"\n{'='*60}")
        print("Comparing guides...")
        print(f"{'='*60}")

        comparison = compare_all_guides(results, ontology_name)
        print(comparison)

        # Save comparison
        output_path = Path("experiments/results")
        timestamp = results["timestamp"]
        comparison_path = output_path / f"{ontology_name}_comparison_{timestamp}.md"
        comparison_path.write_text(comparison)
        print(f"\nComparison saved: {comparison_path}")
    else:
        print(f"\nOnly {successful} approach(es) succeeded, skipping comparison")
