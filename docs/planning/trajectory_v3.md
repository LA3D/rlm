# Trajectory v3: DSPy-only RLM (Graph REPL parity + Remote SPARQL + UniProt Evals)

**Last Updated:** 2026-01-21

**Status:** ✅ **Phases 1-2 COMPLETE** | 🚧 **Phases 3-7 planned** (v2 delivered the foundation; v3 completes DSPy-only + remote SPARQL + UniProt eval harness + SHACL tools)

This document supersedes `docs/planning/trajectory_v2.md` as the active trajectory for *finishing the DSPy migration*, especially the missing SPARQL/graph-navigation capabilities required for UniProt-style endpoint evaluation.

---

## Motivation and background (why this structure)

This project is in service of a research goal: **ontology-based query construction** over knowledge graphs, where the ontology provides **affordances** that improve both correctness and efficiency.

The key claim we want to test is not "can an LLM answer questions?", but:

> Can an LLM *use* ontology structure (and related metadata) to reliably construct and execute correct multi-hop SPARQL queries, rather than blindly guessing or retrieving?

That is why the architecture prioritizes:

- **Progressive disclosure via a REPL**: keep large graphs/results outside the LLM context window; interact via bounded views and handles.
- **A tool-surface contract**: make the "correct way" of interacting with graphs the easiest way (and gradeable).
- **Procedural memory (ReasoningBank)**: store strategies ("recipes") for using ontology affordances (e.g., how to traverse hierarchies, when to use `GRAPH`, when to use federation).
- **Evals as the forcing function**: the evaluation harness should make it obvious when the agent is applying graph/ontology logic vs freewheeling.

---

## System philosophy: self-bootstrapping ontology navigation

This system is designed to work with **any** ontology or federation of ontologies without pre-programmed domain knowledge. The core claim is:

> Given schema access and bounded execution capabilities, an LLM can discover operational rules (affordances) through exploration, encode them as procedural memory, and improve over time.

### What the system receives

- Ontology schema (classes, properties, hierarchy structure)
- Endpoint access (for remote SPARQL execution)
- Bounded view functions (progressive disclosure, not dumps)

### What the system must discover

- Which hierarchies are materialized vs require closure (`+`)
- When `GRAPH` clauses are needed (dataset partitioning)
- When `SERVICE` federation is required
- Effective query patterns for common task types

### Role of reference materials

Reference materials like `AGENT_GUIDE.md` and SHACL exemplars serve specific purposes:

- **Benchmark for evaluation**: They document what the system *should* learn, not what it is told
- **Gold-standard queries**: Exemplars provide ground truth for evaluating structural correctness
- **Optional curriculum seeds**: For cold-start bootstrapping (not runtime injection)

The system's value comes from its ability to **discover** these affordances through exploration and encode them in procedural memory—not from being pre-programmed with domain knowledge.

---

## Research questions this trajectory is meant to answer

### RQ1 — Metadata structure: can LMs discover and use ontology affordances?

Can the system dynamically discover operational rules through schema exploration and encode them as reusable knowledge?

We test this by measuring whether the system:
- Discovers hierarchy materialization rules through trial and error
- Learns when `GRAPH` and `SERVICE` clauses are required
- Encodes these discoveries as retrievable procedures

Candidate metadata the system should be able to derive:
- Ontology "sense cards" / affordances: schema overview, key classes/properties, labeling predicates, hierarchy hints
- Endpoint semantics/policies: named graph partitioning, materialized hierarchies, federation expectations, LIMIT/timeout constraints
- Procedural memory: learned strategies distilled from successful trajectories

We will test whether LMs *actually discover and apply* these signals by grading structural properties of the executed SPARQL and the trajectory (not just the final answer).

### RQ2 — Multi-hop Q&A: what must be accounted for in SPARQL?

Multi-hop SPARQL questions require the agent to correctly compose operators:

- Joins across entity types (protein → annotation → disease; protein → enzyme → reaction, etc.)
- Named graph joins (dataset partitioning via `GRAPH <...>`)
- Federated joins (`SERVICE <...>`)
- Closure semantics:
  - when hierarchies are materialized vs when property-path closure (`+`) is required
  - when alternation and path composition are needed (`(p1|p2)`, `(p1/p2)`)

We will evaluate whether the agent uses these correctly and efficiently.

### RQ3 — "Uses ontology logic" vs "blind retrieval": does the architecture help?

We want evidence that the system:

