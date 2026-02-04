# S3 Experiment: Bug Report

**Date**: 2026-02-03
**Total Bugs Found**: 3 critical issues
**Status**: ALL FIXED

---

## Bug 1: Missing `llm_query` Tool - FIXED

### Root Cause
`llm_query` is a DSPy RLM built-in function available only in the Deno sandbox interpreter. Our `LocalPythonInterpreter` did not have it.

### Fix Applied
Modified `LocalPythonInterpreter.__init__()` to accept `sub_lm` parameter and inject `llm_query` / `llm_query_batched` into the namespace, mimicking DSPy's built-in behavior.

**Files modified**:
- `experiments/reasoningbank/tools/local_interpreter.py` - Added `sub_lm` parameter and `_make_llm_query()` method
- `experiments/reasoningbank/tools/sparql.py` - Removed incorrect llm_query from tools dict
- `experiments/reasoningbank/run/rlm_uniprot.py` - Pass `sub_lm` to LocalPythonInterpreter

---

## Bug 2: Task 5 `NoneType.strip()` Error - FIXED

### Root Cause
**Anthropic API returns `finish_reason='refusal'`** for the query "Find UniProtKB entries with merged loci in Bordetella avium". This is a **safety filter false positive** - *Bordetella avium* is a bird pathogen, and the model misinterprets it as a biosafety concern.

The refusal results in `content=None`, which DSPy cannot parse:
1. `_strip_code_fences(None)` crashes with AttributeError
2. `REPLEntry(reasoning=None, code=None)` fails Pydantic validation

### Fix Applied
Two DSPy monkey patches + refusal detection in runner:

1. **`dspy_patches.py`** - `patch_strip_code_fences()`: Handles None code
2. **`dspy_patches.py`** - `patch_process_execution_result()`: Detects refusal, injects SUBMIT with refusal message
3. **`rlm_uniprot.py`** - Post-run refusal detection: checks `GLOBAL_HISTORY` for `finish_reason='refusal'`, sets `converged=False`

**Files modified**:
- `experiments/reasoningbank/tools/dspy_patches.py` - Two patches + refusal detection
- `experiments/reasoningbank/run/rlm_uniprot.py` - Post-run refusal detection

### Verification
- Task 5 no longer crashes; returns `converged=False, answer="LLM refused (13/13 calls refused by safety filter)"`
- Working tasks (Task 1) unaffected by patches

---

## Bug 3: No LM-as-Judge in S3 Results - FIXED

### Root Cause
The judge WAS implemented and called in `run_stochastic_uniprot()`, but the S3 experiment's result aggregation script (`run_experiment_s3.py`) crashed with a KeyError during post-processing. The reprocessing script used `converged` as a proxy for `success` instead of re-running the LLM judge.

### Fix Applied
Created `judge_s3_results.py` to re-run the LLM judge (deterministic, temperature=0.0) on all 100 S3 trajectories.

### Judgment Results

| Strategy | Pass@1 | Best-of-N | Pass@k |
|----------|--------|-----------|--------|
| none     | 80.0%  | 80.0%     | 76.0%  |
| prefix   | 80.0%  | 80.0%     | 76.0%  |
| thinking | 80.0%  | 80.0%     | 76.0%  |
| rephrase | 80.0%  | 80.0%     | 80.0%  |

**Key findings from LLM judge**:
- **80 converged trajectories judged**: 76/80 successful (95%)
- **4 false positives caught**: Task 2 rollout 5 (3 strategies) used incorrect `rdfs:subClassOf` pattern - judge correctly identified this as a failure despite convergence
- **20 non-converged** (Task 5): All `finish_reason='refusal'` - correctly marked as failures
- **Rephrase strategy slightly better**: 80% Pass@k vs 76% for others

**Files created**:
- `experiments/reasoningbank/judge_s3_results.py` - Re-judges S3 trajectories
- `experiments/reasoningbank/results/s3_prompt_perturbation/s3_judged_results.json` - Full judgment results

---

## Summary Table

| Bug | Severity | Root Cause | Status |
|-----|----------|------------|--------|
| **1. Missing llm_query** | Moderate | Not injected in LocalPythonInterpreter | **FIXED** |
| **2. Task 5 crash** | Critical | Safety filter false positive (Bordetella avium) | **FIXED** |
| **3. No LM-as-judge** | Critical | S3 aggregation crash lost judgment data | **FIXED** |

---

## Files Modified

### Bug 1
- `experiments/reasoningbank/tools/local_interpreter.py`
- `experiments/reasoningbank/tools/sparql.py`
- `experiments/reasoningbank/run/rlm_uniprot.py`

### Bug 2
- `experiments/reasoningbank/tools/dspy_patches.py` (new)
- `experiments/reasoningbank/run/rlm_uniprot.py`

### Bug 3
- `experiments/reasoningbank/judge_s3_results.py` (new)
- `experiments/reasoningbank/results/s3_prompt_perturbation/s3_judged_results.json` (generated)
