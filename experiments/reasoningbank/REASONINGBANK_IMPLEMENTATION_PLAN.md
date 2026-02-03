# ReasoningBank Implementation Plan: Stochastic Memory-Driven Learning for RLM

**Version**: 2.0
**Date**: February 2026
**Status**: Research Experiment
**Supersedes**: JUDGE_MEMORY_EXPERIMENT_PLAN.md

---

## Executive Summary

This document outlines an **evidence-based, incremental implementation** of ReasoningBank for RLM agents conducting ontology exploration and SPARQL query construction. Unlike the previous plan, this implementation recognizes that:

1. **Agent behavior is stochastic** - single-trajectory evaluation is unreliable
2. **Ensemble methods (MaTTS) are essential** - multiple trajectories provide contrastive signals
3. **Self-contrast across trajectories** is the key to quality memory extraction
4. **Evidence must guide decisions** - calibration before commitment

**Core Research Question**: Can memory-aware test-time scaling (MaTTS) improve RLM agent performance on ontology query tasks, and does the ReasoningBank methodology transfer from web browsing to structured knowledge graph reasoning?

**Key Difference from Web Browsing Domain**: SPARQL query construction may be more deterministic than web navigation. We must first establish whether stochastic ensemble methods provide value in our domain before scaling up.

---

## 1. ReasoningBank Methodology (From the Paper)

### 1.1 Core Loop

```
┌─────────────────────────────────────────────────────────────────────────┐
│  ReasoningBank Closed Loop                                               │
│                                                                          │
│  For each task in streaming sequence:                                    │
│                                                                          │
│  1. RETRIEVE: Query memory bank for relevant strategies (k=1 default)    │
│  2. RUN: Execute k trajectories (parallel scaling) or k refinements      │
│  3. JUDGE: LLM-as-judge labels each trajectory success/failure           │
│  4. CONTRAST: Compare successful vs failed trajectories (MaTTS)          │
│  5. EXTRACT: Distill transferable strategies from contrast               │
│  6. CONSOLIDATE: Add new memories to bank (simple append)                │
│                                                                          │
│  Key Insight: Step 4 (CONTRAST) is what makes MaTTS better than          │
│  vanilla test-time scaling. Multiple trajectories on SAME task           │
│  provide contrastive signals for better extraction.                      │
└─────────────────────────────────────────────────────────────────────────┘
```

### 1.2 MaTTS: Memory-Aware Test-Time Scaling

The paper introduces two complementary scaling strategies:

**Parallel Scaling** (Primary):
- Generate k trajectories for same task simultaneously
- Self-contrast across trajectories to identify success patterns
- Best-of-N selection for final answer
- Contrastive extraction: "what made successful ones succeed?"

**Sequential Scaling** (Secondary):
- Iteratively refine a single trajectory through k self-checks
- Intermediate reasoning signals captured for memory
- Less effective than parallel at higher k

**Key Finding**: Memory and scaling create a **virtuous cycle**:
- Better memory → more effective scaling (guides exploration)
- More scaling → better memory (more contrastive signal)
- Weaker memory methods (Synapse, AWM) actually get WORSE with scaling

### 1.3 Critical Parameters (From Paper)

| Parameter | Paper Default | Rationale |
|-----------|---------------|-----------|
| **Temperature (generation)** | 0.7 | Stochastic exploration needed for diverse trajectories |
| **Temperature (judge)** | 0.0 | Deterministic judgment for consistency |
| **Scaling factor k** | 3-5 | k=3 typical, k=5 for maximum benefit |
| **Retrieved memories** | k=1 | More memories hurt (k=4: 49.7→44.4%) |
| **Extracted per trajectory** | ≤3 | Concise, non-redundant |

### 1.4 Evaluation Metrics

| Metric | Definition | When to Use |
|--------|------------|-------------|
| **Pass@1** | Success rate of randomly selected trajectory | Measures average quality |
| **Best-of-N (BoN)** | Success rate when selecting best trajectory | Measures ceiling with selection |
| **Pass@k** | Probability at least 1 of k trajectories succeeds | Measures coverage |

**Key Insight**: Pass@1 vs BoN gap shows how much ensemble selection helps. If gap is small, stochastic methods may not apply to our domain.

---

## 2. Research Questions (Revised for Stochastic Approach)

### Primary Research Questions

**RQ1: Domain Applicability**
- Does stochastic variation exist in SPARQL query construction?
- Is the Pass@1 vs Best-of-N gap significant in our domain?
- Does parallel scaling help more than single trajectories?