- explores schema before committing to a query
- uses ontology affordances (domain/range, hierarchy hints, exemplar patterns)
- chooses appropriate SPARQL operators based on endpoint semantics (materialized vs not)
- produces answers grounded in executed query results

This is why the system is DSPy-only: typed `SUBMIT` outputs + structured trajectories + a controlled tool surface make these behaviors measurable and enforceable.

### RQ4 — Learning dynamics: does the system improve with experience?

We measure whether ReasoningBank accumulation produces measurable improvement:

- **Learning curve**: Does iteration count decrease over trials on similar tasks?
- **Transfer**: Do strategies learned on one task type help with related types?
- **Curriculum effect**: Does structured progression outperform random task ordering?
- **Feedback value**: How much does human correction accelerate learning?

This requires longitudinal experiments where the same system instance runs many tasks in sequence, with memory persisting across runs.

---

## Curriculum design: from cold start to competence

The system cannot discover complex affordances (federation, named graphs) without first succeeding at simpler tasks. We define a curriculum that progresses through query complexity.

### Curriculum levels

| Level | Query Type | Example | What's Learned |
|-------|-----------|---------|----------------|
| L0 | Schema exploration | "What classes exist?" | Bounded view usage, namespace discovery |
| L1 | Single-hop, single endpoint | "List bacterial taxa" | Basic triple patterns, LIMIT discipline |
| L2 | Multi-hop, single endpoint | "Proteins → annotations → diseases" | Join patterns, result handle chaining |
| L3 | Hierarchy-sensitive | "All E. coli strains" | Materialized vs closure semantics |
| L4 | Named graph joins | "Proteins with genetic diseases" | `GRAPH` clause usage |
| L5 | Federation | "Rhea reactions → UniProt enzymes" | `SERVICE` clause, cross-endpoint joins |
| L6 | Complex pipelines | "Dopamine-like → reactions → variants → diseases" | Composition of L3-L5 patterns |

### Curriculum progression strategies

**Option A: Strict progression**
- System must pass N tasks at level L before attempting level L+1
- Pro: Avoids confusing failures
- Con: Slow, may over-fit to early levels

**Option B: Interleaved with scaffolding**
- Attempt all levels, but inject level-appropriate hints on failure
- Pro: Faster exploration
- Con: Hints may leak affordances

**Option C: Failure-driven curriculum**
- Attempt any task; on repeated failure at a pattern, regress to simpler tasks targeting that pattern
- Pro: Adaptive
- Con: Requires failure classification

**Recommendation:** Start with Option A for initial validation, then experiment with Option C.

### Cold-start bootstrapping options

**1. Zero-shot**: No seeding; system learns entirely from exploration
- Use for measuring baseline learning rate
- Expect high initial failure rate

**2. Exemplar-seeded**: Import synthetic trajectories derived from SHACL exemplars
- Convert exemplar queries into "as-if" successful trajectories
- Seeds ReasoningBank with known-good patterns
- Use for practical deployment; compare learning curves to zero-shot

**3. Human-guided**: Human annotates first N trajectories
- Corrects judgment errors during cold start
- Most efficient but requires human time

---

## Human-in-the-loop feedback

The closed-loop memory system can learn wrong patterns if judgment is incorrect. Human feedback provides correction signal.

### Feedback insertion points

**1. Trajectory judgment override**
- After automatic judgment, human can mark trajectory as success/failure
- Captures cases where: correct answer but wrong method, or vice versa

**2. Procedure curation**
- Before extracted procedures enter long-term memory, human reviews
- Approve: procedure is correct and generalizable
- Reject: procedure is incorrect or too specific
- Edit: procedure needs refinement

**3. Memory pack review**
- Before exporting memory packs (git-shipped), human reviews accumulated procedures
- Prune: remove procedures that haven't proven useful
- Annotate: add human-written context to procedures

### Feedback interface requirements

- CLI command: `rlm memory review --pending` to show un-reviewed extractions
- Structured annotation: success/failure + reason code (`structural_error`, `grounding_error`, `efficiency`, `lucky_guess`)
- Feedback persistence: stored in ReasoningBank alongside procedures

### When feedback is required vs optional

| Scenario | Feedback | Rationale |
|----------|----------|-----------|
| High-confidence success (structural match + grounded) | Optional | Automatic judgment likely correct |
| High-confidence failure (syntax error, empty results) | Optional | Clear signal |
| Ambiguous (correct answer, unexpected structure) | Required | May be novel strategy or lucky guess |
| Novel pattern (no similar procedure in memory) | Recommended | Prevents bad generalization |

