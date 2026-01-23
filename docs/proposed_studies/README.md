# Proposed Studies

This directory tracks experimental studies that have been designed but not yet executed.

## Active Proposals

### E009: Memory Impact Sampling Study

**Status**: Proposed (awaiting implementation verification)
**Document**: [E009-memory-impact-sampling-study.md](./E009-memory-impact-sampling-study.md)
**Estimated Cost**: $40-60
**Estimated Time**: 4-6 hours
**Priority**: High

**Purpose**: Systematically test memory impact with proper sampling (N=10) to account for LLM stochasticity.

**Design**:
- 3 cohorts: No memory, Current memory, Explicit prompting
- 4 tasks: bacteria_taxa, ecoli_k12, rhea_reaction, gene_protein
- 10 trials per cohort per task = 120 runs
- Statistical analysis: t-tests, effect sizes, p < 0.05

**Blockers**:
- Implementation verification needed before execution
- Memory application tracking (was_referenced detection) should be added first

**Decision criteria**:
- p < 0.05 and positive effect → Keep memory, optimize
- p < 0.05 and negative effect → Redesign architecture
- p > 0.05 → Increase N or rethink hypothesis

---

## Study Lifecycle

**Proposed** → Designed but not ready to execute (blocked or pending review)
**Ready** → Implementation verified, ready to run
**In Progress** → Currently executing
**Completed** → Results documented in `docs/analysis/`

## Adding New Proposals

When proposing a new study:
1. Create detailed document in this directory
2. Update this README with summary
3. Include: purpose, design, cost/time estimates, blockers, decision criteria
4. Reference related analysis/design documents
