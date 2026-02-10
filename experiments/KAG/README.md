# KAG: Agentic Search Indexer for Progressive Disclosure

## Overview

KAG is the **write side** of an agentic search system. It builds DoCO-based
knowledge graphs from scientific papers (OCR markdown + figures), producing
SHACL-conformant RDF that gets loaded into a SPARQL graph store. The **read
side** uses bounded view tools to answer competency questions over the enriched
graphs.

```
WRITE (KAG Indexer)                          READ (KAG QA Agent)

Document (PDF/OCR)                           User question
  -> RLM agent builds DoCO graph               -> RLM agent explores graph
    -> op_create_node + SHACL validation          -> g_search / g_section_content / g_node_detail
      -> finalize_graph + enrichment                -> bounded answers with evidence
        -> knowledge_graph.ttl + content_store.jsonl
```

## Status

### Implemented

| Component | File | Sprint |
|---|---|---|
| Deterministic baseline | `agentic_kag_runner.py`, `agentic_doc_agents.py` | 1 |
| Bounded tool surface | `agentic_doc_tools.py` | 1 |
| Symbolic handle store | `symbolic_handles.py` | 1 |
| Memory layers (L0-L2) | `kag_memory.py` | 1 |
| DoCO + KAG ontology | `kag_ontology/kag_document_ext.ttl` | 1 |
| SHACL shapes | `kag_ontology/kag_document_shapes.ttl` | 2-3 |
| RLM context-first runner | `rlm_kag_runner.py` | 2 |
| RLM entrypoint | `run_kag_1.py` | 2 |
| Trajectory dump | `dump_trajectory.py` | 2 |
| Guardrails v3 (finalize_graph gate) | `agentic_doc_tools.py` | 3 |
| SHACL actionable messages | `kag_ontology/kag_document_shapes.ttl` | 3 |
| `op_create_node` (1-call-per-block) | `agentic_doc_tools.py` | 4 |
| `op_set_single_iri_link` (replace links) | `agentic_doc_tools.py` | 4 |
| Full-text persistence (`kag:fullText`) | `agentic_doc_tools.py` | 4 |
| Content store sidecar | `agentic_doc_tools.py` | 4 |
| Deterministic enrichment pipeline | `agentic_doc_tools.py` | 4 |
| Vision indexing (post-agent) | `rlm_kag_runner.py` | 4 |
| QA toolset (5 bounded views) | `kag_qa_tools.py` | 4c |
| QA runner | `rlm_kag_qa_runner.py` | 4c |
| QA entrypoint | `run_kag_qa.py` | 4c |
| QA eval tasks | `kag_qa_tasks.json` | 4c |
| Return schema docs + error classification | `rlm_kag_qa_runner.py` | 4d |

### Validated (Sprint 4)

| Metric | Chemrxiv | PET (PubMed) |
|---|---|---|
| SHACL conforms | **true** | **true** |
| Triples | 1043 | 1133 |
| RLM iterations | 10 | 14 |
| Cost | $0.31 | $0.48 |
| QA correct | 6/6 | 6/6 |
| Enrichment: DEO sections | classified | classified |
| Enrichment: bibliography | structured | structured |
| Enrichment: cross-refs | linked | linked |
| Enrichment: citations | linked | linked |

## Architecture

### Two-Sided Design

**KAG Indexer (write)** takes a document and produces an enriched knowledge graph:

```
document.md (40KB OCR markdown)
  -> DSPy RLM agent (document + blocks + task)
    -> Build tools: op_create_node, op_assert_type, op_set_single_literal,
                    op_add_iri_link, op_set_single_iri_link,
                    validate_graph / finalize_graph
    -> Agent iterates pre-parsed blocks, builds DoCO hierarchy
    -> finalize_graph gate: SHACL conformance required before SUBMIT
    -> Deterministic enrichment (DEO sections, bibliography, cross-refs, citations)
    -> Post-agent vision indexing (figure descriptions via Haiku)
    -> Output: knowledge_graph.ttl + content_store.jsonl
```

