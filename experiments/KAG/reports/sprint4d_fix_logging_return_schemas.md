# KAG Sprint 4d Fix: Logging, Return Schemas, Sandbox Crash

**Date:** 2026-02-10
**Papers tested:** Chemrxiv (1043 triples), PET (1133 triples)
**Model:** Claude Sonnet 4.5 (agent + sub-LM)
**Run IDs:** `kag_qa_chemrxiv_20260210T182859Z`, `kag_qa_pet_20260210T183650Z`

---

## 1. Problems from Sprint 4c

Sprint 4c's chemrxiv run ($0.70, 6 questions) exposed three issues:

| Issue | Symptom | Root Cause |
|-------|---------|------------|
| Schema misread | Agent accessed `result.get('type')` instead of `result['types']` | DSPy only shows input arg signatures to the agent; return schemas never communicated |
| Sandbox crash | `dict[:5]` on `g_section_content()` output → TypeError → all tool bindings wiped | `g_section_content` returned a wrapper dict, agent expected an iterable list |
| Logging gaps | Sandbox crashes only visible as `[Error] Unhandled async error: PythonError` | No error classification in iteration logs |

The sandbox crash in `chemrxiv_synthesis_01` caused **7 wasted iterations** (iterations 4-10
all failed with NameError because tool functions were gone). The agent submitted a
non-answer.

## 2. Fixes Applied

### 2.1 Tool Docstrings with Return Schemas (`kag_qa_tools.py`)

Added explicit return key documentation to all 5 tool docstrings. DSPy passes the
full docstring to the agent, so the return structure is now visible:

```python
def g_search(self, query: str, limit: int = 10) -> list[dict[str, Any]]:
    """Full-text search over kag:fullText.

    Returns list of dicts with keys: iri, types, page, score, snippet, text_preview.
    """
```

### 2.2 `g_section_content` Returns Children List Directly

**Before:** Returned `{"section": ..., "title": ..., "child_count": N, "children": [...]}`
— the agent naturally wrote `for node in result` and `result[:5]`, which failed on a dict.

**After:** Returns `list[dict]` directly. Section title embedded as `_section_title`
on the first element. Error case also returns a list for consistency.

This eliminates the class of sandbox crashes caused by the agent slicing a dict.

### 2.3 Error Classification in Iteration Logs (`rlm_kag_qa_runner.py`)

Each iteration log event now includes:
- `has_error` (bool): whether `[Error]` appeared in output
- `error_type` (str | None): classified as `sandbox_crash`, `tool_binding_lost`,
  `type_error`, or `unknown`

Question-complete events now include:
- `sandbox_crashes` (int): count of sandbox crash iterations
- `tool_binding_errors` (int): count of tool binding loss iterations

## 3. Results

### 3.1 Chemrxiv (6 questions)

| Question | Type | Iters | Cost | Tools | Answer Quality |
|----------|------|-------|------|-------|----------------|
| structural_01 | structural | 2 | $0.025 | (context) | Correct: 11 sections listed |
| content_01 | content | 4 | $0.062 | search, detail, figure, section | Correct: TCNE = tetracyanoethylene, dienophile role |
| cross_ref_01 | cross_ref | 5 | $0.061 | figure, search, detail, section | Correct: VT NMR spectra, section identified |
| citation_01 | citation | 3 | $0.039 | section, refs | Correct: refs [16]-[27] listed |
| synthesis_01 | synthesis | 4 | $0.062 | search, detail | Correct: 1.637(4) A in TMAnnHept-DA |
| content_02 | content | 5 | $0.082 | search, detail | Correct: 5 temperatures listed |

**Total: 6/6 correct, $0.331, 0 crashes, 0 binding errors**

### 3.2 PET (6 questions)

| Question | Type | Iters | Cost | Tools | Answer Quality |
|----------|------|-------|------|-------|----------------|
| structural_01 | structural | 4 | $0.065 | search, section | Correct: all sections/subsections |
| content_01 | content | 4 | $0.060 | search, detail | Correct: 53 +/- 8% yield, 90% purity |
| cross_ref_01 | cross_ref | 4 | $0.069 | search, detail, refs | Correct: Table 1 = injected doses |
| citation_01 | citation | 10 | $0.183 | search, section, detail, refs | Correct: 37 refs, first 5 listed |
| synthesis_01 | synthesis | 3 | $0.042 | search, detail | Correct: spleen uptake + blocking |
| content_02 | content | 3 | $0.039 | search, detail | Correct: K_D 3.10 nM / 3.75 nM |

**Total: 6/6 correct, $0.459, 0 crashes, 0 binding errors**

### 3.3 Comparison vs Sprint 4c

| Metric | Sprint 4c (chemrxiv) | Sprint 4d (chemrxiv) | Sprint 4d (PET) |
|--------|---------------------|---------------------|-----------------|
| Questions correct | 5/6 | **6/6** | **6/6** |
| Total cost | $0.70 | **$0.331** | $0.459 |
| Sandbox crashes | 1 | **0** | **0** |
| Tool binding losses | 7 iters | **0** | **0** |
| Avg iters/question | ~7 | **3.8** | **4.7** |

## 4. Remaining Issues

### 4.1 `pet_citation_01` Efficiency (10 iterations)

The agent used all 10 iterations to answer "How many references does this paper cite?"
despite the References section IRI (`ex:section_18`) being listed in the injected context.
In iteration 2 it tried passing a SectionTitle block IRI (`ex:b_p008_0012`) to
`g_section_content`, got an error, then spent 5 iterations searching indirectly before
finding `ex:section_18` by brute-force enumeration.

**Not a tooling bug** — the agent failed to read the context carefully. Could be
mitigated by making the task prompt more explicit about using section IRIs from context.

### 4.2 Minor `unknown` Errors

Both papers had one `unknown` error each (both KeyError from the agent accessing
keys on error-return dicts without checking). The agent recovered in all cases.
These are normal agent mistakes, not systemic issues.

## 5. Lessons Learned

1. **Return schemas must be in docstrings.** DSPy shows the agent input parameter
   signatures but not return types. The agent guesses key names and gets them wrong.
   Every tool docstring should document the return dict keys explicitly.

2. **Tool returns must match agent idiom.** Agents naturally write `for x in result`
   and `result[:5]`. If a tool returns a wrapper dict when the useful data is a list
   inside it, the agent will try to iterate/slice the dict and crash. Return the
   list directly.

3. **Error classification in logs is cheap and invaluable.** Adding `has_error` +
   `error_type` to iteration events took 15 lines of code but makes post-hoc
   analysis trivial — `jq '.data | select(.has_error)' trajectory.jsonl` finds
   all problems instantly.

4. **Bad eval questions waste budget.** The original `chemrxiv_citation_01` asked
   about citations in Conclusions, which has none. The agent correctly found nothing
   but burned 10 iterations being thorough. Eval questions must be validated against
   the actual graph data.

## 6. Files Modified

| File | Change |
|------|--------|
| `experiments/KAG/kag_qa_tools.py` | Return schemas in 5 docstrings; `g_section_content` returns list |
| `experiments/KAG/rlm_kag_qa_runner.py` | Error classification + crash counts in logging |
| `experiments/KAG/kag_qa_tasks.json` | Fixed `chemrxiv_citation_01` to target Introduction (has 12 citations) |
| `experiments/KAG/reports/sprint4d_fix_logging_return_schemas.md` | This report |
