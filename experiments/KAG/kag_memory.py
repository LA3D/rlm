"""Memory layers for KAG experiments (L0-L2 for baseline)."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass
class L0Sense:
    page_count: int
    detection_types: list[str]
    counts_by_label: dict[str, int]
    inferred_type: str
    has_equations: bool


@dataclass
class L1Schema:
    doc_type: str
    expected_structure: dict[str, list[str]]
    required_labels: list[str]


@dataclass
class L2Procedure:
    pattern: str
    parse_steps: list[str]
    success_count: int = 0
    updated_at: str = field(default_factory=_now_iso)


class KagMemoryStore:
    """Lightweight in-memory memory store for baseline KAG runs."""

    def __init__(self) -> None:
        self._procedures: list[L2Procedure] = []

    def build_l0(self, sense: dict[str, Any]) -> L0Sense:
        detection_types = sorted(sense.get("counts_by_label", {}).keys())
        has_equations = sense.get("counts_by_label", {}).get("equation", 0) > 0
        inferred = self._infer_document_type(sense.get("counts_by_label", {}))
        return L0Sense(
            page_count=int(sense.get("page_count", 0)),
            detection_types=detection_types,
            counts_by_label=dict(sense.get("counts_by_label", {})),
            inferred_type=inferred,
            has_equations=has_equations,
        )

    def build_l1(self, doc_type: str) -> L1Schema:
        # Baseline schema; later runs can specialize this per domain.
        expected = {
            "Document": ["Section", "Title"],
            "Section": ["SectionTitle", "Paragraph", "Figure", "Table", "Formula", "Caption"],
        }
        required = ["sub_title", "text"]
        return L1Schema(doc_type=doc_type, expected_structure=expected, required_labels=required)

    def add_procedure(self, pattern: str, parse_steps: list[str], success: bool) -> L2Procedure:
        for item in self._procedures:
            if item.pattern == pattern:
                item.parse_steps = parse_steps
                if success:
                    item.success_count += 1
                item.updated_at = _now_iso()
                return item
        proc = L2Procedure(pattern=pattern, parse_steps=parse_steps, success_count=1 if success else 0)
        self._procedures.append(proc)
        return proc

    def list_procedures(self) -> list[dict[str, Any]]:
        return [
            {
                "pattern": p.pattern,
                "parse_steps": list(p.parse_steps),
                "success_count": p.success_count,
                "updated_at": p.updated_at,
            }
            for p in self._procedures
        ]

    def _infer_document_type(self, counts: dict[str, int]) -> str:
        if counts.get("equation", 0) > 0 and counts.get("figure_title", 0) > 0:
            return "research_paper"
        if counts.get("table", 0) > 0 and counts.get("sub_title", 0) > 2:
            return "technical_report"
        return "document"

