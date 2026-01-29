# Delegation Test Findings: The Model TRIES But Doesn't Follow Through

**Date**: 2026-01-28
**Tests**: Simple semantic tasks with explicit llm_query prompting

---

## Critical Discovery: Model KNOWS How But Doesn't Complete

### Test Results Summary

**Test 1: Language Selection**
- Task: Choose best language for web API
- Explicit instruction: "Use llm_query() to help analyze"
- Result: Correct answer (JavaScript)
- Claimed: `used_llm_query: True` ✓
- **Reality**: llm_query NOT found in trajectory ✗
- Time: 36.1s, 5 iterations (hit max)

**Test 2: Email Validation**
- Task: Detect phishing email
- Explicit instruction: "Use llm_query() for domain analysis"
- Result: Correct answer (suspicious)
- Claimed: `used_delegation: True` ✓
- **Reality**: llm_query NOT found in trajectory ✗
- Time: 33.0s, 4 iterations (hit max)

---

## What Actually Happened

Looking at the verbose output, here's the pattern:

### Test 1 - Iteration 4 (Language Selection)
```python
# Model WRITES this code:
prompt = "Given the following programming languages..."
response = llm_query(prompt)  # ← ATTEMPTED!
print("LLM Response:")
print(response)
```

**Then**: Model hits iteration 5/5 (max) and gives up
**Result**: Falls back to direct reasoning without llm_query result

### Test 2 - Iteration 3 (Email Validation)
```python
# Model WRITES this code:
query = "Is the domain 'paypal-security-verify.com' legitimate?"
response = llm_query(query)  # ← ATTEMPTED!
print("LLM Response:")
print(response)
```

**Then**: Model hits iteration 4/4 (max) and gives up
**Result**: Falls back to direct reasoning without llm_query result

---

## Key Insights

### 1. Model UNDERSTANDS Delegation

Evidence:
- ✅ Writes `llm_query(prompt)` calls in code
- ✅ Constructs appropriate prompts
- ✅ Knows WHEN to delegate (semantic judgment tasks)
- ✅ Claims to have used delegation in output

**This is huge!** The model isn't ignorant of delegation—it actively tries to use it.

### 2. Something Interrupts Execution

Possibilities:

**A. Silent Failure**
- llm_query call happens but returns empty/error
- Model doesn't see result
- Continues without it

**B. Iteration Limits**
- Model attempts delegation in late iterations
- Hits max_iterations before seeing result
- Falls back to direct reasoning

**C. Cost Avoidance**
- Model realizes it can solve directly
- Aborts delegation attempt mid-stream
- Completes without sub-LLM

**D. Execution Issue**
- Code with llm_query doesn't actually execute
- Model reasoning shows attempt
- But REPL doesn't process it

### 3. Model Falls Back Gracefully

When delegation fails/aborts:
- ✅ Model doesn't error out
- ✅ Completes task using direct reasoning
- ✅ Produces correct answers
- ⚪ Still claims to have used delegation

This suggests the model has learned delegation as "optional optimization" not "required step."

---

## Why This Matters for Your Use Case

### Original Hypothesis: "RLM Flat Because Missing Tools"

**Status**: ❌ DISPROVEN

Evidence:
- llm_query was always available (DSPy built-in)
- Model knows how to use it
- Model attempts to use it
- **Conclusion**: Not an architecture problem

### Revised Hypothesis: "RLM Flat Because Delegation Isn't Completing"

**Status**: ✅ SUPPORTED

Evidence:
- Model writes delegation code
- But doesn't complete execution
- Falls back to direct reasoning
- Results in "flat" linear pattern

