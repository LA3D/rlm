"""Agentic OWL+SHACL RLM runner with trajectory logging."""

from __future__ import annotations

import argparse
import json
import os
import re
from hashlib import sha256
from dataclasses import dataclass
from datetime import datetime, timezone
from functools import wraps
from pathlib import Path
from typing import Any

import dspy

from experiments.owl.agentic_ontology import AgenticOntologyWorkspace
from experiments.owl.agentic_tools import AgenticOwlToolset
from experiments.owl.owl_memory import OwlSymbolicMemory
from experiments.owl.symbolic_handles import SymbolicBlobStore
from experiments.reasoningbank.prototype.tools.dspy_patches import apply_all_patches
from experiments.reasoningbank.prototype.tools.local_interpreter import LocalPythonInterpreter


MAIN_MODEL = "anthropic/claude-sonnet-4-5-20250929"
SUB_MODEL = "anthropic/claude-haiku-4-5-20251001"


@dataclass
class CQRunResult:
    cq_id: str
    answer: str
    cq_passed_reported: str
    cq_passed_actual: bool
    shacl_conforms: bool
    iterations: int
    lm_usage: dict[str, Any]
    leakage: dict[str, Any]
    memory_episode_id: str
    memory_pattern_key: str
    operator_counts: dict[str, int]


@dataclass
class LeakageMetrics:
    stdout_chars: int = 0
    large_returns: int = 0
    subcalls: int = 0
    vars_n: int = 0


class JsonlTrajectoryLogger:
    def __init__(self, path: Path) -> None:
        self.path = path
        self.path.parent.mkdir(parents=True, exist_ok=True)

    def log(self, event_type: str, data: dict[str, Any]) -> None:
        event = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "event_type": event_type,
            "data": data,
        }
        with self.path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(event) + "\n")


def ensure_lm(model: str = MAIN_MODEL) -> None:
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        raise ValueError("Set ANTHROPIC_API_KEY for live RLM runs.")
    dspy.configure(lm=dspy.LM(model, api_key=api_key, temperature=0.0))


def _preview(value: Any, limit: int = 300) -> str:
    text = str(value)
    if len(text) <= limit:
        return text
    return text[:limit] + "...<truncated>"


def _wrap_tools_with_logging(
    raw_tools: dict[str, Any],
    logger: JsonlTrajectoryLogger,
    run_id: str,
    cq_id: str,
    leakage: LeakageMetrics,
    operator_counts: dict[str, int],
) -> dict[str, Any]:
    wrapped: dict[str, Any] = {}
    for name, fn in raw_tools.items():
        @wraps(fn)
        def _wrapper(*args, __name=name, __fn=fn, **kwargs):
            if __name.startswith("op_"):
                operator_counts[__name] = operator_counts.get(__name, 0) + 1
            logger.log(
                "tool_call",
                {
                    "run_id": run_id,
                    "cq_id": cq_id,
                    "tool": __name,
                    "args": [_preview(a) for a in args],
                    "kwargs": {k: _preview(v) for k, v in kwargs.items()},
                },
            )
            error = None
            try:
                result = __fn(*args, **kwargs)
            except Exception as exc:
                error = str(exc)
                result = {"error": str(exc), "exception_type": type(exc).__name__}
            result_len = len(str(result))
            if result_len > 1000:
                leakage.large_returns += 1
            logger.log(
                "tool_result",
                {
                    "run_id": run_id,
                    "cq_id": cq_id,
                    "tool": __name,
                    "error": error,
                    "result_size": result_len,
                    "result_preview": _preview(result, limit=1200),
                },
            )
            return result

        wrapped[name] = _wrapper
    return wrapped


