# Experiment Log

This file is a human-readable log of all experiments, complementing the machine-readable `experiments/registry.yaml`.

---

## E001: Baseline Before Reasoning Fields

**Date**: 2026-01-20 to 2026-01-22 (pre-21:52 UTC)
**Git Commit**: `03d298b4`
**Status**: ✅ Completed

### Hypothesis
Establish baseline performance metrics before implementing Think-Act-Verify-Reflect reasoning cycles.

### Configuration
- DSPy RLM with standard QueryConstructionSig (no reasoning fields)
- No memory enabled
- Remote SPARQL execution to UniProt endpoint

### Tasks
- `uniprot/taxonomy/uniprot_bacteria_taxa_001` (15 runs, 29 trials)
- `uniprot/taxonomy/uniprot_ecoli_k12_sequences_001` (6 runs, 6 trials)

### Results
| Task | Pass Rate | Avg Iterations | Key Findings |
|------|-----------|----------------|--------------|
| bacteria_taxa | 58.6% (17/29) | 8.9 | Moderate success, but inconsistent |
| ecoli_k12 | **0.0% (0/6)** | 11.0 | **Evidence format issues: storing `sequence_length` instead of actual sequences** |

### Key Findings
1. **Evidence format problem**: Agent stores metadata (sequence_length) instead of actual data (amino acid sequences)
2. **E. coli K12 failure mode**: Task requires actual sequences, but agent's evidence dict has wrong fields
3. **No explicit verification**: Agent doesn't check that evidence has required fields before SUBMIT

### Next Steps
→ **E002**: Implement Rung 1 of Think-Act-Verify-Reflect plan to address evidence format issues

---

## E002: Rung 1 - Think-Act-Verify-Reflect

**Date**: 2026-01-22 (after 21:52 UTC)
**Git Commit**: `9efd8204`
**Status**: 🚧 In Progress (needs more trials with full implementation)

### Hypothesis
Adding explicit thinking/verification/reflection output fields to QueryConstructionSig will:
1. Improve evidence quality (actual data vs metadata)
2. Increase pass rate on E. coli K12 task
3. Minimal overhead (iteration count should not increase significantly)

### Changes from E001
**Code changes:**
- Added `thinking`, `verification`, `reflection` fields to QueryConstructionSig
- Added THINK→ACT→VERIFY→REFLECT guidance to context prompts
- Enhanced evidence description: "actual data (sequences, labels) NOT just counts or lengths"

**Prompt changes:**
- Explicit verification step: "Check results match expectations"
- Reflection before SUBMIT: "Does evidence include actual data (not just metadata)?"
- Example guidance: "'Results have sequence field with amino acids ✓' (NOT just sequence_length!)"

### Tasks
- `uniprot/taxonomy/uniprot_ecoli_k12_sequences_001` (3 runs, 5 trials)

### Preliminary Results
| Task | Baseline (E001) | Rung 1 (E002) | Improvement |
|------|-----------------|---------------|-------------|
| ecoli_k12 pass rate | 0.0% (0/6) | **60.0% (3/5)** | **+60.0%** ✅ |
| ecoli_k12 iterations | 11.0 | 11.9 | +0.9 (minimal overhead) |

**Evidence quality check (latest run with thinking fields):**
```json
{
  "metadata_based": false,  ✅
  "sample_results": [{
    "sequence_preview": "MNKVGMFYTYWSTEWMVDFP...",  // Actual amino acids!
    "sequence_length": 298
  }]
}
```

**Reasoning fields populated:**
- **Thinking**: "Explored schema → identified K12 taxa → constructed query..."
- **Verification**: "Verified 16 K12-related taxa, query structure correct, samples valid..."
- **Reflection**: "Query successfully addresses request by including main strain + 15 substrains..."

### Key Findings
1. **Evidence format fixed**: Agent now includes actual sequences, not just sequence_length
2. **Dramatic improvement**: E. coli K12 went from 0% → 60% pass rate
3. **Minimal overhead**: 0.9 iteration increase is acceptable
4. **Reasoning fields work**: Agent populates thinking/verification/reflection with meaningful content