---

## Goal

Enable an agent to answer multi-hop questions over real knowledge graphs by **constructing and executing SPARQL** using:

- **RLM progressive disclosure** (handles-not-dumps; explore before answer)
- **Ontology affordances** (dynamically discovered sense/meta-ontology)
- **ReasoningBank procedural memory** (retrieve→inject→judge→extract→persist)
- **DSPy-only runtime** (typed `SUBMIT`, structured trajectories, tool-surface guarantees)

Primary target testbed: **UniProt** endpoint + exemplars under `ontology/uniprot/examples/**`.

---

## Evals background: why UniProt and what we measure

UniProt is a strong benchmark for these research questions because it requires *structural* SPARQL correctness, not just factual recall:

- **Named graphs**: some questions require joining partitioned datasets (e.g., UniProtKB vs diseases) via `GRAPH <...>`.
- **Federation**: many queries require `SERVICE` to external endpoints (Rhea, OrthoDB, ChEBI similarity, etc.).
- **Closure semantics vary by subdomain**:
  - taxonomy and EC hierarchies are frequently **materialized** → `rdfs:subClassOf` (not `+`)
  - CHEBI (via Rhea) often requires **transitive closure** → `rdfs:subClassOf+`

This enables eval tasks where the agent must apply the *correct* operator given metadata/affordance hints.

### What UniProt evals should demonstrate

For a given task, we grade not only "answer exists", but whether:

- the executed SPARQL includes required structural operators (`GRAPH`, `SERVICE`, property paths)
- the trajectory demonstrates progressive disclosure (schema exploration → bounded query → bounded view → submit)
- the final answer is grounded in bounded evidence from result handles

### Why the testing matrix matters (context vs memory)

We explicitly vary:

- baseline context vs `ont_sense` vs SHACL exemplars vs both
- ReasoningBank off vs retrieve-only vs closed-loop

Then measure changes in:

- convergence rate and iteration counts
- fewer invalid SPARQL attempts / correction loops
- higher structural compliance (operator-sensitive tasks)
- better grounding and evidence completeness

See `docs/guides/uniprot-evals.md` for the current UniProt task suite and rationale.

### Reference: sample UniProt eval tasks already staged

The following tasks have been added as initial "operator-sensitive" benchmarks derived from the UniProt/Rhea exemplar corpus:

- `evals/tasks/uniprot/taxonomy/uniprot_bacteria_taxa_001.yaml`
- `evals/tasks/uniprot/taxonomy/uniprot_ecoli_k12_sequences_001.yaml`
- `evals/tasks/uniprot/multigraph/uniprot_genetic_disease_proteins_001.yaml`
- `evals/tasks/uniprot/multihop/uniprot_gene_protein_rhea_sets_001.yaml`
- `evals/tasks/uniprot/federated/uniprot_sphingolipids_chembl_001.yaml`
- `evals/tasks/uniprot/federated/uniprot_orthologs_orthodb_001.yaml`
- `evals/tasks/uniprot/federated/uniprot_rhea_reaction_ec_protein_001.yaml`
- `evals/tasks/uniprot/complex/uniprot_dopamine_similarity_variants_disease_001.yaml`

These are intentionally not "exact count" tests. They focus on whether the agent uses the required **structural operators** (`GRAPH`, `SERVICE`, property paths where appropriate) and produces bounded, grounded evidence.

---

## Testing matrix (ablation study design)

To attribute performance to specific components, we test combinations systematically.

### Component toggles

| Component | Off | On | Notes |
|-----------|-----|-----|-------|
| `sense_card` | Minimal schema stats only | Dynamic affordance summary | Tests value of schema reasoning |
| `memory_retrieve` | No procedure injection | Top-k procedures in context | Tests value of retrieved memory |
| `memory_store` | No learning | Extract + persist procedures | Tests value of accumulation |
| `curriculum` | Random task order | Structured progression | Tests value of curriculum |
| `human_feedback` | Automatic judgment only | Human correction on ambiguous | Tests value of feedback |
| `shacl_tools` | No template access | Query/shape index tools available | Tests value of template-guided construction (Phase 7) |

### Primary comparisons (minimum viable experiment)

1. **Baseline**: sense_card=off, memory=off
2. **Sense only**: sense_card=on, memory=off
3. **Memory only**: sense_card=off, memory=on (retrieve+store)
4. **Full system**: sense_card=on, memory=on

### Extended comparisons (if resources permit)

