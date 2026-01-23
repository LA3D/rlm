# Tool Provisioning Gap Analysis

**Date:** 2026-01-22
**Status:** CRITICAL - Root cause of inefficient iteration count identified
**Impact:** Agent taking 10-13 iterations due to missing local ontology tools

---

## Problem Summary

**Observed behavior:**
- Agent queries remote SPARQL endpoint for schema exploration (iterations 0-3)
- Causes timeouts, errors, wasted iterations
- Ignores prompt guidance: "Use query() on local ontology FIRST"

**Root cause:**
- Local ontology tools exist in codebase but are NOT provided to agent
- Agent only receives remote SPARQL tools
- Prompt references tools that don't exist in execution environment

---

## Evidence

### Tool Usage Analysis (5 trials, improved baseline)

**Tools actually used:**
- `sparql_query`: 60 calls (remote endpoint only)
- `res_head`: 64 calls
- `res_sample`: 8 calls
- `res_distinct`: 4 calls
- `res_group`: 1 call
- `SUBMIT`: 11 calls

**Tools referenced in prompts but NOT available:**
- `query()` - Query local ontology (2,816 triples loaded but inaccessible)

### Current Tool Provisioning (task_runner.py:446-476)

```python
from rlm_runtime.tools import make_sparql_tools

# Build tools for remote SPARQL
tools = make_sparql_tools(
    endpoint=endpoint,
    ns=ns,
    max_results=max_results,
    timeout=timeout
)

# Returns ONLY:
# - sparql_query (remote endpoint)
# - res_head, res_sample, res_where, res_group, res_distinct
```

**Missing:** `make_ontology_tools()` never called despite ontologies being loaded!

### Ontology Loading vs Tool Provisioning

**Lines 338-352:** Ontologies ARE loaded:
```python
for onto in ontologies:
    name = onto.get('name', 'ont')
    source = onto.get('source', '')
    if source and Path(source).exists():
        setup_ontology_context(source, ns, name=name)  # ✅ Loaded
        meta = ns.get(f"{name}_meta")
        if meta is not None and hasattr(meta, "summary"):
            ontology_summaries.append(meta.summary())
```

**Lines 474-476:** But tools NOT provided:
```python
tools = make_sparql_tools(endpoint=endpoint, ns=ns, ...)  # ❌ Only remote tools
# make_ontology_tools() NEVER CALLED
```

**Result:** Agent has no way to access the 2,816 ontology triples loaded into memory!

---

## Comparison: Martin Bowling's RLM vs Ours

### Martin's Approach (from article)
**Principle:** Tools match data sources

**Data sources:**
1. Google Search Console data → `safe_get()`, `safe_rows()` helpers
2. Page content → DataStore abstraction
3. Competitive intelligence → Analysis functions like `find_striking_distance()`
4. Sub-tasks → `llm_query()` for delegation

**Result:** Agent can efficiently access all available data

### Our Current Approach
**Data sources:**
1. Remote SPARQL endpoint → ✅ `sparql_query()` tool provided
2. Local ontology (2,816 triples) → ❌ NO TOOLS despite being loaded
3. Sub-tasks → ❌ No `llm_query()` delegation

**Result:** Agent forced to query expensive remote endpoint for schema info that exists locally

---

## Available Tools (Not Provisioned)

Tools exist in `rlm_runtime/tools/ontology_tools.py` but are never given to agent:

```python
def make_ontology_tools(meta: GraphMeta, include_sparql: bool = True) -> dict[str, Callable]:
    """Create all bounded ontology tools for the given GraphMeta.

    Returns:
        - 'search_entity': Search for entities by label/IRI
        - 'describe_entity': Get bounded description of an entity
        - 'probe_relationships': Explore one-hop neighbors
        - 'sparql_select': Execute SPARQL SELECT queries on LOCAL graph
    """
```

**Most critical:** `sparql_select` - Query local ontology without network calls!

---

## Impact Analysis

### Iteration Breakdown (Trial 2, 13 iterations)

**Iterations 0-2: Schema Exploration (3 iterations wasted)**
- Iteration 0: Print context, query remote for taxonomy classes
- Iteration 1: Query remote for UniProt classes (returns 50+ classes to parse)
- Iteration 2: Query remote for Taxon-related items

**Should have been:**
- Iteration 0: `sparql_select("SELECT ?class WHERE { ?class a owl:Class ... } LIMIT 10", name="local")` on LOCAL ontology
- Result: Instant response, no network, finds `up:Taxon` immediately

**Savings:** 2-3 iterations (~20-30% reduction)

### Performance Impact

**Current:**
- 10.2 avg iterations (old baseline)
- 10.2 avg iterations (improved prompts - no change!)
- 80-100% pass rate

**Why prompts didn't help:**
- Prompt says: "Use query() to explore local ontologies"
- Agent tries to follow but tool doesn't exist
- Falls back to remote queries

**Expected with local tools:**
- 6-8 avg iterations (30% reduction)
- Schema exploration: local (instant) vs remote (timeout risk)
- Higher pass rate (fewer errors from remote timeouts)

---

## Missing Tools Summary

### 1. Local Ontology Query Tools ❌ (CRITICAL)

**Need:** `sparql_select(query, name)` for local graph
- Queries 2,816 triples in memory
- No network latency
- No timeout risk
- Finds schema info instantly

**Current state:** Tool exists, never provided

### 2. Schema Inspection Helpers ❌ (HIGH)

**Need:**
- `search_entity(term)` - Find entities by label/IRI
- `describe_entity(iri)` - Get bounded description
- `probe_relationships(iri)` - Explore neighbors

**Current state:** Tools exist, never provided

