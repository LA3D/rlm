# Trajectory Access Pattern Analysis: Code Writing vs Results Retrieval

**Analysis Date:** 2026-01-24
**Trajectory Analyzed:** `uniprot_bacteria_taxa_001` (10 iterations, 94 events)
**Task:** "Select all bacterial taxa and their scientific name from UniProt taxonomy"

## Executive Summary

Your concern is **valid and significant**. The agent spends substantial time:
1. **Writing exploratory code** rather than using pre-existing documentation
2. **Iterating through schema discovery** when AGENT_GUIDE.md provides this upfront
3. **Calling tools indirectly through Python** rather than declaratively

**Key finding:** 10 LLM calls and 25 tool invocations to solve a task that could be answered in 1-2 queries with proper documentation.

## Event Breakdown

```
Total events: 94
  llm_call: 10
  llm_response: 10
  module_start: 11
  module_end: 11
  tool_call: 25
  tool_result: 25
  session_start: 1
  session_end: 1
```

**Ratio analysis:**
- **10 LLM calls** (cognitive effort)
- **25 tool calls** (actual work done)
- **2.5 tools per LLM call** (low efficiency - lots of thinking, little doing)

## Tool Usage Breakdown

```
Tool frequency:
  sparql_query: 10  (remote endpoint queries)
  res_head: 9       (inspecting stored results)
  query: 4          (local schema exploration)
  res_distinct: 1   (result processing)
  res_sample: 1     (result processing)
```

**Pattern observed:**
- **4 schema exploration queries** (`query()` on local graph)
- **10 remote endpoint queries** (`sparql_query()` to UniProt)
- **11 result inspection calls** (`res_head`, `res_distinct`, `res_sample`)

## Iteration-by-Iteration Analysis

### Iteration 1: Schema Exploration (Local)
**Code written:** 18 lines
**Tool calls:** 1x `query()`
**Purpose:** Find taxonomy-related classes in local ontology
**Result:** Found `up:Taxon`, `up:Rank` classes

**Analysis:** Pure exploration. Agent doesn't know what classes exist.

---

### Iteration 2: Property Discovery (Local)
**Code written:** 31 lines
**Tool calls:** 2x `query()`
**Purpose:** Find properties related to taxonomy and names
**Result:** Found `up:scientificName`, `up:commonName`, etc.

**Analysis:** Still exploring schema. Should already know this from sense card.

---

### Iteration 3: Rank/Parent Properties (Local)
**Code written:** 34 lines
**Tool calls:** 2x `query()`, 1x `sparql_query()`
**Purpose:** Find rank-related properties and sample taxa
**Result:** Found `up:rank` property, but sample query returned empty

**Analysis:** Third iteration still exploring. No results yet.

---

### Iteration 4: Remote Endpoint Test
**Code written:** 24 lines
**Tool calls:** 1x `sparql_query()`, 1x `res_head()`
**Purpose:** Test query to remote endpoint
**Result:** SUCCESS - got sample taxa with scientific names

**Analysis:** First actual results! But took 4 iterations to get here.

---

### Iteration 5: Entity Description Attempt
**Code written:** 29 lines
**Tool calls:** 1x `describe_entity()`, 1x `sparql_query()`, 1x `res_head()`
**Purpose:** Understand taxon structure, confirm taxon:2 is Bacteria
**Result:** `describe_entity()` returned empty, but confirmed taxon:2 = "Bacteria"

**Analysis:** Wasted time with `describe_entity()` (returns nothing). But discovered key fact: taxon:2 = Bacteria.

---

### Iteration 6: More Entity Exploration
**Code written:** 30 lines
**Tool calls:** 1x `describe_entity()`, 1x `query()`
**Purpose:** Try to find parent/ancestor properties
**Result:** Both calls returned empty

**Analysis:** More wasted exploration. `describe_entity()` still doesn't work.

---

### Iteration 7: Probe Relationships Attempt
**Code written:** 22 lines
**Tool calls:** 1x `probe_relationships()`, 1x `sparql_query()`, 1x `res_head()`
**Purpose:** Probe relationships from taxon
**Result:** **ERROR** - `probe_relationships()` doesn't exist