5. **Seeded vs zero-shot**: memory=on with/without exemplar seeding
6. **Curriculum effect**: structured vs random task ordering
7. **Feedback value**: with/without human correction on ambiguous cases
8. **SHACL tools value** (Phase 7): full system vs full system + shacl_tools — measures incremental value of template-guided construction after baseline is established

### Sample size considerations

- Per condition: minimum 3 trials per task
- For learning curves: 20+ sequential runs to observe trends
- Statistical test: paired comparisons (same tasks across conditions)

---

## Eval framework integration plan (make the staged UniProt evals executable)

We have two separate concerns:

1) **The eval harness mechanics**: loading tasks, running trials, grading, saving results
2) **The execution backend and artifacts**: ensuring DSPy-only runs emit the right structured outputs and logs for graders and MLflow

### 1) Migrate eval execution to DSPy-only

Current state:
- The eval framework exists under `evals/`.
- UniProt tasks are staged under `evals/tasks/uniprot/**`.
- The harness currently does not execute UniProt tasks successfully because:
  - UniProt requires **remote endpoint SPARQL** (with `GRAPH`/`SERVICE`), and
  - DSPy runs do not yet expose `sparql_query` and result-handle views.

Required changes:
- Make `evals.runners.TaskRunner` (or a new runner) invoke the DSPy engine as the default executor:
  - use `rlm_runtime/engine/dspy_rlm.py` as the backend (DSPy-only going forward)
  - ensure the run returns `{answer, sparql, evidence, trajectory}` (typed output contract)
- Keep the **tool name** stable for graders and task YAMLs:
  - expose a DSPy tool named `sparql_query` (wrapping `rlm/sparql_handles.py`) so the UniProt task YAMLs do not need to churn.

### 2) Ensure DSPy tool parity for endpoint tasks

To run UniProt tasks, DSPy must have:
- `sparql_query(...)` (remote execution) with:
  - endpoint selection (UniProt, Rhea, OrthoDB, etc.)
  - timeouts
  - bounded results / handle summaries
  - support for `GRAPH` and `SERVICE` clauses
- result-handle view helpers (bounded inspection), conceptually:
  - `res_sample(handle, ...)`, `res_head(handle, ...)`, etc.

This is explicitly a v3 requirement because it is what enables multi-hop and federated UniProt exemplars to run under DSPy-only.

### 3) Update graders to inspect structured artifacts (not just stdout)

Today's graders primarily work by scanning "code blocks" and REPL stdout.

For endpoint SPARQL, the most reliable signal is the **executed SPARQL string** plus a bounded **evidence** payload.

Required grader updates/additions:
- Add a grading path that checks `result.sparql` directly for required structural operators:
  - `GRAPH <...>` presence for multi-graph tasks
  - `SERVICE <...>` presence for federation tasks
  - property-path patterns where required/forbidden (e.g., "materialized hierarchies")
- Keep groundedness checks based on bounded evidence samples (rows/URIs), not full dumps.

### 4) Integrate MLflow into eval runs (cohort analysis)

We want to use MLflow to answer the research questions via cohort comparisons across the testing matrix.

The eval harness should:
- Start one MLflow run per **trial** (or nested runs under a task-level parent run).
- Log **params**:
  - `task_id`, `category`, `difficulty`, `trial_number`
  - `backend=dspy`
  - `ontology_id`, `endpoint`
  - matrix condition flags:
    - `use_ont_sense` (0/1)
    - `use_shacl_exemplars` (0/1)
    - `memory_mode` (`none` | `retrieve_only` | `closed_loop`)
- Log **metrics**:
  - `passed` (0/1)
  - `iteration_count`
  - `converged` (0/1)
  - grader scores (groundedness, structural compliance)
- Log **artifacts**:
  - executed SPARQL (`sparql.sparql`)
  - evidence payload (`evidence.json`)
  - trajectory log (`trajectory.jsonl` or normalized JSON)

This allows questions like:
- "Does `ont_sense` reduce iterations on multi-graph tasks?"
- "Does ReasoningBank reduce invalid query attempts on federation tasks?"
- "Do SHACL exemplars increase `SERVICE` and `GRAPH` compliance?"

### 5) Live vs offline posture (endpoint constraints)

UniProt evaluation is inherently "live" (networked). The harness must support:
- opt-in execution (requires API keys + network)
- explicit labeling/tagging of endpoint-backed trials
- resilience to endpoint drift (grade structural operators + bounded evidence, not exact counts)

## What v3 changes vs v2

