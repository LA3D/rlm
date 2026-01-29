# RLM Token Efficiency Explained

**Date**: 2026-01-28
**Question**: Why does RLM use "more tokens per iteration" but still cost less?

---

## The Answer: You're Measuring the Wrong Thing

**Per Iteration** (misleading):
- RLM: 7,069 tokens/iteration
- ReAct: 4,172 tokens/iteration
- ❌ Makes RLM look inefficient

**Per LLM Call** (what matters):
- RLM: 3,213 tokens/call
- ReAct: 7,416 tokens/call
- ✅ RLM is **57% MORE efficient!**

---

## Why "Per Iteration" is Misleading

**RLM makes multiple LLM calls per iteration**:
- 5 iterations × 2.2 calls/iteration = 11 LLM calls total
- So: 7,069 tokens/iter ÷ 2.2 calls/iter = ~3,200 tokens/call ✓

**ReAct makes fewer calls (weird counting)**:
- 16 iterations but only 9 LLM calls total
- Something is off with iteration counting here

**Bottom line**: Compare tokens per API call, not per "iteration" (which means different things).

---

## Token Breakdown: Where Do They Go?

### RLM Pattern

**Call 1** (1,561 tokens):
- Input: 1,356 tokens (small start)
  - System: RLM instructions (~500 tokens)
  - User: Query + minimal context (~850 tokens)
- Output: 205 tokens (code generation)

**Call 2** (2,254 tokens):
- Input: 1,895 tokens (+539 from Call 1)
  - Previous: System + query
  - **Added**: REPL history (previous code + output)
- Output: 359 tokens (more complex code)

**Call 3-5**: Context continues growing with REPL history
- Input: 2,787 → 3,886 → 244 (varies)
- Output: 383 → 461 → 312 tokens

**Call 6** (peak, 5,913 tokens):
- Input: 4,664 tokens (all REPL history accumulated)
- Output: 1,249 tokens (final SUBMIT with evidence)

**Total: 35,346 tokens across 11 calls**

### ReAct Pattern

**Call 1** (6,025 tokens):
- Input: 5,887 tokens (**4.3x larger start!**)
  - System: ReAct instructions
  - User: Query + full ontology sense card (LARGE)
  - Thought/Action history: Empty (first call)
- Output: 138 tokens (first thought)

**Call 2-9**: Context stays high
- Input: 6,272 → 7,106 → 8,237 tokens
- Each call includes: Full sense card + all previous thoughts + actions
- Output: 138-1,399 tokens per call

**Total: 66,747 tokens across 9 calls**

---

## Why RLM is More Efficient Per Call

### 1. **Smaller Initial Context** (4.3x smaller!)

**RLM starts with**:
- Core RLM instructions
- Query
- **Minimal** ontology info
- **Total**: 1,356 tokens

**ReAct starts with**:
- ReAct instructions
- Query
- **Full** ontology sense card (~18K chars)
- **Total**: 5,887 tokens

### 2. **Different Context Growth Patterns**

**RLM Growth** (Progressive):
```
Call 1: 1,356 tokens (base)
Call 2: 1,895 tokens (+539, added REPL output)
Call 3: 2,787 tokens (+892, more history)
Call 4: 3,886 tokens (+1,099, accumulating)
...
```
**Growth rate**: ~500-1000 tokens/call

**ReAct Growth** (High plateau):
```
Call 1: 5,887 tokens (starts high)
Call 2: 6,272 tokens (+385, added thought)
Call 3: 7,106 tokens (+834, more thoughts)
Call 4: 6,639 tokens (-467, varies)
...
```
**Growth rate**: Varies, but starts 4x higher

### 3. **Output Efficiency** (Similar)

- RLM: ~553 tokens/call (code generation)
- ReAct: ~607 tokens/call (thought generation)
- **Comparable**: Both generate similar output amounts

---

## Why Does This Lead to Lower Total Cost?

### The Multiplication Effect

**RLM**:
```
11 calls × 3,213 tokens/call = 35,346 total tokens
```

