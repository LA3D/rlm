# Research Trajectory: ReasoningBank Experiments

**Purpose**: Document the research journey based on git history and experimental results.

**Last updated**: 2026-02-04

---

## Overview

This document traces the evolution of the ReasoningBank experiments from initial design through current stochastic evaluation experiments. It reconstructs the research trajectory from git commits, experimental results, and analysis files.

---

## Timeline: Key Milestones

### Phase 0: Foundation (Jan 2026)

**Commit**: `4552c0b` - Add ReasoningBank implementation plan with MaTTS methodology
- Established MaTTS (Memory-aware Test-Time Scaling) methodology
- Defined 5-layer memory architecture (L0-L4)
- Designed experiment progression: baseline → ablation → integration

### Phase 1: Layer Ablation Experiments (Jan 25-30, 2026)

**Core Infrastructure Built**:
- `ca0dcd7` - Upgrade to Claude Sonnet 4.5 and Haiku 4.5
- `fade927` - Align UniProt runner with PROV fixes, add --log-dir
- `1365ecf` - Fix trajectory capture and tool calling robustness
- `23651a0` - Enhance L1 schema: property types, SPARQL hints, NamedIndividuals
- `7c2059d` - Fix SPARQL prefix handling: always prepend defaults

**Experiments Run** (results in `results_uniprot/`):
- **E1 (Baseline)**: No memory layers → 0 tool calls (agent passive)
- **E2 (L0 Sense Card)**: Ontology summary → 5-7 tool calls, 100% convergence
- **E3 (L1 Schema)**: Schema constraints → improved correctness
- **E4 (L3 Guide)**: Summary-based guide → partial improvement
- **E5 (L2 Memory)**: Seeded memories → helpful but extraction-dependent
- **E6 (Full Stack)**: All layers → testing layer synergy

**Key Finding**: L0 sense card is critical enabler (0→5-7 tool calls)

**Evidence**: `results_uniprot/phase0_uniprot_analysis.md`, trajectory logs E1-E6

### Phase 2: Handle Pattern Validation (Jan 27, 2026)

**Commits**:
- `a86c787` - Increase sparql_peek and sparql_slice default limits
- `dbf2496` - Add memory reflection tools and update implementation plan

**Experiments** (E7a, E7b):
- **E7a (Naive tools)**: Direct graph returns → high prompt leakage baseline
- **E7b (Handle-based tools)**: BlobRef pattern → 52% reduction in large_returns

**Key Finding**: Handle pattern (BlobRef) prevents prompt leakage

**Evidence**: `findings/validated_patterns/handle_pattern.md`

### Phase 3: Closed-Loop Learning (Jan 28, 2026)

**Commit**: `5c42aca` - Add phase 1 closed-loop test results with local interpreter
- `7e68429` - Add LocalPythonInterpreter to bypass Deno sandbox corruption

**Experiment**: Phase1 Closed-Loop UniProt (10 tasks)
- Ran closed-loop extraction: query → judge → extract → store
- Extracted 9 strategies from successful runs
- Used LocalPythonInterpreter to fix Deno sandbox issues

**Location**: `experiments_archive/2026-01-28_phase1_closed_loop/`

**Trajectories**:
```
1_select_all_taxa_used_in_uniprot.jsonl
2_bacteria_taxa_and_their_scientific_name.jsonl
4_uniprot_mnemonic_id.jsonl
12_entries_integrated_on_date.jsonl
30_merged_loci.jsonl
33_longest_variant_comment.jsonl
85_taxonomy_host.jsonl
104_uniprot_recomended_protein_full_name.jsonl
106_uniprot_reviewed_or_not.jsonl
121_proteins_and_diseases_linked.jsonl
```

**Critical Finding**: Judge accuracy only 44% when validated against ground truth
- 5/9 false positives (missing clauses, non-canonical patterns)
- 1 false negative (terminology misunderstanding)
- Memory corruption risk: extracting incorrect patterns

**Evidence**: `results/phase1_subset_analysis.md` (557 lines, detailed failure analysis)

