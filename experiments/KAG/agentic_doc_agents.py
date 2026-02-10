"""Agent implementations for KAG baseline runs."""

from __future__ import annotations

import re
from dataclasses import dataclass
from hashlib import sha256
from typing import Any

from rdflib.namespace import XSD

from experiments.KAG.agentic_doc_tools import DEO, DOCO, EX, KAG, KagDocToolset

_TABLE_CAPTION_RE = re.compile(r"^Table\s+\d+", re.IGNORECASE)


@dataclass
class StructureParseResult:
    document_iri: str
    section_count: int
    node_counts: dict[str, int]
    notes: list[str]


class StructureParserAgent:
    """Baseline deterministic agent for document graph construction."""

    def __init__(self) -> None:
        self._notes: list[str] = []

    def build(self, tools: KagDocToolset, document_id: str = "doc1") -> StructureParseResult:
        doc_iri = str(EX[document_id])
        tools.op_assert_type(doc_iri, str(DOCO.Document))

        section_index = 0
        node_counts: dict[str, int] = {}
        section_children: dict[str, int] = {}
        current_section: str | None = None

        # Collect caption IRIs and their blocks for post-pass proximity linking
        pending_captions: list[tuple[str, Any, str, str]] = []  # (caption_iri, block, section_iri, kind)
        # Collect visual IRIs with their blocks for proximity lookup
        visuals_by_page: dict[int, list[tuple[str, Any, str]]] = {}  # page -> [(iri, block, kind)]

        for block in tools.blocks:
            label = block.label
            kind = block.kind

            # Reclassify figure_title blocks whose text starts with "Table N"
            if kind == "caption" and label == "figure_title" and _TABLE_CAPTION_RE.match(block.text_preview):
                kind = "table_caption"

            if label == "title":
                title_iri = str(EX[f"title_{section_index + 1}"])
                self._create_node(
                    tools=tools,
                    node_iri=title_iri,
                    class_iri=str(DOCO.Title),
                    block=block,
                    short_text=block.text_preview,
                )
                tools.op_add_iri_link(doc_iri, str(KAG.contains), title_iri)
                node_counts["title"] = node_counts.get("title", 0) + 1
                continue

            if label == "sub_title":
                section_index += 1
                section_iri = str(EX[f"section_{section_index:03d}"])
                title_iri = str(EX[f"section_title_{section_index:03d}"])
                self._create_node(
                    tools=tools,
                    node_iri=section_iri,
                    class_iri=str(DOCO.Section),
                    block=block,
                    short_text=block.text_preview,
                    ref_kind="section",
                )
                self._create_node(
                    tools=tools,
                    node_iri=title_iri,
                    class_iri=str(DOCO.SectionTitle),
                    block=block,
                    short_text=block.text_preview,
                    ref_kind="section_title",
                )
                tools.op_add_iri_link(doc_iri, str(KAG.contains), section_iri)
                tools.op_add_iri_link(section_iri, str(KAG.containsAsHeader), title_iri)
                section_children[section_iri] = 0
                node_counts["section"] = node_counts.get("section", 0) + 1
                node_counts["section_title"] = node_counts.get("section_title", 0) + 1
                current_section = section_iri
                continue

            if current_section is None:
                current_section = self._create_default_section(tools, doc_iri, section_index + 1, block.page_number)
                section_index += 1
                section_children[current_section] = section_children.get(current_section, 0)
                node_counts["section"] = node_counts.get("section", 0) + 1
                node_counts["section_title"] = node_counts.get("section_title", 0) + 1

            # Use original kind for class mapping (caption for both caption and table_caption)
            class_kind = "caption" if kind == "table_caption" else kind
            class_iri = self._class_for_kind(class_kind)
            node_iri = str(EX[f"{class_kind}_{block.page_number:03d}_{block.order:04d}"])
            self._create_node(
                tools=tools,
                node_iri=node_iri,
                class_iri=class_iri,
                block=block,
                short_text=block.text_preview,
            )
            tools.op_add_iri_link(current_section, str(KAG.contains), node_iri)
            section_children[current_section] = section_children.get(current_section, 0) + 1
            node_counts[class_kind] = node_counts.get(class_kind, 0) + 1

            if kind in {"figure", "table"}:
                visuals_by_page.setdefault(block.page_number, []).append((node_iri, block, kind))
            if kind in {"caption", "table_caption"}:
                # Defer linking; record for post-pass
                pending_captions.append((node_iri, block, current_section, kind))

        # Post-pass: link captions to nearest visual by bbox proximity
        self._link_captions_by_proximity(
            tools=tools,
            pending_captions=pending_captions,
            visuals_by_page=visuals_by_page,
            section_children=section_children,
            node_counts=node_counts,
        )

        for section_iri, child_count in list(section_children.items()):
            if child_count > 0:
                continue
            placeholder_text = "Autogenerated placeholder paragraph for empty section."
            block_stub = _placeholder_block(section_iri, placeholder_text)
            para_iri = str(EX[f"paragraph_placeholder_{sha256(section_iri.encode('utf-8')).hexdigest()[:8]}"])
            self._create_node(
                tools=tools,
                node_iri=para_iri,
                class_iri=str(DOCO.Paragraph),
                block=block_stub,
                short_text=placeholder_text,
                ref_kind="paragraph",
            )
            tools.op_add_iri_link(section_iri, str(KAG.contains), para_iri)
            section_children[section_iri] = 1
            node_counts["paragraph"] = node_counts.get("paragraph", 0) + 1
            self._notes.append(f"Filled empty section {section_iri} with autogenerated paragraph.")

        return StructureParseResult(
            document_iri=doc_iri,
            section_count=sum(1 for _ in section_children.keys()),
            node_counts=node_counts,
            notes=list(self._notes),
        )

    def _link_captions_by_proximity(
        self,
        tools: KagDocToolset,
        pending_captions: list[tuple[str, Any, str, str]],
        visuals_by_page: dict[int, list[tuple[str, Any, str]]],
        section_children: dict[str, int],
        node_counts: dict[str, int],
    ) -> None:
        """Link each caption to the nearest visual on the same page by bbox vertical midpoint."""
        for caption_iri, cap_block, cap_section, cap_kind in pending_captions:
            page = cap_block.page_number
            page_visuals = visuals_by_page.get(page, [])

            # For table_caption, prefer table targets; for regular caption prefer figures
            prefer_table = cap_kind == "table_caption"

            best_iri: str | None = None
            best_dist: float = float("inf")
            cap_mid = self._bbox_midpoint_y(cap_block.bbox)

            for vis_iri, vis_block, vis_kind in page_visuals:
                vis_mid = self._bbox_midpoint_y(vis_block.bbox)
                dist = abs(cap_mid - vis_mid)
                # Prefer matching type (table_caption→table, caption→figure) via tiebreak
                type_match = (prefer_table and vis_kind == "table") or (not prefer_table and vis_kind == "figure")
                # Use a small bonus for type match to break ties
                effective_dist = dist - (0.5 if type_match else 0.0)
                if effective_dist < best_dist:
                    best_dist = effective_dist
                    best_iri = vis_iri

            if best_iri:
                tools.op_add_iri_link(caption_iri, str(KAG.describes), best_iri)
            else:
                # No visual on this page; create placeholder figure
                placeholder_iri = str(EX[f"figure_placeholder_{cap_block.page_number:03d}_{cap_block.order:04d}"])
                placeholder_block = _placeholder_block(
                    seed=f"{cap_block.block_id}|figure_placeholder",
                    text=f"Autogenerated figure placeholder for {cap_block.block_id}",
                )
                placeholder_block.page_number = cap_block.page_number
                placeholder_block.order = cap_block.order
                placeholder_block.label = "image"
                placeholder_block.kind = "figure"
                self._create_node(
                    tools=tools,
                    node_iri=placeholder_iri,
                    class_iri=str(DOCO.Figure),
                    block=placeholder_block,
                    short_text=placeholder_block.text_preview,
                    ref_kind="figure",
                )
                tools.op_add_iri_link(cap_section, str(KAG.contains), placeholder_iri)
                tools.op_add_iri_link(caption_iri, str(KAG.describes), placeholder_iri)
                visuals_by_page.setdefault(page, []).append((placeholder_iri, placeholder_block, "figure"))
                section_children[cap_section] = section_children.get(cap_section, 0) + 1
                node_counts["figure"] = node_counts.get("figure", 0) + 1
                self._notes.append(
                    f"No visual target found for caption block {cap_block.block_id} on page {page}; added placeholder figure."
                )

    def _bbox_midpoint_y(self, bbox: Any) -> float:
        """Return vertical midpoint from a bbox like [[x1, y1, x2, y2]]."""
        try:
            coords = bbox[0] if bbox and isinstance(bbox[0], list) else bbox
            if coords and len(coords) >= 4:
                return (coords[1] + coords[3]) / 2.0
        except (IndexError, TypeError):
            pass
        return 0.0

    def _create_node(
        self,
        tools: KagDocToolset,
        node_iri: str,
        class_iri: str,
        block: Any,
        short_text: str,
        ref_kind: str = "",
    ) -> None:
        tools.op_assert_type(node_iri, class_iri)
        tools.op_set_single_literal(node_iri, str(KAG.hasContentRef), self._content_ref(block, kind=ref_kind or block.kind))
        tools.op_set_single_literal(node_iri, str(KAG.detectionLabel), str(block.label))
        tools.op_set_single_literal(node_iri, str(KAG.pageNumber), str(int(block.page_number)), datatype_iri=str(XSD.integer))
        tools.op_set_single_literal(node_iri, str(KAG.order), str(int(block.order)), datatype_iri=str(XSD.integer))
        tools.op_set_single_literal(node_iri, str(KAG.hasBBox), str(block.bbox))
        if short_text:
            tools.op_set_single_literal(node_iri, str(KAG.mainText), short_text[:240])

    def _create_default_section(
        self,
        tools: KagDocToolset,
        doc_iri: str,
        section_number: int,
        page_number: int,
    ) -> str:
        section_iri = str(EX[f"section_{section_number:03d}"])
        title_iri = str(EX[f"section_title_{section_number:03d}"])
        pseudo = _placeholder_block(section_iri, "Unsectioned content")
        pseudo.page_number = page_number
        pseudo.label = "auto_section"
        self._create_node(
            tools=tools,
            node_iri=section_iri,
            class_iri=str(DOCO.Section),
            block=pseudo,
            short_text="Unsectioned content",
            ref_kind="section",
        )
        self._create_node(
            tools=tools,
            node_iri=title_iri,
            class_iri=str(DOCO.SectionTitle),
            block=pseudo,
            short_text="Unsectioned content",
            ref_kind="section_title",
        )
        tools.op_add_iri_link(doc_iri, str(KAG.contains), section_iri)
        tools.op_add_iri_link(section_iri, str(KAG.containsAsHeader), title_iri)
        return section_iri

    def _class_for_kind(self, kind: str) -> str:
        if kind == "paragraph":
            return str(DOCO.Paragraph)
        if kind == "equation":
            return str(DOCO.Formula)
        if kind == "figure":
            return str(DOCO.Figure)
        if kind == "table":
            return str(DOCO.Table)
        if kind == "caption":
            return str(DEO.Caption)
        if kind == "title":
            return str(DOCO.Title)
        if kind == "section":
            return str(DOCO.Section)
        return str(DOCO.Paragraph)

    def _content_ref(self, block: Any, kind: str) -> str:
        value = str(getattr(block, "content_ref_id", ""))
        if value and value.startswith(f"{kind}:"):
            return value
        payload = f"{kind}|{block.page_number}|{block.order}|{block.text_preview}"
        digest = sha256(payload.encode("utf-8")).hexdigest()[:16]
        return f"{kind}:{digest}"


class _PlaceholderBlock:
    def __init__(self, seed: str, text: str) -> None:
        digest = sha256(seed.encode("utf-8")).hexdigest()[:16]
        self.block_id = f"placeholder_{digest}"
        self.page_number = 1
        self.order = 1
        self.label = "text"
        self.kind = "paragraph"
        self.bbox = []
        self.content_ref_id = f"paragraph:{digest}"
        self.text_preview = text


def _placeholder_block(seed: str, text: str) -> _PlaceholderBlock:
    return _PlaceholderBlock(seed=seed, text=text)
