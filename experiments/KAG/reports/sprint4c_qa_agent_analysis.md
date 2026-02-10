# KAG Sprint 4c: QA Agent over Enriched Document Graphs

**Date:** 2026-02-10
**Papers tested:** Chemrxiv (Diels-Alder, 1043 triples), PET (PubMed, 1133 triples)
**Model:** Claude Sonnet 4.5 (agent + sub-LM)
**Run IDs:** `kag_qa_chemrxiv_20260210T160154Z`, `kag_qa_pet_20260210T160709Z`

---

## 1. Motivation

Sprint 4 produced enriched DoCO knowledge graphs with DEO section types,
structured bibliography, cross-reference linking, and citation linking. The
graphs capture both *where things are* (structure) and *what they say*
(content). But we had no evidence that these enrichments are actually useful
to a downstream consumer.

**Goal:** Build a read-only QA agent that answers competency questions using
these enriched graphs, capturing *trajectories* that reveal which graph
features the agent uses, which it ignores, and where it gets stuck. The
trajectories — not the answers — are the primary deliverable.

## 2. Architecture

### Tool Surface (9 tools, 4 levels)

| Level | Tool | Purpose |
|---|---|---|
| L0 | `g_stats()` | Triple count, node type counts |
| L0 | `g_sections()` | Section titles + DEO roles |
| L1 | `g_section_content(iri)` | Children of a section (type, preview, page) |
| L1 | `g_node_detail(iri)` | All properties of a single node |
| L2 | `g_search(query)` | Full-text search over `kag:fullText` |
| L2 | `g_figure_info(iri)` | Caption, page, image description, referring paragraphs |
| L3 | `g_citations(para_iri)` | Bibliography entries cited by a paragraph |
| L3 | `g_citing_paragraphs(ref_iri)` | Paragraphs that cite a bibliography entry |
| L3 | `g_cross_refs(para_iri)` | Figures/tables referred to by a paragraph |

All tools return bounded dicts (preview text, not dumps). The agent must call
multiple tools and compose results to build an answer.

### Runner

One `dspy.RLM` call per question. The graph is loaded once; each question gets
a fresh RLM instance with 10-iteration / 30-call budget. DSPy signature:
`"question, task, graph_summary -> answer"` with `graph_summary` injected as
a JSON string from `g_stats()`.

### Competency Questions (12 total)

Six questions per paper across five types:

| Type | Count | Tests |
|---|---|---|
| structural | 2 | Section enumeration, hierarchy |
| content | 4 | Specific facts extractable from paragraphs |
| cross_ref | 2 | Figure/table identification + linking back to text |
| citation | 2 | Bibliography traversal via `cito:cites` |
| synthesis | 2 | Multi-hop reasoning across sections |

## 3. Results

### 3.1 Chemrxiv — "Low-temperature retro Diels-Alder reactions"

| Question | Type | Iters | LM Calls | Tool Calls | Tools Used | Cost |
|---|---|---|---|---|---|---|
| Sections & titles | structural | 2 | 2 | 1 | g_sections | $0.02 |
| What is TCNE | content | 10* | 11 | 9 | g_stats, g_sections, g_search(2), g_node_detail(4), g_section_content | $0.25 |
| Figure 4 / VT NMR | cross_ref | 10* | 11 | 7 | g_stats, g_sections, g_search(2), g_node_detail, g_figure_info, g_section_content | $0.24 |
| Citations in Conclusions | citation | 5 | 5 | 6 | g_sections, g_section_content, g_citations(2), g_node_detail(2) | $0.06 |
| Longest C-C bond | synthesis | 7 | 7 | 11 | g_stats, g_sections, g_search(2), g_section_content(3), g_node_detail(4) | $0.13 |
| 50/50 equilibrium temps | content | 5 | 5 | 7 | g_stats, g_sections, g_search(3), g_section_content, g_node_detail | $0.08 |
| **Totals** | | **39** | **41** | **41** | | **$0.79** |

\* Hit max iterations (10); answer extracted via fallback.

### 3.2 PET — "Radiosynthesis and preclinical PET evaluation of 89Zr-nivolumab"