**KAG QA Agent (read)** takes a question and explores the enriched graph:

```
User question + graph context (stats + sections)
  -> DSPy RLM agent (context + question)
    -> QA tools: g_section_content, g_node_detail, g_search,
                 g_figure_info, g_node_refs
    -> Agent navigates sections, searches content, follows references
    -> SUBMIT(answer='grounded answer with evidence')
```

### Context-First RLM Pattern

The key insight: **context = data, task = goal**. The full document markdown is
passed as the `document` input to DSPy RLM. Pre-parsed OCR blocks are injected
as a `blocks` variable in the REPL. Tools are limited to graph construction +
SHACL validation.

```python
# Context-first approach
document = Path("document.md").read_text()  # 40KB OCR markdown
blocks = toolset.blocks_for_repl()          # slim block dicts
task = "Build a DoCO graph from `document`..."
rlm = dspy.RLM("document, task, blocks -> answer", tools=[graph_ops...])
result = rlm(document=document, task=task, blocks=blocks)
```

### Enrichment Pipeline (Deterministic, Zero LLM Calls)

After SHACL conformance, `finalize_graph` runs four enrichment passes:

1. **DEO Section Classification** — Maps section titles to DEO types
   (Introduction, Methods, Results, etc.) and identifies References sections
2. **Bibliography Structuring** — Adds `deo:BibliographicReference` type and
   `kag:citationNumber` / `kag:citationText` to entries in References sections
3. **Cross-Reference Linking** — Links paragraphs to figures/tables via
   `kag:refersTo` based on "Figure N" / "Table N" mentions
4. **Citation Linking** — Links paragraphs to bibliography entries via
   `cito:cites` based on `[N]` citation patterns

### Figure Handling (RLM Progressive Disclosure)

Figures follow the handles-not-dumps principle:

```
L0  Caption text + page + bbox       (already in KG, free)
L1  inspect_figure(figure_id)        (vision sub-LM -> kag:imageDescription)
L2  ask_figure(figure_id, question)  (vision sub-LM + question -> answer)
```

At **index time**, the runner calls `inspect_figure` post-agent to generate L1
descriptions stored as `kag:imageDescription`. At **retrieval time**, the QA
agent searches descriptions via `g_figure_info`.

## Tool Surfaces

### Build Tools (6)

| Tool | Purpose |
|---|---|
| `op_create_node(block_id, class_iri)` | Create node from pre-parsed block (auto-sets type, page, bbox, text, contentRef) |
| `op_assert_type(node_iri, class_iri)` | Add rdf:type (for non-block nodes: Document, synthetic Sections) |
| `op_set_single_literal(node, prop, value)` | Set/replace a literal property |
| `op_add_iri_link(s, p, o)` | Add an IRI-valued triple |
| `op_set_single_iri_link(s, p, o)` | Replace all values for (s, p) with a single new one |
| `validate_graph()` / `finalize_graph(answer)` | SHACL validation + enrichment gate |

### QA Tools (5)

| Tool | Purpose |
|---|---|
| `g_section_content(section_iri)` | Children of a section: type, text preview, page |
| `g_node_detail(node_iri)` | Full properties of a single node (text truncated to 500 chars) |
| `g_search(query, limit=10)` | Full-text search over `kag:fullText` |
| `g_figure_info(figure_iri)` | Caption + page + image description + referring paragraphs |
| `g_node_refs(node_iri)` | Bidirectional relationships: citations, cross-references, inverses |

## Namespaces

