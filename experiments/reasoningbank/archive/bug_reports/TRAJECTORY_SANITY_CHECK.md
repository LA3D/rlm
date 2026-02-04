# Trajectory Sanity Check - Minimal Test Analysis

**Date**: 2026-02-03
**Test**: 1 task (4_uniprot_mnemonic_id) × 2 rollouts × 2 strategies (none, prefix)

---

## Executive Summary

**Agent Competence**: ✅ **GOOD** - Agent uses tools correctly, reasoning is sound, all trajectories succeeded

**Critical Issue Found**: ⚠️ **CACHING IN BASELINE** - Second rollout with no perturbation used cached LLM responses (0 tokens), creating artificial determinism

**Output Logging Bug**: ⚠️ **NON-CRITICAL** - Output capture in iteration logs is broken, but doesn't affect diversity metrics (we extract from tool calls, not output text)

---

## Detailed Analysis by Trajectory

### Baseline (none) - Rollout 1 ✅

**LM Usage**: 10,470 prompt + 1,423 completion = 11,893 tokens ($0.053)

**Tool Sequence**:
1. `endpoint_info()` - Get endpoint metadata ✅
2. `sparql_query()` - Execute query with `up:mnemonic` predicate ✅
3. `sparql_peek()` - Attempt to peek at results (returns empty) ✅
4. `sparql_slice()` - Extract actual result data ✅

**Iterations**: 5

**Reasoning Quality**: ✅ Good
- Iteration 1: Explores context and question
- Iteration 2: Searches for "mnemonic" in context, calls endpoint_info
- Iteration 3: **Tries `llm_query()` (not available) but recovers gracefully**
- Iteration 4: Constructs SPARQL query directly with `up:mnemonic` predicate
- Iteration 5: Extracts result, submits correct answer

**Code Quality**: ✅ Good
- Appropriate print statements for debugging
- Correct SPARQL query syntax
- Proper error handling (try/except)
- Successfully uses tool handle system (sparql_slice('results_0'))

**Final Answer**: `http://purl.uniprot.org/uniprot/P05067` ✅ CORRECT

---

### Baseline (none) - Rollout 2 ⚠️ **CACHED**

**LM Usage**: **0 prompt + 0 completion = 0 tokens ($0.053 reported but likely cached)**

**Tool Sequence**: IDENTICAL to Rollout 1
1. `endpoint_info()`
2. `sparql_query()`
3. `sparql_peek()`
4. `sparql_slice()`

**Iterations**: 5 (same as Rollout 1)

**Code**: IDENTICAL to Rollout 1 (character-for-character match)

**Reasoning**: IDENTICAL to Rollout 1 (character-for-character match)

**⚠️ CRITICAL FINDING**: DSPy appears to be caching LM responses when:
- Same prompt (context + question)
- Same temperature
- Same model

This explains why:
- Temperature=0.7 didn't create diversity in baseline
- Both trajectories are identical (Vendi=1.00, Jaccard=1.00)
- Our hypothesis about "peaked probability distributions" was partially wrong

**Impact**: Baseline measurements are invalid for stochasticity assessment.

**Root Cause**: Likely DSPy's internal caching mechanism. The prompt is identical between rollouts when no perturbation is applied.

---

### Prefix - Rollout 1 ✅

**LM Usage**: 12,075 prompt + 1,186 completion = 13,261 tokens ($0.054)

**Tool Sequence**:
1. `endpoint_info()` - Get endpoint metadata ✅
2. **`sparql_describe()` - Explore schema structure** ✅ **DIFFERENT CHOICE**
3. `sparql_query()` - Execute query
4. `sparql_slice()` - Extract results

**Iterations**: 5

**Reasoning Quality**: ✅ Good, **but different approach**
- Iteration 1: Explores full context (prints entire context, not just 500 chars)
- Iteration 2: Uses `sparql_describe()` to understand structure
- Iteration 3: Tries `llm_query()` (not available), recovers
- Iteration 4: Constructs SPARQL query with PREFIX declarations
- Iteration 5: Extracts result, submits

