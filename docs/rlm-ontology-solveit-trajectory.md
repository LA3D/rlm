# RLM + Ontologies (rdflib) in Solveit: Exploratory Trajectory

This document is the source of truth for implementing an `rlmpaper`-faithful Recursive Language Model (RLM) workflow in this repo, extended to support ontology (RDF/OWL/SHACL) exploration and SPARQL result management in a REPL using `rdflib`, developed via nbdev (exploratory + literate programming) on the Solveit platform.

## Problem Statement

We want an LLM to answer questions that require interacting with:
- A local RDF graph (ontologies in `ontology/`), including OWL axioms and optionally SHACL shapes/examples.
- SPARQL query results (local graph queries and, optionally, remote endpoints).
- A mutable “agent memory” store that can be updated over time, using RDF **Dataset** constructs (named graphs / quads) in newer `rdflib`.

But we want to do this *the RLM way*:
- The large context (graph, results) lives in the execution environment (REPL), not the root LLM context.
- The root LLM iteratively emits small REPL actions and delegates heavy reading/summarization to sub-LLMs via `llm_query` / `llm_query_batched`.
- The system converges by building buffers in the REPL and returning `FINAL(...)` or `FINAL_VAR(...)`.

## Non-Negotiable RLM Invariants (from `rlmpaper/`)

Treat these as architectural contracts; don’t “simplify” them away:

1. **Context externalization**
   - The root model does *not* receive ontology content directly.
   - It receives only metadata (type, lengths, chunking) and learns content via REPL interactions.

2. **REPL-first discovery**
   - The model must be forced to explore before answering (first-iteration safeguard).
   - Outputs are truncated; the model should respond by doing *more REPL work* or using sub-LLMs, not guessing.

3. **Recursive delegation for semantics**
   - Use `llm_query` / `llm_query_batched` inside the REPL for large blob analysis (summarizing, extracting, comparing).
   - The root model should see summaries, not raw bulk data.

4. **Iteration protocol**
   - The root model emits ```repl``` blocks.
   - The loop executes code blocks, appends execution results to the next iteration’s prompt, and repeats until `FINAL(...)` or `FINAL_VAR(...)`.

5. **Fail-fast / bounded behavior**
   - Iterations are bounded (`max_iterations`).
   - If no final answer is produced, a “default answer” step synthesizes from history (but this should be a last resort).

## Why the Current Direction Feels Weak

These are common failure modes when extending RLM to graphs:

- **Re-implementing the loop**: building a new loop (or mixing with toolloops) makes it easy to drift away from `rlmpaper`’s exploration protocol and safety defaults.
- **“One big tool” SPARQL**: a single `sparql_query()` that returns large tables/graphs tends to create either (a) huge outputs the root model can’t read, or (b) overly truncated outputs that don’t support iterative refinement.
- **Missing “views” and “handles”**: graphs and SPARQL results need *bounded view operations* so the root model can progressively disclose information (counts, heads, grouping, sampling).

## Solveit + nbdev Development Approach

We will develop as a sequence of *literate experiments* that become stable exports.

### Workflow Rules (for the Solveit AI)

- Prefer **small REPL actions** and **stored buffers** over dumping large content into the chat.
- Every exported function should have a fast.ai-style docstring and predictable, minimal outputs.
- Outputs should be **summaries + handles**, not full datasets.
- Keep a tight loop: *explore → name → store → summarize → refine → finalize*.
- Treat architecture as an **explorable artifact**: capture decisions as you discover constraints (performance, serialization, query semantics), and update this doc as the system evolves.

### Answer.AI `dialoghelper`-Style Methodology (Tool Surface)

Solveit tool interfaces can only pass **serializable** values, so we adopt the `dialoghelper.inspecttools` convention:

- Tools accept **string arguments** (symbol names and dotted symbol paths), not live Python objects.
- Tools resolve symbols in the active namespace (REPL) and then operate on the resolved object.
- Tools store results back into the namespace (often as a named handle and/or `_last`) so subsequent tool calls can chain.
- Tools return **small, formatted summaries** suitable for progressive disclosure (never bulk dumps).