`trajectory_v2.md` established the runtime, DSPy engine, SQLite ReasoningBank, and observability. v3 focuses on the remaining integration gap:

1) **DSPy tool surface parity** with the "graph REPL ergonomics" previously experienced via the claudette-backed RLM namespace.
2) **Remote SPARQL execution** (must support `GRAPH` and `SERVICE`) by integrating `rlm/sparql_handles.py` into the DSPy tool surface.
3) **Eval harness migration to DSPy-only**, including a UniProt task suite and a proper testing matrix over:
   - `ont_sense` vs baseline context
   - SHACL exemplar injection
   - ReasoningBank on/off / closed-loop
4) **Curriculum and learning dynamics**: structured progression through query complexity with learning curve measurement.
5) **Human feedback mechanism**: correction signal for ambiguous judgments and procedure curation.
6) **v2 correctness items carried forward**:
   - Dataset snapshot `session_id` restoration (incomplete in v2)
   - Tool output bounding enforcement (audit and verify all DSPy tools)
7) **SHACL-driven query construction** (deferred to Phase 7): expose SHACL query/shape indexes as bounded tools, measure incremental value after establishing baseline.

## Non-negotiable invariants (carry forward)

1) **Handles-not-dumps**: SPARQL results and graphs are handles; only bounded views go to the model.
2) **REPL-first discovery**: the agent must explore schema/affordances before finalizing.
3) **Bounded execution**: iteration budgets, call budgets, timeouts, and result limits are enforced.
4) **Evidence-first answers**: final answer must cite evidence from executed queries/handle samples.
5) **Separation of concerns**:
   - Tools = bounded execution + views
   - DSPy-RLM = orchestration loop + typed output contract
   - ReasoningBank = procedural memory service (retrieve/extract/persist)
   - Context builder = dynamic meta-ontology + retrieved procedures

## Target architecture (DSPy-only)

**Context Builder**
- Inputs: user query, ontology id, endpoint, optional task type
- Outputs: compact context string:
  - dynamically generated "sense card" / affordances (from schema exploration)
  - retrieved ReasoningBank procedures (top-k)
  - endpoint policies (LIMIT discipline, named graphs, federation rules)

**DSPy RLM Engine**
- Persistent interpreter namespace with graph navigation conveniences
- Bounded tool surface:
  - local schema navigation (GraphMeta tools)
  - remote SPARQL execution (via `sparql_handles`)
  - bounded handle views (sample/head/group/distinct)
- Typed termination via `SUBMIT(answer=..., sparql=..., evidence=...)`

**ReasoningBank (SQLite)**
- Retrieves procedures for context injection
- Stores trajectories + judgments + extracted procedures
- Supports human feedback annotations
- Exports git-shippable memory packs

**Observability**
- JSONL trajectory log + MLflow structured runs
- Must capture: executed SPARQL, endpoints used, bounded samples, tool calls, iterations
- Learning metrics: cumulative tasks, memory size, retrieval hits, novel extractions

## v3 Phases (with "done" criteria)

**Phase Status:**
- ✅ Phase 1: Foundation correctness — **COMPLETED** (Jan 18-21, 2026)
- ✅ Phase 2: Remote SPARQL integration — **COMPLETED** (Jan 21, 2026)
- 🔄 Phase 3: Procedural memory model — **PLANNED**
- 🔄 Phase 4: Eval harness & learning metrics — **PLANNED**
- 🔄 Phase 5: Human feedback integration — **PLANNED**
- 🔄 Phase 6: Retire claudette — **PLANNED**
- 🔄 Phase 7: SHACL-driven query construction — **PLANNED**

### Phase 1 — Define DSPy "Graph REPL" contract (parity with legacy ergonomics) ✅

**Status:** ✅ **COMPLETED** (Jan 18-21, 2026)

**Problem:** claudette-backed RLM implicitly provided a graph-friendly namespace; DSPy needs an explicit bootstrap contract.

Deliverables:
- A documented list of "always-present" REPL globals (e.g., `context`, `meta`, `g`, handle registries).
- A documented list of "always-present" helpers for **navigating rdflib graphs** without dumping:
  - schema discovery and neighborhood probing
  - safe preview/format utilities
  - handle view helpers for results
- A single, stable **trajectory event schema** for DSPy runs that includes:
  - executed code
  - tool calls and bounded outputs
  - errors/retries
  - SPARQL executions and result handle summaries

**What was delivered:**