**RQ2: Memory Effectiveness Under Ensembles**
- Does memory improve Pass@1 (average quality)?
- Does memory improve Best-of-N (ceiling performance)?
- Does memory + scaling show synergy (virtuous cycle)?

**RQ3: Contrastive Extraction Quality**
- Does self-contrast across k trajectories produce better memories than single-trajectory extraction?
- Do failure guardrails from contrast provide value?

**RQ4: Transfer from Web Browsing**
- Do the paper's findings (k=1 retrieval, 0.7 temperature, etc.) transfer to our domain?
- What domain-specific adjustments are needed?

**RQ5: Human-in-Loop Integration**
- When does human-guided contrastive extraction outperform automated?
- What's the cost/benefit of human review?

### Hypotheses

**H1: Stochastic Variation Exists**
- Running same task with temperature=0.7 produces measurably different trajectories
- Expected variance: 10-30% of runs differ in success/failure outcome

**H2: Ensemble Methods Help**
- Best-of-5 > Pass@1 by at least 10% relative improvement
- If not, our domain may require different approach

**H3: Memory + Scaling Synergy**
- With memory: Pass@1 at k=5 > Pass@1 at k=1
- Without memory: Smaller or no improvement

**H4: Contrastive > Single Extraction**
- Memories extracted from self-contrast are more transferable
- Measured by: downstream task success when using extracted memories

**H5: Human Contrastive Review is High-Value**
- Human-guided contrastive extraction (comparing trajectories) produces higher-quality memories than automated
- But: Human review of every extraction has diminishing returns

---

## 3. System Architecture

### 3.1 Core Components

```
┌─────────────────────────────────────────────────────────────────────────┐
│  MaTTS-Enabled ReasoningBank System                                      │
│                                                                          │
│  ┌────────────────────────────────────────────────────────────────────┐ │
│  │  PARALLEL RUNNER (k trajectories)                                   │ │
│  │                                                                      │ │
│  │   Task ──┬──→ Trajectory 1 ──→ Judge ──→ success/failure            │ │
│  │          ├──→ Trajectory 2 ──→ Judge ──→ success/failure            │ │
│  │          ├──→ Trajectory 3 ──→ Judge ──→ success/failure            │ │
│  │          └──→ ...                                                    │ │
│  │                                                                      │ │
│  │   All trajectories share: retrieved memories, context (L0/L1/L3)    │ │
│  └────────────────────────────────────────────────────────────────────┘ │
│                           │                                              │
│                           ▼                                              │
│  ┌────────────────────────────────────────────────────────────────────┐ │
│  │  SELF-CONTRAST EXTRACTOR                                            │ │
│  │                                                                      │ │
│  │   Input: All k trajectories + judge verdicts                        │ │
│  │   Process: Compare successful vs failed trajectories                │ │
│  │   Output: Contrastive memories (what made success succeed?)         │ │
│  │                                                                      │ │
│  │   If all succeed: Extract common patterns                           │ │
│  │   If all fail: Extract failure guardrails                           │ │
│  │   If mixed: Extract contrastive strategies (most valuable)          │ │
│  └────────────────────────────────────────────────────────────────────┘ │
│                           │                                              │
│                           ▼                                              │
│  ┌────────────────────────────────────────────────────────────────────┐ │
│  │  MEMORY STORE (SQLite + FTS5)                                       │ │
│  │                                                                      │ │
│  │   Items: {title, desc, content, src, tags, provenance}              │ │
│  │   Retrieval: Embedding-based similarity (k=1 default)               │ │
│  │   Consolidation: Simple append (no pruning in v1)                   │ │
│  └────────────────────────────────────────────────────────────────────┘ │
└─────────────────────────────────────────────────────────────────────────┘
```

### 3.2 Memory Schema

```python
@dataclass
class MemoryItem:
    # Core fields (from paper)
    id: str                      # SHA256(title + content)
    title: str                   # ≤10 words, concise identifier
    desc: str                    # 1 sentence summary
    content: str                 # Full procedure/strategy/guardrail
    src: str                     # 'success' | 'failure' | 'contrastive' | 'seed' | 'human'

    # Provenance
    created_at: float            # Unix timestamp
    task_id: str                 # Source task
    run_id: str                  # Source run (may have multiple trajectories)
    extraction_method: str       # 'single' | 'contrastive' | 'human-guided'

    # For contrastive extraction
    trajectory_ids: list[str]    # All trajectories used for extraction
    contrast_summary: str|None   # What made successful trajectories succeed

    # Quality tracking (measured over time)
    retrieval_count: int = 0
    downstream_success_rate: float = 0.0  # Success rate when this memory was retrieved
```

### 3.3 Judge (Simplified)

