# UniProt Evals: Multi-hop SPARQL Query Construction

This guide defines a UniProt-focused evaluation suite for measuring whether an agent (RLM + meta-ontology context + ReasoningBank procedural memory) can *use ontology structure* to construct and execute correct multi-hop SPARQL queries over real knowledge graphs.

## Why UniProt?

This repo already vendors:

- UniProt core ontology (schema): `ontology/uniprot/core.ttl`
- A large, curated set of SPARQL exemplars encoded as SHACL executables: `ontology/uniprot/examples/**`
- An agent affordance guide including crucial operational rules (e.g., “materialized hierarchies”): `ontology/uniprot/AGENT_GUIDE.md`

UniProt is also a strong testbed because “hard” questions frequently require:

- Multi-hop joins across protein → annotations → entities (disease, enzyme, taxonomy, etc.)
- Named graph joins (UniProt partitions some datasets into different graphs)
- Federated `SERVICE` queries (Rhea, OrthoDB, ChEBI similarity, etc.)
- Selective use of ontology semantics (e.g., when to use `rdfs:subClassOf` vs `rdfs:subClassOf+`)

## The testing matrix (what we vary)

The goal is to answer: *does our architecture make it more likely the LM will use ontology affordances rather than blindly retrieving?*

We run the same task set under a matrix of configurations and compare outcomes (pass rate, iterations, tool usage, groundedness, query validity, etc.).

### Axis A: Context shaping (meta-ontology)

- `baseline`: minimal schema summary (e.g., `GraphMeta.summary()`-style overview)
- `ont_sense`: inject a compact “sense card” + query-relevant brief sections (domain scope, key classes/properties, labels, hierarchy hints)
- `shacl_exemplars`: retrieve 1–3 relevant exemplar queries from `ontology/uniprot/examples/**` and include them as patterns
- `ont_sense + shacl_exemplars`: combined

### Axis B: Engine / loop

- `rlm` (claudette loop): the original RLM protocol (`FINAL` / `FINAL_VAR`)
- `dspy_rlm` (DSPy): typed `SUBMIT` output and structured trajectories

### Axis C: ReasoningBank procedural memory

- `none`: no retrieval, no storage
- `retrieve_only`: retrieve top-k procedures/strategies into context
- `closed_loop`: retrieve + judge + extract + persist new strategies, generating “memory packs”

## What we measure (beyond “got an answer”)

UniProt tasks are designed so correctness depends on using structural affordances. We want to measure:

- **Structural operators used**:
  - `GRAPH <...>` when required (multi-graph joins)
  - `SERVICE <...>` when required (federation)
  - `rdfs:subClassOf` vs `rdfs:subClassOf+` chosen appropriately based on “materialized hierarchy” guidance
  - predicate alternation and property-path composition (e.g., `(p1|p2)` and `(p1/p2)` patterns)
- **Grounding**: answer references items that appear in result samples
- **Efficiency**: iteration count, number of SPARQL executions, and correction loops

Observability via MLflow + trajectory JSONL artifacts should be enabled during eval sweeps to support post-hoc analysis.

## Critical plumbing required (TODO for runnable UniProt evals)

UniProt evals are **endpoint-backed**. The local ontology file is for schema/affordance discovery, but the *data* comes from the live SPARQL endpoint.

### 1) Load UniProt schema locally for affordances

- Load `ontology/uniprot/core.ttl` into an `rdflib.Graph` for class/property discovery and “sense” generation.
- Optionally load `ontology/uniprot/examples/prefixes.ttl` for consistent prefix bindings when emitting SPARQL.

### 2) Execute remote SPARQL (must support `SERVICE` + `GRAPH`)

Local `rdflib.Graph.query()` cannot emulate UniProt’s dataset partitioning and federation behavior.

We integrate `rlm/sparql_handles.py` as a runtime tool surface so agents can execute:

- Remote SELECT queries against `https://sparql.uniprot.org/sparql/`
- Queries containing `GRAPH <...>` clauses
- Queries containing `SERVICE <...>` federation clauses

Recommended approach:

- Expose a bounded tool (e.g., `sparql_query(...)`) backed by `rlm/sparql_handles.py:sparql_query`
- Ensure **safe defaults**: inject/require `LIMIT`, apply timeouts, and bound result materialization (via `SPARQLResultHandle`)
- Capture executed SPARQL as an artifact for graders and MLflow

Current status:

- The eval runner binds `sparql_query` into the execution namespace via `rlm/sparql_handles.py:setup_sparql_context` (`evals/runners/task_runner.py`).
- DSPy engine support still needs a bounded “remote SPARQL” tool in `rlm_runtime/tools/` for parity with the `dspy_rlm` backend.

### 3) Graders need access to the SPARQL string

To evaluate “uses ontology structure”, graders should check query text for required patterns (`SERVICE`, `GRAPH`, property paths, etc.).

This requires that the execution loop:

- Stores the executed SPARQL query string in a predictable place (e.g., structured output field, or in a trajectory artifact)
- Or prints/logs it in a machine-readable way so graders can inspect it

## UniProt eval task suite

Task definitions live under `evals/tasks/uniprot/` and are derived from the SHACL exemplar corpus.

Each task references the exemplar file it is based on and specifies which structural patterns must appear in the constructed query (e.g., `GRAPH`, `SERVICE`, materialized hierarchy use).

See:

- `evals/tasks/uniprot/taxonomy/`
- `evals/tasks/uniprot/multigraph/`
- `evals/tasks/uniprot/multihop/`
- `evals/tasks/uniprot/federated/`
- `evals/tasks/uniprot/complex/`

## How to run (once executor support is wired)

Intended usage:

```bash
python -m evals.cli list
python -m evals.cli run 'uniprot/*'
python -m evals.cli run 'uniprot/federated/*' --trials 3
```

Then analyze runs via:

- MLflow params/metrics/tags for cohort comparisons
- Trajectory JSONL artifacts for protocol and structural checks