- ✅ **Dataset snapshot `session_id` restoration** (commit 97be6a6, Jan 18):
  - Fixed `rlm/dataset.py::load_snapshot` to properly restore session_id
  - Supports both new format (explicit sessionId triple) and old format (from prov events)
  - All 15 session tracking tests passing

- ✅ **Tool output bounding enforcement** (commits df5a8a6, Jan 21):
  - All `ontology_tools.py` tools clamp limits:
    - `search_entity`: [1, 10]
    - `describe_entity`: [1, 25]
    - `probe_relationships`: [1, 15]
    - `sparql_select`: injects LIMIT with max_limit (default 100)
  - All `sparql_tools.py` tools clamp limits:
    - `res_head`, `res_sample`: [1, 100]
    - `res_where`: [1, 200]
    - `res_group`: [1, 50]
    - `res_distinct`: [1, 100]
  - Explicit tests added (31 tests in test_sparql_tools.py, all passing)

**Done criteria satisfied:**
- ✅ DSPy runs perform graph navigation with iterative discovery and bounded views
- ✅ Trajectories include structured events (code, outputs, errors, SPARQL executions)
- ✅ Dataset snapshots correctly restore `session_id` (verified by passing tests)
- ✅ All exposed tools have documented and tested output bounds

### Phase 2 — Remote SPARQL tool integration (DSPy ↔ `sparql_handles`) ✅

**Status:** ✅ **COMPLETED** (Jan 21, 2026)

**Problem:** current DSPy tool surface only supports local `rdflib.Graph.query()`; UniProt tasks require endpoint execution with `GRAPH` + `SERVICE`.

**What was delivered:**

- ✅ **Remote SPARQL tool factory** (`rlm_runtime/tools/sparql_tools.py`, commit 06adbd1):
  - `make_sparql_query_tool()`: wraps `sparql_query()` for remote endpoints
  - Enforces timeouts (default 30s, configurable)
  - Enforces bounded outputs (default 100 rows, configurable)
  - Injects LIMIT clauses where missing
  - Returns handle summary, stores handle in namespace

- ✅ **Result handle view tools**:
  - `res_head`, `res_sample`, `res_where`, `res_group`, `res_distinct`
  - All tools take string handle names (consistent API)
  - All tools enforce safety bounds (documented in Phase 1)

- ✅ **DSPy engine support** (`rlm_runtime/engine/dspy_rlm.py`, commit 06adbd1):
  - `run_dspy_rlm_with_tools()`: accepts pre-built tools and context
  - Supports remote SPARQL without local ontology files
  - Full memory integration, MLflow logging, trajectory tracking

- ✅ **Eval harness integration** (`evals/runners/task_runner.py`, commit 06adbd1):
  - `_execute_dspy_rlm()`: runs tasks with DSPy backend
  - `_serialize_dspy_trajectory()`: converts trajectories for graders
  - Reads config from task YAML (max_results, timeout, ontology_name)
  - CLI `--dspy` flag to select backend

- ✅ **UniProt eval tasks** (commit 3d6b932):
  - 8 tasks across 5 categories (complex, federated, multigraph, multihop, taxonomy)
  - Tasks test `GRAPH`, `SERVICE`, hierarchy patterns

- ✅ **Code review fixes** (commit df5a8a6):
  - Fixed interpreter.namespace crash
  - Added safety bounds to all view tools
  - Clarified API documentation

**Done criteria satisfied:**
- ✅ DSPy runs can execute UniProt queries with `GRAPH` and `SERVICE`
- ✅ Result handles stored and inspected via bounded views
- ✅ `--dspy` flag works without crashes
- ✅ Evidence contract includes endpoint, query, bounded samples

### Phase 3 — Procedural memory model + dynamic affordance discovery

**Problem:** The system must discover operational rules through exploration and encode them in a retrievable, generalizable form.

Deliverables:

- **Procedure data model specification:**

  A stored procedure contains:
  ```json
  {
    "id": "proc_001",
    "trigger": "taxonomy hierarchy query",
    "observation": "UniProt taxonomy uses materialized rdfs:subClassOf",
    "strategy": "Use rdfs:subClassOf directly, not rdfs:subClassOf+",
    "evidence": {
      "task_id": "uniprot_bacteria_taxa_001",
      "successful_sparql": "...",
      "iteration_count": 3
    },
    "confidence": 0.85,
    "human_reviewed": false,
    "retrieval_keywords": ["taxonomy", "hierarchy", "subClassOf", "UniProt"]
  }
  ```

