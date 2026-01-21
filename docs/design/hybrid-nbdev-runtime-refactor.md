# Hybrid Development Model: nbdev Notebooks for Research + Handwritten Runtime for Agents

This is a sanity-check and implementation trajectory for migrating from a notebook-generated (nbdev) codebase to a **hybrid** model:

- **Keep nbdev notebooks** for research, documentation, and interactive experiments.
- **Move “production/runtime” code** (what an SWE agent should read/modify) into a small set of handwritten Python modules, minimizing token waste and reducing churn from notebook diffs.

This plan is designed to support the features discussed in this dialog:
- DSPy RLM + typed `SUBMIT` outputs
- SQLite-backed ReasoningBank (procedural memory) + git-shipped memory packs
- Ontology affordances (sense + GraphMeta + SHACL example retrieval) driving SPARQL query construction
- Observability/trajectories (JSONL logs + DB rows)
- Eventual “agent tool/subagent” interface (CLI returning structured JSON)

---

## 1) Why hybrid (what we’re optimizing)

### 1.1 Keep what nbdev is great at
- Literate research, narrative + code + outputs
- Reproducible experiments (curricula runs, ontology comparisons)
- Documentation generation (`nbdev_docs`)

### 1.2 Avoid what’s costly for coding agents
- Notebooks are large, noisy, and expensive to “read” for LLM coding agents.
- Small code changes can cause large notebook diffs/metadata churn.
- Generated modules (`rlm/*.py`) are not ideal to hand-edit or refactor.

**Target outcome:** notebooks remain the *explanatory layer*; runtime code becomes the *authoritative implementation layer*.

---

## 2) Proposed repo structure (minimal disruption)

Add a new handwritten runtime package alongside nbdev-generated `rlm/`:

```
rlm_runtime/                 # handwritten “production” code (new)
  engine/                    # RLM execution engines (DSPy RLM + optional legacy)
  memory/                    # SQLite ReasoningBank store + pack import/export
  ontology/                  # affordance surface (sense, GraphMeta wrappers, SHACL helpers)
  sparql/                    # bounded SPARQL execution + result handles/views
  logging/                   # JSONL + DB event hooks (observability)
  cli.py                     # tool/subagent entrypoint (structured JSON)

nbs/                         # notebooks remain (research + docs + examples)
  ...                        # updated to import rlm_runtime

rlm/                         # existing nbdev-generated library (kept initially)
```

### Why not just “stop generating rlm/*.py”?
Because nbdev expects a `lib_path` and will keep exporting. We can keep the existing `rlm/` package stable while moving core logic into `rlm_runtime/`, then gradually:
- make `rlm/*.py` thin wrappers/re-exports to runtime (optional), or
- leave `rlm/` as the “research API” and move deployments to `rlm_runtime/`.

Either way: **SWE agents work in `rlm_runtime/`**, notebooks demonstrate usage.

---

## 3) What moves to handwritten runtime vs stays in notebooks

### 3.1 Handwritten runtime (high leverage / stable interfaces)

These are the pieces we want agents to modify safely and efficiently:

1) **DSPy integration**
   - host `CodeInterpreter` adapter (tool-only execution mode)
   - DSPy RLM engine wrapper (selectable model, sub-LM, budgets)
   - typed signatures for query construction (`sparql`, `answer`, `evidence`)

2) **ReasoningBank memory service**
   - SQLite store schema + migrations
   - retrieval (FTS5 bm25 + fallback)
   - memory loop hooks (usage logging, trajectory persistence)
   - memory pack import/export (JSONL) with stable IDs

3) **Observability**
   - structured run IDs / trajectory IDs
   - JSONL logs for trajectories (DSPy REPL history or legacy RLMIteration)
   - DB audit rows: what memories were injected, what tools were used, etc.

4) **Tool/subagent interface**
   - CLI that returns structured JSON for: answer + artifacts + queries + evidence
   - “curriculum runner” CLI for training + export packs

These are stable “product surface” concerns—better in regular `.py` files.

### 3.2 Notebooks (research + docs + demonstrations)

Notebooks should focus on:
- Explaining affordances and why they work
- Showing example runs on `ontology/` fixtures
- Comparing engines (claudette RLM vs DSPy RLM)
- Demonstrating memory effects (iterations reduction, failure lessons)
- Rendering documentation outputs (graphs, tables, qualitative trajectories)

But notebooks should *import* runtime functions rather than implement them.

---

## 4) Migration trajectory (sensible, incremental)

### Phase 0 — Freeze the public “capabilities”
Deliverable: an explicit list of required capabilities and output contracts.
- “Query construction engine must output `{sparql, answer, evidence}`”
- “ReasoningBank must support: retrieve/inject/judge/extract/store”
- “SHACL examples must support: search_templates → get_text → adapt”