**Recommendation**: Fix judge validation before scaling

### Phase 4: Stochastic Evaluation Infrastructure (Feb 1-3, 2026)

**Commit**: `aa90687` - Add stochastic evaluation for UniProt queries with Pass@k metrics
- Implements MaTTS evaluation framework
- Add temperature parameter to run_uniprot()
- Add run_stochastic_uniprot() for k rollouts per task
- Add compute_stochastic_metrics() for Pass@1, Best-of-N, Pass@k
- Comprehensive documentation (STOCHASTIC_EVALUATION.md)

**Commit**: `0d8563e` - Add smoke test report for stochastic evaluation

**Experiment S1**: Stochastic Smoke Test (Feb 1, 2026)
- **Configuration**: 2 tasks, k=2 rollouts, temperature=0.7
- **Tasks**: `4_uniprot_mnemonic_id` (simple), `106_uniprot_reviewed_or_not` (moderate)
- **Memory**: Empty (baseline without procedural memory)

**Location**: `experiments_archive/2026-02-01_stochastic_smoke/`

**Trajectories**:
```
results/106_uniprot_reviewed_or_not_rollout1.jsonl
results/106_uniprot_reviewed_or_not_rollout2.jsonl
results/4_uniprot_mnemonic_id_rollout1.jsonl
results/4_uniprot_mnemonic_id_rollout2.jsonl
```

**Key Findings**:
1. ✅ Stochastic variation exists for complex tasks (iterations 9-12 diverged)
2. ⚠️ Simple tasks remain deterministic despite temperature=0.7
3. ⚠️ Memory store empty → this is baseline evaluation
4. ✅ LLM judge working with grounded reasoning

**Metrics**:
- Pass@1: 100%
- Best-of-N: 100%
- Pass@k: 100%
- Task-dependent stochasticity confirmed

**Evidence**: `results/SMOKE_TEST_REPORT_2026-02-03.md`

### Phase 5: Trajectory Diversity (Feb 3, 2026)

**Commit**: `ebf213d` - Add S3 prompt perturbation experiment and trajectory diversity metrics
- Implements 4 perturbation strategies (none, prefix, rephrase, thinking)
- Vendi Score for trajectory diversity
- Jaccard similarity for sampling efficiency
- Comprehensive diversity metrics suite

**Commit**: `98f1d17` - Fix 3 critical S3 experiment bugs and add LM-as-judge evaluation
- Fixed trajectory logging bug (missing iteration capture)
- Fixed judging bug (JSONL format issues)
- Fixed diversity bug (normalize by unique count)
- Added LM-as-judge for quality assessment

**Experiment S3**: Prompt Perturbation (Minimal Test - Feb 3, 2026)
- **Configuration**: 1 task, k=5 rollouts, 4 strategies
- **Task**: `1_select_all_taxa_used_in_uniprot`
- **Strategies**: none (baseline), prefix, rephrase, thinking
- **Memory**: With L2 procedural memory (if available)

**Location**: `experiments_archive/2026-02-03_s3_prompt_perturbation/`

**Trajectories** (100 files total for minimal test):
```
results/logs/{task_name}/{strategy}/{task_name}_rollout{1-5}.jsonl

Example structure:
results/logs/1_select_all_taxa_used_in_uniprot/
├── none/     (baseline: 5 rollouts)
├── prefix/   (prefix perturbation: 5 rollouts)
├── rephrase/ (rephrase perturbation: 5 rollouts)
└── thinking/ (thinking perturbation: 5 rollouts)
```

**Key Finding**: Prefix perturbation increases diversity +33% without degrading performance

**Metrics** (Minimal Test):
| Strategy | Pass@1 | Trajectory Vendi | Sampling Efficiency |
|----------|--------|-----------------|-------------------|
| Baseline | 100% | 1.00 | 50% |
| Prefix | 100% | 1.33 | 66.6% |
| Change | 0% | **+33%** | +16.6pp |

**Full S3 Pending**: 5 tasks × 5 rollouts × 4 strategies = 100 runs (~2-3 hours)

