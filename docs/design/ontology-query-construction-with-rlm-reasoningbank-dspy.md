# Ontology-Based Query Construction: RLM + ReasoningBank + SHACL + DSPy Signatures

This document specifies requirements and a target design for **ontology-based query construction** over RDF graphs, using:
- **RLM** (REPL-first progressive disclosure over long context and large state),
- **ReasoningBank** (procedural and contextual memory),
- **SHACL indexes + `sh:SPARQLExecutable` examples** (affordance discovery and query templating),
- **DSPy signatures** (typed structure for tool use, sense, and outputs).

The objective is to build an agent that uses ontology structure (“affordances”) to:
1) choose good exploration actions,
2) construct correct SPARQL,
3) validate and interpret results,
4) converge with fewer iterations than a “blind KG agent”.

---

## 1) Problem Statement (Affordances, Not Blind Querying)

Ontology-based query construction is not just “generate SPARQL”.
The ontology provides explicit affordances that should guide the agent:
- **Naming affordances**: label/description predicates; URI patterns.
- **Schema affordances**: class/property inventory; hierarchy; domains/ranges; OWL constraints.
- **Example affordances**: SHACL shapes and executable query templates.
- **Execution affordances**: bounded result handles and view operators to iterate safely.

Without making these affordances legible in context, the agent:
- guesses predicates/classes,
- hardcodes URIs,
- runs unbounded queries,
- misreads results,
- wastes iterations on “orientation”.

Our design goal is to expose the affordances explicitly and compactly, and then enforce structured behavior through typed tool surfaces and typed outputs.

---

## 2) Architectural Roles

### 2.1 RLM (long-context interaction and progressive disclosure)

RLM requirements (from `docs/planning/trajectory.md`):
- Large state (graphs, results) lives in the REPL environment.
- The root model must explore via bounded actions; no bulk dumps.
- Heavy semantic work can be delegated via `llm_query` / batched calls.
- Iterations are bounded; termination is explicit (`FINAL(...)` or DSPy `SUBMIT(...)`).

For ontology-based query construction, RLM provides:
- safe iteration over graph metadata and query results,
- the “peek / search / describe / refine / validate / synthesize” workflow.

### 2.2 ReasoningBank (procedural + contextual memory)

ReasoningBank requirements (from paper + repo goals):
- Store reusable strategies distilled from successful and failed trajectories.
- Retrieve relevant items at test time and inject them so the agent:
  - chooses better tools,
  - constructs better queries,
  - avoids known failure modes.
- Persist, curate, and ship “memory packs” for reproducible bootstrapping.

For ontology-based query construction, ReasoningBank should store:
- **procedures** (“how to do it”), not raw ontology content.
- Templates and checklists that reference *available tools* and *bounded views*.

### 2.3 SHACL (schema and example-driven affordances)

SHACL requirements in this project:
- Shapes expose constraints (what properties exist, expected domains/ranges, cardinalities).
- SHACL-AF `sh:SPARQLExecutable` examples provide “retrieve → adapt → run” query patterns.

For query construction, SHACL adds:
- high signal for which predicates matter,
- executable example queries that reduce search space.

### 2.4 DSPy signatures (typed structure and guarantees)

DSPy’s contributions for this problem:
- **Typed inputs/outputs**: enforce a structured answer contract (e.g., return both `sparql` and `answer`).
- **Tool surfaces**: docstrings + signature docs + name validation improve tool discoverability.
- **Typed termination** via `SUBMIT(...)`: reduces unstructured finalization.

Key constraint:
- Don’t pass huge objects (rdflib graphs) as signature inputs. Keep those as REPL-resident handles and expose bounded operations as tools/closures.

---

## 3) Requirements: What the Agent Must Do (Behavioral)

### 3.1 Sense-first, schema-aware query construction

