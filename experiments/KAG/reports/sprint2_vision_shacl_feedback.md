# KAG Sprint 2: Vision Indexing & SHACL-Driven Agent Feedback

**Date:** 2026-02-10
**Papers tested:** Chemrxiv (Diels-Alder, 8 pages), PET (9 pages)
**Model:** Claude Sonnet 4.5 (agent), Claude Haiku 4.5 (sub-LM + vision)
**Runs analyzed:** 17 total (10 chemrxiv, 7 PET)

---

## 1. Session Goals

This session had two objectives:

1. **Add vision-based figure indexing** so the RLM agent can describe figure
   images during graph construction using a vision model (`dspy.Image` +
   `dspy.Predict`).
2. **Improve agent convergence** on SHACL validation, particularly for the
   larger PET paper where the agent was failing to produce conforming graphs.

The second objective evolved into a broader design investigation: how should
the system balance coded automation (auto-repair) vs. agent autonomy
(SHACL feedback + reasoning)?

## 2. What Was Built

### 2.1 Vision Indexing Pipeline

The agent can now call `inspect_figure(figure_iri)` during the RLM loop to
describe figure images. The pipeline:

1. `op_assert_type(node, doco:Figure)` creates the figure node
2. Agent sets `kag:pageNumber` from OCR page separators
3. Agent calls `inspect_figure(figure_iri)` which:
   - Looks up the figure's page number
   - Finds the corresponding PNG in the auto-discovered `_figures/` directory
   - Sends the image + caption context to Haiku via `dspy.Predict(DescribeFigure)`
   - Caches the result per-file (multiple OCR bboxes on the same page share one image)
4. Agent stores the description via `op_set_single_literal(figure_iri, 'kag:imageDescription', description)`
5. Agent stores the image path via `op_set_single_literal(figure_iri, 'kag:imagePath', path)`

The feature is opt-in (`--enable-figure-indexing` CLI flag) and costs ~$0.05-0.10
extra per paper for Haiku vision calls.

**Files modified:**
- `kag_ontology/kag_document_ext.ttl` -- added `kag:imageDescription`, `kag:imagePath` properties
- `kag_ontology/kag_document_shapes.ttl` -- added optional SHACL constraints on FigureShape
- `agentic_doc_tools.py` -- `inspect_figure()`, `ask_figure()`, DSPy signatures, vision LM caching
- `rlm_kag_runner.py` -- wiring, CLI params, task prompt
- `run_kag_1.py` -- CLI flags

### 2.2 Tool Surface Improvements

Four changes to the tool surface, each driven by a specific agent failure:

| Tool Change | Failure Observed | Fix |
|---|---|---|
| **`_resolve_iri()`** on all ops | Agent used CURIEs (`ex:elem_1`) instead of full IRIs; tools stored CURIEs as literal strings | Expand CURIEs via graph namespace bindings before all operations |
| **`op_assert_type` auto-generates `hasContentRef`** | Agent never generated SHA256 hashes for the PET paper (129 violations) | Auto-compute `kind:hex16` from `make_content_ref_id(kind, node_iri)` on type assertion |
| **`op_set_single_iri_link`** | Agent linked captions to wrong figures, then couldn't fix it (append-only tools) | Replace-semantics for IRI links (analogous to existing `op_set_single_literal`) |
| **`validate_graph()` default args** | Agent forgot file paths by iteration 10 and skipped validation entirely | Sensible defaults so `validate_graph()` works with no arguments |

### 2.3 SHACL Feedback System

The validate_graph output was completely rewritten to serve as actionable
feedback for the agent rather than a diagnostic for humans.

**Before (signature-based):**
```json
{
  "validation_results": 8,
  "top_signatures": [
    {
      "signature": "nb52f49...b26|kag:describes|sh:MinCountConstraintComponent",
      "count": 3,
      "top_focus_nodes": [{"node": "http://la3d.local/kag/doc/elem_81", "count": 1}]
    }
  ]
}
```

