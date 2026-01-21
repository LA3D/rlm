# DSPy Migration: System-Wide Impact Analysis (RLM + Ontologies + ReasoningBank)

This document analyzes the modules currently implemented in this repo, how they fit together today (claudette-backed RLM + ontology REPL tooling + procedural memory), and what would need to change to migrate to DSPy—especially if we want to use **`dspy.RLM`** and DSPy’s **typed `SUBMIT`** + tool surface to add stronger guarantees around structured outputs and controlled tool use.

This builds on:
- `docs/planning/trajectory.md` (RLM invariants, handles-not-dumps)
- `docs/design/claudette-to-dspy-migration.md` (DSPy RLM + interpreter adapter sketch)
- `docs/design/reasoningbank-sqlite-architecture.md` (SQLite-backed procedural memory + packs)

---

## 1) High-level Architecture (Current)

**Core loop (RLM):**
- `nbs/00_core.ipynb` → `rlm/core.py`
- Root LM emits ```repl``` blocks; host executes them in a Python namespace (`ns`).
- Sub-LLM calls via `llm_query` / `llm_query_batched` (claudette).
- Termination by parsing `FINAL(...)` / `FINAL_VAR(...)`.

**Ontology exploration (handles + bounded views):**
- `nbs/01_ontology.ipynb` → `rlm/ontology.py`
- `GraphMeta` provides cached indexes (labels, hierarchy, domains/ranges).
- Bounded view functions: `search_entity`, `describe_entity`, `probe_relationships`, etc.
- Sense building includes one LLM synthesis call (`build_sense`, and structured sense functions).

**Dataset “fact memory” (RDF Dataset):**
- `nbs/02_dataset_memory.ipynb` → `rlm/dataset.py`
- Named graphs (`mem`, `prov`, `work/*`), bounded query helpers, snapshot/load.

**SPARQL handles (bounded result access):**
- `nbs/03_sparql_handles.ipynb` → `rlm/sparql_handles.py`
- Handles to avoid materializing huge result sets.

**SHACL + query template retrieval:**
- `nbs/06_shacl_examples.ipynb` → `rlm/shacl_examples.py`
- Index SHACL shapes and `sh:SPARQLExecutable` templates for “retrieve → adapt → run”.

**Procedural memory (ReasoningBank-style):**
- `nbs/05_procedural_memory.ipynb` → `rlm/procedural_memory.py`
- Closed-loop: retrieve → inject → run → judge → extract → store.
- Currently: in-memory/JSON store + BM25-like retrieval (to be replaced).

**Logging (observability):**
- `nbs/03_logger.ipynb` → `rlm/logger.py`
- JSONL run logs + Rich console display.

---

## 2) Why DSPy is Interesting Here (What Guarantees We Actually Get)

### 2.1 Typed termination via `SUBMIT`

DSPy RLM terminates by calling `SUBMIT(field1=..., field2=...)` **inside the REPL**, returning `FinalOutput` that DSPy:
- validates for missing required fields,
- parses/types fields according to the signature,
- returns structured `Prediction(...)`.

This is a meaningful “structured output guarantee” vs `FINAL(...)` text parsing.

### 2.2 Tool surface with validation + discoverability

DSPy RLM:
- validates tool names (must be Python identifiers; reserved names blocked),
- includes tool docstrings and signatures in instructions,
- exposes `llm_query` + `llm_query_batched` with a call budget.

This can make our bounded ontology tools more discoverable and reduce “random REPL spelunking”.

### 2.3 Structured trajectories

DSPy returns a structured `trajectory` (REPL history entries: reasoning/code/output).
That helps:
- logging/observability,
- memory extraction (better artifacts),
- curriculum development.

### 2.4 What DSPy does *not* guarantee

DSPy cannot guarantee the model won’t do “bad” things unless we control the interpreter/tool surface:
- If code execution can access raw rdflib graphs, the model can still dump them.
- If tools return unbounded outputs, we violate handles-not-dumps.

So the guarantee is: **typed outputs and a structured execution loop**, *not* safety by default.

---

## 3) Module-by-Module Migration Impact

Below is the inventory of modules and how a DSPy migration affects each.

