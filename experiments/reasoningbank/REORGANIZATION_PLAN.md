# ReasoningBank Directory Reorganization Plan

**Goal**: Transform scattered research artifacts into a structured research-to-production pipeline that enables future systematic extraction and clean reimplementation.

**Status**: Ready for execution
**Est. Time**: 2-3 hours
**Risk**: Low (git preserves history, can revert)

---

## Target Structure

```
experiments/reasoningbank/
│
├── INDEX.md                           # 👈 START HERE - Progressive disclosure entry point
├── README.md                          # High-level overview (updated)
│
├── 00_FOUNDATIONS/                    # 🔒 Core design principles (stable)
│   ├── IMPLEMENTATION_PLAN.md         # Architecture, module specs, LOC budget
│   ├── rlm_notes.md                   # RLM v2 invariants (handles not payloads)
│   └── DESIGN_RATIONALE.md            # Key architectural decisions (new)
│
├── 01_PROTOTYPE/                      # 🧪 Exploratory code (reference only)
│   ├── README.md                      # "This is throwaway prototype code"
│   ├── core/                          # blob.py, graph.py, mem.py, instrument.py
│   ├── packers/                       # l0_sense.py, l1_schema.py, l2_mem.py, l3_guide.py
│   ├── ctx/                           # builder.py
│   ├── metrics/                       # diversity.py, visualize.py
│   ├── tools/                         # sparql.py, endpoint.py, memory_reflect.py
│   └── run/                           # rlm.py, rlm_uniprot.py, phase1_uniprot.py
│
├── 02_EXPERIMENTS/                    # 📊 Timestamped research runs
│   ├── README.md                      # Experiment index with extraction status
│   ├── 2026-02-03_s3_prompt_perturbation/
│   │   ├── EXPERIMENT.md              # Design + status + findings (all in one)
│   │   ├── run_s3.py                  # Runner script
│   │   └── results/                   # Raw JSONL logs
│   ├── 2026-02-01_stochastic_smoke/
│   ├── 2026-01-28_phase1_closed_loop/
│   └── 2026-01-25_layer_ablation_e2/
│
├── 03_FINDINGS/                       # 📝 What we learned (extraction-ready)
│   ├── README.md                      # Summary with extraction priorities
│   ├── validated_patterns/            # ✅ Things that WORKED
│   │   ├── handle_pattern.md          # BlobRef approach (E7b validated)
│   │   ├── two_phase_retrieval.md     # search() then get() (validated)
│   │   ├── l0_sense_card.md           # Ont-Sense packer (E2 validated)
│   │   └── l1_schema_constraints.md   # Anti-patterns + domain/range
│   ├── failed_approaches/             # ❌ Things that DIDN'T work
│   │   ├── tool_mediated_retrieval.md # Delegation doesn't emerge
│   │   └── static_endpoint_preambles.md
│   ├── open_questions/                # 🤔 Still investigating
│   │   ├── memory_consolidation.md    # E10 not tested
│   │   └── layer_interactions.md      # E6 partial results
│   └── metrics/                       # 📊 Quantitative evidence
│       ├── e2_validation.md
│       ├── s3_diversity.md
│       └── iteration_counts.md
│
├── 04_EXTRACTION_GUIDE/               # 🎯 For future productionization
│   ├── README.md                      # How to extract patterns systematically
│   ├── ARCHITECTURE.md                # Proposed production architecture
│   ├── API_DESIGN.md                  # Public API design
│   ├── IMPLEMENTATION_NOTES.md        # Key lessons for reimplementation
│   └── METRICS.md                     # Validation benchmarks
│
├── 05_ARCHIVE/                        # 🗄️ Historical artifacts (reference)
│   ├── bug_reports/                   # FIXES.md, S3_BUG_REPORT.md, etc.
│   ├── status_snapshots/              # Dated STATUS.md copies
│   └── exploratory_tests/             # 30+ test_*.py files
│
├── tests/                             # Organized test suite (current)
│   ├── smoke/                         # test_basic.py, test_s3_quick.py
│   ├── integration/                   # test_full_layer_cake.py, etc.
│   ├── unit/                          # test_e1_minimal.py, etc.
│   └── debug/                         # inspect_rlm_prompt.py, verify_*.py
│
├── analysis/                          # Analysis scripts (kept as-is)
│   ├── analyze_s3_trajectories.py
│   ├── judge_s3_results.py
│   └── compare_l0_approaches.py
│
├── seed/                              # Bootstrap data (unchanged)
│   ├── strategies.json
│   └── constraints/
│
└── results/                           # Gitignored outputs (unchanged)
```