**After (actionable violations):**
```json
{
  "total_violations": 3,
  "violations": [
    {
      "node": "http://la3d.local/kag/doc/caption_6",
      "node_type": "Caption",
      "message": "Caption must describe exactly one Figure or Table via kag:describes.
                  Fix: op_add_iri_link(caption_iri, 'kag:describes', figure_or_table_iri).
                  Read the caption text to identify which Figure/Table it refers to.",
      "text_preview": "Table 1. Thermodynamic parameters for DA adduct formation..."
    }
  ],
  "action_required": "Graph does NOT conform. Fix the violations above, then call
                      validate_graph() again. Do NOT SUBMIT until conforms=true."
}
```

Key changes:
- Every SHACL `sh:message` includes the exact tool call to fix the violation
- Violations include `text_preview` for captions/paragraphs so the agent can reason about content
- `action_required` field explicitly tells the agent what to do next
- Removed opaque signature hashing and delta tracking

## 3. Design Principle: Feedback Over Auto-Repair

A key architectural decision emerged during this session. After implementing
auto-repair for `hasContentRef` and Section page numbers, we considered extending
auto-repair to structural issues (orphan paragraphs, missing `describes` links,
empty sections). The decision was explicitly **not** to do this.

**The principle:** Mechanical bookkeeping (deterministic, one right answer) should
be automated at the tool level. Structural reasoning (which section contains which
paragraph? which figure does this caption describe?) should remain the agent's
responsibility, guided by rich SHACL feedback.

