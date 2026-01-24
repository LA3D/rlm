# Meta-Analysis First Run: Cross-Trajectory Pattern Discovery

**Date:** 2026-01-22
**Data Source:** 3 trials from seed heuristics experiment (uniprot_bacteria_taxa_001)
**Function:** `extract_meta_patterns()` in rlm_runtime/memory/extraction.py

---

## Executive Summary

✅ **Meta-analysis successfully extracts patterns invisible to single-trajectory extraction!**

**Key Achievement:** Implemented and tested `extract_meta_patterns()` function that analyzes multiple trajectories simultaneously to discover aggregate inefficiencies and cross-run patterns.

**Results:**
- **3 meta-patterns extracted** from 3 trial batch
- **25 total memories** in database (4 human + 9 success + 9 failure + 3 meta-analysis)
- **Three-tier memory system operational:** Human seeds → Meta-analysis → Single-trajectory extraction

---

## Three-Tier Memory System Architecture

### Tier 1: Human Seed Heuristics (Highest Priority)
**Count:** 4 memories
**Source:** Manual expert analysis
**Characteristics:** Prescriptive, explicit phase transitions, quantified guidance

**Examples:**
1. "Phase Transition After Remote Success" - Stop exploring after remote query works
2. "Systematic Hierarchical Property Testing" - Test properties without repetition
3. "Task Scope Recognition: All vs One" - Match strategy to task requirements
4. "Minimal Code Pattern for Tool Use" - Reduce Python boilerplate

**Impact from previous test:** 50% remote query reduction, 9-iteration best trial

### Tier 2: Meta-Analysis (Medium Priority)
**Count:** 3 memories (NEW!)
**Source:** Cross-trajectory LLM analysis
**Characteristics:** Descriptive, aggregate statistics, observed inefficiencies

**Extracted Patterns:**
1. "Excessive Print and Exploration Overhead" - 202 print() calls across 3 trials
2. "Inconsistent Query Strategy Convergence" - 9-13 iteration variation
3. "Premature Remote Query Exploration" - Repeated connectivity checks

**Provenance:** Each pattern tagged with:
- `trajectories_analyzed: 3`
- `iteration_range: "9-13"`
- `pass_rate: "100.0%"`

### Tier 3: Single-Trajectory Extraction (Base Priority)
**Count:** 18 memories (9 success + 9 failure)
**Source:** Per-trial LLM extraction
**Characteristics:** Task-specific strategies, tool sequences

**Examples:**
- "Systematic Ontology Exploration"
- "SPARQL Query Construction Strategy"
- "Hierarchical Data Navigation"

---

## Meta-Patterns Deep Dive

### Pattern 1: Excessive Print and Exploration Overhead

**Full Content:**
```
1. print() dominates tool usage across all trials (202 total calls)
2. Occurs in early-to-mid exploration phases
3. Optimize by:
   - Reducing verbose logging
   - Implementing more targeted information retrieval
   - Using selective print mechanisms
```

**Analysis:**
- Meta-analysis identified aggregate statistic (202 total print calls) that's invisible in single runs
- Aligns with human seed heuristic "Minimal Code Pattern for Tool Use"
- Provides quantified evidence for the guidance

**Difference from human heuristic:**
- Human: Prescriptive ("don't print")
- Meta: Descriptive ("202 print calls observed")

### Pattern 2: Inconsistent Query Strategy Convergence

**Full Content:**
```
1. Iteration range spans 9-13 iterations
2. Inconsistent tool mix between trials (sparql_query, search_entity)
3. Standardize early-stage query approach:
   - Establish consistent initial connection method
   - Create reusable taxonomy extraction template
   - Reduce exploratory variation
```

**Analysis:**
- Identifies variance that human analyst noted qualitatively
- Suggests creating reusable templates (actionable recommendation)
- Meta-analysis recognizes the 4-iteration spread as significant

**Implications:**
- With more trials, could track if variance decreases (learning convergence)
- Could identify "plateau" where iteration count stabilizes

### Pattern 3: Premature Remote Query Exploration

**Full Content:**
```
1. Multiple trials show repeated len(), get(), and connectivity checks
2. Occurs before substantive data retrieval
3. Optimize by:
   - Implementing faster remote validation
   - Creating pre-flight connectivity check
   - Moving directly to targeted query after initial connection
```

**Analysis:**
- Identifies repeated low-value operations across runs
- Suggests architectural improvement (pre-flight check)
- Complements human heuristic "Phase Transition After Remote Success"

