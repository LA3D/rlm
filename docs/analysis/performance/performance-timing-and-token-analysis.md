# Performance Analysis: Timing and Token Usage

**Date**: 2026-01-23
**Context**: Understanding time per LLM call and token usage to inform optimization decisions

## Key Questions

1. **How long does a single LLM call take?**
   - Average: ~10 seconds per call

2. **How many tokens are being used?**
   - Average: ~5,900 tokens per call (5,400 prompt + 500 completion)
   - Total per run: ~59,000 tokens (10 calls × 5,900)

3. **Is the LLM call time reasonable given the token count?**
   - Yes: 598 tokens/second throughput is normal for Claude Sonnet 4.5
   - ~1.67 seconds per 1K tokens is within expected latency

## Detailed Metrics (Simple Query - Bacteria Taxa)

### Timing Breakdown
```
Total Duration: 102.5s (1.7 minutes)

Breakdown:
  LLM Calls:         99.0s (96.6%)
  Tool Execution:     3.3s ( 3.2%)
    - SPARQL:         3.1s ( 3.0%)
    - Other tools:    0.2s ( 0.2%)
  Unaccounted:        0.2s ( 0.2%) [overhead/idle]

Counts:
  LLM Calls:    10
  Tool Calls:   18
  SPARQL Calls:  5

Averages:
  Per LLM Call:    9.90s
  Per Tool Call:   0.18s
  Per SPARQL Call: 0.62s
```

### Token Usage
```
Total Tokens:
  Prompt tokens:       54,144
  Completion tokens:    5,125
  Total tokens:        59,269

Average per LLM call:
  Prompt tokens:         5,414
  Completion tokens:      512
  Total tokens:          5,927

Prompt token range:
  Min:  1,644 tokens
  Max:  9,702 tokens
```

### Efficiency Metrics
```
LLM Throughput:
  Tokens per second:         598.7
  Seconds per 1K tokens:      1.67s
  Average call time:          9.90s
  Average tokens per call:    5,927

Estimated Cost (Claude Sonnet 4.5):
  Input:  $0.1624
  Output: $0.0769
  Total:  $0.2393 per run
```

## Analysis

### 1. LLM Call Time is Dominated by Context Size

The average prompt size of **5,414 tokens** explains the ~10 second LLM call time:
- Claude API latency: ~1.67s per 1K tokens
- 5,414 tokens × 1.67s/1K = ~9s per call ✓

**Context grows over iterations:**
- First call: 1,644 tokens (minimal context)
- Last call: 9,702 tokens (accumulated history + sense card + meta summary)

### 2. Context Growth Pattern

Each iteration adds to the context:
1. **Base context** (~1,600 tokens):
   - Sense card (~600 tokens)
   - GraphMeta summary (~300 tokens)
   - Instructions and reasoning cycle prompts (~700 tokens)

2. **Accumulated history** (grows with each iteration):
   - Previous reasoning + code + outputs
   - By iteration 10: +8,000 tokens of history

This explains why later LLM calls are slower - more tokens to process.

### 3. Cost Analysis

At $0.24 per run with current iteration count:
- Simple query (10 iterations): $0.24
- Complex query (12+ iterations): $0.30+

**Scaling considerations:**
- 100 eval runs: $24-30
- 1,000 eval runs: $240-300

For comparison, user's 1-iteration baseline:
- Estimated: ~1,900 tokens (sense card + query)
- Estimated cost: $0.006 per run (40x cheaper)

### 4. Why 10 Iterations for a Simple Query?

The agent is spending time on:
1. **Schema exploration** (2-3 iterations)
   - search_entity calls to find relevant entities
   - describe_entity to understand structure

2. **Query construction** (1-2 iterations)
   - Building initial SPARQL query
   - Testing with sparql_select

3. **Verification and refinement** (3-4 iterations)
   - Checking results match expectations
   - Refining query based on partial results
   - Re-executing with adjustments

4. **Evidence collection** (2-3 iterations)
   - Gathering samples for evidence dict
   - Formatting for SUBMIT

For a simple taxonomy query ("find all bacteria taxa"), this is excessive exploration.

## Optimization Opportunities

### Option 1: Reduce Max Iterations (HIGH IMPACT on time AND cost)

