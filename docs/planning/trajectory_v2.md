# Trajectory v2: Ontology Query Construction (DSPy RLM + SQLite ReasoningBank + Affordances)

**Last Updated:** 2026-01-21

**Current Status:** 🎯 **4 of 5 phases completed** (Phases A, B, C, E complete; Phase D planned)

This document supersedes `docs/planning/trajectory.md` as the active implementation trajectory.

Goal (unchanged): enable an agent to answer questions over RDF ontologies/knowledge graphs by **constructing and executing SPARQL** using **ontology affordances** (sense + meta-graph + SHACL examples) while staying faithful to the **RLM progressive disclosure** philosophy (handles-not-dumps).

What changes in v2:
- Adopt a **hybrid codebase**: nbdev notebooks remain for research/docs; stable runtime moves to hand-written modules (see `docs/design/hybrid-nbdev-runtime-refactor.md`). ✅ **Done**
- Prefer **DSPy RLM** for the execution loop where it helps (typed `SUBMIT`, structured trajectories, tool-surface), while keeping the core invariants from v1. ✅ **Done**
- Implement **SQLite-backed ReasoningBank** as the durable procedural memory store and add **git-shipped memory packs** (see `docs/design/reasoningbank-sqlite-architecture.md`). ✅ **Done**
- Add comprehensive observability with dual logging (JSONL + MLflow). ✅ **Done** (2026-01-21)

---

## Non-negotiable invariants to carry forward (from v1)

1) **Context externalization**
- Large context (graphs, results) stays in the REPL environment; the root model sees only bounded summaries and tool outputs.

2) **REPL-first discovery**
- The agent must explore before answering; bounded view functions are the default interface.

3) **Recursive delegation for semantics**
- Sub-LLM calls are used for meaning extraction over bounded blobs; the root orchestrates.

4) **Handles-not-dumps**
- SPARQL results and graphs are stored as handles; inspection happens via bounded views.

5) **Bounded iteration**
- Max iterations and call budgets are enforced; fallback behaviors are explicit.

---

## Sanity check: what v1 delivered that we keep

Implemented (keep; don’t regress):
- Ontology handles + `GraphMeta` scaffolding and bounded views (`rlm/ontology.py`).
- Dataset memory model with `mem`/`prov` graphs, provenance, cache invalidation (`rlm/dataset.py`).
- SPARQL result handles + bounded sampling/view patterns (`rlm/sparql_handles.py`, dataset `res_*` helpers).
- SHACL shape/query template indexing and bounded retrieval functions (`rlm/shacl_examples.py`).
- Procedural memory closed loop (retrieve→inject→run→judge→extract→store) in notebook form (`rlm/procedural_memory.py`).
- JSONL logging for iteration-level observability (`rlm/logger.py`).

Gaps discovered (must address in v2):
- Procedural memory retrieval depends on `rank-bm25` and is rebuilt per query; we want a lightweight/SQLite-backed retriever.
- Dataset snapshot `session_id` restoration is still incomplete per tests and docs (`rlm/dataset.py::load_snapshot`).
- No stable “query construction contract” output (e.g., `{sparql, answer, evidence}`) in the core API; v2 enforces this.
- No production-grade runtime surface (agents will churn notebooks). v2 moves runtime into a handwritten package.
- DSPy was intentionally deferred in v1; v2 integrates it while preserving invariants.

---

## v2 Trajectory (phased, with "done" criteria)

**Status Summary:**
- ✅ Phase A: Stable runtime surface — **COMPLETED**
- ✅ Phase B: DSPy RLM engine — **COMPLETED**
- ✅ Phase C: SQLite ReasoningBank — **COMPLETED**
- 🔄 Phase D: SHACL-driven query construction — **PLANNED**
- ✅ Phase E: Observability — **COMPLETED** (2026-01-21)

### Phase A — Establish a stable runtime surface (hybrid nbdev) ✅

**Status:** ✅ **COMPLETED**

**Goal:** move agent-facing code out of notebooks while keeping notebooks as documentation and experiment drivers.

Actions:
- Create `rlm_runtime/` (handwritten) for:
  - execution engines (DSPy RLM, optional legacy)
  - bounded tool surface wrappers
  - logging hooks and artifacts
  - CLI entrypoint

Done when:
- One notebook imports runtime functions and runs an end-to-end demo without re-implementing core logic in notebook cells.

References:
- `docs/design/hybrid-nbdev-runtime-refactor.md`

### Phase B — DSPy RLM engine with bounded tools + typed outputs ✅

**Status:** ✅ **COMPLETED**

**Goal:** use DSPy RLM's typed `SUBMIT` and structured trajectory to enforce a query-construction contract.