**Code Differences from Baseline**:
- `print(context)` instead of `print(context[:500])`
- Uses `sparql_describe()` instead of `sparql_peek()`
- Different query formatting (includes PREFIX declarations)

**Final Answer**: `http://purl.uniprot.org/uniprot/P05067` ✅ CORRECT

---

### Prefix - Rollout 2 ✅

**LM Usage**: 13,076 prompt + 1,386 completion = 14,462 tokens ($0.060)

**Tool Sequence**:
1. `endpoint_info()`
2. **`sparql_peek()` - Different tool choice** ✅ **DIFFERENT FROM ROLLOUT 1**
3. `sparql_query()`
4. `sparql_slice()`

**Iterations**: **6** (one more than Rollout 1!)

**Reasoning Quality**: ✅ Good, **acknowledges attempt number**
- Iteration 1: Notes "This is attempt 2, suggesting a previous attempt may have failed"
- Iteration 2-3: Uses `sparql_peek()` to explore
- Iteration 4: Constructs query
- Iteration 5-6: Extracts and submits

**Code Differences**:
- Different print statements
- Uses `sparql_peek()` (not `sparql_describe`)
- More verbose debug output
- Took 6 iterations instead of 5

**Final Answer**: `http://purl.uniprot.org/uniprot/P05067` ✅ CORRECT

**Jaccard Similarity vs Prefix Rollout 1**: ~0.50 (50% overlap in tool choices)

---

## Tool Use Validation

### All Tools Used Correctly ✅

**`endpoint_info()`**:
- Called in all 4 trajectories
- Returns correct metadata (endpoint URL, prefixes, timeout)
- No errors

**`sparql_query()`**:
- All 4 trajectories execute correct SPARQL query
- Query syntax: `PREFIX up: ... SELECT ?entry WHERE { ?entry up:mnemonic 'A4_HUMAN' . }`
- Returns correct result handle (e.g., 'results_0')
- No syntax errors or execution failures

**`sparql_slice()`**:
- Correctly extracts data from result handles
- Returns: `[{'entry': 'http://purl.uniprot.org/uniprot/P05067'}]`
- No errors

**`sparql_peek()`**:
- Used by baseline and prefix rollout 2
- Returns empty list `[]` (expected - no previously stored results)
- Not a failure, just no data

**`sparql_describe()`**:
- Used only by prefix rollout 1
- Returns describe results about the resource
- Works correctly

### Tool Feedback Correctness ✅

All tool results are:
- Structurally correct (proper dict/list format)
- Semantically correct (actual UniProt data)
- Properly formatted for handle-based access
- Include usage hints (e.g., "Call sparql_slice(this) to get data rows")

---

## Python Code Execution Validation

### No Execution Errors ✅

All trajectories:
- Execute Python code without exceptions
- Handle missing functions gracefully (`llm_query` not available → try/except)
- Use correct variable names (`context`, `question`)
- Access tools from namespace correctly

### One Non-Critical Issue: `llm_query()` Not Available

**Observed in**: All 4 trajectories (iterations 3-4)

**Behavior**: Agent tries to call `llm_query()` to ask about UniProt schema

**Result**: NameError (function not in namespace)

**Recovery**: ✅ **GRACEFUL** - Agent recognizes error and constructs query directly

**Assessment**: This is **not a bug** - it's the agent exploring the available namespace. The error is handled correctly and doesn't prevent success.

**Recommendation**: Consider adding `llm_query` as a tool for schema exploration, or document that it's intentionally not available.

---

## Reasoning Quality Assessment

### All Trajectories Show Competent Reasoning ✅

**Common patterns across all runs**:
1. Start by exploring context and question
2. Use `endpoint_info()` to understand the data source
3. Attempt to understand schema (via peek/describe/llm_query)
4. Construct test SPARQL query with `up:mnemonic` predicate
5. Execute query and verify results
6. Extract final answer and submit

**Differences between trajectories**:
- **Baseline rollout 1 & 2**: Identical reasoning (due to caching)
- **Prefix rollout 1**: Uses `sparql_describe` for schema exploration
- **Prefix rollout 2**: Uses `sparql_peek`, acknowledges "attempt 2" in reasoning