def _extract_lm_usage(history_before: int, history_after: int) -> dict[str, Any]:
    out = {
        "total_calls": 0,
        "prompt_tokens": 0,
        "completion_tokens": 0,
        "total_tokens": 0,
        "cache_read_tokens": 0,
        "cache_creation_tokens": 0,
        "total_cost": 0.0,
    }
    if not hasattr(dspy.settings, "lm") or not hasattr(dspy.settings.lm, "history"):
        return out
    calls = dspy.settings.lm.history[history_before:history_after]
    for call in calls:
        out["total_calls"] += 1
        usage = call.get("usage", {})
        out["prompt_tokens"] += usage.get("prompt_tokens", 0)
        out["completion_tokens"] += usage.get("completion_tokens", 0)
        out["total_tokens"] += usage.get("total_tokens", 0)
        out["cache_read_tokens"] += usage.get("cache_read_input_tokens", 0)
        out["cache_creation_tokens"] += usage.get("cache_creation_input_tokens", 0)
        out["total_cost"] += call.get("cost", 0.0)
    return out


def _response_text(entry: dict[str, Any]) -> str:
    outputs = entry.get("outputs")
    if isinstance(outputs, list) and outputs:
        return str(outputs[0])
    response = entry.get("response")
    if response and hasattr(response, "choices") and response.choices:
        choice = response.choices[0]
        if hasattr(choice, "message") and choice.message:
            return str(choice.message.content)
    return ""


def _extract_reasoning_and_code(response_text: str) -> tuple[str, str]:
    reasoning = ""
    code = ""
    if not response_text:
        return reasoning, code
    reasoning_match = re.search(
        r"\[\[\s*##\s*reasoning\s*##\s*\]\]\s*(.*?)(?:\[\[\s*##|$)",
        response_text,
        re.DOTALL | re.IGNORECASE,
    )
    if reasoning_match:
        reasoning = reasoning_match.group(1).strip()
    code_match = re.search(
        r"\[\[\s*##\s*code\s*##\s*\]\]\s*```python\s*(.*?)\s*```",
        response_text,
        re.DOTALL | re.IGNORECASE,
    )
    if not code_match:
        code_match = re.search(
            r"\[\[\s*##\s*code\s*##\s*\]\]\s*\n(.*?)(?:\[\[\s*##|$)",
            response_text,
            re.DOTALL,
        )
    if code_match:
        code = code_match.group(1).strip()
        if code.endswith("```"):
            code = code[:-3].strip()
    return reasoning, code


def _extract_output_from_next_entry(history: list[dict[str, Any]], idx: int) -> str:
    if idx + 1 >= len(history):
        return ""
    nxt = history[idx + 1]
    messages = nxt.get("messages", [])
    if not isinstance(messages, list):
        return ""
    for msg in messages:
        if msg.get("role") != "user":
            continue
        content = str(msg.get("content", ""))
        m = re.search(r"Output[^:]*:\s*(.*?)(?=\n===\s*Step|\[\[\s*##|$)", content, re.DOTALL)
        if m:
            return m.group(1).strip()
    return ""


def _build_context(prompt_ref: dict[str, Any], cq_details: dict[str, Any]) -> str:
    return (
        "You are running in strict symbolic RLM mode.\n"
        "Rules:\n"
        "1) Prompt P is symbolic; inspect P only via bounded prompt_* tools.\n"
        "2) Use cq_query_symbols for required triples/filters; avoid reconstructing queries from text windows.\n"
        "3) Call cq_anchor_nodes first and only mutate allowed nodes.\n"
        "4) Prefer additive operators (op_add_*) for multi-valued properties.\n"
        "5) Use ontology_signature_index and ontology_validate_focus for compact SHACL guidance.\n"
        "6) Keep large artifacts behind handles. Avoid repeated handle_read_window loops.\n"
        "7) Validate with ontology_validate and verify with cq_eval before SUBMIT.\n"
        "8) End by calling SUBMIT(answer=..., cq_id=..., cq_passed=...).\n"
        f"Prompt handle metadata: {prompt_ref}\n"
        f"Current CQ: {cq_details}\n"
    )


def _add_memory_item(
    owl_memory: OwlSymbolicMemory,
    blob_store: SymbolicBlobStore,
    kind: str,
    title: str,
    summary: str,
    content: str,
    tags: list[str] | None = None,
) -> dict:
    content_ref = blob_store.put(content, kind=f"{kind.lower()}_content")
    content_hash = sha256(content.encode("utf-8")).hexdigest()[:16]
    meta = owl_memory.add_item(
        kind=kind,
        title=title,
        summary=summary,
        content_key=content_ref.key,
        content_hash=content_hash,
        tags=tags or [],
    )
    meta["content_ref"] = content_ref.to_dict()
    return meta