**Tasks for Full Run**:
- `1_select_all_taxa_used_in_uniprot`
- `2_bacteria_taxa_and_their_scientific_name`
- `4_uniprot_mnemonic_id`
- `30_merged_loci`
- `121_proteins_and_diseases_linked`

**Evidence**: Minimal test trajectories in `experiments_archive/2026-02-03_s3_prompt_perturbation/results/logs/`

### Phase 6: Directory Reorganization (Feb 4, 2026)

**Commits**:
- `524672d` - Move foundational design docs to 00_FOUNDATIONS/
- `9281eb4` - Move prototype code to 01_PROTOTYPE/
- `04adda4` - Organize experiments into timestamped directories
- `5b0a981` - Archive historical documentation
- `6acbae7` - Organize test suite by type
- `3f0641e` - Add comprehensive documentation for research-to-production workflow
- `c057176` - Organize task definition files into tasks/ directory
- `f60bae1` - Move analysis scripts to analysis/ directory
- `696b0c1` - Remove number prefixes from directories for Python import compatibility
- `040ac16` - Update all test imports to use new prototype/ path
- `95cd915` - Fix internal imports within prototype/ modules
- `90aeacb` - Fix imports in analysis scripts

**Changes**:
- Created research-to-production pipeline structure
- Fixed 132 imports across 47 files
- Organized 27 test files into smoke/unit/integration/debug
- Created progressive disclosure documentation (INDEX.md, GETTING_STARTED.md)
- Established session handoff system (WORK_LOG.md, STATUS.md)

**Evidence**: See `WORK_LOG.md` for detailed session notes

---

## Current Experimental Data Structure

### UniProt Stochastic Trajectories

#### Location 1: `results/` (Early Experiments)

**Layer Ablation Results** (E1-E6):
```
results/
├── E1_entity_lookup_trajectory.jsonl
├── E1_hierarchy_trajectory.jsonl
├── E1_property_find_trajectory.jsonl
├── E2_entity_lookup_trajectory.jsonl
├── E2_hierarchy_trajectory.jsonl
├── E2_property_find_trajectory.jsonl
├── E3_entity_lookup_trajectory.jsonl
├── E3_hierarchy_trajectory.jsonl
├── E3_property_find_trajectory.jsonl
├── E4_entity_lookup_trajectory.jsonl
├── E4_hierarchy_trajectory.jsonl
├── E4_property_find_trajectory.jsonl
├── E5_entity_lookup_trajectory.jsonl
├── E5_hierarchy_trajectory.jsonl
├── E5_property_find_trajectory.jsonl
├── E6_entity_lookup_trajectory.jsonl
├── E6_hierarchy_trajectory.jsonl
└── E6_property_find_trajectory.jsonl
```

**Analysis Files**:
```
results/
├── phase0_analysis.md             # E1-E6 analysis
├── phase1_subset_analysis.md      # Phase 1 closed-loop (557 lines)
├── uniprot_phase1_analysis.md     # UniProt-specific analysis
├── e9a_summary.md                 # E9 experiment summary
├── e9a_uniprot_summary.md         # E9 UniProt analysis
└── SMOKE_TEST_REPORT_2026-02-03.md # S1 stochastic smoke test
```

#### Location 2: `results_uniprot/` (Phase 0 UniProt)

**Phase 0 Results** (E1-E6 with UniProt endpoint):
```
results_uniprot/
├── E1_annotation_types_trajectory.jsonl
├── E1_protein_lookup_trajectory.jsonl
├── E1_protein_properties_trajectory.jsonl
├── E2_annotation_types_trajectory.jsonl
├── E2_protein_lookup_trajectory.jsonl
├── E2_protein_properties_trajectory.jsonl
├── E3_annotation_types_trajectory.jsonl
├── E3_protein_lookup_trajectory.jsonl
├── E3_protein_properties_trajectory.jsonl
├── E4_annotation_types_trajectory.jsonl
├── E4_protein_lookup_trajectory.jsonl
├── E4_protein_properties_trajectory.jsonl
├── E5_annotation_types_trajectory.jsonl
├── E5_protein_lookup_trajectory.jsonl
├── E5_protein_properties_trajectory.jsonl
├── E6_annotation_types_trajectory.jsonl
├── E6_protein_lookup_trajectory.jsonl
├── E6_protein_properties_trajectory.jsonl
├── phase0_uniprot_analysis.md     # Analysis
├── phase0_uniprot_results.json    # Structured results
├── phase0_run.log                 # Execution log
└── l2_memory_analysis.md          # Memory layer analysis
```

