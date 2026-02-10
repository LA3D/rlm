# KAG Sprint 3: Tool-Level Guardrails Analysis

**Date:** 2026-02-10
**Paper tested:** Chemrxiv (Diels-Alder, 8 pages, ~116 OCR blocks)
**Model:** Claude Sonnet 4.5 (agent), Claude Haiku 4.5 (sub-LM + vision)
**Run ID:** `run_kag_1_guardrails_chemrxiv_20260210T140516Z`

---

## 1. What Was Changed

Two tool-level guardrails were added based on trajectory analysis of 17
prior runs (sprint 2):

### 1.1 Pre-Parsed Block Injection

The OCR document is pre-parsed into `blocks` — a Python list of dicts
injected as a REPL variable alongside `document`. Each block contains:

```python
{"id": "b_p002_0001", "page": 2, "order": 1, "label": "title",
 "kind": "title", "bbox": [[276, 160, 896, 210]],
 "ref": "title:37ca783fba8e881d",
 "text": "# Low-temperature retro Diels-Alder reactions"}
```

**Rationale:** Prior runs spent 7-8 iterations (40-50% of budget) writing
regex parsers for the OCR tag format. The parser already exists in
`_parse_blocks()` — the runner just wasn't exposing the results.

### 1.2 Validation Gate (`finalize_graph`)

New tool that wraps `validate_graph()` with a pre-SUBMIT protocol:

- `finalize_graph(answer)` → `{"status": "READY"}` or `{"status": "NOT_READY", "violations": [...]}`
- All `op_*` methods reset `_validated = False` (mutation invalidation)
- Task prompt instructs: "Do NOT call SUBMIT directly — always go through
  finalize_graph first"

**Rationale:** Failed runs in sprint 2 never called `validate_graph()`.
The agent would do a manual self-check and submit. `finalize_graph` makes
validation a structural gate rather than an optional step.

## 2. Results

| Metric | Sprint 2 Best | Sprint 2 Median | **Sprint 3** |
|--------|--------------|-----------------|--------------|
| Conforms | true (2/6 = 33%) | false | **true** |
| Iterations | 15-17 | 11 | **22** (14 core + 8 vision) |
| Triples | 757-759 | 1067 | **975** |
| Cost | $0.57-$0.69 | $0.39 | **$0.89** |
| finalize_graph calls | — | — | **8** |
| Vision calls | 0-6 | 0 | **6** |
| Parsing iterations | 7-8 est. | 7-8 est. | **0** |

### 2.1 What Improved

**Parsing waste eliminated.** The agent iterated `blocks` directly starting
in iteration 1. Zero iterations spent on OCR regex debugging. In iteration 1,
the agent explored the blocks structure; by iteration 5, it was already
creating graph nodes.

**Validation gate worked.** The agent called `finalize_graph` 8 times total.
6 returned NOT_READY (triggering repair), 2 returned READY (first for core
graph, second after vision enrichment). It also called `validate_graph` once
as a mid-construction check.

**Graph completeness improved.** 975 triples vs 757-759 in prior conforming
runs. The agent captured more content because it wasn't spending its iteration
budget on parsing.

### 2.2 What Didn't Improve

**Iteration count increased.** 22 total iterations (14 core + 8 vision), vs
15-17 in prior conforming runs without vision. The core construction count
(14) is comparable, not better. The predicted 8-12 target was not met.

**Cost increased.** $0.89 vs $0.57-0.69 for prior conforming runs. Most of
the cost increase comes from the additional repair iterations and vision calls.

## 3. Repair Cycle Deep Dive

The agent spent **iterations 10-20** (11 iterations, 50% of core budget)
fixing a single structural problem: two orphan paragraphs.

### 3.1 The Problem

The chemrxiv paper has a preprint cover page (page 1) that repeats the
title and abstract from page 2. The agent (correctly) skipped page 1 blocks
to avoid duplicates. However, the Abstract section title (`## Abstract`) only
appears on page 1. Without it, the two paragraphs before the first `sub_title`
on page 2 — the author list (`b_p002_0002`) and abstract text (`b_p002_0003`)
— had no section to belong to.

### 3.2 The SHACL Trap

The containment constraint on ParagraphShape is:

```turtle
sh:property [
    sh:path [ sh:inversePath kag:contains ] ;
    sh:minCount 1 ;
    sh:class doco:Section ;
    sh:message "Paragraph must be contained by a Section. ..."
] ;
```

In SHACL, `sh:class doco:Section` means **every** value on the inverse path
must be a Section — not just "at least one." So when the agent had both:

- `Document → kag:contains → Paragraph` (from iteration 8)
- `Section_0 → kag:contains → Paragraph` (from iteration 12)

...the constraint still failed because Document is not a Section. The
SHACL message ("Fix: add a contains link from a section") was **misleading**
— the real fix was to **remove** the Document→Paragraph link.

### 3.3 Iteration-by-Iteration Breakdown