**Analysis:** Tool doesn't exist! Agent wastes iteration on invalid function call.

---

### Iteration 8: Direct Property Query (Breakthrough)
**Code written:** 33 lines
**Tool calls:** 2x `sparql_query()`, 2x `res_head()`
**Purpose:** Directly query all properties for taxon:100 and taxon:2
**Result:** **BREAKTHROUGH** - discovered `rdfs:subClassOf` relationship!

**Analysis:** Finally! After 7 iterations, discovered the key pattern. Found that taxa use `rdfs:subClassOf` for hierarchy.

---

### Iteration 9: First Complete Query Attempt
**Code written:** 48 lines
**Tool calls:** 1x `sparql_query()`, 1x `res_head()`, 1x `sparql_query()`, 1x `res_head()`
**Purpose:** Execute final query with ORDER BY
**Result:** **ERROR** - SPARQL syntax error (ORDER BY not supported)

**Analysis:** Query logic correct, but syntax error.

---

### Iteration 10: Final Success
**Code written:** 51 lines
**Tool calls:** 2x `sparql_query()`, 2x `res_head()`
**Purpose:** Fixed query without ORDER BY + count query
**Result:** **SUCCESS** - 588,389 bacterial taxa retrieved

**Final SUBMIT with:**
- thinking (exploration summary)
- verification (testing steps)
- reflection (correctness assessment)
- answer (natural language)
- sparql (working query)
- evidence (sample results + count)

---

## Problem Pattern Analysis

### Problem 1: Iterative Schema Discovery (Iterations 1-3)

**What happened:**
- 3 iterations exploring local ontology schema
- 4 `query()` calls to find classes and properties
- 71 lines of exploratory code written

**What should have happened (with AGENT_GUIDE.md):**

From AGENT_GUIDE.md (lines 53-65):
```markdown
## Core Classes
- up:Protein - Protein entries
- up:Taxon - Taxonomic classifications  ← Right here!
- up:Gene - Gene information
...

## Key Properties
- up:scientificName - Scientific name  ← Right here!
- up:rank - Taxonomic rank
...
```

**Impact:** **3 wasted iterations** that could have been avoided by reading documentation.

---

### Problem 2: Non-Existent Tool Usage (Iterations 5-7)

**What happened:**
- 2 calls to `describe_entity()` - returns empty
- 1 call to `probe_relationships()` - doesn't exist (ERROR)
- 30+ lines of code written for failed tool calls

**Root cause:** Agent doesn't have clear documentation of what tools exist and what they do.

**Simple approach solution:**
Tools are documented with clear signatures:
```python
def view(path):
    """View file/directory contents"""

def rg(argstr):
    """Search files using ripgrep"""

def sparql_query(query, endpoint, max_results, name, ns):
    """Execute SPARQL query, store results"""
```

**Impact:** **2 wasted iterations** on invalid tool calls.

---

### Problem 3: Delayed Discovery of rdfs:subClassOf (Iteration 8)

**What happened:**
- Took 8 iterations to discover `rdfs:subClassOf` is used for taxonomy hierarchy
- Required direct property inspection of sample taxon

**What AGENT_GUIDE.md says (lines 113-116):**
```markdown
## Important Query Considerations

### Taxonomic Hierarchy
- Taxonomy subclasses are **materialized** - use `rdfs:subClassOf` directly
- Example: To get all E. coli strains, use:
  ?organism rdfs:subClassOf taxon:83333 .
```

**Impact:** **The critical pattern was documented but not visible**. Agent had to rediscover it.

---

### Problem 4: Code Writing Overhead

**Observation:**
Every iteration requires writing Python code to call tools:

```python
# Iteration 8 example (33 lines to make 2 SPARQL queries)
taxon_props_query = """
PREFIX up: <http://purl.uniprot.org/core/>
PREFIX taxon: <http://purl.uniprot.org/taxonomy/>

SELECT ?property ?value
WHERE {
  taxon:100 ?property ?value .
}
LIMIT 30
"""

props_result = sparql_query(taxon_props_query, "taxon_100_props")
props_data = res_head("taxon_100_props", 30)
print("Properties and values for taxon 100:")
for row in props_data:
    print(f"  {row}")

# ... repeat for taxon:2
```

**Simple approach comparison:**

In the fabric demo, agent calls tools more directly (still through code, but more declaratively):
```python
# One tool call, result stored automatically
sparql_query(query="""...""", endpoint="https://sparql.uniprot.org/sparql", name="res")
```

**Impact:** Each iteration has ~30 lines of code overhead for simple queries.

---

## Quantitative Analysis

### Time Distribution

| Activity | Iterations | Tool Calls | Lines of Code |
|----------|-----------|-----------|---------------|
| **Schema exploration** | 3 | 4 | ~71 |
| **Remote testing** | 1 | 2 | ~24 |
| **Failed tool calls** | 3 | 4 | ~81 |
| **Breakthrough discovery** | 1 | 4 | ~33 |
| **Query refinement** | 2 | 11 | ~99 |
| **Total** | **10** | **25** | **~308** |

**Breakdown:**
- **30% of iterations** wasted on schema exploration (should be in docs)
- **30% of iterations** wasted on failed/empty tool calls
- **40% of iterations** doing actual productive work

**Efficiency:**
- **60% wasted effort** (6 out of 10 iterations)
- **40% productive** (4 out of 10 iterations)

---

## Comparison: Current RLM vs Simple Approach

### Current RLM Approach (this trajectory)

**Workflow:**
1. Agent receives sense card + GraphMeta summary
2. Agent explores local schema with `query()` calls
3. Agent tries various tools (`describe_entity`, `probe_relationships`)
4. Agent eventually discovers pattern via trial and error
5. Agent queries remote endpoint
6. Agent refines query

**Characteristics:**
- Exploration-heavy (4 schema queries)
- Trial-and-error (failed tool calls)
- Indirect (write code → call tools → inspect results)
- Limited documentation (sense card only)

**Total cost: 10 iterations, 25 tool calls**

---

### Simple Approach (hypothetical with AGENT_GUIDE.md)

**Workflow:**
1. Agent receives instruction to read AGENT_GUIDE.md
2. `view("./ontology/uniprot/AGENT_GUIDE.md")` → learns:
   - `up:Taxon` class exists
   - `up:scientificName` property for names
   - `rdfs:subClassOf` for hierarchy (materialized!)
   - Example: `?organism rdfs:subClassOf taxon:83333`
3. Agent constructs query directly
4. Agent executes query
5. Agent submits answer

**Characteristics:**
- Documentation-driven (1 file read)
- Direct (no schema exploration needed)
- Efficient (minimal trial-and-error)
- Comprehensive guidance (387 lines of examples)

**Estimated cost: 2-3 iterations, ~5 tool calls**

**Speedup: ~3-5x faster**

---

## Root Cause: Documentation Gap

### What Sense Card Provides (~500 chars)

```
Classes: up:Protein, up:Taxon, up:Gene, up:Enzyme (50 total)
Properties: up:organism, up:sequence, up:annotation (200 total)
Annotations: rdfs:label, rdfs:comment (RDFS vocab)
Maturity: owl:versionInfo "2013-04-30"
```

**Missing:**
- ❌ Which properties link to which classes
- ❌ Query patterns for common tasks
- ❌ Critical ontology-specific details (e.g., "taxonomy is materialized")
- ❌ Example SPARQL queries
- ❌ Common pitfalls

### What AGENT_GUIDE.md Provides (387 lines, ~13KB)

```markdown
## Core Classes (with descriptions)
- up:Taxon - Taxonomic classifications

## Key Properties (with domains/ranges)
- up:scientificName - Scientific name (domain: Taxon, range: string)
- up:rank - Taxonomic rank (domain: Taxon, range: Rank)

## Query Patterns (14 examples)
### Proteins by Organism
SELECT ?protein WHERE {
    ?protein a up:Protein ;
             up:organism taxon:9606 .
}

## Important Query Considerations
- Taxonomy subclasses are **materialized** ← Critical!
- Use rdfs:subClassOf directly, NOT rdfs:subClassOf+ ← Saves iteration!
```

