# Extraction Guide: Research to Production

This guide helps future Claude systematically convert research findings into a production Python package.

## Purpose

This directory **is not the research**. It's a **protocol** for how to extract validated patterns from research and reimplement cleanly.

## Overview

```
Research Phase (Current)          Production Phase (Future)
├── 01_PROTOTYPE/                 ├── Clean package
│   └── ~1300 LOC (throwaway)     │   └── Extracted patterns
├── 02_EXPERIMENTS/               │       implemented properly
│   └── Timestamped runs          │
└── 03_FINDINGS/                  └── Validation:
    ├── validated_patterns/           Meets or exceeds
    └── metrics/                      research metrics
```

**Key Principle**: Extract patterns and rewrite. Do NOT refactor prototype code.

## Why Not Refactor?

From `00_FOUNDATIONS/IMPLEMENTATION_PLAN.md`:

> "The existing `rlm_runtime` code embodies assumptions we want to *test*, not assume."

The same applies here: `01_PROTOTYPE/` embodies **experimental assumptions**. Production code should be:
- Type-hinted throughout
- Comprehensively tested (pytest)
- Performance-optimized
- API-stable
- Well-documented

Prototype code is none of these things by design (optimized for research velocity).

## Step-by-Step Extraction

### Step 1: Review Validated Patterns (1-2 hours)

Read all files in `03_FINDINGS/validated_patterns/`:

1. [handle_pattern.md](../03_FINDINGS/validated_patterns/handle_pattern.md) - 🔥 High priority
2. [l0_sense_card.md](../03_FINDINGS/validated_patterns/l0_sense_card.md) - 🔥 High priority
3. [two_phase_retrieval.md](../03_FINDINGS/validated_patterns/two_phase_retrieval.md) - 🔥 High priority
4. [l1_schema_constraints.md](../03_FINDINGS/validated_patterns/l1_schema_constraints.md) - 🔥 High priority
5. (Others as added)

Each file contains:
- Problem statement
- Solution approach
- Validation evidence
- **Production implications** ← Critical section
- Code reference

### Step 2: Review Failed Approaches (30 min)

Read `03_FINDINGS/failed_approaches/*.md` to avoid repeating mistakes:

- What was tried
- Why it failed
- What to do instead

### Step 3: Synthesize Architecture (2-3 hours)

Use [ARCHITECTURE.md](ARCHITECTURE.md) as starting point, but adjust based on validated patterns.