Concrete conventions to mirror from `dialoghelper.inspecttools`:
- **`resolve(sym)`** supports dotted paths and simple indexing like `name[0]`, and sets a global **`_last`** for chaining.
- Tools should work with the Solveit runtime’s “caller namespace” discovery pattern (frame-walking via `__msg_id`) rather than requiring explicit object passing.
- “Show, don’t dump”: prefer returning a short summary and keeping large objects in the REPL; use separate “view” tools for bounded slices.
- Use `add_msg(...)`-style note insertion only when you explicitly want content persisted into the dialog (e.g. `showsrc`), not as a default.
- Treat `run_code_interactive` as a last-resort, terminal tool call (when a capability truly can’t be provided via tools).

Implication for ontology/SPARQL work:
- “Handles” are not just a design convenience—they are the primary interface between the root model and large state.
- The meta-graph navigation layer should be built as REPL symbols that are easy to inspect via the existing inspecttools-style primitives (`symlen`, `symslice`, `symsearch`, `getval`, etc.).

### fast.ai Style Constraints (practical)

Use the fast.ai style guide as the default, with these project-specific emphases:
- Prefer short functions with strong names over complex abstractions.
- Prefer docstrings over inline comments.
- Prefer explicit return values that summarize what was stored (e.g. `"Stored 120 rows in 'res'"`).
- Prefer simple Python data structures (`dict`, `list`, dataclasses) that are easy to inspect and serialize.
- Use `**kwargs` only where it improves extensibility (e.g. backend params), not as a blanket.

## Design Decisions to Explore (Decision Log)

This project is intentionally exploratory/literate. The agent should be able to make and revise design decisions during development, but those decisions must be captured here so the system remains coherent.

For each decision:
- Record the choice and rationale (1–3 sentences).
- Record the alternatives considered.
- Record the "proof": which experiment(s) or evaluation scenario(s) demonstrated the constraint.

### Stage 1: Ontology Context Model (Completed 2026-01-17)

**Decision**: Ontologies are exposed to RLM as **handles + meta-graph scaffolding**, not as graph dumps.

**Implementation** (`nbs/01_ontology.ipynb`):
1. `load_ontology()` loads RDF into rdflib Graph and stores it in namespace as a handle
2. `GraphMeta` dataclass provides lazy-loaded navigation properties:
   - `namespaces` - prefix bindings
   - `classes` - sorted list of OWL/RDFS class URIs
   - `properties` - sorted list of property URIs
   - `labels` - URI → label mapping for search
   - `summary()` - bounded summary string
3. Bounded view functions (not methods) operate on GraphMeta:
   - `graph_stats(meta)` - summary statistics
   - `search_by_label(meta, search, limit=10)` - substring search with result limit
   - `describe_entity(meta, uri, limit=20)` - bounded entity description
4. `setup_ontology_context()` creates Graph + GraphMeta + bound helpers in namespace for RLM use

**Rationale**:
- Graph handle prevents root model from accessing raw triples directly
- Meta-graph properties are computed lazily and cached for efficiency
- Bounded view functions enforce progressive disclosure (no unbounded queries)
- Functions (not methods) follow fast.ai style and are easier to inject into REPL

**Alternatives considered**:
- GraphMeta as dict with bound methods → rejected (less inspectable, harder to serialize)
- Expose rdflib Graph directly → rejected (violates "handles not dumps" principle)
- Pre-compute all indexes at load time → rejected (wasteful for large ontologies)

**Proof**: Tested with PROV ontology (1,664 triples, 59 classes, 89 properties). RLM successfully used `search_by_label()` and `describe_entity()` to explore and answer "What is the Activity class?" without accessing raw graph. See `tests/test_ontology_rlm.py`.

### Dataset Memory Model (core exploratory area)

We intend to model “agent memory” using RDF Dataset constructs (named graphs / quads). The following decisions must be made explicitly during development:

1. **Dataset type and access pattern**
   - Options: `Dataset`, `ConjunctiveGraph`, dataset-backed store plugins.
   - Constraint to evaluate: query semantics, performance, ease of persisting/restoring, compatibility with named graphs.

2. **Named graph layout**
   - Proposed baseline:
     - `onto/<name>`: read-only imported ontologies
     - `mem`: mutable agent memory overlay
     - `prov`: provenance/audit for memory writes
     - `work/<task_id>`: scratch graphs for intermediate CONSTRUCT results
   - Constraint to evaluate: clarity for the root model and avoidance of accidental ontology mutation.

