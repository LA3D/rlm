# Owl + RLM Symbolic Memory (Prototype)

This directory is a scaffold for combining strict RLM-style symbolic execution with a traditional symbolic memory system built in Python using `owlready2` and `rdflib`.

This is the next-generation direction for a UniProt-like scientific literature graph constructor (from Markdown), with explicit provenance/evidence/curation layers:

- From: a workflow that emits graphs in a mostly fixed sequence.
- To: an agentic system that can *retrieve*, *construct*, *repair*, and *curate* graphs over multiple ontologies with deterministic judges and RLM-safe progressive disclosure.

The intent is not “RAG with extra steps”. The intent is RLM-faithful agent memory:

- The user prompt `P` itself is a symbolic object in the environment.
- The model must write recursive code (executed) to understand/transform `P`.
- Tools and subcalls must return into symbolic variables without leaking payloads into the model’s context window.

## Use Case: Paper KG Construction From Markdown

The motivating use case for these experiments is:

- Input: scientific paper content in Markdown (plus optional structured metadata like DOI/PMID, authors, venue, year).
- Output: a set of RDF named graphs that separate "what the paper says" from "why we believe it" and "how it was curated".

This mirrors the way curated resources (e.g., UniProt-style pipelines) structure knowledge:

- Assertions are never "floating": each fact is grounded to evidence (document spans, figures/tables, citations).
- Curation is first-class: each assertion carries provenance, curator decisions, and quality signals (human or agent).
- Multiple fixed ontologies are used simultaneously: provenance ontologies, evidence/justification ontologies, curation/status ontologies, and domain ontologies (biology/chemistry/etc).

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

## Graph Model: Multi-Graph, Named-Graph First

The experiments in this directory assume the “real” system will be multi-step and multi-ontology. Model that explicitly as multiple graphs (even if an MVP uses a single in-memory `rdflib.Graph`).

Minimum "paper KG" split:

- `G_doc` (DocumentGraph): Markdown structure (sections/paragraphs/tables/figures), stable span ids, citation anchors, and pointers to blob windows.
- `G_evidence` (EvidenceGraph): evidence items and justifications that link facts to `G_doc` spans (and optionally to external references).
- `G_curation` (CurationGraph): agent/human decisions, status, confidence, disagreements, review tasks, and provenance over edits.
- `G_fact` (FactGraph): extracted assertions about entities/events/relations, grounded to `G_evidence`.

Supporting graphs:

- `G_vocab` (Vocabulary): SKOS concepts, labels, alignments, synonym sets.
- `G_onto` (Ontology/TBox): fixed ontologies + any synthetic schema needed for the experiment.
- `G_shapes` (Judges): SHACL bundles used as deterministic validation and regression tests.
- `G_mem` (Agent memory): principles/episodes/procedures/judge rules (stored symbolically, payload behind handles).

This aligns with:

- UniProt-like curated extraction across multiple fixed ontologies and many named graphs.
- Earlier workflow prototypes (document graph + schema + instances), while making the "agentic" aspects explicit.

## Mapping: Graph Profiles And Alignment Contracts

Different graphs can use different ontologies for their instances. The agent needs an explicit, symbolic routing layer that answers:

- Which ontologies and namespaces are "allowed" in graph `G`?
- What are the expected root types and required links for `G`?
- When two graphs use different ontologies, what mappings and transforms are allowed to bridge them?

Model that as two first-class, queryable objects (stored in `G_mem` as small symbolic fields, with any long documentation behind handles):

- `GraphProfile(G)`: per-graph contract
- `AlignmentProfile(A)`: cross-graph contract

### GraphProfile(G): Per-Graph Contract

Each named graph gets a profile describing its "local language":

- `ontologies`: the ontology set in-scope for instances in `G` (imports + prefix map + allowed namespaces)
- `targets`: expected root classes (what "good" looks like for that graph)
- `required_links`: required cross-graph grounding edges (for example, `G_fact` -> `G_evidence` -> `G_doc`)
- `forbidden_patterns`: namespaces/predicates/classes that should not appear in that graph (prevents ontology bleed)
- `judges`: the SHACL bundles that validate `G` locally

