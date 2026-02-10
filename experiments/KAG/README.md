# KAG: Agentic Search Indexer for Progressive Disclosure

## Overview

KAG is the **write side** of an agentic search system. It builds DoCO-based
knowledge graphs from scientific papers (OCR markdown + figures), producing
SHACL-conformant RDF that gets loaded into a SPARQL graph store. The **read
side** uses the same RLM progressive disclosure pattern (from `experiments/
reasoningbank/`) to query the store and answer questions.

```
WRITE (KAG Indexer)                          READ (RLM Retrieval)

Document (PDF/OCR)                           User question
  -> RLM agent builds DoCO graph               -> RLM agent queries graph store
    -> SHACL validation loop                     -> g_stats / g_sections / g_search
      -> SPARQL graph store  ─────────────>        -> bounded answers with evidence

ReasoningBank provides strategies for BOTH sides
```

## Status

### Implemented

| Component | File | Status |
|---|---|---|
| Deterministic baseline | `agentic_kag_runner.py`, `agentic_doc_agents.py` | Done |
| Bounded tool surface | `agentic_doc_tools.py` | Done |
| Symbolic handle store | `symbolic_handles.py` | Done |
| Memory layers (L0-L2) | `kag_memory.py` | Done |
| DoCO + KAG ontology | `kag_ontology/kag_document_ext.ttl` | Done |
| SHACL shapes | `kag_ontology/kag_document_shapes.ttl` | Done |
| **RLM context-first runner** | **`rlm_kag_runner.py`** | **Done** |
| RLM entrypoint | `run_kag_1.py` | Done |
| Trajectory dump | `dump_trajectory.py` | Done |
| DSPy patches | `../reasoningbank/prototype/tools/dspy_patches.py` | Done |

### Validated (Run 3, 2026-02-10)

| Metric | Value |
|---|---|
| SHACL conforms | **true** |
| Violations | 0 |
| Triples | 741 |
| Nodes | 126 (1 Document, 11 Sections, 78 Paragraphs, 9 Figures, 9 Captions, 3 Tables, 4 Formulas) |
| RLM iterations | 9 / 20 max |
| Cost | $0.30 |
| Leakage | 0 large returns, 0 stdout chars |

### Planned

| Component | Description |
|---|---|
| `inspect_figure` tool | Vision sub-LM describes figures at index time |
| `ask_figure` tool | Vision sub-LM answers questions about figures at retrieval time |
| Local SPARQL mode | `SPARQLToolsV2` with `graph.query()` backend |
| Named graph store | Multiple documents per store, one graph per document |
| ReasoningBank integration | Seed strategies from run trajectories, closed loop |
| Retrieval agent | RLM agent with SPARQL tools pointed at graph store |

## Architecture

### Two-Sided Design

**KAG Indexer (write)** takes a document and produces a knowledge graph:

```
document.md (40KB OCR markdown)
  -> DSPy RLM agent (context=document, task=goal)
    -> Tools: op_assert_type, op_set_single_literal, op_add_iri_link,
              validate_graph, graph_stats
    -> Agent parses OCR tags, builds DoCO hierarchy, validates with SHACL
    -> Output: knowledge_graph.ttl (SHACL-conformant)
```

**RLM Retrieval (read)** takes a question and queries the graph:

```
User question
  -> RLM agent (progressive disclosure)
    -> L0: g_stats()           -> 741 triples, 11 sections, 9 figures
    -> L1: g_sections()        -> find "Reaction Kinetics" on p5
    -> L2: g_section_content() -> 10 nodes with text previews
    -> L2: g_search("TCNE")    -> 6 hits across the paper
    -> L1: g_captions()        -> Figure 5 = kinetic traces
    -> Synthesize answer from bounded retrievals
```

### Context-First RLM Pattern

The key insight: **context = data, task = goal**. The full document markdown is
passed as the `document` input to DSPy RLM. The agent explores it via REPL code
(`print(document[:2000])`, regex, split) rather than through OCR exploration
tools. Tools are limited to graph construction + SHACL validation.

This replaces the original approach where `context` contained procedural
instructions telling the LLM how to build the graph step-by-step.