Actions:
- Implement a host `CodeInterpreter` adapter (tool-only mode).
- Provide a DSPy signature that *requires*:
  - `sparql: str` (exact executed query)
  - `answer: str` (grounded)
  - `evidence: dict` (rows/URIs/handle summaries)
- Provide bounded tools:
  - ontology: `search_entity`, `describe_entity`, `probe_relationships`
  - SPARQL local execution: bounded SELECT with LIMIT injection
  - result inspection: `res_head`/`res_sample` equivalents

Done when:
- A local ontology task (e.g., PROV) returns `{sparql, answer, evidence}` via `SUBMIT` and the evidence is sufficient to justify the answer.

We already validated feasibility with the PoC scripts:
- `examples/dspy_rlm_quick_experiment.py`
- `examples/dspy_sparql_query_poc.py`

### Phase C — ReasoningBank v2: SQLite-backed procedural memory + packs ✅

**Status:** ✅ **COMPLETED**

**Goal:** make procedural memory durable, inspectable, and easy to curate/share.

Actions:
- Implement SQLite schema + FTS5 retrieval (fallback if needed).
- Store: trajectories, judgments, extracted memories, memory_usage (what was injected).
- Add memory pack import/export (JSONL with stable IDs).
- Add curriculum runner that generates trajectories and exports packs.

Done when:
- You can run a small curriculum against `ontology/` files, then re-run and observe improved convergence (fewer iterations/false starts) due to retrieved memories.

References:
- `docs/design/reasoningbank-sqlite-architecture.md`

### Phase D — SHACL-driven query construction (example → adapt → run)

**Goal:** make SHACL examples a first-class affordance for query construction.

Actions:
- Expose SHACL query index and shape index as bounded tools in the DSPy RLM environment:
  - `search_queries`, `get_query_text`, `describe_query`
  - `search_shapes`, `describe_shape`, `shape_constraints`
- Add output requirements:
  - include `template_uri` (if a template was used) in `evidence`
  - include shape URIs used (if constraints guided query)

Done when:
- On a SHACL example corpus (e.g., UniProt examples), the agent retrieves a relevant template by keyword, adapts it, executes it (or a local surrogate), and returns grounded results in the typed output contract.

### Phase E — Observability and deployment interface (subagent/tool) ✅

**Status:** ✅ **COMPLETED** (2026-01-21)

**Goal:** allow Codex/Claude Code to call a stable tool and get artifacts for debugging.

**What was delivered:**

1. **Dual logging system:**
   - JSONL trajectory logs (`rlm_runtime/logging/trajectory_callback.py`)
   - Memory event logs (`rlm_runtime/logging/memory_callback.py`)
   - DSPy callback integration for LLM calls, module execution, tool usage

2. **MLflow integration** (`rlm_runtime/logging/mlflow_integration.py`):
   - Structured experiment tracking with parameters, metrics, tags
   - Artifact logging (trajectory JSONL, SPARQL queries, evidence JSON)
   - Programmatic querying via `mlflow.search_runs()`
   - Custom tracking URIs for isolated experiments
   - Graceful degradation (warnings on failure, never crashes)

3. **Structured output contract:**
   - `DSPyRLMResult` with `answer`, `sparql`, `evidence`, `trajectory`, `iteration_count`, `converged`
   - Provenance tracking with `run_id` and `trajectory_id`
   - All runs stored in memory backend with full artifacts

4. **API surface:**
   - `run_dspy_rlm()` in `rlm_runtime/engine/dspy_rlm.py` provides full programmatic access
   - Returns structured `DSPyRLMResult` with all required fields
   - Logs to JSONL and/or MLflow based on configuration

**Done criteria satisfied:**
- ✅ Structured JSON output (`DSPyRLMResult` dataclass)
- ✅ Reproducible logs (JSONL + MLflow artifacts)
- ✅ DB artifacts (SQLite memory backend + MLflow tracking database)
- ✅ Tool usage tracking (DSPy callbacks + memory event logger)
- ✅ Memory usage tracking (retrieval, extraction, judgment logged)
- ✅ Query execution summaries (metrics + artifacts in MLflow)

**Future enhancements (optional):**
- CLI wrapper for shell/subagent invocation (could use `rlm_runtime/cli.py`)
- Analysis commands (`mlflow search`, `mlflow export`)

**References:**
- Implementation: `rlm_runtime/logging/mlflow_integration.py`, `rlm_runtime/engine/dspy_rlm.py`
- Tests: `tests/live/test_logging.py` (10/10 passing)
- Documentation: See "Observability and Experiment Tracking" in `CLAUDE.md`
- Design: `docs/design/mlflow-integration-analysis.md`, `docs/design/mlflow-implementation-complete.md`