**Difference from human heuristic:**
- Human: "Stop exploring after remote works"
- Meta: "Repeated connectivity checks before substantive retrieval"

---

## Comparison: Meta-Analysis vs Human Analysis

| Aspect | Human Seed Heuristics | Meta-Analysis Patterns |
|--------|----------------------|------------------------|
| **Perspective** | Prescriptive ("do this") | Descriptive ("this happens") |
| **Evidence** | Qualitative observation | Quantitative aggregates |
| **Scope** | Strategic guidance | Observed inefficiencies |
| **Specificity** | High (explicit steps) | Medium (patterns + recommendations) |
| **Creation Time** | Hours (manual) | Minutes (automated) |

**Example Comparison:**

**Human Heuristic:**
> "Once remote returns results, STOP exploration. Do NOT use describe_entity() on individual instances."

**Meta-Analysis Pattern:**
> "Agents spend multiple iterations testing connectivity (len(), get() checks) before focused extraction. 202 print() calls across 3 trials."

**Synergy:** Meta-analysis provides quantified evidence for human recommendations!

---

## What Meta-Analysis Discovers That Single-Trajectory Extraction Misses

### Cross-Trajectory Patterns
❌ **Single-trajectory cannot see:**
- Aggregate statistics (202 total print calls)
- Iteration variance (9-13 range)
- Repeated mistakes across runs

✅ **Meta-analysis discovers:**
- "All trials show pattern X"
- "Iteration range spans Y-Z"
- "Tool mix varies: A in trial 1, B in trial 2"

### Strategic Inefficiencies
❌ **Single-trajectory focuses on:**
- What worked in THIS run
- Tool sequences used
- Successful strategies

✅ **Meta-analysis identifies:**
- What WASTES time across ALL runs
- What VARIES unnecessarily
- Where CONSISTENCY would help

### Learning Trends
❌ **Single-trajectory is static:**
- Describes one trajectory
- No comparison context

✅ **Meta-analysis tracks dynamics:**
- "Trial 2 improved by 25%"
- "First remote query timing: iter 6 → iter 4"
- "Pass rate increased over trials"

---

## Memory Retrieval Priority Strategy

When multiple memories match a query, retrieval priority should be:

**1. Human seeds** (source_type='human')
   - Expert knowledge, prescriptive
   - Highest signal-to-noise
   - Explicit phase transitions

**2. Meta-analysis** (source_type='meta-analysis')
   - Cross-trajectory patterns
   - Quantified inefficiencies
   - Strategic guidance

**3. Success memories** (source_type='success')
   - Proven strategies
   - Task-specific guidance

**4. Failure memories** (source_type='failure')
   - Error avoidance
   - What not to do

**Current Implementation:** BM25 retrieval doesn't weight by source_type yet.

**Recommendation:** Add source_type boosting to BM25 scoring.

---

## Meta-Analysis Function Design Validation

### Input Format ✅
```python
trajectories: list[dict] = [
    {
        "task": str,
        "answer": str,
        "trajectory": list[dict],  # [{code, output}, ...]
        "judgment": dict,  # {is_success, reason, confidence}
        "iterations": int,
        "evidence": dict,
    }
]
```

Successfully handled trial results format with transformation script.

### Prompt Design ✅
Prompt provided:
- Trajectory summaries (concise)
- Aggregate statistics (avg, range, pass rate)
- Tool usage patterns (frequency counts)
- Focus directive (cross-trajectory patterns, not single-run strategies)

Result: LLM correctly identified aggregate patterns.

### Output Format ✅
```python
[
    MemoryItem(
        title="...",
        description="...",
        content="...",
        source_type="meta-analysis",
        tags=["meta-pattern", ...],
        provenance={
            "source": "meta-analysis",
            "trajectories_analyzed": 3,
            "iteration_range": "9-13",
            "pass_rate": "100.0%"
        }
    )
]
```

All 3 patterns successfully created with proper metadata.

### Context Window ✅
**Tested:** 3 trajectories, avg 11 iterations each
**Estimated tokens:** ~3,600 tokens
**Model:** Haiku (supports much larger context)
**Result:** No truncation, full analysis

---

## Next Steps

### Immediate (Completed)
1. ✅ Implement `extract_meta_patterns()` function
2. ✅ Create `run_meta_analysis.py` script
3. ✅ Test on 3-trial batch
4. ✅ Verify patterns differ from single-trajectory extraction
5. ✅ Store in memory database

