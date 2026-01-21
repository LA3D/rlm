"""Test UniProt genetic disease query with affordance-guided SPARQL.

This tests the core affordance challenge: Can the LLM figure out that disease
information is in a separate named graph and construct the correct multi-graph query?

Expected SPARQL pattern:
    GRAPH <http://sparql.uniprot.org/uniprot> {
        ?protein a up:Protein ;
                 up:annotation ?diseaseAnnotation .
        ?diseaseAnnotation up:disease ?disease .
    }
    GRAPH <http://sparql.uniprot.org/diseases> {
        ?disease a up:Disease ;
                 rdfs:comment ?diseaseComment .
    }

The sense card should guide the LLM to discover this pattern through:
1. SPARQL templates showing how to query for entities
2. Procedural memory (if available) with past multi-graph patterns
3. Class/property descriptions in the ontology

This is a live test against the real UniProt endpoint.
"""

import os
import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from rlm_runtime.engine.dspy_rlm import run_dspy_rlm_with_tools
from rlm_runtime.tools.sparql_tools import make_sparql_tools
from rlm_runtime.ontology import build_sense_card, format_sense_card


def build_uniprot_context(sense_card: str) -> str:
    """Build context string with UniProt-specific guidance.

    Args:
        sense_card: Pre-built sense card for UniProt core ontology

    Returns:
        Context string with sense card and multi-graph guidance
    """
    context_lines = [
        "# UniProt SPARQL Endpoint Query Task",
        "",
        "You are querying the UniProt SPARQL endpoint to answer questions about proteins.",
        "",
        "## Important Architectural Notes",
        "",
        "1. **Multi-Graph Architecture**: UniProt uses named graphs to organize data:",
        "   - `<http://sparql.uniprot.org/uniprot>` - Core protein data",
        "   - `<http://sparql.uniprot.org/diseases>` - Disease annotations",
        "   - `<http://sparql.uniprot.org/taxonomy>` - Taxonomy data",
        "   - Other specialized graphs for citations, keywords, etc.",
        "",
        "2. **Cross-Graph Queries**: When querying data from multiple graphs, use GRAPH clauses:",
        "   ```sparql",
        "   GRAPH <http://sparql.uniprot.org/uniprot> {",
        "       # protein data here",
        "   }",
        "   GRAPH <http://sparql.uniprot.org/diseases> {",
        "       # disease data here",
        "   }",
        "   ```",
        "",
        "3. **Available Tools**:",
        "   - `sparql_query(query, name='res')` - Execute SPARQL and store result handle",
        "   - `res_head(result_name, n=10)` - View first N rows",
        "   - `res_sample(result_name, n=10)` - Random sample of N rows",
        "   - `res_where(result_name, column, pattern=...)` - Filter rows",
        "   - `res_group(result_name, column)` - Group by column",
        "   - `res_distinct(result_name, column)` - Distinct values",
        "",
        "4. **Ontology Information**:",
        "",
        sense_card,
        "",
        "## Task",
        "",
        "Construct and execute SPARQL queries to answer the user's question.",
        "Use the tools to explore and inspect results progressively.",
        "",
    ]
    return "\n".join(context_lines)