The paper uses a **single LLM-as-judge** with binary output, not the two-phase architecture in the previous plan.

```python
class TrajectoryJudge(dspy.Signature):
    """Judge whether a trajectory successfully completed the task."""

    task: str = dspy.InputField(desc="The original task/query")
    trajectory: str = dspy.InputField(desc="Condensed trajectory (thinking + actions + final state)")
    final_output: str = dspy.InputField(desc="Agent's final answer/SPARQL")

    reasoning: str = dspy.OutputField(desc="Step-by-step analysis of whether task was completed")
    verdict: Literal["Success", "Failure"] = dspy.OutputField()

def judge_trajectory(task: str, trajectory: str, final_output: str) -> dict:
    """Simple binary judge with deterministic temperature."""
    judge = dspy.Predict(TrajectoryJudge, temperature=0.0)
    result = judge(task=task, trajectory=trajectory, final_output=final_output)
    return {
        'success': result.verdict == "Success",
        'reasoning': result.reasoning
    }
```

**Judge Best Practices** (from evaluation literature):

1. **Binary output** - Avoid scoring scales (less reliable)
2. **Chain-of-thought** - Require reasoning before verdict
3. **Deterministic** - Use temperature=0.0 for consistency
4. **Position bias mitigation** - Randomize order when comparing (for contrastive)
5. **Same backbone** - Use same model as agent for consistency

### 3.4 Self-Contrast Extractor

The key innovation from MaTTS - extract memories by comparing trajectories:

```python
class ContrastiveExtractor(dspy.Signature):
    """Extract transferable strategies by comparing successful vs failed trajectories."""

    task: str = dspy.InputField()
    successful_trajectories: str = dspy.InputField(desc="Trajectories that succeeded")
    failed_trajectories: str = dspy.InputField(desc="Trajectories that failed")

    analysis: str = dspy.OutputField(desc="""
        1. What patterns appear in successful trajectories?
        2. What mistakes appear in failed trajectories?
        3. What specific actions/strategies made the difference?
    """)

    memories: list[dict] = dspy.OutputField(desc="""
        Up to 3 memory items, each with:
        - title: Concise identifier (≤10 words)
        - description: One sentence summary
        - content: Actionable procedure/strategy
        - src: 'success' | 'failure' | 'contrastive'
    """)

def extract_contrastive(task: str, trajectories: list[dict]) -> list[MemoryItem]:
    """Extract memories from k trajectories using self-contrast."""
    successes = [t for t in trajectories if t['judgment']['success']]
    failures = [t for t in trajectories if not t['judgment']['success']]

    if len(successes) == 0:
        # All failed - extract failure guardrails
        return extract_failure_guardrails(task, failures)
    elif len(failures) == 0:
        # All succeeded - extract common success patterns
        return extract_success_patterns(task, successes)
    else:
        # Mixed - contrastive extraction (most valuable!)
        extractor = dspy.Predict(ContrastiveExtractor, temperature=0.7)
        result = extractor(
            task=task,
            successful_trajectories=format_trajectories(successes),
            failed_trajectories=format_trajectories(failures)
        )
        return parse_memories(result.memories, extraction_method='contrastive')
```

### 3.5 Layer Cake Context (Unchanged)

```python
@dataclass
class ContextConfig:
    l0: bool = True   # Ont-Sense (~600 chars) - ontology metadata
    l1: bool = True   # Schema Constraints (~1000 chars) - anti-patterns, domain/range
    l2: bool = True   # Procedural Memory (~2000 chars) - retrieved memories
    l3: bool = False  # Guide Summary (~1000 chars) - compressed exploration guide

    # L2 retrieval (paper default: k=1)
    l2_retrieval_k: int = 1  # Number of memories to retrieve
```

---

## 4. Experimental Design: Evidence-Based Incremental Approach

### 4.1 Philosophy

Instead of committing to an 11-week plan upfront, we use an **evidence-based incremental approach**:

1. **Calibration Phase**: Establish whether stochastic methods apply to our domain
2. **Decision Points**: Make go/no-go decisions based on evidence
3. **Pivot Capability**: If evidence contradicts assumptions, change approach

### 4.2 Task Corpus

**Primary Dataset**: UniProt SPARQL Examples
- **Source**: `ontology/uniprot/examples/UniProt/*.ttl` (46 SHACL examples)
- **Ground Truth**: Each example includes `sh:select` with expected SPARQL

**Task Subsets**:
- **Calibration Set**: 10 diverse tasks (2 per complexity level)
- **Development Set**: 16 tasks for iterating
- **Held-Out Test Set**: 20 tasks for final evaluation

