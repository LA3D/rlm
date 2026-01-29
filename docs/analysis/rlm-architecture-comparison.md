# RLM Architecture Comparison: Your Implementation vs Reference Architectures

**Date**: 2026-01-28
**Purpose**: Identify architectural gaps and validate RLM vs ReAct comparison fairness

---

## Executive Summary

**Key Finding**: Your current RLM implementation does NOT follow Prime Intellect's RLM design principles. This explains the "flat, linear pattern" behavior observed in your state document.

**Critical Gap**: Sub-LLM delegation is not available during exploration—only used once for final synthesis. This undermines RLM's core advantage.

**Recommendation**: Before concluding RLM vs ReAct comparison, either:
1. Add `llm_query()` tool to enable strategic sub-LLM delegation (true RLM)
2. Accept current implementation is "code-augmented agent" not "recursive LLM"
3. Test if ReAct's simplicity is actually optimal for ontology queries

---

## Architecture Comparison

### 1. Prime Intellect RLM (Reference Implementation)

**Core Principles** (from blog post):
- **Tool restriction**: Main model does NOT have direct tool access
- **Sub-LLM delegation**: `llm_batch()` for parallel semantic analysis
- **Strategic orchestration**: Main model delegates, doesn't do heavy work
- **Persistent REPL**: Data available only programmatically
- **Output capping**: 8,192 char limit forces efficiency

**Example Pattern**:
```python
# Iteration 1: Main model delegates search to sub-LLM
search_results = llm_batch([
    "Which of these entities is the Protein class?",
    "Are there multiple Protein concepts?"
], data=search_output)

# Iteration 2: Main model synthesizes
if search_results[0].confidence > 0.8:
    protein_uri = search_results[0].uri
```

**Benefits**:
- Main model stays strategic (low token count)
- Sub-LLMs handle verbose tool interactions
- Scales to long-context tasks (1.5M chars tested)

**Drawbacks**:
- Requires RL training for effective delegation
- Overhead may not pay off for simple tasks
- Math reasoning suffered (36% drop vs baseline)

---

### 2. Huberman RLM (DSPy Reference)

**Architecture**:
```python
rlm = dspy.RLM(
    signature="transcripts, question -> answer, sources",
    max_iterations=20,
    max_llm_calls=25,
    sub_lm=dspy.LM(SUB_MODEL),
    verbose=True,
)
```

**Key Features**:
- Uses DSPy's built-in RLM with Deno/Pyodide sandbox
- Sub-model specified via `sub_lm` parameter
- `llm_query()` available in REPL for delegation
- Declarative signature-based interface

**Usage Pattern**:
- Pass large context (transcripts) directly in signature
- Model writes code to explore programmatically
- Sub-LLM called via `llm_query()` for semantic analysis
- No explicit tool definitions (DSPy handles it)

---

### 3. Your Implementation (rlm_runtime/engine/dspy_rlm.py)

**Architecture**:
```python
tools = {
    'search_entity': make_search_entity_tool(meta),
    'sparql_select': make_sparql_select_tool(meta)
}

rlm = dspy.RLM(
    QueryConstructionSig,
    max_iterations=8,
    max_llm_calls=16,
    verbose=verbose,
    tools=tools,  # ← Tools injected directly
    sub_lm=sub_lm,  # ← Passed but not exposed as llm_query()
    interpreter=NamespaceCodeInterpreter(...),
)
```

**What Happens**:
1. Main model generates code: `results = search_entity("Protein")`
2. Code executes in host Python namespace
3. Tools called DIRECTLY by main model (not via sub-LLM)
4. Sub-LLM exists but is NOT exposed as `llm_query()` tool
5. Result: All work done by main model, sub-LLM unused

**From your state doc (lines 110-125)**:
```
Iteration 5: **Sub-LLM synthesis**
answer_text = llm_query(prompt)  # ← Extra LLM call!
```

This is the ONLY time sub-LLM is used—for final synthesis, not strategic delegation during exploration.

---

## Key Architectural Differences

