# Memory Tracking System Findings

**Date**: 2026-01-23
**Purpose**: Document what we know about memory usage tracking and what needs investigation

## Key Finding: Memory Tracking IS Working (But Not in Our N=1 Test)

### Memory Bank Status

**Total memories**: 73
**Memories with usage**: 9 (12.3%)
**Total usage records**: 59
**Total runs tracked**: 22
**Total trajectories**: 22

### Most Used Memories

| Memory | Accesses | Successes | Failures | Success Rate |
|--------|----------|-----------|----------|--------------|
| Task Scope Recognition: All vs One | 19 | 12 | 7 | **63%** |
| Inconsistent Query Strategy Convergence | 11 | 8 | 3 | **73%** |
| Taxonomic Data Extraction Protocol | 9 | 6 | 3 | **67%** |
| Incremental Data Source Investigation | 7 | 5 | 2 | **71%** |
| Explore RDF Schema for Data Retrieval | 5 | 2 | 3 | **40%** ⚠️ |
| Taxonomic Entity Resolution Strategy | 4 | 3 | 1 | **75%** |

### Key Observations

1. **"Task Scope Recognition" is the most accessed memory** (19 times)
   - This is the SAME memory we saw retrieved in our N=1 test
   - It has a 63% success rate
   - 12 successes, 7 failures

2. **Success rates vary widely**
   - Best: Hierarchical Data Navigation (100%, but only 1 access)
   - Worst: Taxonomic Data Extraction (0%, but only 1 access)
   - Most reliable: Taxonomic Entity Resolution (75%, 4 accesses)
   - Inconsistent: Explore RDF Schema (40%, 5 accesses)

3. **Our N=1 test runs likely didn't have tracking enabled**
   - The memories we examined show 19, 4, and 9 accesses
   - But we saw NO evidence of memory use in our trajectory analysis
   - This suggests our N=1 test was from runs without proper tracking

## Implications for N=1 Analysis

### Our N=1 Conclusion Was: "Agent ignores memories"

**But now we know:**
- Memory tracking HAS worked in 22 runs
- The same memories we tested have 19+ tracked accesses
- Success rates are 60-75% (not 0%)

**Revised conclusion:**
- Our specific N=1 test runs may have been WITHOUT tracking
- OR our N=1 runs were from a different configuration
- We CANNOT conclude "memories are always ignored" from N=1

### What We Still Don't Know

1. **When do memories help vs hurt?**
   - "Task Scope Recognition" succeeds 63% of the time
   - What's different about the 37% failures?

2. **How are memories actually used?**
   - We saw no explicit references in code
   - But tracking shows they're "used" (access_count incremented)
   - Does "used" mean "retrieved" or "applied"?

3. **Why the stochasticity?**
   - Same memory, same task type → sometimes helps, sometimes doesn't
   - Is this LLM variance?
   - Or task-specific differences?

4. **Are successes correlation or causation?**
   - Success_count incremented when trajectory succeeds AND memory was retrieved
   - But did the memory CAUSE success, or just happen to be present?

## What "Usage" Means Currently

Looking at the code, usage tracking appears to work like this:

```python
# On retrieval
memories = backend.retrieve(query, k=3)
# → access_count incremented for top-k memories

# On trajectory completion
if trajectory_succeeded:
    for memory in retrieved_memories:
        memory.success_count += 1
else:
    for memory in retrieved_memories:
        memory.failure_count += 1
```

**Problem**: This tracks RETRIEVAL + OUTCOME, not ACTUAL USE

**Example**:
- Memory retrieved but ignored by agent → still increments access_count
- Trajectory succeeds → increments success_count
- But memory didn't actually contribute!

**This explains our findings:**
- Memory has 19 accesses (retrieved 19 times)
- Memory has 12 successes (12 trajectories succeeded when it was present)
- But we saw no evidence of agent USING the memory in our N=1 test

**Correlation ≠ Causation**

## What We Need: Better Tracking

### Current Tracking (Retrieval + Outcome)

```
Memory retrieved → access_count++
Trajectory succeeds → success_count++
Trajectory fails → failure_count++
```

**Missing**: Did the agent actually REFERENCE or APPLY the memory?

### Proposed Tracking (Application + Impact)

```
Memory retrieved → access_count++
Memory referenced in code/reasoning → was_applied = True
Trajectory succeeds + was_applied → success_count++
Trajectory succeeds + NOT was_applied → coincidental_success++
Trajectory fails + was_applied → failure_count++
Trajectory fails + NOT was_applied → coincidental_failure++
```

**Detection**: Search LLM outputs for:
- Memory title keywords
- Memory content keywords
- Phrases like "based on", "following", "as suggested"

## Recommended Experiment Design

### Phase 1: Add Application Tracking

1. **Track memory injection**
   - Log exact text added to context
   - Log token overhead
   - Log which iteration memory was present