def run_single_cq(
    workspace: AgenticOntologyWorkspace,
    prompt_text: str,
    cq_id: str,
    logger: JsonlTrajectoryLogger,
    model: str,
    sub_model: str,
    max_iters: int,
    max_calls: int,
    use_local_interpreter: bool,
    blob_store: SymbolicBlobStore,
    owl_memory: OwlSymbolicMemory,
) -> CQRunResult:
    toolset = AgenticOwlToolset(
        prompt_text=prompt_text,
        workspace=workspace,
        blob_store=blob_store,
        owl_memory=owl_memory,
        current_cq_id=cq_id,
    )
    cq_details = toolset.cq_details(cq_id)
    if "error" in cq_details:
        raise ValueError(cq_details["error"])
    run_id = f"{cq_id}_{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S')}"
    logger.log(
        "run_start",
        {
            "run_id": run_id,
            "cq_id": cq_id,
            "model": model,
            "sub_model": sub_model,
            "max_iters": max_iters,
            "max_calls": max_calls,
        },
    )
    leakage = LeakageMetrics()
    operator_counts: dict[str, int] = {}

    raw_tools = {fn.__name__: fn for fn in toolset.as_tools()}
    wrapped_dict = _wrap_tools_with_logging(
        raw_tools=raw_tools,
        logger=logger,
        run_id=run_id,
        cq_id=cq_id,
        leakage=leakage,
        operator_counts=operator_counts,
    )
    wrapped_tools = list(wrapped_dict.values())

    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        raise ValueError("Set ANTHROPIC_API_KEY for live RLM runs.")
    sub_lm = dspy.LM(sub_model, api_key=api_key, temperature=0.0)
    interpreter = None
    if use_local_interpreter:
        interpreter = LocalPythonInterpreter(
            tools=wrapped_dict,
            output_fields=[{"name": "answer"}, {"name": "cq_id"}, {"name": "cq_passed"}],
            sub_lm=sub_lm,
        )

    rlm = dspy.RLM(
        "context, task -> answer, cq_id, cq_passed",
        max_iterations=max_iters,
        max_llm_calls=max_calls,
        tools=wrapped_tools,
        sub_lm=sub_lm,
        interpreter=interpreter,
    )

    context = _build_context(toolset.prompt_ref.to_dict(), cq_details)
    task = (
        f"Construct or repair ontology state so {cq_id} passes and SHACL conforms. "
        "Start with cq_query_symbols, apply operator deltas, then validate and submit."
    )

    history_before = len(dspy.settings.lm.history) if hasattr(dspy.settings.lm, "history") else 0
    out = rlm(context=context, task=task)
    history_after = len(dspy.settings.lm.history) if hasattr(dspy.settings.lm, "history") else history_before
    lm_usage = _extract_lm_usage(history_before, history_after)
    leakage.subcalls = lm_usage.get("total_calls", 0)
    leakage.vars_n = len(getattr(blob_store, "_blobs", {}))

    history = list(getattr(rlm, "history", []) or [])
    for idx, entry in enumerate(history):
        text = _response_text(entry)
        reasoning, code = _extract_reasoning_and_code(text)
        output = _extract_output_from_next_entry(history, idx)
        logger.log(
            "iteration",
            {
                "run_id": run_id,
                "cq_id": cq_id,
                "iteration": idx + 1,
                "reasoning": reasoning[:2000],
                "code": code[:4000],
                "output": output[:2000],
            },
        )

    cq_eval = toolset.cq_eval(cq_id)
    validation = workspace.validate_graph(store=blob_store, max_results=25, include_rows=False)
    top_signatures = validation.get("top_signatures", [])
    top_signature = top_signatures[0]["signature"] if top_signatures else ""
    top_operator = ""
    if operator_counts:
        top_operator = max(operator_counts.items(), key=lambda x: x[1])[0]
    outcome = "pass" if bool(cq_eval.get("passed", False)) else "fail"
    pattern_key = "|".join([cq_id, top_signature or "none", top_operator or "none", outcome])
    episode_summary = (
        f"{cq_id} {outcome}; shacl_conforms={bool(validation.get('conforms', False))}; "
        f"top_operator={top_operator or 'none'}"
    )
    episode_payload = {
        "run_id": run_id,
        "cq_id": cq_id,
        "cq_passed_actual": bool(cq_eval.get("passed", False)),
        "shacl_conforms": bool(validation.get("conforms", False)),
        "top_signatures": top_signatures[:5],
        "operator_counts": operator_counts,
        "lm_usage": lm_usage,
        "leakage": {
            "stdout_chars": leakage.stdout_chars,
            "large_returns": leakage.large_returns,
            "subcalls": leakage.subcalls,
            "vars_n": leakage.vars_n,
        },
        "validation_refs": {
            "report_text_ref": validation.get("report_text_ref", {}),
            "report_ttl_ref": validation.get("report_ttl_ref", {}),
            "violations_ref": validation.get("violations_ref", {}),
            "signatures_ref": validation.get("signatures_ref", {}),
        },
    }
    episode_meta = _add_memory_item(
        owl_memory=owl_memory,
        blob_store=blob_store,
        kind="episode",
        title=f"{cq_id} {run_id}",
        summary=episode_summary,
        content=json.dumps(episode_payload, ensure_ascii=True),
        tags=["agentic_owl", cq_id.lower(), outcome],
    )
    summary = {
        "run_id": run_id,
        "cq_id": cq_id,
        "answer": str(getattr(out, "answer", "")),
        "cq_passed_reported": str(getattr(out, "cq_passed", "")),
        "cq_passed_actual": bool(cq_eval.get("passed", False)),
        "shacl_conforms": bool(validation.get("conforms", False)),
        "iterations": len(history),
        "lm_usage": lm_usage,
        "operator_counts": operator_counts,
        "memory_episode_id": episode_meta.get("item_id", ""),
        "memory_pattern_key": pattern_key,
        "leakage": {
            "stdout_chars": leakage.stdout_chars,
            "large_returns": leakage.large_returns,
            "subcalls": leakage.subcalls,
            "vars_n": leakage.vars_n,
        },
    }
    logger.log("run_complete", summary)

    return CQRunResult(
        cq_id=cq_id,
        answer=summary["answer"],
        cq_passed_reported=summary["cq_passed_reported"],
        cq_passed_actual=summary["cq_passed_actual"],
        shacl_conforms=summary["shacl_conforms"],
        iterations=summary["iterations"],
        lm_usage=summary["lm_usage"],
        leakage=summary["leakage"],
        memory_episode_id=summary["memory_episode_id"],
        memory_pattern_key=summary["memory_pattern_key"],
        operator_counts=summary["operator_counts"],
    )


