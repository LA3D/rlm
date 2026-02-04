# ReasoningBank Experiments

**Quick orientation** for LLMs and humans working with this codebase.

## What is this?

Testing whether **memory layers** (ontology sense cards, schema constraints, procedural strategies) improve LLM query construction over RDF ontologies using the RLM (Recursive Language Model) pattern.

**Core principle** (see [00_FOUNDATIONS/rlm_notes.md](00_FOUNDATIONS/rlm_notes.md)): Use **handles not payloads**. Keep large context in REPL state, not in chat history.

**Current phase**: Research/exploration → will later be extracted into production Python package.

## Current Status (2026-02-04)

- **Active experiment**: S3 prompt perturbation (MaTTS Phase 3)
- **Latest finding**: Prefix perturbation increases trajectory diversity 33%
- **Next**: Full S3 run (5 tasks × 5 rollouts × 4 strategies)

👉 See [STATUS.md](STATUS.md) for complete current status
👉 See [05_ARCHIVE/status_snapshots/](05_ARCHIVE/status_snapshots/) for historical status

## Quick Navigation

| I want to... | Go to... |
|--------------|----------|
| **Understand the architecture** | [00_FOUNDATIONS/IMPLEMENTATION_PLAN.md](00_FOUNDATIONS/IMPLEMENTATION_PLAN.md) |
| **Understand RLM v2 principles** | [00_FOUNDATIONS/rlm_notes.md](00_FOUNDATIONS/rlm_notes.md) |
| **See what worked** | [03_FINDINGS/validated_patterns/](03_FINDINGS/validated_patterns/) |
| **See what failed** | [03_FINDINGS/failed_approaches/](03_FINDINGS/failed_approaches/) |
| **Review experiment results** | [02_EXPERIMENTS/](02_EXPERIMENTS/) (timestamped directories) |
| **Extract to production** | [04_EXTRACTION_GUIDE/](04_EXTRACTION_GUIDE/) |
| **Check current status** | [STATUS.md](STATUS.md) |
| **Examine prototype code** | [01_PROTOTYPE/](01_PROTOTYPE/) (~1300 LOC) |

## Directory Structure

```
00_FOUNDATIONS/      - Core design principles (stable, foundational)
01_PROTOTYPE/        - Exploratory code (reference only, not production)
02_EXPERIMENTS/      - Timestamped experimental runs with results
03_FINDINGS/         - Extraction-ready validated/failed patterns
04_EXTRACTION_GUIDE/ - How to reimplement for production
05_ARCHIVE/          - Historical artifacts (bug reports, old docs)
tests/               - Organized test suite (smoke, integration, unit, debug)
analysis/            - Analysis scripts
tasks/               - Task definition files (evaluation queries)
seed/                - Bootstrap data (strategies, constraints)
results/             - Raw outputs (gitignored)
```

## RLM v2 Design Principles

From [00_FOUNDATIONS/rlm_notes.md](00_FOUNDATIONS/rlm_notes.md):

1. **Handles not payloads** - Wrap large data in `BlobRef` with metadata-only `repr()`
2. **REPL state not history** - Memory lives in variables, not chat context
3. **Inspect before load** - Tools return stats/peek/slice, not full content
4. **Two-phase retrieval** - `search()` returns IDs, `get()` returns content (capped)
5. **Programmatic recursion** - Loops + batched LLM calls, not "sub-agent vibes"
6. **Bounded tools** - All tools have explicit limits, refuse unbounded requests
7. **Structured output** - Return variables, then `SUBMIT()`, not raw text generation

**Why this matters**: Violating these principles drifts back into "agent with summarization" (Algorithm-2) instead of scalable RLM (Algorithm-1).

## Research-to-Production Pipeline

This directory is organized for **extraction**, not direct productionization:

### Current Phase: Research & Validation