| Prefix | URI | Purpose |
|---|---|---|
| `doco:` | `http://purl.org/spar/doco/` | Document, Section, SectionTitle, Paragraph, Table, Figure, Formula |
| `deo:` | `http://purl.org/spar/deo/` | Caption, BibliographicReference, Introduction, Methods, Results, etc. |
| `cito:` | `http://purl.org/spar/cito/` | Citation typing (`cito:cites`) |
| `kag:` | `http://la3d.local/kag#` | contains, containsAsHeader, describes, hasContentRef, fullText, citationNumber, citationText, refersTo, pageNumber, hasBBox, mainText, imageDescription, imagePath |
| `ex:` | `http://la3d.local/kag/doc/` | Instance namespace |

## SHACL Constraints

- Document must contain >=1 Section (via `kag:contains`)
- Section must have exactly 1 SectionTitle (via `kag:containsAsHeader`) and >=1 child
- All content nodes (Paragraph, Figure, Table, Formula, Caption) must be inside a Section only
- Caption must describe exactly 1 Figure or Table (via `kag:describes`)
- `hasContentRef` pattern: `kind:` + 16 hex chars (SHA256 hash)
- `pageNumber` required on all Section and content nodes (`xsd:integer`, >=1)
- `hasBBox` required on all Figures

## File Structure

```
KAG/
├── README.md                          # This file
│
├── Core
├── agentic_kag_runner.py              # Run 0: deterministic baseline runner
├── agentic_doc_agents.py              # Run 0: deterministic structure parser
├── agentic_doc_tools.py               # Bounded tool surface (build: op_* + validate + enrich)
├── rlm_kag_runner.py                  # Run 1: DSPy RLM context-first runner
├── kag_memory.py                      # Memory layers (L0-L2)
├── symbolic_handles.py                # Handle-based blob store
├── dump_trajectory.py                 # Trajectory JSONL -> markdown report
│
├── QA
├── kag_qa_tools.py                    # Read-only QA toolset (5 bounded views)
├── rlm_kag_qa_runner.py               # QA runner: one RLM call per question
├── kag_qa_tasks.json                  # Eval tasks for QA agent
│
├── Entrypoints
├── run_kag_0.py                       # Run deterministic baseline
├── run_kag_1.py                       # Run RLM context-first agent
├── run_kag_qa.py                      # Run QA agent over enriched graph
│
├── Ontology
├── kag_ontology/
│   ├── kag_document_ext.ttl           # DoCO extensions (handles, bbox, fullText, citations, etc.)
│   └── kag_document_shapes.ttl        # SHACL shapes for validation
│
├── Reports
├── reports/
│   ├── sprint2_vision_shacl_feedback.md
│   ├── sprint3_guardrails_analysis.md
│   ├── sprint4_quality_enrichment.md
│   ├── sprint4c_qa_agent_analysis.md
│   └── sprint4d_fix_logging_return_schemas.md
│
├── Test Data
├── test_data/
│   ├── chemrxiv_ocr/                  # 8-page chemistry paper (page_*.md + document.md)
│   ├── chemrxiv_figures/              # Cropped figure PNGs (6 files, 468KB)
│   ├── pet_test_ocr/                  # PET imaging paper
│   ├── pet_test_figures/              # PET figure PNGs
│   ├── omd_test_ocr/                  # Materials science paper
│   └── omd_test_figures/              # OMD figure PNGs
│
├── Tests
├── test_rlm_compliance.py             # Leakage + correctness tests (baseline)
├── test_structure_parser.py           # Structure parsing tests
│
└── results/                           # Run outputs (gitignored)
    └── <run_name>_<timestamp>/
        ├── knowledge_graph.ttl        # SHACL-conformant DoCO graph
        ├── content_store.jsonl        # Full text keyed by hasContentRef
        ├── trajectory.jsonl           # Full RLM iteration trace
        └── summary.json               # Metrics, costs, validation
```

## Running