#### Location 3: `experiments_archive/2026-01-28_phase1_closed_loop/` (Phase 1)

**Closed-Loop UniProt Experiments** (10 tasks):
```
experiments_archive/2026-01-28_phase1_closed_loop/
├── 1_select_all_taxa_used_in_uniprot.jsonl
├── 2_bacteria_taxa_and_their_scientific_name.jsonl
├── 4_uniprot_mnemonic_id.jsonl
├── 12_entries_integrated_on_date.jsonl
├── 30_merged_loci.jsonl
├── 33_longest_variant_comment.jsonl
├── 85_taxonomy_host.jsonl
├── 104_uniprot_recomended_protein_full_name.jsonl
├── 106_uniprot_reviewed_or_not.jsonl
├── 121_proteins_and_diseases_linked.jsonl
└── phase1_uniprot_local/
    ├── annotation_types.jsonl
    ├── protein_lookup.jsonl
    └── protein_properties.jsonl
```

**Extracted Memories**: 9 strategies stored in memory system (44% judge accuracy)

#### Location 4: `experiments_archive/2026-02-01_stochastic_smoke/` (S1)

**Stochastic Smoke Test** (2 tasks, k=2):
```
experiments_archive/2026-02-01_stochastic_smoke/
└── results/
    ├── 4_uniprot_mnemonic_id_rollout1.jsonl
    ├── 4_uniprot_mnemonic_id_rollout2.jsonl
    ├── 106_uniprot_reviewed_or_not_rollout1.jsonl
    └── 106_uniprot_reviewed_or_not_rollout2.jsonl
```

**Findings**:
- Simple tasks: deterministic (both rollouts identical)
- Complex tasks: stochastic variation in iterations 9-12
- Memory store: empty (baseline)
- Pass@1 = Best-of-N = Pass@k = 100%

#### Location 5: `experiments_archive/2026-02-03_s3_prompt_perturbation/` (S3)

**Prompt Perturbation Experiment** (Minimal: 1 task × 5 rollouts × 4 strategies):
```
experiments_archive/2026-02-03_s3_prompt_perturbation/
└── results/
    └── logs/
        ├── 1_select_all_taxa_used_in_uniprot/
        │   ├── none/
        │   │   ├── 1_select_all_taxa_used_in_uniprot_rollout1.jsonl
        │   │   ├── 1_select_all_taxa_used_in_uniprot_rollout2.jsonl
        │   │   ├── 1_select_all_taxa_used_in_uniprot_rollout3.jsonl
        │   │   ├── 1_select_all_taxa_used_in_uniprot_rollout4.jsonl
        │   │   └── 1_select_all_taxa_used_in_uniprot_rollout5.jsonl
        │   ├── prefix/ (5 rollouts)
        │   ├── rephrase/ (5 rollouts)
        │   └── thinking/ (5 rollouts)
        ├── 121_proteins_and_diseases_linked/ (4 strategies × 5 rollouts)
        ├── 2_bacteria_taxa_and_their_scientific_name/ (4 strategies × 5 rollouts)
        ├── 30_merged_loci/ (4 strategies × 5 rollouts)
        └── 4_uniprot_mnemonic_id/ (4 strategies × 5 rollouts)
```

**Total Trajectories**: 5 tasks × 4 strategies × 5 rollouts = **100 trajectory files**

**Minimal Test Result** (1 task):
- Prefix perturbation: +33% diversity, no performance degradation
- Trajectory Vendi Score: 1.00 → 1.33
- Sampling Efficiency: 50% → 66.6%

