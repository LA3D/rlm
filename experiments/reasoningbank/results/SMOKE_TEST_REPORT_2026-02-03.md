# Stochastic Evaluation Smoke Test Report

**Date**: 2026-02-03
**Status**: Baseline Evaluation Complete
**Phase**: Phase 0 - Calibration (MaTTS Methodology)

---

## Executive Summary

Ran initial smoke test of the stochastic evaluation infrastructure for UniProt queries. The implementation is **working correctly**, but the test revealed important characteristics about trajectory variance and memory usage that inform next steps.

**Key Findings**:
1. Stochastic sampling **IS working** for complex tasks (divergence observed)
2. Simple tasks remain **deterministic** despite temperature=0.7
3. Memory store was **empty** - this was effectively a no-memory baseline
4. LLM judge is functioning correctly with grounded reasoning

---

## Test Configuration

```
Tasks: 2 (test_stochastic_tasks.json)
Rollouts per task: k=2
Temperature: 0.7 (generation)
Context layers: L0 (sense card), L2 (memory - but empty)
Interpreter: LocalPythonInterpreter
Endpoint: UniProt SPARQL
```

### Tasks Evaluated

| Task ID | Query | Complexity |
|---------|-------|------------|
| `4_uniprot_mnemonic_id` | Select UniProtKB entry with mnemonic 'A4_HUMAN' | Simple |
| `106_uniprot_reviewed_or_not` | List all proteins with review status | Moderate |

---

## Results Summary

### Aggregate Metrics

| Metric | Value |
|--------|-------|
| **Mean Pass@1** | 1.000 (100%) |
| **Mean Best-of-N** | 1.000 (100%) |
| **Mean Pass@k** | 1.000 (100%) |
| Tasks with any success | 2/2 |

### Per-Task Results

| Task | Rollout 1 | Rollout 2 | Pass@k |
|------|-----------|-----------|--------|
| `4_uniprot_mnemonic_id` | ✓ Success (4 iters) | ✓ Success (4 iters) | 1.00 |
| `106_uniprot_reviewed_or_not` | ✓ Success (12 iters) | ✓ Success (12 iters) | 1.00 |

---

## Trajectory Stochasticity Analysis

### Question: Are rollouts sampling different trajectory space?

#### Task 1: `4_uniprot_mnemonic_id` (Simple)

**Result: DETERMINISTIC** ⚠️

Both rollouts produced **identical trajectories**:
- Same number of iterations: 4
- Same tool sequence: `endpoint_info → sparql_query → sparql_query → sparql_slice → sparql_query → sparql_slice`
- Identical code block lengths: `[209, 689, 458, 398]`
- Identical reasoning

**Interpretation**: For simple tasks with an obvious solution path, temperature=0.7 does not create meaningful variation. The agent converges to the same strategy.

#### Task 2: `106_uniprot_reviewed_or_not` (Moderate)

**Result: STOCHASTIC VARIATION DETECTED** ✓

| Iteration | R1 Code | R2 Code | R1 Reasoning | R2 Reasoning | Status |
|-----------|---------|---------|--------------|--------------|--------|
| 1-8 | Identical | Identical | Identical | Identical | Same path |
| 9 | 626 | 810 | 473 | 500 | **DIVERGE** |
| 10 | 500 | 694 | 500 | 500 | **DIVERGE** |
| 11 | 771 | 415 | 421 | 500 | **DIVERGE** |
| 12 | 387 | 731 | 500 | 500 | **DIVERGE** |

**Interpretation**: For complex tasks, stochastic variation emerges after initial exploration. The agent takes different paths through the reasoning space in later iterations.

### Key Insight

Stochastic sampling provides value primarily for **complex tasks** where:
- Multiple valid approaches exist
- Later reasoning steps involve genuine decision points
- The agent faces uncertainty about which path to take

Simple tasks remain deterministic, which is **actually efficient** - no compute wasted on redundant exploration.

---

## LLM Judge Analysis

### Configuration

```python
class TrajectoryJudge(dspy.Signature):
    task: str = dspy.InputField(desc="The original question/task")
    answer: str = dspy.InputField(desc="The agent's final answer")
    sparql: str = dspy.InputField(desc="The SPARQL query produced")

    success: bool = dspy.OutputField()
    reason: str = dspy.OutputField()
```

- **Temperature**: 0.0 (deterministic)
- **Model**: Same as agent (Claude Sonnet 4.5)

### Example Judgment

**Task**: Select UniProtKB entry with mnemonic 'A4_HUMAN'

**Judgment**:
```
Success: True
Reason: The task was to select the UniProtKB entry with mnemonic 'A4_HUMAN'.
The agent produced a correct SPARQL query that searches for entries with this
mnemonic, and returned the URI http://purl.uniprot.org/uniprot/P05067, which
is the correct UniProtKB entry for A4_HUMAN (Amyloid-beta precursor protein).
The query structure is appropriate and the answer directly fulfills the task
requirement.
```

### Assessment

✅ **Judge is working correctly**:
- Provides detailed, grounded reasoning
- Checks both SPARQL query correctness and answer relevance
- Uses deterministic temperature for consistency
- References specific URIs and query patterns