---

## File Mapping

### 00_FOUNDATIONS/ (Stable Design Docs)

| Current Location | New Location | Action |
|------------------|--------------|--------|
| `IMPLEMENTATION_PLAN.md` | `00_FOUNDATIONS/IMPLEMENTATION_PLAN.md` | `git mv` |
| `rlm_notes.md` | `00_FOUNDATIONS/rlm_notes.md` | `git mv` |
| (new) | `00_FOUNDATIONS/DESIGN_RATIONALE.md` | Create |

### 01_PROTOTYPE/ (Exploratory Code)

| Current Location | New Location | Action |
|------------------|--------------|--------|
| (new) | `01_PROTOTYPE/README.md` | Create |
| `core/` | `01_PROTOTYPE/core/` | `git mv` |
| `packers/` | `01_PROTOTYPE/packers/` | `git mv` |
| `ctx/` | `01_PROTOTYPE/ctx/` | `git mv` |
| `metrics/` | `01_PROTOTYPE/metrics/` | `git mv` |
| `tools/` | `01_PROTOTYPE/tools/` | `git mv` |
| `run/` | `01_PROTOTYPE/run/` | `git mv` |

### 02_EXPERIMENTS/ (Timestamped Runs)

| Current Files | New Location | Consolidation |
|---------------|--------------|---------------|
| `run_experiment_s3.py`<br>`S3_EXPERIMENT_STATUS.md`<br>`S3_EXPERIMENT_ANALYSIS.md`<br>`S3_TRAJECTORY_ANALYSIS_REPORT.md`<br>`results/s3_prompt_perturbation/` | `02_EXPERIMENTS/2026-02-03_s3_prompt_perturbation/`<br>└── `EXPERIMENT.md` (consolidated) | Merge 3 md files into one |
| `STOCHASTIC_EVALUATION.md`<br>`STOCHASTICITY_EXPERIMENT_DESIGN.md`<br>`run_stochastic_test.sh`<br>`results/stochastic_logs/` | `02_EXPERIMENTS/2026-02-01_stochastic_smoke/`<br>└── `EXPERIMENT.md` | Consolidate |
| `results/phase1_uniprot_subset/`<br>`results/phase1_uniprot_local/` | `02_EXPERIMENTS/2026-01-28_phase1_closed_loop/` | Organize results |
| (E2 test results) | `02_EXPERIMENTS/2026-01-25_layer_ablation_e2/` | Extract from STATUS.md |

### 03_FINDINGS/ (Extraction-Ready)

| Source | New Location | Content |
|--------|--------------|---------|
| STATUS.md (E2 section)<br>IMPLEMENTATION_PLAN.md (L0 section) | `03_FINDINGS/validated_patterns/l0_sense_card.md` | Extract + format |
| IMPLEMENTATION_PLAN.md (blob section)<br>Status (E7b results) | `03_FINDINGS/validated_patterns/handle_pattern.md` | Extract + format |
| IMPLEMENTATION_PLAN.md (mem section) | `03_FINDINGS/validated_patterns/two_phase_retrieval.md` | Extract + format |
| IMPLEMENTATION_PLAN.md (L1 section) | `03_FINDINGS/validated_patterns/l1_schema_constraints.md` | Extract + format |
| STATUS.md (lessons learned) | `03_FINDINGS/failed_approaches/tool_mediated_retrieval.md` | Extract |
| S3 experiment results | `03_FINDINGS/metrics/s3_diversity.md` | Create from results |
| Status iteration comparisons | `03_FINDINGS/metrics/iteration_counts.md` | Extract tables |
| (analyze open issues) | `03_FINDINGS/open_questions/*.md` | Create from STATUS |

### 04_EXTRACTION_GUIDE/ (Production Roadmap)

| File | Purpose |
|------|---------|
| `README.md` | Step-by-step extraction protocol |
| `ARCHITECTURE.md` | Proposed production package design |
| `API_DESIGN.md` | Public API surface |
| `IMPLEMENTATION_NOTES.md` | DSPy tool signatures, handle pattern, etc. |
| `METRICS.md` | Benchmarks the rewrite must meet/exceed |

### 05_ARCHIVE/ (Historical Reference)