**Full Test Pending**: Remaining 4 tasks need to be analyzed

---

## Evolution of Research Questions

### Initial Questions (Phase 0)

1. ❓ Do memory layers improve query construction?
2. ❓ Which layers are critical vs additive?
3. ❓ Does handle pattern prevent prompt leakage?

### Questions Answered

1. ✅ **L0 sense card is critical** (E2: 0 → 5-7 tool calls)
2. ✅ **Handle pattern reduces leakage 52%** (E7b)
3. ✅ **Schema constraints improve correctness** (E3)
4. ✅ **Stochastic variation exists for complex tasks** (S1)
5. ⚠️ **Judge accuracy problematic** (Phase 1: 44% accuracy)

### Current Questions (Phase 5)

1. ❓ Does prompt perturbation increase trajectory diversity at scale? (S3 full run pending)
2. ❓ What is the Best-of-N vs Pass@1 gap? (Need harder tasks with failures)
3. ❓ Does memory augmentation improve Pass@k? (Need memory-augmented baseline)
4. ❓ Can we fix judge accuracy? (Need ground truth validation, AGENT_GUIDE context)
5. ❓ Do all layers work synergistically? (E6 full layer cake pending)

### Future Questions (Phase 6+)

1. ❓ Does memory consolidation prevent bloat? (E10)
2. ❓ Does forgetting improve quality? (E11)
3. ❓ Can MaTTS rollouts improve extraction quality? (E12)
4. ❓ What is the representation ablation boundary? (Which knowledge helps?)
5. ❓ Where do LM capabilities end? (What requires tool extension?)

---

## Validated Patterns (Production-Ready)

| Pattern | Evidence | Extraction Status | Location |
|---------|----------|------------------|----------|
| **Handle Pattern** | E7b: 52% leakage reduction | ✅ Extracted | `findings/validated_patterns/handle_pattern.md` |
| **L0 Sense Card** | E2: 100% convergence, 0→5-7 tool calls | ✅ Extracted | `findings/validated_patterns/l0_sense_card.md` |
| **Two-Phase Retrieval** | All experiments: prevents unbounded context | ✅ Validated | Implementation in `prototype/tools/` |
| **L1 Schema Constraints** | E3: improved correctness, anti-patterns | ✅ Validated | Implementation in `prototype/packers/l1_schema.py` |

---

## Open Issues

### Critical Blockers

1. **Judge Accuracy** (Phase 1)
   - Only 44% accurate vs ground truth
   - Extracting incorrect patterns at 2:1 ratio
   - Needs ground truth validation + AGENT_GUIDE context
   - **Blocker for**: Scaled closed-loop learning

2. **Memory Consolidation Not Implemented** (E10)
   - Risk of memory bloat
   - No merge/supersede logic
   - **Blocker for**: Production deployment

### Needs Investigation

3. **Prompt Perturbation at Scale** (S3)
   - Minimal test: +33% diversity with prefix
   - Full test: 5 tasks pending (~2-3 hours)
   - **Needed for**: MaTTS methodology validation

4. **Full Layer Cake** (E6)
   - E1-E5 validated individually
   - Need to test synergy vs redundancy
   - **Needed for**: Production configuration

5. **Best-of-N Gap** (Stochastic)
   - Current tasks: 100% Pass@1 (too easy)
   - Need harder tasks with failures
   - **Needed for**: MaTTS value proposition

---

## Recommendations for Next Session

### Priority 1: Complete S3 Full Run
**Why**: Minimal test succeeded (+33% diversity), need full validation

**Command**:
```bash
source ~/uvws/.venv/bin/activate
python experiments_archive/2026-02-03_s3_prompt_perturbation/run_experiment_s3.py \
  --full --output experiments_archive/2026-02-03_s3_prompt_perturbation/results/
```

**Expected**: 100 runs (~2-3 hours), 500 trajectory files
**Success criteria**: Diversity ≥1.5x baseline, Pass@1 within 10%

