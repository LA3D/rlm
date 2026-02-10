"""DSPy RLM runner for KAG QA: answers competency questions over enriched graphs.

Read-only: loads a pre-built TTL + content store and explores via bounded view tools.
Runs one RLM call per question, capturing trajectories that show how the agent
uses (or fails to use) the graph structure.
"""

from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import dspy

from experiments.KAG.kag_qa_tools import KagQAToolset
from experiments.KAG.rlm_kag_runner import (
    MAIN_MODEL,
    SUB_MODEL,
    JsonlTrajectoryLogger,
    LeakageMetrics,
    _extract_lm_usage,
    _preview,
    _wrap_tools_with_logging,
)
from experiments.reasoningbank.prototype.tools.dspy_patches import apply_all_patches


def _build_qa_task() -> str:
    return (
        "Answer the question about a scientific paper using the graph exploration tools.\n"
        "The context above contains graph stats and section listings — do NOT call\n"
        "tools just for orientation. Jump straight to the question.\n"
        "\n"
        "## Available Tools\n"
        "  g_section_content(section_iri)  — content nodes in a section (type, preview, page)\n"
        "  g_node_detail(node_iri)         — full properties of a single node\n"
        "  g_search(query, limit=10)       — full-text search over content\n"
        "  g_figure_info(figure_iri)       — caption + page + image description + referring paragraphs\n"
        "  g_node_refs(node_iri)           — bidirectional relationships (cites/cited-by, refs/referred-by)\n"
        "\n"
        "## Strategy\n"
        "1. Read the section listing in the context to find relevant sections\n"
        "2. Use g_search() to find relevant content by keywords\n"
        "3. Drill into specific nodes with g_section_content() or g_node_detail()\n"
        "4. Use g_node_refs() for citations and cross-references (works on any node type)\n"
        "5. SUBMIT(answer='your detailed answer with evidence')\n"
        "\n"
        "## IRI Format\n"
        "Use compact IRIs: 'ex:b_p002_0005' or 'ex:section_01'\n"
        "Section IRIs are listed in the context above.\n"
        "\n"
        "## Answer Format\n"
        "Provide a clear, specific answer grounded in the graph content.\n"
        "Reference specific nodes (IRIs) and content you found.\n"
        "If the graph doesn't contain enough information, say so.\n"
    )


