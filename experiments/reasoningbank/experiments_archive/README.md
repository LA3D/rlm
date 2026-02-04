# Experiment Index

All research runs organized by timestamp. Each experiment is self-contained with design + status + findings.

## Extraction Priority

| Priority | Pattern | Status | Evidence |
|----------|---------|--------|----------|
| 🔥 High | Handle pattern | ✅ Validated | E7b, E2 |
| 🔥 High | L0 sense card | ✅ Validated | E2 |
| 🔥 High | Two-phase retrieval | ✅ Validated | All experiments |
| 🔴 High | L1 schema constraints | ✅ Validated | E3, UniProt runs |
| 🟡 Medium | Prompt perturbation | 🔄 Promising | S3 minimal test |
| 🟢 Low | Memory consolidation | ⏳ Not tested | E10 not run |

## Experiment Timeline

| ID | Date | Name | Status | Key Finding | Extractable? |
|----|------|------|--------|-------------|--------------|
| **E1** | 2026-01-25 | Baseline (no layers) | ✅ Complete | 0 tool calls → context needed | ℹ️ Negative control |
| **E2** | 2026-01-25 | Layer ablation (L0) | ✅ Complete | Sense card enables tool usage (0→5-7 calls) | ✅ Yes → l0_sense_card.md |
| **E3** | 2026-01-25 | Layer ablation (L1) | ✅ Complete | Schema constraints improve correctness | ✅ Yes → l1_schema.md |
| **E4** | 2026-01-25 | Layer ablation (L3) | 🔄 Partial | Guide summary useful if materialized | 🤔 Needs full test |
| **E5** | 2026-01-26 | Layer ablation (L2) | ✅ Complete | Seeded memories help but extraction critical | 🤔 Open question |
| **E6** | - | Full layer cake | ⏳ Not started | - | ❌ Pending |
| **E7a** | 2026-01-27 | Naive tools (leakage) | ✅ Complete | High prompt leakage baseline | ℹ️ Control |
| **E7b** | 2026-01-27 | Handle-based tools | ✅ Complete | 52% reduction in large_returns | ✅ Yes → handle_pattern.md |
| **E8** | - | Retrieval policy ablation | ⏳ Not started | - | ❌ Pending |
| **E9** | - | Closed-loop (append-only) | ⏳ Not started | - | ❌ Pending |
| **E10** | - | With consolidation | ⏳ Not started | - | ❌ Pending |
| **E11** | - | With forgetting | ⏳ Not started | - | ❌ Pending |
| **E12** | - | MaTTS rollouts | ⏳ Not started | - | ❌ Pending |
| **Phase1** | 2026-01-28 | Closed-loop UniProt | ✅ Complete | 5 memories extracted, API defaults matter more than memory | 🤔 Mixed results |
| **S1** | 2026-02-01 | Stochastic smoke test | ✅ Complete | Task-dependent stochasticity (simple=deterministic) | 🤔 Needs more data |
| **S3** | 2026-02-03 | Prompt perturbation | 🔄 In progress | Prefix +33% diversity (minimal test) | ⏳ Pending full run |

## Experiment Directories

Each directory contains:
- `EXPERIMENT.md` - Design, hypothesis, methodology, results, findings (all in one)
- Runner script(s)
- `results/` - Raw JSONL logs
- (Optional) Analysis scripts

### 2026-02-03_s3_prompt_perturbation/
**Status**: 🔄 In progress
**Goal**: Test prompt perturbation for trajectory diversity
**Finding**: Minimal test shows +33% diversity with prefix, full run pending

### 2026-02-01_stochastic_smoke/
**Status**: ✅ Complete
**Goal**: Validate stochastic evaluation infrastructure
**Finding**: Temperature alone insufficient for simple tasks (deterministic)

### 2026-01-28_phase1_closed_loop/
**Status**: ✅ Complete
**Goal**: Closed-loop learning on UniProt
**Finding**: API defaults had more impact than procedural memory

## Creating New Experiments

### Template Structure

```
02_EXPERIMENTS/YYYY-MM-DD_experiment_name/
├── EXPERIMENT.md          # Single consolidated doc
├── run_experiment.py      # Reproducible runner
├── requirements.txt       # Pinned dependencies (if different)
└── results/               # Raw outputs
```

### EXPERIMENT.md Template

```markdown
# [ID]: [Name]

**Date**: YYYY-MM-DD
**Status**: 🔄 In Progress | ✅ Complete
**Extraction Status**: ✅ Ready | 🔄 Promising | 🤔 Needs More Data | ❌ Not Extractable

## Hypothesis
[Clear testable hypothesis]

## Methodology
- Configuration details
- Task suite
- Metrics
- Validation criteria

## Results

### [Phase 1 Name]
| Metric | Value | Target | Pass? |
|--------|-------|--------|-------|
| ... | ... | ... | ... |

✅/❌ **Finding**: [One-sentence key takeaway]

### [Phase 2 Name]
...

## Extraction Notes

**If validated**:
- What to extract
- How it affects production design
- API implications

**If invalidated**:
- Why it failed
- What we learned
- Alternative approaches

## Code Reference
- Runner: `run_*.py`
- Prototype: `01_PROTOTYPE/path/to/module.py`

## Related
- Builds on: [previous experiment]
- Blocks: [future work]
```

### Naming Convention

`YYYY-MM-DD_short_name`

Examples:
- `2026-02-03_s3_prompt_perturbation`
- `2026-02-01_stochastic_smoke`
- `2026-01-28_phase1_closed_loop`

### Commit Message

```bash
git add 02_EXPERIMENTS/YYYY-MM-DD_name/
git commit -m "Add [ID] experiment: [short description]"
```

## Querying Experiments

```bash
# List all experiments
ls -1 02_EXPERIMENTS/

# Find experiments by status
grep -r "Status.*Complete" 02_EXPERIMENTS/*/EXPERIMENT.md

# Find extractable patterns
grep -r "Extraction Status.*Ready" 02_EXPERIMENTS/*/EXPERIMENT.md
```

---

**Last updated**: 2026-02-04