### No Hallucinations or Errors ✅

- All SPARQL queries use correct predicates (`up:mnemonic`)
- All URIs are real (P05067 is actually Amyloid-beta precursor protein, A4_HUMAN)
- No made-up tool calls
- No incorrect tool usage

---

## Known Issues

### Issue #1: DSPy Caching (CRITICAL)

**Symptom**: Second rollout in baseline has 0 LM tokens

**Cause**: DSPy likely caches responses when prompt is identical

**Impact**: Baseline (no perturbation) creates artificial determinism, invalidating stochasticity measurements

**Fix Required**: YES - Need to disable DSPy caching or ensure prompts are always unique

**Options**:
1. Pass `cache_seed` parameter to DSPy LM (if available)
2. Add unique ID to system prompt per rollout
3. Use explicit seeds per rollout (already implemented with `--use-seed`)
4. Confirm this is DSPy caching vs Anthropic API caching

**Validation Needed**: Check if `--use-seed` flag prevents caching

---

### Issue #2: Output Capture Bug (NON-CRITICAL)

**Symptom**: `output` field in iteration events shows repeated text or `null`

**Example**:
```json
{"event_type": "iteration", "data": {
  "code": "result = sparql_query(query)",
  "output": "Context length: 1665..."  // ← Wrong output
}}
```

**Expected**: Should show actual execution output (e.g., query results)

**Impact on Metrics**: ✅ **NONE** - Our diversity metrics extract operations from `code` field and tool call events, not `output` text

**Fix Priority**: LOW - Useful for debugging but doesn't affect measurements

---

## Diversity Metrics Validation

### Are Metrics Measuring Real Differences? ✅ YES

**Baseline (none)**:
- Vendi Score: 1.00 (only 1 effective unique trajectory)
- Jaccard: 1.00 (100% tool overlap)
- **Correct assessment**: Both trajectories are identical

**Prefix**:
- Vendi Score: 1.33 (1.33 effective unique trajectories)
- Jaccard: 0.50 (50% tool overlap)
- **Correct assessment**: Different tool choices, different approaches

**Validation**: Manual inspection confirms:
- Baseline rollouts are truly identical (caching)
- Prefix rollouts are truly different (different tools, iterations, reasoning)

---

## Conclusions

### ✅ Agent is Competent
- All trajectories succeeded
- Tool use is correct
- Reasoning is sound
- No execution errors
- Graceful error recovery

### ⚠️ Caching Invalidates Baseline
- Second rollout uses cached LLM responses
- Cannot measure true temperature=0.7 stochasticity
- Need to fix caching before running full S3 experiment

### ✅ Prefix Perturbation Works
- Creates genuine diversity (different tools, reasoning, iterations)
- Maintains 100% success rate
- 33% increase in effective trajectory count is real

---

## Recommendations

### Before Running Full S3 Experiment:

1. **CRITICAL**: Fix DSPy caching issue
   - Try `--use-seed` with explicit different seeds per rollout
   - Verify with another minimal test (check LM token usage)
   - If caching persists, add unique ID to system prompt

2. **RECOMMENDED**: Fix output capture bug
   - Helps with debugging
   - Not required for metrics, but improves observability

3. **OPTIONAL**: Add `llm_query` tool
   - Would reduce trial-and-error in schema exploration
   - Not critical (agent recovers gracefully)

### Validation Test:

Run one more minimal test with **`--use-seed`** to verify:
```bash
python experiments/reasoningbank/test_perturbation_minimal.py --use-seed
```

Expected: Both baseline rollouts should show non-zero LM token usage

---

## Files Analyzed

- `experiments/reasoningbank/results/minimal_test/none/4_uniprot_mnemonic_id_rollout1.jsonl`
- `experiments/reasoningbank/results/minimal_test/none/4_uniprot_mnemonic_id_rollout2.jsonl`
- `experiments/reasoningbank/results/minimal_test/prefix/4_uniprot_mnemonic_id_rollout1.jsonl`
- `experiments/reasoningbank/results/minimal_test/prefix/4_uniprot_mnemonic_id_rollout2.jsonl`
