# Claudette → DSPy Migration Plan (RLM + ReasoningBank) and Required Custom Pieces

This document outlines what it would take to migrate this repo from a `claudette`-backed RLM loop to DSPy, and what we’d need to custom implement to run **DSPy’s `dspy.RLM` loop on top of the current “namespace REPL” model** (handles-not-dumps, rdflib objects in-process).

It also proposes a small, low-risk experiment to validate feasibility before committing to a larger refactor.

---

## 1) Current State (Claudette-Coupled RLM)

The core loop lives in `nbs/00_core.ipynb` (exported to `rlm/core.py`) and is coupled to `claudette` in two places:
- Root-model call in `rlm_run(...)` (iterative loop producing ```repl``` blocks)
- Sub-LLM calls in `llm_query(...)` and `llm_query_batched(...)`

Procedural memory (ReasoningBank-style) is implemented in `nbs/05_procedural_memory.ipynb` (`rlm/procedural_memory.py`) and relies on:
- `judge_trajectory()` and `extract_memories()` calling `llm_query()` (claudette)
- `retrieve_memories()` using lexical retrieval (currently `rank_bm25`, which we plan to replace)

We also have logging infrastructure in `nbs/03_logger.ipynb` (`rlm/logger.py`) that writes JSONL iteration logs.

---

## 2) What DSPy Brings (and What It Doesn’t)

### 2.1 DSPy `dspy.RLM`

DSPy includes an experimental `dspy.RLM` (`dspy.predict.rlm.RLM`) that:
- Runs an iterative “REPL + LLM code-writing” loop
- Exposes `llm_query` and `llm_query_batched` inside the REPL with an explicit call budget
- Uses a `CodeInterpreter` abstraction to execute code each iteration
- Uses `SUBMIT({...})` rather than `FINAL(...)` / `FINAL_VAR(...)`
- Returns a structured `trajectory` (REPL history entries: reasoning/code/output)

### 2.2 The key mismatch for this repo

Our ontology system depends on **in-process Python objects**:
- rdflib `Graph` / `Dataset`
- `GraphMeta` and various bounded “view” functions
- SPARQL result handles

DSPy’s default interpreter (`PythonInterpreter`) is a sandboxed Pyodide environment and typically cannot access these host Python objects. Therefore, to use `dspy.RLM` for ontology exploration we likely need a **custom `CodeInterpreter`** that runs code in the host Python process (or another trusted environment that can hold these objects).

---

## 3) Migration Options

### Option A — Keep our RLM loop; swap backend + judge/extractor to DSPy

This is the lowest-risk path:
- Keep `rlm_run` protocol (our rlmpaper-aligned prompt, `FINAL(...)` semantics).
- Introduce an `LLMBackend` interface and implement:
  - `ClaudetteBackend` (status quo)
  - `DSPyLMBackend` (using `dspy.LM`)
- Migrate `judge_trajectory()` / `extract_memories()` first to DSPy (since you already have DSPy ReasoningBank with judge).

Pros: minimal behavior drift in the RLM protocol.
Cons: doesn’t use DSPy’s `dspy.RLM`.

### Option B — Use DSPy `dspy.RLM` as the root loop (requires custom interpreter)

This gives you DSPy’s orchestration model (structured trajectory, tool surface, batching, budgets), but requires a host-side interpreter so the loop can interact with rdflib handles.

Pros: unified DSPy RLM + judge patterns; structured trajectory.
Cons: biggest behavior-change surface; DSPy RLM is marked experimental.

This document focuses on Option B (as requested).

---

## 4) What We Must Custom Implement for Option B

### 4.1 A host-side `CodeInterpreter` that executes against a persistent namespace

DSPy’s `CodeInterpreter` protocol (`dspy.primitives.code_interpreter.CodeInterpreter`) requires:
- a mutable `.tools` dict
- `start()`, `execute(code, variables)`, `shutdown()`
- `execute()` returns:
  - `FinalOutput(...)` if `SUBMIT()` is called
  - or captured stdout as `str` (or other supported outputs)

We need an interpreter that:
- Maintains state across iterations (like our `ns`)
- Injects input variables each iteration (DSPy passes `variables=dict(input_args)` each call)
- Exposes `.tools` callables as globals for code execution
- Provides `SUBMIT(...)` which triggers `FinalOutput(...)`
- Captures stdout/stderr
- Translates runtime errors into `CodeInterpreterError` (DSPy catches this as a recoverable iteration output)

### 4.2 A “tool surface” compatible with RLM invariants

