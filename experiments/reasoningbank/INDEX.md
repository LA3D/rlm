# ReasoningBank Experiments

**Quick orientation** for LLMs and humans working with this codebase.

👉 **First time here?** Read [GETTING_STARTED.md](GETTING_STARTED.md) for practical quick-start guide.

## What is this?

Testing whether **memory layers** (ontology sense cards, schema constraints, procedural strategies) improve LLM query construction over RDF ontologies using the RLM (Recursive Language Model) pattern.

**Core principle** (see [foundations/rlm_notes.md](foundations/rlm_notes.md)): Use **handles not payloads**. Keep large context in REPL state, not in chat history.

**Current phase**: Research/exploration → will later be extracted into production Python package.

## Current Status (2026-02-04)

- **Active experiment**: S3 prompt perturbation (MaTTS Phase 3)
- **Latest finding**: Prefix perturbation increases trajectory diversity 33%
- **Next**: Full S3 run (5 tasks × 5 rollouts × 4 strategies)

👉 See [STATUS.md](STATUS.md) for complete current status
👉 See [WORK_LOG.md](WORK_LOG.md) for session-by-session history
👉 See [archive/status_snapshots/](archive/status_snapshots/) for historical status

## Quick Navigation

| I want to... | Go to... |
|--------------|----------|
| **Understand the architecture** | [foundations/IMPLEMENTATION_PLAN.md](foundations/IMPLEMENTATION_PLAN.md) |
| **Understand RLM v2 principles** | [foundations/rlm_notes.md](foundations/rlm_notes.md) |
| **See what worked** | [findings/validated_patterns/](findings/validated_patterns/) |
| **See what failed** | [findings/failed_approaches/](findings/failed_approaches/) |
| **Review experiment results** | [experiments_archive/](experiments_archive/) (timestamped directories) |
| **Extract to production** | [extraction_guide/](extraction_guide/) |
| **Check current status** | [STATUS.md](STATUS.md) |
| **Examine prototype code** | [prototype/](prototype/) (~1300 LOC) |

## Directory Structure

```
foundations/         - Core design principles (stable, foundational)
prototype/           - Exploratory code (reference only, not production)
experiments_archive/ - Timestamped experimental runs with results
findings/            - Extraction-ready validated/failed patterns
extraction_guide/    - How to reimplement for production
archive/             - Historical artifacts (bug reports, old docs)
tests/               - Organized test suite (smoke, integration, unit, debug)
analysis/            - Analysis scripts
tasks/               - Task definition files (evaluation queries)
seed/                - Bootstrap data (strategies, constraints)
results/             - Raw outputs (gitignored)
```

## RLM v2 Design Principles

From [foundations/rlm_notes.md](foundations/rlm_notes.md):

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

- **prototype/**: Exploratory code (~1300 LOC) - tests hypotheses, validates patterns
- **experiments_archive/**: Timestamped runs with design + results + findings
- **findings/**: Extraction-ready documentation of what worked/failed

### Future Phase: Engineering & Production

Future Claude will:
1. Read `findings/validated_patterns/` → know what to build
2. Read `findings/failed_approaches/` → avoid repeat mistakes
3. Follow `extraction_guide/README.md` → systematic extraction protocol
4. **Reimplement cleanly** (not refactor prototype code)

## Recent Work (Last 3 Commits)

- 98f1d17: Fix 3 critical S3 bugs + LM-as-judge evaluation
- ebf213d: Add S3 prompt perturbation + trajectory diversity metrics
- 0d8563e: Add smoke test report for stochastic evaluation

## Key Files (Read These First)

### For Newcomers
1. **THIS FILE** - Entry point
2. **[GETTING_STARTED.md](GETTING_STARTED.md)** - Practical quick-start guide
3. **[foundations/IMPLEMENTATION_PLAN.md](foundations/IMPLEMENTATION_PLAN.md)** - Architecture (~1320 lines)
4. **[foundations/rlm_notes.md](foundations/rlm_notes.md)** - RLM v2 principles (~137 lines)
5. **[STATUS.md](STATUS.md)** - Current state

### For Current Research
6. **[RESEARCH_TRAJECTORY.md](RESEARCH_TRAJECTORY.md)** - Research journey from git history
7. **[experiments_archive/README.md](experiments_archive/README.md)** - Experiment index
8. **[findings/README.md](findings/README.md)** - What we've learned

### For Future Engineering
8. **[extraction_guide/README.md](extraction_guide/README.md)** - How to extract
9. **[findings/validated_patterns/](findings/validated_patterns/)** - Proven approaches

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

1. **Progressive disclosure**: Start here → [GETTING_STARTED.md](GETTING_STARTED.md) → foundations → specific area
2. **Timestamped experiments**: Each in `experiments_archive/YYYY-MM-DD_name/` with single `EXPERIMENT.md`
3. **Findings as you go**: Update `findings/` as experiments complete
4. **Prototype is throwaway**: Code in `prototype/` is for reference, not refactoring
5. **Git history preserved**: All moves used `git mv`, can trace origins
6. **Session handoff**: Update [WORK_LOG.md](WORK_LOG.md) and [STATUS.md](STATUS.md) at end of each session

## Questions?

- **"How do I get started?"** → [GETTING_STARTED.md](GETTING_STARTED.md)
- **"What's the current status?"** → [STATUS.md](STATUS.md)
- **"What's the research journey?"** → [RESEARCH_TRAJECTORY.md](RESEARCH_TRAJECTORY.md)
- **"What happened in recent sessions?"** → [WORK_LOG.md](WORK_LOG.md)
- **"What's the architecture?"** → [foundations/IMPLEMENTATION_PLAN.md](foundations/IMPLEMENTATION_PLAN.md)
- **"Why these design choices?"** → [foundations/rlm_notes.md](foundations/rlm_notes.md)
- **"What worked?"** → [findings/validated_patterns/](findings/validated_patterns/)
- **"How do I extract this?"** → [extraction_guide/README.md](extraction_guide/README.md)

---

**Last updated**: 2026-02-04
**Reorganization**: Completed (see REORGANIZATION_PLAN.md for details)