**Provides:**
- ✅ Domain/range information
- ✅ 14 query templates
- ✅ Ontology-specific details
- ✅ Common pitfalls documented
- ✅ Performance tips

---

## Key Insights

### Insight 1: Schema Exploration is Expensive

**Current approach:**
- Agent writes exploratory SPARQL queries
- 3 iterations just to discover classes/properties
- ~71 lines of code written for exploration

**Simple approach:**
- Agent reads AGENT_GUIDE.md (1 tool call)
- All schema info provided upfront
- No exploratory code needed

**Implication:** **Pre-built documentation >> runtime exploration**

---

### Insight 2: Tool Surface Confusion

**Current approach:**
- Agent tries `describe_entity()` (returns empty)
- Agent tries `probe_relationships()` (doesn't exist)
- No clear documentation of available tools

**Simple approach:**
- 3 tools with clear signatures
- Rich docstrings explaining usage
- No ambiguity about what exists

**Implication:** **Simple, well-documented tools >> many specialized tools**

---

### Insight 3: Critical Patterns Hidden

**The breakthrough (Iteration 8):**
Agent discovers `rdfs:subClassOf` is used for taxonomy hierarchy through direct inspection.

**AGENT_GUIDE.md has this documented:**
```markdown
### Taxonomic Hierarchy
- Taxonomy subclasses are **materialized**
- Use `rdfs:subClassOf` directly, NOT `rdfs:subClassOf+`
```

**Implication:** **Documentation must surface critical patterns, not just list classes/properties**

---

### Insight 4: Code Writing Overhead

**Every iteration requires:**
1. Writing Python code to construct query
2. Writing code to call tool
3. Writing code to inspect results
4. Writing code to print/debug

**Contrast with declarative approach:**
- Tool call with query string
- Result automatically stored
- Less boilerplate

**Implication:** **Code writing creates cognitive overhead**

---

## Recommendations

### Immediate Actions

1. **Add AGENT_GUIDE.md to context**
   - Inject as first context layer
   - Agent reads it before exploring
   - Provides all schema info upfront

2. **Simplify tool surface**
   - Remove non-functional tools (`describe_entity`, `probe_relationships`)
   - Provide clear tool documentation
   - Use rich docstrings

3. **Reduce code writing overhead**
   - Consider more declarative tool calling
   - Pre-compute common operations
   - Minimize boilerplate

### Longer-Term Strategy

**Option A: Hybrid Approach**
- Detect if AGENT_GUIDE.md exists
- If yes: Use simple approach (filesystem tools + read guide)
- If no: Generate guide from GraphMeta
- Always provide comprehensive documentation upfront

**Option B: Improve Sense Cards**
- Add query patterns to sense cards
- Include domain/range information
- Document critical ontology-specific details
- Expand from ~500 chars to ~2000 chars

**Option C: Tool-Based Documentation Discovery**
- Add `view_ontology_guide()` tool
- Returns formatted documentation
- Agent can request it when needed

---

## Conclusion

Your concern is **well-founded**. The trajectory shows:

1. **60% wasted effort** (6/10 iterations on exploration/failed tools)
2. **Schema exploration is expensive** (3 iterations, 4 queries)
3. **Tool surface is confusing** (non-existent functions called)
4. **Critical patterns are hidden** (rdfs:subClassOf discovered via trial-and-error)
5. **Code writing overhead** (~30 lines per iteration for simple queries)

**Simple approach with AGENT_GUIDE.md would likely achieve:**
- **2-3 iterations** (vs 10)
- **~5 tool calls** (vs 25)
- **3-5x speedup**
- **Higher success rate** (no failed tool calls)

The agent is spending time **rediscovering** what could be **documented** upfront.

**Recommended next step:** Prototype the simple approach and run comparative evaluation to quantify the performance difference.