Key decisions:
- Public API surface (what users interact with)
- Internal architecture (modules, abstractions)
- Extension points (what's pluggable)
- Performance requirements

### Step 4: Define API (1-2 hours)

Use [API_DESIGN.md](API_DESIGN.md) to spec public interface:

```python
# Example (to be refined)
from reasoningbank import RLMEngine, DataStore, MemoryBank

# Create engine with memory
engine = RLMEngine(
    model="claude-sonnet-4",
    memory=MemoryBank.from_seed("strategies.json")
)

# Execute query
result = engine.run(
    query="What is Activity?",
    ontology="prov.ttl",
    max_iterations=12
)

# Access results
print(result.answer)        # Structured output
print(result.sparql)        # Generated query
print(result.converged)     # Success indicator
```

### Step 5: Implement Clean (5-10 hours)

**Do NOT refactor `01_PROTOTYPE/` code.**

Instead:
1. Create new package structure
2. Extract patterns from findings docs
3. Reference prototype for **what** it does (not how)
4. Implement with:
   - Type hints (`typing`, `TypedDict`, `Protocol`)
   - Docstrings (Google/NumPy style)
   - Tests (pytest, >80% coverage)
   - Performance (profiling, optimization)
   - API stability (semantic versioning)

#### Implementation Order

**Priority 1: Core Abstractions** (~500 LOC)
- `DataRef` (handle pattern)
- `DataStore` (storage + bounded access)
- `Tool` protocol (bounded tool interface)

**Priority 2: Packers** (~300 LOC)
- `SenseCardPacker` (L0)
- `SchemaConstraintsPacker` (L1)
- `MemoryPacker` (L2)

**Priority 3: Memory Substrate** (~400 LOC)
- `MemoryStore` (two-phase retrieval)
- `MemoryItem` (with validation)
- Retrieval strategies (BM25, curriculum)

**Priority 4: Execution Engine** (~600 LOC)
- `RLMEngine` (DSPy integration)
- Context builder (layer cake)
- Result types (structured output)

**Priority 5: Evaluation** (~200 LOC)
- Diversity metrics (Vendi Score, Jaccard)
- Leakage instrumentation
- Benchmark runner

**Total**: ~2000 LOC (vs prototype's 1300 LOC)
- More comprehensive (error handling, typing, docs)
- But cleaner (no experimental cruft)

### Step 6: Validate Against Metrics (1-2 hours)

Compare reimplementation against benchmarks in `03_FINDINGS/metrics/`.

Must meet or exceed:
- **E7b leakage**: <12 large returns per run
- **E2 convergence**: 100% on test tasks
- **E2 tool usage**: 5-7 calls per task
- **S3 diversity**: Vendi Score ≥ 1.3 (if perturbation implemented)

### Step 7: Document (2-3 hours)

- Public API documentation
- Architecture overview
- Migration guide (if replacing existing code)
- Performance characteristics
- Extension guide

## Files in This Directory

### ARCHITECTURE.md (To be written)

Proposed production architecture:

```
Architecture:
├── Core abstractions
│   ├── DataRef, DataStore
│   └── Tool protocol
├── Packer layer
│   ├── L0: Sense card
│   ├── L1: Schema constraints
│   └── L2: Memory formatting
├── Memory substrate
│   ├── Storage (SQLite)
│   ├── Retrieval (BM25)
│   └── Policies (judge, extract, consolidate)
├── Execution engine
│   ├── DSPy RLM integration
│   ├── Context builder
│   └── Tool registry
└── Evaluation
    ├── Metrics (diversity, leakage)
    └── Benchmarks
```

### API_DESIGN.md (To be written)

Public API specification with examples and type signatures.

### IMPLEMENTATION_NOTES.md (To be written)

Critical lessons from prototype:
- DSPy tool signatures (`lambda args, kwargs:`)
- Context impact on tool usage
- API defaults matter
- Bounded tools essential
- Two-phase retrieval prevents bloat

### METRICS.md (To be written)

Validation benchmarks the rewrite must meet:

| Metric | Baseline (E1) | Target (E7b, E2) | Measurement |
|--------|---------------|------------------|-------------|
| Leakage (large returns) | 23 | ≤12 | Count returns >1K chars |
| Convergence | 67% | ≥90% | % successful tasks |
| Tool usage | 0 | 5-7 | Calls per task |
| Iterations | 8.2 | ≤7 | Average per task |

## Quality Gates

Before calling extraction "complete":

- [ ] All high-priority patterns implemented
- [ ] All failed approaches avoided
- [ ] Metrics meet or exceed targets
- [ ] Tests pass (>80% coverage)
- [ ] Documentation complete
- [ ] API is stable (semantic versioning ready)

## Common Pitfalls

### ❌ Don't: Copy-paste prototype code

Prototype lacks types, docs, error handling, performance optimization.

### ✅ Do: Extract pattern and implement properly

Read findings doc → understand pattern → implement cleanly.

### ❌ Don't: Assume prototype is "almost done"

Prototype is optimized for **research velocity**, not production.

### ✅ Do: Budget 2-3x LOC for production

Types, docs, tests, error handling add substantial code.

### ❌ Don't: Skip failed approaches

Understanding what doesn't work is as important as what does.

### ✅ Do: Reference metrics continuously

Benchmarks ensure reimplementation preserves research gains.

## Timeline Estimate

| Phase | Time | Cumulative |
|-------|------|------------|
| Review patterns | 1-2h | 2h |
| Review failures | 0.5h | 2.5h |
| Architecture design | 2-3h | 5h |
| API design | 1-2h | 7h |
| Implementation | 5-10h | 15h |
| Validation | 1-2h | 17h |
| Documentation | 2-3h | 20h |

**Total**: ~20 hours (3 days of focused work)

## Next Steps

After reading this guide:

1. Read `03_FINDINGS/README.md` for extraction priorities
2. Read all `validated_patterns/*.md` files
3. Read all `failed_approaches/*.md` files
4. Start with ARCHITECTURE.md (design before coding)
5. Follow implementation order (core abstractions first)

---

**Last updated**: 2026-02-04
**Status**: Template ready, awaiting extraction phase
