# Tool Access Pattern Analysis: Simple Approach vs RLM

**Analysis Date:** 2026-01-24
**Notebooks Analyzed:**
- `docs/reference/01-fabric-demo.ipynb` (33 tool calls)
- `docs/reference/01-fabric-e616.ipynb` (21 tool calls)

## Executive Summary

The fabric demo notebooks demonstrate a **radically simpler approach** that gives the LLM direct filesystem access to explore ontology documentation, rather than pre-building bounded tools or sense cards. The agent dynamically discovers what it needs rather than having affordances pre-computed.

## Tool Inventory Comparison

### Simple Approach (Fabric Demo)

**Tools provided:**
1. **`view(path)`** - View file/directory contents (like `Read` tool)
2. **`rg(argstr)`** - Search files using ripgrep (like `Grep` tool)
3. **`sparql_query(query, endpoint, max_results, name, ns)`** - Execute SPARQL and store results in namespace

**Key tool: `swtools.sparql_query`**
```python
def sparql_query(query:str, endpoint:str, max_results:int=100, name:str='res', ns:dict=None):
    """Execute SPARQL query, store results in REPL, return summary"""
    # Stores results in namespace as `res`, `res2`, etc.
    # Returns: "Stored 15 results into 'res': columns ['protein', 'mnemonic']"
```