| Current Location | New Location | Category |
|------------------|--------------|----------|
| `FIXES.md` | `05_ARCHIVE/bug_reports/FIXES.md` | Bug reports |
| `S3_BUG_REPORT.md` | `05_ARCHIVE/bug_reports/S3_BUG_REPORT.md` | Bug reports |
| `CACHING_ISSUE_ANALYSIS.md` | `05_ARCHIVE/bug_reports/CACHING_ISSUE_ANALYSIS.md` | Bug reports |
| `OUTPUT_EXTRACTION_FIX.md` | `05_ARCHIVE/bug_reports/OUTPUT_EXTRACTION_FIX.md` | Bug reports |
| `TRAJECTORY_FIX.md` | `05_ARCHIVE/bug_reports/TRAJECTORY_FIX.md` | Bug reports |
| `TRAJECTORY_SANITY_CHECK.md` | `05_ARCHIVE/bug_reports/TRAJECTORY_SANITY_CHECK.md` | Bug reports |
| `STATUS.md` (copy) | `05_ARCHIVE/status_snapshots/2026-02-04_STATUS.md` | Status snapshot |
| `run_status.md` | `05_ARCHIVE/status_snapshots/run_status.md` | Status snapshot |
| `IMPLEMENTATION_SUMMARY.md` | `05_ARCHIVE/implementation_notes/IMPLEMENTATION_SUMMARY.md` | Notes |
| `quick_wins.md` | `05_ARCHIVE/implementation_notes/quick_wins.md` | Notes |
| `LLM_TEST_RESULTS.md` | `05_ARCHIVE/implementation_notes/LLM_TEST_RESULTS.md` | Notes |
| `TEST_RESULTS.md` | `05_ARCHIVE/implementation_notes/TEST_RESULTS.md` | Notes |
| `QUICK_START.md` | `05_ARCHIVE/implementation_notes/QUICK_START.md` | Notes (content extracted to HOW_TO_RUN.md) |
| `REASONINGBANK_IMPLEMENTATION_PLAN.md` | `05_ARCHIVE/implementation_notes/REASONINGBANK_IMPLEMENTATION_PLAN.md` | Old plan (superseded) |
| `TRAJECTORY_DIVERSITY_SUMMARY.md` | `05_ARCHIVE/implementation_notes/TRAJECTORY_DIVERSITY_SUMMARY.md` | Notes (content extracted to findings) |

### tests/ (Organized Test Suite)

| Current Files | New Location | Type |
|---------------|--------------|------|
| `test_basic.py`<br>`test_s3_quick.py` | `tests/smoke/` | Smoke tests |
| `test_full_layer_cake.py`<br>`test_enhanced_l0_all.py`<br>`test_l0_l1_context.py`<br>`test_context_impact.py`<br>`test_perturbation_minimal.py` | `tests/integration/` | Integration tests |
| `test_e1_minimal.py`<br>`test_e5_sense_card.py`<br>`test_l0_comparison.py`<br>`test_current_l1.py`<br>`test_enhanced_l1.py`<br>`test_l1_output.py`<br>`test_l2_mem.py`<br>`test_l3_guide.py`<br>`test_caching_fix.py`<br>`test_llm_query_availability.py`<br>`test_llm_query_fix.py`<br>`test_tool_signature.py`<br>`test_widoco_metadata.py` | `tests/unit/` | Component tests |
| `debug_l2_retrieval.py`<br>`inspect_rlm_prompt.py`<br>`verify_l0_replacement.py`<br>`verify_tools.py`<br>`compare_l0_approaches.py`<br>`compare_l1_versions.py` | `tests/debug/` | Debug scripts |

### analysis/ (Analysis Scripts - Keep)

No moves needed, keep as-is:
- `analyze_s3_trajectories.py`
- `judge_s3_results.py`
- `reprocess_s3_results.py`
- `examine_reasoning_quality.py`

### Task Files (Keep Root)

- `uniprot_pure_tasks.json`
- `uniprot_shacl_tasks.json`
- `uniprot_subset_tasks.json`
- `uniprot_test_tasks.json`
- `test_stochastic_tasks.json`

---

## Execution Plan

### Pre-Flight Checklist

```bash
# 1. Ensure clean working directory
cd /Users/cvardema/dev/git/LA3D/rlm/experiments/reasoningbank
git status  # Should be clean

# 2. Create a safety branch
git checkout -b reorganize-reasoningbank-2026-02-04

# 3. Verify no uncommitted changes
git diff --exit-code
```

### Phase 1: Create Directory Structure

```bash
# Create numbered directories
mkdir -p 00_FOUNDATIONS
mkdir -p 01_PROTOTYPE
mkdir -p 02_EXPERIMENTS
mkdir -p 03_FINDINGS/{validated_patterns,failed_approaches,open_questions,metrics}
mkdir -p 04_EXTRACTION_GUIDE
mkdir -p 05_ARCHIVE/{bug_reports,status_snapshots,implementation_notes,exploratory_tests}
mkdir -p tests/{smoke,integration,unit,debug}

# Create placeholder READMEs
touch 02_EXPERIMENTS/README.md
touch 03_FINDINGS/README.md
touch 04_EXTRACTION_GUIDE/README.md
```

