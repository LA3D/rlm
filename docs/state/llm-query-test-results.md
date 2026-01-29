# llm_query() Test Results

**Date**: 2026-01-28
**Test Run**: Initial integration test with PROV ontology

---

## Key Discovery: llm_query is BUILT-IN to DSPy RLM

**Critical Finding**: We don't need to add `llm_query()` - **it's already a built-in DSPy RLM function!**

From DSPy source (`dspy/predict/rlm.py`):
```python
# Built-in tools:
- llm_query(prompt) - query a sub-LLM (~500K char capacity) for semantic analysis
- llm_query_batched(prompts) - query multiple prompts concurrently
```

**Impact**: Your RLM implementation has ALWAYS had strategic sub-LLM delegation available.

---

## Test Results

### Configuration
- **Query**: "What is Activity in this ontology?"
- **Ontology**: PROV (prov.ttl)
- **Max Iterations**: 6
- **Verbose**: True

### Performance Metrics
- **Time**: 50.3 seconds
- **Iterations**: 4
- **Converged**: True ✅
- **llm_query calls**: 0 (not used)

### Model Behavior

**Iterations**:
1. **Search**: `search_entity("Activity", limit=10)` → Found prov:Activity
2. **Detail Query**: SPARQL for Activity properties and definition
3. **Relationship Query**: SPARQL for domain/range properties, subclasses
4. **Synthesis**: Constructed comprehensive answer with evidence

**Pattern**: Linear exploration (search → query → query → submit)
- No strategic delegation to sub-LLM
- All work done by main model
- Same pattern observed in state doc analysis

---

## Why llm_query Wasn't Used

**Expected behavior** per Prime Intellect research:

> "Models without explicit training in RLM usage underutilized sub-LLMs, even when given tips... true potential of RLM will be unleashed after training via RL"

**Reasons**:
1. **No RL training**: Model hasn't been trained on delegation patterns
2. **Simple task**: L1 query (entity discovery) may not need delegation
3. **Direct tools work**: search_entity + sparql_select sufficient
4. **Cost-benefit**: Model may optimize for speed over delegation

**This is NOT a bug** - it's documented baseline behavior.

---

## What We Learned

### 1. Architecture Was Already Complete

Your state document concern: "Is RLM missing strategic delegation?"

**Answer**: NO - llm_query was always available (DSPy built-in)

**Implication**: Your "flat, linear pattern" is due to:
- ✅ Model behavior (not using available delegation)
- ❌ NOT missing architecture

### 2. Current RLM is "Code-RLM" Not "Trained RLM"

Your implementation:
- ✅ Persistent REPL (state across iterations)
- ✅ Code generation with tool access
- ✅ Sub-LLM delegation available (llm_query built-in)
- ❌ Model doesn't use delegation spontaneously