3. **Default graph semantics for SPARQL**
   - Options:
     - default graph is a specific graph (e.g. `mem`)
     - default graph is union of named graphs
     - require explicit `GRAPH` / `FROM NAMED` in all queries
   - Constraint to evaluate: whether the root model can reliably form correct queries under ambiguity.

4. **Update protocol**
   - Options:
     - only add/retract in `mem` (strict)
     - allow updates in `work/*` and promote to `mem` via explicit “commit”
   - Constraint to evaluate: safety, debuggability, and ability to roll back.

5. **Index/meta-graph invalidation**
   - Requirement: any mutation must invalidate or version the meta-graph navigation layer (labels, subclass adjacency, predicate frequencies, etc.).
   - Constraint to evaluate: incremental vs rebuild-on-demand vs hybrid.

6. **Persistence scope**
   - Options:
     - session-only (memory lives only as long as the agent process)
     - durable (snapshot `mem`/`prov` to TriG/N-Quads or an append-only log)
   - Constraint to evaluate: deployment needs and restart behavior.

### Procedural Memory (ReasoningBank-style)

We also want to explore a ReasoningBank-style **procedural memory** loop on top of RLM:
- RLM provides *environmental interaction* and progressive disclosure over large state.
- ReasoningBank provides *self-evolving procedural knowledge* distilled from trajectories (what worked, what failed, reusable strategies).

This is intentionally separate from RDF Dataset “fact memory”:
- Dataset memory stores domain facts as RDF quads.
- ReasoningBank stores reusable *methods* (query templates, debugging moves, exploration heuristics, safety checks).

Decisions to make explicitly:

1. **Memory item schema**
   - Baseline fields (from `ace-dspy/reasoningbank_dspy.ipynb`): `title`, `description`, `content`, `source_type` (success/failure), timestamps, embedding.
   - Constraint: keep items small enough to inject into the root prompt without violating RLM’s “no bulk context” discipline.

2. **Trajectory source and granularity**
   - Options:
     - use `rlmpaper` iteration logs directly (RLMIteration list: prompts, repl code blocks, outputs)
     - store a higher-level “semantic trajectory” (tool calls, key handles, query ids, final evidence)
   - Constraint: extraction quality and debuggability.

3. **Judge/extractor implementation**
   - Options:
     - sub-LLM prompts (`llm_query`) for judge + extractor (**default for experimentation**)
     - DSPy signatures/modules (defer; only if we later want training/teleprompting)
   - Constraint: must run inside Solveit experiments and in deployed agents without Solveit-specific dependencies.

   **Decision (experiment phase):** Use Answer.AI `claudette` via `llm_query` / `llm_query_batched`. Do not depend on DSPy.

4. **Retrieval mechanism**
   - Options:
     - embedding similarity (ReasoningBank paper-style)
     - lexical/regex retrieval (baseline for determinism)
     - hybrid (lexical prefilter + embedding rerank)
   - Constraint: reproducibility, dependency footprint, and offline testing.

5. **Injection point (how retrieved memories influence behavior)**
   - Options:
     - inject top-k memories into the root LM’s user prompt/system instruction (small, explicit)
     - keep memories in REPL and require the model to retrieve them via a tool (more “pure RLM”, but less reliable)
   - Constraint: whether retrieval reliably improves trajectories without encouraging premature answering.

6. **Persistence**
   - Options:
     - JSON + numpy (fast, simple; good for experimentation)
     - vector DB (FAISS/Qdrant/Chroma) (heavier; consider later)
     - represent memories in RDF (as named graph) with embeddings stored out-of-band
   - Constraint: deployment environment and the need for inspectable, auditable memory.

7. **Consolidation and growth management**
   - Options:
     - no consolidation (append-only, prune by recency/access count)
     - periodic deduplication via embedding clustering + LLM merge
     - hierarchical: group similar memories under a "meta-strategy" item
   - Constraint to evaluate: memory pool size vs retrieval quality, cost of consolidation passes, interpretability of merged items.
   - Implementation sketch:
     - Track memory access counts and timestamps.
     - Periodically (e.g., every N extractions) run a consolidation pass:
       1. Cluster memories by embedding similarity.
       2. For clusters with >3 similar items, use `llm_query` to merge into a more general strategy.
       3. Archive or delete subsumed items.

#### Claudette implementation hints (no DSPy)

Implement ReasoningBank operations as *structured sub-LLM calls* with strict I/O:

- **Trajectory artifact (bounded):**
  - Input to judge/extractor should be a compact representation, not the full raw transcript.
  - Prefer: task query + final answer + a small list of “key steps” (tool/REPL actions + 1–2 line outcomes) + a small “evidence” section (URIs/handles queried).
  - If the trajectory is too large, first run a sub-LLM to summarize the raw iteration log into this bounded artifact.

- **Judge prompt:**
  - Ask for a strict JSON object with `is_success: bool`, `reason: str`, and (optionally) `missing: [str]` listing what evidence is lacking.
  - Judge should be evidence-sensitive: “success” requires that the answer is supported by retrieved facts/handles, not just plausible text.

- **Extractor prompt:**
  - Ask for a strict JSON object matching your memory schema: `title`, `description`, `content`, `source_type`, plus optional `tags` and `applicability`.
  - Request **up to 3 memory items** per trajectory (not one monolithic item). Each item should capture a distinct, reusable insight. Fewer is fine if the trajectory doesn't yield multiple lessons.
  - `content` should be procedural (steps/checklist/templates), not a retelling of the run. The `content` field is stored as a string but may contain Markdown formatting (bullet lists, code blocks for query templates) for readability when injected into prompts.
  - For SPARQL/ontology work, encourage templated guidance: "when stuck, run X view; if result empty, broaden by Y; prefer GRAPH scoping; validate against labels/comments".

- **Retrieval (claudette-first baseline):**
  - Start without embeddings: lexical filter by keywords over `title/description/tags`, then use one `llm_query` reranker that sees only the candidate titles/descriptions.
  - Add embeddings later if needed for scale; keep JSON persistence regardless.

- **Injection discipline:**
  - Inject only the top-k memories' `title + 1–3 bullets` into the *next* run's prompt.
  - Prepend retrieved memories with an instruction: "Before taking action, briefly assess which of these prior strategies apply to the current task and which do not." This prevents blind pattern-matching and encourages selective application.
  - Never inject large `content` verbatim; treat `content` as REPL-resident and retrieve/browse it via handles if needed.

### Execution Topology (Solveit vs Deploy)

We will prototype in Solveit, but deploy “semantic agents” outside Solveit. Record decisions about runtime topology explicitly:

1. **RLM environment selection for deployment**
   - Options (from `rlmpaper`): `local`, `docker`, `modal`, `prime`.
   - Constraint to evaluate: whether in-memory RDF Dataset state can persist across iterations and/or requests without expensive serialization.

2. **Process lifetime**
   - Options:
     - per-request (fresh environment per `completion`)
     - long-lived agent (persistent environment across requests)
   - Constraint to evaluate: memory continuity vs isolation and resource control.

3. **Where ontologies live**
   - Options:
     - baked into image
     - mounted volume
     - fetched at startup (avoid unless you control network and pin versions)
   - Constraint to evaluate: reproducibility and startup latency.

## Trajectory (Exploratory Development Plan)

Each stage has a concrete “done” condition and produces notebook artifacts suitable for nbdev export.

### Stage 0 — Baseline: Use `rlmpaper` as the reference loop

**Goal:** Stop drifting from the paper by anchoring to `rlmpaper/rlm`.

Actions:
- Identify the minimal interface we rely on:
  - Environment provides `context`, `llm_query`, `llm_query_batched`, `FINAL_VAR`.
  - Parser finds ```repl``` blocks and `FINAL(...)` / `FINAL_VAR(...)`.
  - Prompt builder provides metadata-only system prompt + first-iteration safeguard.
- Treat anything else (custom parsing, custom prompts, extra tool frameworks) as optional and justified.

Done when:
- A small demo can run with `prompt=context` and produce an answer via REPL exploration, without introducing a second “RLM loop” implementation.

### Stage 1 — Define the Ontology “Context Model”

**Goal:** Decide what “context” means for ontology work in RLM.

We will support at least two modes:
1. **Graph context**: `context` is a file path (or a small dict of paths) and the REPL loads it into a graph handle.
2. **Results context**: `context` is a list/dict of “result handles” produced by previous steps.

Key principle:
- The *root model never gets a graph dump*. It gets a handle name (e.g. `ont`, `res_0`) and uses bounded view operations.

Done when:
- We can represent “loaded ontology” and “SPARQL results” as inspectable REPL symbols with stable names.

### Stage 1.5 — Dataset-Based Memory (Named Graphs / Quads)

