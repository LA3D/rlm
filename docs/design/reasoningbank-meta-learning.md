# ReasoningBank Meta-Learning: Cross-Trajectory Pattern Discovery

**Date:** 2026-01-22
**Context:** After analyzing 3 trials, found patterns that ReasoningBank's single-trajectory extraction missed
**Questions:**
1. Can we inject hand-crafted heuristics into ReasoningBank?
2. Should ReasoningBank analyze multiple trajectories to discover meta-patterns?

---

## Question 1: Hand-Crafted Seed Heuristics

### Can We Inject Human-Discovered Heuristics?

**YES - Already supported!** MemoryItem has `source_type: 'human'` for this exact purpose.

### Implementation Approach

Create seed memories based on cross-trajectory analysis and inject them before trials:

```python
from rlm_runtime.memory import SQLiteMemoryBackend, MemoryItem
from datetime import datetime, timezone

# Initialize memory backend
backend = SQLiteMemoryBackend("evals/memory.db")

# Create seed heuristic based on our analysis
seed_heuristic = MemoryItem(
    memory_id=MemoryItem.compute_id(
        "Phase Transition After Remote Success",
        "Stop exploring after remote query succeeds"
    ),
    title="Phase Transition After Remote Success",
    description="Transition from exploration to execution phase once remote connectivity is validated",
    content="""1. Use query(local) to find target class and properties (1-2 iterations)
2. Test remote connection with simple query
3. **Once remote returns results, STOP exploration**
4. Switch to hierarchical query construction
5. Test rdfs:subClassOf+, skos:narrower+, etc.
6. Refine and submit

❌ Do NOT after remote works:
- describe_entity() on individual instances
- Exploratory queries for random samples
- Deep dives into single entities""",
    source_type="human",
    task_query="General SPARQL query construction",
    created_at=datetime.now(timezone.utc).isoformat(),
    tags=["meta-strategy", "efficiency", "phase-transition", "sparql", "exploration"],
    scope={"transferable": True, "task_types": ["sparql", "taxonomy", "hierarchy"]},
    provenance={"source": "cross-trajectory-analysis", "analyst": "human", "trials_analyzed": 3}
)

# Add to memory bank
backend.add_memory(seed_heuristic)
```

### Seed Heuristics to Create

Based on tool usage analysis, create 3-4 seed memories:

**1. Phase Transition After Remote Success** (above)
**2. Systematic Property Testing**
```python
MemoryItem(
    title="Systematic Hierarchical Property Testing",
    content="""When finding hierarchical relationships:
1. List candidate properties: rdfs:subClassOf, skos:narrower, owl:imports
2. Test each systematically (don't repeat failed properties)
3. If property returns 0 results after 1 attempt, move to next
4. Use probe_relationships() if all standard properties fail

Common hierarchy properties:
- rdfs:subClassOf / rdfs:subClassOf+ (transitive)
- skos:narrower / skos:narrowerTransitive+
- skos:broader / skos:broaderTransitive+
- owl:imports""",
    tags=["property-testing", "hierarchy", "sparql", "systematic"]
)
```

**3. Scope Awareness**
```python
MemoryItem(
    title="Task Scope Recognition",
    content="""Distinguish between task types:
- **Find ALL instances:** Use transitive queries, no LIMIT, test hierarchy
- **Find ONE example:** describe_entity, inspect sample, validate
- **Explore structure:** probe_relationships, schema queries

For 'find ALL bacteria':
✓ Use transitive hierarchy (?taxon subClassOf+ bacteria)
✗ Don't inspect individual taxa lineages""",
    tags=["task-scope", "strategy-selection", "all-vs-one"]
)
```

**4. Minimal Boilerplate**
```python
MemoryItem(
    title="Minimal Code Pattern for Tool Use",
    content="""Write minimal code focused on tool calls:
✓ Good: sparql_query(query, name)
✗ Bad: result = sparql_query(...); for row in result: print(row)

Tool outputs are logged automatically.
- Don't print() results
- Don't use for-loops just to display
- Trust tool outputs without manual inspection

Use ~5-15 lines per iteration, not 30-50.""",
    tags=["code-style", "efficiency", "boilerplate"]
)
```