### 4.3 Phase 0: Stochastic Calibration (1 week)

**Goal**: Establish whether ReasoningBank methodology applies to our domain.

**Critical Question**: Does stochastic variation exist in SPARQL query construction?

#### E0.1: Variance Measurement

```
Run 10 calibration tasks × 5 trajectories each = 50 runs

Configuration:
- Temperature: 0.7 (generation), 0.0 (judge)
- Context: L0 + L1 (no memory)
- No parallel execution - sequential to measure variance

Metrics per task:
- Success count: How many of 5 trajectories succeed?
- Pass@1: Random trajectory success rate
- Best-of-5: Best trajectory success rate
- Variance: Standard deviation of outcomes

Aggregate metrics:
- Per-task variance distribution
- Pass@1 vs Best-of-5 gap (key indicator)
- Tasks with mixed outcomes (needed for contrastive extraction)
```

**Decision Point**:

| Outcome | Interpretation | Action |
|---------|----------------|--------|
| **High variance** (2-4 successes per task typical) | Stochastic methods apply | Continue to E0.2 |
| **Low variance** (0-1 or 4-5 successes typical) | Domain may be more deterministic | Consider lower temperature, or pivot to single-trajectory approach |
| **All succeed** (5/5 on most tasks) | Tasks too easy | Need harder tasks or stricter success criteria |
| **All fail** (0/5 on most tasks) | Tasks too hard or system broken | Debug before proceeding |

#### E0.2: Memory Effect Under Ensembles

**Only if E0.1 shows variance exists.**

```
Run 10 calibration tasks × 5 trajectories each = 50 runs

Condition A: No memory (L0 + L1 only)
Condition B: With current memory bank (L0 + L1 + L2, k=1 retrieval)

Compare:
- Pass@1_A vs Pass@1_B
- BoN_A vs BoN_B
- Per-task improvement

Statistical test: Paired t-test or Wilcoxon signed-rank
```

**Decision Point**:

| Outcome | Interpretation | Action |
|---------|----------------|--------|
| **Memory helps Pass@1** | Memory improves average quality | Continue to E0.3 |
| **Memory helps BoN only** | Memory helps best case but not average | May need better retrieval |
| **Memory hurts** | Current memory bank is noise | Review memory quality before proceeding |
| **No difference** | Memory neutral | May need domain-specific memories |

#### E0.3: Contrastive Extraction Pilot

**Only if E0.2 shows promise.**

```
Take 5 tasks with mixed outcomes (from E0.1/E0.2)

For each task:
1. Run self-contrast extraction on the k=5 trajectories
2. Also run single-trajectory extraction (baseline)

Compare extracted memories:
- Specificity: Do contrastive memories reference specific patterns?
- Actionability: Can future agents use these?
- Novelty: Are they different from existing memories?
```

**Deliverables (Phase 0)**:
- Variance analysis report
- Go/no-go decision on stochastic approach
- If go: Validated calibration (temperature, k, etc.)
- If no-go: Alternative approach recommendation

---

### 4.4 Phase 1: Parallel Scaling Validation (1-2 weeks)

**Prerequisites**: Phase 0 shows stochastic methods apply.

**Goal**: Validate that MaTTS (memory-aware test-time scaling) provides benefit.

#### E1.1: Parallel Scaling Baseline

```
Run 16 development tasks with k=3 parallel trajectories

Configuration:
- Temperature: 0.7
- Context: L0 + L1 (no memory)
- Judge each trajectory independently

Metrics:
- Pass@1 (random selection)
- Best-of-3 (optimal selection)
- Pass@3 (any success)
```

#### E1.2: Memory + Parallel Scaling

```
Same 16 tasks with k=3 parallel trajectories

Configuration:
- Temperature: 0.7
- Context: L0 + L1 + L2 (with memory retrieval, k=1)
- Same memory bank for all

Compare to E1.1:
- Δ Pass@1 (does memory improve average?)
- Δ Best-of-3 (does memory improve ceiling?)
- Synergy test: Is improvement > additive?
```

#### E1.3: Contrastive Extraction at Scale

```
For each task in E1.2 with mixed outcomes:
1. Run self-contrast extraction
2. Add extracted memories to bank (simple append)
3. Track downstream impact

Measure over 16 tasks:
- Memory bank growth
- Extraction quality (human review sample)
- Downstream success improvement (later tasks)
```

**Decision Point**:

| Outcome | Interpretation | Action |
|---------|----------------|--------|
| **Synergy observed** | Memory + scaling reinforce each other | Continue to Phase 2 |
| **Parallel helps but memory doesn't** | May need better retrieval | Focus on retrieval before Phase 2 |
| **Memory helps but parallel doesn't** | Domain may be more deterministic | Consider sequential scaling or single-trajectory |
| **Neither helps** | Approach may not transfer | Major pivot needed |