def main():
    print("=" * 80)
    print("UniProt Genetic Disease Query Test")
    print("=" * 80)
    print("Testing affordance-guided SPARQL construction with multi-graph architecture")
    print()

    # Check API key
    if not os.environ.get("ANTHROPIC_API_KEY"):
        print("ERROR: ANTHROPIC_API_KEY not set")
        return 1

    # Query from eval task
    query = "List UniProtKB proteins related to a genetic disease, including disease comment and optional MIM cross-reference."

    print(f"Query: {query}")
    print()

    # Build sense card from UniProt core ontology
    ontology_path = project_root / "ontology" / "uniprot" / "core.ttl"
    if not ontology_path.exists():
        print(f"ERROR: Ontology not found: {ontology_path}")
        return 1

    print("Building sense card from UniProt core ontology...")
    sense_card_obj = build_sense_card(str(ontology_path), "uniprot_core")
    sense_card = format_sense_card(sense_card_obj, include_sparql_templates=True)

    print(f"  Formalism: {sense_card_obj.formalism.level}")
    print(f"  Classes: {sense_card_obj.class_count}")
    print(f"  Properties: {sense_card_obj.property_count}")
    print(f"  Triples: {sense_card_obj.triple_count:,}")
    print(f"  Description property: {sense_card_obj.metadata.primary_desc_prop()}")
    print(f"  Label property: {sense_card_obj.metadata.primary_label_prop()}")
    print()

    # Build context with sense card
    context = build_uniprot_context(sense_card)

    # Create namespace for results
    ns = {}

    # Create remote SPARQL tools
    print("Creating remote SPARQL tools for UniProt endpoint...")
    endpoint = "https://sparql.uniprot.org/sparql/"
    tools = make_sparql_tools(
        endpoint=endpoint,
        ns=ns,
        max_results=100,
        timeout=60.0  # UniProt can be slow
    )
    print(f"  Endpoint: {endpoint}")
    print(f"  Tools: {list(tools.keys())}")
    print()

    # Set up logging
    log_path = project_root / "test_uniprot_genetic_disease.jsonl"
    print(f"Trajectory log: {log_path}")
    print()

    # Run the query
    print("Running DSPy RLM with remote SPARQL tools...")
    print("-" * 80)

    try:
        result = run_dspy_rlm_with_tools(
            query=query,
            context=context,
            tools=tools,
            ontology_name="uniprot_core",
            ns=ns,
            max_iterations=12,  # May need more for exploration
            max_llm_calls=24,
            log_path=str(log_path),
            verbose=True,
            log_llm_calls=True
        )

        print()
        print("-" * 80)
        print("RESULTS")
        print("-" * 80)
        print()
        print(f"✓ Converged: {result.converged}")
        print(f"✓ Iterations: {result.iteration_count}")
        print(f"✓ Answer length: {len(result.answer)} chars")
        print()
        print("Answer:")
        print(result.answer)
        print()

        if result.sparql:
            print("SPARQL Query:")
            print(result.sparql)
            print()

        if result.evidence:
            print(f"Evidence fields: {len(result.evidence)}")
            print()

        # Check if multi-graph pattern was used
        if result.sparql:
            has_uniprot_graph = "GRAPH <http://sparql.uniprot.org/uniprot>" in result.sparql
            has_diseases_graph = "GRAPH <http://sparql.uniprot.org/diseases>" in result.sparql
            has_disease_class = "up:Disease" in result.sparql
            has_disease_prop = "up:disease" in result.sparql

            print("-" * 80)
            print("AFFORDANCE ANALYSIS")
            print("-" * 80)
            print(f"  Used GRAPH clause for uniprot: {has_uniprot_graph}")
            print(f"  Used GRAPH clause for diseases: {has_diseases_graph}")
            print(f"  Queried up:Disease class: {has_disease_class}")
            print(f"  Used up:disease property: {has_disease_prop}")
            print()

            if has_uniprot_graph and has_diseases_graph:
                print("✓ SUCCESS: LLM correctly used multi-graph architecture!")
                print("  The sense card and context successfully guided GRAPH clause usage.")
            else:
                print("⚠ PARTIAL: LLM may not have fully utilized multi-graph architecture")
                print("  Review trajectory to understand reasoning process.")

        print()
        print(f"Full trajectory saved to: {log_path}")
        print()
        print("=" * 80)
        print("NEXT STEPS:")
        print("=" * 80)
        print("1. Review trajectory log to see how LLM discovered the multi-graph pattern")
        print("2. Check if sense card SPARQL templates were consulted")
        print("3. Identify any gaps in affordance guidance")
        print("4. Use findings to design Phase 4 eval harness measurements")
        print()

        return 0

    except Exception as e:
        print()
        print("-" * 80)
        print("ERROR during execution:")
        print(str(e))
        import traceback
        traceback.print_exc()
        print()
        print("This may indicate:")
        print("  - Network connectivity issues with UniProt endpoint")
        print("  - Tool surface gaps (missing needed functionality)")
        print("  - Context guidance needs refinement")
        print()
        return 1


if __name__ == "__main__":
    sys.exit(main())