### 3.1 `rlm/core.py` (RLM loop + LLM backend)

Current:
- hard dependency on `claudette.Chat`
- `llm_query`/`llm_query_batched` are claudette-based utilities
- `rlm_run` parses `FINAL(...)`

DSPy migration options:
- **Keep our loop, swap backend**: introduce `LLMBackend` abstraction; implement `ClaudetteBackend` + `DSPyBackend`.
- **Replace loop with `dspy.RLM`**: remove `rlm_run` as the root driver (or keep as legacy wrapper), and use DSPy signatures + `SUBMIT`.

Custom work required if using `dspy.RLM`:
- A host-side `CodeInterpreter` (see §4) so the REPL can use rdflib handles.
- A compatibility wrapper that returns `(answer, iterations, ns)` for existing code/tests, or a deliberate API break.

### 3.2 `rlm/ontology.py` (GraphMeta + bounded views + sense)

Current:
- Excellent fit for a tool-based RLM: most functions are bounded summaries.
- One LLM call inside `build_sense(...)` (`rlm/ontology.py#L928`) via `rlm.core.llm_query`.

DSPy opportunities:
- Expose bounded functions as DSPy RLM tools (docstrings become part of the instruction set).
- Define an **ontology sense signature** to make sense outputs structured (see §5).

Migration tasks:
- Replace `build_sense`/structured sense LLM call with DSPy `Predict` (typed output), *or* route it through a backend interface so it can be either claudette or DSPy.
- Ensure no unbounded outputs leak through tools (tight limits).

### 3.3 `rlm/dataset.py` (RDF Dataset memory)

Current:
- Pure Python; no LLM calls.
- Already “handle-first”: `DatasetMeta` stores graphs; helpers return bounded results.

DSPy impact:
- Minimal. These functions become tools the DSPy RLM can call.
- If we want typed outputs, we can keep returning serializable dict/list types (ideal for DSPy tool calls).

Key consideration:
- Avoid passing `DatasetMeta` as an input variable to `dspy.RLM` (DSPy will try to serialize/preview it). Prefer closure tools.

### 3.4 `rlm/sparql_handles.py` (result handles)

Current:
- Pure Python; no LLM calls.
- Designed for progressive disclosure.

DSPy impact:
- Minimal; these are tool candidates.
- Helps provide “result handle” primitives that encourage the model not to dump large tables.

### 3.5 `rlm/shacl_examples.py` (SHACL + query templates)

Current:
- Pure Python; no LLM calls.
- Builds indices and returns bounded summaries.

DSPy impact:
- Minimal; good tools for an RLM to call.
- A DSPy signature could also be used to “adapt a template query” with structured placeholders, but that is optional.

### 3.6 `rlm/procedural_memory.py` (ReasoningBank loop)

Current:
- The extraction pipeline already matches the paper fairly closely:
  - `judge_trajectory()` and `extract_memories()` are LLM-based and return strict JSON.
- Retrieval is lexical and will be replaced (stdlib BM25 / SQLite FTS).

DSPy impact:
- High leverage:
  - convert judge/extractor to DSPy predictors with typed outputs (less JSON parsing fragility),
  - reuse DSPy’s evaluation/judge mechanisms,
  - store structured trajectories from DSPy RLM directly.

Migration tasks:
- Replace `llm_query` calls inside judge/extractor with DSPy modules OR a backend interface.
- Update the “trajectory artifact” builder to accept either:
  - our `RLMIteration` objects, or
  - DSPy REPL history entries.
- Adopt SQLite storage (per `docs/design/reasoningbank-sqlite-architecture.md`).

### 3.7 `rlm/reasoning_bank.py` (ontology-specific recipes + injection)

Current:
- Context injection helper (`inject_context`) and `rlm_run_enhanced`.

DSPy impact:
- If we move to DSPy RLM, context injection still exists, but:
  - the “context” becomes an **input field** (e.g., `context: str`) in a DSPy signature.
  - recipe/memory injection becomes systematic composition of inputs (or a pre-processing step before calling DSPy).

Migration tasks:
- Decide whether “recipes” remain a text injection layer (fine), or become structured tool guidance (DSPy tool docs may reduce the need).