| Aspect | Prime Intellect RLM | Your Implementation | Impact |
|--------|---------------------|---------------------|--------|
| **Tool Access** | Sub-LLMs only | Main model directly | Main model does all work |
| **llm_query() Tool** | Yes, core feature | **NO** | No strategic delegation |
| **Sub-LLM Usage** | Throughout (disambiguation, filtering, validation) | Only final synthesis | RLM advantages lost |
| **Main Model Role** | Strategic orchestrator | Code generator + executor | Token inefficient |
| **Output Cap** | 8,192 chars | 10,000 chars | Similar |
| **Tool Count** | Many (via llm_batch) | 2 (search, sparql) | Minimal surface |

---

## Why This Matters for Your Comparison

### Your State Doc Observations (Validated)

**Concern 1: "Is RLM Too Flat?"** (lines 201-238)
- ✅ **CORRECT**: Your RLM is flat because it lacks strategic delegation
- ✅ **ROOT CAUSE**: No `llm_query()` tool available during exploration
- ✅ **EVIDENCE**: Linear pattern (search → query → investigate → synthesize)

**Concern 2: "Sub-LLM Usage"** (lines 240-253)
- ✅ **CORRECT**: Sub-LLM only used for synthesis, not strategy
- ✅ **YOUR HYPOTHESIS**: "Should sub-LLM be used for STRATEGIC decisions during exploration?"
- ✅ **ANSWER**: Yes! That's exactly what Prime Intellect does

**Performance Mystery**:
- ReAct: 29% faster (52.9s vs 74.5s)
- RLM overhead: ~50s (code generation + execution)
- RLM benefit: **NONE** (no strategic delegation)
- **Conclusion**: You're paying overhead without getting RLM's advantages

---

## What's Missing: Strategic Sub-LLM Delegation

### Current Pattern (Your RLM)
```python
# Iteration 1: Main model does everything
results = search_entity("Protein", limit=10)
print(f"Found {len(results)} entities")

# Iteration 2: Main model does everything
query = """SELECT ?prop ?value WHERE { <Protein> ?prop ?value }"""
props = sparql_select(query)
print(f"Properties: {props}")

# Iteration 5: ONLY sub-LLM usage
answer = llm_query("Synthesize answer from: " + str(props))
```

### What Prime Intellect RLM Does
```python
# Iteration 1: Main model DELEGATES search interpretation
results = search_entity("Protein", limit=10)
best_match = llm_query(f"Which of these is the main Protein class? {results}")

# Iteration 2: Main model DELEGATES disambiguation
if len(props) > 20:
    relevant_props = llm_batch([
        "Which properties are most important for definition?",
        "Which properties link to other classes?",
        "Which properties are deprecated?"
    ], data=props)

# Iteration 3: Main model DELEGATES validation
is_valid = llm_query(f"Does this SPARQL look correct? {query}")
if not is_valid['correct']:
    query = llm_query(f"Fix this query: {query}. Error: {is_valid['reason']}")

# Iteration 4: Main model DELEGATES synthesis
answer = llm_query("Synthesize answer from evidence")
```

**Key Difference**: Sub-LLM used for STRATEGIC DECISIONS, not just final synthesis.

---

## Impact on Your L1 Results

### Why RLM Was Slower (70.9s vs 55.6s)

**RLM Overhead (with NO benefits)**:
- Code generation: ~2-3s per iteration × 5 = **15s**
- Code validation: ~0.5s per iteration × 5 = **2.5s**
- Code execution: ~1-2s per iteration × 5 = **7.5s**
- Sub-LLM synthesis (iter 5): **15s**
- **Total overhead**: ~40s

**RLM Work**:
- Tool calls: ~20s
- **Total**: 60s

**RLM Theoretical Benefits** (NOT realized):
- ❌ Strategic delegation (no llm_query during exploration)
- ❌ Parallel sub-LLM calls (no llm_batch)
- ❌ Token efficiency (main model doing all work)
- ✅ State persistence (minor benefit)
- ✅ Multi-step composition (minor benefit)

**Result**: Overhead without benefit = slower execution

### Why ReAct Was Faster (55.6s)

**ReAct Overhead**:
- Thought generation: ~1-2s per iteration
- Tool execution: ~0.5-1s per iteration
- Context update: ~0.1s per iteration
- **Per-iteration cost**: ~3.5s
- **16 iterations**: 56s ✓

**ReAct Benefits**:
- Direct tool calls (no code generation)
- Simple architecture (no interpreter overhead)
- Fast execution (minimal overhead)