def run_rlm_kag_qa(
    graph_dir: str,
    questions_path: str,
    paper: str | None = None,
    out_dir: str = "experiments/KAG/results",
    run_name: str = "kag_qa",
    model: str = MAIN_MODEL,
    sub_model: str = SUB_MODEL,
    max_iters: int = 10,
    max_calls: int = 30,
) -> dict[str, Any]:
    """Run QA agent over an enriched KAG graph, one RLM call per question."""
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        raise ValueError("Set ANTHROPIC_API_KEY for live RLM runs.")

    apply_all_patches()
    dspy.configure(lm=dspy.LM(model, api_key=api_key, temperature=0.0))

    graph_path = Path(graph_dir)
    ttl_path = graph_path / "knowledge_graph.ttl"
    content_store_path = graph_path / "content_store.jsonl"
    if not ttl_path.exists():
        raise ValueError(f"knowledge_graph.ttl not found in {graph_path}")
    if not content_store_path.exists():
        raise ValueError(f"content_store.jsonl not found in {graph_path}")

    # Load questions
    questions = json.loads(Path(questions_path).read_text(encoding="utf-8"))
    if paper:
        questions = [q for q in questions if q["paper"] == paper]
    if not questions:
        raise ValueError(f"No questions found for paper={paper!r}")

    ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    paper_tag = f"_{paper}" if paper else ""
    run_id = f"{run_name}{paper_tag}_{ts}"
    run_out = Path(out_dir) / run_id
    run_out.mkdir(parents=True, exist_ok=True)
    (run_out / "answers").mkdir(exist_ok=True)

    logger = JsonlTrajectoryLogger(run_out / "trajectory.jsonl")

    # Load graph ONCE and build context
    toolset = KagQAToolset(str(ttl_path), str(content_store_path))
    graph_stats = toolset._stats()
    context = toolset.build_context()

    logger.log("run_start", {
        "run_id": run_id,
        "graph_dir": str(graph_path),
        "paper": paper,
        "model": model,
        "sub_model": sub_model,
        "max_iters": max_iters,
        "questions": len(questions),
        "graph_stats": graph_stats,
        "context_length": len(context),
    })

    task = _build_qa_task()
    # Merge context (graph overview + sections) with task instructions
    full_context = context + "\n\n" + task
    sub_lm = dspy.LM(sub_model, api_key=api_key, temperature=0.0)
    total_cost = 0.0
    results: list[dict[str, Any]] = []

    for qi, q in enumerate(questions):
        qid = q["id"]
        question_text = q["question"]
        print(f"\n[{qi+1}/{len(questions)}] {qid}: {question_text}")

        leakage = LeakageMetrics()
        operator_counts: dict[str, int] = {}
        tool_counts: dict[str, int] = {}

        # Build per-question tool dict from the shared toolset (5 tools)
        qa_tools = {
            "g_section_content": toolset.g_section_content,
            "g_node_detail": toolset.g_node_detail,
            "g_search": toolset.g_search,
            "g_figure_info": toolset.g_figure_info,
            "g_node_refs": toolset.g_node_refs,
        }

        wrapped_dict = _wrap_tools_with_logging(
            raw_tools=qa_tools,
            logger=logger,
            run_id=f"{run_id}/{qid}",
            leakage=leakage,
            operator_counts=operator_counts,
        )
        # Add counting wrapper for all tools (operator_counts only tracks op_*)
        for tname, tfn in list(wrapped_dict.items()):
            _tn = tname
            _tf = tfn
            def _counting(*a, __n=_tn, __f=_tf, **kw):
                tool_counts[__n] = tool_counts.get(__n, 0) + 1
                return __f(*a, **kw)
            _counting.__name__ = tfn.__name__
            _counting.__doc__ = tfn.__doc__
            _counting.__wrapped__ = tfn
            wrapped_dict[tname] = _counting
        wrapped_tools = list(wrapped_dict.values())

        logger.log("question_start", {
            "run_id": run_id,
            "question_id": qid,
            "question": question_text,
            "type": q["type"],
        })

        rlm = dspy.RLM(
            "context, question -> answer",
            tools=wrapped_tools,
            max_iterations=max_iters,
            max_llm_calls=max_calls,
            max_output_chars=8000,
            sub_lm=sub_lm,
        )

        history_before = len(dspy.settings.lm.history) if hasattr(dspy.settings.lm, "history") else 0

        out = None
        try:
            out = rlm(
                context=full_context,
                question=question_text,
            )
            answer = str(getattr(out, "answer", ""))
        except Exception as exc:
            answer = f"ERROR: {exc}"
            print(f"  ERROR: {exc}")

        history_after = len(dspy.settings.lm.history) if hasattr(dspy.settings.lm, "history") else history_before
        lm_usage = _extract_lm_usage(history_before, history_after)

        trajectory = getattr(out, "trajectory", None) if out is not None else None
        iteration_count = len(trajectory) if trajectory else 0

        # Log trajectory entries with error classification
        sandbox_crashes = 0
        tool_binding_errors = 0
        if trajectory:
            for idx, entry in enumerate(trajectory):
                reasoning = (entry.get("reasoning", "") if isinstance(entry, dict)
                             else getattr(entry, "reasoning", "")) or ""
                code = (entry.get("code", "") if isinstance(entry, dict)
                        else getattr(entry, "code", "")) or ""
                output = (entry.get("output", "") if isinstance(entry, dict)
                          else getattr(entry, "output", "")) or ""
                output_str = str(output)[:2000]
                has_error = "[Error]" in output_str
                error_type = None
                if has_error:
                    if "NameError" in output_str or "is not defined" in output_str:
                        error_type = "tool_binding_lost"
                        tool_binding_errors += 1
                    elif "Unhandled async error" in output_str:
                        error_type = "sandbox_crash"
                        sandbox_crashes += 1
                    elif "TypeError" in output_str:
                        error_type = "type_error"
                    else:
                        error_type = "unknown"
                logger.log("iteration", {
                    "run_id": run_id,
                    "question_id": qid,
                    "iteration": idx + 1,
                    "reasoning": str(reasoning)[:2000],
                    "code": str(code)[:4000],
                    "output": output_str,
                    "has_error": has_error,
                    "error_type": error_type,
                })

        question_cost = lm_usage.get("total_cost", 0.0)
        total_cost += question_cost

        # Collect tools used from tool_counts
        tools_used = list(tool_counts.keys())

        result_entry = {
            "question_id": qid,
            "question": question_text,
            "type": q["type"],
            "answer": answer,
            "iterations": iteration_count,
            "tools_used": tools_used,
            "tool_counts": dict(tool_counts),
            "cost": question_cost,
            "lm_usage": lm_usage,
        }
        results.append(result_entry)

        # Save individual answer
        answer_path = run_out / "answers" / f"{qid}.json"
        answer_path.write_text(json.dumps(result_entry, indent=2), encoding="utf-8")

        logger.log("question_complete", {
            "run_id": run_id,
            "question_id": qid,
            "iterations": iteration_count,
            "tools_used": tools_used,
            "cost": question_cost,
            "answer_length": len(answer),
            "sandbox_crashes": sandbox_crashes,
            "tool_binding_errors": tool_binding_errors,
        })

        print(f"  -> {iteration_count} iters, ${question_cost:.3f}, {len(tools_used)} tools: {tools_used}")
        print(f"  -> Answer: {answer[:200]}...")

    summary = {
        "run_id": run_id,
        "graph_dir": str(graph_path),
        "paper": paper,
        "model": model,
        "questions_answered": len(results),
        "total_cost": total_cost,
        "results": results,
    }

    summary_path = run_out / "summary.json"
    summary_path.write_text(json.dumps(summary, indent=2), encoding="utf-8")

    logger.log("run_complete", {
        "run_id": run_id,
        "questions_answered": len(results),
        "total_cost": total_cost,
    })

    print(f"\nDone: {len(results)} questions, ${total_cost:.3f} total")
    print(f"Output: {run_out}")
    return summary