| Iter | Action | Result |
|------|--------|--------|
| 10 | First `finalize_graph` call | NOT_READY: 2 paragraphs not in any Section |
| 11 | Checks blocks, finds Abstract section title on page 1 | Discovery |
| 12 | Creates section_0 (Abstract), links paragraphs to it | Links added but... |
| 13 | Realizes it linked the title node incorrectly, re-validates | Still NOT_READY |
| 14 | Adds correct `section_0 → contains → b_p002_0003` | Still NOT_READY |
| 15 | Re-adds same links (additive, no effect on RDF set) | Still NOT_READY |
| 16 | Re-validates again | Still NOT_READY |
| 17 | Tries `validate_graph('shapes.ttl')` with wrong path — FileNotFoundError returned as dict, agent misreads as "0 violations" | **False signal** |
| 18 | Calls `finalize_graph` expecting READY | Still NOT_READY (correct) |
| 19 | Re-asserts section_0 type, re-adds contains links | Still NOT_READY |
| 20 | **Eureka:** uses `op_set_single_iri_link` on Document contains to rebuild links without paragraphs | **READY** |

### 3.4 Three Root Causes

**1. No structural hint about pre-section content.**
The task prompt says "Group blocks into sections based on sub_title
boundaries" but doesn't explain what to do with blocks that appear before
the first `sub_title`. The agent had to discover this pattern through trial
and error.

**2. Misleading SHACL message.**
The message says "add a contains link from a section" — implying the fix is
additive. But the real problem was the *existing* `Document → Paragraph`
link. The agent couldn't reason about what to remove because the violation
message didn't mention the conflicting containment.

**3. No diagnostic tool for graph structure.**
The agent had no way to query "what contains this paragraph?" It could only
call `graph_stats()` (returns triple count) or `validate_graph()` (returns
violations). Without a way to inspect the actual triples, it kept re-adding
links that already existed.

### 3.5 The validate_graph Error Trap

In iteration 17, the agent called `validate_graph('shapes.ttl')` with a
bad path. The tool wrapper caught the exception and returned:

```python
{"error": "No such file or directory: '.../shapes.ttl'",
 "exception_type": "FileNotFoundError"}
```

The agent's code did `len(result.get('violations', []))` which returned 0
(no 'violations' key in the error dict). The agent misinterpreted this as
"0 violations — validation passed!" and proceeded to call `finalize_graph`
expecting READY. This wasted iteration 18.

**This is a tool-surface bug:** error responses should be clearly
distinguishable from success responses. The `finalize_graph` gate caught
the discrepancy (it ran its own validation), but the standalone
`validate_graph` path doesn't protect against this.

## 4. Structural Improvements

Based on this analysis, four improvements would address the observed
failure modes:

### 4.1 Pre-Section Block Grouping (Prompt Enhancement)

**Problem:** Agent doesn't know what to do with blocks before the first
`sub_title`.

**Fix:** Add explicit instructions to the task prompt:

```
Blocks before the first sub_title (e.g., author list, abstract text) should
be grouped into an "Abstract" or "Front Matter" section. Create a
doco:Section with a doco:SectionTitle for these blocks.
If the blocks list includes an "Abstract" sub_title on a skipped page,
use that as the section title.
```

**Alternatively (stronger):** Pre-compute section groupings in
`blocks_for_repl()` — add a `section` field to each block dict indicating
which section it belongs to. This makes the grouping deterministic instead
of leaving it to agent reasoning.

### 4.2 Improved SHACL Messages (Feedback Enhancement)

**Problem:** SHACL message says "add a contains link" when the real fix
is "remove the Document→Paragraph link."

**Fix:** Change the SHACL `sh:message` for the containment constraint to
explain both failure modes:

```
"Paragraph must be contained ONLY by Sections (not by Document directly).
 If this paragraph is already in a Section but also linked from the Document,
 remove the Document link: op_set_single_iri_link(document_iri, 'kag:contains', ...)
 to rebuild Document's children without this paragraph.
 If this paragraph is not in any Section, add it:
 op_add_iri_link(section_iri, 'kag:contains', this_paragraph_iri)."
```

### 4.3 Graph Inspection Tool (`query_contains`)

**Problem:** Agent can't see the existing triples. It keeps adding links
that already exist because it can't verify what's already in the graph.

**Fix:** Add a lightweight inspection tool:

```python
def query_contains(self, node_iri: str) -> dict:
    """Show what contains this node and what this node contains."""
    node = self._resolve_iri(node_iri)
    contained_by = [
        {"iri": str(s), "type": str(self.graph.value(s, RDF.type) or "")}
        for s in self.graph.subjects(KAG.contains, node)
    ]
    contains = [
        {"iri": str(o), "type": str(self.graph.value(o, RDF.type) or "")}
        for o in self.graph.objects(node, KAG.contains)
    ]
    return {"node": str(node), "contained_by": contained_by, "contains": contains}
```

This lets the agent diagnose "who contains this paragraph?" instead of
guessing.