- **Extraction heuristics:**
  - Compare failed vs successful queries in same trajectory
  - Identify structural differences (closure operator, GRAPH clause, etc.)
  - Generalize: "this endpoint" → "endpoints with materialized hierarchies"

- **Retrieval strategy:**
  - BM25 on `trigger` + `retrieval_keywords` (current approach)
  - Future: embedding-based retrieval for semantic matching

- **Dynamic sense card generation:**
  - System generates affordance summaries from schema exploration
  - Not pre-written guides injected into context

Done when:
- Procedure format is implemented in ReasoningBank schema
- Extraction produces human-readable, non-trivial procedures
- Retrieval returns relevant procedures for test queries
- DSPy runs can generate sense cards dynamically from schema exploration

### Phase 4 — Eval harness: DSPy-only execution + learning metrics

**Problem:** current evaluation code paths were originally oriented around the claudette loop and do not reliably inspect structured DSPy artifacts.

Deliverables:
- Eval runner supports DSPy backend as the default executor and collects:
  - `answer`, `sparql`, `evidence`, `trajectory` artifacts
- Graders are updated (or new graders added) to inspect:
  - the executed SPARQL string and endpoint(s)
  - structural operator usage (`GRAPH`, `SERVICE`, property paths)
  - bounded evidence presence
- UniProt task suite (already staged under `evals/tasks/uniprot/**`) becomes runnable under DSPy-only.
- A "matrix runner" to execute cohorts:
  - baseline vs `ont_sense` vs `shacl_exemplars` vs combined
  - ReasoningBank off vs retrieve-only vs closed-loop

**Additional deliverables for learning measurement:**

- **Longitudinal run mode:**
  - Single system instance runs task sequence with persistent memory
  - Memory state checkpointed after each task
  - Enables learning curve analysis

- **Learning metrics logged to MLflow:**
  - `cumulative_tasks`: number of tasks completed so far
  - `memory_size`: number of procedures in ReasoningBank
  - `retrieval_hit`: whether retrieved procedures were relevant (human-judged or heuristic)
  - `novel_extraction`: whether this run produced a new procedure

- **Learning curve visualization:**
  - Plot: iterations vs cumulative_tasks (should trend down)
  - Plot: pass_rate vs cumulative_tasks (should trend up)
  - Plot: memory_size vs cumulative_tasks (should plateau)

Done when:
- `python -m evals.cli run 'uniprot/*'` runs via DSPy-only and produces artifacts suitable for analysis (even if pass rate is initially low).
- The matrix can be run reproducibly, and MLflow allows cohort comparisons.
- Longitudinal runs produce interpretable learning curves.
- We can answer: "Does the system get better with experience?"

### Phase 5 — Human feedback integration + curriculum runner

**Problem:** Automatic judgment can be wrong; the system needs human correction to learn reliably.

Deliverables:
- CLI for reviewing pending procedure extractions: `rlm memory review --pending`
- Feedback annotation schema: success/failure + reason codes
- Feedback persistence in ReasoningBank
- Curriculum runner that orders tasks by complexity level
- Cold-start seeding option (import synthetic trajectories from exemplars)

Done when:
- Human can review and approve/reject extracted procedures
- Curriculum progression is configurable (strict, interleaved, or failure-driven)
- System can bootstrap from exemplar-derived seeds

### Phase 6 — Retire claudette and stabilize

Deliverables:
- Claudette backend becomes explicitly "legacy/optional" or removed from the supported path.
- Documentation updated to describe DSPy-only workflow for:
  - local ontology tasks (rdflib)
  - endpoint tasks (UniProt)
  - procedural memory training and memory pack export
- CI/test posture:
  - live endpoint tests are opt-in
  - offline unit tests validate tool bounding, trajectory schema, and pack import/export

Done when:
- The "happy path" requires no claudette code and no claudette-specific REPL assumptions.

### Phase 7 — SHACL-driven query construction (template-guided)

**Problem:** After establishing baseline performance (sense cards + procedural memory), we want to measure whether SHACL exemplars provide additional value for query construction.

**Rationale for sequencing:** This phase comes after the baseline experiments (Phases 1-6) so we can measure the incremental value of SHACL tools. The experimental progression becomes:
1. Baseline (no affordances, no memory)
2. + Sense cards (dynamic schema discovery)
3. + ReasoningBank (procedural memory)
4. + SHACL tools (template-guided construction) ← **this phase measures incremental value**

