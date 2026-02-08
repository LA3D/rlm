# Owl + RLM Symbolic Memory (Prototype)

This directory is a scaffold for combining strict RLM-style symbolic execution with a traditional symbolic memory system built in Python using `owlready2` and `rdflib`.

The intent is not “RAG with extra steps”. The intent is RLM-faithful agent memory:

- The user prompt `P` itself is a symbolic object in the environment.
- The model must write recursive code (executed) to understand/transform `P`.
- Tools and subcalls must return into symbolic variables without leaking payloads into the model’s context window.

## RLM-Strict Memory Principles (Extended)

These are the architectural constraints this directory is aiming for:

- `P` is never provided as a raw prompt payload to the model; the model receives only `PromptRef` metadata.
- The model inspects `P` via bounded tools only (no grep, no “read all”), and uses recursion in executed code to scale.
- All external data (prompt text, traces, ontology blobs, long memory content) is stored behind handles; tools return handles + metadata.
- Any human-readable text returned by tools must be treated as hazardous: it can accidentally leak into `variables_info`, `stdout`, or history. Prefer handle-return + safe `repr()` objects.

## Architecture: Three Stores

1. **Blob store (payload)**
- Holds large strings (prompt text, trajectory logs, guides, evidence, long memory content).
- Access must be bounded and handle-first.

2. **Symbolic memory KG (owlready2 + rdflib)**
- OWL/RDF objects representing memory items, applicability constraints, provenance, conflicts, exceptions, and “compiled” rules.
- Retrieval uses deterministic SPARQL over the memory graph to return item ids and compact metadata.

3. **Indexes (optional, metadata-only)**
- Lexical or embedding indices over titles/tags/summaries or compiled fields.
- Indexes return ids only; payload stays in the blob store.

## How An Agent Structures Memory (RLM + OWL/RDF)

The core idea is: **OWL/RDF holds the executable, small, symbolic part of memory; handles hold everything large** (prompt text, evidence, traces, long explanations).

### Memory Layers

- **Environment objects (handles):** `PromptRef`, `OntologyRef`, `TraceRef`, `WindowRef` all point into the blob store.
- **Long-term symbolic memory (KG):** OWL individuals + RDF triples that are cheap to retrieve and safe to inject.
- **Long-term payloads (blob store):** human-readable “why”, snippets, and provenance artifacts referenced by `content_ref`.
- **Optional metadata indexes:** fast lookup over `title/summary/tags/compiled_fields` that returns ids only.

### What “Compiled Memory” Means Here

RLM memory should not depend on rereading prose. For each memory item, store:

- **Applicability conditions:** ontology URIs, task type, preconditions, known failure modes.
- **Action schema:** a small, deterministic recipe the executor can run (often: which graph to query, which relation to prefer, which constraint to enforce).
- **Verification hooks:** what to check after acting (a judge rule, invariant, or sanity query).

The LLM is used to bridge semantic gaps, but the *state* that persists is symbolic and minimal.

### Retrieval Contract (Metadata-First)

Retrieval should look like:

1. `memory_search(query_meta)` returns `[{id, title, summary, kind, applies_to, priority, confidence}]`
2. Code selects ids deterministically (by applicability + priority).
3. Only if needed: request bounded access to payload via handles (`content_ref` or a `WindowRef`) and immediately distill into new symbolic fields.

### Interaction With Real Ontologies (`ontology/`)

Keep ontologies and memory distinct:

- **Ontology graphs:** domain facts and schema (`ontology/*.ttl`, OWL files) loaded as read-only graphs.
- **Memory graph:** agent-learned items + relations (PROV-style provenance works well here).
- **Alignment links:** memory items reference ontology URIs (`appliesToOntology`, `aboutClass`, `aboutProperty`) rather than copying ontology content into memory.

This avoids “training on the world”: the ontology stays a source of truth; memory stores *procedural and diagnostic* knowledge for how to use it.

## Agentic Ontology Construction (OWL + SHACL)