**Goal:** Make the “agent memory” model explicit and testable using an RDF Dataset, while keeping the root model’s interface handle-based and bounded.

Minimum capabilities to demonstrate (in notebooks, then export):
- Load ontology graphs into named graph slots (`onto/<name>`) without mutating them.
- Maintain a mutable overlay named graph (`mem`) that can be updated (add/retract) and queried.
- Keep provenance of memory updates (`prov`) as data the agent can inspect (at least timestamp/source/reason).
- Provide bounded views over dataset contents (counts per graph, top predicates, sample triples per graph).

Decision checkpoints (must be recorded in the Decision Log above):
- Default graph semantics for queries.
- Which graphs the agent is allowed to write to.
- How meta-graph indexes are versioned/invalidated under mutation.

Done when:
- A trajectory can (a) add a small fact to `mem`, (b) query it back, (c) show provenance, and (d) demonstrate index invalidation/rebuild behavior without dumping large data.

### Stage 2.5 — Procedural Memory Loop (ReasoningBank × RLM)

**Goal:** Add a ReasoningBank-style closed loop *around* RLM completions to accumulate reusable procedural memories for ontology/SPARQL work.

Minimum capabilities to demonstrate (in notebooks, then export):
- After an RLM run, capture a trajectory artifact suitable for analysis (iteration log + key handles + final evidence).
- Judge success/failure of the run (task-completion signal).
- Extract a compact, reusable memory item (strategy/template/checklist) from that trajectory using `llm_query` (claudette), not DSPy.
- Persist and retrieve memory items across runs (start with JSON+npy).
- On a new, similar task, retrieve top-k memories and inject them (in a bounded way) to improve convergence.

Hard requirement:
- Retrieved memories must not become a substitute for retrieval. They are **procedural guidance**, and final answers still require evidence gathered via bounded REPL interactions.

#### Closed-Loop Cycle

Each RLM completion triggers the following cycle:

1. **Retrieve**: Before the RLM run, embed the task query and retrieve top-k relevant memories. Inject into root prompt (bounded, with "assess relevance" instruction).

2. **Interact**: Run the RLM loop (REPL exploration → `FINAL`).

3. **Extract**: After completion, capture trajectory artifact, run judge, extract up to 3 memory items if trajectory is informative.