### Phase 2: Move Foundational Documents

```bash
# Move core design docs (preserves git history)
git mv IMPLEMENTATION_PLAN.md 00_FOUNDATIONS/
git mv rlm_notes.md 00_FOUNDATIONS/

# Commit immediately to preserve history
git commit -m "Move foundational design docs to 00_FOUNDATIONS/"
```

### Phase 3: Move Prototype Code

```bash
# Move implementation directories
git mv core 01_PROTOTYPE/
git mv packers 01_PROTOTYPE/
git mv ctx 01_PROTOTYPE/
git mv metrics 01_PROTOTYPE/
git mv tools 01_PROTOTYPE/
git mv run 01_PROTOTYPE/

# Commit
git commit -m "Move prototype code to 01_PROTOTYPE/"
```

### Phase 4: Organize Experiments

```bash
# Create S3 experiment directory
mkdir -p 02_EXPERIMENTS/2026-02-03_s3_prompt_perturbation
git mv run_experiment_s3.py 02_EXPERIMENTS/2026-02-03_s3_prompt_perturbation/
git mv results/s3_prompt_perturbation 02_EXPERIMENTS/2026-02-03_s3_prompt_perturbation/results

# Create stochastic experiment directory
mkdir -p 02_EXPERIMENTS/2026-02-01_stochastic_smoke
git mv run_stochastic_test.sh 02_EXPERIMENTS/2026-02-01_stochastic_smoke/
git mv results/stochastic_logs 02_EXPERIMENTS/2026-02-01_stochastic_smoke/results

# Create phase1 experiment directory
mkdir -p 02_EXPERIMENTS/2026-01-28_phase1_closed_loop
git mv results/phase1_uniprot_subset 02_EXPERIMENTS/2026-01-28_phase1_closed_loop/
git mv results/phase1_uniprot_local 02_EXPERIMENTS/2026-01-28_phase1_closed_loop/

# Commit
git commit -m "Organize experiments into timestamped directories"
```

### Phase 5: Archive Historical Docs

```bash
# Bug reports
git mv FIXES.md 05_ARCHIVE/bug_reports/
git mv S3_BUG_REPORT.md 05_ARCHIVE/bug_reports/
git mv CACHING_ISSUE_ANALYSIS.md 05_ARCHIVE/bug_reports/
git mv OUTPUT_EXTRACTION_FIX.md 05_ARCHIVE/bug_reports/
git mv TRAJECTORY_FIX.md 05_ARCHIVE/bug_reports/
git mv TRAJECTORY_SANITY_CHECK.md 05_ARCHIVE/bug_reports/

# Status snapshots
cp STATUS.md 05_ARCHIVE/status_snapshots/2026-02-04_STATUS.md
git mv run_status.md 05_ARCHIVE/status_snapshots/

# Implementation notes
git mv IMPLEMENTATION_SUMMARY.md 05_ARCHIVE/implementation_notes/
git mv quick_wins.md 05_ARCHIVE/implementation_notes/
git mv LLM_TEST_RESULTS.md 05_ARCHIVE/implementation_notes/
git mv TEST_RESULTS.md 05_ARCHIVE/implementation_notes/
git mv QUICK_START.md 05_ARCHIVE/implementation_notes/
git mv REASONINGBANK_IMPLEMENTATION_PLAN.md 05_ARCHIVE/implementation_notes/
git mv TRAJECTORY_DIVERSITY_SUMMARY.md 05_ARCHIVE/implementation_notes/

# Analysis docs (extract content first, then move)
git mv S3_EXPERIMENT_ANALYSIS.md 05_ARCHIVE/implementation_notes/
git mv S3_TRAJECTORY_ANALYSIS_REPORT.md 05_ARCHIVE/implementation_notes/
git mv S3_EXPERIMENT_STATUS.md 05_ARCHIVE/status_snapshots/
git mv STOCHASTIC_EVALUATION.md 05_ARCHIVE/implementation_notes/
git mv STOCHASTICITY_EXPERIMENT_DESIGN.md 05_ARCHIVE/implementation_notes/

# Commit
git commit -m "Archive historical documentation"
```

### Phase 6: Organize Test Suite