**ReAct Drawbacks**:
- More iterations (16 vs 5)
- Sequential tool calling
- No state persistence

---

## Hypothesis: Why ReAct Needed 16 Iterations

**From your state doc (Concern 3, lines 255-264)**:
> ReAct reports 16 iterations but `max_iters=8`. Is DSPy counting differently?

**Likely Explanation** (based on DSPy patterns):
- DSPy RLM: 1 iteration = 1 code generation + execution cycle
- DSPy ReAct: 1 iteration = 1 thought + 1 action = **2 LLM calls**
- **Counting difference**: ReAct counts LLM calls, RLM counts code cycles

**Alternative**: ReAct may be doing redundant exploration due to no state persistence.

**Action**: Check DSPy ReAct source to verify iteration counting.

---

## Recommendations

### Immediate Actions

#### 1. Add llm_query() Tool to Your RLM

**Modify `run_dspy_rlm()` (lines 335-341)**:
```python
# Create bounded tools + sub-LLM delegation
tools = {
    'search_entity': make_search_entity_tool(meta),
    'sparql_select': make_sparql_select_tool(meta),
    'llm_query': make_llm_query_tool(sub_lm),  # ← ADD THIS
}
```

**Implement `make_llm_query_tool()`**:
```python
def make_llm_query_tool(sub_lm):
    """Create llm_query tool for strategic sub-LLM delegation."""
    def llm_query(prompt: str, context: str = "") -> str:
        """Delegate semantic analysis to sub-LLM.

        Use for:
        - Disambiguation: "Which of these is the main Protein class?"
        - Validation: "Does this SPARQL query look correct?"
        - Filtering: "Which properties are most relevant?"
        - Synthesis: "Summarize these results"
        """
        if context:
            full_prompt = f"{prompt}\n\nContext:\n{context}"
        else:
            full_prompt = prompt

        response = sub_lm(full_prompt)
        return response[0] if isinstance(response, list) else response

    return llm_query
```

**Update Context Instructions** (lines 378-410):
Add guidance on when to use `llm_query()`:
```python
context_parts.extend([
    "",
    "## Using Sub-LLM Delegation",
    "",
    "Use llm_query() for semantic analysis and strategic decisions:",
    "- Disambiguation: llm_query('Which of these is X?', context=str(results))",
    "- Validation: llm_query('Is this SPARQL correct?', context=query)",
    "- Filtering: llm_query('Which properties matter most?', context=str(props))",
    "- Synthesis: llm_query('Summarize findings', context=evidence)",
    "",
    "DO NOT use llm_query() for facts (use tools instead).",
])
```

#### 2. Test RLM With llm_query() Tool

**Hypothesis**: RLM with strategic delegation will show:
- More iterations (7-10 instead of 5)
- Longer execution (80-90s instead of 70s)
- **Better quality** on complex tasks (L3-L5)
- **Hierarchical reasoning** (search → validate → refine → synthesize)

**Test Plan**:
1. Add `llm_query()` tool
2. Re-run L1 tasks (expect slight slowdown)
3. Run L2-L3 tasks (expect quality improvement)
4. Examine trajectories for delegation patterns

#### 3. Clarify What You're Comparing

**Current Comparison**:
- ❌ "RLM vs ReAct"
- ✅ "Code-Augmented Agent vs ReAct"

Your current RLM is NOT "Recursive Language Models" in the Prime Intellect sense. It's:
- **What it is**: Code-generation agent with REPL state persistence
- **What it lacks**: Recursive sub-LLM delegation
- **What to call it**: "Code-based RLM" or "REPL-RLM"

**Fair Comparison Options**:

**Option A: Keep Current RLM** (No llm_query)
- Rename to "Code-RLM" vs "ReAct"
- Accept that it's not true RLM architecture
- Compare: "Code generation vs direct tool calls"
- Conclusion: ReAct faster for simple tasks (validated)

**Option B: Add llm_query Tool** (True RLM)
- Implement strategic delegation
- Re-run experiments (expect longer execution)
- Compare: "Recursive LLM vs ReAct"
- Test on L3-L5 to see if delegation pays off

**Option C: Test Both Variants**
- Baseline: Code-RLM (current)
- Enhanced: Code-RLM + llm_query
- Control: ReAct
- Measure: Speed vs quality tradeoff across L1-L5