**Critical features:**
- Results stored in **persistent namespace** (like RLM's dataset memory)
- Returns **summary strings** (count + column names), not full results
- Includes **extensive docstring guidance** on SPARQL patterns, endpoint differences, discovery strategies
- No ontology file loading - queries remote endpoints directly

### Current RLM Approach

**Tools provided:**
1. **`search_entity(pattern, limit)`** - Search for entities by label/URI (built from local GraphMeta)
2. **`sparql_select(query, limit)`** - Execute SPARQL on local graph (built from local GraphMeta)

**Context provided:**
1. **Sense card** (~500 chars) - Pre-computed ontology affordances
2. **GraphMeta summary** - Statistics about loaded graph
3. **Procedural memories** - Retrieved strategies from SQLite
4. **Reasoning guidance** - Think-Act-Verify-Reflect instructions

## Access Pattern Analysis

### Fabric Demo Pattern (01-fabric-e616.ipynb, 21 tool calls)

**Discovery phase:**
1. `view("./ontology")` → See directory structure
2. `view("./ontology/uniprot/AGENT_GUIDE.md")` → Read full guide (387 lines)
3. `rg("-l 'AGENT_GUIDE' ./ontology/wikipathways")` → Search for other guides

**Execution phase:**
4-21. `sparql_query(...)` → 16 iterative queries to UniProt endpoint
   - Query 1: Find DNM1L protein by gene name
   - Query 2: Get annotations for found protein
   - Query 3: Get function annotations
   - Query 4: Get subcellular locations
   - Query 5: Get domain annotations
   - ... (iterative refinement)

**Pattern characteristics:**
- **Read-then-query**: Agent reads AGENT_GUIDE.md in full, then uses it as reference
- **Dynamic discovery**: Agent explores what's available via filesystem
- **Iterative refinement**: 16 queries = progressive disclosure over remote endpoint
- **No pre-processing**: Documentation read directly, no sense card generation

### Fabric Demo Pattern (01-fabric-demo.ipynb, 33 tool calls)

Same pattern, but 26 SPARQL queries (more iterative exploration).

## Key Architectural Differences

| Aspect | Simple Approach | RLM Approach |
|--------|----------------|--------------|
| **Ontology access** | Filesystem tools (view/rg) | Pre-loaded GraphMeta |
| **Documentation** | Read AGENT_GUIDE.md directly | Pre-computed sense card |
| **Query target** | Remote SPARQL endpoint | Local RDFLib graph |
| **Result storage** | Namespace dict (like dataset memory) | Implicit in code interpreter |
| **Tool surface** | 3 general tools | 2 bounded ontology tools |
| **Context injection** | Tool docstrings | 4-layer context (sense+meta+memory+reasoning) |
| **Discovery model** | Dynamic filesystem exploration | Static affordances |

## Critical Insight: AGENT_GUIDE.md vs Sense Card

### AGENT_GUIDE.md (387 lines, ~13KB)
```markdown
# UniProt SPARQL Endpoint - Agent Navigation Guide

## Core Classes
- up:Protein - Protein entries
- up:Taxon - Taxonomic classifications
- up:Annotation - Various annotation types
  - up:Function_Annotation
  - up:Disease_Annotation
  - up:Subcellular_Location_Annotation
  ...

## Key Properties
- up:organism - Links to taxon
- up:sequence - Links to sequence
- up:annotation - Links to annotations
...

## Query Patterns
[14 example queries with explanations]

## Important Query Considerations
- Taxonomy subclasses are materialized
- Filter by up:reviewed true for curated data
...
```

**Characteristics:**
- Comprehensive reference (classes, properties, patterns, tips)
- Agent reads it once, consults as needed
- Includes query templates and common pitfalls
- 100% URI grounding with examples

### Sense Card (~500 chars, ~0.5KB)
```
Classes: prov:Activity, prov:Entity, prov:Agent (3 total)
Properties: prov:wasGeneratedBy, prov:used, prov:wasAssociatedWith (7 total)
Annotations: rdfs:label, rdfs:comment (RDFS vocab)
Maturity: owl:versionInfo "2013-04-30" (stable)
```

**Characteristics:**
- Compact summary
- Lists what exists, not how to use it
- No query patterns
- No common pitfalls or tips

## The Fundamental Question

**Is the RLM approach solving a problem that doesn't need solving?**

The simple approach suggests:
1. **LLMs can navigate documentation directly** - No need to compress into sense cards
2. **Filesystem tools are sufficient** - No need for custom bounded tools
3. **Remote endpoints work fine** - No need to load local graphs
4. **Tool docstrings provide context** - No need for multi-layer context injection

## What RLM Adds Over Simple Approach

**Unique RLM features:**
1. **Procedural memory** - SQLite-backed strategy retrieval
2. **Local graph loading** - Faster queries than remote endpoints (but requires loading)
3. **Sense cards** - Compact affordances (but loses detail vs AGENT_GUIDE.md)
4. **Memory extraction** - Judge/extract/store loop
5. **MLflow tracking** - Experiment observability
6. **Think-Act-Verify-Reflect** - Explicit reasoning structure

**Trade-offs:**
- **Complexity**: 1,186 lines (dspy_rlm.py) vs ~71 lines (swtools.py)
- **Dependencies**: DSPy, rdflib, SQLite backend vs SPARQLWrapper
- **Setup**: Load ontology, build sense card, init memory vs just query
- **Flexibility**: Fixed tools vs dynamic filesystem exploration

## Questions for Investigation

1. **Performance**: Does local graph loading + sense card beat remote endpoint + AGENT_GUIDE.md?
2. **Success rate**: Do procedural memories improve convergence vs tool docstrings?
3. **Iteration count**: Does sense card reduce queries vs reading full documentation?
4. **Generalization**: Can simple approach handle ontologies without AGENT_GUIDE.md?

## Recommended Experiment

**Hypothesis**: The simple approach may perform as well or better for well-documented ontologies.

**Test setup:**
1. Implement `run_simple_rlm()` using filesystem tools + sparql_query
2. Run eval tasks on both approaches
3. Compare:
   - Iteration count
   - Success rate
   - Query quality
   - Context efficiency

**Prediction**: Simple approach will:
- ✓ Work well for UniProt (has AGENT_GUIDE.md)
- ✗ Struggle with PROV (no agent guide, just raw TTL)
- ? Middle ground for others

**Implication**: Hybrid approach?
- Use simple approach when AGENT_GUIDE.md exists
- Use RLM sense card for raw ontologies
- Best of both worlds

## Potential Simplification Path

**Level 1: Minimal viable RLM**
```python
def run_minimal_rlm(query, ontology_path):
    # Check for AGENT_GUIDE.md
    guide_path = ontology_path.parent / "AGENT_GUIDE.md"
    if guide_path.exists():
        # Use simple approach
        tools = {
            'view': make_view_tool(),
            'rg': make_rg_tool(),
            'sparql_query': make_sparql_tool(endpoint)
        }
        context = "Read AGENT_GUIDE.md, then query endpoint"
    else:
        # Fall back to RLM approach
        tools = {
            'search_entity': make_search_entity_tool(meta),
            'sparql_select': make_sparql_select_tool(meta)
        }
        sense_card = build_sense_card(ontology_path)
        context = sense_card + meta.summary()

    return dspy.RLM(...)(query=query, context=context)
```

**Level 2: Dynamic documentation generation**
- If no AGENT_GUIDE.md exists, generate one from GraphMeta
- Gives agent the same rich documentation either way
- Removes sense card compression step

**Level 3: Memory-augmented simple approach**
- Keep simple filesystem tools
- Add procedural memory retrieval
- Skip sense cards, keep AGENT_GUIDE.md pattern

## Conclusion

The fabric demo notebooks reveal a **much simpler architecture** that relies on:
1. LLM's ability to read and use documentation directly
2. General-purpose filesystem tools (view, rg)
3. Well-designed tool docstrings with guidance
4. Remote SPARQL endpoints (no local loading)

The current RLM implementation adds significant machinery (sense cards, local graphs, bounded tools, multi-layer context) that may not be necessary when good documentation exists.

**Recommendation**: Run comparative evaluation to quantify the trade-offs before further RLM complexity additions.