### 4.4 Error-Distinct Responses in Tool Wrapper

**Problem:** Error dicts from the tool wrapper look like empty success
responses to agent code that checks `result.get('violations', [])`.

**Fix:** Two options:

A. Add an `"ok": False` field to error responses so agent code can check
   `if not result.get("ok", True): print("ERROR:", result["error"])`

B. Raise the exception through to the REPL (DSPy's interpreter will capture
   and show it as an error message). This is simpler and more Pythonic —
   the agent sees a traceback instead of a misleading empty dict.

## 5. Priority Assessment

| Improvement | Impact | Effort | Priority |
|---|---|---|---|
| 4.1 Pre-section grouping (prompt) | High — eliminates the most expensive failure mode | Low | **P0** |
| 4.2 Improved SHACL messages | Medium — helps when containment issues arise | Low | **P1** |
| 4.3 Graph inspection tool | Medium — helps diagnosis but agent may not use it | Medium | **P2** |
| 4.4 Error-distinct responses | Low — only triggered by bad tool args | Low | **P1** |

The pre-section grouping fix (4.1) would have prevented all 11 repair
iterations in this run. Combined with better SHACL messages (4.2), the
agent would get actionable fix instructions on the first violation.

## 6. Blocks Injection Assessment

The `blocks` variable worked as intended:

- **Iteration 1:** Agent examined `blocks` structure (len, keys, first 3 entries)
- **Iteration 2:** Agent counted kinds/labels, analyzed page distribution
- **Iteration 4-5:** Agent iterated blocks to create nodes directly

**Zero parsing iterations.** The agent never wrote regex. It accessed
`b['page']`, `b['kind']`, `b['bbox']`, `b['text']` directly.

**One edge case:** The agent used blocks data to identify the Abstract
section title on page 1 (`blocks` includes all pages, even the cover page
the agent chose to skip for node creation). This was helpful — the blocks
list served as a manifest for reasoning about document structure, not just
as node-creation input.

## 7. finalize_graph Assessment

The validation gate worked correctly:

- **8 calls total:** 6 NOT_READY (drove repair), 2 READY (gated submission)
- **Mutation invalidation worked:** After the agent modified triples in
  iteration 19, the next `finalize_graph` call re-ran full validation
- **Caught the validate_graph error:** In iteration 18, after the agent
  misread a `validate_graph` error as "0 violations," `finalize_graph`
  correctly returned NOT_READY

**Observation:** The agent never tried to bypass `finalize_graph`. It
consistently called it before SUBMIT, following the completion protocol.
The structural gate achieved its goal of eliminating validation avoidance.

## 8. Updated Architecture Diagram

```
                     Task Prompt
                         |
                    +---------+
                    | blocks  |  <── Pre-parsed OCR (list of dicts)
                    +---------+
                         |
                         v
    +--------------------------------------------+
    |              DSPy RLM Agent                |
    |  (Sonnet 4.5, max 30 iterations)           |
    |                                            |
    |  REPL Variables:                           |
    |    document   (full OCR markdown, 40KB)    |
    |    blocks     (parsed block list, ~12KB)   |
    |                                            |
    |  Tools:                                    |
    |    op_assert_type      (auto hasContentRef)|
    |    op_set_single_literal                   |
    |    op_add_iri_link                         |
    |    op_set_single_iri_link   (replace)      |
    |    validate_graph      (mid-construction)  |
    |    finalize_graph      (pre-SUBMIT gate)   |
    |    graph_stats                             |
    |    inspect_figure      (vision, optional)  |
    +--------------------------------------------+
```

## 9. Open Questions

1. **Should `blocks` include section groupings?** Pre-computing which
   section each block belongs to would eliminate the grouping problem
   entirely. But this removes a task that tests the agent's structural
   reasoning. Tradeoff: reliability vs. agent capability assessment.

2. **Is `finalize_graph` sufficient or should SUBMIT be blocked?**
   Currently, the agent could still call `SUBMIT` without `finalize_graph`.
   DSPy's SUBMIT mechanism is internal and can't be intercepted. The prompt
   is the only enforcement. In this run, prompt-based enforcement worked.

3. **How many repair cycles are acceptable?** This run had 6 NOT_READY
   cycles for a single issue. With better SHACL messages (4.2), this could
   drop to 1-2 cycles. But the agent's inability to inspect graph state
   (4.3) means some trial-and-error is inherent.

4. **Does this generalize to PET?** The PET paper has different structural
   challenges (more figures, complex section hierarchy). A second data point
   is needed to validate the guardrails.

## 10. Next Steps

- [ ] Implement 4.1: Add pre-section block grouping hint to task prompt
- [ ] Implement 4.2: Improve SHACL containment message to mention both failure modes
- [ ] Run PET paper with guardrails for a second data point
- [ ] Consider 4.3 (query_contains) if repair cycles remain >3 after 4.1+4.2
- [ ] Consider pre-computed section groupings in blocks if prompt hint is insufficient
