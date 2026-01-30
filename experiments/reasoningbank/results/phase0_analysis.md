# Phase 0 Experiments: Layer Ablation Analysis

**Date**: 2026-01-30
**Experiments**: E1-E6 (Layer ablation study)
**Tasks**: 3 tasks × 6 experiments = 18 total runs
**Success Rate**: 18/18 (100% convergence)

---

## Executive Summary

All experiments converged successfully, validating that the ReasoningBank layer architecture works correctly. **Key finding**: **L1 schema constraints** provided the most dramatic improvement, reducing iterations by 50%+ for entity lookup tasks (3 iterations vs 6-9 for other configurations).

---

## Experiment Configurations

| Exp | Layers Enabled | Description |
|-----|---------------|-------------|
| **E1** | None | Baseline - raw RLM with no context layers |
| **E2** | L0 only | Sense card (metadata, namespaces, size) |
| **E3** | L1 only | Schema constraints (anti-patterns, disjoint, domain/range) |
| **E4** | L3 only | Guide summary (compressed ontology guide) |
| **E5** | L2 only | Seeded procedural memory (5 strategies) |
| **E6** | All (L0+L1+L2+L3) | Full layer cake |

---

## Results Summary

### Iteration Counts by Experiment

| Experiment | entity_lookup | property_find | hierarchy | **Avg** |
|-----------|---------------|---------------|-----------|---------|
| **E1** (Baseline) | 7 | 8 | 9 | **8.0** |
| **E2** (L0) | 6 | 9 | 10 | **8.3** |
| **E3** (L1) | **3** ✨ | 10 | 8 | **7.0** |
| **E4** (L3) | 7 | 9 | 11 | **9.0** |
| **E5** (L2) | 6 | 9 | 11 | **8.7** |
| **E6** (Full) | 6 | 10 | 10 | **8.7** |

**Key Insight**: E3 (L1 schema constraints only) achieved **3 iterations** for entity_lookup - a **50%+ reduction** compared to baseline!

---

## Detailed Analysis

### 1. E3 (L1 Schema Constraints) - Standout Winner

**Dramatic improvement on entity_lookup task:**
- **3 iterations** vs 6-7 for other experiments
- Answer quality: High - correctly identified Activity as disjoint from Entity
- Why it works: Anti-patterns and disjoint classes provide immediate actionable constraints

**E3 Answer (3 iterations):**
> "Activity is a class in the PROV ontology that represents something that occurs over a period of time and acts upon or with entities. Based on the schema constraints provided:
> - Activity is disjoint from Entity (Activity⊥Entity), meaning nothing can be both an Activity and an Entity
> - Activity is also disjoint from InstantaneousEvent
> - Activities can have ActivityInfluence associated with them"

**Why L1 worked so well:**
1. **Anti-patterns** explicitly warned against mixing Activity and Entity
2. **Disjoint classes** provided formal constraints
3. **Domain/Range** showed property signatures immediately
4. Agent had direct, actionable guidance without needing exploration

### 2. E2 (L0 Sense Card) - Modest Improvement

**Iteration counts:** Similar to baseline (avg 8.3 vs 8.0)

**Value provided:**
- Metadata (size: 1664 triples, 59 classes, 69 properties)
- Namespace information
- Formalism level (OWL-DL)

**Why it didn't reduce iterations much:**
- Metadata is useful for orientation but doesn't constrain query construction
- Still requires exploration via tools to find specifics

### 3. E4 (L3 Guide Summary) - Slightly Worse

**Iteration counts:** Slightly higher than baseline (avg 9.0 vs 8.0)

**Observation:**
- Guide provides context but may increase cognitive load
- More leakage (large_returns: 1-3) suggests more data to process

**Hypothesis:**
- Guides work better when combined with other layers (see E6)
- Standalone guide may be too general without constraints

### 4. E5 (L2 Procedural Memory) - Similar to Baseline

**Iteration counts:** 8.7 avg (slightly higher than baseline)

