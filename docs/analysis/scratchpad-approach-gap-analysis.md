# Scratchpad Approach Gap Analysis

**Date**: 2026-01-28
**Status**: Critical Gap Identified
**Purpose**: Understand why current DSPy RLM doesn't leverage ontology semantics

---

## Executive Summary

The original RLM scratchpad approach was designed for **ontology-grounded reasoning**:
1. Load ontology into structured indexes (GraphMeta)
2. Provide bounded exploration functions (describe_entity, probe_relationships, find_path)
3. Use `llm_query()` for semantic analysis of what's discovered
4. Model reasons ABOUT the ontology, then constructs queries

Our current DSPy RLM implementation **bypasses this entirely**:
- Context is text (AGENT_GUIDE.md) not loaded ontology
- Tools are SPARQL execution, not ontology exploration
- No semantic analysis via llm_query - just brute-force search/filter

**This is why the model doesn't produce ontology-grounded chain-of-thought.**

---

## The Original Scratchpad Design

### Philosophy (from rlmpaper)

From `RLM_SYSTEM_PROMPT`:

> "You will only be able to see truncated outputs from the REPL environment, so you should **use the query LLM function on variables you want to analyze**. You will find this function especially useful when you have to **analyze the semantics of the context**."

The design intent:
1. **Context is loaded into namespace** - not just text, but structured data
2. **Sub-LLMs for semantic analysis** - understand what things mean
3. **Iterative exploration** - chunk, query, aggregate
4. **Buffers for state** - build up understanding incrementally

### For Ontology Work (from `rlm/ontology.py`)

The ontology module provides:

```python
# Load ontology into GraphMeta (structured indexes)
setup_ontology_context(path, ns, name='ont')

# GraphMeta provides:
meta.classes       # All class URIs
meta.properties    # All property URIs
meta.labels        # URI → label mapping
meta.by_label      # label → URI mapping (inverted)
meta.subs          # superclass → subclasses
meta.supers        # subclass → superclasses
meta.doms          # property → domain
meta.rngs          # property → range
meta.pred_freq     # predicate frequency counts

# Bounded view functions for exploration:
search_entity(meta, query)           # Find entities by label/URI/localname
describe_entity(meta, uri)           # Get bounded description
probe_relationships(meta, uri)       # One-hop neighbors
find_path(meta, source, target)      # BFS path finding
predicate_frequency(meta)            # Ranked predicates
```

### The Sense-Building Pattern

From `build_sense()`:

```python
# Extract ontology structure programmatically
ont_meta(f'{ont_name}_meta', ...)     # Prefixes, annotations, imports
ont_roots(f'{ont_name}_meta', ...)    # Root classes
# Build hierarchy, properties, OWL constructs...

# Then use llm_query to SYNTHESIZE understanding:
prompt = f"""Analyze this ontology and provide a sense document:
**Structure:** {hier}
**Properties:** {top_props}
**OWL Constructs:** {owl_constructs}

Provide:
1) Domain/scope - what is this ontology about?
2) Key branches - main conceptual areas
3) Important properties - key relationships
4) Detected patterns - reification, part-whole, restrictions
5) SPARQL navigation hints"""

summary = llm_query(prompt, ns=ns, name='_sense_summary')
```

**This is the key insight:** The model uses `llm_query` to **understand the ontology**, not just find IDs.

---

## Current DSPy RLM Implementation

### What We Have

```python
# In run_dspy_rlm_with_tools():

# Context is text (AGENT_GUIDE.md)
guide_path = Path(f"ontology/{ontology_name}/AGENT_GUIDE.md")
context = guide_path.read_text()

# Tools are SPARQL execution only
tools = make_sparql_tools(
    endpoint="https://sparql.uniprot.org/sparql",
    ns=ns,
    max_results=100
)
# Returns: sparql_query, res_head, res_sample, res_where, res_group, res_distinct
```

### What's Missing

| Original Design | Current Implementation |
|----------------|----------------------|
| Load ontology into GraphMeta | ❌ Just text context (AGENT_GUIDE.md) |
| `search_entity()` for exploration | ❌ No ontology exploration tools |
| `describe_entity()` for bounded views | ❌ Only SPARQL execution |
| `probe_relationships()` for neighbors | ❌ Can't navigate structure |
| `find_path()` for connecting concepts | ❌ No path finding |
| `llm_query()` for semantic analysis | ⚠️ Available but unused |
| Sense document synthesis | ❌ No ontology understanding step |

### Why the Model Brute-Forces

Without ontology exploration tools, the model can only:
1. Read AGENT_GUIDE.md (text)
2. Execute SPARQL queries

So it:
- Uses `FILTER(CONTAINS(...))` instead of understanding class hierarchies
- Searches by text instead of navigating relationships
- Doesn't ask llm_query "What does this ontology say about X?"

---

## The Chain-of-Thought Gap

### What SHOULD Happen

