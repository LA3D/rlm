# DSPy/Anthropic Caching Issue - Analysis & Solutions

**Date**: 2026-02-03
**Status**: CRITICAL BLOCKER for S3 experiment

---

## Problem Summary

When running multiple stochastic rollouts with temperature=0.7 **without prompt perturbation**, DSPy/Anthropic API returns **identical trajectories** due to caching.

### Evidence

**Test 1: No perturbation, no explicit seed**
```
Baseline Rollout 1: 10,470 prompt + 1,423 completion tokens ($0.053)
Baseline Rollout 2: 0 prompt + 0 completion tokens (CACHED!)
Result: Identical code, reasoning, tool calls (Vendi=1.00, Jaccard=1.00)
```

**Test 2: No perturbation, with explicit seed=rollout_id**
```
Error: anthropic does not support parameters: ['seed']
All rollouts failed with UnsupportedParamsError
```

**Test 3: With prefix perturbation "[Attempt N]"**
```
Prefix Rollout 1: 12,075 prompt + 1,186 completion tokens ($0.054)
Prefix Rollout 2: 13,076 prompt + 1,386 completion tokens ($0.060)
Result: Different trajectories (Vendi=1.33, Jaccard=0.50)
```

### Key Findings

1. **Caching occurs** when prompts are identical (same context + same task)
2. **Anthropic API doesn't support `seed` parameter** via litellm/DSPy
3. **Prompt perturbation prevents caching** by making prompts unique
4. **Temperature alone is insufficient** to create diversity when caching

---

## Root Cause Analysis

### Where Caching Happens

Could be at multiple levels:
1. **DSPy internal cache** - DSPy may cache LM responses by prompt hash
2. **Anthropic API cache** - Anthropic may cache identical requests
3. **litellm proxy cache** - litellm may implement caching

### Why It Matters

For **baseline measurements** (no perturbation):
- We want to measure inherent temperature=0.7 stochasticity
- Caching makes temperature irrelevant (same output every time)
- Can't establish true baseline for comparison

For **perturbation experiments**:
- Perturbation already prevents caching (different prompts)
- Not affected by this issue

---

## Proposed Solutions

### Option 1: Unique Context ID (RECOMMENDED)

**Approach**: Add a unique, invisible ID to the context per rollout

**Implementation**:
```python
def build_context_uniprot(cfg, ont_path, task, mem=None, rollout_id=None):
    parts = []

    # Add unique ID as invisible marker (prevents caching)
    if rollout_id is not None:
        parts.append(f"<!-- Rollout ID: {rollout_id} -->")

    # ... rest of context building ...
```

**Pros**:
- Simple, non-invasive
- Doesn't affect agent behavior (HTML comment ignored in reasoning)
- Prevents caching without changing API parameters
- Compatible with all models

**Cons**:
- Adds a few tokens per request (~10 tokens)
- Slightly increased cost

**Change Required**:
- Modify `build_context_uniprot()` in `rlm_uniprot.py`
- Pass `rollout_id` from `run_stochastic_uniprot()`

---

### Option 2: Disable DSPy Caching

**Approach**: Find and disable DSPy's internal caching mechanism

**Implementation**: (needs investigation)
```python
# Hypothetical - need to check DSPy source
dspy.settings.cache = False
# or
lm = dspy.LM(..., cache=False)
```

**Pros**:
- Cleaner solution if it exists
- No prompt modifications

**Cons**:
- Unclear if DSPy has this option
- May still have Anthropic API caching
- Requires DSPy source code investigation

**Status**: NEEDS INVESTIGATION

---

### Option 3: Accept Caching, Focus on Perturbation

**Approach**: Accept that baseline will have caching, rely entirely on perturbation for diversity

**Rationale**:
- Our goal is to find the best perturbation strategy
- Perturbation already prevents caching
- Baseline is only for comparison (can use k=1)

**Pros**:
- No code changes needed
- Simplifies implementation
- Still achieves experiment goals