### 3. Sub-LLM Delegation ❌ (MEDIUM)

**Need:** `llm_query(prompt, context)` for focused subtasks
- Delegate analysis to Haiku sub-model
- Fresh context for focused reasoning
- Martin's article emphasizes this pattern

**Current state:** Tool doesn't exist

**Example use cases:**
- "Analyze these taxa and identify common patterns"
- "Extract key properties from this schema fragment"
- "Determine if this result matches the query intent"

### 4. Result Analysis Helpers ❌ (LOW)

**Have:** `res_head`, `res_sample`, `res_where`, `res_group`, `res_distinct`
**Missing:** Domain-specific analysis (like Martin's `find_striking_distance()`)

**Current state:** Generic tools adequate for now

---

## Fix Implementation Plan

### Phase 1: Add Local Ontology Tools (IMMEDIATE)

**File:** `evals/runners/task_runner.py`

**Change:**
```python
# Current (line 474):
tools = make_sparql_tools(endpoint=endpoint, ns=ns, max_results, timeout)

# Fixed:
tools = make_sparql_tools(endpoint=endpoint, ns=ns, max_results, timeout)

# Add local ontology tools if ontologies were loaded
for onto in ontologies:
    name = onto.get('name', 'ont')
    meta = ns.get(f"{name}_meta")
    if meta is not None:
        from rlm_runtime.tools import make_ontology_tools
        local_tools = make_ontology_tools(meta, include_sparql=True)
        # Rename to avoid collision with remote sparql_query
        local_tools['query'] = local_tools.pop('sparql_select')
        tools.update(local_tools)
```

**Result:** Agent gets `query()` for local ontology exploration

### Phase 2: Add Sub-LLM Delegation (NEXT)

**Create:** `rlm_runtime/tools/llm_tools.py`

```python
def make_llm_query_tool(model: str = "anthropic/claude-3-5-haiku-20241022") -> Callable:
    """Create tool for delegating focused analysis to sub-LLM.

    Returns:
        Callable with signature: llm_query(prompt, context="")
    """
    def llm_query_tool(prompt: str, context: str = "") -> str:
        """Delegate focused task to sub-LLM with fresh context.

        Use this for:
        - Extracting insights from data
        - Analyzing patterns
        - Semantic comparison/matching

        Args:
            prompt: Task description for sub-LLM
            context: Optional data/context to analyze

        Returns:
            Sub-LLM's response
        """
        # Implementation: Call sub-model with prompt + context
        pass

    return llm_query_tool
```

**Add to tool provisioning in task_runner.py**

### Phase 3: Update Prompts to Match Tools (NEXT)

**Current prompt references:**
- "Use query() function to explore these local ontologies"

**After fix:**
- Actually works! `query()` tool exists
- Add examples showing `query()` vs `sparql_query()` distinction
- Clarify: `query()` for local, `sparql_query()` for remote

---

## Expected Outcomes After Fix

### Iteration Count Reduction

**Current:** 10-13 iterations
**Expected:** 6-9 iterations (~30% reduction)

**Why:**
- Iterations 0-2 become local queries (instant vs 2-30 seconds each)
- No remote timeouts during exploration
- Faster discovery of schema patterns

### Pass Rate Improvement

**Current:** 80-100%
**Expected:** 95-100%

**Why:**
- Fewer remote query errors
- No timeouts on schema exploration
- More deterministic behavior

### Tool Usage Pattern

**Current:**
```python
# Iteration 0
sparql_query("SELECT ?class WHERE { ?class a owl:Class ... }", name="schema")  # REMOTE
# → 2-5 second latency, possible timeout
```

**Expected:**
```python
# Iteration 0
query("SELECT ?class WHERE { ?class a owl:Class ... }", name="schema")  # LOCAL
# → <100ms, no network, no errors
```

---

## Validation Plan

### Test 1: Run Baseline with Local Tools

**Setup:**
1. Apply Phase 1 fix (add local ontology tools)
2. Run bacteria taxa task, 5 trials
3. Compare to previous baselines

**Success criteria:**
- Average iterations < 9 (down from 10.2)
- Pass rate ≥ 95%
- Early iterations use `query()` not `sparql_query()`

### Test 2: Check Tool Usage

**Method:** Analyze trajectory logs

**Expected pattern:**
```python
# Iteration 0: Local exploration
query("SELECT ?class WHERE { ?class a owl:Class } LIMIT 10", name="classes")

# Iteration 1: Local property discovery
query("SELECT ?p WHERE { ?p a owl:ObjectProperty } LIMIT 10", name="props")

# Iteration 2: Remote query (now informed by local schema)
sparql_query("SELECT ?taxon ?name WHERE { ... }", name="taxa")
```

### Test 3: Measure Performance

**Metrics:**
- Iteration count distribution
- Time per iteration
- Remote query count
- Error rate

**Expected:**
- Remote queries: 5-7 per trial (down from 8-11)
- Schema exploration: local only
- Errors: <5% (down from 20%)

---

## References

- **Martin Bowling article:** RLM principles, tool design patterns
- **Current baseline:** 10.2 avg iterations, 80-100% pass rate
- **Tool implementation:** `rlm_runtime/tools/ontology_tools.py` (exists but unused)
- **Evidence:** Trial transcripts showing remote queries for schema info

---

## Action Items

- [x] Document root cause
- [ ] Implement Phase 1: Add local ontology tools
- [ ] Run validation test
- [ ] Implement Phase 2: Add sub-LLM delegation
- [ ] Update prompts to match available tools
- [ ] Integrate ReasoningBank to cache successful patterns

**Priority:** CRITICAL - This is the root cause of iteration inefficiency