### Priority 2: Extract S3 Results
**If validated**:
- Create `findings/validated_patterns/prompt_perturbation.md`
- Document optimal perturbation strategy
- Recommend for MaTTS implementation

**If invalidated**:
- Document why perturbation doesn't scale
- Move to `findings/failed_approaches/`

### Priority 3: Run E6 (Full Layer Cake)
**Why**: Need to test layer synergy

**Command**:
```bash
python prototype/run/phase0_uniprot.py \
  --l0 --l1 --l2 --l3 \
  --tasks tasks/uniprot_subset_tasks.json \
  --output experiments_archive/2026-02-XX_e6_full_layer_cake/
```

**Success criteria**: Performance ≥ max(E2,E3,E4,E5), acceptable cost

### Priority 4: Fix Judge Accuracy
**Why**: 44% accuracy blocks closed-loop learning

**Approach**:
- Add ground truth SPARQL validation
- Inject AGENT_GUIDE context into judge
- Re-run Phase 1 with improved judge

---

## File Organization Summary

### Experimental Results Structure

```
experiments/reasoningbank/
├── results/                      # Early experiments (E1-E6 on PROV)
│   ├── E{1-6}_*_trajectory.jsonl
│   ├── phase0_analysis.md
│   ├── phase1_subset_analysis.md
│   └── SMOKE_TEST_REPORT_2026-02-03.md
│
├── results_uniprot/              # Phase 0 UniProt endpoint
│   ├── E{1-6}_*_trajectory.jsonl
│   ├── phase0_uniprot_analysis.md
│   └── l2_memory_analysis.md
│
└── experiments_archive/          # Timestamped experiments
    ├── 2026-01-28_phase1_closed_loop/
    │   ├── {task_id}.jsonl (10 tasks)
    │   └── phase1_uniprot_local/*.jsonl
    │
    ├── 2026-02-01_stochastic_smoke/
    │   └── results/*.jsonl (4 trajectories)
    │
    └── 2026-02-03_s3_prompt_perturbation/
        └── results/logs/{task}/{strategy}/*.jsonl (100 trajectories)
```

### Total Trajectory Count

| Location | Trajectories | Experiments |
|----------|-------------|-------------|
| `results/` | 18 | E1-E6 (PROV) |
| `results_uniprot/` | 18 | E1-E6 (UniProt) |
| `experiments_archive/2026-01-28_*/` | 13 | Phase 1 closed-loop |
| `experiments_archive/2026-02-01_*/` | 4 | S1 stochastic smoke |
| `experiments_archive/2026-02-03_*/` | 100 | S3 prompt perturbation (minimal) |
| **Total** | **153** | **5 experiments** |

### Pending Trajectories (S3 Full)

- Current: 1 task × 4 strategies × 5 rollouts = 20 trajectories
- Full: 5 tasks × 4 strategies × 5 rollouts = 100 trajectories
- **Remaining**: 80 trajectories (~2-3 hours)

---

## References

### Key Documents

- `STATUS.md` - Current priorities and next steps
- `WORK_LOG.md` - Session-by-session journal
- `findings/validated_patterns/` - Production-ready patterns
- `experiments_archive/README.md` - Experiment index

### Analysis Files

- `results/phase1_subset_analysis.md` - Judge accuracy analysis (557 lines)
- `results/SMOKE_TEST_REPORT_2026-02-03.md` - S1 stochastic findings
- `results_uniprot/phase0_uniprot_analysis.md` - E1-E6 UniProt analysis
- `results_uniprot/l2_memory_analysis.md` - Memory layer deep dive

### Git Milestones

- `4552c0b` - MaTTS methodology established
- `aa90687` - Stochastic evaluation infrastructure
- `ebf213d` - Trajectory diversity metrics
- `98f1d17` - S3 bug fixes + LM-as-judge
- `696b0c1` - Directory reorganization complete

---

**Last updated**: 2026-02-04
**Next milestone**: S3 full run → 5 tasks, 100 rollouts, diversity validation
