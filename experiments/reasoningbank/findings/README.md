# Research Findings

Extraction-ready documentation of validated patterns, failed approaches, open questions, and quantitative evidence.

## Overview

This directory organizes what we've learned from experiments into **actionable knowledge** for future production implementation.

## Structure

```
validated_patterns/     - ✅ Proven approaches ready for extraction
failed_approaches/      - ❌ Documented mistakes to avoid
open_questions/         - 🤔 Needs more research
metrics/                - 📊 Quantitative evidence
```

## Extraction Priority

### 🔥 High Priority (Immediate Production Value)

1. **Handle Pattern** (`validated_patterns/handle_pattern.md`)
   - **Evidence**: E7b (52% leakage reduction), E2 (tool usage enabled)
   - **Impact**: Core abstraction, affects all tool interactions
   - **Production**: Must-have for scalable RLM

2. **L0 Sense Card** (`validated_patterns/l0_sense_card.md`)
   - **Evidence**: E2 (0→5-7 tool calls), E3/E4 comparison
   - **Impact**: Enables tool discovery and ontology orientation
   - **Production**: Required for cold-start exploration

3. **Two-Phase Retrieval** (`validated_patterns/two_phase_retrieval.md`)
   - **Evidence**: All experiments (prevents unbounded context)
   - **Impact**: Memory access pattern, prevents prompt bloat
   - **Production**: Core memory interface design

4. **L1 Schema Constraints** (`validated_patterns/l1_schema_constraints.md`)
   - **Evidence**: E3 (correctness improvement), UniProt runs
   - **Impact**: Query quality, anti-pattern prevention
   - **Production**: Validation layer

### 🟡 Medium Priority (Promising, Needs Validation)

5. **Prompt Perturbation** (pending full S3 results)
   - **Evidence**: S3 minimal (+33% diversity, no degradation)
   - **Impact**: Test-time scaling, MaTTS rollout selection
   - **Production**: Optional optimization

### 🟢 Low Priority (Future Work)

6. **Memory Consolidation** (E10 not tested)
7. **Memory Forgetting** (E11 not tested)
8. **Layer Interactions** (E6 not completed)

## Validated Patterns

### What Makes a Pattern "Validated"?

1. **Evidence-based**: Quantitative results from experiments
2. **Reproducible**: Multiple runs show consistent benefit
3. **Actionable**: Clear production implications
4. **Documented**: Problem, solution, validation, extraction notes

### Current Validated Patterns

| Pattern | Experiments | Key Metric | Production Ready? |
|---------|-------------|------------|-------------------|
| Handle pattern | E7b, E2 | 52% leakage↓ | ✅ Yes |
| L0 sense card | E2 | 0→5-7 tool calls | ✅ Yes |
| Two-phase retrieval | All | Prevents unbounded context | ✅ Yes |
| L1 schema constraints | E3, UniProt | Correctness↑ | ✅ Yes |

### Template: validated_patterns/pattern_name.md

Each validated pattern file includes:

```markdown
# [Pattern Name]

**Status**: ✅ Validated ([Experiment IDs])
**Evidence**: [Quantitative results with links]
**Extraction Priority**: 🔥 High | 🟡 Medium | 🟢 Low

## Problem
[What problem does this solve?]

## Solution
[How does this pattern work?]

## Validation
- **Experiment**: [ID]
- **Metrics**: [Quantitative results]
- **Comparison**: [Baseline vs pattern]

## Production Implications
- Must-have or optional?
- Performance considerations
- API design implications
- Dependencies

## Code Reference
See `01_PROTOTYPE/path/to/module.py` (lines X-Y) for prototype

## Related Patterns
- Depends on: [other patterns]
- Enables: [future patterns]
```

## Failed Approaches

### Purpose

Document approaches that **didn't work** to avoid repeating mistakes.

### Current Failed Approaches

| Approach | Experiment | Why It Failed | Alternative |
|----------|------------|---------------|-------------|
| Tool-mediated retrieval | E8 (planned), empirical | Delegation doesn't emerge | Auto-inject (Mode 1) |
| Static endpoint preambles | UniProt early runs | Caused refusals | Agentic discovery |

### Template: failed_approaches/approach_name.md

```markdown
# [Approach Name]

**Status**: ❌ Failed ([Experiment ID])
**Why We Tried**: [Original hypothesis]

## What We Did
[Description of approach]

## Why It Failed
- **Evidence**: [Quantitative/qualitative]
- **Root Cause**: [Analysis]

## What We Learned
[Key insights]

## Don't Do This in Production
[Specific anti-patterns to avoid]

## Alternative Approach
[What works instead]
```

## Open Questions

Approaches that need more research before validation/invalidation.

### Current Open Questions

1. **Memory Consolidation** (E10 not run)
   - Does merge/supersede improve quality over append-only?
   - What consolidation policy works best?

2. **Layer Interactions** (E6 partial)
   - Are layers redundant or synergistic?
   - Optimal layer combination?

3. **Curriculum Learning** (Phase 1 partial results)
   - Does memory quality improve over time?
   - What curriculum strategy works?

## Metrics

Quantitative evidence organized by category.

### Files

- `e2_validation.md` - Layer ablation (E1-E6) quantitative results
- `s3_diversity.md` - Trajectory diversity metrics
- `iteration_counts.md` - Before/after API improvements
- `leakage_comparison.md` - E7a vs E7b prompt leakage

### Format

Each metrics file includes:
- Raw data (tables, JSON excerpts)
- Statistical analysis
- Visualizations (if applicable)
- Comparison to baselines
- Interpretation

## Using These Findings

### For Current Research

When completing an experiment:
1. Analyze results
2. Write validated pattern (if proven) OR failed approach (if disproven)
3. Update metrics/ with quantitative data
4. Update this README with extraction priority

### For Future Production

When extracting to production:
1. Read `validated_patterns/` in priority order
2. Check `failed_approaches/` to avoid mistakes
3. Use `metrics/` to set validation benchmarks
4. Follow `04_EXTRACTION_GUIDE/` for systematic extraction

## Contributing New Findings

```bash
# After experiment completes
cd 03_FINDINGS/

# If validated
vim validated_patterns/new_pattern.md

# If failed
vim failed_approaches/failed_approach.md

# Add metrics
vim metrics/experiment_id_metrics.md

# Update index
vim README.md

# Commit
git add .
git commit -m "Add findings from experiment [ID]"
```

---

**Last updated**: 2026-02-04
**Total validated patterns**: 4
**Total failed approaches**: 2 (documented)
**Extraction priority items**: 4 (high priority)