def run_sprint1(
    ontology_path: str,
    shapes_path: str,
    out_dir: str,
    cqs: list[str] | None,
    model: str,
    sub_model: str,
    max_iters: int,
    max_calls: int,
    use_local_interpreter: bool,
) -> dict[str, Any]:
    ensure_lm(model=model)
    apply_all_patches()

    workspace = AgenticOntologyWorkspace(ontology_path=ontology_path, shapes_path=shapes_path)
    available = [row["cq_id"] for row in workspace.list_cqs()]
    run_cqs = [cq for cq in (cqs or available) if cq in available]
    if not run_cqs:
        raise ValueError(f"No valid CQs selected. Available: {available}")

    ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    out_root = Path(out_dir)
    out_root.mkdir(parents=True, exist_ok=True)
    log_path = out_root / f"trajectory_{ts}.jsonl"
    summary_path = out_root / f"summary_{ts}.json"
    logger = JsonlTrajectoryLogger(log_path)

    blob_store = SymbolicBlobStore()
    owl_memory = OwlSymbolicMemory()
    runs: list[dict[str, Any]] = []
    pattern_counts: dict[str, int] = {}
    compiled_principles: list[dict[str, Any]] = []

    for cq_id in run_cqs:
        prompt_text = (
            f"Agentic ontology construction task for {cq_id}. "
            "Use symbolic tools, SHACL feedback, and minimal repair operators."
        )
        result = run_single_cq(
            workspace=workspace,
            prompt_text=prompt_text,
            cq_id=cq_id,
            logger=logger,
            model=model,
            sub_model=sub_model,
            max_iters=max_iters,
            max_calls=max_calls,
            use_local_interpreter=use_local_interpreter,
            blob_store=blob_store,
            owl_memory=owl_memory,
        )
        runs.append(
            {
                "cq_id": result.cq_id,
                "answer": result.answer,
                "cq_passed_reported": result.cq_passed_reported,
                "cq_passed_actual": result.cq_passed_actual,
                "shacl_conforms": result.shacl_conforms,
                "iterations": result.iterations,
                "lm_usage": result.lm_usage,
                "leakage": result.leakage,
                "memory_episode_id": result.memory_episode_id,
                "memory_pattern_key": result.memory_pattern_key,
                "operator_counts": result.operator_counts,
            }
        )
        key = result.memory_pattern_key
        if not key:
            continue
        count = pattern_counts.get(key, 0) + 1
        pattern_counts[key] = count
        if count != 2:
            continue
        parts = key.split("|", 3)
        if len(parts) != 4:
            continue
        key_cq, key_signature, key_operator, key_outcome = parts
        principle_meta = _add_memory_item(
            owl_memory=owl_memory,
            blob_store=blob_store,
            kind="principle",
            title=f"{key_cq} {key_operator} {key_outcome}",
            summary="Compiled from repeated episode pattern",
            content=json.dumps(
                {
                    "pattern_key": key,
                    "cq_id": key_cq,
                    "violation_signature": key_signature,
                    "operator": key_operator,
                    "outcome": key_outcome,
                    "observed_count": count,
                },
                ensure_ascii=True,
            ),
            tags=["agentic_owl", "compiled_principle", key_cq.lower(), key_outcome],
        )
        compiled_principles.append(
            {"pattern_key": key, "item_id": principle_meta.get("item_id", ""), "observed_count": count}
        )

    snapshot_file = out_root / f"working_graph_{ts}.ttl"
    graph_snapshot = workspace.save_snapshot(str(snapshot_file))
    final_validation = workspace.validate_graph(store=blob_store, max_results=50)
    summary = {
        "timestamp": ts,
        "model": model,
        "sub_model": sub_model,
        "ontology_path": ontology_path,
        "shapes_path": shapes_path,
        "cqs": run_cqs,
        "trajectory_log": str(log_path),
        "graph_snapshot": graph_snapshot,
        "final_validation": {
            "conforms": final_validation.get("conforms", False),
            "validation_results": final_validation.get("validation_results", 0),
        },
        "memory_stats": owl_memory.stats(),
        "compiled_principles": compiled_principles,
        "runs": runs,
    }
    with summary_path.open("w", encoding="utf-8") as f:
        json.dump(summary, f, indent=2)
    return summary


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run agentic OWL+SHACL sprint-1 with trajectory logs.")
    parser.add_argument("--ontology-path", default="ontology/core-vocabulary.ttl")
    parser.add_argument("--shapes-path", default="ontology/core-shapes.ttl")
    parser.add_argument("--out-dir", default="experiments/owl/results/agentic_sprint1")
    parser.add_argument("--cqs", default="", help="Comma-separated CQ ids (default: all sprint-1 CQs)")
    parser.add_argument("--model", default=MAIN_MODEL)
    parser.add_argument("--sub-model", default=SUB_MODEL)
    parser.add_argument("--max-iters", type=int, default=12)
    parser.add_argument("--max-calls", type=int, default=40)
    parser.add_argument("--no-local-interpreter", action="store_true")
    return parser.parse_args()


def main() -> None:
    args = _parse_args()
    cqs = [x.strip() for x in args.cqs.split(",") if x.strip()] or None
    summary = run_sprint1(
        ontology_path=args.ontology_path,
        shapes_path=args.shapes_path,
        out_dir=args.out_dir,
        cqs=cqs,
        model=args.model,
        sub_model=args.sub_model,
        max_iters=args.max_iters,
        max_calls=args.max_calls,
        use_local_interpreter=not args.no_local_interpreter,
    )
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