Given a task query `Q`, the agent should:
1) Determine ontology scope and available indexes (sense card).
2) Resolve entities by label/pattern to URIs (avoid guessing URIs).
3) Select predicates via:
   - domain/range lookups,
   - hierarchy navigation,
   - SHACL constraints (when present),
   - SHACL executable examples (when present).
4) Construct a bounded SPARQL query:
   - `LIMIT` and/or bounded projections by default,
   - avoid CONSTRUCT/DESCRIBE that can explode without bounds unless explicitly needed.
5) Execute via `sparql_local` or `sparql_query` and store a result handle.
6) Inspect with bounded result views (`res_head`, `res_where`, `res_group`, `res_distinct`, `res_sample`).
7) Validate grounding:
   - ensure returned URIs exist,
   - ensure results support the final claim.
8) Synthesize final answer plus the query/evidence.

### 3.2 Failure-aware behavior (learned from ReasoningBank)

The agent should incorporate “negative lessons”:
- Don’t assume CURIEs/URIs exist; search first.
- If query yields empty results:
  - broaden search (e.g., label predicate variations),
  - check namespace bindings / URI patterns,
  - check SHACL constraints or example templates.
- If results are too large:
  - add `LIMIT`, narrower WHERE patterns, or aggregate/group.
- If graph returns truncated results:
  - use alternate query forms (SELECT count first; then sample).

### 3.3 Affordance discipline (handles-not-dumps)

Tools and outputs must remain bounded:
- Tools return summaries, handles, and small slices.
- Avoid printing entire graphs/tables.
- Always prefer “view” operators for result inspection.

---

## 4) Requirements: What Must Be Stored in Memory (ReasoningBank)

We need two memory categories:

### 4.1 Procedural memory (universal strategies)

Examples:
- “Resolve label → URI → describe → then query.”
- “Prefer GraphMeta indexes over traversal.”
- “When writing SPARQL, start with SELECT + LIMIT + key variables; validate with res_head.”
- “If empty results, check label predicates and CURIE expansion; broaden search.”

These must be ontology-agnostic and avoid hardcoded URIs.

### 4.2 Contextual memory (ontology- or dataset-specific)

Examples:
- “PROV uses `prov:definition` / patterns around Activity–Entity–Agent.”
- “SIO has many measurement/process conventions; common predicates X/Y.”
- “This dataset’s endpoint requires GRAPH scoping; use named graph `...`.”

These should be scoped by ontology/dataset and stored as such (not injected universally).

### 4.3 Memory retrieval/injection requirements

- Retrieve top-k by query similarity (SQLite FTS BM25 or hybrid).
- Inject *bounded* memory: title + description + 1–3 bullets.
- Include an instruction: “assess applicability of each memory item before acting.”

---

## 5) Requirements: Sense, SHACL, and Example Indexes as Typed Artifacts

The affordances should be exposed in a compact, structured way.

### 5.1 Sense card (typed)

We already have a sense schema in `rlm/ontology.py` (`SENSE_CARD_SCHEMA`).
We should formalize it into a typed artifact for DSPy signatures:
- `ontology_id`, counts (triples/classes/properties)
- `label_predicates`, `description_predicates`
- `uri_pattern`
- `available_indexes` flags/summary
- `key_classes`/`key_properties` (bounded list)
- `quick_hints` (bounded list)

Critical requirement:
- All URIs in the card must be grounded/validated (`validate_sense_grounding`).

### 5.2 SHACL affordance signature (typed)

When SHACL is present, surface:
- Shape summary: count, top targets, common paths
- Constraints for relevant shapes: min/max counts, datatype/class constraints, patterns
- Whether executable SPARQL examples exist and how many

This can be expressed as a typed “SHACL affordance summary” that is:
- small,
- query-oriented (not a dump of the SHACL graph).

### 5.3 SPARQL example/template signature (typed)

From `rlm/shacl_examples.py`, we can provide:
- `QueryIndex.summary()`
- `search_queries(keyword)` results: uri/comment/endpoints/type
- `get_query_text(uri)` to retrieve template text