### 3.8 `rlm/logger.py` (JSONL + Rich)

Current:
- Logs our `RLMIteration` objects.

DSPy impact:
- If we switch to DSPy RLM, we need a logging adapter:
  - DSPy REPL history entry → JSONL “iteration” record
  - include tool calls / errors / SUBMIT payload

Migration tasks:
- Implement a second logger mode (or converter) that takes DSPy trajectories.
- Ensure trajectory IDs/run IDs align with SQLite store.

---

## 4) The Critical Custom Piece: DSPy `CodeInterpreter` Adapter

To run DSPy RLM over rdflib handles, we need a host-side interpreter that:
- executes Python code in-process with persistent state across iterations,
- injects DSPy’s tools (including llm_query and our ontology tools),
- provides `SUBMIT(...)` to end execution with structured outputs.

See `docs/design/claudette-to-dspy-migration.md` for a concrete outline.

Two recommended patterns for ontology work:

1) **Tool-only access (preferred)**
   - Only pass small serializable inputs to DSPy (`query`, `sense_context`, `base_context`).
   - Keep rdflib `Graph` / `GraphMeta` in host memory and expose bounded views as tools that close over them.
   - Prevents accidental “dump the graph” behaviors.

2) **Shared-namespace access (fast PoC)**
   - Expose the full existing namespace to the interpreter.
   - Higher risk of violating handles-not-dumps unless strictly instructed.

---

## 5) “Ontology Sense Signature” (Typed Inputs/Outputs)

If we adopt DSPy, we can represent “sense” as either:

### 5.1 A small string input (lowest friction)

- Keep `sense_context: str` as a bounded injected string (what we do today).
- Benefits from `SUBMIT` typed outputs without changing sense generation.

### 5.2 A structured sense card model (recommended if we want stronger guarantees)

Define a Pydantic model (or simple dict schema) for the sense card:
- `ontology_id`, `triple_count`, `class_count`, `property_count`
- `label_predicates`, `description_predicates`
- `key_classes[]` / `key_properties[]` (bounded)
- `available_indexes` summary

Then define DSPy signatures like:
- `SenseBuilder(stats, annotation_predicates, roots, top_props, ...) -> sense_card`
- `OntologyAnswerer(query, sense_card, base_context) -> answer`

This helps:
- enforce boundedness and consistent fields,
- standardize what the root loop can rely on,
- improve tool selection by conditioning on explicit “available_indexes”.

Important: avoid passing huge objects (e.g., raw GraphMeta) as signature inputs; keep them as tools/closures.

---

## 6) Quick Experiment Proposal (Feasibility)

Before committing to a full migration, run a proof-of-concept:

1. Implement the host `CodeInterpreter` adapter (tool-only mode).
2. Load a small ontology (e.g., `ontology/prov.ttl`) in host Python.
3. Provide tools:
   - `search_entity(label, limit)`
   - `describe_entity(uri, limit)`
   - optionally `probe_relationships(uri, limit)`
4. Run DSPy RLM with signature: `"query, context -> answer"`, where `context` includes a minimal sense card + base summary.
5. Verify:
   - the model iterates and prints outputs,
   - it terminates with `SUBMIT(answer=...)`,
   - the trajectory can be logged and converted into a bounded artifact for memory extraction.

Success = we can drive progressive disclosure with DSPy orchestration without losing the handle discipline.

---

## 7) Recommended Migration Sequence (Minimize Risk)

1) **Backend abstraction (no behavior change):**
   - Introduce an LLM backend interface; keep claudette as default.

2) **DSPy judge/extractor first:**
   - Move `judge_trajectory` and `extract_memories` to DSPy predictors (typed outputs).

3) **SQLite store + packs:**
   - Implement the SQLite-backed ReasoningBank store and memory pack import/export.

4) **DSPy RLM PoC (tool-only interpreter):**
   - Add `dspy.RLM` as an optional execution engine behind a flag.
   - Keep `rlm_run` as the stable public API for now (wrap DSPy prediction).

5) **Evaluate via curricula across sample ontologies:**
   - Compare: success rate, iterations, memory quality, logging artifacts.

If DSPy RLM is consistently better (or equal) and stable, we can switch the default engine later.