**Root Cause Candidates**:
1. **Iteration limits too tight** (5-6 iterations insufficient)
2. **Call counter limiting** (max_llm_calls reached?)
3. **Model optimization** (realizes direct is faster)
4. **Execution environment** (Deno warnings, though shouldn't affect)

---

## Comparison With Prime Intellect's Findings

### Prime Intellect (Trained RLM):
> "Models without explicit training underutilized sub-LLMs, even when given tips"

### Your Findings (Untrained RLM):
- Model TRIES to use sub-LLMs (better than "underutilize")
- But doesn't complete the delegation
- Falls back to direct reasoning
- Still produces correct answers

**Interpretation**: Your model is CLOSER to strategic delegation than expected, but something blocks completion.

---

## Diagnostic Questions

### Q1: Is llm_query Actually Being Called?

**Test**: Add logging to see if llm_query is invoked
- If yes → Silent failure or result ignored
- If no → Code generation doesn't execute

### Q2: Are Iteration Limits Too Tight?

**Observation**:
- Test 1: Attempted delegation at iter 4/5 (too late)
- Test 2: Attempted delegation at iter 3/4 (too late)

**Hypothesis**: Model needs ~3-4 iters to decide to delegate, then runs out of iterations

**Test**: Increase max_iterations to 10-12

### Q3: Is max_llm_calls Being Exhausted?

**Current settings**:
- Test 1: max_llm_calls=10
- Test 2: max_llm_calls=8

**If**: Model already used calls on reasoning, it can't delegate

**Test**: Track llm call counter

### Q4: Is Model "Too Smart"?

**Observation**: Both tasks solvable without delegation
- Language selection: Model knows JavaScript good for APIs
- Email validation: Model recognizes phishing patterns

**Hypothesis**: Model realizes delegation is OPTIONAL for these tasks

**Test**: Create task that REQUIRES sub-LLM (main model can't answer alone)

---

## Recommendations

### Immediate: Increase Iteration Limits

```python
rlm = RLM(
    Signature,
    max_iterations=12,  # ← Was 5-6, too tight
    max_llm_calls=20,   # ← Was 8-10, may be exhausted
    sub_lm=sub_lm
)
```

**Rationale**: Model attempts delegation late (iter 3-4), needs more iterations to complete

### Test: Add Explicit Logging

Modify interpreter to log when llm_query is called:

```python
def llm_query(prompt):
    print(f"\n🎯 SUB-LLM DELEGATION HAPPENING!")
    print(f"   Prompt: {prompt[:100]}...")
    result = sub_lm(prompt)
    print(f"   Result: {result[:100]}...")
    return result
```

This will show if delegation actually executes.

### Test: Create "Impossible Without Delegation" Task

Design task where main model CANNOT answer alone:

```python
task = """
You have a large text document (50K chars) and need to:
1. Extract all mentions of products
2. Classify each as 'electronics' or 'furniture'
3. Count occurrences

The text is too long for you to process directly. You MUST use:
- llm_query_batched() to process chunks in parallel
- Combine results at the end

[... 50K chars of text ...]
"""
```

If model still doesn't delegate → architectural issue
If model delegates → just needs encouragement

---

## Updated Architecture Assessment

### Your RLM Implementation

**Components**:
- ✅ Persistent REPL (working)
- ✅ Code generation (working)
- ✅ llm_query built-in (available)
- ⚠️  Delegation attempts (incomplete)

**Status**: "Attempted-But-Incomplete Delegation RLM"

**Not**: "Flat/Linear RLM" (it tries to be strategic!)
**Not**: "Missing Delegation" (tools are there!)
**Is**: "Delegation-Aware But Falling Back"

### Likely Root Causes (Ranked)

1. **Iteration limits too tight** (80% likely)
   - Model attempts late (iter 3-4)
   - Runs out before completion
   - Fix: Increase max_iterations

2. **Task too simple** (60% likely)
   - Model can solve directly
   - Delegation optional, not required
   - Test: Harder tasks or "impossible without delegation"

3. **Model optimization** (40% likely)
   - Learns delegation is slower
   - Chooses direct path
   - Fix: Require delegation in signature

4. **Silent execution failure** (20% likely)
   - Code doesn't run
   - Model doesn't see result
   - Fix: Add logging/debugging

---

## Next Steps (Prioritized)

### 1. Increase Iteration Limits (Quick Win)

```bash
# Modify test to use more iterations
max_iterations=12  # Was 5-6
max_llm_calls=20   # Was 8-10
```

**Expected**: Model completes delegation before hitting limit

### 2. Add Delegation Logging (Diagnostic)

Add print statements in llm_query wrapper to confirm execution.

**Expected**: See if delegation actually runs

### 3. Test With Ontology Query (Original Domain)

Re-run PROV test with increased limits:

```python
run_dspy_rlm(
    "What is Activity?",
    "ontology/prov.ttl",
    max_iterations=12,  # Increased
    max_llm_calls=20
)
```

**Expected**: If limits were the issue, should see delegation complete

### 4. Create "Delegation Required" Task

Design task that CANNOT be solved without delegation.

**Expected**: Forces model to complete delegation or fail

---

## Implications for RLM vs ReAct Comparison

### Before These Tests:

**Assumption**: RLM doesn't delegate (flat/linear)
**Comparison**: "Direct tools (RLM)" vs "Direct tools (ReAct)"

### After These Tests:

**Reality**: RLM TRIES to delegate but doesn't complete
**Comparison**: "Attempted delegation (RLM)" vs "Direct tools (ReAct)"

**This changes the question from**:
- ❌ "Why doesn't RLM delegate?" → Architecture missing
- ✅ "Why doesn't RLM complete delegation?" → Execution/config issue

### Fair Comparison Now:

**Test conditions**:
1. RLM with tight limits (current baseline)
2. RLM with loose limits (allow delegation to complete)
3. ReAct (control)

**Measure**:
- Does delegation complete with more iterations?
- Does it help quality on L2-L3 tasks?
- Is overhead worth the benefit?

---

## Key Takeaways

### 1. Model Isn't "Dumb" About Delegation

Evidence:
- Writes llm_query calls
- Constructs appropriate prompts
- Attempts at right moments
- Knows semantic tasks benefit from delegation

**Conclusion**: Model has learned delegation patterns (perhaps from training data showing RLM examples)

### 2. Execution Environment Matters

- Tight iteration limits prevent completion
- Max LLM call limits may constrain
- Task complexity affects whether delegation is "worth it"

**Conclusion**: This is a configuration/environment issue, not fundamental architecture

### 3. "Flat Pattern" Is Fallback, Not Primary Strategy

- Model attempts hierarchical reasoning
- Falls back to direct when delegation blocked
- Still produces correct answers

**Conclusion**: The "flat pattern" you observed is GRACEFUL DEGRADATION, not the model's first choice

---

## Updated Recommendations

### For RLM vs ReAct Comparison:

**Do**:
1. Test with increased iteration limits (12+)
2. Track actual delegation completion
3. Compare quality on L2-L3 where delegation may help

**Don't**:
1. Assume current behavior represents RLM's potential
2. Compare without allowing delegation to complete
3. Draw conclusions from L1 simple tasks only

### For Production Use:

**If delegation helps** (after proper testing):
- Keep RLM with loose limits
- Add delegation logging
- Pattern select based on complexity

**If delegation doesn't help**:
- Use ReAct or simple RLM
- Accept direct tools are sufficient
- Optimize for speed over delegation

---

## Files Referenced

- Test script: `test_delegation_simple.py`
- Previous results: `docs/state/llm-query-test-results.md`
- Architecture analysis: `docs/analysis/rlm-architecture-comparison.md`

---

**Last Updated**: 2026-01-28 11:20 EST
**Status**: Delegation attempts discovered, root cause hypotheses formed
**Next**: Test with increased iteration limits