**ReAct**:
```
9 calls × 7,416 tokens/call = 66,747 total tokens
```

Even though ReAct makes **fewer calls**, each call is so expensive that the total is **nearly 2x** RLM's cost.

### Cost Calculation

**At $3/M input + $15/M output**:

**RLM**:
- Input: 29,265 tokens × $0.000003 = $0.088
- Output: 6,081 tokens × $0.000015 = $0.091
- **Total: $0.179**

**ReAct**:
- Input: 61,288 tokens × $0.000003 = $0.184
- Output: 5,459 tokens × $0.000015 = $0.082
- **Total: $0.266**

**RLM saves 32.6%** ($0.087 per query)

---

## Is the Code Efficient?

**Question**: "Could RLM be more efficient?"

### What's Efficient

✅ **Small initial context** (1.3K tokens vs ReAct's 5.9K)
- RLM loads minimal ontology info upfront
- Fetches details on-demand via tools

✅ **Progressive context growth** (vs ReAct's full context)
- REPL history adds only what was executed
- Not repeating full sense card every call

✅ **Fewer total calls** (11 vs 9, but covers 5 logical iterations)
- Multi-step code does more work per iteration
- Fewer round-trips overall

### What's Potentially Inefficient

⚠️ **Code generation verbosity** (205-1,249 tokens/call output)
- Python code is more verbose than "thought + action" text
- Example: `results = search_entity("Activity")` vs `Action: search Activity`

⚠️ **REPL history accumulation** (grows to 4.6K tokens by end)
- Each iteration's code + output stays in context
- Could potentially summarize or truncate old history

⚠️ **Multiple calls per logical iteration** (2.2 calls/iter)
- RLM may be making extra LLM calls internally
- Could be for parsing, validation, or sub-tasks

---

## Optimization Opportunities

### 1. Truncate Old REPL History

**Current**: All previous code + outputs stay in context

**Potential**: Keep only last 2-3 iterations

**Savings**: ~30-40% input tokens (reduce 4.6K → 2K)

**Tradeoff**: Model loses long-term context

### 2. Compress Code Representation

**Current**: Full Python code syntax

**Potential**: Pseudo-code or compressed format

**Savings**: ~20% output tokens

**Tradeoff**: Harder to execute, may need translation layer

### 3. Lazy Sense Card Loading

**Current**: Minimal initial context (already good!)

**Already doing this well**: RLM starts with 1.3K vs ReAct's 5.9K

---

## Comparison Summary

| Aspect | RLM | ReAct | Winner |
|--------|-----|-------|--------|
| **Tokens per API call** | 3,213 | 7,416 | RLM (57% better) |
| **Initial context** | 1,356 | 5,887 | RLM (77% smaller) |
| **Context growth rate** | 500-1K/call | Flat ~6-7K | RLM (slower growth) |
| **Total API calls** | 11 | 9 | ReAct (fewer) |
| **Total tokens** | 35,346 | 66,747 | RLM (47% fewer) |
| **Total cost** | $0.179 | $0.266 | RLM (33% cheaper) |

---

## Answering Your Question

> "Is the code efficient?"

**Answer: YES, RLM is actually MORE efficient than it appeared!**

**Evidence**:
1. ✅ 57% fewer tokens per API call
2. ✅ 77% smaller initial context
3. ✅ 47% fewer total tokens
4. ✅ 33% lower total cost

**The "7,069 tokens/iteration" metric was misleading** because:
- It counts multiple LLM calls as one "iteration"
- Real comparison should be per API call (what you pay for)
- By that measure, RLM is significantly more efficient

**Minor optimizations possible**:
- Could truncate old REPL history (save ~30% input)
- Could compress code format (save ~20% output)
- But current approach is already quite efficient

---

## Key Takeaway

**Don't worry about "tokens per iteration"** - that's an artificial construct.

**Worry about "tokens per API call"** - that's what Anthropic charges for.

By that measure, **RLM is 57% more efficient** than ReAct, leading to **33% cost savings**.

---

**Related**: `experiments/cost_analysis/comparison_*.json`
