# Simple Approach Analysis: Key Findings and Recommendations

**Analysis Date:** 2026-01-24
**Analyst:** Claude Code
**Context:** Comparative analysis of fabric demo notebooks vs current RLM implementation

## TL;DR

Your fabric demo experiments use a **dramatically simpler architecture** (3 general tools + rich docstrings) that may achieve comparable or better results than the current RLM implementation (specialized tools + sense cards + multi-layer context).

The core insight: **LLMs can read and use comprehensive documentation directly** - no need to compress it into sense cards.

## What the Simple Approach Does

### Tools (3 total, from swtools.py - 71 lines)

1. **`view(path)`** - Read files/directories (general filesystem access)
2. **`rg(argstr)`** - Search files with ripgrep (general filesystem search)
3. **`sparql_query(query, endpoint, max_results, name, ns)`** - Query any SPARQL endpoint
   - Stores results in namespace as handles (like RLM dataset memory)
   - Returns summary: "Stored 15 results into 'res': columns ['protein', 'gene']"
   - **Rich docstring** (~800 chars) with SPARQL guidance, common patterns, endpoint tips

### Workflow Pattern (from notebooks)

```
1. view("./ontology") → Discover structure
2. view("./ontology/uniprot/AGENT_GUIDE.md") → Read 387-line comprehensive guide
3. sparql_query(...) → Query remote endpoint iteratively (16-26 queries)
   - Stores results as handles
   - Progressive disclosure via handle inspection
```

### AGENT_GUIDE.md Structure (387 lines, ~13KB)

```markdown
# UniProt SPARQL Endpoint - Agent Navigation Guide

## Core Classes
- up:Protein - Protein entries (reviewed and unreviewed)
- up:Taxon - Taxonomic classifications
- up:Annotation - Various annotation types (15+ subtypes listed)

## Key Properties
- up:organism - Links to taxon
- up:annotation - Links to annotations
- up:sequence - Links to sequence
[~20 properties with descriptions]

## Query Patterns
[14 example queries with explanations]

## Important Query Considerations
- Taxonomy subclasses are materialized - use rdfs:subClassOf directly
- Filter by up:reviewed true for curated data
- Use specific annotation types for performance
[~10 performance tips and common pitfalls]

## Common Query Tasks
[8 templated queries for frequent operations]
```

**Key characteristics:**
- **Comprehensive reference** - Not a summary, a complete guide
- **100% URI grounding** - All classes/properties shown with full URIs
- **Query templates** - Copy-paste patterns for common tasks
- **Pitfalls documented** - "Don't use rdfs:subClassOf+ (materialized)"
- **Endpoint-specific** - Details that matter for UniProt specifically

## What RLM Does Differently

### Tools (2 specialized, from rlm_runtime/tools/ontology_tools.py)

1. **`search_entity(pattern, limit)`** - Search pre-loaded local graph for entities
2. **`sparql_select(query, limit)`** - Query pre-loaded local graph
   - Returns formatted table directly (no handles)
   - Minimal docstrings (~200 chars)
   - Auto-adds LIMIT if missing

### Context Injection (4 layers, ~1000+ chars)

1. **Sense card** (~500 chars) - Compact ontology summary
   ```
   Classes: up:Protein, up:Taxon (50 total)
   Properties: up:organism, up:sequence (200 total)
   Annotations: rdfs:label, rdfs:comment (RDFS vocab)
   Maturity: owl:versionInfo "2013-04-30"
   ```

2. **GraphMeta summary** - Statistics (triples, classes, properties counts)
3. **Procedural memories** - Retrieved strategies from SQLite ReasoningBank
4. **Reasoning guidance** - Think-Act-Verify-Reflect instructions

### Workflow Pattern

```
[Context pre-loaded: sense card + meta + memories + reasoning]

1. search_entity("protein") → Search local graph
2. sparql_select("SELECT ...") → Query local graph
3. [Results returned directly as formatted table]
```

## Side-by-Side Comparison

| Aspect | Simple Approach | RLM Approach |
|--------|----------------|--------------|
| **Tool count** | 3 general | 2 specialized |
| **Tool code** | 71 lines | ~200 lines |
| **Documentation** | Read AGENT_GUIDE.md (387 lines) | Sense card (500 chars) |
| **Query target** | Remote SPARQL endpoint | Local rdflib graph |
| **Result pattern** | Store as handles → inspect | Return directly |
| **Guidance** | Rich tool docstrings | Multi-layer context injection |
| **Setup time** | None (no loading) | Load + parse ontology |
| **Query latency** | Higher (network) | Lower (local) |
| **Memory usage** | Lower (no graph) | Higher (full graph) |
| **Flexibility** | Any SPARQL endpoint | Single loaded graph |
| **Discovery** | Filesystem exploration | Pre-indexed search |