`owlready2` (OWL) and `pyshacl` (SHACL) are intentionally different models:

- **OWL (owlready2):** meaning + inference (open-world). Used for schema design (TBox), alignments, and any typed individuals you want to reason over.
- **SHACL (pyshacl):** constraints + regression tests (validation). Used as the scalable judge for “definition of done”.

The agentic pattern is an online propose -> verify -> repair loop where SHACL produces a compact symbolic signal and the agent learns reusable repair operators.

### Online Loop (Handle-First)

All artifacts are environment objects (handles):

- `OntologyRef`: current ontology artifact (OWL/RDF serialization in blob store)
- `ShapesRef`: SHACL bundle used as judge (in blob store)
- `DeltaRef`: symbolic patch description (small) + optional handle to full diff
- `ReportRef`: full SHACL report (in blob store), never injected as raw text
- `TraceRef`: action log for provenance

Loop:

1. **Task/competency question**: represent the requirement as a small query template + expected outcomes (symbolic).
2. **Propose minimal delta**: add only what is required (classes/properties/restrictions/mappings).
3. **Apply** (code execution): produce a new `OntologyRef`.
4. **Verify** (SHACL): return only `conforms: bool`, `violation_count`, `violated_shape_IRIs`, `focus_node_IRIs`, plus `ReportRef`.
5. **Repair**: if violations exist, select a repair operator and iterate until conforming or timeout.
6. **Distill**: store an `Episode` and compile a reusable `Principle/Procedure/JudgeRule` from the delta + violation signature.

### Repair Operators (What The Agent Learns)

Treat each SHACL failure as a typed signature:

- `(shapeIRI, path, constraintComponent, nodeKind/datatype/class)` -> `operator_id`

Each operator is stored as compiled memory:

- Applicability: which ontologies/shapes/profiles it applies to.
- Action schema: deterministic patch template (fill IRIs/values programmatically).
- Verification hook: which shape(s) must pass after applying.

This keeps learning symbolic and makes improvements accumulate across runs without rereading long reports.

## Memory Item Design (What We Store)

A memory item should have two representations:

- **Symbolic (machine-usable, small):** typed fields and relationships that can be applied without reading long text.
- **Payload (human-readable, large):** explanation, evidence, trace snippets stored behind a `content_ref`.

Recommended item types (OWL classes):

- `Principle` (general rule), `Episode` (specific case), `Procedure` (how-to), `Constraint` (hard requirement), `AntiPattern` (avoid), `EndpointProfile` (capabilities), `JudgeRule` (evaluation).

Recommended properties:

- Data (small): `title`, `summary`, `kind`, `scope` (`general|exception`), `confidence`, `priority`, `created_at`, `use_count`.
- Links (symbolic): `appliesToOntology`, `appliesToTaskType`, `preventsFailureMode`, `refines`, `hasException`, `groundedByEpisode`, `derivedFromTrace`.
- Payload pointer: `content_ref` (blob key) and `content_hash`.

The key “RLM extension” is to store a **compiled form** of each memory item:

- Example: “taxonomy direct enumeration requires FROM graph X” as structured fields (not as prose the LLM must reread).
- This lets the agent apply memory by computation, and use the LLM only for semantic gaps.

## Tool Surface (What The Model Gets)

Tools should be designed for progressive disclosure:

- Phase 1: `*_search` returns ids + metadata only.
- Phase 2: `*_read_window` is only used if absolutely required.
- Prefer tools that return handles to windows (and keep window payload in the blob store) to avoid accidental prompt injection via variable reprs.

### RLM-Safe Return Types (Important)

Even bounded text is hazardous if it can be printed, logged, or injected into `variables_info`.
For strict RLM-style operation, prefer:

- Return `WindowRef` (handle) + byte/char offsets + hash.
- Return *symbolic extractions* (triples, labels, ids) rather than raw substrings.
- Ensure all tool return values have a safe `repr()` that never expands payload.