---

### 4.5 Phase 2: Closed-Loop Learning (2-3 weeks)

**Prerequisites**: Phase 1 shows memory + scaling synergy.

**Goal**: Run full closed-loop learning and measure learning curve.

#### E2.1: Streaming Task Sequence

```
Run 20 held-out tasks in streaming sequence

For each task:
1. Retrieve relevant memories (k=1)
2. Run k=3 parallel trajectories
3. Judge all trajectories
4. Best-of-3 selection for answer
5. Self-contrast extraction
6. Append new memories to bank

Track over time:
- Cumulative Pass@1
- Cumulative Best-of-3
- Memory bank size
- Memory quality (periodic human review)
```

#### E2.2: Learning Curve Analysis

```
Plot cumulative metrics vs task number:
- Does success rate improve over time?
- When does improvement plateau?
- Which memories are most retrieved/impactful?

Compare to baseline (no memory, single run)
```

#### E2.3: Ablation Studies

```
Condition A: Full system (MaTTS + contrastive extraction)
Condition B: MaTTS without contrastive (vanilla extraction)
Condition C: Single trajectory with memory
Condition D: Single trajectory without memory

Run on same 20 tasks
Compare learning curves
```

**Deliverables (Phase 2)**:
- Learning curve analysis
- Memory bank quality assessment
- Ablation results
- Recommendations for production

---

## 5. Human-in-the-Loop Integration

### 5.1 Philosophy

Human expertise is valuable for:
1. **Contrastive review** - Comparing trajectories to extract subtle patterns
2. **Memory refinement** - Clarifying when/why to use a strategy
3. **Quality control** - Catching judge errors

Human expertise is NOT needed for:
1. Routine high-confidence extractions
2. Every single trajectory review
3. Replacing automated systems entirely

### 5.2 Tool: `memory_reflect.py`

**Three modes aligned with MaTTS methodology:**

#### Mode 1: Human-Guided Contrastive Extraction

The most valuable use of human time - comparing multiple trajectories:

```bash
python tools/memory_reflect.py \
    --trajectories results/task_123_traj_*.jsonl \
    --memory memories.json \
    --hint "Trajectory 2 succeeded with property path; trajectories 1,3 failed with UNION" \
    --contrastive --interactive --save memories.json
```

**When to use**:
- Tasks with mixed outcomes (some success, some failure)
- Human notices pattern the automated extractor missed
- Domain-specific insight needed

#### Mode 2: Single Trajectory Reflection

For efficient runs or unique insights:

```bash
python tools/memory_reflect.py \
    --trajectory results/efficient_run.jsonl \
    --memory memories.json \
    --hint "Agent used early-exit pattern saving 5 iterations" \
    --interactive --save memories.json
```

**When to use**:
- Exceptionally efficient trajectories
- Novel strategies not in contrastive set
- Efficiency patterns (iteration reduction)

#### Mode 3: Memory Refinement

Improving existing memories based on new evidence:

```bash
python tools/memory_reflect.py \
    --trajectory results/new_evidence.jsonl \
    --memory memories.json \
    --refine <memory_id> \
    --hint "Memory works for simple cases but needs exception for federated queries" \
    --interactive --save memories.json
```

**When to use**:
- Memory retrieved but not helpful
- Memory too vague or too specific
- Memory partially wrong

### 5.3 Integration with MaTTS

```python
# In closed-loop with human review integration
for task in tasks:
    trajectories = run_parallel(task, k=3)
    judgments = [judge(t) for t in trajectories]

    successes = sum(j['success'] for j in judgments)

    if successes == 0 or successes == 3:
        # Unanimous outcome - automated extraction sufficient
        memories = extract_automated(task, trajectories, judgments)
        memory_bank.add_all(memories)

    elif successes in [1, 2]:
        # Mixed outcome - high value for contrastive extraction
        # Queue for human review if capacity allows
        if human_review_queue.has_capacity():
            human_review_queue.add(task, trajectories, judgments)
        else:
            # Fall back to automated contrastive
            memories = extract_contrastive(task, trajectories, judgments)
            memory_bank.add_all(memories)
```

### 5.4 Quality Guidelines (Preserved from Original)

**When to Use Human Reflection**:

✅ **DO use for**:
- Mixed-outcome tasks (contrastive extraction opportunity)
- Correcting known judge errors
- Domain expertise injection (ontology-specific conventions)
- Efficiency pattern extraction