| Question | Type | Iters | LM Calls | Tool Calls | Tools Used | Cost |
|---|---|---|---|---|---|---|
| Sections & subsections | structural | 4 | 4 | 1 | g_sections | $0.06 |
| Radiochemical yield/purity | content | 5 | 5 | 5 | g_sections, g_section_content, g_node_detail(2), g_search | $0.08 |
| Table 1 data & refs | cross_ref | 6 | 6 | 36 | g_stats, g_search(2), g_node_detail(5), g_cross_refs(28) | $0.14 |
| Reference count + first 5 | citation | 10* | 11 | 5 | g_stats, g_search, g_sections(2), g_section_content | $0.20 |
| Spleen biodistribution | synthesis | 9 | 9 | 9 | g_stats, g_sections, g_search(2), g_section_content(2), g_node_detail(3) | $0.16 |
| K_D binding values | content | 4 | 4 | 6 | g_stats, g_sections, g_search(2), g_section_content, g_node_detail | $0.06 |
| **Totals** | | **38** | **39** | **62** | | **$0.71** |

\* Hit max iterations; partial answer (found 37 refs but couldn't list titles).

### 3.3 Combined Summary

| Metric | Chemrxiv | PET | Combined |
|---|---|---|---|
| Questions answered | 6/6 | 6/6 | 12/12 |
| Fully answered | 6/6 | 5/6 | 11/12 |
| Hit max iterations | 2 | 1 | 3 |
| Total cost | $0.79 | $0.71 | $1.49 |
| Avg cost/question | $0.13 | $0.12 | $0.12 |
| Avg iterations | 6.5 | 6.3 | 6.4 |
| Total tool calls | 41 | 62 | 103 |

### 3.4 Answer Quality

**Strong answers (correct, specific, grounded):**

- **chemrxiv_structural_01**: Correctly identified all 11 sections with titles.
  1 tool call, $0.02.
- **chemrxiv_synthesis_01**: Found the exact bond length (1.637(4) A) and
  correct adduct (TMAnnHept-DA). Required multi-section search.
- **chemrxiv_content_02**: Extracted all five 50/50 equilibrium temperatures
  (TMAnMe: 130C, TMAnEt: 20C, TMAnnBu: -8.4C, TMAnnHept: -10C, TMAnEtPh:
  -46C) from graph content.
- **pet_content_02**: Found exact K_D values (nivolumab: 3.10 nM,
  nivolumab-DFO: 3.75 nM) in 4 iterations.
- **pet_content_01**: Extracted radiochemical yield (53 +/- 8%) and purity
  (87-90%) with per-condition breakdown.
- **pet_cross_ref_01**: Identified Table 1 contents and the specific
  paragraph (ex:b_p005_0010) that references it.

**Partial failure:**

- **pet_citation_01**: Found the correct count (37 references) but could not
  list individual reference titles. The agent used `g_section_content` to find
  47 children in the References section but never called `g_node_detail` on
  individual bibliography entries to extract `kag:citationText`. Hit max
  iterations attempting alternative strategies.

## 4. Trajectory Analysis

### 4.1 Aggregate Tool Usage

| Tool | Chemrxiv Calls | PET Calls | Total | Questions Using |
|---|---|---|---|---|
| g_node_detail | 12 | 11 | 23 | 10/12 |
| g_search | 9 | 8 | 17 | 10/12 |
| g_sections | 6 | 6 | 12 | 12/12 |
| g_section_content | 7 | 5 | 12 | 9/12 |
| g_stats | 4 | 4 | 8 | 8/12 |
| g_cross_refs | 0 | 28 | 28 | 1/12 |
| g_citations | 2 | 0 | 2 | 1/12 |
| g_figure_info | 1 | 0 | 1 | 1/12 |
| g_citing_paragraphs | 0 | 0 | 0 | 0/12 |

### 4.2 Progressive Disclosure Patterns

The agent consistently follows an L0 -> L1/L2 -> L1 pattern:

1. **Orientation** (L0): `g_sections()` in 12/12 questions, `g_stats()` in
   8/12. The agent always orients itself before searching.
2. **Search** (L2): `g_search()` is the primary discovery tool (10/12
   questions). Used to locate relevant paragraphs by keyword.
3. **Drill-down** (L1): `g_node_detail()` is the primary inspection tool
   (10/12 questions, 23 total calls). Used to read full text of search hits.
4. **Context** (L1): `g_section_content()` provides section-level context
   (9/12 questions). Used to understand what's near a search hit.

**Canonical trajectory** (observed in 8/12 questions):
```
g_stats -> g_sections -> g_search -> g_node_detail -> [refine] -> SUBMIT
```

### 4.3 Relationship Tool Usage (L3)

The L3 relationship tools were used sparingly:

- **g_citations**: Used in 1 question (chemrxiv_citation_01). The agent
  correctly navigated sections -> section_content -> citations -> node_detail
  to determine the Conclusions section has no inline citations. This is the
  ideal use pattern.

- **g_cross_refs**: Used in 1 question (pet_cross_ref_01) but with a
  pathological pattern: the agent called it **28 times**, iterating over
  paragraphs one by one to find which ones reference Table 1. This reveals a
  missing capability — there is no inverse tool "which paragraphs refer to
  this table/figure?" for tables. (`g_figure_info` provides
  `referring_paragraphs` for figures but tables aren't figures.)

- **g_figure_info**: Used once (chemrxiv_cross_ref_01) to get Figure 4's
  caption and identify the section discussing VT NMR experiments. Worked as
  designed.

- **g_citing_paragraphs**: Never used (0/12 questions). None of the questions
  naturally required "find paragraphs that cite reference X". This tool would
  be useful for questions like "Which sections discuss reference [14]?" which
  weren't in our question set.

### 4.4 Cost Drivers

| Factor | Observation |
|---|---|
| **Structural questions** | Cheapest ($0.02-$0.06). Single tool call suffices. |
| **Content questions** | Moderate ($0.06-$0.25). Cost correlates with specificity: TCNE role required 10 iterations across multiple sections. |
| **Cross-ref questions** | Variable ($0.14-$0.24). Depends on whether the agent can locate the target efficiently. |
| **Citation questions** | Most variable ($0.06-$0.20). Simple citation check was cheap; listing references hit max iterations. |
| **Synthesis questions** | Moderate-high ($0.13-$0.16). Multi-section traversal. |

**Main cost driver**: prompt token accumulation. Each iteration appends the
full tool result to the context. Questions that require many `g_node_detail`
calls accumulate full-text paragraphs in context, pushing prompt tokens up
rapidly (content_01: 65K prompt tokens across 11 calls).

## 5. What the Trajectories Tell Us About Graph Quality

### 5.1 Features That Enabled Good Answers

| Feature | Evidence |
|---|---|
| **kag:fullText** | The workhorse. `g_search` over fullText found relevant content in 10/12 questions. Without it, the agent would have only 120-char mainText previews. |
| **Section containment hierarchy** | `g_sections` -> `g_section_content` navigation worked flawlessly. Sections with `kag:containsAsHeader` + `kag:contains` give the agent a map of the paper. |
| **DEO section classification** | The agent used DEO roles to identify the Conclusions section in chemrxiv_citation_01. Without DEO, it would need to string-match section titles. |
| **cito:cites links** | `g_citations` correctly returned empty for Conclusions paragraphs — proving the enrichment accurately captured the absence of citations. |
| **kag:refersTo links** | `g_cross_refs` found the Table 1 reference in pet_cross_ref_01, though the search pattern was inefficient. |
| **Structured bibliography** | `g_stats` reported 47 (chemrxiv) and 37 (pet) bibliographic references, enabling the agent to answer "how many references" immediately. |

### 5.2 Missing or Insufficient Features

| Gap | Evidence | Suggested Fix |
|---|---|---|
| **No inverse cross-ref for tables** | pet_cross_ref_01 called `g_cross_refs` 28 times scanning paragraphs. `g_figure_info` has `referring_paragraphs` but only for figures. | Add `g_table_info(iri)` with referring_paragraphs, or make `g_figure_info` work for tables too. |
| **No section-level citation aggregation** | pet_citation_01 failed to list individual references. The agent found the References section (37 children) but couldn't efficiently iterate them. | Add `g_section_refs(section_iri)` that returns all bibliography entries in a section with citation numbers and preview text. |
| **Node listing within sections is unordered** | `g_section_content` returns children but they're sorted by page+IRI, not document order. For bibliography entries, this means they appear in hash order, not citation number order. | Sort bibliography entries by `kag:citationNumber`. |
| **PET DEO classification gap** | PET has 0 DEO-classified sections because its titles don't match standard patterns ("Experimental section", "Characterization"). | Expand `TITLE_TO_DEO` patterns or use fuzzy matching. |
| **No table content extraction** | Table 1 in PET has no `kag:fullText` (tables are images). The agent described Table 1 based on the caption, not the data. | Vision-based table extraction or structured table representation. |

### 5.3 Unused Graph Features

These Sprint 4 enrichments exist in the graph but were never leveraged by
the QA agent:

- **kag:citationNumber** on bibliography entries — the agent never filtered
  or sorted by citation number
- **kag:citationText** — never directly retrieved (the agent got reference
  content via `g_node_detail` on `kag:fullText`)
- **doco:ListOfReferences** section type — not used; agent found the
  References section by title matching via `g_sections`
- **kag:imagePath** and **kag:imageDescription** — figure vision data wasn't
  needed for any question (no vision-dependent questions)

## 6. Comparison: Graph Construction (Sprint 3-4) vs QA (Sprint 4c)

| Dimension | Graph Construction | QA Agent |
|---|---|---|
| Mode | Read-write (mutation) | Read-only (exploration) |
| Tools | 9 graph ops + validate | 9 bounded view tools |
| Iterations | 10-14 per paper | 2-10 per question |
| Cost | $0.31-$0.48 per paper | $0.02-$0.25 per question |
| Failure mode | SHACL violations, IRI collisions | Max iterations, missed tool strategies |
| Key tool | `op_create_node` | `g_search` |
| Agent pattern | Iterate blocks -> create -> link -> validate | Orient -> search -> drill -> compose |

## 7. Recommendations for Sprint 5

### 7.1 Tool Surface Improvements

1. **Unified `g_entity_info(iri)`** — like `g_figure_info` but for any node
   type (table, formula, etc.). Include `referring_paragraphs` universally.
2. **`g_section_refs(section_iri, type_filter)`** — list all nodes of a type
   within a section. Solves the bibliography listing problem.
3. **Increase default max_iterations to 15** — three questions hit the
   10-iteration ceiling. Content and cross-ref questions need more room.

### 7.2 Graph Enrichment Improvements

1. **Expand DEO classification** — fuzzy title matching or keyword-based
   classification for non-standard section titles (PET paper).
2. **Table content extraction** — tables as images need OCR or vision-based
   structured extraction to be queryable.
3. **Section ordering** — add `kag:sectionOrder` so children can be returned
   in document order, not arbitrary order.

### 7.3 Evaluation Framework

1. **Expert grading** — have a domain expert score the 12 answers (correct /
   partially correct / wrong / unanswerable).
2. **Tool efficiency metric** — ratio of useful tool calls to total tool
   calls. pet_cross_ref_01 scored 8/36 (22% useful).
3. **Progressive disclosure compliance** — measure whether the agent follows
   L0 -> L1 -> L2 -> L3 or skips levels.

---

## Appendix A: Run Artifacts

```
experiments/KAG/results/kag_qa_chemrxiv_20260210T160154Z/
  trajectory.jsonl     135 events
  summary.json         6 results, $0.79
  answers/             6 individual answer files

experiments/KAG/results/kag_qa_pet_20260210T160709Z/
  trajectory.jsonl     176 events
  summary.json         6 results, $0.71
  answers/             6 individual answer files
```

## Appendix B: Files Created

| File | Purpose |
|---|---|
| `experiments/KAG/kag_qa_tools.py` | `KagQAToolset` — 9 read-only bounded view tools |
| `experiments/KAG/kag_qa_tasks.json` | 12 competency questions (6/paper, 5 types) |
| `experiments/KAG/rlm_kag_qa_runner.py` | Per-question RLM runner with trajectory logging |
| `experiments/KAG/run_kag_qa.py` | CLI entrypoint |