```bash
source ~/uvws/.venv/bin/activate

# Build: RLM context-first agent (requires ANTHROPIC_API_KEY)
python experiments/KAG/run_kag_1.py \
  --ocr-dir experiments/KAG/test_data/chemrxiv_ocr \
  --out-dir experiments/KAG/results

# QA: answer questions over an enriched graph
python experiments/KAG/run_kag_qa.py \
  --graph-dir experiments/KAG/results/sprint4b_chemrxiv_20260210T152308Z \
  --questions experiments/KAG/kag_qa_tasks.json \
  --paper chemrxiv

# Dump trajectory as markdown report
python experiments/KAG/dump_trajectory.py experiments/KAG/results/run_kag_1_*/

# Query the output graph
python -c "
from rdflib import Graph
g = Graph()
g.parse('experiments/KAG/results/sprint4b_chemrxiv_20260210T152308Z/knowledge_graph.ttl')
for row in g.query('''
    PREFIX doco: <http://purl.org/spar/doco/>
    PREFIX kag: <http://la3d.local/kag#>
    SELECT ?title WHERE {
        ?sec a doco:Section .
        ?sec kag:containsAsHeader ?st .
        ?st kag:mainText ?title .
    }
'''):
    print(row.title)
"
```

## Experiment History

### Sprint 1: Deterministic Baseline

Procedural pipeline (no LLM). Proves tool surface, SHACL validation,
trajectory logging. Conforms on simple documents but uses hardcoded heuristics
for section assignment and caption linking.

### Sprint 2: RLM Context-First Agent

Three iterations to reach 100% SHACL conformance. Key insight:
context = document data, task = goal (not procedural instructions).
Agent self-corrects when it gets real SHACL violation feedback.

### Sprint 3: Guardrails v3

`finalize_graph` gate: agent cannot SUBMIT until SHACL conforms.
Actionable SHACL messages with fix instructions. Section grouping rules
for pre-section blocks. Both papers: 100% conformance, 10-14 iters, $0.31-$0.48.

### Sprint 4: Quality & Enrichment

`op_create_node`: 1-call-per-block auto-sets type/page/bbox/mainText/fullText/contentRef.
Full-text persistence via `kag:fullText`. Content store sidecar (`content_store.jsonl`).
Deterministic enrichment pipeline: DEO section classification, bibliography
structuring, cross-reference linking, citation linking. Vision indexing post-agent.

### Sprint 4c: QA Agent

5-tool read surface over enriched graphs. Pre-assembled context (stats + sections).
12/12 correct answers across both papers. Error classification for sandbox crashes
and tool binding errors.

### Sprint 4d: Return Schema Docs & Fixes

Agent-friendly return value documentation in tool docstrings. Error classification
in trajectory logging (`has_error`, `error_type`). Sandbox crash prevention:
never re-raise in tool wrappers.

## Next Steps

**Sprint 5: Multi-Ontology Entity Extraction**

Extend from single G_doc to a three-layer graph architecture:

| Layer | Ontology Stack | Purpose |
|---|---|---|
| G_doc (existing, read-only) | DoCO + DEO + KAG | Document structure |
| G_entity (new) | SIO + QUDT | Extracted entities and measurements |
| G_claim (new) | SIO + PROV + CiTO | Scientific claims and evidence |

Key elements:
- Vendor SIO + QUDT subsets with SHACL shapes
- Multi-graph workspace with GraphProfile namespace contracts
- Generic `op_*` tools with `graph` parameter for layer routing
- Ontology sense cards (SIO/QUDT/PROV) in task prompt
- Cross-graph provenance links (`prov:wasDerivedFrom` to G_doc spans)

## References

- Original KAG: https://arxiv.org/html/2409.13731v3
- DoCO: http://purl.org/spar/doco/ (Document Components Ontology)
- DEO: http://purl.org/spar/deo/ (Discourse Elements Ontology)
- SIO: http://semanticscience.org/ (Semanticscience Integrated Ontology)
- QUDT: http://qudt.org/ (Quantities, Units, Dimensions and Types)
- RLM patterns: `../owl/` and `../reasoningbank/`
- DSPy RLM: `dspy.predict.rlm` (DSPy 3.1.3)
