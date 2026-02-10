"""Run 0 KAG baseline runner with trajectory logging."""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

if __package__ in {None, ""}:
    sys.path.append(str(Path(__file__).resolve().parents[2]))

from experiments.KAG.agentic_doc_agents import StructureParserAgent
from experiments.KAG.agentic_doc_tools import KagDocToolset
from experiments.KAG.kag_memory import KagMemoryStore


DEFAULT_OUT_DIR = "experiments/KAG/results"


@dataclass
class LeakageMetrics:
    stdout_chars: int = 0
    large_returns: int = 0
    tool_calls: int = 0


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
        with self.path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(event) + "\n")


class LoggedToolProxy:
    def __init__(self, toolset: KagDocToolset, logger: JsonlTrajectoryLogger, leakage: LeakageMetrics, run_id: str) -> None:
        self._toolset = toolset
        self._logger = logger
        self._leakage = leakage
        self._run_id = run_id

    def __getattr__(self, name: str):
        attr = getattr(self._toolset, name)
        if not callable(attr):
            return attr

        def wrapped(*args, **kwargs):
            self._leakage.tool_calls += 1
            self._logger.log(
                "tool_call",
                {
                    "run_id": self._run_id,
                    "tool": name,
                    "args": [self._preview(x) for x in args],
                    "kwargs": {k: self._preview(v) for k, v in kwargs.items()},
                },
            )
            out = attr(*args, **kwargs)
            out_len = len(str(out))
            if out_len > 4000:
                self._leakage.large_returns += 1
            self._logger.log(
                "tool_result",
                {
                    "run_id": self._run_id,
                    "tool": name,
                    "result_size": out_len,
                    "result_preview": self._preview(out, limit=800),
                },
            )
            return out

        return wrapped

    def _preview(self, value: Any, limit: int = 300) -> str:
        text = str(value)
        if len(text) <= limit:
            return text
        return text[:limit] + "...<truncated>"


def run_pipeline(ocr_dir: str, out_dir: str = DEFAULT_OUT_DIR, run_name: str = "run_kag_0") -> dict[str, Any]:
    ocr_path = Path(ocr_dir)
    if not ocr_path.exists():
        raise ValueError(f"OCR directory not found: {ocr_path}")

    run_id = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    run_out = Path(out_dir) / f"{run_name}_{run_id}"
    run_out.mkdir(parents=True, exist_ok=True)

    logger = JsonlTrajectoryLogger(run_out / "trajectory.jsonl")
    leakage = LeakageMetrics()

    logger.log("run_start", {"run_id": run_id, "ocr_dir": str(ocr_path), "out_dir": str(run_out)})

    toolset = KagDocToolset(ocr_dir=str(ocr_path))
    tools = LoggedToolProxy(toolset=toolset, logger=logger, leakage=leakage, run_id=run_id)
    memory = KagMemoryStore()

    logger.log("iteration", {"run_id": run_id, "phase": "l0_sense", "reasoning": "Compute OCR metadata deterministically."})
    l0_raw = tools.ocr_sense()
    l0 = memory.build_l0(l0_raw)
    l1 = memory.build_l1(l0.inferred_type)

    logger.log(
        "iteration",
        {
            "run_id": run_id,
            "phase": "structure_parse",
            "reasoning": "Build DoCO-based document graph from OCR blocks using bounded handles.",
        },
    )
    agent = StructureParserAgent()
    parse_result = agent.build(tools=tools, document_id=ocr_path.name)

    ontology_paths = [
        "ontology/doco.ttl",
        "ontology/deo.ttl",
        "experiments/KAG/kag_ontology/kag_document_ext.ttl",
    ]
    shapes_path = "experiments/KAG/kag_ontology/kag_document_shapes.ttl"
    logger.log(
        "iteration",
        {
            "run_id": run_id,
            "phase": "validate",
            "reasoning": "Validate graph against SHACL with local ontology artifacts only.",
        },
    )
    validation = tools.validate_graph(shapes_path=shapes_path, ontology_paths=ontology_paths)

    graph_path = run_out / "knowledge_graph.ttl"
    tools.serialize_graph(str(graph_path))

    procedure = memory.add_procedure(
        pattern=f"{l0.inferred_type}_structure_parser",
        parse_steps=[
            "Map OCR labels to DoCO/DEO classes",
            "Create sections from sub_title blocks",
            "Attach content blocks to active section",
            "Link captions to nearest visual on same page",
            "Autofill empty sections with placeholder paragraph",
        ],
        success=bool(validation.get("conforms", False)),
    )

    summary = {
        "run_id": run_id,
        "ocr_dir": str(ocr_path),
        "out_dir": str(run_out),
        "l0": {
            "page_count": l0.page_count,
            "detection_types": l0.detection_types,
            "counts_by_label": l0.counts_by_label,
            "inferred_type": l0.inferred_type,
            "has_equations": l0.has_equations,
        },
        "l1": {
            "doc_type": l1.doc_type,
            "expected_structure": l1.expected_structure,
            "required_labels": l1.required_labels,
        },
        "parse_result": {
            "document_iri": parse_result.document_iri,
            "section_count": parse_result.section_count,
            "node_counts": parse_result.node_counts,
            "notes": parse_result.notes,
        },
        "validation": validation,
        "graph_stats": tools.graph_stats(),
        "leakage": {
            "stdout_chars": leakage.stdout_chars,
            "large_returns": leakage.large_returns,
            "tool_calls": leakage.tool_calls,
        },
        "memory": {
            "procedures": memory.list_procedures(),
            "latest": {
                "pattern": procedure.pattern,
                "success_count": procedure.success_count,
            },
        },
        "artifacts": {
            "trajectory_jsonl": str(run_out / "trajectory.jsonl"),
            "summary_json": str(run_out / "summary.json"),
            "knowledge_graph_ttl": str(graph_path),
        },
    }

    summary_path = run_out / "summary.json"
    summary_path.write_text(json.dumps(summary, indent=2), encoding="utf-8")

    logger.log(
        "run_complete",
        {
            "run_id": run_id,
            "conforms": validation.get("conforms", False),
            "validation_results": validation.get("validation_results", 0),
            "triples": summary["graph_stats"]["triples"],
            "large_returns": leakage.large_returns,
        },
    )
    return summary


def main() -> int:
    parser = argparse.ArgumentParser(description="Run KAG baseline structure parser experiment.")
    parser.add_argument(
        "--ocr-dir",
        type=str,
        default="experiments/KAG/test_data/chemrxiv_ocr",
        help="Directory containing page_*.md OCR outputs.",
    )
    parser.add_argument(
        "--out-dir",
        type=str,
        default=DEFAULT_OUT_DIR,
        help="Output base directory.",
    )
    parser.add_argument(
        "--run-name",
        type=str,
        default="run_kag_0",
        help="Run prefix.",
    )
    args = parser.parse_args()
    summary = run_pipeline(ocr_dir=args.ocr_dir, out_dir=args.out_dir, run_name=args.run_name)
    print(json.dumps(summary["artifacts"], indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
