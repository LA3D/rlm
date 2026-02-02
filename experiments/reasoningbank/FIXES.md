# ReasoningBank Experiment Fixes (Trajectory + Tooling)

This document is a **portable checklist** (usable from a fresh git checkout on another machine) to diagnose and fix the remaining issues seen in Phase 1 runs, and to evaluate **Option A** (structured, execution-time trajectory capture) so we can choose the best approach.

It is written to be actionable even when absolute paths differ across computers.

---

## 0) Reproduce + Capture a Log

### Run command (local PROV)

From the repo root (`agents/rlm`), run (pick **one** of the following patterns):

**Option 1 (recommended if you use uv):**

```bash
PYTHONPATH="$PWD" uv run python experiments/reasoningbank/run/phase1.py \
  --ont ontology/prov.ttl --l0 --extract --verbose \
  2>&1 | tee experiments/reasoningbank/results/phase1_trajectory_test.log
```

**Option 2 (explicit venv python):**

```bash
source ~/uvws/.venv/bin/activate
PYTHONPATH="$PWD" python experiments/reasoningbank/run/phase1.py \
  --ont ontology/prov.ttl --l0 --extract --verbose \
  2>&1 | tee experiments/reasoningbank/results/phase1_trajectory_test.log
```

Notes:
- `PYTHONPATH="$PWD"` is required in this repo layout because the code imports `experiments.*` directly (see `experiments/reasoningbank/test_basic.py`).
- If you don’t use uv, any python with the project deps installed is fine; keep `PYTHONPATH="$PWD"`.

### Fast “is it fixed?” greps

```bash
rg -n "missing 2 required positional arguments|unexpected keyword argument 'limit'|slice\\(None, 10, None\\)" experiments/reasoningbank/results/phase1_trajectory_test.log
rg -n "Tool bridge error|ctx_peek error|ctx_stats error" experiments/reasoningbank/results/phase1_trajectory_test.log
```

---

## 1) Issues Observed in Recent Logs (What to Fix)

### A. “`g_classes()` slicing” error

Symptom in logs:
- The model does `classes = g_classes()` then `classes[:10]` which raises `slice(None, 10, None)` because `g_classes()` returns a **handle dict**, not a list.

Where it shows up:
- Example log: `experiments/reasoningbank/results/phase1_trajectory_test.log` (search for `slice(None, 10, None)`).

Root cause:
- Tool return type is not obvious to the model because tool docs are currently “No description” in the RLM tool listing (DSPy derives tool docs from the callable’s docstring; our tools are lambdas).
- `experiments/reasoningbank/core/graph.py` returns handle dicts for `g_classes/g_props/g_query` and expects the agent to use `ctx_peek(ctx_key)` / `ctx_slice(ctx_key, ...)`.

Fix direction:
- Ensure the RLM sees a clear contract: “these functions return handle dicts; inspect via ctx_*”.
- Optionally: adjust tools to return a list for `g_classes/g_props` to match agent expectations, but that trades off the “handles-not-payloads” invariant.

### B. `g_classes(limit=20)` “unexpected keyword argument”

Symptom:
- The model calls pythonically: `g_classes(limit=20)` and gets `unexpected keyword argument 'limit'`.

Where it originates:
- DSPy’s REPL is executing Python code that calls your tool function directly; if your tool wrapper signature is `(args=None, kwargs=None)` without `**kw`, then `limit=20` will raise.

Fix direction:
- Make tool wrappers accept both:
  - “DSPy tool convention”: `tool(args, kwargs)` (2 positional params), and
  - normal python calls: `tool(limit=20)` / `tool(q="...", limit=10)` / `tool("...")`.

References:
- DSPy tool docs are generated from callable signatures in `dspy/predict/rlm.py` (`_format_tool_docs`) and code is executed after `_strip_code_fences()` in `_execute_iteration()`.

### C. `ctx_peek(['key'], {})` / `ctx_slice(['key'], {})` pattern

Symptom:
- The agent sometimes passes list-wrapped keys (e.g., `['results_7']`) because it is mixing calling conventions.

Fix direction:
- Tools should robustly handle list-wrapped keys by unwrapping the first element.
- Tools should also accept direct calls `ctx_peek('results_7')` and `ctx_slice('results_7', 0, 200)`.

### D. Markdown fences inside `[[ ## code ## ]]`

Symptom:
- The model sometimes emits fenced blocks inside code (“```python … ```”), even though DSPy strips fences before execution.

Reality check:
- DSPy already strips a *single* outer fence via `_strip_code_fences()` in `dspy/predict/rlm.py`.
- This is more of a **trajectory readability** and **downstream extractor grounding** issue than an execution correctness issue.

Fix direction:
- Reinforce instruction (“never output fences in code field”) and/or post-process the logged code for analysis.

---

## 2) Trajectory Extraction Reliability: Regex vs Option A

You asked: is regex parsing fragile? Yes.

### Current situation in this repo

Local runner code (`experiments/reasoningbank/run/rlm.py`) historically attempted to reconstruct trajectories by parsing DSPy RLM internal history message text with regex (see `experiments/reasoningbank/TRAJECTORY_FIX.md` and `experiments/reasoningbank/OUTPUT_EXTRACTION_FIX.md` for the approach).

That approach is fragile because it depends on:
- DSPy’s internal history entry format (`rlm.history` structure),
- how messages are serialized,
- and how “repl_history” blocks are embedded.

