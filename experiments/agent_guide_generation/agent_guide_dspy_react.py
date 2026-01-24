"""Experiment: DSPy ReAct approach for AGENT_GUIDE.md generation

This adds a third approach using DSPy ReAct (not RLM) for comparison:
1. Direct LLM - Full ontology in context, single shot
2. RLM - Iterative exploration with REPL recursion
3. **DSPy ReAct - Tool-based exploration, structured but non-recursive**
"""

import os
import json
from pathlib import Path
from datetime import datetime

# Ensure API key is set
if not os.environ.get("ANTHROPIC_API_KEY"):
    raise ValueError("Set ANTHROPIC_API_KEY environment variable")


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


def run_react_experiment(ontology_path: str, ontology_name: str, output_dir: str = "experiments/results"):
    """Run DSPy ReAct approach and save results."""

    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

    print(f"\n{'='*60}")
    print(f"Approach 3: DSPy ReAct for {ontology_name}")
    print(f"{'='*60}")

    try:
        result = approach_3_dspy_react(ontology_path, ontology_name)

        # Save guide
        guide_path = output_path / f"{ontology_name}_AGENT_GUIDE_react_{timestamp}.md"
        guide_path.write_text(result["guide"])
        print(f"Saved: {guide_path}")
        print(f"Elapsed: {result['elapsed_seconds']:.1f}s")
        print(f"Tool calls: {result.get('tool_calls', 'unknown')}")

        # Save metadata
        metadata_path = output_path / f"{ontology_name}_react_metadata_{timestamp}.json"
        with open(metadata_path, "w") as f:
            metadata = {k: v for k, v in result.items() if k != "guide"}
            json.dump(metadata, f, indent=2)

        return result

    except Exception as e:
        print(f"Error in DSPy ReAct: {e}")
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

    print(f"Running DSPy ReAct experiment for: {ontology_name}")
    print(f"Ontology path: {ontology_path}")

    result = run_react_experiment(ontology_path, ontology_name)

    if "error" not in result:
        print(f"\n{'='*60}")
        print("Success!")
        print(f"Guide length: {len(result['guide'])} chars")
        print(f"{'='*60}")