### Phase 1 — Introduce `rlm_runtime/` without breaking anything
Deliverable: new runtime package coexists with current `rlm/`.
- Start with minimal modules:
  - `rlm_runtime/engine/dspy_rlm.py` (wraps DSPy RLM)
  - `rlm_runtime/engine/interpreter.py` (host CodeInterpreter)
  - `rlm_runtime/cli.py` (single `run` command)
- Keep notebooks and tests unchanged initially.

### Phase 2 — Move the PoCs into runtime and add a stable API
Deliverable: the PoCs become first-class runtime demos.
- Migrate logic from:
  - `examples/dspy_rlm_quick_experiment.py`
  - `examples/dspy_sparql_query_poc.py`
- Expose a runtime API:
  - `run_query_construction(ontology_path, query, ...) -> structured result`
- Keep notebooks calling this API.

### Phase 3 — Implement SQLite ReasoningBank store in runtime
Deliverable: real persistence + retrieval + pack system.
- Add:
  - `rlm_runtime/memory/sqlite_store.py`
  - `rlm_runtime/memory/packs.py`
  - `rlm_runtime/memory/retrieval.py` (FTS5 + fallback)
- Add a tiny adapter so `rlm/procedural_memory.py` can optionally write to SQLite (or keep it separate and migrate callers).

### Phase 4 — “Affordance-first” tool surface (ontology + SHACL + results)
Deliverable: a coherent set of bounded tools with predictable signatures.
- Wrap:
  - ontology views (`search_entity`, `describe_entity`, dom/range helpers)
  - SHACL example retrieval (`search_queries`, `get_query_text`, `describe_shape`)
  - SPARQL execution + result viewing
- Ensure docstrings are crisp because DSPy will surface them to the model.
- Enforce bounds by design (limit parameters clamped).

### Phase 5 — Typed signatures and curricula
Deliverable: enforce structured outputs and train memory packs.
- DSPy signatures:
  - `OntologySense` (typed sense card)
  - `QueryConstruction` outputs `{sparql, answer, evidence}`
  - optional “plan → execute → verify” split
- Curriculum runner:
  - `train` runs tasks on sample ontologies and stores trajectories/memories
  - `export-pack` writes curated JSONL packs

### Phase 6 — Deprecate notebook-generated implementations where appropriate
Deliverable: notebooks become docs-only; runtime is authoritative.
- Update notebooks to remove large code cells and keep only:
  - imports, small glue, plots/tables, outputs, narrative.
- Keep `rlm/` stable for compatibility, or turn it into thin wrappers over `rlm_runtime` (optional).

---

## 5) Testing strategy for the hybrid model

### 5.1 Unit tests (offline)
- SQLite schema + import/export pack roundtrips
- stable ID determinism
- bounded tool output sizes
- SPARQL LIMIT injection + result schema

### 5.2 Integration tests (mostly offline)
- Use local ontologies in `ontology/`:
  - PROV, SIO, and one SHACL-rich ontology
- Stub/mocking path:
  - For deterministic tests, mock LM calls (DSPy LM stub or adapter) and ensure tool calls + outputs remain structured.

### 5.3 Live tests (optional)
- Mark with `pytest.mark.live` as today.
- Validate that DSPy RLM returns structured outputs and uses bounded tools.

---

## 6) Practical nbdev guidance for the hybrid approach

To keep notebooks valuable but cheap:
- Keep notebooks short; push implementation into `rlm_runtime/`.
- Use `#| eval: false` for long-running/live cells.
- Create “docs notebooks” that:
  - import runtime modules,
  - run a few minimal examples,
  - display outputs/plots,
  - and link to generated docs.

This preserves the research-documentation workflow without forcing coding agents to parse notebook internals.

---

## 7) Decision points to resolve early

1) Do we keep `rlm/` as the package name for deployment, or deploy `rlm_runtime/` as a separate package?
2) Do we standardize on DSPy RLM as default engine, or keep claudette loop as default with DSPy optional?
3) Do we require SQLite FTS5, or support fallback retrieval only?
4) How strict should typed outputs be (single `answer` vs `{sparql, answer, evidence}` always)?

---

## 8) Recommended “first refactor” (smallest useful cut)

Start by creating `rlm_runtime/engine/` and moving the DSPy RLM + interpreter PoC there, then update one notebook to call it.

That gives us:
- a stable runtime surface,
- minimal notebook churn,
- a clear place to implement the SQLite ReasoningBank next,
- and a path toward a tool/subagent CLI.