### Limitations
- Only 1 of 3 post-commit runs has full implementation (task_runner.py changes uncommitted)
- Need 10+ trials with full implementation for statistical significance
- Haven't re-tested bacteria_taxa with Rung 1 yet

### Next Steps
1. **Commit task_runner.py changes** to capture reasoning fields
2. **Run 10 trials** on both tasks with full implementation
3. **Statistical comparison** with E001 baseline
4. **Decision point**: Is Rung 1 sufficient, or proceed to Rung 2 (exploration/planning phases)?

---

## Planned Experiments

### E003: Rung 2 - Exploration/Planning Phases
**Status**: 📋 Planned
**Hypothesis**: Separating exploration (discover schema) from planning (decide strategy) from execution will improve pass rate further and reduce iteration count.

**Changes**:
- Add `exploration_summary` and `plan` fields to signature
- Phase-based context guidance (iterations 1-3: explore, 4: plan, 5+: execute)

**Decision criteria**: Only proceed if E002 analysis shows need for more structure.

---

### E004: Affordance Ablation
**Status**: 📋 Planned
**Hypothesis**: Domain/range info and hierarchy depth specifically help with JOIN construction; materialization hints help with closure operator selection.

**Cohorts**:
- Minimal (basic_stats only)
- Structural (+ domain_range, hierarchy)
- Semantic (+ materialization_hints, property_characteristics)
- Navigational (+ labeling_predicates, uri_patterns)
- Full (all affordances)

**Metrics**:
- Primary: pass_rate
- Secondary: affordance_utilization_rate, join_correctness, closure_operator_correctness

**Maps to**: RQ5 (representation utility) from trajectory_v3.md

---

### E005: Memory Learning Curves
**Status**: 📋 Planned
**Hypothesis**: ReasoningBank procedural memory reduces iteration count over sequential runs as the agent learns strategies.

**Design**:
- 20 sequential tasks (not random order)
- Cohorts: memory off vs memory on
- Measure: iteration_count vs cumulative_tasks (should trend down with memory)

**Maps to**: RQ4 (learning dynamics) from trajectory_v3.md

---

### E006: Reasoning Boundaries (L0-L7)
**Status**: 📋 Planned
**Hypothesis**: Pass rate will show capability cliff at L5-L6, informing which new RLM tools are needed.

**Design**:
- Create tasks at each reasoning level (L0 direct → L7 explanation)
- Measure pass rate by level
- Identify: where does LLM capability end?

**Maps to**: RQ6 (reasoning boundaries) from trajectory_v3.md

---

## Experiment Naming Convention

- **EXXX**: Unique experiment ID (sequential)
- **Descriptive name**: Short phrase describing what's being tested
- **Directory**: `experiments/EXXX_name/`

Examples:
- `E001_baseline_before_reasoning`
- `E002_rung1_think_act_verify_reflect`
- `E003_rung2_exploration_planning`
- `E004_affordance_ablation`

---

## Quick Reference

### Current Best Practice (as of 2026-01-23)
- **Agentic pattern**: Rung 1 Think-Act-Verify-Reflect
- **Git commit**: `9efd8204`
- **Pass rate**: 60% on E. coli K12, TBD on bacteria_taxa
- **Evidence quality**: ✅ Fixed (actual data, not metadata)

### Next Experiments to Run
1. **E002 completion**: 10 trials on both tasks
2. **E004 affordance ablation**: Test which sense card features help
3. **E005 memory learning curves**: Validate ReasoningBank value

### Research Questions Status
| RQ | Status | Experiments |
|----|--------|-------------|
| RQ1 (Affordance discovery) | 🔄 Planned | E004 |
| RQ4 (Learning dynamics) | 🔄 Planned | E005 |
| RQ5 (Representation utility) | 🔄 Planned | E004 |
| RQ6 (Reasoning boundaries) | 🔄 Planned | E006 |

---

## Change Log

- **2026-01-23**: Created experiment log, documented E001 and E002
- **2026-01-22**: E002 preliminary results show 60% pass rate on E. coli K12
- **2026-01-22**: E001 baseline measurements complete (58.6% bacteria_taxa, 0% ecoli_k12)