❌ **DON'T use for**:
- Routine unanimous outcomes (automate those)
- Every single extraction (defeats scalability)
- General advice without trajectory grounding

**Memory Quality Standards**:

1. **Grounded in Trajectory**: Must reference specific patterns from trajectories
2. **Actionable**: Future agent can execute the procedure
3. **Scoped**: Clear about when to use AND when NOT to use
4. **Concrete**: Include SPARQL patterns, not just abstract advice

**Example - Good vs Bad**:

❌ **Bad** (too abstract):
```
Title: "Use Good SPARQL Practices"
Content: "Write clean queries that follow best practices."
```

✅ **Good** (concrete + contrastive):
```
Title: "Use Property Paths for Transitive Hierarchy"
Content: "When querying class hierarchies, use rdfs:subClassOf+ instead of
manual UNION chains. Observed: Trajectory 2 succeeded with '?x rdfs:subClassOf+
up:Protein' while Trajectories 1,3 failed with UNION of direct subClassOf
calls that missed intermediate classes."
```

---

## 6. Success Metrics

### 6.1 Primary Metrics (Stochastic Evaluation)

| Metric | Baseline Target | Success Threshold | Method |
|--------|-----------------|-------------------|--------|
| **Pass@1** | ~40% (estimated) | ≥55% | Random trajectory selection |
| **Best-of-3** | ~50% (estimated) | ≥65% | Optimal trajectory selection |
| **Pass@1 improvement** | - | ≥25% relative over no-memory | Compare conditions |
| **BoN improvement** | - | ≥20% relative over no-memory | Compare conditions |

### 6.2 Learning Metrics

| Metric | Definition | Target |
|--------|------------|--------|
| **Learning slope** | Δ Pass@1 per 10 tasks | Positive |
| **Plateau point** | Task number where improvement slows | After 15-20 tasks |
| **Memory utilization** | % of retrieved memories that appear in successful trajectories | ≥40% |

### 6.3 Extraction Quality Metrics

| Metric | Definition | Target |
|--------|------------|--------|
| **Contrastive yield** | % of mixed-outcome tasks that produce useful memories | ≥60% |
| **Novelty rate** | % of extracted memories not duplicating existing | ≥70% |
| **Human agreement** | % of automated extractions human would approve | ≥75% |

### 6.4 Efficiency Metrics

| Metric | Definition | Target |
|--------|------------|--------|
| **Cost per task (k=1)** | $ for single trajectory | Baseline |
| **Cost per task (k=3)** | $ for parallel scaling | ≤3× baseline (ideally 2.5×) |
| **Cost per success** | Total cost / successful tasks | Decrease over time |

---

## 7. Implementation Priorities

### Existing Infrastructure (Already Implemented)

The codebase already has substantial ReasoningBank infrastructure:

**Production Memory System** (`rlm_runtime/memory/`):
- `SQLiteMemoryBackend`: Full FTS5/BM25 retrieval, stats tracking
- `MemoryItem`: Complete dataclass with provenance, scope, tags
- `judge_trajectory_dspy()`: LLM judgment with Think-Act-Verify-Reflect support
- `extract_memories_dspy()`: Single-trajectory extraction (1-3 items)
- `extract_meta_patterns()`: Cross-trajectory analysis (≥3 trajectories)
- `curriculum_retrieval.py`: L1-L5 level estimation and prioritized retrieval

**Experimental MaTTS Runner** (`experiments/reasoningbank/run/phase1.py`):
- `run_matts_parallel()`: **Already implements k parallel rollouts!**
- `ContrastiveExtractor`: DSPy signature for success vs failure comparison
- `PatternExtractor`: DSPy signature for multi-success patterns
- `run_closed_loop()`: Standard closed-loop learning
- CLI with `--matts` and `--matts-k` flags

### Priority 1: Stochastic Evaluation Harness

**What's missing**: Pass@1, Best-of-N, Pass@k metrics