### Option A (preferred): use DSPy’s built-in structured trajectory

**Key finding:** DSPy RLM already records structured steps as `REPLHistory` and returns them as `Prediction.trajectory` (list of dicts).

How this works (DSPy v3.1.2):
- Code execution happens in `dspy/predict/rlm.py` in `_execute_iteration()`.
- After each iteration, DSPy appends `reasoning`, `code`, and formatted `output` to a `REPLHistory` via `_process_execution_result()`.
- When FINAL is produced, DSPy returns:
  - `Prediction(..., trajectory=[e.model_dump() for e in final_history], final_reasoning=...)`

Why Option A is more reliable:
- No text parsing required.
- No dependence on message formatting.
- The trajectory is already structured as `{reasoning, code, output}` at the right granularity.

Tradeoffs / gotchas:
- DSPy stores the *original* model code (`pred.code`) in trajectory; execution uses `_strip_code_fences(pred.code)` first, so the stored code may still include fences even if execution didn’t.
- Output is truncated by DSPy’s `max_output_chars` (default 100,000). This is usually fine; you can tighten it for leakage control.

How to assess feasibility on a new machine:
1. Locate DSPy RLM source:
   ```bash
   python -c "import dspy.predict.rlm as r; print(r.__file__)"
   ```
2. Confirm trajectory exists in returned predictions:
   - In your runner, print `hasattr(res, 'trajectory')` and inspect `type(res.trajectory)`.
3. Confirm it includes `code` and `output` per step (it should).

Decision recommendation:
- Prefer Option A unless you have a hard requirement to recover *additional* information that DSPy does not record (e.g., the fence-stripped code, or richer interpreter metadata). If you do, extend Option A by capturing metadata in a controlled way rather than parsing text.

---

## 3) What Would Be Needed for Option A (Execution-Time Capture)

There are two sub-variants:

### A1) “Pure Option A”: consume `Prediction.trajectory` (no DSPy patching)

You would update the experiment runner to:
- Use `res.trajectory` directly for downstream extractors and logging.
- Stop parsing `rlm.history` text.

Minimal changes expected:
- In the local runner (`experiments/reasoningbank/run/rlm.py`):
  - Set `Result.trajectory = getattr(res, 'trajectory', [])`.
  - (Optional) Set `Result.thinking = getattr(res, 'final_reasoning', None)` if useful.
- In formatters/extractors (`experiments/reasoningbank/run/phase1.py`):
  - Ensure `format_trajectory()` expects list entries containing `code` and `output`.

Risk:
- Very low. This uses public DSPy behavior.

### A2) “Augmented Option A”: capture executed code (post-fence-strip) + richer metadata

If you need the exact code that executed (not the original fenced code), or want per-step tool call counts, etc., you have two approaches:

1) Patch/extend DSPy RLM:
   - In `dspy/predict/rlm.py`, `_execute_iteration()` computes `code = _strip_code_fences(action.code)` before executing.
   - DSPy currently logs `pred.code` to history, not `code`.
   - A patch could store both `pred.code` and `executed_code` in history.

2) Wrap the interpreter:
   - DSPy executes `repl.execute(code, variables=dict(input_args))`.
   - A wrapper around `CodeInterpreter.execute()` could log `(executed_code, result)` plus timing.
   - This avoids modifying DSPy internals but requires a custom `CodeInterpreter` implementation (or a decorator around the interpreter object used in `RLM._interpreter_context()`).

Decision criteria for A2:
- Choose A2 only if fenced/unfenced code differences are materially affecting your extraction quality or reproducibility.

---

## 4) Tooling Fix Plan (to eliminate remaining trajectory errors)

Goal: make tools “hard to misuse” regardless of whether the model calls them:
- as `tool(args, kwargs)` (DSPy tool convention), or
- as normal python `tool(x=..., y=...)`.

Concrete required behavior:
1. Accept keyword arguments like `limit=20` on `g_classes` / `g_props`.
2. For `ctx_peek` / `ctx_slice`:
   - accept `ctx_peek('results_7')`
   - accept `ctx_peek(['results_7'], {})`
   - accept `ctx_slice('results_7', 0, 200)`
3. Improve tool docstrings so DSPy prints meaningful help (avoid “No description”), which directly reduces misuse.

Primary code location:
- `experiments/reasoningbank/ctx/builder.py` (tool wrapper definitions)

Supporting code:
- `experiments/reasoningbank/core/graph.py` (handle types and conventions)
- `experiments/reasoningbank/core/blob.py` (store API)

Verification:
- Re-run Phase 1 and confirm `phase1_trajectory_test.log` contains none of:
  - `unexpected keyword argument 'limit'`
  - `slice(None, 10, None)`
  - `Tool bridge error`

---

## 5) Appendix: Relevant Upstream DSPy Internals (for Option A)

If you need to review upstream behavior:
- DSPy RLM file location can be printed via:
  ```bash
  python -c "import dspy.predict.rlm as r; print(r.__file__)"
  ```
- In DSPy v3.1.2, the following functions are the key references:
  - `_strip_code_fences()` (strips outer ``` fences before execution)
  - `_execute_iteration()` (generates action + executes code)
  - `_process_execution_result()` (appends `{reasoning, code, output}` to REPLHistory)
  - `forward()` (returns `Prediction` with `.trajectory`)

This is the basis for Option A: **consume `Prediction.trajectory` directly**.
