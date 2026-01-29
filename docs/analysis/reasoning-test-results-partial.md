# Reasoning Test Results (Partial)

**Date**: 2026-01-28
**Status**: Incomplete (2/5 queries completed, 1 failed, 2 not run)
**Finding**: L3 complexity increases cost 2-3x, still NO delegation

---

## Executive Summary

Testing L3-L4 reasoning queries to see if complexity triggers delegation. **Results so far:**

- ✅ **L3-1** (multi-entity): Completed, $0.27, 10 iterations, **0 delegation**
- ✅ **L3-2** (multi-hop): Completed, $0.35, 11 iterations, **0 delegation**
- ❌ **L4-1** (spatial): Failed - model refused to generate code (content safety filter)
- ⚪ **L3-3** (comparison): Not run
- ⚪ **L4-2** (integration): Not run

**Key findings:**
1. **No delegation on L3 queries** - Tool-first pattern continues
2. **Cost increased 2-3x** ($0.27-0.35 vs $0.11-0.13 for L1-L2)
3. **More exploration needed** (10-12 search calls vs 1-2 for L1-L2)
4. **L3-2 exceeded ReAct baseline** ($0.35 > $0.27)
5. **Content safety issue** on spatial reasoning query

---

## Detailed Results

### L3-1: Multi-Entity Coordination ✅

**Query**: "Find reviewed human proteins with kinase activity"

**Complexity**: Coordinate 4 concepts (human + reviewed + kinase + GO hierarchy)

**Results**:
- **Time**: 123.5s
- **Iterations**: 9/15 (converged)
- **Tool calls**: 19 (12 search + 6 SPARQL + 1 llm_query)
- **Tokens**: 64,378 (57K input / 7K output)
- **Cost**: $0.2736
- **Delegation**: 0 attempts (llm_query in tool list but not used)

**Pattern**:
```
12x search_entity: Explored 'kinase', 'activity', 'human', 'reviewed', 'organism', 'homo sapiens', '9606', 'GO_'
6x sparql_select: Query construction and validation
1x llm_query: Listed but not executed
→ SUBMIT
```

**Cost breakdown**:
- L1-L2 baseline: $0.11-0.13
- This query: $0.27
- **Increase: 2x more expensive**

**Why more expensive?**
- More exploration (12 search vs 1-2)
- More SPARQL queries (6 vs 5-6, but similar)
- More iterations (9 vs 5-7)
- Model struggled to find GO term for "kinase activity"

**Answer quality**: 535 chars, mentions GO:0016301, taxon:9606, up:reviewed true - correct concepts

---

### L3-2: Multi-Hop Annotation ✅

**Query**: "What diseases involve enzymes located in mitochondria?"

**Complexity**: Navigate 2 annotation paths (disease + location) with transitive hierarchy

**Results**:
- **Time**: 127.5s
- **Iterations**: 11/15 (did NOT converge!)
- **Tool calls**: 21 (7 search + 14 SPARQL)
- **Tokens**: 85,301 (77K input / 8K output)
- **Cost**: $0.3492
- **Delegation**: 0 attempts

**Pattern**:
```
7x search_entity: Explored 'mitochondria', 'enzyme', 'disease', 'mitochondrial', 'location', 'cellular component', 'subcellular'
14x sparql_select: Heavy query exploration (2x more than L3-1)
→ SUBMIT (but marked as not converged?)
```

**Cost breakdown**:
- L1-L2 baseline: $0.11-0.13
- ReAct baseline: $0.27
- This query: $0.35
- **More expensive than ReAct!**

**Why so expensive?**
- Extensive SPARQL exploration (14 queries)
- Larger token usage (85K vs 64K for L3-1)
- Did not converge within budget
- Model struggled to find mitochondria location URI

**Answer quality**: 1183 chars, discusses schema structure but seems more conceptual than concrete

---

### L4-1: Spatial Reasoning ❌

**Query**: "Find diseases caused by natural variants in enzyme active sites"

**Complexity**: Position overlap reasoning with FALDO ontology

**Result**: **FAILED**

**Error**:
```python
ValueError: Model refused to generate code for this query.
This may be due to content safety filters.
Try rephrasing the query to avoid potentially sensitive terms.

Original error: 'NoneType' object has no attribute 'strip'
```