### Testing Seed Heuristics

**Experiment design:**
1. Clear existing memory database
2. Inject 4 seed heuristics
3. Run 5 trials with memory enabled
4. Compare to baseline (3 trials with learned memories)

**Expected outcome:**
- Seed heuristics retrieved early (high relevance to query)
- Faster phase transitions (iteration 3-4 vs 6+)
- Fewer remote queries (2-3 vs 6)
- Lower average iterations (6-7 vs 10)

---

## Question 2: Cross-Trajectory Pattern Discovery

### What Patterns Did Human Analysis Find?

**Single-trajectory patterns** (current extraction could find):
- ✅ "Use query(local) before sparql_query(remote)" - sequence within one run
- ✅ "Test simple query before complex query" - progression within one run
- ✅ "Extract using transitive property paths" - successful pattern in one run

**Cross-trajectory patterns** (current extraction misses):
- ❌ **"Iterations 5-8 are wasteful across all trials"** - requires comparing 3 runs
- ❌ **"All trials try up:partOfLineage 2-3 times before abandoning"** - repeated mistake pattern
- ❌ **"First remote query happens at iteration 6 for trials 0-1, iteration 4 for trial 2"** - milestone comparison
- ❌ **"6 remote queries average when 2-3 would suffice"** - aggregate statistics
- ❌ **"Trial 2 learned to move faster"** - learning trajectory over time

### Current Extraction Limitations

**Single-trajectory extraction** (lines 234-265 in extraction.py):
```python
prompt = f"""Extract 1-3 reusable procedural memories from this RLM trajectory.

Task: {task}
Answer: {answer}
Outcome: {"Success" if judgment['is_success'] else "Failure"}

Execution Steps:
{steps_text}

Focus on:
- Generalizable patterns (not task-specific details)
- Tool usage strategies
- Error handling if failure
"""
```

**What it CAN'T see:**
- Patterns across multiple runs
- Aggregate inefficiencies (common waste)
- Milestone timing (when things happen)
- Learning progression (iteration count trends)
- Repeated mistakes across trials

### Could LLM-Based Meta-Analysis Work?

**YES, with modifications!** But needs:

1. **Multiple trajectories in one prompt**
2. **Different extraction prompt** (meta-patterns, not strategies)
3. **Additional context** (iteration counts, milestones, timestamps)

---

## Proposed: Meta-Analysis Function

### Architecture

Add new function to `rlm_runtime/memory/extraction.py`:

```python
def extract_meta_patterns(
    trajectories: list[dict],  # List of {task, answer, trajectory, judgment, iterations}
    *,
    min_trajectories: int = 3,
    model: str = "anthropic/claude-3-5-haiku-20241022",
) -> list[MemoryItem]:
    """Extract meta-patterns by analyzing multiple trajectories.

    Identifies:
    - Common inefficiencies across runs
    - Repeated mistakes (trying same wrong approach)
    - Phase transition patterns (when to stop exploring)
    - Aggregate metrics (iteration counts, tool usage)

    Args:
        trajectories: List of trajectory dicts with judgment and iteration count
        min_trajectories: Minimum trajectories needed for meta-analysis (default: 3)
        model: Model for analysis (default: Haiku)

    Returns:
        List of MemoryItem objects with source_type='meta-analysis'
    """
```

### Prompt Design

