# ReasoningBank Overhead Analysis

**Date**: 2026-01-23
**Context**: Investigating if ReasoningBank (procedural memory) is helping or hurting performance

## Key Finding: ReasoningBank Currently Slows Down Performance

**Without Memory** (baseline):
- Time: 102.5s (10 iterations)
- Cost: $0.24
- Tokens: 59,269 total
- Avg prompt: 5,414 tokens

**With Memory** (ReasoningBank enabled):
- Time: 147.1s (12 iterations)
- Cost: $0.39
- Tokens: 97,572 total
- Avg prompt: 6,412 tokens

**Impact:**
- **+44% slower** (102s → 147s)
- **+62% more expensive** ($0.24 → $0.39)
- **+65% more tokens** (59K → 98K)
- **+2 more iterations** (10 → 12)

## What Happened?

### Memory Operations Timeline

1. **Retrieval** (at session start, <1s):
   - Query: "Select all bacterial taxa..."
   - Retrieved 3 memories:
     1. "Task Scope Recognition: All vs One"
     2. "Taxonomic Entity Resolution Strategy"
     3. "Taxonomic Data Extraction Protocol"
   - Time cost: ~0.0s (instant)

2. **Extraction** (after run completion, <1s):
   - Extracted 3 new memories from this run:
     1. "Explore Ontology Schema Before Querying"
     2. "Remote Endpoint Query Strategy"
     3. "Taxonomic Lineage Retrieval Approach"
   - Time cost: ~0.0s (instant)

3. **Judgment** (LLM-based, ~4-5s):
   - Uses LLM to judge if trajectory was successful
   - Time cost: ~4-5s (one additional LLM call)

### The Problem: Context Pollution

Memory operations themselves are fast (<1s), but the **retrieved memories added noise**:

1. **Added ~1,000 tokens to context**:
   - Average prompt: 5,414 → 6,412 tokens (+18%)
   - Max prompt: 9,702 → 12,587 tokens (+30%)

2. **Caused agent to take MORE iterations**:
   - Without memory: 10 iterations
   - With memory: 12 iterations (+2)
   - Likely because memories suggested more exploration

3. **Increased LLM latency**:
   - More tokens per call = longer LLM processing time
   - More iterations = more total LLM calls

### Why Did Memories Hurt Instead of Help?

The retrieved memories seem to have **encouraged more exploration** rather than providing a direct solution:

- "Explore Ontology Schema Before Querying" → Agent spends more time exploring
- "Taxonomic Entity Resolution Strategy" → Agent tries different resolution approaches
- "Task Scope Recognition: All vs One" → Agent second-guesses scope

Instead of using a stored solution, the agent used the memories as **guidance to explore more**, defeating the purpose of memory.

## Comparison: Memory as Overhead vs Memory as Cache

### Current Behavior (Memory as Guidance)
- Memories provide strategic hints
- Agent still explores from scratch
- Result: **Slower** (more context, more iterations)

### Desired Behavior (Memory as Cache)
- Memories provide direct solutions
- Agent skips exploration if memory hits
- Result: **Faster** (skip to solution)

## User's Proposed Alternative

> "Looking up a hit in straight memory and then deciding whether you should use a strategy or you should use a direct procedure to answer the question"

**Conceptual flow:**
```
1. Query arrives: "Select all bacterial taxa..."

2. Memory lookup:
   - Check for exact/near match
   - Found: "bacteria taxa query from UniProt"

3. Decision:
   IF memory confidence > threshold:
     → Use stored SPARQL query directly (1-2 iterations)
   ELSE:
     → Full exploration mode (10+ iterations)

4. Execute and verify
```

**Expected impact:**
- Cache hit: 2-3 iterations (vs 10-12 currently)
- Time: 20-30s (vs 147s with current memory)
- Cost: $0.05 (vs $0.39 with current memory)

## Current Memory Architecture Issues

### 1. No Fast Path Based on Memory Confidence

Currently, memory retrieval happens but doesn't trigger a fast path:
```python
# Current code (simplified)
memories = backend.retrieve(query, k=3)
context = build_context(sense_card, memories, meta)  # Memories added to context
result = rlm.run(query, context, max_iterations=16)   # Full iteration budget
```

No decision point based on memory quality.

### 2. Memories Are Injected as Context, Not Used as Solutions

Memories are formatted as text and added to the prompt:
```
You have these related strategies:
1. Task Scope Recognition: All vs One
   [strategy description...]
2. Taxonomic Entity Resolution Strategy
   [strategy description...]
```

The LLM reads these as suggestions, not direct solutions to use.

### 3. No Memory Confidence Scoring

Retrieved memories have BM25 scores, but there's no confidence threshold to decide:
- "This memory is a strong match, use it directly"
- "This memory is weak, explore from scratch"