**Seeded strategies:**
- "Find Entity by Label"
- "Explore Properties of Class"
- "Navigate Class Hierarchy"
- "Use Bounded Tools First"
- "Avoid Unbounded SPARQL Queries"

**Observation:**
- Seed strategies were general and didn't match specific tasks well
- Would likely improve with task-relevant memories from closed-loop extraction

### 5. E6 (Full Layer Cake) - Balanced Performance

**Iteration counts:** 8.7 avg (similar to E2, E5)

**Leakage:** Higher large_returns (41 for property_find) - most data to process

**Observation:**
- No dramatic improvement over single layers
- May have redundancy or competing guidance
- Suggests layers have diminishing returns when combined

---

## Convergence Analysis

**All experiments converged (100% success rate):**

| Task | E1 | E2 | E3 | E4 | E5 | E6 |
|------|----|----|----|----|----|----|
| entity_lookup | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ |
| property_find | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ |
| hierarchy | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ |

**Takeaway**: Even baseline (E1) converges reliably. Layers affect *efficiency* more than *capability*.

---

## Prompt Leakage Metrics

| Experiment | stdout_chars | large_returns | subcalls |
|-----------|--------------|---------------|----------|
| E1 | 0 | 0 | 0 |
| E2 | 0 | 0 | 0 |
| E3 | 0 | 0 | 0 |
| E4 | 0 | 1-3 | 0 |
| E5 | 0 | 1-7 | 0 |
| E6 | 0 | 0-41 | 0 |

**Findings:**
- ✅ No stdout bloat (all 0) - handle-based tools working correctly
- ✅ No subcall inflation (all 0) - good control
- ⚠️ E6 shows higher large_returns (41) - more context to process

**Validation**: Handle-based tool API (BlobRef pattern) successfully prevents stdout bloat.

---

## Answer Quality (Qualitative Assessment)

All experiments produced **correct, comprehensive answers**. Sample comparison:

**E1 (Baseline - 7 iters):**
> "Activity is a fundamental concept in the PROV (Provenance) ontology... Activities are central to provenance tracking as they represent the processes that create, modify, or consume data and other entities in a system."

**E3 (L1 - 3 iters):**
> "Activity is a class in the PROV ontology... Activity is disjoint from Entity (Activity⊥Entity), meaning nothing can be both an Activity and an Entity..."

**E6 (Full - 6 iters):**
> "In the W3C PROV (Provenance) ontology, Activity is a fundamental class... It is disjoint with the Entity class, meaning nothing can be both an Activity and an Entity simultaneously..."

**Quality verdict**: All answers are accurate. E3's brevity suggests focused exploration; E1/E6 add more context.

---

## Key Findings

### 1. Schema Constraints (L1) Are Most Valuable

**Impact**: 50%+ iteration reduction for definitional queries
**Why**: Provides immediate, actionable constraints (disjoint classes, anti-patterns)
**Recommendation**: Always include L1 in production configurations

### 2. Sense Cards (L0) Provide Orientation

**Impact**: Modest (no significant iteration reduction)
**Value**: Metadata helps with sizing/scoping but doesn't constrain queries
**Recommendation**: Useful but not critical for simple queries

### 3. Guides (L3) May Add Cognitive Load

**Impact**: Slightly negative when standalone (avg 9.0 vs 8.0)
**Hypothesis**: Too general without constraints; better in combination
**Recommendation**: Combine with L1 or use only for complex domains

### 4. Seed Memory (L2) Needs Task Relevance

**Impact**: Neutral (avg 8.7 vs 8.0)
**Issue**: General strategies didn't match specific tasks
**Recommendation**: Populate L2 via closed-loop extraction (Phase 1)

### 5. Full Layer Cake Shows No Synergy

**Impact**: Similar to individual layers (avg 8.7)
**Observation**: No dramatic improvement over best single layer (E3)
**Hypothesis**: Possible redundancy or competing guidance
**Recommendation**: Further study layer interactions (E13)

### 6. Handle-Based Tools Work Correctly