We should assume the model will try to call *whatever it can see*.
To preserve “handles-not-dumps”:
- Prefer exposing bounded view functions as tools (or globals)
- Avoid exposing raw rdflib `Graph` variables directly (or name them defensively and discourage access)
- Ensure view functions return bounded summaries / handles

DSPy `dspy.RLM` supports user tools via `tools={...}`:
- Tools show up in the instruction template and are injected into the interpreter
- Tool docstrings are included, improving discoverability

### 4.3 Trajectory/observability integration

DSPy returns a `trajectory` list in the `Prediction`. We still want:
- JSONL logging aligned with our current format (`rlm/logger.py`)
- SQLite storage of trajectories + judgments + extracted memories (per the other design doc)

So we should add an adapter that converts DSPy REPL history entries into:
- our JSONL format (iteration boundaries)
- our “bounded trajectory artifact” for memory extraction

---

## 5) Sketch: `NamespaceCodeInterpreter` (host Python, persistent `ns`)

Below is an outline of what the adapter would look like. This is intentionally minimal: it executes code in-process with Python `exec`, so it is *not sandboxed*. (We can later harden it by restricting builtins, running in a subprocess, or using an allowlist-only environment.)

```python
from __future__ import annotations

from dataclasses import dataclass, field
from io import StringIO
import sys
import time
from typing import Any, Callable

from dspy.primitives.code_interpreter import CodeInterpreterError, FinalOutput


class _SubmitCalled(Exception):
    def __init__(self, payload: dict[str, Any]):
        self.payload = payload


@dataclass
class NamespaceCodeInterpreter:
    tools: dict[str, Callable[..., Any]] = field(default_factory=dict)
    output_fields: list[dict] | None = None
    _tools_registered: bool = False

    def __post_init__(self):
        self._started = False
        self._globals: dict[str, Any] = {}

    def start(self) -> None:
        if self._started:
            return
        self._globals = {}
        self._started = True

    def shutdown(self) -> None:
        self._globals.clear()
        self._started = False

    def execute(self, code: str, variables: dict[str, Any] | None = None) -> Any:
        if not self._started:
            self.start()

        # Inject variables each iteration (DSPy passes inputs here)
        if variables:
            self._globals.update(variables)

        # Inject tools as globals
        self._globals.update(self.tools)

        # Provide SUBMIT that returns FinalOutput
        def SUBMIT(**kwargs):
            raise _SubmitCalled(kwargs)

        self._globals["SUBMIT"] = SUBMIT

        stdout_capture = StringIO()
        stderr_capture = StringIO()
        old_stdout, old_stderr = sys.stdout, sys.stderr
        start = time.time()
        try:
            sys.stdout, sys.stderr = stdout_capture, stderr_capture
            exec(compile(code, "<dspy-repl>", "exec"), self._globals)
        except _SubmitCalled as e:
            return FinalOutput(e.payload)
        except SyntaxError:
            raise
        except Exception as e:
            # Return a DSPy-style recoverable error string
            raise CodeInterpreterError(f"{type(e).__name__}: {e}")
        finally:
            sys.stdout, sys.stderr = old_stdout, old_stderr

        stdout = stdout_capture.getvalue()
        stderr = stderr_capture.getvalue().strip()
        if stderr:
            # You can choose to surface stderr as output, or raise CodeInterpreterError.
            # Surface as output keeps the loop moving and matches “recoverable error” behavior.
            return f"[stderr]\\n{stderr}\\n\\n[stdout]\\n{stdout}"
        return stdout
```

Notes:
- DSPy’s default `PythonInterpreter` registers tools with typed signatures. Our host interpreter can ignore that and just expose callables.
- If we want typed SUBMIT signatures, we can use `output_fields` to validate keys and types inside `SUBMIT` before emitting `FinalOutput`.
- This gives the DSPy loop access to any globals we choose to preload (e.g., a `GraphMeta` handle). For safer behavior, preload only bounded tools.

---

## 6) Running DSPy RLM “on top of” our current namespace model

There are two practical approaches:

### Approach 1 — Tool-only access (recommended)

Keep the interpreter’s `_globals` minimal and expose only bounded view functions and store handles intentionally.

Example setup flow:
1. In host Python, load ontology and build `GraphMeta`.
2. Construct a tool dict that closes over the host objects.
3. Pass tools to `dspy.RLM(..., tools=tools, interpreter=NamespaceCodeInterpreter(...))`.