```python
prompt = f"""Analyze these {len(trajectories)} trajectories for the same task and extract meta-patterns.

Task: {task}

Trajectory Summaries:
{trajectory_summaries}

Iteration Statistics:
- Average: {avg_iterations:.1f}
- Range: {min_iterations}-{max_iterations}
- Pass rate: {pass_rate:.1%}

Tool Usage Patterns:
{tool_usage_summary}

Identify:
1. **Common Inefficiencies:** What wastes iterations across multiple runs?
2. **Repeated Mistakes:** What wrong approaches are tried multiple times?
3. **Phase Transitions:** When should agent stop exploring and start executing?
4. **Meta-Strategies:** High-level guidance (not captured in single-run analysis)

Format as JSON array (1-3 meta-patterns):
[
  {{
    "title": "...",
    "description": "Cross-trajectory pattern identified",
    "content": "1. Pattern description\n2. When it occurs\n3. How to avoid/optimize",
    "tags": ["meta-pattern", "efficiency", ...]
  }}
]

Focus on patterns visible only when comparing multiple runs.
"""
```

### When to Run Meta-Analysis

**Trigger conditions:**
1. **Every N trials** (e.g., after every 5 trials)
2. **When learning plateaus** (iteration count stops improving)
3. **On-demand** (manual trigger for cohort analysis)
4. **End of experiment** (batch analysis of all trials)

### Context Window Constraints

**Can Haiku handle 3+ trajectories?**

**Trajectory size per run:**
- 10 iterations × 100 tokens/iter = 1,000 tokens
- Plus judgment, stats, tools = 1,200 tokens total