4. **Consolidate**: Append new items to the memory pool. Periodically run consolidation to manage growth (see decision #7 above).

This cycle runs automatically after every `completion` call in deployed agents. In Solveit experiments, it can be triggered manually for inspection.

Done when:
- A repeated evaluation task (e.g. UniProt crosswalk discovery) shows fewer iterations or fewer “wrong turns” on the second attempt due to retrieved procedural memory.

### Meta-Graph Navigation Layer (Core Goal)

**Goal:** Treat “metadata” and “meta-graphs” as first-class *REPL-resident navigation scaffolding* that enables progressive disclosure over RDF graphs and SPARQL results.

This work uses two different kinds of metadata, and they must not be conflated:

1. **Root-prompt metadata (outside the REPL)**  
   The `rlmpaper` loop shows the root model only context *shape* (type, total length, chunk lengths). This enforces exploration.

2. **Domain metadata / meta-graphs (inside the REPL)**  
   Derived, cheap-to-query structures computed from an ontology graph or result set (indexes, summaries, small adjacency views). These are the *tools of exploration*.

#### Contract: What the meta-graph layer is

- **A set of REPL symbols** derived from a graph/result handle that:
  - are **small** enough to inspect directly (counts, small dicts/lists),
  - support **bounded views** (head/sample/group/describe),
  - enable **candidate generation** (search by label/localname/IRI substring),
  - and guide **chunking strategy** (roots/branches, common predicates, SHACL example buckets).

Examples of meta-graph artifacts (not exhaustive):
- Namespaces/prefixes
- Label/comment index and inverted lookup
- Class hierarchy skeleton (roots, `subClassOf` adjacency)
- Property inventory + domain/range where available
- Predicate frequency summary (top predicates)
- OWL “expressivity signals” (presence of restrictions, disjoints, property chains) as counts/samples
- SHACL example/query index: keyword → example handle
- SPARQL result meta: columns, row count, distinct counts, group-by summaries

#### Contract: What the meta-graph layer is not

- Not a full dump of triples, a full materialized adjacency matrix, or a “print everything” interface.
- Not a one-shot “sense doc” that replaces retrieval. Any “sense” summary is a **buffer** that must be validated by bounded retrieval.
- Not ontology-specific hardcoding (“UniProt special cases”) when a general view primitive can express the same thing.

#### Design requirements

- **Cheap to compute**: building the meta-graph should be fast enough to run often (or incrementally) during exploration.
- **Stable handles**: creating/updating meta-graph symbols should not rename or invalidate existing handles unexpectedly.
- **Evidence-friendly**: every high-level claim should be traceable to a small set of REPL-visible facts (e.g. a described URI, a query handle, a small sample of triples).
- **Sub-LLM boundaries**: only pass *bounded blobs* to `llm_query` (entity descriptions, small query results, a small hierarchy slice). The root model should orchestrate; sub-LLMs interpret.

#### “Sense document” guidance (fits RLM if used correctly)

If you generate an ontology “sense” summary:
- Treat it as a **navigation hypothesis**: “what to inspect next”, “likely important properties”, “URI patterns”.
- Keep the input bounded (counts + samples + small hierarchy slice).
- Always follow with retrieval steps (`search → describe → probe → expand`) to confirm before finalizing.

### Stage 2 — Create Bounded View Primitives (Graph + Results)

**Goal:** Enable progressive disclosure on RDF graphs without specialized “ontology expert” tools.

Design these as a minimal set of view operations that work for many tasks:
- Graph stats: triple count, distinct subject/predicate/object counts, namespace/prefix listing.
- Entity search: by label/comment/localname/IRI substring (returns a small candidate list).
- Entity describe: bounded “neighborhood” summary of a URI (types, labels, comments, outgoing predicates, incoming predicates).
- Relationship probe: one-hop neighbors for a given predicate; optional two-hop expansion but bounded.
- Result table view: columns, row count, head N, filter by column value/pattern, group-by counts.

Important: these should **return small summaries** and **store full results in REPL**. They operate over the graph handle *and* the meta-graph symbols built from it.

Done when:
- A root model can answer “Is X defined?”, “What is X’s comment?”, “What predicates connect A to B?”, and “List top 20 properties by frequency” with iterative REPL calls.

### Stage 3 — Make SPARQL “Result Handles” First-Class

**Goal:** Stop treating SPARQL results as raw strings or huge tables.

Treat every SPARQL execution as producing a handle with:
- `meta`: query, endpoint/local, timestamp, row count, columns.
- `rows`: stored internally as a list of dicts (or a lightweight dataframe-like structure), but never dumped wholesale.
- `graph`: if CONSTRUCT/DESCRIBE returns triples, store as a graph handle.

Provide view primitives that operate on handles:
- `res_head(handle, n)`
- `res_where(handle, column, pattern/value)`
- `res_group(handle, column)` (counts)
- `res_sample(handle, n)` (random or stratified)

Done when:
- The root model can refine queries by inspecting result meta and small slices, not rerunning blind.

### Stage 4 — SHACL as Retrieval Scaffolding (UniProt use case)

**Goal:** Use SHACL examples/shapes to help the model discover “how to query this dataset”.

Approach:
- Parse SHACL example assets (where present) into an indexed store in REPL: keywords → example query handle.
- Enable “retrieve example → adapt → run → inspect”.

Done when:
- For UniProt, the model can find a relevant example by keyword and adapt it iteratively to answer a question, without needing to “know UniProt” upfront.

### Stage 5 — Sub-LLM Patterns for Graph Semantics

**Goal:** Use `llm_query` effectively (as intended by `rlmpaper`) for meaning extraction.

Define canonical sub-LLM call patterns that repeatedly show up in ontology work:
- Summarize an entity description into: “what is it?”, “how to use it in queries?”, “what are key predicates?”.
- Convert raw result rows into a concise narrative answer with citations to row ids/URIs.
- Compare two candidate entities and decide which matches the user’s intent.
- Turn a SHACL example into an explanation + query template.

Done when:
- Root model primarily manipulates handles and asks sub-LLMs to interpret bounded blobs, rather than reading RDF triples directly.

### Stage 6 — Evaluation Harness (Small, Local, Repeatable)

**Goal:** Prevent regressions and keep development honest.

Create a small suite of “trajectory tests” (not unit tests at first; notebook scenarios are fine):
- PROV ontology:
  - Existence + definition: “Is `InstantaneousEvent` defined? Where is its comment?”.
  - Hierarchy: “What are its subclasses/superclasses?” (bounded depth).
- UniProt ontology:
  - SHACL/example-driven query discovery: “Find WikiPathways crosswalk predicates or mappings”.
  - Identify pathway-related classes/properties and show an example query that returns pathway annotations.
- Dataset memory:
  - Update: “Add a new assertion about X into `mem`, then retrieve it with a query scoped to `mem`.”
  - Provenance: “Show when/why the assertion was added (from `prov`).”
  - Invalidation: “Demonstrate a meta-graph index was rebuilt or marked stale after the update.”
  - Continuity: “If running as a long-lived agent, show the assertion persists across two separate user queries (two `completion` calls).”
- Procedural memory (ReasoningBank-style):
  - “Attempt a task, extract a success/failure memory, persist it, then re-attempt and confirm the retrieved memory changes behavior.”

Measure:
- Number of iterations to converge.
- Max size of any printed output (should stay small).
- Whether the final answer is grounded in REPL-observed evidence.

Done when:
- The same questions produce stable trajectories and stable answers over multiple runs.

## Proposed nbdev Notebook Structure

This is a suggested end-state organization for `nbs/` (you can arrive there gradually):

1. **`00_core.ipynb` — Thin glue over `rlmpaper`**
   - Goal: expose a stable interface for Solveit usage without re-implementing the RLM algorithm.
   - Focus: configuration, prompt selection, environment selection, logging/trace visibility, and “how to run”.

2. **`01_repl_views.ipynb` — General-purpose bounded views**
   - Goal: view/inspect handles (graph handles, result handles) predictably.
   - Focus: “head”, “count”, “group”, “describe”, “search” patterns.

3. **`02_ontology_rdflib.ipynb` — Ontology setup + indexing**
   - Goal: load graphs and build the meta-graph navigation layer (labels/comments/types, hierarchy skeleton, property inventory, prefixes, expressivity signals).

4. **`03_sparql_handles.ipynb` — SPARQL execution + result handles**
   - Goal: produce and inspect SPARQL results without dumping them.
   - Keep remote endpoints optional; prefer local graph SPARQL for repeatability.

5. **`04_dataset_memory.ipynb` — Dataset memory + updates**
   - Goal: implement the Dataset-based memory model (named graphs, update protocol, provenance, invalidation/versioning).

6. **`05_procedural_memory.ipynb` — ReasoningBank-style procedural memory**
   - Goal: capture RLM trajectories, judge, extract reusable memories, retrieve/inject top-k, and persist (JSON+npy baseline).

7. **`06_shacl_examples.ipynb` — SHACL and example query retrieval**
   - Goal: parse, index, retrieve, adapt, execute.

8. **`90_eval.ipynb` — Trajectory scenarios**
   - Goal: repeatable “demo tests” that reflect real use.

## Design Heuristics (What to Build vs Avoid)

Build:
- A small set of composable, general primitives that can be chained.
- “Handles” that keep large objects in the REPL and expose small views.
- Sub-LLM calls that interpret bounded blobs and return compact structured summaries.

Avoid:
- Specialized one-off tools for each ontology feature unless a view primitive cannot express it.
- Printing entire query result tables or large slices of triples.
- Encoding ontology knowledge in code (“hardcoding UniProt quirks”) instead of enabling discovery.

## Practical Notes for Ontology Work in RLM

- RDF data is graph-shaped; progressive disclosure should be graph-shaped too:
  - Start with **search** → **describe** → **probe neighbors** → **expand**.
- Most “ontology questions” are really one of:
  - Find the right URI (entity identification).
  - Interpret what a URI means (labels/comments/types).
  - Understand how URIs connect (predicates, domains/ranges, SHACL constraints).
  - Translate a natural language question into a query template (use examples + sub-LLM).

## Definition of Done (Project-Level)

This effort is “working” when:
- The Solveit AI can answer non-trivial questions about `ontology/prov.ttl` and `ontology/uniprot/` by:
  - Loading graphs into REPL symbols.
  - Using bounded views to retrieve evidence.
  - Using `llm_query` to interpret evidence.
  - Returning `FINAL(...)` grounded in those observations.
- The root model never needs a bulk ontology dump in its own context window.
- The approach remains faithful to the `rlmpaper` loop semantics and prompting discipline.