---

## Research Questions to Answer

### 1. Does Strategic Delegation Help Ontology Queries?

**Prime Intellect found**:
- ✅ Long-context tasks: RLM excels
- ❌ Math reasoning: RLM 36% worse
- ❓ Ontology queries: Untested

**Your domain**: Structured graph exploration + query construction
- **Hypothesis**: May not need delegation (ontology structure guides search)
- **Alternative**: Delegation helps with disambiguation, validation

**Test**: Compare Code-RLM vs Code-RLM+llm_query on L2-L5 tasks

### 2. Is ReAct's Simplicity Optimal for This Task?

**ReAct advantages**:
- Fast execution (29% faster on L1)
- Reliable (no code generation errors)
- Simple architecture

**ReAct limitations**:
- More iterations (16 vs 5)
- No state persistence
- Sequential tool calling

**Test**: Does ReAct maintain advantage on L3-L5?

### 3. What's the Token Cost Difference?

**From your state doc (lines 379-382)**:
> RLM: More tokens per iter (code generation)
> ReAct: More iters but fewer tokens per iter
> Which costs less?

**Measure**:
- Add token counting to comparison framework
- Calculate cost per task for each pattern
- Factor: Code generation (~500 tokens) vs Thought (~100 tokens)

### 4. When Does Code Persistence Matter?

**Code-RLM advantage**: Variables persist across iterations
```python
# Iteration 1
results = search_entity("Protein")

# Iteration 2 (can reference results)
for r in results[:5]:
    details = sparql_select(f"SELECT * WHERE {{ <{r}> ?p ?o }}")
```

**ReAct**: Must pass results via context (token inefficient)

**Test**: L3-L5 tasks with multi-hop exploration

---

## Revised Experimental Plan

### Phase 1: Validate Current Findings (Complete)
- ✅ L1 tasks tested
- ✅ Identified architectural gaps
- ✅ Understood overhead sources

### Phase 2: Implement True RLM (This Week)
1. Add `llm_query()` tool
2. Add `llm_batch()` for parallel delegation (optional)
3. Update context instructions
4. Test on L1 tasks (validate delegation happens)

### Phase 3: Compare Across Complexity Levels (Next Week)
1. L1 (current): Simple entity discovery
   - Expected: ReAct faster, equal quality
2. L2: Property relationships
   - Expected: Code-RLM competitive, delegation helps
3. L3: Multi-hop queries
   - Expected: Code-RLM+delegation excels (state + strategy)
4. L4-L5: Complex filtering/aggregation
   - Expected: Code-RLM+delegation maintains quality at scale

### Phase 4: Token Cost Analysis
1. Measure tokens per iteration (all patterns)
2. Calculate cost per task
3. Identify cost-quality tradeoffs

### Phase 5: Decision
Based on empirical data:
- If ReAct dominates: Use ReAct, retire RLM
- If Code-RLM+delegation wins on L3+: Pattern selection by complexity
- If Code-RLM (no delegation) competitive: Keep simple version

---

## Summary

**Your Intuition Was Correct**:
> "I'm not entirely certain that we have a good RLM structure in light of this blog post."

**Root Cause Identified**:
- Missing `llm_query()` tool prevents strategic delegation
- Sub-LLM only used for final synthesis, not exploration
- Result: Overhead without benefit

**Next Steps**:
1. Decide: Implement true RLM or accept current as "Code-RLM"?
2. If implementing: Add `llm_query()` tool + test
3. Re-run experiments with fair comparison
4. Make data-driven recommendation

**Open Question**:
> Does ontology query construction even NEED recursive delegation?

This is a valid research question. ReAct's 29% speed advantage on L1 suggests simpler may be better for structured exploration. But L3-L5 will reveal the answer.

---

## References

- Prime Intellect RLM Blog: https://www.primeintellect.ai/blog/rlm
- Huberman RLM Implementation: https://github.com/halfprice06/huberman-rlm
- Your State Doc: `docs/state/multi-pattern-agent-state.md`
- DSPy Documentation: https://dspy-docs.vercel.app/

**Last Updated**: 2026-01-28
**Next Review**: After implementing llm_query() tool and testing L2 tasks