### AlignmentProfile(A): Cross-Graph Contract

When `G_fact` uses one domain ontology and `G_evidence` or `G_curation` uses another, alignment is not "freeform". Keep it explicit:

- `canonical_core`: a small shared hub vocabulary for interoperability (often `prov` plus a core domain like `sio`)
- `mappings`: allowed semantic bridges (`owl:equivalentClass`, `rdfs:subClassOf`, property alignments, SKOS mappings)
- `materializations`: allowed procedural transforms (SPARQL `CONSTRUCT` rules) to normalize into the canonical view when OWL alone is not sufficient
- `cross_judges`: SHACL bundles that validate cross-graph invariants (grounding, provenance completeness, mapping consistency)

### Agent Runtime: How It Uses Profiles (RLM-Strict)

The agent should not "read the ontology" to decide what to do. It should:

- Load `GraphProfile(G)` metadata (symbolic, small) for the graph it is operating on.
- Run scoped SPARQL and scoped SHACL; tools return compact signatures and handles, not raw payload dumps.
- When bridging ontologies, consult `AlignmentProfile(A)` to pick an allowed mapping/materialization operator and then re-validate (local + cross-graph).

## KAG Parallels (Knowledge-Augmented Generation)

KAG (Knowledge Augmented Generation) describes a knowledge-enhanced LLM service framework with:

- chunk/knowledge mutual indexing,
- knowledge alignment to reduce noisy extraction,
- schema-constrained construction,
- mixed reasoning guided by logical forms.

This experiment maps those ideas into an RLM-safe, handle-first architecture:

- **Mutual indexing:** `G_fact` is grounded to `G_evidence`, which is grounded to `G_doc` spans/windows (handles). This gives "graph-first inverted indices" without dumping raw text into context.
- **Alignment:** `AlignmentProfile(A)` enumerates allowed semantic bridges (OWL/SKOS) and allowed procedural bridges (SPARQL `CONSTRUCT` materializations). The agent is not allowed to invent alignments ad hoc.
- **Schema constraints:** SHACL bundles in `G_shapes` (published via `role:validation` resources) are the hard gate/judge for construction and repair; OWL is used for meaning and reuse, not for pass/fail.
- **Logical-form guidance:** the agent's "logical forms" are `CQ` ASK queries, SHACL violation signatures, and profile-published mapping/materialization recipes; it composes `retrieval`, `reasoning`, and `planning` operators over those symbolic objects.

## Cross-Ontology Reuse, Partitioning, And Alignment

In a UniProt-like setting you will use multiple ontologies at once: provenance, evidence, curation/status, and one or more domain ontologies. If you allow free mixing, graphs become hard to validate and hard to query. The design target is:

- **vocabulary reuse by default** (avoid minting new terms),
- **partitioned graphs** with clear local "languages",
- **alignment as a governed artifact**, not ad hoc model invention.

### Partitioning: Keep Graphs "Pure"

Treat each named graph as having a local language defined by its `GraphProfile(G)`:

- `allowed_namespaces`: which namespaces are allowed for instances/predicates in the graph.
- `targets`: which root types you expect to exist.
- `required_links`: what must connect to other graphs (e.g., `G_fact -> G_evidence -> G_doc`).

To keep reuse clean, introduce explicit bridge graphs:

- `G_align` (AlignmentGraph): mapping assertions and alignment metadata live here.
- `G_view` (optional): materialized canonical views used for query answering, derived from source graphs by approved `CONSTRUCT` recipes.

Keep ontology artifacts themselves as separate resources (or named graphs) and avoid copying TBox axioms into fact graphs.

### Alignment Contract: What The Agent Is Allowed To Do

Alignment must be explicit and auditable. Represent it as an `AlignmentProfile(A)` published like a PROF profile pack:

- `role:mapping`: the allowed semantic and procedural bridges.
- `role:validation`: SHACL bundles for cross-graph invariants.
- `role:guidance`: optional human documentation (handle-first; rarely read).

