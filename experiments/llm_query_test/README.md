# Testing llm_query() Integration

**Date**: 2026-01-28
**Purpose**: Verify that strategic sub-LLM delegation (llm_query) is working

---

## What We're Testing

We've added `llm_query()` tool to enable **true RLM architecture** where:
- Main model delegates semantic analysis to sub-LLM
- Sub-LLM handles disambiguation, validation, filtering
- Main model stays strategic (orchestrator role)

This addresses the "flat, linear pattern" issue identified in the state document.

---

## Step-by-Step Test Plan

### Step 1: Verify Integration (5 minutes)

Run the basic integration test:

```bash
cd /Users/cvardema/dev/git/LA3D/rlm
python test_llm_query_integration.py
```

**Expected Output**:
- ✅ Basic Integration: Tool is available
- ✅ Usage Analysis: Check if llm_query was called
- ⚪ Pattern Check: May be empty (model needs guidance)

**Key Question**: Did the model use `llm_query()` spontaneously?

### Step 2: Check Trajectory (5 minutes)

Open the trajectory log:

```bash
cat test_llm_query_trajectory.jsonl | grep -i "llm_query" | head -5
```

Look for:
- Code blocks containing `llm_query(` calls
- Strategic patterns (disambiguation, validation)
- Sub-LLM delegation happening during exploration (not just final synthesis)

### Step 3: Compare With/Without llm_query (10 minutes)

Create two configurations:

**A. With llm_query (current)**:
```python
from rlm_runtime.engine.dspy_rlm import run_dspy_rlm

result_with = run_dspy_rlm(
    "What is the Protein class?",
    "ontology/uniprot-core.ttl",
    max_iterations=8,
    log_path="with_llm_query.jsonl"
)
```

**B. Without llm_query (baseline)**:

Temporarily comment out in `dspy_rlm.py:341`:
```python
tools = {
    'search_entity': make_search_entity_tool(meta),
    'sparql_select': make_sparql_select_tool(meta),
    # 'llm_query': make_llm_query_tool(sub_lm)  # ← COMMENT THIS
}
```

Run again:
```python
result_without = run_dspy_rlm(
    "What is the Protein class?",
    "ontology/uniprot-core.ttl",
    max_iterations=8,
    log_path="without_llm_query.jsonl"
)
```

**Compare**:
- Iterations: with vs without
- Execution time: with vs without
- Quality: Are answers different?
- Patterns: Does delegation happen?

### Step 4: Examine Delegation Patterns (10 minutes)

If llm_query WAS used, examine HOW:

```bash
# Extract all llm_query calls from trajectory
grep -A 5 "llm_query" test_llm_query_trajectory.jsonl | less
```

Look for:
1. **When**: Which iteration number?
2. **Why**: What semantic task (disambiguation, validation, synthesis)?
3. **Context**: What data was passed to sub-LLM?
4. **Impact**: Did it change the exploration strategy?

---

## Expected Outcomes

### Scenario A: Model Uses llm_query Spontaneously

**Signs**:
- ✅ Trajectory shows `llm_query()` calls in iterations 2-4
- ✅ Strategic patterns visible (disambiguation, validation)
- ✅ Sub-LLM used DURING exploration, not just synthesis

**Interpretation**: Model learned delegation pattern (unlikely without training)

**Next Steps**:
- Compare performance on L2-L3 tasks
- Measure if quality improves on complex queries

### Scenario B: Model Doesn't Use llm_query (Most Likely)

**Signs**:
- ⚪ No `llm_query()` calls in trajectory
- ⚪ OR only called once at end (synthesis)
- ⚪ Pattern check shows no strategic delegation

**Interpretation**: Model needs explicit guidance (expected per Prime Intellect)

**Next Steps**:
1. Test with explicit prompt: "Use llm_query for disambiguation"
2. Add exemplar showing delegation pattern
3. Accept that benefit may only appear on L3-L5 complexity

### Scenario C: Model Uses llm_query But Wrong

**Signs**:
- ⚠️  llm_query called for facts (should use search_entity)
- ⚠️  llm_query called for simple operations (should use Python)
- ⚠️  Excessive delegation (every decision)

**Interpretation**: Model misunderstands when to delegate

**Next Steps**:
- Improve context guidance (examples of good vs bad delegation)
- Add negative examples to prevent misuse

---

## Measuring Success

### Metric 1: Delegation Frequency

**Without llm_query**: 0 delegations
**With llm_query (baseline)**: 0-1 delegations (synthesis only)
**With llm_query (strategic)**: 2-4 delegations (during exploration)

### Metric 2: Delegation Quality

**Good delegation**:
- Disambiguation: "Which of these 5 results is the main Protein class?"
- Validation: "Does this SPARQL query have syntax errors?"
- Filtering: "Which 3 properties are most important?"

**Bad delegation**:
- Facts: "What is RDF?" (use search_entity)
- Counting: "How many results?" (use Python len())
- General knowledge: "Explain ontologies" (irrelevant)

### Metric 3: Task Performance

Compare on same L1 task:
- **Speed**: May be slower with delegation (overhead)
- **Quality**: Should be equal or better
- **Iterations**: May change (strategic vs linear)

---

## Troubleshooting

### Issue: llm_query not available

**Symptom**: Error "llm_query is not defined"

**Fix**:
1. Verify `delegation_tools.py` exists
2. Check import in `dspy_rlm.py` line 199
3. Verify tool added to dict at line 341

### Issue: llm_query never called

**Symptom**: Trajectory shows no usage

**Possible Causes**:
1. Model doesn't know when to use it (add examples)
2. Task too simple (doesn't need delegation)
3. Model prefers direct tools (acceptable)

**Not a Bug**: Prime Intellect found models need RL training for effective delegation

### Issue: llm_query fails during execution

**Symptom**: Error during sub-LLM call

**Check**:
1. API key set: `echo $ANTHROPIC_API_KEY`
2. Sub-model valid: Default is `claude-3-5-haiku-20241022`
3. Context not too long: Truncates at 4000 chars

---

## What's Next?

### If llm_query Works:
1. Test on L2 tasks (property relationships)
2. Measure delegation patterns across complexity
3. Compare RLM (with delegation) vs ReAct baseline

### If llm_query Doesn't Get Used:
1. Try explicit prompting: "Use llm_query to validate findings"
2. Add exemplar memory showing delegation pattern
3. Accept baseline behavior, test on L3-L5 to see if it emerges

### Regardless:
1. Document findings in state doc
2. Update architecture comparison analysis
3. Run fair comparison: RLM+delegation vs RLM-baseline vs ReAct

---

## Files Created

- `rlm_runtime/tools/delegation_tools.py` - llm_query implementation
- `test_llm_query_integration.py` - Integration test
- `experiments/llm_query_test/README.md` - This guide

## Next Steps

After basic test:
1. Review trajectory to understand behavior
2. Decide: Keep, improve, or revert llm_query
3. Run structured comparison (with/without/react)
4. Update state document with findings