```
Query: "Find human proteins involved in apoptosis"

ONTOLOGY EXPLORATION:
1. "Let me explore how this ontology models biological processes..."
2. describe_entity('GO:0006915')  # What is apoptosis?
   → Label: "apoptotic process", Parent: "programmed cell death"
3. probe_relationships('up:classifiedWith')  # How are proteins classified?
   → Domain: Protein, Range: GO Term
4. find_path('Protein', 'GO Term')  # What connects them?
   → Protein -classifiedWith→ GO Term -subClassOf*→ GO:0006915

SEMANTIC ANALYSIS:
5. llm_query("Based on this ontology structure, what's the best way to query
   for proteins involved in apoptosis? Should I use direct annotation or
   traverse the GO hierarchy?")
   → "Use rdfs:subClassOf* for transitive closure of GO:0006915"

QUERY CONSTRUCTION:
6. Now construct SPARQL query grounded in ontology understanding
```

### What ACTUALLY Happens

```
Query: "Find human proteins involved in apoptosis"

BRUTE-FORCE:
1. Construct SPARQL with FILTER(CONTAINS(?goLabel, 'apoptosis'))
2. Execute query
3. Done

NO:
- Exploration of ontology structure
- Understanding of class hierarchies
- Semantic analysis via llm_query
- Chain-of-thought reflecting ontology understanding
```

---

## Proposed Fix

### For Remote SPARQL Endpoints (UniProt)

We can't load the full UniProt data locally, but we CAN:

1. **Load the schema ontology** (`ontology/uniprot/core.ttl`) into GraphMeta
2. **Provide exploration tools over the schema**:
   - `describe_class(uri)` - What is this class?
   - `describe_property(uri)` - What does this property connect?
   - `find_path(class1, class2)` - How are these related?
   - `get_subclasses(uri)` - What are the children?

3. **Inject exploration guidance** in the prompt:
   ```
   Before constructing SPARQL queries:
   1. Use describe_class() to understand key concepts
   2. Use find_path() to discover how concepts connect
   3. Use llm_query() to synthesize understanding:
      llm_query("Based on exploring the schema, how should I query for X?")
   ```

4. **Track exploration in chain-of-thought**:
   - Model must show what it learned from exploration
   - Must show reasoning about ontology structure
   - Must show how structure informs query construction

### Implementation Steps

1. **Create schema exploration tools**:
   ```python
   def make_schema_tools(schema_path: str) -> dict:
       """Create tools for exploring ontology schema."""
       meta = setup_ontology_context(schema_path, {}, 'schema')
       return {
           'describe_class': partial(describe_entity, meta),
           'describe_property': partial(describe_entity, meta),
           'find_class_path': partial(find_path, meta),
           'get_subclasses': lambda uri: meta.subs.get(uri, []),
           'get_superclasses': lambda uri: meta.supers.get(uri, []),
           'search_schema': partial(search_entity, meta),
       }
   ```

2. **Add schema exploration phase**:
   ```python
   # Before query construction:
   SCHEMA_EXPLORATION_GUIDANCE = """
   ## Required: Explore Schema Before Querying

   Before constructing SPARQL, you MUST:
   1. search_schema() for key concepts mentioned in the query
   2. describe_class() for main classes involved
   3. find_class_path() to understand how concepts connect
   4. llm_query() to synthesize understanding:
      "Based on exploring the schema, I learned that..."

   Only after schema exploration, construct the SPARQL query.
   """
   ```

3. **Require chain-of-thought to show exploration**:
   ```python
   thinking: str = dspy.OutputField(
       desc="THINK: First describe what you learned from exploring the schema "
            "(classes found, relationships discovered, paths identified). "
            "Then explain how this informs your query construction."
   )
   ```

---

## Why This Matters

### Complex Queries Fail Without Ontology Understanding

For L3-L4 queries:
- Multi-hop reasoning requires understanding relationship chains
- Spatial reasoning requires understanding position ontologies (FALDO)
- Aggregation requires understanding class hierarchies
- Integration requires understanding how annotation types connect

Brute-force SPARQL filters will fail because:
- They don't traverse hierarchies correctly
- They miss indirect relationships
- They can't reason about position overlaps
- They don't understand the ontology's design patterns

### Ontology-Grounded CoT is the Goal

The whole point of RLM for ontologies is:
1. **Progressive disclosure** - Explore structure before querying
2. **Semantic understanding** - Use llm_query to analyze what's found
3. **Grounded reasoning** - Chain-of-thought reflects ontology semantics
4. **Correct queries** - Constructed from understanding, not pattern matching

---

## Summary

| Aspect | Original Design | Current Gap | Fix |
|--------|----------------|-------------|-----|
| **Context** | Loaded ontology | Text guide | Load schema into GraphMeta |
| **Tools** | Exploration + Query | Query only | Add schema exploration tools |
| **llm_query** | Semantic analysis | Unused | Require for understanding synthesis |
| **CoT** | Ontology-grounded | Brute-force | Track exploration in thinking |

**The fundamental issue:** We stripped out the ontology exploration layer and went straight to SPARQL execution. This defeats the purpose of RLM's progressive disclosure philosophy.

---

## Files Referenced

- `/Users/cvardema/dev/git/LA3D/rlm/rlm/core.py` - Original RLM loop with llm_query
- `/Users/cvardema/dev/git/LA3D/rlm/rlm/ontology.py` - GraphMeta and bounded views
- `/Users/cvardema/dev/git/LA3D/rlm/rlm/_rlmpaper_compat.py` - RLM system prompt
- `/Users/cvardema/dev/git/LA3D/rlm/rlm_runtime/engine/dspy_rlm.py` - Current implementation

**Last Updated**: 2026-01-28