Alignment operators fall into two categories:

- **Declarative semantic bridges:** `owl:equivalentClass`, `rdfs:subClassOf`, `owl:equivalentProperty`, `rdfs:subPropertyOf`, and SKOS mapping predicates for concept schemes.
- **Procedural bridges:** SPARQL `CONSTRUCT` recipes that normalize into a canonical core view when OWL/SKOS is insufficient.

The agent should only apply bridges that are listed in the active `AlignmentProfile(A)`; it should not invent new mappings during a run.

### Vocabulary Reuse Policy (Agent-Facing)

The agent should bias toward reusing existing terms and linking vocabularies at the vocabulary level. In practice:

- Reuse existing classes/properties when a correct term exists.
- Prefer terms from stable, resolvable namespaces with clear versioning and metadata hygiene (avoid "import rot").
- Pin ontology artifacts/versions via handles (or local paths) in `GraphProfile(G)` / `AlignmentProfile(A)` so runs are reproducible and RLM-safe.

Mint new terms only when:

- no reusable term exists,
- alignment would be lossy/incorrect for the use case,
- and you can define a stable URI + minimal axioms + labels/definitions + mapping hooks.

### RLM-Safe Alignment Workflow

At runtime, the agent should:

- Load `GraphProfile(G)` (symbolic metadata) for the current graph.
- Retrieve candidates via scoped SPARQL over ontology graphs and `G_align` (no ontology prose dumps).
- If bridging is needed, consult `AlignmentProfile(A)` and apply an approved mapping/materialization operator.
- Re-validate with SHACL (local + cross-graph) and iterate repair using typed operators and violation signatures.

## Ontology Load Set (UniProt-Like Paper Curation)

For the scientific-paper curation use case, load multiple ontologies from `ontology/` into memory for different purposes. Keep them partitioned by purpose (separate named graphs or separate in-memory `rdflib.Graph` handles) and expose them to the agent via `GraphProfile(G)` / `AlignmentProfile(A)` instead of dumping ontology text.

Recommended baseline load set for this repo:

- **Scientific domain spine:** SIO (`ontology/sio/*`) as the base vocabulary for scientific entities, measurements, propositions, and evidence relationships.
- **Provenance:** PROV-O (`ontology/prov.ttl`) for activity/agent attribution and lineage (especially in `G_curation` and for grounding edges).
- **Profile/capability navigation:** PROF + roles (`ontology/prof.ttl`, `ontology/role.ttl`) for publishing graph profiles, mapping packs, SHACL packs, and discovery affordances.
- **Alignment metadata:** SEMAPV (`ontology/sssom/semapv.owl`) for describing mapping processes, review, and chaining/inversion provenance in `G_align`.
- **Curation lifecycle metadata:** PAV (`ontology/pav.rdf`) for lightweight provenance/authoring/versioning/curation properties on artifacts (created/curated/authored/imported).
- **Citation semantics:** CiTO (`ontology/cito.ttl`) for typed citation relations (e.g., cites-as-data-source, discusses, is-discussed-by) and citation characterization.
- **Bibliographic entities:** BIBO (`ontology/bibo.owl`) for publications, identifiers, and bibliographic types/status.

Rule of thumb:

- Use **SIO** for the scientific "what".
- Use **PROV + PAV** for the "who/when/how curated/derived".
- Use **CiTO + BIBO** for literature/citation structure and typed relationships to the scholarly record.
- Use **PROF (+ role vocabulary)** to publish machine-discoverable profile packs and to drive progressive disclosure.
- Use **SEMAPV** to make cross-ontology alignment decisions auditable and queryable by method/review status.

## SSSOM/SEMAPV For Alignment Provenance (G_align)

This repo includes `ontology/sssom`, which primarily provides SEMAPV (Semantic Mapping Vocabulary). SEMAPV is designed to accompany SSSOM-style mappings by providing a vocabulary for mapping processes, review, and metadata.

In this architecture, use SEMAPV to make alignment *agentic and auditable*:

- Keep alignment assertions and mapping metadata in `G_align` (the AlignmentGraph).
- Represent direct semantic bridges as lightweight edges when possible:
  - OWL bridges for schema alignment (`owl:equivalentClass`, `rdfs:subClassOf`, etc.)
  - SKOS mapping relations for concept schemes (`skos:exactMatch`, `skos:closeMatch`, etc.)
- When you need reviewability and lifecycle provenance, reify mappings as first-class records and annotate with SEMAPV/PROV:
  - `semapv:Mapping` as the mapping entity (subject, predicate, object)
  - `semapv:MappingActivity` / `semapv:Matching` / `semapv:ManualMappingCuration` / `semapv:LogicalReasoningMatching` / `semapv:MappingReview` to describe how a mapping was created and whether it was reviewed
  - connect mapping activities into `G_curation` provenance using `prov:Activity`/`prov:wasAssociatedWith`/`prov:hadRole` for agent/human attribution

Agent-facing benefit: instead of treating all mappings as equal, the agent can query `G_align` for mappings by method, review status, or chaining/inversion provenance, and choose safer bridges first.

## Sprint 2: Paper-To-KG Construction Trajectory (UniProt-Like)

Sprint 1 focused on RLM-safe symbolic guardrails, constraint-driven repair loops, and trajectory logging (tool calls + handles + signature deltas). Sprint 2 extends the trajectory to a UniProt-like scientific paper curation setting and incorporates lessons from ReasoningBank:

- SPARQL-first agentic search (no vectors) with progressive disclosure.
- Layer-cake context (L0/L1/L2) to avoid ontology dumps and reduce SHACL report reads.
- Deterministic judges (CQs as ASK + SHACL) to make runs comparable and debuggable.
- Judge architecture lessons: return compact signatures + handles, gate report text reads, and use signature deltas to drive repair selection.

### Environment: Multi-Graph State

Sprint 2 uses explicit named graphs (or separate in-memory `rdflib.Graph` handles) to avoid ontology bleed and to enable scoped queries/judges:

- `G_doc`: Markdown document graph with spans/sections/tables/figures and stable span ids that point to bounded `WindowRef` handles.
- `G_biblio`: bibliographic entities (BIBO) + citation relationships (CiTO).
- `G_evidence`: evidence items (SIO) that link facts to document spans and/or citations.
- `G_fact`: extracted scientific claims/propositions (SIO spine) grounded to `G_evidence`.
- `G_curation`: provenance and curation records (PROV + PAV), including agent/human attribution for edits and derived artifacts.
- `G_align` (optional): alignment bridges and mapping provenance (OWL/SKOS + SEMAPV).

### Sprint 2 Competency Questions (Deterministic ASK)

The run is only considered successful when these are true (each query is scoped to the relevant graph(s)):

1. **Doc grounding:** every claim in `G_fact` has at least one evidence pointer in `G_evidence` that resolves to a `G_doc` span (`WindowRef` handle exists).
2. **Evidence semantics:** evidence is typed as SIO evidence and is explicitly linked as evidence-for (supporting/refuting/disputing allowed).
3. **Bibliography grounding:** when evidence is citation-backed, it links to a `G_biblio` bibliographic entity (BIBO) and the citation intent is typed (CiTO).
4. **Curation provenance:** every new/changed claim has a corresponding `prov:Activity`/agent attribution in `G_curation`, and the produced artifact has minimal PAV metadata.
5. **Graph purity:** each graph uses only allowed namespaces as declared by `GraphProfile(G)` (no CiTO/BIBO leaking into `G_fact`, no domain assertions into `G_doc`, etc.).

### SHACL Packs: Local + Cross-Graph Judges

Use separate SHACL bundles to keep violations local, interpretable, and satisfiable:

- `Shapes(G_doc)`: span ids, section hierarchy, required `WindowRef` links.
- `Shapes(G_biblio)`: paper/citation objects are well-formed (title/id/status as needed).
- `Shapes(G_evidence)`: evidence items have required links to spans/citations and evidence-for relations.
- `Shapes(G_fact)`: claim/proposition minimal structure; cross-pack requires evidence grounding.
- `Shapes(G_curation)`: PROV activity has agent + role; PAV stamps exist on outputs.
- `Shapes(cross)`: "no orphan claims", "no unresolvable evidence spans", namespace allowlists per graph, and any required cross-graph invariants.

### Minimal Operator Set (Sprint 2)

Keep the operator set small but sufficient to satisfy judges without dumping Markdown or ontology text:

- `doc_index(spanspec)`: create/lookup span nodes and attach bounded `WindowRef` handles.
- `bibo_upsert_paper(meta)`: create paper entity + identifiers.
- `cito_link(citing, cited, cito_predicate)`: add typed citation intent edges.
- `fact_assert_claim(template)`: create a claim/proposition in `G_fact`.
- `evidence_attach(claim, span_ref, evidence_kind)`: create evidence item and connect it to claim and doc span (and optionally citation).
- `prov_record_activity(delta, agent_id, role)`: record curation/extraction activity and link affected nodes.
- `pav_stamp(artifact, authored/curated/created/imported...)`: stamp lightweight curation/versioning metadata.
- `validate(pack_or_graph)`: SHACL validate returning `conforms`, violation signatures, signature deltas, and handles to any full reports.

### Trajectory Pattern (Agentic But Judgeable)

Runs should follow a consistent high-level order (agentic behavior shows up in repair/operator selection):

1. Build `G_doc` span index (bounded reads only; progressive disclosure).
2. Populate `G_biblio` (paper + citations) and typed CiTO edges.
3. Assert a small set of claims in `G_fact` (2-3 is enough for the toy run).
4. Attach evidence in `G_evidence` linking claims to spans (and citations when applicable).
5. Record curation/provenance in `G_curation` (PROV activity + PAV stamps).
6. Validate local packs, then cross-pack; repair until all CQs and SHACL packs pass or timeout.

### Sprint 1 Lessons To Preserve

- Always operate on symbolic objects and handles; never dump full SHACL report text or long Markdown into model context.
- Use signature deltas to measure progress and to select repair operators; throttle `handle_read_window` and report text reads.
- Keep CQ and validation scope local (avoid cross-CQ query leakage) and use global signature hints only as a last resort.
- Prefer "closure" operators that patch missing structural requirements deterministically (typed literals, required links) rather than relying on free-form text reasoning.

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

## Retrieval: Evidence-Grounded Agentic Search (No Vectors)

The target retrieval mechanism is SPARQL-first agentic search with progressive disclosure:

- Retrieval returns *symbolic ids and compact metadata* (counts, signatures, node IRIs), not payloads.
- Every assertion in `G_fact` should be grounded to evidence in `G_evidence`, which in turn points into `G_doc`:
  - e.g., `prov:wasDerivedFrom` pointing to document span ids, plus a `WindowRef` handle for bounded inspection.
- The agent uses deterministic graph queries to identify candidates, then pulls bounded evidence windows via handles only when needed.

Vectors are intentionally not required. If any indexing exists, it returns ids only and is always secondary to symbolic search.

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

## Layer Cake Context (ReasoningBank L0/L1 Port)

ReasoningBank demonstrated that a budgeted “layer cake” context works for ontology-backed query construction (e.g., UniProt) without dumping raw ontology text.

For ontology construction/curation, port the same idea:

- L0 (sense): inventory + affordances (which named graphs exist, what each graph is for, what target classes/paths exist, scale hints).
- L1 (constraints/logic): compiled rules derived deterministically from ontologies and judges (SHACL):
  - targets (`sh:targetClass`, `sh:targetNode`), required properties, datatypes/nodeKinds, cardinalities, enums/patterns,
  - materialized closure affordances via SPARQL (`subClassOf*`, qualified constraints),
  - operator feasibility map (which constraint types are satisfiable with current ops).
- L2 (procedures): retrieved principles/episodes for repair strategies and anti-patterns.

Important: L1 is not “ontology prose”. It is a compact, executable affordance map.

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