**Cons**:
- Can't measure inherent temperature stochasticity
- Baseline is artificial (not true temperature=0.7 behavior)
- Less scientifically rigorous

**Recommended**: Only if Options 1 & 2 don't work

---

### Option 4: Perturbation in Baseline Too

**Approach**: Add minimal perturbation even to "baseline" (e.g., random number)

**Implementation**:
```python
strategies = {
    'baseline': lambda q, i: f"{q} [ID:{random.randint(1000,9999)}]",
    'prefix': lambda q, i: f"[Attempt {i+1}] {q}",
    'thinking': lambda q, i: f"{THINKING_PROMPTS[i]} {q}",
}
```

**Pros**:
- Prevents caching in all conditions
- Still allows comparison of perturbation effectiveness
- Simple to implement

**Cons**:
- "Baseline" is no longer true baseline
- Random ID might affect behavior slightly

**Note**: This is essentially Option 1 but in the query instead of context

---

## Recommendation

**Implement Option 1: Unique Context ID**

### Why:
1. **Minimal impact**: HTML comment won't affect agent reasoning
2. **Guaranteed to work**: Makes prompts unique at the source
3. **Preserves intent**: Agent still sees same semantic content
4. **Easy to implement**: Single function modification
5. **Debuggable**: Can verify in logs

### Implementation Plan:

**Step 1**: Add `rollout_id` parameter to `build_context_uniprot()`

**Step 2**: Add invisible marker at start of context:
```python
if rollout_id is not None:
    parts.insert(0, f"<!-- Rollout: {rollout_id} | Timestamp: {time.time()} -->")
```

**Step 3**: Pass `rollout_id` from `run_stochastic_uniprot()`:
```python
for i in range(k):
    result = run_uniprot(
        task=task,
        ...
        rollout_id=i,  # NEW PARAMETER
    )
```

**Step 4**: Validate with minimal test:
- Run 2 rollouts with no perturbation
- Verify both have non-zero LM tokens
- Verify trajectories are different (if temperature creates variation)

---

## Alternative: Timestamp Instead of ID

Instead of rollout ID, use timestamp:
```python
import time
parts.insert(0, f"<!-- Timestamp: {time.time()} -->")
```

**Pros**:
- Even more unique (microsecond precision)
- Don't need to pass rollout_id parameter

**Cons**:
- Less deterministic (can't reproduce exact prompt)
- Harder to track which rollout in logs

**Verdict**: Rollout ID is better for reproducibility

---

## Testing Protocol

After implementing solution:

1. **Validation Test**: Run minimal test without perturbation
   ```bash
   python experiments/reasoningbank/test_perturbation_minimal.py
   ```

   **Expected**:
   - Both rollouts show non-zero LM tokens
   - Vendi Score > 1.0 (if temperature creates variation)
   - Different tool calls or reasoning (if stochastic)

2. **Cost Check**: Verify token increase is minimal
   - Context ID adds ~10 tokens per request
   - Acceptable cost: <1% increase

3. **Behavior Check**: Verify agent behavior unchanged
   - Success rate should match original test
   - Agent shouldn't reference the ID in reasoning

---

## Questions for User

1. **Approve Option 1 (Unique Context ID)?**
   - If yes, I'll implement immediately

2. **Prefer rollout ID or timestamp?**
   - rollout_id = deterministic, reproducible
   - timestamp = more unique, less reproducible

3. **Acceptable to add 10 tokens per request?**
   - Cost increase: ~$0.0001 per rollout (negligible)

4. **Alternative suggestions?**
   - Any other approaches to consider?

---

## Impact on S3 Experiment

**If we don't fix this:**
- Baseline measurements will be invalid (cached)
- Can't measure inherent temperature stochasticity
- Comparison between strategies will be skewed

**If we fix this:**
- True baseline measurements possible
- Can quantify temperature effect
- Fair comparison across all strategies
- More scientifically rigorous results

**Urgency**: HIGH - blocking full S3 experiment