```python
# Add to experiments/reasoningbank/run/evaluation.py

def evaluate_stochastic(
    tasks: list[dict],
    ont: str,
    mem: MemStore,
    cfg: Cfg,
    k: int = 5,
    temperature: float = 0.7,
) -> dict:
    """Evaluate with stochastic metrics (Pass@1, Best-of-N, Pass@k).

    Uses EXISTING run_matts_parallel infrastructure with metrics computation.
    """
    from experiments.reasoningbank.run.phase1 import run_matts_parallel, judge

    all_results = []
    for task in tasks:
        # Run k trajectories (uses existing infrastructure)
        results = [run(task['query'], ont, cfg, mem) for _ in range(k)]
        judgments = [judge(res, task['query']) for res in results]

        successes = sum(1 for j in judgments if j['success'])

        all_results.append({
            'task_id': task['id'],
            'pass_1': judgments[0]['success'],  # First trajectory
            'best_of_n': any(j['success'] for j in judgments),  # Any success
            'pass_k': successes / k,  # Fraction that succeed
            'successes': successes,
            'k': k,
        })

    # Aggregate metrics
    n = len(all_results)
    return {
        'pass_1': sum(r['pass_1'] for r in all_results) / n,
        'best_of_n': sum(r['best_of_n'] for r in all_results) / n,
        'avg_pass_k': sum(r['pass_k'] for r in all_results) / n,
        'per_task': all_results,
    }
```

### Priority 2: Production Backend Integration

**What's missing**: Connect experimental runner to SQLiteMemoryBackend

```python
# Update experiments/reasoningbank/run/phase1.py to support both backends

def run_closed_loop_sqlite(
    tasks: list[dict],
    ont: str,
    backend: 'SQLiteMemoryBackend',  # Production backend
    cfg: Cfg = None,
    run_id: str = None,
    **kwargs
) -> list[dict]:
    """Closed-loop with production SQLiteMemoryBackend.

    Integrates with existing SQLiteMemoryBackend for:
    - Trajectory storage
    - Judgment storage
    - Memory usage tracking
    - Stats updates (success_count, failure_count)
    """
    from rlm_runtime.memory.backend import MemoryItem
    from rlm_runtime.memory.extraction import (
        judge_trajectory_dspy,
        extract_memories_dspy,
    )

    # Use production extraction instead of experimental signatures
    # ... implementation uses existing backend methods
```

### Priority 3: Temperature Configuration

**What's missing**: Configurable temperature for stochastic generation

```python
# The existing run() function in experiments/reasoningbank/run/rlm.py
# needs temperature parameter propagation

# Current: Uses DSPy default temperature
# Needed: Explicit temperature=0.7 for generation, 0.0 for judge

# Modify run() signature:
def run(
    task: str,
    ont: str,
    cfg: Cfg,
    mem: MemStore,
    *,
    temperature: float = 0.7,  # ADD THIS
    log_path: str = None,
    use_local_interpreter: bool = False,
) -> Result:
    ...
```

### Priority 4: Human Review Interface

**Existing**: `experiments/reasoningbank/tools/memory_reflect.py` already has basic structure

**What's missing**: Integration with MaTTS trajectory sets

```python
# Add to experiments/reasoningbank/tools/memory_reflect.py

def reflect_on_matts_run(
    task: str,
    trajectories: list[Result],
    judgments: list[dict],
    hint: str,
    interactive: bool = True,
) -> list[Item]:
    """Human-guided contrastive extraction from MaTTS run.

    Uses existing ContrastiveExtractor with human hint injection.
    """
    successes = [(t, j) for t, j in zip(trajectories, judgments) if j['success']]
    failures = [(t, j) for t, j in zip(trajectories, judgments) if not j['success']]

    if successes and failures:
        # Present comparison to human with hint
        # Use existing contrastive_extract() with human-enhanced prompt
        ...
```

### Priority 5: Best-of-N Selection by LLM

**What's missing**: Paper uses LLM to select best trajectory, not iteration count

```python
# Add to experiments/reasoningbank/run/phase1.py

class BestOfNSelector(dspy.Signature):
    """Select the best answer from N candidate trajectories."""
    task: str = dspy.InputField()
    candidates: str = dspy.InputField(desc="N answers with their reasoning, separated by ---")

    best_index: int = dspy.OutputField(desc="Index of best answer (1-indexed)")
    reason: str = dspy.OutputField(desc="Why this answer is best")

def select_best_of_n(task: str, results: list[Result], judgments: list[dict]) -> int:
    """Use LLM to select best trajectory (paper methodology).

    Current implementation selects by iteration count.
    Paper uses LLM-as-judge to compare all candidates.
    """
    # Format candidates
    candidates = []
    for i, (res, j) in enumerate(zip(results, judgments), 1):
        status = "SUCCESS" if j['success'] else "FAILURE"
        candidates.append(f"Candidate {i} ({status}):\nAnswer: {res.answer}\nSPARQL: {res.sparql or 'N/A'}")

    selector = dspy.Predict(BestOfNSelector, temperature=0.0)
    result = selector(task=task, candidates="\n---\n".join(candidates))
    return result.best_index - 1  # Convert to 0-indexed
```

---

## 8. Risk Mitigation

### 8.1 Key Risks

