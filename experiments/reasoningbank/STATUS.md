# Current Status

**Last updated**: 2026-02-04
**Branch**: reorganize-reasoningbank-2026-02-04 (ready to merge)

---

## 🔄 Active Work

### S3 Prompt Perturbation Experiment
- **Status**: Minimal test ✅ complete, full run ⏳ pending
- **Last session**: 2026-02-03
- **Finding**: Prefix perturbation increases diversity +33% without degrading performance
- **Next**: Run full experiment (5 tasks × 5 rollouts × 4 strategies = 100 runs, ~2-3 hours)
- **Location**: `experiments_archive/2026-02-03_s3_prompt_perturbation/`

---

## 📊 Experiment Status

### Completed Experiments

| ID | Name | Status | Key Finding | Extraction |
|----|------|--------|-------------|------------|
| **E2** | L0 sense card | ✅ Validated | Enables tool usage (0→5-7 calls) | ✅ `findings/validated_patterns/l0_sense_card.md` |
| **E7b** | Handle pattern | ✅ Validated | 52% leakage reduction | ✅ `findings/validated_patterns/handle_pattern.md` |
| **Phase1** | Closed-loop UniProt | ✅ Complete | 5 memories extracted, API defaults matter | 🤔 Mixed results |
| **S1** | Stochastic smoke | ✅ Complete | Task-dependent stochasticity | 📊 Data collected |
| **S3-mini** | Prompt perturbation (minimal) | ✅ Complete | Prefix +33% diversity | ⏳ Pending full validation |

### In Progress

| ID | Name | Status | Next Action |
|----|------|--------|-------------|
| **S3** | Prompt perturbation (full) | 🔄 In progress | Run 100 rollouts |

### Planned

| ID | Name | Priority | Depends On |
|----|------|----------|------------|
| **E6** | Full layer cake | 🔥 High | E2, E3 complete |
| **E10** | Memory consolidation | 🟡 Medium | E9 complete |
| **E11** | Memory forgetting | 🟡 Medium | E10 complete |
| **E12** | MaTTS rollouts | 🟢 Low | S3 complete |

---

## ✅ What's Working

### Validated Patterns (Production-Ready)

1. **Handle Pattern** (`findings/validated_patterns/handle_pattern.md`)
   - 52% reduction in prompt leakage
   - Core abstraction for RLM

2. **L0 Sense Card** (`findings/validated_patterns/l0_sense_card.md`)
   - Enables tool discovery (0→5-7 tool calls)
   - 100% convergence on test tasks

3. **Two-Phase Retrieval**
   - Prevents unbounded context growth
   - Validated across all experiments

4. **L1 Schema Constraints**
   - Improves correctness
   - Anti-patterns prevent common mistakes

### Infrastructure

- ✅ Prototype code (~1300 LOC) in `prototype/`
- ✅ All tests passing (smoke, unit, integration)
- ✅ Task definitions in `tasks/` (5 JSON files, 750+ tasks)
- ✅ Trajectory diversity metrics validated
- ✅ Stochastic evaluation framework working
- ✅ LM-as-judge evaluation working

---

## 📁 Directory Structure

```
experiments/reasoningbank/
├── INDEX.md                 # 👈 START HERE
├── STATUS.md                # This file
├── WORK_LOG.md              # Session-by-session journal
├── README.md                # Experiment design
│
├── foundations/             # Core design docs
│   ├── IMPLEMENTATION_PLAN.md
│   └── rlm_notes.md
│
├── prototype/               # Working code (~1300 LOC)
│   ├── core/               # BlobRef, MemStore
│   ├── packers/            # L0-L3 packers
│   ├── ctx/                # Context builder
│   ├── metrics/            # Diversity metrics
│   ├── tools/              # SPARQL, endpoint tools
│   └── run/                # Experiment runners
│
├── experiments_archive/     # Timestamped runs
│   ├── 2026-02-03_s3_prompt_perturbation/
│   ├── 2026-02-01_stochastic_smoke/
│   └── 2026-01-28_phase1_closed_loop/
│
├── findings/               # Extraction-ready patterns
│   ├── validated_patterns/
│   ├── failed_approaches/
│   └── metrics/
│
├── tests/                  # All passing ✅
│   ├── smoke/
│   ├── integration/
│   ├── unit/
│   └── debug/
│
└── tasks/                  # Task definitions
```

---

## 🎯 Next Steps (Priority Order)

### Priority 1: Complete S3 Full Run
**Why**: Minimal test succeeded, need full validation before extracting pattern
**How**:
```bash
source ~/uvws/.venv/bin/activate
python experiments_archive/2026-02-03_s3_prompt_perturbation/run_experiment_s3.py \
  --full --output experiments_archive/2026-02-03_s3_prompt_perturbation/results/
```
**Expected**: 2-3 hours, 100 runs
**Success criteria**: Diversity ≥1.5x baseline, Pass@1 within 10%

### Priority 2: Extract S3 Results
**Why**: If validated, becomes production pattern
**How**:
1. Analyze results with `analysis/analyze_s3_trajectories.py`
2. If validated → create `findings/validated_patterns/prompt_perturbation.md`
3. Update `experiments_archive/2026-02-03_s3_prompt_perturbation/EXPERIMENT.md`

### Priority 3: Run E6 (Full Layer Cake)
**Why**: E1-E5 validated individually, need to test synergy
**How**:
```bash
python prototype/run/phase0_uniprot.py \
  --l0 --l1 --l2 --l3 \
  --tasks tasks/uniprot_subset_tasks.json \
  --output experiments_archive/2026-02-XX_e6_full_layer_cake/
```
**Success criteria**: Performance ≥ max(E2,E3,E4,E5), cost tradeoff acceptable

### Priority 4: Memory Consolidation (E10)
**Why**: Prevent memory bloat, improve quality
**Blocked by**: E9 (closed-loop extraction) needs work
**How**: Implement merge/supersede logic in `prototype/core/mem.py`

---

## 🚫 Known Issues

1. **STATUS.md paths outdated** → Fixed 2026-02-04 (this update)
2. **E10 consolidation not implemented** → Pending
3. **E11 forgetting not implemented** → Pending
4. **E12 MaTTS not implemented** → Pending (after S3 validates)

---

## 📝 Recent Changes (Last 7 Days)

- **2026-02-04**: Directory reorganization, import fixes, documentation overhaul
- **2026-02-03**: S3 minimal test ✅, bug fixes, LM-as-judge working
- **2026-02-01**: Stochastic evaluation infrastructure, trajectory diversity metrics
- **2026-01-28**: Phase 1 closed-loop UniProt experiments

See `WORK_LOG.md` for detailed session notes.

---

## 🔗 Quick Links

- **Current work**: See "Active Work" section above
- **Next session start**: See "Priority 1" in Next Steps
- **Design docs**: `foundations/IMPLEMENTATION_PLAN.md`
- **Validated patterns**: `findings/validated_patterns/`
- **Session history**: `WORK_LOG.md`