```bash
# Smoke tests
git mv test_basic.py tests/smoke/
git mv test_s3_quick.py tests/smoke/

# Integration tests
git mv test_full_layer_cake.py tests/integration/
git mv test_enhanced_l0_all.py tests/integration/
git mv test_l0_l1_context.py tests/integration/
git mv test_context_impact.py tests/integration/
git mv test_perturbation_minimal.py tests/integration/

# Unit tests
git mv test_e1_minimal.py tests/unit/
git mv test_e5_sense_card.py tests/unit/
git mv test_l0_comparison.py tests/unit/
git mv test_current_l1.py tests/unit/
git mv test_enhanced_l1.py tests/unit/
git mv test_l1_output.py tests/unit/
git mv test_l2_mem.py tests/unit/
git mv test_l3_guide.py tests/unit/
git mv test_caching_fix.py tests/unit/
git mv test_llm_query_availability.py tests/unit/
git mv test_llm_query_fix.py tests/unit/
git mv test_tool_signature.py tests/unit/
git mv test_widoco_metadata.py tests/unit/

# Debug scripts
git mv debug_l2_retrieval.py tests/debug/
git mv inspect_rlm_prompt.py tests/debug/
git mv verify_l0_replacement.py tests/debug/
git mv verify_tools.py tests/debug/
git mv compare_l0_approaches.py tests/debug/
git mv compare_l1_versions.py tests/debug/

# Commit
git commit -m "Organize test suite by type"
```

### Phase 7: Create New Documentation Files

This phase creates new markdown files - done via separate commands after moves complete.

---

## New Files to Create

### 1. INDEX.md (Root Entry Point)

Progressive disclosure starting point (see detailed template in reorganization discussion).

### 2. 01_PROTOTYPE/README.md

```markdown
# Prototype Code (Exploratory, Not Production)

This directory contains **exploratory prototype code** from the research phase.

**Important**: This code is for **reference only**, not production use.

## Purpose

- Rapid experimentation to test hypotheses
- Validate design patterns (handle pattern, layer cake, etc.)
- Discover what works before engineering investment

## Usage

Future implementation should:
- ✅ Extract patterns from `03_FINDINGS/validated_patterns/`
- ✅ Reference this code for implementation details
- ❌ Do NOT refactor or productionize this code directly
- ❌ Do NOT import from this directory in production

## Architecture

See `00_FOUNDATIONS/IMPLEMENTATION_PLAN.md` for design rationale.

Total: ~1300 LOC
```

### 3. 02_EXPERIMENTS/README.md (Experiment Index)

Tracks all experiments with extraction status.

### 4. 03_FINDINGS/README.md

Summarizes findings and extraction priorities.

### 5. 03_FINDINGS/validated_patterns/*.md

One file per validated pattern (see detailed templates in discussion).

### 6. 04_EXTRACTION_GUIDE/README.md

Step-by-step protocol for future Claude to extract and reimplement.

### 7. Consolidated EXPERIMENT.md files

For each experiment in `02_EXPERIMENTS/`, create single EXPERIMENT.md consolidating design + status + findings.

---

## Validation Checklist

After all moves:

- [ ] All original files accounted for (use git status)
- [ ] Git history preserved for all moved files
- [ ] No import errors in prototype code
- [ ] Smoke tests still run: `python tests/smoke/test_basic.py`
- [ ] INDEX.md provides clear entry point
- [ ] All findings have evidence links
- [ ] Extraction guide is actionable
- [ ] Results directories still accessible (absolute paths if needed)

---

## Rollback Plan

If anything goes wrong:

```bash
# Return to original branch
git checkout main

# Delete reorganization branch
git branch -D reorganize-reasoningbank-2026-02-04
```

All original files remain intact on `main` branch.

---

## Timeline Estimate

- Phase 1-6 (moves): 30 minutes
- Phase 7 (create docs): 60-90 minutes
- Phase 8 (validation): 30 minutes

**Total**: 2-3 hours

---

## Success Criteria

1. ✅ Progressive disclosure: Can navigate from INDEX.md → foundations → experiments → findings
2. ✅ Clear extraction path: validated_patterns/ documents have evidence and production notes
3. ✅ Self-documenting experiments: Each has EXPERIMENT.md with design+status+findings
4. ✅ No ambiguity: Single source of truth for status, no duplicate/conflicting docs
5. ✅ Future-ready: 04_EXTRACTION_GUIDE/ provides systematic reimplementation protocol
6. ✅ Git history: All moves preserve history, can trace file origins

---

## Post-Reorganization

After completion:
1. Merge reorganization branch to main
2. Update any external references to old paths
3. Add this structure to CLAUDE.md as the canonical organization
4. Continue research in timestamped experiment directories
5. Update findings as new experiments complete