2. **Track memory references**
   - Search each LLM output for memory keywords
   - Log binary: was_referenced (True/False)
   - Log which specific memory was referenced

3. **Revise success/failure tracking**
   ```python
   if was_referenced and trajectory_succeeded:
       memory.applied_success_count += 1
   elif not was_referenced and trajectory_succeeded:
       memory.present_but_unused_success += 1
   elif was_referenced and trajectory_failed:
       memory.applied_failure_count += 1
   elif not was_referenced and trajectory_failed:
       memory.present_but_unused_failure += 1
   ```

### Phase 2: Controlled Sampling (N=10 per cohort)

**Why N=10:**
- With 60-75% success rates and likely high variance
- N=10 gives reasonable power to detect medium-large effects
- Total: 4 tasks × 3 cohorts × 10 trials = 120 runs
- Estimated cost: $40-60, time: 4-6 hours

**Cohorts:**
1. **No memory** (baseline)
2. **Memory, current format** (retrieval-based)
3. **Memory, explicit prompting** ("CONSULT retrieved memories")

**Metrics:**
- Iteration count (primary)
- Time, tokens, cost
- Pass rate
- Memory was_referenced (%)
- Memory applied_success vs present_but_unused_success

### Phase 3: Qualitative Deep Dive

**For each cohort, sample 3 trajectories:**
- 1 fastest run
- 1 median run
- 1 slowest run

**Manual analysis:**
- Did agent reference memories?
- Did agent behavior align with memory guidance?
- If memory was present but not referenced, why?
- If memory was referenced but trajectory failed, why?

## Open Questions

### 1. Cold Start Problem

**Not actually a problem!**
- 73 memories already exist
- 9 have been used in previous runs
- System has learned from prior experiments

**Real question**: Are these 73 memories the RIGHT memories?
- Most are strategic guidance ("Incremental Data Source Investigation")
- Few are direct solutions (SPARQL templates)

### 2. Retrieval Quality

**Seems reasonable:**
- Bacteria taxa query → taxonomic memories
- E. coli K12 query → taxonomic + lineage memories
- BM25 retrieval is working

**Question**: Are retrieved memories ACTIONABLE?
- "Task Scope Recognition" has good advice
- But we saw agent not following it
- Format problem? Attention problem?

### 3. Architectural vs Execution

**Evidence for architectural problem:**
- Memories are strategic guidance, not direct solutions
- No routing logic (fast path vs slow path)
- No confidence-based decisions

**Evidence for execution problem:**
- Memory content is actually good ("Task Scope Recognition")
- Retrieval works (relevant memories retrieved)
- But agent doesn't explicitly consult them
- May need explicit instruction: "CONSULT memories before planning"

### 4. Success Rate Variance

**"Task Scope Recognition" succeeds 63% of the time**

**Possible explanations:**
1. **Task matching**: Works for some tasks, not others
2. **Stochasticity**: LLM variance in how it interprets context
3. **Context competition**: Sometimes memory is read, sometimes ignored
4. **Query complexity**: Works for simple queries, not complex ones

**Need to test**: Control for task type, analyze success vs failure cases

## Recommendations

### Immediate

1. ✅ **Document findings** (this document)
2. ⏭️ **Add application tracking** (was_referenced detection)
3. ⏭️ **Pilot test** (N=3, 1 task, verify tracking works)

### Short-term

4. ⏭️ **Run E009 sampling study** (N=10, 4 tasks, 3 cohorts)
5. ⏭️ **Statistical analysis** (test if memory impact is significant)
6. ⏭️ **Qualitative deep dive** (sample trajectories, manual analysis)

### Medium-term (Based on E009 results)

**If memory helps (p < 0.05, positive effect):**
- Optimize retrieval (tune k, improve BM25)
- Expand memory bank (more direct solutions)
- Add fast path routing

**If memory hurts (p < 0.05, negative effect):**
- Redesign architecture (Type A/B split)
- Add confidence-based routing
- Remove strategic guidance, focus on templates

**If no consistent effect (p > 0.05):**
- Increase N (higher power)
- Test explicit prompting cohort
- Reconsider hypothesis

## Summary

**What we thought (N=1)**: Memories are always ignored, always hurt performance

**What we know now**:
- Memory tracking IS working (22 runs, 59 usage records)
- "Task Scope Recognition" has been used 19 times (63% success rate)
- Our N=1 test may have been without tracking or different configuration
- Success rates vary (40-75%), suggesting memory helps SOMETIMES

**Key insight**: We have a STOCHASTICITY problem, not a COLD START problem

**Next step**: Proper sampling (E009) to understand:
- When do memories help vs hurt?
- Why does "Task Scope Recognition" succeed 63% of the time?
- Is agent actually USING memories or just having them present?

**User is correct**: N=1 is insufficient to conclude memories are fundamentally broken.