```python
# Old approach (broken heuristics)
context = "1) Use ocr_list_blocks() to see all blocks..."
task = "Build a DoCO graph using ocr_list_blocks..."

# New approach (context-first)
document = Path("document.md").read_text()  # 40KB OCR markdown
task = "Build a DoCO graph from `document`. Namespaces: ... SHACL: ..."
rlm = dspy.RLM("document, task -> answer", tools=[graph_ops...])
result = rlm(document=document, task=task)
```

### Figure Handling (RLM Progressive Disclosure)

Figures follow the handles-not-dumps principle:

```
L0  Caption text + page + bbox       (already in KG, free)
     -> "Figure 3. Dynamic equilibrium of TMAnR..."

L1  inspect_figure(figure_id)         (tool call -> vision sub-LM)
     -> "Bar chart showing K_eqCT values for 4 TMAnR variants..."

L2  ask_figure(figure_id, question)   (tool call -> vision sub-LM + question)
     -> "K_eqCT for TMAnnBu is approximately 80 M^-1"
```

At **index time**, KAG calls `inspect_figure` to generate L1 descriptions
stored as `kag:imageDescription` in the KG. At **retrieval time**, the agent
searches descriptions via SPARQL, and calls `ask_figure` only for deeper
follow-up.

### Memory (ReasoningBank Pattern)

Strategies extracted from indexing trajectories, stored as `Item` objects:

| src | Example |
|---|---|
| `seed` | "Sections need hasContentRef (kind: + 16 hex SHA256)" |
| `failure` | "validate_graph needs exact file paths, not guessable names" |
| `success` | "Parse sub_title blocks to identify sections, assign content by position" |
| `pattern` | "table_title captions describe Tables, not Figures" |
| `observation` | "Figure 1 shows reaction scheme + crystal structures" |

The closed loop:

```
1. RETRIEVE   mem.search("document graph DoCO sections")     -> [metadata]
2. INJECT     L0(doc sense) + L1(schema) + L2(strategies)    -> enriched task
3. RUN        RLM(document=md, task=goal, tools=graph_ops)   -> KG + trajectory
4. JUDGE      validate_graph() -> conforms? + structural checks
5. EXTRACT    from trajectory: what worked, what failed       -> [Item(...)]
6. STORE      mem.consolidate(items, dedup=True)              -> ready for next doc
```

## DoCO-Based Document Graphs

We use SPAR's DoCO ontology with a local KAG extension namespace. Do not rely
on network dereferencing of `owl:imports` -- load vendored files:

- `ontology/doco.ttl` -- Document Components Ontology
- `ontology/deo.ttl` -- Discourse Elements Ontology
- `experiments/KAG/kag_ontology/kag_document_ext.ttl` -- KAG extensions
- `experiments/KAG/kag_ontology/kag_document_shapes.ttl` -- SHACL shapes

### Namespaces

| Prefix | URI | Purpose |
|---|---|---|
| `doco:` | `http://purl.org/spar/doco/` | Document, Section, SectionTitle, Paragraph, Table, Figure, Formula |
| `deo:` | `http://purl.org/spar/deo/` | Caption |
| `kag:` | `http://la3d.local/kag#` | contains, containsAsHeader, describes, hasContentRef, pageNumber, order, hasBBox, mainText |
| `ex:` | `http://la3d.local/kag/doc/` | Instance namespace |

### SHACL Constraints

- Document must contain >=1 Section (via `kag:contains`)
- Section must have exactly 1 SectionTitle (via `kag:containsAsHeader`) and >=1 child
- All content nodes must be inside a Section
- Caption must describe exactly 1 Figure or Table (via `kag:describes`)
- `hasContentRef` pattern: `kind:` + 16 hex chars (SHA256 hash)
- `pageNumber` required on all nodes (`xsd:integer`, >=1)
- `hasBBox` required on all content nodes including Figures

## File Structure

