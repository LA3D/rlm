"""
Quick experiment: Can DSPy `dspy.RLM` drive this repo's bounded ontology tools?

This uses a host-side CodeInterpreter (in-process exec) so DSPy can interact with
rdflib/GraphMeta handles via *tools* (closures), preserving the "handles not dumps"
discipline.

Run (from repo root):
  source ~/uvws/.venv/bin/activate
  XDG_CACHE_HOME=/tmp/dspy_cache DSPY_CACHE_DIR=/tmp/dspy_cache \\
    python examples/dspy_rlm_quick_experiment.py
"""

from __future__ import annotations

from dataclasses import dataclass, field
from io import StringIO
from pathlib import Path
import os
import sys
import time
from typing import Any, Callable


def _ensure_writable_cache_dir() -> None:
    cache_dir = os.environ.get("DSPY_CACHE_DIR") or os.environ.get("XDG_CACHE_HOME") or "/tmp/dspy_cache"
    os.environ.setdefault("XDG_CACHE_HOME", cache_dir)
    os.environ.setdefault("DSPY_CACHE_DIR", cache_dir)
    Path(cache_dir).mkdir(parents=True, exist_ok=True)


class _SubmitCalled(Exception):
    def __init__(self, payload: dict[str, Any]):
        self.payload = payload


@dataclass
class NamespaceCodeInterpreter:
    """Host-Python interpreter for DSPy RLM (non-sandboxed).

    State persists across execute() calls (DSPy iterations).
    Tools are injected as globals each iteration by DSPy.
    """

    tools: dict[str, Callable[..., Any]] = field(default_factory=dict)
    output_fields: list[dict] | None = None
    _tools_registered: bool = False  # DSPy may toggle this attribute

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
        from dspy.primitives.code_interpreter import CodeInterpreterError, FinalOutput

        if not self._started:
            self.start()

        if variables:
            self._globals.update(variables)

        self._globals.update(self.tools)

        def SUBMIT(*args, **kwargs):
            if args:
                if len(args) == 1 and isinstance(args[0], dict) and not kwargs:
                    raise _SubmitCalled(args[0])
                raise CodeInterpreterError("SUBMIT only supports keyword args or a single dict argument.")
            raise _SubmitCalled(dict(kwargs))

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
            raise CodeInterpreterError(f"{type(e).__name__}: {e}") from e
        finally:
            sys.stdout, sys.stderr = old_stdout, old_stderr

        stdout = stdout_capture.getvalue()
        stderr = stderr_capture.getvalue().strip()
        if stderr:
            return f"[stderr]\n{stderr}\n\n[stdout]\n{stdout}"
        return stdout


def main() -> int:
    _ensure_writable_cache_dir()

    if not os.environ.get("ANTHROPIC_API_KEY"):
        print("Missing ANTHROPIC_API_KEY in environment.")
        return 2

    import dspy

    # Default to Anthropic models available on this key via LiteLLM.
    # Override with env vars if you want to try other snapshots.
    root_model = os.environ.get("DSPY_ROOT_MODEL", "anthropic/claude-sonnet-4-20250514")
    sub_model = os.environ.get("DSPY_SUB_MODEL", "anthropic/claude-3-5-haiku-20241022")

    dspy.configure(
        lm=dspy.LM(root_model, temperature=0.2, max_tokens=1200, cache=False)
    )
    sub_lm = dspy.LM(sub_model, temperature=0.2, max_tokens=1200, cache=False)

    from rlm.ontology import load_ontology, GraphMeta, search_entity, describe_entity, probe_relationships

    ns: dict[str, Any] = {}
    prov_path = Path("ontology/prov.ttl")
    load_ontology(str(prov_path), ns, name="prov_graph")
    prov_meta = GraphMeta(ns["prov_graph"], name="prov")

    def tool_search_entity(query: str, limit: int = 8, search_in: str = "all") -> list[dict]:
        """Search ontology entities by label/IRI/localname (bounded)."""
        limit = max(1, min(int(limit), 10))
        return search_entity(prov_meta, query, limit=limit, search_in=search_in)

    def tool_describe_entity(uri: str, limit: int = 12) -> dict:
        """Describe an entity by URI or CURIE (bounded outgoing_sample)."""
        limit = max(1, min(int(limit), 20))
        return describe_entity(prov_meta, uri, limit=limit)

    def tool_probe_relationships(uri: str, predicate: str | None = None, direction: str = "both", limit: int = 10) -> dict:
        """Probe 1-hop relationships for an entity (bounded)."""
        limit = max(1, min(int(limit), 15))
        return probe_relationships(prov_meta, uri, predicate=predicate, direction=direction, limit=limit)

    context = "\n".join(
        [
            "You are exploring an RDF ontology via bounded tools. Do not dump large structures.",
            prov_meta.summary(),
            "",
            "Goal: Answer the query grounded in retrieved evidence (e.g., describe_entity output).",
        ]
    )

    rlm = dspy.RLM(
        "query, context -> answer",
        max_iterations=int(os.environ.get("DSPY_MAX_ITERS", "6")),
        max_llm_calls=int(os.environ.get("DSPY_MAX_LLM_CALLS", "12")),
        verbose=True,
        tools={
            "search_entity": tool_search_entity,
            "describe_entity": tool_describe_entity,
            "probe_relationships": tool_probe_relationships,
        },
        sub_lm=sub_lm,
        interpreter=NamespaceCodeInterpreter(),
    )

    query = os.environ.get("DSPY_QUERY", "What is the Activity class?")
    pred = rlm(query=query, context=context)

    print("\n=== FINAL ANSWER ===\n")
    print(pred.answer)

    print("\n=== TRAJECTORY (first 2 steps) ===\n")
    traj = getattr(pred, "trajectory", [])
    for i, step in enumerate(traj[:2], 1):
        print(f"--- Step {i} ---")
        print(step)
        print()

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
