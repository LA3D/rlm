"""DSPy RLM runner for KAG document graph construction.

Context-first approach: the full OCR markdown is passed as `document` context,
and the LLM explores it via the REPL (print, split, etc.) rather than through
OCR exploration tools.  Tools are limited to graph construction ops + validate.
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from datetime import datetime, timezone
from functools import wraps
from pathlib import Path
from typing import Any

import dspy

from experiments.KAG.agentic_doc_tools import KagDocToolset
from experiments.KAG.kag_memory import KagMemoryStore
from experiments.KAG.symbolic_handles import SymbolicBlobStore
from experiments.reasoningbank.prototype.tools.dspy_patches import apply_all_patches


MAIN_MODEL = "anthropic/claude-sonnet-4-5-20250929"
SUB_MODEL = "anthropic/claude-haiku-4-5-20251001"

DEFAULT_ONTOLOGY_PATHS = [
    "ontology/doco.ttl",
    "ontology/deo.ttl",
    "experiments/KAG/kag_ontology/kag_document_ext.ttl",
]
DEFAULT_SHAPES_PATH = "experiments/KAG/kag_ontology/kag_document_shapes.ttl"


@dataclass
class KagRlmResult:
    run_id: str
    answer: str
    shacl_conforms: bool
    iterations: int
    lm_usage: dict[str, Any]
    leakage: dict[str, Any]
    graph_stats: dict[str, Any]
    parse_notes: list[str]


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


def _preview(value: Any, limit: int = 300) -> str:
    text = str(value)
    if len(text) <= limit:
        return text
    return text[:limit] + "...<truncated>"


def _wrap_tools_with_logging(
    raw_tools: dict[str, Any],
    logger: JsonlTrajectoryLogger,
    run_id: str,
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
                logger.log(
                    "tool_result",
                    {
                        "run_id": run_id,
                        "tool": __name,
                        "error": error,
                        "result_size": 0,
                        "result_preview": f"EXCEPTION: {type(exc).__name__}: {exc}",
                    },
                )
                raise  # Let REPL show traceback instead of misleading empty dict
            result_len = len(str(result))
            if result_len > 4000:
                leakage.large_returns += 1
            logger.log(
                "tool_result",
                {
                    "run_id": run_id,
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


def _build_task(enable_figure_indexing: bool = False) -> str:
    """Goal-oriented task description with namespace URIs and SHACL constraints."""
    base = (
        "Build a DoCO-based document graph from the OCR markdown in `document`.\n"
        "\n"
        "## Namespaces\n"
        "- doco: http://purl.org/spar/doco/  (Document, Section, SectionTitle, Paragraph, Table, Figure, Formula, Title)\n"
        "- deo: http://purl.org/spar/deo/  (Caption)\n"
        "- kag: http://la3d.local/kag#  (contains, containsAsHeader, describes, hasContentRef, detectionLabel, pageNumber, order, hasBBox, mainText)\n"
        "- ex: http://la3d.local/kag/doc/  (instance namespace)\n"
        "- xsd: http://www.w3.org/2001/XMLSchema#\n"
        "\n"
        "## Pre-Parsed Blocks\n"
        "The `blocks` variable is a Python list of pre-parsed OCR blocks. Each block is a dict:\n"
        "  {id, page, order, label, kind, bbox, ref, text}\n"
        "- label: raw OCR label (title, sub_title, text, equation, image, table, figure_title, table_title)\n"
        "- kind: DoCO mapping (title, section, paragraph, equation, figure, table, caption)\n"
        "- ref: pre-computed hasContentRef value\n"
        "- text: first 120 chars of content\n"
        "\n"
        "Do NOT parse `document` with regex. Iterate `blocks` directly:\n"
        "  for b in blocks:\n"
        "      op_assert_type(f'ex:{b[\"kind\"]}_{b[\"order\"]}', f'doco:{CLASS_MAP[b[\"kind\"]]}')\n"
        "Use `document` only when you need full text beyond the 120-char preview.\n"
        "\n"
        "## Required Properties (EVERY node must have ALL of these)\n"
        "1. rdf:type — the DoCO/DEO class (set via op_assert_type)\n"
        "2. kag:pageNumber — xsd:integer >= 1, use b['page'] from blocks\n"
        "3. kag:hasContentRef — auto-generated by op_assert_type. No manual hashing needed.\n"
        "4. kag:hasBBox — use str(b['bbox']) from blocks\n"
        "5. kag:mainText — use b['text'] from blocks (or read full text from document)\n"
        "\n"
        "## SHACL Constraints (the graph MUST satisfy ALL of these)\n"
        "- Document must contain >=1 Section (via kag:contains)\n"
        "- Section must have exactly 1 SectionTitle (via kag:containsAsHeader) and >=1 child\n"
        "- All content nodes (Paragraph, Figure, Table, Formula, Caption) must be inside a Section\n"
        "- Caption must describe exactly 1 Figure or Table (via kag:describes).\n"
        "  READ each caption's text BEFORE linking. Use op_set_single_iri_link to fix wrong links.\n"
        "- hasContentRef MUST match pattern ^kind:[a-f0-9]{16}$ — op_assert_type handles this\n"
        "- pageNumber MUST be xsd:integer >= 1 on ALL Section and content nodes\n"
        "- hasBBox required on ALL content nodes including Figures\n"
        "\n"
        "## Completion Protocol\n"
        "When your graph is ready, call: finalize_graph('your summary here')\n"
        "- If status='READY': the graph is valid. Call SUBMIT(answer='your summary')\n"
        "- If status='NOT_READY': fix the violations listed, then call finalize_graph again\n"
        "Do NOT call SUBMIT directly — always go through finalize_graph first.\n"
        "You may also call validate_graph() (no args) mid-construction for progress checks.\n"
        "To fix wrong IRI links: op_set_single_iri_link(subject, predicate, correct_object)\n"
        "  — this REPLACES all existing values for that (subject, predicate) pair.\n"
        "\n"
        "## Section Grouping Rules\n"
        "Sections are delimited by sub_title blocks (kind='section'). Group blocks between consecutive\n"
        "sub_titles into the same Section. IMPORTANT edge cases:\n"
        "- Blocks BEFORE the first sub_title (e.g., author list, abstract text) must go into an\n"
        "  'Abstract' or 'Front Matter' section. Create a doco:Section + doco:SectionTitle for them.\n"
        "  Check `blocks` for a sub_title containing 'Abstract' on an earlier page (cover pages).\n"
        "- Content nodes (Paragraph, Figure, Table, Formula, Caption) must ONLY be contained by\n"
        "  Sections, NOT by Document directly. Document should contain only Title and Sections.\n"
        "- Preprint cover pages (page 1) often duplicate the title and abstract from page 2.\n"
        "  Skip duplicates but use cover-page section titles if they exist.\n"
        "\n"
        "## Goal\n"
        "1. Iterate `blocks` to build the graph: for every block, call op_assert_type, then set pageNumber, hasBBox, mainText\n"
        "2. Group blocks into Sections following the Section Grouping Rules above\n"
        "3. Link Document to Title and Sections only (NOT to Paragraphs/Figures directly)\n"
        "4. Link each Caption to the Figure or Table it describes (read the caption text)\n"
        "5. Call finalize_graph('...summary...') — if violations exist, fix them and call again\n"
        "6. SUBMIT(answer='...summary...') ONLY when finalize_graph returns status='READY'\n"
    )
    if enable_figure_indexing:
        base += (
            "\n"
            "## Figure Vision Indexing\n"
            "After finalize_graph returns READY, enrich Figure nodes:\n"
            "1. For each doco:Figure node, call inspect_figure(figure_iri)\n"
            "   - Use full IRI: 'http://la3d.local/kag/doc/figure_1'\n"
            "2. Store description: op_set_single_literal(figure_iri, 'http://la3d.local/kag#imageDescription', description)\n"
            "3. Store image path: op_set_single_literal(figure_iri, 'http://la3d.local/kag#imagePath', image_path)\n"
            "4. Skip figures where inspect_figure returns an error\n"
            "5. Call finalize_graph again after adding descriptions\n"
            "6. SUBMIT only when finalize_graph returns status='READY'\n"
        )
    return base


def ensure_lm(model: str = MAIN_MODEL) -> None:
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        raise ValueError("Set ANTHROPIC_API_KEY for live RLM runs.")
    dspy.configure(lm=dspy.LM(model, api_key=api_key, temperature=0.0))


def run_rlm_kag(
    ocr_dir: str,
    out_dir: str = "experiments/KAG/results",
    run_name: str = "run_kag_1",
    model: str = MAIN_MODEL,
    sub_model: str = SUB_MODEL,
    max_iters: int = 20,
    max_calls: int = 50,
    figures_dir: str | None = None,
    vision_model: str | None = None,
    enable_figure_indexing: bool = False,
) -> dict[str, Any]:
    """Run DSPy RLM agent to build a KAG document graph from OCR output.

    Context-first: the full document.md is passed as `document` so the LLM can
    explore the markdown directly via REPL code.  Tools are limited to graph
    construction operations and SHACL validation.
    """
    ensure_lm(model=model)
    apply_all_patches()

    ocr_path = Path(ocr_dir)
    if not ocr_path.exists():
        raise ValueError(f"OCR directory not found: {ocr_path}")

    # Load the full OCR markdown as context
    doc_path = ocr_path / "document.md"
    if not doc_path.exists():
        raise ValueError(f"document.md not found in {ocr_path}")
    document = doc_path.read_text(encoding="utf-8")

    ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    run_id = f"{run_name}_{ts}"
    run_out = Path(out_dir) / run_id
    run_out.mkdir(parents=True, exist_ok=True)

    logger = JsonlTrajectoryLogger(run_out / "trajectory.jsonl")
    leakage = LeakageMetrics()
    operator_counts: dict[str, int] = {}

    # Build toolset — graph ops only (no OCR exploration tools)
    blob_store = SymbolicBlobStore()
    effective_vision_model = (vision_model or sub_model) if enable_figure_indexing else None
    toolset = KagDocToolset(
        ocr_dir=str(ocr_path),
        blob_store=blob_store,
        figures_dir=figures_dir,
        vision_model=effective_vision_model,
    )

    logger.log("run_start", {
        "run_id": run_id,
        "ocr_dir": str(ocr_path),
        "model": model,
        "sub_model": sub_model,
        "max_iters": max_iters,
        "max_calls": max_calls,
        "document_size": len(document),
        "enable_figure_indexing": enable_figure_indexing,
        "figures_dir": str(toolset.figures_dir) if toolset.figures_dir else None,
    })
    memory = KagMemoryStore()

    # Increase iteration budget when figure indexing is enabled
    if enable_figure_indexing and max_iters < 30:
        max_iters = 30

    # Build pre-parsed blocks for REPL injection
    blocks = toolset.blocks_for_repl()

    # Select only graph construction + validation tools
    graph_tools = {
        "op_assert_type": toolset.op_assert_type,
        "op_set_single_literal": toolset.op_set_single_literal,
        "op_add_iri_link": toolset.op_add_iri_link,
        "op_set_single_iri_link": toolset.op_set_single_iri_link,
        "validate_graph": toolset.validate_graph,
        "finalize_graph": toolset.finalize_graph,
        "query_contains": toolset.query_contains,
        "graph_stats": toolset.graph_stats,
    }

    # Add vision tool when figure indexing is enabled and figures exist
    if enable_figure_indexing and toolset.figures_dir:
        graph_tools["inspect_figure"] = toolset.inspect_figure

    # Wrap tools with trajectory logging
    wrapped_dict = _wrap_tools_with_logging(
        raw_tools=graph_tools,
        logger=logger,
        run_id=run_id,
        leakage=leakage,
        operator_counts=operator_counts,
    )
    wrapped_tools = list(wrapped_dict.values())

    # Sub-LM for code execution
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        raise ValueError("Set ANTHROPIC_API_KEY for live RLM runs.")
    sub_lm = dspy.LM(sub_model, api_key=api_key, temperature=0.0)

    task = _build_task(enable_figure_indexing=enable_figure_indexing and toolset.figures_dir is not None)

    # DSPy RLM — context=document+blocks, task=goal
    rlm = dspy.RLM(
        "document, task, blocks -> answer",
        tools=wrapped_tools,
        max_iterations=max_iters,
        max_llm_calls=max_calls,
        max_output_chars=10000,
        sub_lm=sub_lm,
    )

    logger.log("iteration", {
        "run_id": run_id,
        "phase": "rlm_start",
        "document_size": len(document),
        "task_length": len(task),
        "blocks_count": len(blocks),
    })

    history_before = len(dspy.settings.lm.history) if hasattr(dspy.settings.lm, "history") else 0
    out = rlm(document=document, task=task, blocks=blocks)
    history_after = len(dspy.settings.lm.history) if hasattr(dspy.settings.lm, "history") else history_before

    lm_usage = _extract_lm_usage(history_before, history_after)
    leakage.subcalls = lm_usage.get("total_calls", 0)
    leakage.vars_n = len(getattr(blob_store, "_blobs", {}))

    # Extract iteration count from RLM trajectory
    trajectory = getattr(out, "trajectory", None)
    iteration_count = len(trajectory) if trajectory else 0

    # Log trajectory entries (dicts with reasoning/code/output keys)
    if trajectory:
        for idx, entry in enumerate(trajectory):
            reasoning = (entry.get("reasoning", "") if isinstance(entry, dict)
                         else getattr(entry, "reasoning", "")) or ""
            code = (entry.get("code", "") if isinstance(entry, dict)
                    else getattr(entry, "code", "")) or ""
            output = (entry.get("output", "") if isinstance(entry, dict)
                      else getattr(entry, "output", "")) or ""
            logger.log("iteration", {
                "run_id": run_id,
                "iteration": idx + 1,
                "reasoning": str(reasoning)[:2000],
                "code": str(code)[:4000],
                "output": str(output)[:2000],
            })

    # Validate
    ontology_paths = list(DEFAULT_ONTOLOGY_PATHS)
    shapes_path = DEFAULT_SHAPES_PATH
    validation = toolset.validate_graph(shapes_path=shapes_path, ontology_paths=ontology_paths)

    # Serialize graph
    graph_path = run_out / "knowledge_graph.ttl"
    toolset.serialize_graph(str(graph_path))

    # Memory
    procedure = memory.add_procedure(
        pattern=f"rlm_context_first_structure",
        parse_steps=["RLM agent constructed graph from document markdown context"],
        success=bool(validation.get("conforms", False)),
    )

    summary = {
        "run_id": run_id,
        "ocr_dir": str(ocr_path),
        "out_dir": str(run_out),
        "answer": str(getattr(out, "answer", "")),
        "validation": validation,
        "graph_stats": toolset.graph_stats(),
        "leakage": {
            "stdout_chars": leakage.stdout_chars,
            "large_returns": leakage.large_returns,
            "subcalls": leakage.subcalls,
            "vars_n": leakage.vars_n,
        },
        "lm_usage": lm_usage,
        "operator_counts": operator_counts,
        "iterations": iteration_count,
        "memory": {
            "procedures": memory.list_procedures(),
            "latest": {
                "pattern": procedure.pattern,
                "success_count": procedure.success_count,
            },
        },
        "vision_stats": {
            "enabled": enable_figure_indexing,
            "figures_dir": str(toolset.figures_dir) if toolset.figures_dir else None,
            "figure_files_found": len(toolset._figure_file_index),
            "vision_calls_made": len(toolset._vision_cache),
            "vision_model": effective_vision_model,
        },
        "artifacts": {
            "trajectory_jsonl": str(run_out / "trajectory.jsonl"),
            "summary_json": str(run_out / "summary.json"),
            "knowledge_graph_ttl": str(graph_path),
        },
    }

    summary_path = run_out / "summary.json"
    summary_path.write_text(json.dumps(summary, indent=2), encoding="utf-8")

    logger.log("run_complete", {
        "run_id": run_id,
        "conforms": validation.get("conforms", False),
        "total_violations": validation.get("total_violations", 0),
        "triples": summary["graph_stats"]["triples"],
        "large_returns": leakage.large_returns,
        "iterations": iteration_count,
        "total_cost": lm_usage.get("total_cost", 0.0),
    })

    return summary