- **01_PROTOTYPE/**: Exploratory code (~1300 LOC) - tests hypotheses, validates patterns
- **02_EXPERIMENTS/**: Timestamped runs with design + results + findings
- **03_FINDINGS/**: Extraction-ready documentation of what worked/failed

### Future Phase: Engineering & Production

Future Claude will:
1. Read `03_FINDINGS/validated_patterns/` → know what to build
2. Read `03_FINDINGS/failed_approaches/` → avoid repeat mistakes
3. Follow `04_EXTRACTION_GUIDE/README.md` → systematic extraction protocol
4. **Reimplement cleanly** (not refactor prototype code)

## Recent Work (Last 3 Commits)

- 98f1d17: Fix 3 critical S3 bugs + LM-as-judge evaluation
- ebf213d: Add S3 prompt perturbation + trajectory diversity metrics
- 0d8563e: Add smoke test report for stochastic evaluation

## Key Files (Read These First)

### For Newcomers
1. **THIS FILE** - Entry point
2. **[00_FOUNDATIONS/IMPLEMENTATION_PLAN.md](00_FOUNDATIONS/IMPLEMENTATION_PLAN.md)** - Architecture (~1320 lines)
3. **[00_FOUNDATIONS/rlm_notes.md](00_FOUNDATIONS/rlm_notes.md)** - RLM v2 principles (~137 lines)
4. **[STATUS.md](STATUS.md)** - Current state

### For Current Research
5. **[02_EXPERIMENTS/README.md](02_EXPERIMENTS/README.md)** - Experiment index
6. **[03_FINDINGS/README.md](03_FINDINGS/README.md)** - What we've learned

### For Future Engineering
7. **[04_EXTRACTION_GUIDE/README.md](04_EXTRACTION_GUIDE/README.md)** - How to extract
8. **[03_FINDINGS/validated_patterns/](03_FINDINGS/validated_patterns/)** - Proven approaches

## Validation Status

| Pattern | Status | Evidence | Extractable? |
|---------|--------|----------|--------------|
| Handle pattern (BlobRef) | ✅ Validated | E7b: 52% reduction in prompt leakage | ✅ Yes |
| L0 sense card | ✅ Validated | E2: Enables tool usage (0 → 5-7 calls) | ✅ Yes |
| Two-phase retrieval | ✅ Validated | search() then get() prevents unbounded context | ✅ Yes |
| L1 schema constraints | ✅ Validated | Anti-patterns + domain/range improve correctness | ✅ Yes |
| Prompt perturbation | 🔄 Promising | S3 minimal: +33% diversity, no degradation | ⏳ Pending full run |
| Memory consolidation | ⏳ Not tested | E10 not run yet | ❌ No |

## For AI Assistants (Claude Code)

When working on this codebase:

1. **Progressive disclosure**: Start here → foundations → specific area
2. **Timestamped experiments**: Each in `02_EXPERIMENTS/YYYY-MM-DD_name/` with single `EXPERIMENT.md`
3. **Findings as you go**: Update `03_FINDINGS/` as experiments complete
4. **Prototype is throwaway**: Code in `01_PROTOTYPE/` is for reference, not refactoring
5. **Git history preserved**: All moves used `git mv`, can trace origins

## Questions?

- **"What's the current status?"** → [STATUS.md](STATUS.md)
- **"What's the architecture?"** → [00_FOUNDATIONS/IMPLEMENTATION_PLAN.md](00_FOUNDATIONS/IMPLEMENTATION_PLAN.md)
- **"Why these design choices?"** → [00_FOUNDATIONS/rlm_notes.md](00_FOUNDATIONS/rlm_notes.md)
- **"What worked?"** → [03_FINDINGS/validated_patterns/](03_FINDINGS/validated_patterns/)
- **"How do I extract this?"** → [04_EXTRACTION_GUIDE/README.md](04_EXTRACTION_GUIDE/README.md)

---

**Last updated**: 2026-02-04
**Reorganization**: Completed (see REORGANIZATION_PLAN.md for details)