**For 3 trajectories:** 3 × 1,200 = 3,600 tokens (well within Haiku's limit)

**For 5 trajectories:** 5 × 1,200 = 6,000 tokens (still fine)

**For 10 trajectories:** Would need summarization or sampling

**Verdict:** Haiku can handle 3-5 full trajectories comfortably.

---

## Design Decision: Batch vs Incremental

### Option A: Batch Meta-Analysis
**When:** After N trials complete
**Input:** All N trajectories
**Output:** Meta-patterns based on aggregate analysis

**Pros:**
- Can see cross-trajectory patterns
- Aggregate statistics available
- Identifies repeated mistakes

**Cons:**
- Delayed feedback (wait for N trials)
- Doesn't update existing memories
- One-shot analysis

### Option B: Incremental Refinement
**When:** After each trial
**Input:** New trajectory + existing memories
**Output:** Updated/refined memories

**Process:**
```python
# After trial N:
new_memories = extract_memories_dspy(trial_N)  # Current approach

# New step: Compare with existing memories
for new_mem in new_memories:
    similar = find_similar_memories(new_mem, threshold=0.8)
    if similar:
        # Refine/consolidate instead of adding duplicate
        refined = refine_memory(similar, new_mem, evidence=[trial_N])
        update_memory(refined)
    else:
        add_memory(new_mem)
```

**Pros:**
- Continuous learning
- Memory consolidation
- Immediate feedback

**Cons:**
- Harder to see aggregate patterns
- Can't compare cross-trajectory statistics
- More complex bookkeeping

### Recommendation: Hybrid Approach

**Tier 1: Single-trajectory extraction** (current, after each trial)
- Extracts strategies from individual runs
- Source: "success" or "failure"

**Tier 2: Meta-analysis** (every 5 trials)
- Analyzes batch of 5 trajectories
- Extracts inefficiency patterns
- Source: "meta-analysis"
- Higher priority in retrieval (more general)

**Tier 3: Manual seed heuristics** (as needed)
- Human-crafted from deep analysis
- Source: "human"
- Highest priority (expert knowledge)

---

## Implementation Plan

### Phase 1: Seed Heuristics (Immediate - 1 hour)
1. Create 4 seed MemoryItem objects based on tool usage analysis
2. Add script: `scripts/seed_memory_heuristics.py`
3. Inject into evals/memory.db
4. Run 3 trials to test effectiveness
5. Compare: seed heuristics vs learned memories

### Phase 2: Meta-Analysis Function (Next - 4 hours)
1. Add `extract_meta_patterns()` to extraction.py
2. Design cross-trajectory analysis prompt
3. Add trigger: run after every 5 trials
4. Test on existing 3 trials + 2 new trials
5. Verify meta-patterns differ from single-trajectory memories

### Phase 3: Memory Consolidation (Future - 8 hours)
1. Add `find_similar_memories()` using embedding similarity
2. Add `refine_memory()` to consolidate duplicates
3. Add memory versioning (track updates)
4. Test on 10+ trial dataset

---

## Expected Outcomes

### With Seed Heuristics:
- **Trial 1:** Uses human heuristics → **6-7 iterations** (vs 12 baseline)
- **Trial 2-3:** Combines human + learned → **5-6 iterations**
- **Faster phase transitions** (iteration 3 vs 6)
- **Fewer exploratory queries** (2-3 vs 6 remote queries)

### With Meta-Analysis (after 5 trials):
- Extracts: **"Iterations 5-8 are consistently exploratory waste"**
- Extracts: **"All runs try up:partOfLineage before succeeding"**
- Extracts: **"Phase transition should happen by iteration 4"**
- These become high-priority memories for future trials

### Combined Impact:
**Baseline (no memory):** 10-13 iterations
**With learned memories:** 10-12 iterations (modest improvement)
**With seed heuristics:** 6-7 iterations (40% improvement)
**With seed + meta-analysis:** 5-6 iterations (50% improvement)

---

## Open Questions

### 1. Memory Priority/Ranking
When multiple memories retrieved, which takes precedence?
- Proposal: human > meta-analysis > success > failure
- Or: Weight by (access_count × success_rate)?

### 2. Memory Consolidation Strategy
When is a memory "redundant" vs "complementary"?
- Semantic similarity threshold?
- Tag overlap?
- Manual curation?

### 3. Meta-Analysis Frequency
How often to run batch analysis?
- Every N trials (fixed)?
- When variance increases (adaptive)?
- End of experiment only (retrospective)?

### 4. Context Window Management
For 10+ trajectories, how to summarize?
- Sample representative runs?
- Aggregate statistics only?
- Cluster and analyze clusters?

### 5. Feedback Loop
How to measure if meta-patterns help?
- A/B test: with vs without meta-analysis?
- Track iteration reduction over time?
- Manual inspection of agent behavior?

---

## Comparison: Human vs LLM Meta-Analysis

### What Human Analysis Found (Cross-Trajectory)
1. "First remote query at iteration 6 for T0-1, iteration 4 for T2" (milestone timing)
2. "6 remote queries average when 2-3 needed" (aggregate statistics)
3. "Iterations 5-8 are exploratory waste across all trials" (common pattern)
4. "All try up:partOfLineage 2-3 times" (repeated mistake)
5. "Trial 2 learned to move 33% faster" (learning progression)

### Could Meta-Analysis Extract Discover This?

**Pattern 1-2:** ✅ YES - with iteration counts and milestone tracking
**Pattern 3:** ✅ YES - LLM can identify common waste across summaries
**Pattern 4:** ✅ YES - repeated tool call pattern visible in trajectories
**Pattern 5:** ✅ YES - compare iteration counts across trials

**Verdict:** Meta-analysis function COULD discover these patterns, but needs:
- Milestone tracking (when first remote query, when SUBMIT)
- Tool usage counts (how many sparql_query calls)
- Iteration counts and pass/fail status

These are all available - just need to format for the meta-analysis prompt.

---

## Recommendation

**Implement both approaches:**

**Short-term (this week):**
1. ✅ Create 4 seed heuristics from tool usage analysis
2. ✅ Inject into memory.db and test with 3 trials
3. ✅ Measure impact on iteration count

**Medium-term (next sprint):**
1. 🔄 Implement `extract_meta_patterns()` function
2. 🔄 Run after every 5 trials automatically
3. 🔄 Compare meta-patterns to single-trajectory memories

**Long-term (future):**
1. ⏳ Add memory consolidation/refinement
2. ⏳ Implement adaptive meta-analysis triggering
3. ⏳ Build memory dashboard for inspection

This gives us:
- **Immediate value** from expert knowledge (seed heuristics)
- **Automated discovery** of patterns we might miss (meta-analysis)
- **Continuous improvement** as more trials run

