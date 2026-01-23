# Python REPL vs Structured Tool Calling: Architecture Analysis

**Date:** 2026-01-22
**Context:** Eval harness showing inefficiency in DSPy RLM execution
**Problem:** Agent taking 8-13 iterations for simple SPARQL query construction

## Current Architecture: Python REPL with Tool Injection

### How It Works
1. LLM generates Python code as text
2. Code executes in persistent `NamespaceCodeInterpreter`
3. Tools injected as Python functions: `sparql_query()`, `res_head()`, `SUBMIT()`
4. State persists via Python variables: `sample = res_head("taxa", 10)`

### Code Composition Analysis (Trial 2, 13 iterations)

**Total Lines of Code:** 347

| Category | Lines | % | Description |
|----------|-------|---|-------------|
| Tool calls | 39 | 11.2% | Actual `sparql_query()`, `res_head()`, `SUBMIT()` |
| Python boilerplate | 61 | 17.6% | Variable assignments, `print()`, `for` loops |
| SPARQL content | 148 | 42.6% | Query strings (unavoidable) |
| Other logic | 99 | 28.5% | Conditionals, string formatting, list comprehensions |

**Critical Finding: Only 19.6% of code is actual tool usage** (39 tool calls / 199 non-SPARQL lines)

**~45% is Python overhead** (boilerplate + logic that may not be necessary)

---

## Observed Problems

### 1. **Syntax Errors Waste Iterations** (3/13 iterations lost)
```python
```python  # Extra markdown fence inside code block
sample_query = """..."""
...
```
```
**Impact:** Entire iteration wasted on formatting error
**Root cause:** LLM treating code generation as markdown

### 2. **SUBMIT Keyword Argument Confusion** (1/13 iterations lost)
```python
SUBMIT(answer_text, sparql_final, evidence_dict)  # WRONG - positional args
```
**Impact:** Final iteration fails on trivial syntax
**Root cause:** LLM doesn't consistently apply keyword argument pattern

### 3. **Token Waste on Boilerplate**
```python
# Common pattern seen:
result = sparql_query(sample_query, name="sample_taxa")
print("Sample taxa:")
print(res_head("sample_taxa", 10))

# Then later:
sample = res_head("sample_taxa", 10)
for item in sample:
    print(f"  {item['taxon']} - {item['scientificName']}")
```

**45% of tokens** spent on Python syntax instead of reasoning about the query task.

### 4. **Inefficient Exploration Pattern**
Agent writes exploratory queries instead of using tools directly:
- **Iteration 0**: Just prints context (pure waste)
- **Iterations 1-2**: Complex SPARQL exploration of remote endpoint
- **Should do**: Use local `query()` function on loaded ontology

---

## Trade-off Analysis

### Python REPL Approach (Current)

**Pros:**
- ✅ **Stateful iteration**: Variables persist across iterations
- ✅ **Follows RLM paper**: Original design uses Python REPL
- ✅ **Flexible exploration**: Can print, inspect, manipulate results
- ✅ **Handles-not-dumps**: Results stored by name, accessed via bounded views

**Cons:**
- ❌ **Token waste**: 45% overhead on Python syntax/boilerplate
- ❌ **Syntax errors**: Markdown fences, indentation, string escaping
- ❌ **Verbose**: `result = sparql_query(...)` vs direct tool call
- ❌ **Not optimized**: Modern LLMs trained for function calling, not REPL

**Measured Impact:**
- 8-13 iterations to complete simple taxonomy query
- Average 10.2 iterations without ReasoningBank
- 3/13 iterations wasted on syntax errors (23%)

---

### Structured Tool Calling Approach (Alternative)

**Pros:**
- ✅ **No syntax errors**: JSON tool calls, no Python parsing
- ✅ **More efficient**: ~45% more tokens for reasoning/planning
- ✅ **Optimized by LLMs**: Function calling is trained for (tool use optimization)
- ✅ **Clearer intent**: Explicit tool→result boundary
- ✅ **Better observability**: Can log/trace tool calls independently

**Cons:**
- ❌ **State management challenge**: How to persist handles/variables?
- ❌ **Less flexible**: Can't do arbitrary Python computation
- ❌ **Deviates from RLM paper**: Different execution model
- ❌ **Handle registry needed**: Where do result names live?

---

## Hybrid Approach Proposals

### Option A: Structured Tools + Result Registry

**Execution Flow:**
```json
// Iteration 1: Query
{"tool": "sparql_query", "args": {"query": "SELECT ...", "name": "sample"}}
→ Result stored in registry: {"sample": [...]}

// Iteration 2: Inspect
{"tool": "res_head", "args": {"handle": "sample", "n": 10}}
→ Returns first 10 results

// Iteration 3: Submit
{"tool": "SUBMIT", "args": {"answer": "...", "sparql": "...", "evidence": {...}}}
```

**State Management:**
- Interpreter maintains `result_registry: Dict[str, Any]`
- Tools reference handles by name
- Bounded views operate on registry entries

**Advantages:**
- No Python syntax errors
- Preserves RLM handle semantics
- ~45% token efficiency gain