DSPy compatibility note:

- `dspy==3.1.3` expects `tools` as a list of callables (not dicts).

## How To Test As An Agentic Memory System

Use a streaming, ablation-first protocol.

- **Stream tasks** from real ontologies in `/Users/cvardema/dev/git/LA3D/agents/rlm/ontology/`.
- **Online loop:** retrieve → act → verify/judge → extract → store → continue.
- **Holdout checkpoints:** every N tasks, evaluate on held-out tasks to detect real learning vs memorization.

Ablations:

- `A0` no memory
- `A1` prompt-injected text memory (ReasoningBank-style) as a baseline
- `A2` strict symbolic memory (OWL + handles) with metadata-first retrieval
- `A3` hybrid: strict symbolic core + tiny packed hints (bounded) for ergonomics
- `A4` negative control: allow payload leakage and observe token growth / context rot

Metrics:

- Task: success/pass@k, correctness, convergence.
- Cost: iterations, tool calls, subcalls, tokens/cost.
- Memory: growth vs gain, dedup rate, rule conflicts, exception usage.
- RLM compliance: max window size, count of large returns, “payload in history” events.

### Memory-Specific Test Cases (What To Measure)

Beyond task success, add tests that force memory to matter:

- **Delayed recall:** hide a critical constraint early; require correct action 50+ steps later.
- **Conflicting rules:** store two principles with exceptions; measure correct exception resolution.
- **Ontology shifts:** swap ontology versions; ensure memory uses URIs and adapts, not copied text.
- **Over-retrieval pressure:** create many near-miss memory items; measure precision of retrieval.
- **Leakage traps:** seed long “bait” strings in prompt/ontology and ensure no tool return leaks them.

## Files

- `symbolic_handles.py` - Handle store for large text with strict read caps
- `owl_memory.py` - Owlready2-backed symbolic memory schema and retrieval
- `tools.py` - RLM tool surface combining prompt + owl memory
- `rlm_owl_runner.py` - Minimal DSPy RLM runner using list-based tools (`dspy>=3.1`)
- `agentic_ontology.py` - OWL+SHACL workspace with sprint-1 competency questions and repair operators
- `agentic_tools.py` - Combined strict-symbolic toolset for prompt/memory + ontology construction
- `agentic_owl_runner.py` - Agentic runner with per-step trajectory logging (reasoning/code/tool calls)
- `test_symbolic_memory.py` - Local tests for bounded reads and metadata-first retrieval
- `test_agentic_ontology.py` - Local tests for sprint-1 operator sequences and CQ evaluation

## Quick Test (No Model/API Required)

```bash
~/uvws/.venv/bin/python -m pytest experiments/owl/test_symbolic_memory.py -q
~/uvws/.venv/bin/python -m pytest experiments/owl/test_agentic_ontology.py -q
```

## Optional RLM Run

Requires `ANTHROPIC_API_KEY` in environment.

```bash
~/uvws/.venv/bin/python experiments/owl/rlm_owl_runner.py
```

## Agentic OWL+SHACL Run (Trajectory Logging)

Uses the same Anthropic model pair as `experiments/reasoningbank`:

- Main model: `anthropic/claude-sonnet-4-5-20250929`
- Sub-model: `anthropic/claude-haiku-4-5-20251001`

Run sprint-1 competency questions with trajectory logging:

```bash
~/uvws/.venv/bin/python experiments/owl/agentic_owl_runner.py \
  --ontology-path ontology/core-vocabulary.ttl \
  --shapes-path ontology/core-shapes.ttl \
  --out-dir experiments/owl/results/agentic_sprint1
```

Artifacts:

- `trajectory_*.jsonl` - event stream with `run_start`, `iteration` (reasoning/code/output), `tool_call`, `tool_result`, `run_complete`
- `summary_*.json` - per-CQ outcomes, token usage, leakage metrics, final validation
- `working_graph_*.ttl` - final working ontology graph after CQ sequence