---

## Evaluation harness (carry forward, strengthen)

We keep the v1 “small, local, repeatable” philosophy but update the metrics:
- Convergence: iterations to `SUBMIT` / time / sub-LLM calls.
- Grounding: evidence completeness (rows/URIs present).
- Affordance compliance: uses `search_entity` before hardcoding; uses SHACL templates when available; uses bounded SPARQL patterns.
- Memory value: delta in iterations/false starts with/without retrieved memories.

Minimum test scenarios:
- PROV (local graph):
  - “What is Activity?” (entity resolution + describe)
  - “List properties with domain Activity” (SPARQL construction + LIMIT + evidence)
- Dataset memory:
  - add/query/prov + snapshot restore correctness (including session_id restoration)
- SHACL examples:
  - find template by keyword, adapt, and execute bounded query

---

## Migration checklist (v1 → v2)

This is a practical checklist to migrate from the current nbdev-generated implementation to the v2 hybrid runtime approach without losing capabilities.

### A) Decide the “runtime source of truth”

- [ ] Create `rlm_runtime/` as the handwritten runtime package (see `docs/design/hybrid-nbdev-runtime-refactor.md`).
- [ ] Treat `nbs/*.ipynb` as docs/experiments that **import** runtime code; avoid re-implementing runtime logic in notebooks.
- [ ] Keep `rlm/*.py` (nbdev-generated) stable during transition; optionally convert key modules into thin wrappers later.

### B) Classify existing modules: keep / wrap / migrate

**Keep (pure affordance primitives; minimal LLM coupling):**
- [ ] `rlm/ontology.py` (GraphMeta + bounded view functions) as canonical, or migrate into `rlm_runtime/ontology/` if we want handwritten control.
- [ ] `rlm/dataset.py` (DatasetMeta + mem/prov/work + snapshots) as canonical, or migrate into `rlm_runtime/ontology/`.
- [ ] `rlm/sparql_handles.py` (SPARQLResultHandle + sparql_local/query) as canonical, or migrate into `rlm_runtime/sparql/`.
- [ ] `rlm/shacl_examples.py` (QueryIndex/SHACLIndex + retrieval helpers) as canonical, or migrate into `rlm_runtime/ontology/`.

**Wrap (LLM/backend-coupled; will change under DSPy):**
- [ ] `rlm/core.py` (claudette-backed RLM loop + llm_query utilities) should become either:
  - a legacy engine wrapper, or
  - a compatibility layer around the v2 runtime engine.
- [ ] `rlm/logger.py` should gain a DSPy-trajectory adapter (or be replaced by `rlm_runtime/logging/`).

**Migrate (ReasoningBank storage/retrieval; new SQLite core):**
- [ ] `rlm/procedural_memory.py` logic should move into `rlm_runtime/memory/` with SQLite as the source of truth.
- [ ] Replace retrieval (`rank-bm25`) with SQLite FTS5 BM25 + fallback.
- [ ] Add pack import/export (JSONL) and curriculum runner under `rlm_runtime/memory/`.

### C) Enforce the query-construction output contract

- [ ] Define the v2 “done format” for every run: `{sparql, answer, evidence}`.
- [ ] Implement as a DSPy signature and require termination via `SUBMIT(...)` in the DSPy RLM engine.
- [ ] Ensure evidence includes at least:
  - executed query text,
  - bounded result rows/samples,
  - URIs used (resolved entities, key predicates).

### D) Fix known v1 correctness gaps before/while migrating

- [ ] Fix dataset snapshot `session_id` restoration in `rlm/dataset.py::load_snapshot` (tests currently flag this).
- [ ] Ensure all tool outputs remain bounded (clamp limits; avoid dumping graphs/results).

### E) Provide a stable “subagent/tool” interface

- [ ] Add a CLI entrypoint (runtime) that returns structured JSON:
  - `answer`, `sparql`, `evidence`, `run_id`, `trajectory_id`, artifact paths.
- [ ] Persist observability artifacts:
  - JSONL trajectory logs,
  - SQLite rows for trajectories, memory usage, and extracted memories.

---

## References (design documents)

- DSPy migration system analysis: `docs/design/dspy-migration-system-analysis.md`
- Claudette→DSPy details + interpreter adapter: `docs/design/claudette-to-dspy-migration.md`
- SQLite ReasoningBank architecture: `docs/design/reasoningbank-sqlite-architecture.md`
- Ontology query construction requirements: `docs/design/ontology-query-construction-with-rlm-reasoningbank-dspy.md`
- Hybrid nbdev/runtime refactor: `docs/design/hybrid-nbdev-runtime-refactor.md`