**Classification**: Untrained RLM (has tools, doesn't use strategically)

### 3. Performance Pattern Confirmed

**From state doc**:
- RLM: 5 iterations, 70.9s
- ReAct: 16 iterations, 55.6s (29% faster)

**This test**:
- RLM: 4 iterations, 50.3s (faster than before!)

**Possible reasons for speed**:
- PROV ontology simpler than UniProt
- Clearer structure (AGENT_GUIDE may exist)
- Lucky trajectory (fewer iterations)

---

## Architectural Implications

### Prime Intellect RLM vs Your RLM

| Aspect | Prime Intellect | Your Implementation | Status |
|--------|-----------------|---------------------|---------|
| **Persistent REPL** | ✅ Yes | ✅ Yes | Same |
| **llm_query available** | ✅ Built-in | ✅ Built-in (DSPy) | Same |
| **Tools to main model** | ❌ Restricted | ✅ Direct access | **Different** |
| **Model uses llm_query** | ⚪ With training | ⚪ Without training | Same baseline |
| **Delegation patterns** | Trained behavior | Spontaneous (rare) | Expected |

**Key Difference**: Prime Intellect restricts tools to sub-LLMs only. Your RLM gives main model direct tool access.

**Impact**: Your pattern is **"tool-first, delegate-if-needed"** vs Prime's **"delegate-always"**

---

## Comparison: Your RLM vs Prime Intellect RLM

### Your Pattern (Observed)
```python
# Iteration 1: Main model searches directly
results = search_entity("Activity")

# Iteration 2: Main model queries directly
props = sparql_select(query)

# Iteration 3: Main model analyzes directly
relationships = sparql_select(query2)

# Iteration 4: Main model synthesizes
SUBMIT(answer=..., evidence=...)
```

**Characteristics**:
- Fast (4 iterations, 50s)
- Direct (no sub-LLM overhead)
- Effective (good quality answer)
- Linear (no hierarchical reasoning)

### Prime Intellect Pattern (Trained)
```python
# Iteration 1: Delegate search interpretation
results = search_entity("Activity")
best = llm_query("Which is the main Activity class?", str(results))

# Iteration 2: Delegate validation
is_valid = llm_query("Is this SPARQL correct?", query)
props = sparql_select(query) if is_valid else ...

# Iteration 3: Delegate filtering
important = llm_query("Which properties matter most?", str(props))

# Iteration 4: Delegate synthesis
answer = llm_query("Explain Activity", str(evidence))
```

**Characteristics**:
- Slower (more iterations, delegation overhead)
- Strategic (hierarchical decisions)
- Token-efficient (main model stays light)
- Trained (requires RL to learn pattern)

---

## Answer to State Doc Concerns

### Concern 1: "Is RLM Too Flat?" (Lines 201-238)

**Answer**: Yes, but not due to missing architecture.

**Root Cause**: Model behavior, not missing tools
- llm_query was always available
- Model chooses not to use it
- Needs training or explicit guidance

**Solution Options**:
1. Accept baseline (test if it matters on L3-L5)
2. Try explicit prompting ("Use llm_query to validate")
3. Add exemplar memories showing delegation
4. Train with RL (long-term)

### Concern 2: "Sub-LLM Usage" (Lines 240-253)

**Answer**: Your hypothesis was correct!

**Quote from state doc**:
> "Should sub-LLM be used for STRATEGIC decisions during exploration?"

**Answer**: Yes! And llm_query IS available for this.

**But**: Model needs to learn WHEN to delegate (training issue, not architecture)

### Concern 3: "ReAct Iteration Mystery" (Lines 255-264)

**Answer**: Still unresolved (different question)

Need to investigate DSPy ReAct source separately.

---

## Updated Hypotheses

### Original Hypothesis 1: RLM Excels at Complex Tasks

**Status**: Still testable

**Test**: Run L2-L3 tasks and see if:
- Model spontaneously uses llm_query (unlikely)
- State persistence provides value
- Code composition helps

### Original Hypothesis 2: Sub-LLM Should Be Strategic

**Status**: ✅ CONFIRMED available, ⚪ not used

**Findings**:
- llm_query IS available for strategic use
- Model doesn't use it spontaneously
- Needs training or prompting

### New Hypothesis 5: Direct Tools Are Sufficient

**Status**: To test

**Claim**: For ontology queries, direct tool access (your pattern) may be optimal.

**Evidence**:
- Fast execution (50s)
- Good quality (comprehensive answer)
- Simple architecture (no delegation overhead)

**Test**: Compare quality on L2-L3 tasks

---

## Next Steps (Revised)

### Immediate (Today) - DONE ✅

1. ✅ Verified llm_query is built-in (DSPy native)
2. ✅ Confirmed model doesn't use it spontaneously
3. ✅ Documented baseline behavior

### Short-term (This Week)

4. **Test with explicit prompt**
   ```python
   run_dspy_rlm(
       "What is Activity? Use llm_query to validate your findings.",
       "ontology/prov.ttl"
   )
   ```

5. **Test L2 task** (property relationships)
   - More complex query
   - See if delegation emerges naturally
   - Compare quality with/without delegation

6. **Compare three patterns**:
   - A. RLM (current, no delegation)
   - B. RLM (with explicit delegation prompt)
   - C. ReAct (baseline)

### Medium-term (Next Week)

7. **Test L3-L5 complexity**
   - Multi-hop queries
   - Complex filtering
   - Aggregation

8. **Measure when delegation helps**
   - Quality improvement?
   - Speed tradeoff?
   - Token cost?

9. **Decision: Keep or simplify?**
   - If delegation never helps → Remove guidance, accept direct pattern
   - If delegation helps L3+ → Document when to prompt
   - If neither matters → ReAct may be optimal

---

## Recommendations

### 1. Update State Document

Key findings to add:
- ✅ llm_query was always available (DSPy built-in)
- ✅ "Flat pattern" is model behavior, not missing architecture
- ✅ Current RLM has all Prime Intellect tools
- ⚪ Model needs training/prompting to use delegation

### 2. Update Architecture Comparison

Clarify:
- Your RLM = "Untrained Code-RLM with delegation available"
- Prime RLM = "Trained Code-RLM with forced delegation"
- Key difference: tool access pattern + training

### 3. Fair Comparison Strategy

**Option A: Accept Baseline** (Simplest)
- Test current RLM (no delegation) vs ReAct
- Measure: speed, quality, token cost
- Conclusion: Does simple pattern suffice?

**Option B: Force Delegation** (Most comparable)
- Restrict main model tools (only llm_query)
- Force Prime Intellect architecture
- Compare delegated-RLM vs ReAct

**Option C: Test Both** (Most thorough)
- Baseline RLM (no delegation)
- Prompted RLM (with delegation)
- ReAct (control)
- Measure across L1-L5

**Recommendation**: Start with Option A (baseline), move to C if needed

---

## Key Insights

### 1. You Had True RLM All Along

Your concern: "I'm not entirely certain that we have a good RLM structure"

**Reality**: Your structure was always complete.
- ✅ Persistent REPL
- ✅ Code generation
- ✅ Sub-LLM delegation (llm_query built-in)
- ✅ Tool surface

**What's "missing"**: Model training on when to delegate

### 2. Direct Tool Access May Be Better

Prime Intellect restricts tools to sub-LLMs. You give main model direct access.

**Your pattern** (tool-first):
- Faster (no delegation overhead)
- Simpler (linear reasoning)
- Effective (good results)

**Prime pattern** (delegate-first):
- Slower (delegation overhead)
- Strategic (hierarchical)
- Trained (requires RL)

**Question**: Is delegation worth the overhead for ontology queries?

### 3. Simple May Be Optimal

**Occam's Razor**: Your "flat" pattern may be optimal for this task.

**Evidence**:
- 4 iterations, 50s (faster than before)
- Comprehensive answer (good quality)
- No delegation needed (task solvable directly)

**Test**: Does complexity matter on L2-L3?

---

## Files Generated

- `test_llm_query_trajectory.jsonl` - Full event log
- `test_llm_query_summary.txt` - Human-readable summary
- `docs/state/llm-query-test-results.md` - This analysis

---

## Summary

✅ **llm_query is built-in** to DSPy RLM (was always available)

⚪ **Model doesn't use it** spontaneously (expected without training)

✅ **Test successful**: 4 iterations, 50s, converged, good quality

🎯 **Key finding**: Your RLM architecture was complete. "Flat pattern" is model behavior, not missing tools.

📊 **Next**: Test if delegation matters on L2-L3 complexity

---

**Last Updated**: 2026-01-28 11:15 EST
**Test Log**: `test_llm_query_trajectory.jsonl`