We should expose these via bounded tools, and optionally type the retrieval output:
- `template_uri`, `template_type`, `template_text`, `source_file`, `matched_keywords`

---

## 6) DSPy Signatures to Enforce Structure

The goal is to enforce:
- what inputs the agent can rely on,
- what outputs it must produce,
- how tools are used.

### 6.1 Core “query constructor” signature

Minimum viable:
- Inputs:
  - `query: str`
  - `sense_context: str` (or typed `SenseCard`)
  - `base_context: str` (GraphMeta summary)
  - optional `shacl_context: str` or typed SHACL summary
- Outputs:
  - `sparql: str`
  - `answer: str`
  - `evidence: dict` (URIs used, handle summaries, row samples)

This forces the agent to always return the actual query it ran (or intends to run), and the grounded answer.

### 6.2 Optional separation: “plan then execute”

Two-stage signatures:
1) `Plan`: decide which affordances/tools to use and what query shape is needed.
2) `Execute`: run and refine with bounded inspection until results are sufficient, then `SUBMIT`.

This reduces the chance of “hallucinated SPARQL” because the execution stage uses real tool outputs.

### 6.3 Strong tool surface requirements (to avoid “blind” SPARQL)

Expose tools like:
- Ontology:
  - `search_entity`, `describe_entity`, `probe_relationships`
  - optional “domain/range lookup” helpers
- SPARQL:
  - `sparql_local`, `sparql_query`
  - `res_head`, `res_where`, `res_group`, `res_distinct`, `res_sample`
- SHACL:
  - `search_shapes`, `describe_shape`, `shape_constraints`
  - `search_queries`, `get_query_text`, `describe_query`

Ensure each tool is bounded and has clear docstrings; DSPy will include these in its instruction prompt.

---

## 7) Putting It Together: Desired End-to-End Flow

Given a user query:

1) **Sense injection**
   - Provide typed `SenseCard` (and optional SHACL affordance summary).

2) **ReasoningBank injection**
   - Retrieve top-k procedural strategies and inject them (bounded).

3) **RLM loop (DSPy RLM or current loop)**
   - Use tools to resolve entities and schema hints.
   - Retrieve and adapt SHACL query templates when available.
   - Construct bounded SPARQL; execute; inspect results.
   - Iterate until sufficient evidence is collected.

4) **Typed completion**
   - `SUBMIT(sparql=..., answer=..., evidence=...)`

5) **Memory loop**
   - Store trajectory + judge + extracted procedural memories.
   - Optionally curate/export to packs.

---

## 8) Testing Requirements for Ontology-Based Query Construction

Use sample ontologies in `ontology/` to define “affordance tests”:

### 8.1 Offline tests (no LLM)
- Sense grounding validation (`validate_sense_grounding`) always passes for generated cards.
- Tools remain bounded (outputs length thresholds).
- SHACL query index functions return bounded results and stable schemas.

### 8.2 LLM-backed integration tests (optional “live”)
- For PROV:
  - agent must resolve `Activity` via search and describe.
  - agent must return structured outputs: `sparql`, `answer`, `evidence`.
- For a SHACL-heavy ontology:
  - agent must retrieve at least one template via `search_queries` and adapt it.

### 8.3 ReasoningBank efficacy tests
- With memory injection enabled, iteration counts should decrease for repeated tasks (measured on a fixed curriculum).

---

## 9) Implementation Checklist (Concrete Deliverables)

1) Add a typed “query construction” output contract (`sparql`, `answer`, `evidence`).
2) Ensure all ontology/SPARQL/SHACL tools are bounded and well-documented.
3) Represent sense and SHACL affordances as compact typed artifacts (or bounded strings with schemas).
4) Integrate ReasoningBank retrieval/injection as a first-class precondition step.
5) Store trajectories + outputs + memories in SQLite, export curated packs.