**Root cause**: Model returned `None` for code generation, likely triggered by:
- "diseases" + "natural variants" + "enzyme active sites"
- Possible misinterpretation as genetic engineering or biological weapon query
- Content safety filters blocked code generation

**Implications**:
- Need to rephrase sensitive queries
- Or handle model refusals gracefully
- This is a known DSPy RLM issue with certain terms

---

## Analysis

### 1. No Delegation on L3 Queries ⚪

**Expected**: L3 complexity might trigger `llm_query()` for:
- "What GO term is kinase activity?"
- "What location URI is mitochondria?"

**Actual**: 0 delegation attempts on both queries

**Why?**
- Model prefers extensive search over delegation
- 12 search calls to find concepts vs 1 llm_query call
- Tool-first pattern deeply ingrained
- Model doesn't recognize when delegation would help

**Conclusion**: Tool-first pattern persists even on L3 complexity

---

### 2. Cost Scales Badly with Complexity ⚠️

**Cost progression**:
- L1: $0.11-0.13 per query
- L2: $0.11-0.13 per query
- L3-1: $0.27 per query (2x increase)
- L3-2: $0.35 per query (3x increase, **exceeds ReAct**)

**Why?**
1. **More exploration** - 10-12 search calls vs 1-2
2. **More SPARQL queries** - 6-14 vs 5-6
3. **More iterations** - 9-11 vs 5-7
4. **Context growth** - 64K-85K tokens vs 23K-26K

**Problem**: L3-2 query cost $0.35 > ReAct baseline $0.27

**This defeats the purpose of RLM cost optimization!**

---

### 3. Excessive Search Without Strategy 🔴

**L3-1 search pattern** (12 searches):
```
search('kinase activity') → 0 results
search('kinase') → try again
search('human') → try again
search('reviewed') → try again
search('protein') → try again
search('activity') → try again
search('organism') → try again
search('kinase') → repeated!
search('homo sapiens') → try again
search('9606') → finally found taxon
```

**Problem**: Brute-force exploration without learning

**What delegation could have done**:
```python
# Instead of 12 searches:
go_term = llm_query("What is the GO term for kinase activity? Answer with just the GO ID.")
# → "GO:0016301"
```

**Cost comparison**:
- 12 search calls: ~$0.10 in wasted exploration
- 1 llm_query call: ~$0.01 (Haiku)
- **Delegation would save 90% of exploration cost!**

---

### 4. Model Doesn't Learn from AGENT_GUIDE.md 🔴

**AGENT_GUIDE.md contains**:
- GO term examples: `GO:0016301` for kinase activity
- Taxonomy: `taxon:9606` for human
- Review status: `up:reviewed true`
- Example queries showing these patterns

**Model behavior**:
- Searched for all concepts individually
- Didn't consult examples first
- Brute-force exploration instead of pattern application

**Why?**
- AGENT_GUIDE.md may be too long (11K chars)
- Model doesn't prioritize examples
- No explicit instruction to "check guide first"

---

### 5. Content Safety Blocks L4 Query ❌

**Failed query**: "Find diseases caused by natural variants in enzyme active sites"

**Issue**: Combination of terms triggered safety filter

**Workaround**: Rephrase to avoid trigger terms
- Instead of "diseases caused by variants"
- Try "diseases associated with variants" or "diseases linked to sequence changes"

---

## Comparison to L1-L2 Baseline

| Metric | L1-L2 | L3-1 | L3-2 | Change |
|--------|-------|------|------|--------|
| **Cost** | $0.12 | $0.27 | $0.35 | **+125-192%** |
| **Iterations** | 5-7 | 9 | 11 | +40-80% |
| **Tool calls** | 7 | 19 | 21 | +170-200% |
| **Search calls** | 1-2 | 12 | 7 | +250-500% |
| **Delegation** | 0 | 0 | 0 | None |
| **vs ReAct** | Cheaper | Comparable | **MORE EXPENSIVE** | ❌ |

**Critical finding**: L3-2 cost ($0.35) exceeds ReAct baseline ($0.27)!

---

## Why Did Delegation NOT Emerge?

### Hypothesis 1: Model Optimization Failure ❌

**Expected**: Model recognizes when semantic disambiguation saves time

**Actual**: Model prefers brute-force search over strategic delegation