## The Critical Question

**Is the RLM machinery (sense cards, local graphs, specialized tools, multi-layer context) providing value proportional to its complexity?**

**Evidence suggesting "maybe not":**

1. **Documentation richness** - AGENT_GUIDE.md (387 lines) >> sense card (500 chars)
   - Sense card is lossy compression
   - AGENT_GUIDE.md includes query templates, pitfalls, tips
   - LLMs can read and use full documentation effectively

2. **Tool generality** - `sparql_query(endpoint=...)` works with any SPARQL endpoint
   - No need to load local graph
   - No need to build specialized tools per ontology
   - Same tool works for UniProt, Wikidata, DBpedia, etc.

3. **Filesystem exploration** - `view` + `rg` enable dynamic discovery
   - Agent finds documentation organically
   - Can explore examples, read prefixes.ttl, check README files
   - More flexible than pre-indexed search

4. **Simplicity** - 71 lines vs 1,186 lines (dspy_rlm.py)
   - Fewer failure modes
   - Easier to understand and maintain
   - Less framework overhead

**Evidence suggesting "RLM still valuable":**

1. **Procedural memory** - SQLite ReasoningBank with judge/extract/store loop
   - Simple approach has no memory
   - RLM learns from past successes/failures
   - Unique contribution not in simple approach

2. **Local graph performance** - No network latency for queries
   - Faster iteration cycles
   - More reliable (no endpoint downtime)
   - Better for ontologies without public endpoints

3. **Bounded tools** - Auto-LIMIT, error handling
   - Prevents runaway queries
   - More predictable behavior
   - Better for production use

4. **Sense cards for raw ontologies** - What if no AGENT_GUIDE.md exists?
   - Most ontologies don't have agent guides
   - Sense card provides baseline affordances
   - Better than nothing

## Proposed Experiment: Head-to-Head Evaluation

### Hypothesis
For ontologies with comprehensive documentation (AGENT_GUIDE.md), the simple approach will achieve:
- **Equal or better success rates** (rich docs > compressed sense cards)
- **Comparable iteration counts** (guidance compensates for latency)
- **Better generalization** (works with any endpoint)

### Test Setup

1. **Implement `run_simple_rlm()`** using filesystem tools + sparql_query pattern
   ```python
   tools = {
       'view': make_view_tool(),
       'rg': make_rg_tool(),
       'sparql_query': make_sparql_query_tool(default_endpoint)
   }
   context = "Read AGENT_GUIDE.md, then query. See tool docstrings for guidance."
   ```

2. **Run eval tasks on both approaches**
   - Use existing eval framework (evals/tasks/)
   - Test on UniProt tasks (has AGENT_GUIDE.md)
   - Test on PROV tasks (no guide, raw TTL)

3. **Compare metrics**
   - Success rate (answer correctness)
   - Iteration count (efficiency)
   - Query quality (SPARQL patterns)
   - Context usage (tokens)

### Expected Results

**With AGENT_GUIDE.md (UniProt):**
- Simple approach: ✓ High success (comprehensive guidance)
- RLM approach: ✓ High success (sense card + local graph)
- Winner: **Tie or slight edge to simple** (richer docs)

**Without AGENT_GUIDE.md (PROV):**
- Simple approach: ✗ Lower success (no guidance, must explore raw TTL)
- RLM approach: ✓ High success (sense card provides baseline)
- Winner: **RLM** (affordances > raw exploration)

### Implications

If hypothesis holds → **Hybrid approach:**

```python
def run_hybrid_rlm(query, ontology_path):
    guide_path = find_agent_guide(ontology_path)

    if guide_path.exists():
        # Use simple approach with rich documentation
        tools = make_filesystem_tools() + make_sparql_query_tool()
        context = "Read AGENT_GUIDE.md, then query endpoint"
    else:
        # Generate AGENT_GUIDE.md from GraphMeta
        guide_content = generate_agent_guide_from_meta(ontology_path)
        write_guide(guide_path, guide_content)
        # Then use simple approach
        tools = make_filesystem_tools() + make_sparql_query_tool()
        context = "Read generated AGENT_GUIDE.md, then query"

    # Add procedural memory (RLM's unique contribution)
    if memory_backend:
        memories = memory_backend.retrieve(query, k=3)
        context += format_memories_for_context(memories)

    return dspy.RLM(...)(query=query, context=context)
```

**Benefits:**
- Best of both worlds (rich docs + procedural memory)
- Simpler than current RLM (no sense cards, no specialized tools)
- Works with any SPARQL endpoint (local or remote)
- Automatic guide generation for raw ontologies

## Immediate Action Items

### 1. Prototype Simple Approach (2-3 hours)

Create `rlm_runtime/engine/simple_rlm.py`:

```python
def run_simple_rlm(
    query: str,
    ontology_dir: str | Path,  # Directory containing AGENT_GUIDE.md
    endpoint: str,
    max_iterations: int = 8,
    verbose: bool = False
) -> DSPyRLMResult:
    """Run RLM with filesystem tools + sparql_query pattern."""

    # Tools from swtools.py pattern
    tools = {
        'view': make_view_tool(),
        'rg': make_rg_tool(),
        'sparql_query': make_sparql_query_tool(endpoint)
    }

    context = """
You are exploring an ontology via filesystem and SPARQL endpoint.

1. Use view("./ontology") to see structure
2. Read AGENT_GUIDE.md for guidance
3. Query endpoint iteratively using sparql_query()

Results are stored as handles. Inspect them progressively.
"""

    # Use DSPy RLM with filesystem tools
    rlm = dspy.RLM(
        QueryConstructionSig,
        max_iterations=max_iterations,
        tools=tools,
        interpreter=NamespaceCodeInterpreter(),
    )

    return rlm(query=query, context=context)
```

### 2. Run Comparative Eval (1-2 hours)

```bash
# Run simple approach on UniProt tasks
python -m evals.cli run 'uniprot/*' --mode simple

# Run RLM approach on same tasks
python -m evals.cli run 'uniprot/*' --mode rlm

# Compare results
python -m evals.cli compare simple rlm
```

### 3. Analyze Results (1 hour)

Questions to answer:
- Did simple approach match RLM success rate?
- Were iteration counts comparable?
- Which queries were better quality?
- Did reading AGENT_GUIDE.md add significant overhead?

### 4. Decision Point

**If simple approach wins or ties:**
- Adopt hybrid approach (filesystem tools + procedural memory)
- Generate AGENT_GUIDE.md for ontologies that lack it
- Simplify codebase (remove sense cards, specialized tools)

**If RLM approach wins clearly:**
- Document why pre-processing is necessary
- Quantify the benefit of sense cards vs full docs
- Keep current architecture
- Add filesystem exploration as optional mode

## Longer-Term Considerations

### Documentation Generation

If we adopt the AGENT_GUIDE.md pattern, we need a way to generate it:

```python
def generate_agent_guide(ontology_path: Path, endpoint: str = None) -> str:
    """Generate comprehensive agent guide from ontology file."""

    meta = GraphMeta.from_file(ontology_path)

    guide = f"""# {meta.name} - Agent Navigation Guide

## Overview
{infer_ontology_purpose(meta)}

## Core Classes
{format_class_listing(meta.classes, include_descriptions=True)}

## Key Properties
{format_property_listing(meta.properties, include_domains_ranges=True)}

## Query Patterns
{generate_example_queries(meta, count=10)}

## Important Query Considerations
{extract_owl_constraints_as_tips(meta)}

## Common Query Tasks
{generate_task_templates(meta)}
"""

    return guide
```

This would:
- Provide rich documentation for any ontology
- Enable simple approach universally
- Remove dependency on manually written guides
- Maintain RLM's "affordances" concept but in expanded form

### Memory Integration

Keep procedural memory (RLM's unique contribution):

```python
# Hybrid: filesystem tools + procedural memory
if memory_backend:
    memories = memory_backend.retrieve(query, k=3)
    context += "\n\n## Retrieved Strategies\n" + format_memories_for_context(memories)
```

This adds learned strategies without adding sense card complexity.

### Progressive Enhancement Path

**Phase 1: Prototype simple approach**
- Implement run_simple_rlm()
- Test on eval tasks
- Measure performance

**Phase 2: Hybrid mode**
- Add memory retrieval to simple approach
- Compare hybrid vs pure RLM
- Keep whichever performs better

**Phase 3: Documentation generation**
- Implement generate_agent_guide()
- Test with ontologies that lack guides
- Refine templates based on results

**Phase 4: Simplification**
- Remove sense cards if hybrid wins
- Remove specialized tools if filesystem tools win
- Streamline codebase

## Conclusion

The fabric demo notebooks reveal a **fundamentally different architecture** that questions core RLM assumptions:

1. **"LLMs need compressed affordances"** → No, they can read full documentation
2. **"Specialized tools reduce errors"** → General tools with rich docstrings work fine
3. **"Local graphs are necessary"** → Remote endpoints work (with latency trade-off)
4. **"Multi-layer context is optimal"** → Tool docstrings may be sufficient

Your concern is **valid and important**. The simple approach deserves serious investigation before adding more complexity to the RLM implementation.

**Recommended immediate action:**
1. Prototype `run_simple_rlm()` (2-3 hours)
2. Run comparative eval (1-2 hours)
3. Make data-driven decision about architecture

The answer isn't obvious, but the experiment is straightforward and will provide clarity.