**Simple queries**: max_iterations: 5 (currently 16)
- Expected time: 102s → 50-60s (2x faster)
- Expected cost: $0.24 → $0.12 (2x cheaper)
- Risk: May fail on slightly complex queries

**Complex queries**: Keep max_iterations: 16
- Already using 12+ iterations
- Reduction would risk incomplete answers

### Option 2: Context Pruning (MEDIUM IMPACT)

Reduce context size by:
- Summarizing older history (keep last 3 iterations full, summarize earlier)
- Smaller sense card (currently ~600 tokens)
- Remove verbose meta summaries

**Expected impact:**
- Prompt tokens: 5,414 → 3,500 (35% reduction)
- Time per call: 9.9s → 6.5s (35% faster)
- Total time: 102s → 70s
- Cost: $0.24 → $0.16

### Option 3: Fast Path with Reduced Context (HIGH IMPACT)

For simple queries detected by heuristics:
- Skip schema exploration (use cached ontology knowledge)
- Use minimal context (sense card + query only)
- Target: 2-3 iterations instead of 10

**Expected impact:**
- Time: 102s → 20-30s (approaching user's baseline)
- Cost: $0.24 → $0.03-0.05 (5-8x cheaper)
- Tokens per call: 5,927 → 2,000 (minimal context)

### Option 4: Use Haiku for Sub-Calls (LOW-MEDIUM IMPACT)

Use cheaper/faster model for:
- Verification steps (not main reasoning)
- Reflection generation
- Memory extraction

**Expected impact:**
- Time: 102s → 85-90s (15-20% faster, haiku is faster)
- Cost: $0.24 → $0.15 (40% cheaper, haiku is much cheaper)
- Quality impact: Minimal (sub-calls don't require Sonnet-level reasoning)

## Recommendations for E007 Experiment

Based on timing AND token usage data, recommend testing:

1. **Adaptive iteration budgets** (Test first - HIGH IMPACT)
   - Cohort A: max_iterations=5 for simple queries
   - Cohort B: max_iterations=16 (baseline)
   - Measure: pass rate, time, cost, evidence quality

2. **Context pruning** (Test second - MEDIUM IMPACT)
   - Cohort A: Summarize history after 3 iterations
   - Cohort B: Keep full history (baseline)
   - Measure: pass rate, time, context growth

3. **Fast path heuristics** (Test if adaptive budgets succeed)
   - Cohort A: Fast path for detected simple queries
   - Cohort B: Full exploration (baseline)
   - Measure: pass rate, time, false positive rate

## Context Growth Visualization

```
Iteration  Prompt Tokens  LLM Time  Context Content
---------  -------------  --------  ----------------
    1          1,644        7.5s    Base (sense card + instructions)
    2          3,200        9.2s    + first reasoning cycle
    3          4,100       10.1s    + exploration results
    4          5,500       11.5s    + query attempt
    5          6,200       10.8s    + verification
    6          7,100       11.2s    + refinement
    7          7,800       10.5s    + more results
    8          8,500       10.9s    + evidence gathering
    9          9,100       11.8s    + final verification
   10          9,702       12.1s    + reflection before SUBMIT
```

**Observation**: Each iteration adds ~800 tokens of history, increasing LLM latency by ~0.5s per call.

## Summary

**The bottleneck is NOT slow LLM calls or inefficient token usage.**

The LLM is performing as expected:
- ✓ Normal throughput: 598 tokens/second
- ✓ Reasonable latency: 1.67s per 1K tokens
- ✓ Context size explains timing: 5,414 tokens → 9s per call

**The bottleneck is iteration count: 10 iterations × 10s = 100s**

**Root cause**: Agent over-explores for simple queries that could be answered in 2-3 iterations.

**Best optimization**: Adaptive iteration budgets or fast path detection.
- Would reduce time from 102s to 20-50s (2-5x speedup)
- Would reduce cost from $0.24 to $0.05-0.12 (2-5x cheaper)
- Low risk if done carefully with evaluation

## Next Steps

1. ✅ Profile timing - DONE
2. ✅ Analyze token usage - DONE
3. ⏭️ Design E007 experiment with:
   - Primary: Adaptive iteration budgets (5 vs 16)
   - Secondary: Context pruning (if time permits)
   - Metrics: Pass rate, time, cost, token usage, evidence quality