| Risk | Likelihood | Impact | Mitigation |
|------|------------|--------|------------|
| **Domain is too deterministic** | Medium | High | Phase 0 calibration before commitment |
| **Parallel scaling too expensive** | Medium | Medium | k=3 not k=5; batch tasks |
| **Contrastive extraction produces noise** | Medium | Medium | Human review for high-value tasks |
| **Memory retrieval hurts** | Low | High | Default k=1; test ablations |
| **Judge unreliable** | Medium | High | Simple binary judge; calibrate first |

### 8.2 Decision Points

After each phase, explicit go/no-go decisions:

**After Phase 0**:
- If variance too low → Consider deterministic approach
- If variance exists → Continue to Phase 1

**After Phase 1**:
- If synergy observed → Continue to Phase 2
- If no synergy → Investigate retrieval, extraction quality

**After Phase 2**:
- If learning curve positive → Productionize
- If plateau early → Analyze what limits growth

### 8.3 Pivot Options

If the stochastic approach doesn't work:

1. **Lower temperature** - Make runs more deterministic, focus on single-trajectory quality
2. **L1/L3 focus** - Our evidence shows L1 schema constraints help 33%; maybe L2 memory isn't needed
3. **Domain-specific methods** - SPARQL may need different patterns than web browsing
4. **Human-in-loop primary** - Use human contrastive extraction as primary, automation as supplement

---

## 9. Timeline (Adaptive)

| Phase | Duration | Key Deliverable | Decision |
|-------|----------|-----------------|----------|
| **Phase 0: Calibration** | 1 week | Variance analysis, go/no-go | Does stochastic approach apply? |
| **Phase 1: Validation** | 1-2 weeks | Synergy measurement | Does MaTTS help? |
| **Phase 2: Learning** | 2-3 weeks | Learning curve, memory bank | Does learning improve over time? |
| **Phase 3: Analysis** | 1 week | Final report, recommendations | What works, what doesn't? |

**Total**: 5-7 weeks (vs 11 weeks in original plan)

**Key Difference**: Each phase has explicit decision points. We don't commit to later phases until earlier phases validate assumptions.

---

## 10. Appendix: Configuration Defaults

### 10.1 Model Configuration

```python
CONFIG = {
    # Generation
    'model': 'claude-sonnet-4-20250514',  # Or Sonnet 3.5
    'temperature_generation': 0.7,  # Stochastic exploration
    'temperature_judge': 0.0,       # Deterministic judgment
    'temperature_extraction': 0.7,  # Creative extraction

    # Scaling
    'k_trajectories': 3,            # Parallel trajectories per task
    'max_iterations': 12,           # Per trajectory

    # Memory
    'k_retrieval': 1,               # Memories to retrieve (paper: 1 is optimal)
    'max_extraction': 3,            # Max memories per task

    # Context
    'l0_enabled': True,             # Ont-Sense
    'l1_enabled': True,             # Schema constraints
    'l2_enabled': True,             # Procedural memory
    'l3_enabled': False,            # Guide summary (optional)
}
```

### 10.2 Evaluation Configuration

```python
EVAL_CONFIG = {
    # Metrics
    'compute_pass_1': True,
    'compute_best_of_n': True,
    'compute_pass_k': True,

    # Statistical
    'confidence_level': 0.95,
    'min_samples': 10,  # Minimum tasks for statistical tests

    # Human review
    'human_review_capacity': 5,  # Tasks per session
    'prioritize_mixed_outcomes': True,
}
```

---

## 11. References

**ReasoningBank Paper**:
- Full citation: "ReasoningBank: Scaling Agent Self-Evolving with Reasoning Memory" (arXiv:2509.25140)
- Key sections: §3.3 MaTTS methodology, §4.3-4.4 Results, §5 Analysis

**Our Prior Evidence**:
- `experiments/reasoningbank/results_uniprot/phase0_uniprot_analysis.md` - Layer ablation
- `experiments/reasoningbank/results_uniprot/l2_memory_analysis.md` - Memory transfer issues
- `experiments/reasoningbank/results/e9a_uniprot_summary.md` - Closed-loop pilot

**LLM Judge Best Practices**:
- Anthropic: https://www.anthropic.com/engineering/demystifying-evals-for-ai-agents
- Key insights: Binary > scoring, chain-of-thought, bias mitigation

---

## Document History

| Version | Date | Changes |
|---------|------|---------|
| 1.0 | Feb 2026 | Original JUDGE_MEMORY_EXPERIMENT_PLAN.md |
| 2.0 | Feb 2026 | Complete rewrite incorporating MaTTS methodology, stochastic evaluation, evidence-based phases |