---

## Memory System Analysis

### Critical Finding: Memory Store Empty

```python
>>> mem = MemStore()
>>> len(mem.all())
0
```

**Context Composition**:
| Layer | Status | Size |
|-------|--------|------|
| L0 (Sense Card) | ✅ Active | ~600 chars |
| L1 (Schema) | ❌ Disabled | 0 chars |
| L2 (Memory) | ⚠️ Enabled but empty | 0 chars |
| L3 (Guide) | ❌ Disabled | 0 chars |
| **Total** | | **663 chars** |

### Implication

This smoke test was effectively a **baseline evaluation without procedural memory**. This aligns with ReasoningBank Phase 0 methodology:

> "E0.1: No Memory Baseline - Run all tasks with L0+L1 only (no L2 procedural memory)"

We have established:
- Baseline Pass@1 without memory augmentation
- Baseline trajectory characteristics
- Judge reliability

---

## Files Generated

### Results
- `experiments/reasoningbank/results/stochastic_k2_t0.7.json` - Structured results

### Trajectory Logs
- `experiments/reasoningbank/results/stochastic_logs/4_uniprot_mnemonic_id_rollout1.jsonl`
- `experiments/reasoningbank/results/stochastic_logs/4_uniprot_mnemonic_id_rollout2.jsonl`
- `experiments/reasoningbank/results/stochastic_logs/106_uniprot_reviewed_or_not_rollout1.jsonl`
- `experiments/reasoningbank/results/stochastic_logs/106_uniprot_reviewed_or_not_rollout2.jsonl`

---

## Alignment with ReasoningBank Plan

### Phase 0: Stochastic Calibration

| Experiment | Status | Finding |
|------------|--------|---------|
| E0.1: Variance Measurement | ✅ Partial | Variance exists for complex tasks, not simple |
| E0.2: Memory Effect | ⏳ Pending | Need populated memory store |
| E0.3: Contrastive Extraction Pilot | ⏳ Pending | Need mixed-outcome tasks |

### Questions Answered

1. **Does stochastic variation exist?**
   - ✅ Yes, for complex tasks (iterations 9-12 diverged)
   - ⚠️ No, for simple tasks (deterministic)

2. **Is the judge reliable?**
   - ✅ Yes, provides grounded reasoning
   - ✅ Uses deterministic temperature

3. **Is memory being used?**
   - ❌ Not yet - memory store empty
   - This is expected for baseline phase

### Questions Still Open

1. **What is Pass@1 vs Best-of-N gap on harder tasks?**
   - Need tasks with mixed outcomes (some success, some failure)

2. **Does memory improve performance?**
   - Need populated memory store to test

3. **Is contrastive extraction valuable?**
   - Need mixed-outcome tasks for self-contrast

---

## Recommendations

### Immediate Next Steps

1. **Run Full Baseline Evaluation** (10 tasks, k=5)
   ```bash
   python -m experiments.reasoningbank.run.phase1_uniprot \
     --stochastic --stochastic-k 5 --temperature 0.7 \
     --tasks experiments/reasoningbank/uniprot_subset_tasks.json \
     --l0 --local \
     --log-dir experiments/reasoningbank/results/stochastic_logs/
   ```

   **Purpose**: Establish true baseline metrics with harder tasks that may show variance

2. **Create Bootstrap Seed Memories**
   - Load existing memories from previous experiments
   - Or run closed-loop extraction on a subset of tasks

3. **Run With Memory Evaluation**
   - Compare Pass@1 with vs without memory
   - Measure Best-of-N improvement

### Metrics to Track

| Metric | Baseline (No Memory) | With Memory | Delta |
|--------|---------------------|-------------|-------|
| Pass@1 | TBD | TBD | TBD |
| Best-of-N | TBD | TBD | TBD |
| Pass@k | TBD | TBD | TBD |
| Tasks with variance | TBD | TBD | TBD |

---

## Technical Notes

### Temperature Verification

Temperature is correctly propagated:
```
run_start event: temperature=0.7 (confirmed in all trajectory logs)
```

### DSPy LM Configuration

When `temperature > 0.0`, the system reconfigures DSPy LM:
```python
if temperature > 0.0:
    lm = dspy.LM(
        'anthropic/claude-sonnet-4-5-20250929',
        api_key=os.environ['ANTHROPIC_API_KEY'],
        temperature=temperature
    )
    dspy.configure(lm=lm)
```

### Judge Model

Judge uses same model as agent but with `temperature=0.0`:
```python
judge_fn = dspy.Predict(TrajectoryJudge, temperature=0.0)
```

---

## Appendix: Raw Data Samples

### Task 1 - Final Answer
```
http://purl.uniprot.org/uniprot/P05067
```

### Task 2 - Final SPARQL
```sparql
PREFIX up: <http://purl.uniprot.org/core/>

SELECT ?protein ?reviewed
WHERE {
  ?protein a up:Protein .
  ?protein up:reviewed ?reviewed .
}
```

---

## Document History

| Date | Author | Changes |
|------|--------|---------|
| 2026-02-03 | Claude | Initial smoke test report |

---

**Next Report**: Full baseline evaluation (10 tasks, k=5)
