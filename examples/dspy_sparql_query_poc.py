"""
PoC: ontology-based SPARQL query construction with DSPy RLM + typed SUBMIT outputs.

This is a minimal demonstration of:
- bounded ontology affordances (search/describe)
- bounded local SPARQL execution (SELECT + LIMIT injection)
- structured/typed outputs via DSPy signature: {sparql, answer, evidence}

Run:
  source ~/uvws/.venv/bin/activate
  XDG_CACHE_HOME=/tmp/dspy_cache DSPY_CACHE_DIR=/tmp/dspy_cache \\
    python examples/dspy_sparql_query_poc.py

Notes:
- Uses a host-Python interpreter (non-sandboxed) to let DSPy drive our tools.
- Requires ANTHROPIC_API_KEY in environment.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from io import StringIO
from pathlib import Path
import os
import re
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
    """Host-Python interpreter for DSPy RLM (non-sandboxed)."""

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


def _inject_limit_select(query: str, limit: int) -> tuple[str, bool]:
    q = query.strip()
    q_upper = q.upper()
    if "SELECT" not in q_upper:
        return q, False
    if re.search(r"\bLIMIT\s+\d+\b", q_upper):
        return q, False
    # Insert LIMIT before ORDER BY if present
    order_match = re.search(r"\bORDER\s+BY\b", q_upper)
    if order_match:
        pos = order_match.start()
        return q[:pos] + f" LIMIT {int(limit)} " + q[pos:], True
    return q.rstrip() + f" LIMIT {int(limit)}", True


def main() -> int:
    _ensure_writable_cache_dir()

    if not os.environ.get("ANTHROPIC_API_KEY"):
        print("Missing ANTHROPIC_API_KEY in environment.")
        return 2

    import dspy

    root_model = os.environ.get("DSPY_ROOT_MODEL", "anthropic/claude-sonnet-4-20250514")
    sub_model = os.environ.get("DSPY_SUB_MODEL", "anthropic/claude-3-5-haiku-20241022")

    dspy.configure(lm=dspy.LM(root_model, temperature=0.2, max_tokens=1400, cache=False))
    sub_lm = dspy.LM(sub_model, temperature=0.2, max_tokens=1200, cache=False)

    from rlm.ontology import load_ontology, GraphMeta, search_entity, describe_entity

    prov_path = Path("ontology/prov.ttl")
    ns: dict[str, Any] = {}
    load_ontology(str(prov_path), ns, name="prov_graph")
    prov_meta = GraphMeta(ns["prov_graph"], name="prov")

    # Tools (closures over prov_meta)
    def tool_search_entity(query: str, limit: int = 8, search_in: str = "all") -> list[dict]:
        """Search entities by label/IRI/localname (bounded)."""
        limit = max(1, min(int(limit), 10))
        if search_in in ("classes", "class"):
            search_in = "all"
        return search_entity(prov_meta, query, limit=limit, search_in=search_in)

    def tool_describe_entity(uri: str, limit: int = 12) -> dict:
        """Describe an entity by URI or CURIE (bounded)."""
        limit = max(1, min(int(limit), 25))
        return describe_entity(prov_meta, uri, limit=limit)

    def tool_sparql_select(query: str, max_results: int = 25) -> dict:
        """Run a bounded SELECT query on the local ontology graph.

        - Injects LIMIT if missing.
        - Returns rows as JSON-serializable dicts (string values).
        """
        from rdflib import Graph

        max_results = max(1, min(int(max_results), 50))
        q2, injected = _inject_limit_select(query, max_results)
        result = prov_meta.graph.query(q2)

        rows: list[dict[str, str | None]] = []
        for row in list(result)[:max_results]:
            row_dict: dict[str, str | None] = {}
            for var in result.vars:
                val = row[var]
                row_dict[str(var)] = str(val) if val is not None else None
            rows.append(row_dict)

        cols = [str(v) for v in result.vars] if result.vars else []
        return {
            "type": "select",
            "limit_injected": injected,
            "columns": cols,
            "row_count": len(rows),
            "rows": rows,
        }

    sense = {
        "ontology_id": "prov",
        "uri_pattern": "http://www.w3.org/ns/prov#",
        "triple_count": prov_meta.triple_count,
        "class_count": len(prov_meta.classes),
        "property_count": len(prov_meta.properties),
        "available_indexes": {
            "by_label": True,
            "hierarchy": True,
            "domains": True,
            "ranges": True,
            "pred_freq": True,
        },
        "label_predicates": ["rdfs:label", "skos:prefLabel (if present)", "dc:title (if present)"],
        "description_predicates": ["rdfs:comment", "prov:definition (if present)"],
        "quick_hints": [
            "Resolve labels to URIs with search_entity() before writing SPARQL.",
            "Start with SELECT + LIMIT and inspect rows.",
        ],
    }

    prefixes = "\n".join(
        [
            "PREFIX prov: <http://www.w3.org/ns/prov#>",
            "PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>",
            "PREFIX rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#>",
            "PREFIX owl: <http://www.w3.org/2002/07/owl#>",
        ]
    )

    context = "\n".join(
        [
            "You are constructing SPARQL against a local RDF ontology graph.",
            "Use bounded tools; do not dump large structures.",
            "",
            "You MUST execute your SPARQL using sparql_select(...) and return the exact query you ran in `sparql`.",
            "You MUST ground the answer in returned rows and include those rows (or a small subset) in `evidence`.",
            "",
            "Ontology summary:",
            prov_meta.summary(),
            "",
            "Recommended prefixes:",
            prefixes,
        ]
    )

    class QueryConstructionSig(dspy.Signature):
        """Construct and execute a bounded SPARQL query, then answer with evidence."""

        query: str = dspy.InputField(desc="User question to answer using SPARQL on the local ontology graph.")
        sense: dict = dspy.InputField(desc="Compact, grounded ontology affordances and hints.")
        context: str = dspy.InputField(desc="Bounded context summary (prefixes, counts, constraints).")

        sparql: str = dspy.OutputField(desc="The exact SPARQL query that was executed (include PREFIXes).")
        answer: str = dspy.OutputField(desc="Final grounded answer in natural language (brief).")
        evidence: dict = dspy.OutputField(desc="Grounding evidence: result rows + key URIs used.")

    rlm = dspy.RLM(
        QueryConstructionSig,
        max_iterations=int(os.environ.get("DSPY_MAX_ITERS", "8")),
        max_llm_calls=int(os.environ.get("DSPY_MAX_LLM_CALLS", "16")),
        verbose=True,
        tools={
            "search_entity": tool_search_entity,
            "describe_entity": tool_describe_entity,
            "sparql_select": tool_sparql_select,
        },
        sub_lm=sub_lm,
        interpreter=NamespaceCodeInterpreter(),
    )

    default_query = "List up to 5 properties whose domain is the Activity class in this ontology."
    user_query = os.environ.get("DSPY_QUERY", default_query)

    pred = rlm(query=user_query, sense=sense, context=context)

    print("\n=== STRUCTURED OUTPUT ===\n")
    print("SPARQL:\n", pred.sparql)
    print("\nANSWER:\n", pred.answer)
    print("\nEVIDENCE:\n", pred.evidence)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())