```
KAG/
├── README.md                          # This file
│
├── Core (Implemented)
├── agentic_kag_runner.py              # Run 0: deterministic baseline runner
├── agentic_doc_agents.py              # Run 0: deterministic structure parser
├── agentic_doc_tools.py               # Bounded tool surface (OCR + graph ops)
├── rlm_kag_runner.py                  # Run 1: DSPy RLM context-first runner
├── kag_memory.py                      # Memory layers (L0-L2)
├── symbolic_handles.py                # Handle-based blob store
├── dump_trajectory.py                 # Trajectory JSONL -> markdown report
│
├── Entrypoints
├── run_kag_0.py                       # Run deterministic baseline
├── run_kag_1.py                       # Run RLM context-first agent
│
├── Ontology
├── kag_ontology/
│   ├── kag_document_ext.ttl           # DoCO extensions (handles, bbox, etc.)
│   └── kag_document_shapes.ttl        # SHACL shapes for validation
│
├── Test Data
├── test_data/
│   ├── chemrxiv_ocr/                  # 8-page chemistry paper (page_*.md + document.md)
│   ├── chemrxiv_figures/              # Cropped figure PNGs (6 files, 468KB)
│   ├── pet_test_ocr/                  # PET imaging paper
│   └── omd_test_ocr/                  # Materials science paper
│
├── Tests
├── test_rlm_compliance.py             # Leakage + correctness tests (baseline)
├── test_structure_parser.py           # Structure parsing tests
│
└── results/                           # Run outputs (gitignored)
    └── run_kag_1_<timestamp>/
        ├── knowledge_graph.ttl        # SHACL-conformant DoCO graph
        ├── trajectory.jsonl           # Full RLM iteration trace
        └── summary.json               # Metrics, costs, validation
```

## Running

```bash
source ~/uvws/.venv/bin/activate

# Run 0: Deterministic baseline
python experiments/KAG/run_kag_0.py

# Run 1: RLM context-first agent (requires ANTHROPIC_API_KEY)
python experiments/KAG/run_kag_1.py \
  --ocr-dir experiments/KAG/test_data/chemrxiv_ocr \
  --out-dir experiments/KAG/results

# Dump trajectory as markdown report
python experiments/KAG/dump_trajectory.py experiments/KAG/results/run_kag_1_*/

# Query the output graph
python -c "
from rdflib import Graph
g = Graph()
g.parse('experiments/KAG/results/run_kag_1_*/knowledge_graph.ttl')
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

### Run 0: Deterministic Baseline

Procedural pipeline (no LLM). Proves tool surface, SHACL validation,
trajectory logging. Conforms on simple documents but uses hardcoded heuristics
for section assignment and caption linking.

### Run 1: RLM Context-First (3 iterations)

| | Run 1 | Run 2 | Run 3 |
|---|---|---|---|
| Context | Procedural instructions | Document markdown | Document markdown |
| Task | "use ocr_list_blocks..." | Goal + SHACL constraints | Goal + SHACL + **validation paths** |
| Conforms | false (20 violations) | false (9 violations) | **true (0 violations)** |
| Triples | 831 | 842 | 741 |
| Iterations | 15 | 15 | 9 |
| Cost | $0.61 | $0.61 | $0.30 |
| Trajectory | empty (logging bug) | full (bug fixed) | full |

Key learnings:
- Context = data, task = goal (not procedural instructions)
- Agent needs exact file paths for `validate_graph()`
- Agent needs to know `hasBBox` is required on Figures
- Deno sandbox works (no LocalPythonInterpreter needed)
- Agent self-corrects when it gets real SHACL violation feedback

## Next Steps

1. Add `inspect_figure` / `ask_figure` vision tools to indexer
2. Add `kag:imageDescription` and `kag:imagePath` to KG during indexing
3. Add local graph mode to `SPARQLToolsV2` (swap `urlopen` for `graph.query()`)
4. Build retrieval agent with bounded SPARQL tools
5. Named graph store for multi-document indexing
6. Wire ReasoningBank: seed strategies from run trajectories, closed loop
7. Test on pet_test_ocr and omd_test_ocr documents

## References

- Original KAG: https://arxiv.org/html/2409.13731v3
- DoCO: http://purl.org/spar/doco/ (Document Components Ontology)
- DEO: http://purl.org/spar/deo/ (Discourse Elements Ontology)
- RLM patterns: `../owl/` and `../reasoningbank/`
- DSPy RLM: `dspy.predict.rlm` (DSPy 3.1.3)