Deliverables:
- Expose SHACL query index and shape index as bounded tools in the DSPy RLM environment:
  - `search_queries(keywords)` — find relevant query templates by keyword
  - `get_query_text(uri)` — retrieve the SPARQL text of a template
  - `describe_query(uri)` — get metadata about a query template (parameters, description)
  - `search_shapes(keywords)` — find relevant SHACL shapes by keyword
  - `describe_shape(uri)` — get shape constraints and target class
  - `shape_constraints(uri)` — get property constraints from a shape
- Update the output contract to include template provenance:
  - `evidence.template_uri` — if a SHACL template was used/adapted
  - `evidence.shape_uris` — if SHACL shapes guided query construction
- Add SHACL-aware grader that checks:
  - Whether agent retrieved relevant templates before constructing query
  - Whether final query structurally matches an available template (when one exists)
  - Template adaptation correctness (parameters substituted correctly)

Done when:
- On a SHACL example corpus (e.g., UniProt examples), the agent can:
  - Retrieve a relevant template by keyword
  - Adapt it with task-specific parameters
  - Execute it (remote or local surrogate)
  - Return grounded results with template provenance in evidence
- Ablation experiments show measurable difference between "full system" and "full system + SHACL tools"

### Phase 8 (Future) — Transfer and generalization

**Problem:** Strategies learned on UniProt should transfer to other biomedical ontologies (and eventually other domains).

**Research questions:**
- Do procedures learned on UniProt help with OBO Foundry ontologies?
- Do "materialized hierarchy" strategies transfer to Wikidata?
- What abstraction level enables transfer vs causes interference?

**Approach:**
- Export memory pack from UniProt experiments
- Import into fresh system targeting different ontology
- Measure: does pre-training help, hurt, or have no effect?

**Not in scope for v3**, but the architecture should not preclude this.

---

## Testing plan (what v3 must prove)

### UniProt suite (endpoint-backed)

Use tasks derived from the SHACL exemplar corpus (see `docs/guides/uniprot-evals.md`):

- Taxonomy (materialized hierarchy)
- EC hierarchy (materialized hierarchy)
- Multi-graph joins (`GRAPH <...>`)
- Federated queries (`SERVICE <...>`)
- Complex multi-hop pipelines (chem similarity → reactions → enzymes → variants → diseases)

### Structural operator assertions (key research claims)

We must be able to grade "uses ontology affordances" rather than "guessed answer":

- Uses correct closure operator (`rdfs:subClassOf` vs `rdfs:subClassOf+`) given known endpoint semantics.
- Uses `GRAPH` joins when required by dataset partitioning.
- Uses `SERVICE` when federation is required by the task.
- Uses bounded result views and does not dump large outputs.

### Memory value experiments

Across cohorts, measure:

- iteration count reduction
- fewer invalid SPARQL attempts
- higher structural compliance
- higher pass rates on "operator-sensitive" tasks

### SHACL tools value experiments (Phase 7)

After baseline experiments complete, measure incremental value of SHACL tools:

- Template retrieval rate: how often does the agent find and use relevant templates?
- Adaptation correctness: when templates are used, are parameters substituted correctly?
- Structural compliance delta: does template access improve `GRAPH`/`SERVICE`/property-path usage?
- Iteration reduction: does template access reduce trial-and-error query construction?

### Learning dynamics experiments

Across longitudinal runs, measure:

- Learning curves (iterations vs cumulative tasks)
- Memory growth and plateau
- Effect of curriculum vs random ordering
- Effect of human feedback vs automatic-only

## Known risks / constraints

- Endpoint availability and rate limits (UniProt and federated endpoints).
- Determinism: results may drift over time; graders should check structural properties + bounded evidence, not exact counts unless stable.
- The DSPy interpreter is host-Python; tool bounding and logging must prevent accidental large dumps.
- Cold-start bootstrapping: high initial failure rate expected without seeding or human guidance.
- Judgment accuracy: wrong judgments lead to learning wrong patterns; human feedback mitigates but requires time.
- Generalization risk: procedures may be too specific to transfer; abstraction level must be tuned.

## References

- Prior trajectory: `docs/planning/trajectory_v2.md`
- v2 Phase D (SHACL-driven query construction): origin of Phase 7 in this trajectory
- UniProt eval guide: `docs/guides/uniprot-evals.md`
- UniProt affordances (benchmark): `ontology/uniprot/AGENT_GUIDE.md`
- SPARQL handles: `rlm/sparql_handles.py`
- SHACL exemplar index: `rlm/shacl_examples.py`
- ReasoningBank implementation: `rlm_runtime/memory/`
- Dataset memory (session_id fix): `rlm/dataset.py`