**Evidence**:
- 12 search calls for "kinase activity" vs 1 llm_query
- Repeated searches (searched 'kinase' twice)
- No learning from failed searches

**Conclusion**: Model not trained to use delegation strategically

---

### Hypothesis 2: AGENT_GUIDE.md Too Long ❌

**Size**: 11K characters
**Location**: Front of context
**Problem**: Model may not reference it during iteration

**Test needed**: Inject examples in system prompt vs front of context

---

### Hypothesis 3: Tool-First Bias Too Strong ✅

**Training**: Sonnet 4.5 trained on code generation patterns
**Behavior**: Prefers direct tool calls over delegation
**Result**: Never considers delegation as option

**Evidence**:
- 0 delegation on any query tested (L1, L2, L3)
- Even when it would save cost
- Even when it would save iterations

**Conclusion**: Tool-first is default pattern, delegation not considered

---

## Recommendations

### 1. Add Explicit Delegation Prompting 🔧

**Current**: llm_query available but never suggested

**Proposed**: Add delegation guidance:
```python
"When exploring unfamiliar concepts:
1. First check AGENT_GUIDE.md examples
2. If not found, try search_entity (1-2 attempts max)
3. If still not found, use llm_query for disambiguation:
   llm_query('What is the GO term for kinase activity?')
"
```

### 2. Limit Search Attempts 🔧

**Current**: Unlimited search attempts

**Proposed**:
- Max 3 search attempts per concept
- After 3 failures, require llm_query or move on
- Track search history to avoid repeats

### 3. Prioritize AGENT_GUIDE.md Consultation 🔧

**Current**: Guide injected but not explicitly referenced

**Proposed**:
- Add instruction: "FIRST consult AGENT_GUIDE.md examples"
- Show example: "Search for GO:0016301 in examples before searching ontology"
- Track if model referenced guide

### 4. Rephrase Sensitive Queries 🔧

**Blocked**: "diseases caused by variants in active sites"

**Alternatives**:
- "diseases associated with sequence variants"
- "proteins with disease-linked mutations"
- Avoid "caused by" + medical terms

### 5. Accept Higher Cost for L3+ ⚠️

**Reality**: L3 queries may cost $0.25-0.35

**Options**:
- Accept cost (still fast, good quality)
- Use delegation to reduce exploration
- Use ReAct for L3+ (simpler, comparable cost)

---

## Next Steps

### Immediate: Fix L4-1 Query

Rephrase to avoid content safety trigger:
```python
# Instead of:
"Find diseases caused by natural variants in enzyme active sites"

# Try:
"Find disease-associated sequence variants that overlap with catalytic residues"
```

### Short-term: Test Delegation Prompting

Add explicit delegation guidance and re-run:
- Does it trigger llm_query usage?
- Does cost decrease?
- Does quality improve?

### Long-term: Compare to ReAct on L3+

Since L3-2 costs more than ReAct, test:
- ReAct on same L3 queries
- Compare cost, quality, convergence
- Determine which pattern for which complexity

---

## Conclusions

### 1. Tool-First Pattern Persists ⚪

**No delegation on L3 queries** despite increased complexity

**Why?**
- Model not trained on delegation patterns
- Tool-first bias too strong
- No explicit guidance to delegate

### 2. Cost Scales Poorly ❌

**L3 queries cost 2-3x more** than L1-L2

**L3-2 exceeds ReAct baseline** ($0.35 > $0.27)

**Why?**
- Excessive brute-force exploration
- No strategic delegation to shortcut search
- Context growth from failed attempts

### 3. Delegation Would Help 💡

**12 search attempts** for "kinase activity" could be replaced by **1 llm_query call**

**Estimated savings**: 90% of exploration cost

**But model doesn't recognize this opportunity**

### 4. Need Explicit Delegation Training ⚠️

**Current**: llm_query available but never used

**Needed**: Explicit prompts + examples showing when to delegate

**Alternative**: Use ReAct for L3+ (simpler pattern, comparable cost)

---

## Files

- Logs: `experiments/reasoning_test/l3-1_test.jsonl`, `l3-2_test.jsonl`
- Test script: `experiments/reasoning_test/run_reasoning_test.py`
- Analysis tool: `experiments/reasoning_test/analyze_trajectory.py`

**Last Updated**: 2026-01-28 12:35 EST