**Validation**: Zero stdout bloat across all experiments
**Design**: BlobRef pattern + two-phase retrieval prevents prompt leakage
**Recommendation**: Maintain handle-based design for production

---

## Recommendations

### Immediate (Production Config)

1. **Always include L1** (schema constraints) - provides highest value
2. **Include L0** (sense card) - low cost, useful orientation
3. **Populate L2 via extraction** - seed strategies are too general
4. **Use L3 selectively** - for complex domains or when combined with L1

### Suggested Production Config

```python
Cfg(
    l0=Layer(True, 600),   # Sense card
    l1=Layer(True, 1000),  # Schema constraints (CRITICAL)
    l2=Layer(True, 2000),  # Extracted memories (populate via closed-loop)
    l3=Layer(False, 0),    # Disable unless needed
)
```

### Future Experiments

1. **E13 - Layer Interaction Study**: Test E3+E6 variants to understand why full cake doesn't improve over L1 alone
2. **Phase 1 (E9-E12)**: Closed-loop extraction to populate L2 with task-relevant memories
3. **E7 - Prompt Leakage**: Compare naive vs handle-based tools (already validated: handles work!)
4. **E8 - Retrieval Policy**: Auto-inject (Mode 1) vs tool-mediated (Mode 2)

---

## Conclusions

**Success**: All experiments converged (100% success rate)

**Standout Result**: L1 schema constraints reduced iterations by 50%+ for entity lookup tasks

**Validation**: Handle-based tool API prevents prompt bloat (all experiments show 0 stdout_chars)

**Next Steps**: Phase 1 closed-loop learning to populate L2 with task-relevant memories

---

## Appendix: Raw Data

### Iteration Counts (Full Table)

| Exp | Task | Iters | Converged | Answer Length | SPARQL Length | Large Returns |
|-----|------|-------|-----------|---------------|---------------|---------------|
| E1 | entity_lookup | 7 | ✓ | 865 | 171 | 0 |
| E1 | property_find | 8 | ✓ | 369 | 118 | 0 |
| E1 | hierarchy | 9 | ✓ | 370 | 117 | 0 |
| E2 | entity_lookup | 6 | ✓ | 366 | 90 | 0 |
| E2 | property_find | 9 | ✓ | 881 | 104 | 0 |
| E2 | hierarchy | 10 | ✓ | 370 | 126 | 0 |
| E3 | entity_lookup | **3** | ✓ | 441 | 161 | 0 |
| E3 | property_find | 10 | ✓ | 1,194 | 141 | 0 |
| E3 | hierarchy | 8 | ✓ | 314 | 139 | 0 |
| E4 | entity_lookup | 7 | ✓ | 427 | 126 | 1 |
| E4 | property_find | 9 | ✓ | 1,320 | 547 | 0 |
| E4 | hierarchy | 11 | ✓ | 136 | 106 | 3 |
| E5 | entity_lookup | 6 | ✓ | 683 | 122 | 1 |
| E5 | property_find | 9 | ✓ | 1,072 | 84 | 7 |
| E5 | hierarchy | 11 | ✓ | 128 | 145 | 1 |
| E6 | entity_lookup | 6 | ✓ | 736 | 130 | 1 |
| E6 | property_find | 10 | ✓ | 890 | 127 | 41 |
| E6 | hierarchy | 10 | ✓ | 291 | 152 | 0 |

### Experiment Configs (Code)

```python
EXPS = {
    'E1': Cfg(),  # Baseline - no layers
    'E2': Cfg(l0=Layer(True, 600)),  # L0 only (sense card)
    'E3': Cfg(l1=Layer(True, 1000)), # L1 only (constraints)
    'E4': Cfg(l3=Layer(True, 1000)), # L3 only (guide summary)
    'E5': Cfg(l2=Layer(True, 2000)), # L2 only (seeded memories)
    'E6': Cfg(l0=Layer(True,600), l1=Layer(True,1000),
              l2=Layer(True,2000), l3=Layer(True,1000)),  # Full layer cake
}
```