**Challenges:**
- No arbitrary computation (e.g., can't do `for item in sample: print(...)`)
- Tool surface must be comprehensive
- Registry cleanup/lifecycle management

---

### Option B: Hybrid - Tools for Exploration, Python for Construction

**Phase 1: Exploration (Structured Tools)**
```json
{"tool": "query", "args": {"sparql": "SELECT ?class WHERE ...", "name": "schema"}}
{"tool": "sparql_query", "args": {"query": "SELECT ...", "name": "bacteria"}}
{"tool": "res_head", "args": {"handle": "bacteria", "n": 10}}
```

**Phase 2: Answer Construction (Python REPL if needed)**
```python
# Only if complex formatting/evidence construction needed
evidence = {
    "sample": [{"taxon": str(r['taxon']), "name": r['scientificName']}
               for r in res_head("bacteria", 5)],
    "approach": "Used rdfs:subClassOf hierarchy"
}
SUBMIT(answer="...", sparql=final_query, evidence=evidence)
```

**Advantages:**
- Best of both: efficient exploration, flexible construction
- Phase transition clear (exploration → answer)
- Reduces syntax error surface area

**Challenges:**
- Two execution modes to maintain
- When to switch phases?
- Still has some Python overhead

---

### Option C: Enhanced Python REPL with Guardrails

**Keep current architecture but add:**
1. **Aggressive syntax validation** (already added)
2. **Template-based code generation** (LLM fills slots, not free-form)
3. **Cached tool call patterns** (ReasoningBank stores successful patterns)
4. **Strict prompting** (examples showing tool-only style)

**Example prompt enhancement:**
```
Write minimal Python using ONLY tool calls. Do NOT use:
- print() statements (results are logged automatically)
- for loops to display results (use res_head/res_sample)
- unnecessary variable assignments

Good:
  sparql_query("SELECT ...", name="taxa")
  SUBMIT(answer="...", sparql="...", evidence={...})

Bad:
  result = sparql_query("SELECT ...", name="taxa")
  sample = res_head("taxa", 10)
  for item in sample:
      print(f"Item: {item}")
```

**Advantages:**
- Minimal architecture change
- Preserves flexibility where needed
- Incremental improvement path

**Challenges:**
- Still ~20-30% overhead likely
- Syntax errors still possible
- Requires excellent prompting

---

## Key Questions to Resolve

### 1. **Is variable persistence critical?**
- Observed: `sample = res_head(...)` then later referencing `sample`
- Frequency: Low in current traces (most variables used once)
- **Hypothesis**: Handle registry could replace most variable usage

### 2. **How much logic is essential?**
- 28.5% of code is "other logic" (conditionals, formatting, comprehensions)
- **Need to analyze**: How much adds value vs could be eliminated?
- Examples:
  - Building `evidence` dict with list comprehensions → Could be tool output format
  - Printing intermediate results → Could be automatic tool logging
  - Conditional logic → Rare in traces so far

### 3. **What's the RLM paper's position?**
- Paper emphasizes: "Handles not dumps" + bounded views
- Paper uses: Python REPL in examples
- **Question**: Is Python REPL essential to RLM, or just one implementation?
- **Key insight**: Handles + bounded views can work with tool calling + registry

### 4. **Performance vs Fidelity trade-off?**
- Structured tools: Higher efficiency, lower flexibility
- Python REPL: Lower efficiency, higher flexibility
- **Question**: Is the 45% overhead worth the flexibility we're actually using?

---

## Experimental Path Forward

### Phase 1: Measure Current Overhead (Done)
- ✅ Analyzed code composition: 19.6% actual tool usage
- ✅ Identified syntax error patterns: 23% of iterations wasted
- ✅ Added syntax validation and improved prompts

### Phase 2: Enhanced REPL Baseline (In Progress)
- ✅ Improved prompts emphasizing tool-first, minimal Python
- ✅ Added SUBMIT syntax examples
- ✅ Syntax validation for markdown fences
- 🔄 Running new baseline to measure improvement

### Phase 3: Tool Calling Prototype (Proposed)
1. Implement Option A (Structured Tools + Result Registry)
2. Run same bacteria taxa task
3. Compare metrics:
   - Iterations to convergence
   - Success rate
   - Token efficiency
   - Error patterns

### Phase 4: Hybrid Experiment (If needed)
- If pure tool calling loses essential flexibility
- Implement Option B (Tools for exploration, Python for construction)
- Measure trade-offs

---

## Preliminary Recommendations

**Short-term (next sprint):**
1. ✅ Improve Python REPL prompting (done)
2. ✅ Add syntax validation (done)
3. ⏳ Measure improved baseline
4. 📋 Add ReasoningBank to cache successful patterns
5. 📋 Analyze if improved prompts + memory reduce overhead to acceptable level

**Medium-term (if overhead remains >30%):**
1. Prototype structured tool calling with result registry
2. Run comparative evaluation (same tasks, both architectures)
3. Measure:
   - Token efficiency gain
   - Iteration count reduction
   - Task success rate
   - Error rate

**Long-term (architectural decision):**
- If structured tools show clear wins (>30% efficiency, no capability loss):
  - Migrate to structured tool calling as default
  - Keep Python REPL as fallback for complex construction
- If gains are marginal (<20% efficiency):
  - Keep enhanced Python REPL
  - Focus on ReasoningBank + prompting

---

## Open Questions for Discussion

1. **Flexibility requirement**: Do we have tasks that actually need arbitrary Python logic, or is tool composition sufficient?

2. **Handle semantics**: Can we maintain RLM's "handles not dumps" principle with a tool-calling + registry approach?

3. **Learning curve**: Is Python REPL more intuitive for LLMs despite being less efficient? (Function calling is trained, but code generation is more natural language-like)

4. **Debugging experience**: With Python REPL we see print statements and intermediate state. How to preserve this with tool calling?

5. **ReasoningBank integration**: Would cached tool call sequences (structured) be more reusable than cached Python snippets?

---

## References

- **Empirical data**: Trial 2 trajectory analysis (13 iterations, bacteria taxa task)
- **RLM paper**: Progressive disclosure, handles-not-dumps, bounded views
- **Current baseline**: 10.2 avg iterations, 100% pass rate (without ReasoningBank)
- **Improved baseline**: Running now with enhanced prompts + syntax validation

**Next steps**: Wait for improved baseline, analyze iteration count, decide on prototype direction.