What gets automated:
- `hasContentRef` generation (SHA256 hash, always the same computation)
- Section `pageNumber` inference (min of children's page numbers)

What stays with the agent:
- Section containment hierarchy
- Caption-to-figure/table linking
- Handling duplicate content across pages

This preserves agent flexibility and makes the system's behavior observable
and debuggable via SHACL validation reports.

## 4. Results

### 4.1 Run Progression

**Chemrxiv paper (8 pages, ~116 OCR blocks):**

| Version | Conforms | Violations | Vision | Iters | Cost | Key Change |
|---------|----------|------------|--------|-------|------|------------|
| v0-v2 | mixed | 0-20 | 0 | 9-15 | $0.30-0.61 | pre-vision baseline |
| v5 | true | 0 | 6 | 15 | $0.57 | vision indexing working |
| v6 | false | 6 | 0 | 30 | $2.20 | new SHACL messages, no remove tool |
| v7/v7b | false | 109 | 0 | 11 | $0.39 | cached bad strategy |
| v8 | false | 3 | 0 | 10 | $0.30 | cleared cache, agent skipped validation |
| **v9** | **true** | **0** | **6** | **17** | **$0.69** | **default validate_graph args** |

**PET paper (9 pages, ~130 OCR blocks):**

| Version | Conforms | Violations | Vision | Iters | Cost | Key Change |
|---------|----------|------------|--------|-------|------|------------|
| v1 | false | 164 | 0 | 10 | $0.37 | agent never validated |
| v2 | false | 262 | 0 | 11 | $0.33 | higher budget, still no validation |
| v3 | true | 0 | 0 | 10 | $0.28 | strengthened prompt (CURIE bug masked violations) |
| v4 | false | 155 | 5 | 10 | $0.28 | CURIE fix exposed real violations |
| v5 | false | 8 | 3 | 9 | $0.24 | auto hasContentRef + pageNumber |
| **v6** | **true** | **0** | **4** | **24** | **$1.56** | **actionable SHACL messages** |
| **v7** | **true** | **0** | **0** | **18** | **$0.80** | **default validate_graph args** |

### 4.2 Convergence Analysis

The final configuration (v9 chemrxiv, v7 PET) achieves **100% SHACL conformance**
on both test papers. The key pattern in successful runs:

1. Agent builds the full graph in 5-8 iterations (bulk construction)
2. Agent calls `validate_graph()` (no arguments needed)
3. If violations exist, agent reads the actionable messages and fixes them
4. Agent re-validates until `conforms=true`
5. If figure indexing is enabled, agent enriches figures with vision descriptions
6. Agent submits

Failed runs consistently exhibit one of these anti-patterns:
- **Never called `validate_graph()`** (v1, v2, v7, v8) -- usually because the agent
  didn't know the file paths or chose to do a manual self-check instead
- **Called validation but couldn't fix violations** (v6) -- append-only tools meant
  incorrect `describes` links were permanent
- **Cached bad strategy** (v7b) -- DSPy's LiteLLM cache returned identical responses
  from the previous failed run

### 4.3 Cost Analysis

Successful runs cost $0.28-$1.56 depending on document size and whether
figure indexing is enabled. The most expensive run ($2.20, chemrxiv v6) was a
failure that hit max iterations trying to work around append-only tools.

Vision indexing adds ~$0.05-0.10 for 5-6 Haiku calls per paper. The vision
calls are cached per-file, so composite figures (multiple bboxes on one page)
don't multiply costs.

## 5. Failure Mode Taxonomy

Across 17 runs, we observed five distinct failure modes:

### 5.1 Validation Avoidance (v1, v2, v7, v8)

The agent builds the graph and submits without calling `validate_graph()`. Two
sub-causes:

- **Argument amnesia:** The agent knows `validate_graph` exists but says "I need
  to know what shapes/ontology files to use" and skips it. This was the most
  common cause -- fixed by adding default arguments.
- **Manual self-check substitution:** The agent prints its own summary and
  declares the graph correct based on `graph_stats()`. Fixed by emphasizing
  in the prompt that only `validate_graph()` counts.

### 5.2 Append-Only Trap (v6)

The agent creates incorrect IRI links (e.g., caption describes wrong figure),
then discovers the error via SHACL validation, but cannot remove the wrong
triple. The agent spent 30 iterations trying increasingly creative workarounds
(creating duplicate nodes, changing types, building a "v2" graph) -- all
futile because rdflib's `Graph` accumulates triples.

**Fix:** `op_set_single_iri_link` -- replace-semantics for IRI links.

### 5.3 CURIE/IRI Mismatch (v3, v4)

The agent uses CURIE prefixes (`ex:elem_1`) in tool calls. Without resolution,
the tools store literal strings like `URIRef("ex:elem_1")` instead of
`URIRef("http://la3d.local/kag/doc/elem_1")`. SHACL validation then fails
on inverse-path constraints because the triples don't match.

**Fix:** `_resolve_iri()` expands CURIEs using graph namespace bindings on every
tool call.

### 5.4 Flat-Dump Strategy (v7 cached, early PET runs)

The agent creates all nodes as flat `elem_N` entries under the Document,
without creating Section containers. This produces ~100+ "must be contained
by a Section" violations. The strategy appears when the agent treats the
document as a flat sequence rather than a hierarchy.

**Mitigation:** The strengthened prompt explicitly describes the Section
containment hierarchy. The SHACL messages now include fix instructions.
This failure mode is stochastic -- same prompt can produce different strategies.

### 5.5 Cache Poisoning (v7b)

DSPy's LiteLLM disk cache returns identical responses for identical inputs
(same model, temperature=0.0, same prompt). If a bad strategy gets cached,
all subsequent runs with the same inputs reproduce it exactly.

**Mitigation:** Clear `~/.dspy_cache/*` when testing prompt changes. Be aware
that `temperature=0.0` makes responses fully deterministic for a given cache state.

## 6. What Worked: The Feedback Loop

The successful pattern is a **SHACL-in-the-loop** feedback cycle:

```
Agent builds graph
    |
    v
validate_graph() -- returns actionable violations
    |
    v
Agent reads violation messages with fix instructions
    |
    v
Agent applies fixes using op_* tools
    |
    v
validate_graph() -- re-check
    |
    v
conforms=true? --> SUBMIT
```

Three properties make this work:

1. **Zero-argument validation.** The agent doesn't need to remember file paths.
   `validate_graph()` just works.

2. **Actionable messages.** Every SHACL `sh:message` includes the exact tool call
   to fix the violation. The agent doesn't need to reason about what SHACL
   constraints mean -- it reads the fix instruction and applies it.

3. **Repair tools.** Both `op_set_single_literal` (for literal values) and
   `op_set_single_iri_link` (for IRI links) support replace-semantics, so the
   agent can correct mistakes without needing a general-purpose triple removal tool.

## 7. Architecture After Sprint 2

```
                     Task Prompt
                         |
                         v
    +--------------------------------------------+
    |              DSPy RLM Agent                |
    |  (Sonnet 4.5, max 30 iterations)           |
    |                                            |
    |  Tools:                                    |
    |    op_assert_type      (auto hasContentRef)|
    |    op_set_single_literal                   |
    |    op_add_iri_link                         |
    |    op_set_single_iri_link   (replace)      |
    |    validate_graph      (defaults, SHACL)   |
    |    graph_stats                             |
    |    inspect_figure      (vision, optional)  |
    +--------------------------------------------+
                         |
              +----------+----------+
              |                     |
              v                     v
    +------------------+   +------------------+
    | SHACL Shapes     |   | Vision Model     |
    | (kag_document_   |   | (Haiku 4.5)      |
    |  shapes.ttl)     |   | via dspy.Image   |
    |                  |   |                  |
    | Actionable       |   | DescribeFigure   |
    | sh:message on    |   | AskAboutFigure   |
    | every constraint |   | (cached per-file)|
    +------------------+   +------------------+
              |
              v
    +------------------+
    | Auto-fills       |
    | (tool-level)     |
    |                  |
    | hasContentRef    |
    |   (SHA256 hash)  |
    | Section page#    |
    |   (min of kids)  |
    +------------------+
```

## 8. Files Modified

| File | Lines Changed | Summary |
|---|---|---|
| `agentic_doc_tools.py` | ~200 | CURIE resolution, auto hasContentRef, op_set_single_iri_link, vision tools, actionable validate_graph output |
| `rlm_kag_runner.py` | ~40 | Vision params, tool wiring, simplified prompt, default validate_graph args |
| `run_kag_1.py` | ~10 | CLI flags for figure indexing |
| `kag_document_shapes.ttl` | full rewrite | Actionable sh:message on every constraint |
| `kag_document_ext.ttl` | +8 | imageDescription, imagePath properties |
| `dump_trajectory.py` | ~20 | Handle both old and new validation output formats |

## 9. Open Questions

1. **Stochastic convergence.** The agent's strategy varies across runs (even with
   temperature=0.0 after cache clearing). Some runs produce flat-dump graphs,
   others produce proper hierarchies. Can procedural memory (from successful runs)
   stabilize this?

2. **Figure indexing reliability.** The PET v7 run validated and submitted before
   reaching the figure indexing phase (0 vision calls). The task prompt puts figure
   indexing after validation, but the agent sometimes submits immediately on
   conforms=true. Should figure indexing be a hard gate?

3. **Cost vs. reliability tradeoff.** The cheapest successful run costs $0.28
   (PET v3, no vision). The most reliable configuration (actionable SHACL + default
   args + vision) costs $0.69-$1.56. Is the 3-5x cost increase justified by the
   elimination of structural violations?

4. **Scaling to longer papers.** Both test papers are 8-9 pages. Papers with 20+
   pages may require more iterations and face higher risk of the agent losing
   track of the task prompt instructions.

## 10. Next Steps

- [ ] Run 3+ papers to establish convergence rate with final configuration
- [ ] Add procedural memory: store successful strategies for retrieval in future runs
- [ ] Consider making figure indexing a separate post-validation phase (not agent-gated)
- [ ] Investigate retrieval-time tools (`ask_figure`, SPARQL over the KG)
- [ ] Commit all changes and update experiment README