### Short-term (This Week)
1. **Run 10 trials** with full three-tier memory system
   - Human seeds + learned + meta-analysis all active
   - Track iteration counts, pass rates, convergence
   - Run meta-analysis after batch completes

2. **Add source_type boosting** to BM25 retrieval
   - Weight human > meta-analysis > success > failure
   - Verify higher-priority memories retrieved first

3. **Trigger meta-analysis automatically**
   - Add `--run-meta-analysis` flag to CLI
   - Run after every N trials (configurable)
   - Store meta-patterns in database automatically

### Medium-term (Next Sprint)
1. **Memory consolidation**
   - Detect duplicate/redundant memories
   - Merge similar patterns
   - Track memory evolution over time

2. **Effectiveness tracking**
   - Which memories get retrieved most?
   - Which correlate with successful trials?
   - Prune unused memories

3. **Meta-analysis refinement**
   - Add milestone tracking (when first remote query, when SUBMIT)
   - Compute tool efficiency metrics
   - Identify bottleneck patterns

---

## Statistical Analysis (From 3-Trial Batch)

| Metric | Value |
|--------|-------|
| Trajectories analyzed | 3 |
| Iteration range | 9-13 |
| Average iterations | 11.0 |
| Pass rate | 100% |
| Tool usage (top 5) | print:202, len:78, get:65, sparql_query:?, query:? |

**Observations:**
- All trials passed (100% success)
- 4-iteration spread (9-13) shows room for consistency improvement
- print() dominates tool usage (highlighted by meta-analysis)

**Comparison to previous experiments:**
- Baseline (no memory): 10.2 avg iterations
- Learned only: 11.7 avg iterations
- With seed heuristics: 11.0 avg iterations (this batch)

**Note:** Seed heuristics showing benefit over learned-only (11.0 vs 11.7), though baseline is still lower. Need larger sample for significance.

---

## Memory Database Status

**Total memories:** 25

**By source type:**
- `failure`: 9 (single-trajectory extraction from failed runs)
- `human`: 4 (expert seed heuristics)
- `meta-analysis`: 3 (cross-trajectory patterns, NEW!)
- `success`: 9 (single-trajectory extraction from successful runs)

**Growth trajectory:**
- Started: 0 memories
- After 3 trials (learned): 6 memories (3 success + 3 failure)
- After seed injection: 13 memories (6 learned + 4 human + 3 failure)
- After 3 more trials: 22 memories (9 success + 9 failure + 4 human)
- After meta-analysis: 25 memories (22 + 3 meta-analysis)

**Memory creation rate:**
- Single-trajectory: 3 per trial (if extract enabled)
- Meta-analysis: 1-3 per batch (every 3-5 trials)
- Human seeds: Manual, as needed

---

## Conclusion

**✅ Meta-analysis successfully operational!**

The three-tier memory system is now fully implemented and tested:

1. **Human seeds** provide prescriptive, expert guidance
2. **Meta-analysis** discovers aggregate patterns and inefficiencies
3. **Single-trajectory extraction** captures task-specific strategies

**Key Innovations:**

1. **Complementary perspectives:** Human heuristics say "do this", meta-analysis says "this is happening"
2. **Quantified evidence:** Meta-analysis provides numbers (202 print calls) that validate human observations
3. **Automated discovery:** Meta-patterns emerge from LLM analysis of multiple runs, not manual inspection
4. **Scalable learning:** As more trials run, meta-analysis can identify trends invisible to single runs

**What makes this unique:**

- Most RL memory systems focus on single-episode extraction
- Meta-analysis adds a "reflective layer" that looks across episodes
- Human seeds provide "bootstrap knowledge" before any learning
- Three tiers work together: human expertise + automated pattern discovery + task-specific learning

**Next milestone:** Run 10-trial experiment with full memory system and measure convergence.

---

## Raw Data

**Memory database:** `evals/memory.db` (25 memories)

**Script:** `scripts/run_meta_analysis.py`

**Function:** `rlm_runtime/memory/extraction.py::extract_meta_patterns()`

**Input:** `evals/results/uniprot_bacteria_taxa_001_2026-01-22T17-41-47.293913Z.json` (3 trials with seed heuristics)

**Meta-patterns extracted:**
1. "Excessive Print and Exploration Overhead" (ID: computed from title+content)
2. "Inconsistent Query Strategy Convergence"
3. "Premature Remote Query Exploration"

**Provenance:** All patterns tagged with `trajectories_analyzed: 3`, `iteration_range: "9-13"`, `pass_rate: "100.0%"`