Pseudo-example:
```python
import dspy
from rlm.ontology import load_ontology, GraphMeta, search_entity, describe_entity

ns = {}
load_ontology("ontology/prov.ttl", ns, name="prov_graph")
prov_meta = GraphMeta(ns["prov_graph"], name="prov")

def search(label: str, limit: int = 5):
    return search_entity(prov_meta, label, limit=limit)

def describe(uri: str, limit: int = 15):
    return describe_entity(prov_meta, uri, limit=limit)

tools = {"search_entity": search, "describe_entity": describe}

interp = NamespaceCodeInterpreter(tools={})
rlm = dspy.RLM("query, context -> answer", max_iterations=10, tools=tools, interpreter=interp)

pred = rlm(query="What is Activity?", context="(sense + base context here)")
print(pred.answer)
```

Key point: the model never sees the rdflib graph in prompt metadata, and cannot trivially dump it unless you accidentally expose it.

### Approach 2 — Shared-namespace access (fastest PoC, less safe)

Populate the interpreter’s globals with your existing `ns` (Graph handles, GraphMeta, helpers).
This is closer to how `rlm_run(...)` works today, but increases risk of the model reaching for raw graphs.

If you do this for an experiment, add a strong instruction to avoid raw dumps and prefer view tools.

---

## 7) Mapping Protocol Differences (Our RLM vs DSPy RLM)

### 7.1 Termination: `FINAL(...)` vs `SUBMIT(...)`

- DSPy uses `SUBMIT(output_field=value, ...)` inside code to terminate with structured outputs.
- Our loop uses `FINAL(...)` markers parsed from model text and `FINAL_VAR(...)`.

If we adopt DSPy RLM, we should **embrace `SUBMIT`** (it’s built-in to DSPy’s loop). We can still provide a helper `FINAL_VAR` in globals if we want, but it’s redundant.

### 7.2 Prompting

DSPy RLM uses its own instruction template (`ACTION_INSTRUCTIONS_TEMPLATE`) and appends:
- variable metadata (“variables_info”)
- repl history
- iteration number

If we need rlmpaper-style safeguards (“explore first”) we can:
- rely on DSPy’s built-in instruction (it already says EXPLORE FIRST, ITERATE, PRINT)
- optionally add extra instructions via the signature’s docstring/instructions
- optionally add our own guardrails in the injected `context` input

### 7.3 Sub-LLM calls

DSPy RLM provides `llm_query` and `llm_query_batched` as tools backed by `dspy.settings.lm` (or `sub_lm`).
If we want “root LM” and “sub LM” split (like rlmpaper), use:
- `dspy.configure(lm=<root>)`
- pass `sub_lm=<smaller>` to `dspy.RLM(...)`

---

## 8) Logging / Trajectory Export

DSPy returns `Prediction(trajectory=[...])` where each entry has reasoning/code/output.

We should add a converter:
- `dspy_history_to_rlm_iterations(trajectory) -> list[RLMIteration]`
- or store DSPy’s raw trajectory JSON in SQLite and only convert for compatibility views.

For JSONL logs:
- Write one JSONL “iteration” per DSPy REPL entry.
- Store the same metadata we currently store: query, max_iters, ontology, memory_k, etc.

---

## 9) Quick Experiment (Feasibility Check)

Goal: demonstrate that DSPy `dspy.RLM` can drive ontology exploration using bounded tools and that we can capture useful trajectories.

### Experiment steps

1. Configure environment (avoid DSPy cache writing to read-only locations):
   - set `XDG_CACHE_HOME` to a writable directory (e.g., `/tmp/dspy_cache`)
2. Configure DSPy LM (choose the same model you use via claudette, or another provider).
3. Implement the `NamespaceCodeInterpreter` in a scratch script (or a notebook cell) and run:
   - A single PROV task: “What is Activity?”
4. Tools:
   - `search_entity(meta, label, limit)`
   - `describe_entity(meta, uri, limit)`
   - optionally `probe_relationships(meta, uri, limit)`
5. Confirm:
   - the model iterates (doesn’t one-shot)
   - it calls bounded tools and prints outputs
   - it terminates via `SUBMIT(answer=...)`
   - trajectory entries are captured and loggable

### Success criteria

- The model completes in ≤10 iterations and uses bounded tools.
- The captured trajectory can be converted into the existing “bounded artifact” format for memory extraction.
- No raw graph dumps appear in outputs (or if they do, we tighten tool surface).

---

## 10) Recommendation

If the quick experiment is successful:
- Proceed with the SQLite ReasoningBank architecture, but allow the “root RLM” to be selectable:
  - `backend=claudette` (current)
  - `backend=dspy_rlm` (new)
- Migrate judge/extractor to DSPy regardless (even if we keep the claudette loop), since this is high leverage and less risky.

If the experiment fails (e.g., tool discoverability is poor, or the model keeps trying to access hidden objects):
- Keep our current RLM loop and use DSPy only for judge/extractor, plus optional retrieval/reranking components.