## Proposed Improvements

### Option 1: Memory-Driven Fast Path (HIGH IMPACT)

Add a decision layer after memory retrieval:

```python
memories = backend.retrieve(query, k=3)

# Check if top memory is high-confidence direct match
if memories and memories[0].confidence > 0.8 and memories[0].has_sparql_template:
    # Fast path: Use stored solution directly
    sparql = memories[0].sparql_template
    result = execute_and_verify(sparql, max_iterations=3)
else:
    # Slow path: Full exploration
    context = build_context(sense_card, memories, meta)
    result = rlm.run(query, context, max_iterations=16)
```

**Expected impact:**
- Cache hit rate: 30-50% (with good memory)
- Cache hit time: 20-30s (vs 147s)
- Cache miss time: Same as current (102-147s)
- Overall speedup: 1.5-2x on average

### Option 2: Disable Memory Until Architecture Fixed (IMMEDIATE)

Given that memory **currently hurts performance**, consider:
- Disable memory by default in evals
- Focus on optimizing base iteration count first
- Revisit memory after fast path is implemented

**Rationale:**
- 44% slowdown is significant
- Better to optimize without memory first
- Then add memory with proper fast path architecture

### Option 3: Hybrid Approach (MEDIUM IMPACT)

Keep memory but reduce its impact:
- Only inject 1 memory (best match) instead of 3
- Summarize memories to reduce token count
- Use memories for verification, not exploration

**Expected impact:**
- Reduce token overhead: 6,412 → 5,800 tokens
- Reduce iterations: 12 → 10-11
- Time: 147s → 120-130s
- Still slower than no-memory baseline

## Recommendations

### Immediate (for E007 experiment)
1. ✅ Document memory overhead issue
2. **Run E007 WITHOUT memory enabled** (baseline optimization)
   - Test adaptive iteration budgets
   - Establish performance baseline
   - Avoid memory overhead complicating results

### Short-term (Phase 2)
3. Design memory-driven fast path architecture
4. Implement confidence-based routing
5. Create E008 experiment: Memory fast path vs full exploration

### Long-term (Phase 3)
6. Add memory confidence scoring
7. Build direct solution templates (not just strategies)
8. Implement SPARQL template library in memory

## Memory Performance Summary

| Metric | Without Memory | With Memory | Change |
|--------|----------------|-------------|--------|
| **Time** | 102.5s | 147.1s | +44% ⬆️ |
| **Iterations** | 10 | 12 | +20% ⬆️ |
| **Total tokens** | 59,269 | 97,572 | +65% ⬆️ |
| **Avg prompt** | 5,414 | 6,412 | +18% ⬆️ |
| **Cost** | $0.24 | $0.39 | +62% ⬆️ |
| **Tool calls** | 18 | 31 | +72% ⬆️ |
| **SPARQL calls** | 5 | 8 | +60% ⬆️ |

**Every metric got worse with memory enabled.**

## Root Cause

ReasoningBank retrieves relevant memories, but the current architecture:
1. Adds them to context (token overhead)
2. Uses them as exploration hints (more iterations)
3. Doesn't provide a fast path (no cache benefit)

**Result:** All the cost of memory (retrieval, storage, token overhead) with none of the benefits (faster execution, fewer iterations).

## Next Steps

1. ⏭️ **Disable memory for E007 baseline optimization**
2. ⏭️ **Design memory fast path architecture**
   - Confidence-based routing
   - Direct solution templates
   - Adaptive iteration budgets based on memory hits
3. ⏭️ **Create E008 experiment: Memory fast path effectiveness**
   - Cohort A: Memory fast path (2-3 iterations on cache hit)
   - Cohort B: Full exploration (10-12 iterations)
   - Cohort C: No memory (baseline)

## Appendix: Detailed Memory Events

### Retrieved Memories (k=3)
1. **Task Scope Recognition: All vs One**
   - Likely about distinguishing "all X" vs "one X" queries
   - May have caused agent to verify scope unnecessarily

2. **Taxonomic Entity Resolution Strategy**
   - About resolving taxonomic entities
   - Relevant, but as guidance not solution

3. **Taxonomic Data Extraction Protocol**
   - About extracting taxonomic data
   - Again guidance, not direct solution

### Extracted Memories (k=3)
From this run, the system extracted:

1. **Explore Ontology Schema Before Querying**
   - If this gets reused, will encourage MORE exploration
   - Counterproductive for fast execution

2. **Remote Endpoint Query Strategy**
   - About handling SERVICE/GRAPH in SPARQL
   - Useful for federated queries

3. **Taxonomic Lineage Retrieval Approach**
   - Specific to lineage queries
   - May be useful for similar future queries

**Observation:** Extracted memories are high-level strategies, not direct solutions. This perpetuates the problem.
