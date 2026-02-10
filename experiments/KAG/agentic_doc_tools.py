"""Tool surface for KAG Run 0: OCR parsing, bounded reads, graph ops, validation."""

from __future__ import annotations

import ast
import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import dspy
from pyshacl import validate
from rdflib import Graph, Literal, Namespace, RDF, URIRef
from rdflib.namespace import RDFS, SH, XSD

from experiments.KAG.symbolic_handles import BlobRef, SymbolicBlobStore, make_content_ref_id


DOCO = Namespace("http://purl.org/spar/doco/")
DEO = Namespace("http://purl.org/spar/deo/")
KAG = Namespace("http://la3d.local/kag#")
EX = Namespace("http://la3d.local/kag/doc/")

TAG_BLOCK_RE = re.compile(
    r"<\|ref\|>(?P<label>.*?)<\|/ref\|><\|det\|>(?P<bbox>\[\[.*?\]\])<\|/det\|>\s*(?P<content>.*?)(?=(?:<\|ref\|>|\Z))",
    re.DOTALL,
)

LABEL_KIND = {
    "title": "title",
    "sub_title": "section",
    "text": "paragraph",
    "equation": "equation",
    "image": "figure",
    "table": "table",
    "figure_title": "caption",
    "table_title": "caption",
}

FIGURE_FILE_RE = re.compile(r"fig_page(\d+)_(\d+)\.png")


class DescribeFigure(dspy.Signature):
    """Describe a scientific figure concisely (1-3 sentences)."""
    image: dspy.Image = dspy.InputField()
    caption: str = dspy.InputField(desc="Caption for context")
    description: str = dspy.OutputField(desc="1-3 sentence description")


class AskAboutFigure(dspy.Signature):
    """Answer a question about a scientific figure."""
    image: dspy.Image = dspy.InputField()
    question: str = dspy.InputField()
    answer: str = dspy.OutputField()


@dataclass(frozen=True)
class OCRBlock:
    block_id: str
    page_number: int
    order: int
    label: str
    kind: str
    bbox: list[Any]
    content_ref_id: str
    blob_ref: BlobRef
    text_preview: str

    def to_row(self) -> dict[str, Any]:
        return {
            "block_id": self.block_id,
            "page_number": self.page_number,
            "order": self.order,
            "label": self.label,
            "kind": self.kind,
            "bbox": self.bbox,
            "content_ref": self.content_ref_id,
            "blob_ref": self.blob_ref.to_dict(),
            "text_preview": self.text_preview,
        }


class KagDocToolset:
    """Tools for loading OCR markdown and building a DoCO-based document graph."""

    def __init__(
        self,
        ocr_dir: str,
        blob_store: SymbolicBlobStore | None = None,
        figures_dir: str | None = None,
        vision_model: str | None = None,
    ) -> None:
        self.ocr_dir = Path(ocr_dir)
        if not self.ocr_dir.exists():
            raise ValueError(f"OCR directory not found: {self.ocr_dir}")
        self.store = blob_store or SymbolicBlobStore()
        self.graph = Graph()
        self.graph.bind("doco", DOCO)
        self.graph.bind("deo", DEO)
        self.graph.bind("kag", KAG)
        self.graph.bind("rdfs", RDFS)
        self.graph.bind("ex", EX)
        self.pages: dict[int, BlobRef] = {}
        self.blocks: list[OCRBlock] = []
        self.figures_dir = self._resolve_figures_dir(figures_dir)
        self.vision_model = vision_model
        self._figure_file_index: dict[int, Path] = {}
        self._vision_cache: dict[str, str] = {}
        self._cached_vision_lm = None
        self._validated = False
        self._load_ocr()
        if self.figures_dir:
            self._build_figure_index()

    def ocr_sense(self) -> dict[str, Any]:
        counts_by_label: dict[str, int] = {}
        for block in self.blocks:
            counts_by_label[block.label] = counts_by_label.get(block.label, 0) + 1
        return {
            "page_count": len(self.pages),
            "block_count": len(self.blocks),
            "counts_by_label": counts_by_label,
            "has_equations": counts_by_label.get("equation", 0) > 0,
        }

    def ocr_list_pages(self) -> list[dict[str, Any]]:
        rows = []
        for page_number in sorted(self.pages.keys()):
            ref = self.pages[page_number]
            rows.append(
                {
                    "page_number": page_number,
                    "page_ref": ref.to_dict(),
                }
            )
        return rows

    def ocr_page_read_window(
        self,
        page_number: int,
        start: int = 0,
        size: int = 180,
        include_text: bool = False,
    ) -> dict[str, Any]:
        page_ref = self.pages.get(int(page_number))
        if page_ref is None:
            return {"error": f"unknown page: {page_number}"}
        out = self.store.read_window(page_ref, start=start, size=size)
        if "error" in out:
            return out
        text = str(out.pop("text", ""))
        out["text_preview"] = text[:80]
        if include_text:
            out["text"] = text
        return out

    def ocr_list_blocks(self, page_number: int | None = None, label: str = "", limit: int = 200) -> dict[str, Any]:
        safe_limit = max(1, min(int(limit), 1000))
        rows = []
        for block in self.blocks:
            if page_number is not None and block.page_number != int(page_number):
                continue
            if label and block.label != label:
                continue
            rows.append(block.to_row())
            if len(rows) >= safe_limit:
                break
        return {
            "count": len(rows),
            "limit": safe_limit,
            "rows": rows,
        }

    def ocr_block_read_window(
        self,
        block_id: str,
        start: int = 0,
        size: int = 180,
        include_text: bool = False,
    ) -> dict[str, Any]:
        block = self._block_by_id(block_id)
        if block is None:
            return {"error": f"unknown block_id: {block_id}"}
        out = self.store.read_window(block.blob_ref, start=start, size=size)
        if "error" in out:
            return out
        text = str(out.pop("text", ""))
        out["text_preview"] = text[:80]
        if include_text:
            out["text"] = text
        return out

    def graph_stats(self) -> dict[str, Any]:
        return {
            "triples": len(self.graph),
        }

    def _resolve_iri(self, iri: str) -> URIRef:
        """Expand CURIE prefixes (e.g. 'ex:fig_1') to full URIs using graph namespace bindings."""
        if ":" in iri and not iri.startswith(("http://", "https://", "urn:")):
            prefix, local = iri.split(":", 1)
            for bound_prefix, ns_uri in self.graph.namespaces():
                if bound_prefix == prefix:
                    return URIRef(str(ns_uri) + local)
        return URIRef(iri)

    # DoCO/DEO class -> hasContentRef kind mapping
    _CONTENT_REF_KINDS: dict[URIRef, str] = {
        DOCO.Section: "section",
        DOCO.SectionTitle: "section_title",
        DOCO.Paragraph: "paragraph",
        DOCO.Formula: "equation",
        DOCO.Figure: "figure",
        DOCO.Table: "table",
        DEO.Caption: "caption",
    }

    def op_assert_type(self, node_iri: str, class_iri: str) -> dict[str, Any]:
        self._validated = False
        node = self._resolve_iri(node_iri)
        cls = self._resolve_iri(class_iri)
        self.graph.add((node, RDF.type, cls))
        # Auto-generate hasContentRef if this type requires one
        content_ref_id = None
        kind = self._CONTENT_REF_KINDS.get(cls)
        if kind and (node, KAG.hasContentRef, None) not in self.graph:
            content_ref_id = make_content_ref_id(kind, str(node))
            self.graph.add((node, KAG.hasContentRef, Literal(content_ref_id)))
        return {
            "operator": "op_assert_type",
            "node": str(node),
            "class": str(cls),
            "added": True,
            "auto_content_ref": content_ref_id,
        }

    def op_add_literal(
        self,
        node_iri: str,
        prop_iri: str,
        value: str,
        datatype_iri: str = "",
    ) -> dict[str, Any]:
        self._validated = False
        node = self._resolve_iri(node_iri)
        prop = self._resolve_iri(prop_iri)
        dt = self._resolve_iri(datatype_iri) if datatype_iri else None
        literal = Literal(value, datatype=dt) if dt else Literal(value)
        self.graph.add((node, prop, literal))
        return {
            "operator": "op_add_literal",
            "node": str(node),
            "property": str(prop),
            "value": str(literal),
            "datatype": str(dt) if dt else "",
            "added": True,
        }

    def op_set_single_literal(
        self,
        node_iri: str,
        prop_iri: str,
        value: str,
        datatype_iri: str = "",
    ) -> dict[str, Any]:
        self._validated = False
        node = self._resolve_iri(node_iri)
        prop = self._resolve_iri(prop_iri)
        removed = 0
        for _, _, old_obj in list(self.graph.triples((node, prop, None))):
            self.graph.remove((node, prop, old_obj))
            removed += 1
        dt = self._resolve_iri(datatype_iri) if datatype_iri else None
        literal = Literal(value, datatype=dt) if dt else Literal(value)
        self.graph.add((node, prop, literal))
        return {
            "operator": "op_set_single_literal",
            "node": str(node),
            "property": str(prop),
            "removed": removed,
            "value": str(literal),
            "datatype": str(dt) if dt else "",
        }

    def op_add_iri_link(self, subject_iri: str, predicate_iri: str, object_iri: str) -> dict[str, Any]:
        self._validated = False
        s = self._resolve_iri(subject_iri)
        p = self._resolve_iri(predicate_iri)
        o = self._resolve_iri(object_iri)
        self.graph.add((s, p, o))
        return {
            "operator": "op_add_iri_link",
            "subject": str(s),
            "predicate": str(p),
            "object": str(o),
            "added": True,
        }

    def op_set_single_iri_link(self, subject_iri: str, predicate_iri: str, object_iri: str) -> dict[str, Any]:
        """Replace all existing IRI values for (subject, predicate) with a single new one."""
        self._validated = False
        s = self._resolve_iri(subject_iri)
        p = self._resolve_iri(predicate_iri)
        o = self._resolve_iri(object_iri)
        removed = 0
        for _, _, old_obj in list(self.graph.triples((s, p, None))):
            self.graph.remove((s, p, old_obj))
            removed += 1
        self.graph.add((s, p, o))
        return {
            "operator": "op_set_single_iri_link",
            "subject": str(s),
            "predicate": str(p),
            "object": str(o),
            "removed": removed,
        }

    def _auto_fill_section_page_numbers(self) -> int:
        """Infer missing Section pageNumber from first child's pageNumber."""
        filled = 0
        for section in self.graph.subjects(RDF.type, DOCO.Section):
            if (section, KAG.pageNumber, None) in self.graph:
                continue
            # Find minimum pageNumber among children linked via kag:contains
            min_page = None
            for child in self.graph.objects(section, KAG.contains):
                child_page = self.graph.value(child, KAG.pageNumber)
                if child_page is not None:
                    p = int(child_page)
                    if min_page is None or p < min_page:
                        min_page = p
            # Fall back to containsAsHeader child
            if min_page is None:
                header = self.graph.value(section, KAG.containsAsHeader)
                if header:
                    header_page = self.graph.value(header, KAG.pageNumber)
                    if header_page is not None:
                        min_page = int(header_page)
            if min_page is not None:
                self.graph.add((section, KAG.pageNumber, Literal(min_page, datatype=XSD.integer)))
                filled += 1
        return filled

    def validate_graph(
        self,
        shapes_path: str = "experiments/KAG/kag_ontology/kag_document_shapes.ttl",
        ontology_paths: list[str] | None = None,
        max_results: int = 25,
    ) -> dict[str, Any]:
        """Validate the graph against SHACL shapes. Call with no arguments to use defaults."""
        if ontology_paths is None:
            ontology_paths = [
                "ontology/doco.ttl",
                "ontology/deo.ttl",
                "experiments/KAG/kag_ontology/kag_document_ext.ttl",
            ]
        # Auto-fill missing Section pageNumbers before validation
        sections_filled = self._auto_fill_section_page_numbers()

        shapes_graph = Graph().parse(str(shapes_path))
        ont_graph = Graph()
        for path in ontology_paths:
            ont_graph.parse(str(path))
        conforms, results_graph, report_text = validate(
            data_graph=self.graph,
            shacl_graph=shapes_graph,
            ont_graph=ont_graph,
            inference="rdfs",
            abort_on_first=False,
            meta_shacl=False,
            advanced=False,
            debug=False,
        )
        violations = self._collect_actionable_violations(results_graph, max_results=max_results)
        self.store.put(str(report_text), kind="shacl_report_text")

        result = {
            "conforms": bool(conforms),
            "total_violations": violations["total"],
            "auto_filled": {"section_page_numbers": sections_filled},
        }
        if not conforms:
            result["violations"] = violations["rows"]
            if violations["total"] > max_results:
                result["truncated_to"] = max_results
            result["action_required"] = (
                "Graph does NOT conform. Fix the violations above, then call "
                "validate_graph() again. Do NOT SUBMIT until conforms=true."
            )
        return result

    def finalize_graph(self, answer: str) -> dict[str, Any]:
        """Validate the graph and prepare for submission.

        Call this before SUBMIT. Returns status='READY' if the graph
        conforms to SHACL shapes, or status='NOT_READY' with violations.
        """
        result = self.validate_graph()
        if result["conforms"]:
            self._validated = True
            return {
                "status": "READY",
                "message": f"Graph conforms. Call SUBMIT(answer='{answer[:80]}...')",
                "conforms": True,
                "total_violations": 0,
            }
        else:
            self._validated = False
            return {
                "status": "NOT_READY",
                "message": "Fix violations, then call finalize_graph again.",
                "conforms": False,
                "total_violations": result["total_violations"],
                "violations": result.get("violations", []),
            }

    def inspect_figure(self, figure_node_iri: str) -> dict[str, Any]:
        """Describe a figure's image using a vision model.

        Looks up the figure's pageNumber, finds the PNG file, sends to
        vision model. Agent should store the returned description as
        kag:imageDescription and image_path as kag:imagePath.
        """
        node = self._resolve_iri(figure_node_iri)
        if (node, RDF.type, DOCO.Figure) not in self.graph:
            return {"error": f"Node {figure_node_iri} is not a doco:Figure in the graph."}

        page_lit = self.graph.value(node, KAG.pageNumber)
        if page_lit is None:
            return {"error": f"No kag:pageNumber found for {figure_node_iri}."}
        page = int(page_lit)

        if not self.figures_dir:
            return {"error": "No figures directory configured."}

        fig_file = self._figure_file_index.get(page)
        if fig_file is None:
            return {"error": f"No figure image file found for page {page}."}

        file_key = str(fig_file)
        if file_key in self._vision_cache:
            return {
                "figure_iri": figure_node_iri,
                "page_number": page,
                "image_path": str(fig_file.relative_to(fig_file.parents[2])) if len(fig_file.parts) > 3 else str(fig_file),
                "description": self._vision_cache[file_key],
                "cached": True,
            }

        caption = self._get_caption_for_figure(node)
        vision_lm = self._get_vision_lm()
        if vision_lm is None:
            return {"error": "No vision model configured."}

        predictor = dspy.Predict(DescribeFigure)
        image = dspy.Image.from_file(str(fig_file))
        with dspy.context(lm=vision_lm):
            result = predictor(image=image, caption=caption or "No caption available")

        description = result.description
        self._vision_cache[file_key] = description
        rel_path = str(fig_file.relative_to(fig_file.parents[2])) if len(fig_file.parts) > 3 else str(fig_file)
        return {
            "figure_iri": figure_node_iri,
            "page_number": page,
            "image_path": rel_path,
            "description": description,
            "cached": False,
        }

    def ask_figure(self, figure_node_iri: str, question: str) -> dict[str, Any]:
        """Ask a specific question about a figure's image."""
        node = self._resolve_iri(figure_node_iri)
        if (node, RDF.type, DOCO.Figure) not in self.graph:
            return {"error": f"Node {figure_node_iri} is not a doco:Figure in the graph."}

        page_lit = self.graph.value(node, KAG.pageNumber)
        if page_lit is None:
            return {"error": f"No kag:pageNumber found for {figure_node_iri}."}
        page = int(page_lit)

        if not self.figures_dir:
            return {"error": "No figures directory configured."}

        fig_file = self._figure_file_index.get(page)
        if fig_file is None:
            return {"error": f"No figure image file found for page {page}."}

        vision_lm = self._get_vision_lm()
        if vision_lm is None:
            return {"error": "No vision model configured."}

        predictor = dspy.Predict(AskAboutFigure)
        image = dspy.Image.from_file(str(fig_file))
        with dspy.context(lm=vision_lm):
            result = predictor(image=image, question=question)

        return {
            "figure_iri": figure_node_iri,
            "page_number": page,
            "question": question,
            "answer": result.answer,
        }

    def blocks_for_repl(self) -> list[dict]:
        """Slim block list for REPL injection. ~80 bytes per block."""
        return [
            {
                "id": b.block_id,
                "page": b.page_number,
                "order": b.order,
                "label": b.label,
                "kind": b.kind,
                "bbox": b.bbox,
                "ref": b.content_ref_id,
                "text": b.text_preview,
            }
            for b in self.blocks
        ]

    def as_tools(self) -> list:
        """Return bounded tool surface as callables for DSPy RLM."""
        return [
            self.ocr_sense,
            self.ocr_list_pages,
            self.ocr_page_read_window,
            self.ocr_list_blocks,
            self.ocr_block_read_window,
            self.graph_stats,
            self.op_assert_type,
            self.op_add_literal,
            self.op_set_single_literal,
            self.op_add_iri_link,
            self.validate_graph,
        ]

    def serialize_graph(self, path: str) -> None:
        self.graph.serialize(destination=path, format="turtle")

    def _load_ocr(self) -> None:
        files = sorted(self.ocr_dir.glob("page_*.md"))
        if not files:
            raise ValueError(f"No page_*.md files found in {self.ocr_dir}")
        for page_number, page_file in enumerate(files, start=1):
            text = page_file.read_text(encoding="utf-8")
            page_ref = self.store.put(text, kind=f"page_{page_number:03d}")
            self.pages[page_number] = page_ref
            page_blocks = self._parse_blocks(text, page_number=page_number)
            self.blocks.extend(page_blocks)

    def _parse_blocks(self, text: str, page_number: int) -> list[OCRBlock]:
        rows: list[OCRBlock] = []
        for idx, match in enumerate(TAG_BLOCK_RE.finditer(text), start=1):
            label = match.group("label").strip()
            kind = LABEL_KIND.get(label, "block")
            bbox_text = match.group("bbox").strip()
            content = (match.group("content") or "").strip()
            if not content:
                content = f"[{label}] page={page_number} bbox={bbox_text}"

            try:
                bbox = ast.literal_eval(bbox_text)
            except Exception:
                bbox = []

            content_ref_id = make_content_ref_id(kind, f"{page_number}|{idx}|{bbox_text}|{content}")
            blob_ref = self.store.put(content, kind=kind)
            block_id = f"b_p{page_number:03d}_{idx:04d}"
            rows.append(
                OCRBlock(
                    block_id=block_id,
                    page_number=page_number,
                    order=idx,
                    label=label,
                    kind=kind,
                    bbox=bbox,
                    content_ref_id=content_ref_id,
                    blob_ref=blob_ref,
                    text_preview=content[:120].replace("\n", " "),
                )
            )
        return rows

    def _resolve_figures_dir(self, explicit: str | None) -> Path | None:
        """Auto-discover figures dir: chemrxiv_ocr -> chemrxiv_figures."""
        if explicit:
            p = Path(explicit)
            return p if p.exists() else None
        ocr_name = self.ocr_dir.name
        if ocr_name.endswith("_ocr"):
            candidate = self.ocr_dir.parent / ocr_name.replace("_ocr", "_figures")
            return candidate if candidate.exists() else None
        return None

    def _build_figure_index(self) -> None:
        """Build page_number -> figure file path index."""
        if not self.figures_dir:
            return
        for f in sorted(self.figures_dir.glob("fig_page*.png")):
            m = FIGURE_FILE_RE.match(f.name)
            if m:
                page = int(m.group(1))
                if page not in self._figure_file_index:
                    self._figure_file_index[page] = f

    def _get_vision_lm(self):
        """Lazily construct and cache the vision LM."""
        if self._cached_vision_lm is None and self.vision_model:
            import os
            api_key = os.environ.get("ANTHROPIC_API_KEY", "")
            self._cached_vision_lm = dspy.LM(self.vision_model, api_key=api_key, temperature=0.0)
        return self._cached_vision_lm

    def _get_caption_for_figure(self, figure_node: URIRef) -> str:
        """Find caption text linked to this figure via kag:describes inverse."""
        for caption_node in self.graph.subjects(KAG.describes, figure_node):
            text = self.graph.value(caption_node, KAG.mainText)
            if text:
                return str(text)[:500]
        return ""

    def _block_by_id(self, block_id: str) -> OCRBlock | None:
        for block in self.blocks:
            if block.block_id == block_id:
                return block
        return None

    def _collect_actionable_violations(
        self, results_graph: Graph, max_results: int = 25,
    ) -> dict[str, Any]:
        """Collect SHACL violations as actionable items the agent can fix."""
        rows: list[dict[str, Any]] = []
        total = 0
        for result in results_graph.subjects(RDF.type, SH.ValidationResult):
            total += 1
            if len(rows) >= max_results:
                continue
            focus_uri = results_graph.value(result, SH.focusNode)
            focus = str(focus_uri) if focus_uri else ""
            message = str(results_graph.value(result, SH.resultMessage) or "")
            # Look up the node's rdf:type in our data graph for context
            node_type = self.graph.value(focus_uri, RDF.type) if focus_uri else None
            type_label = str(node_type).split("/")[-1] if node_type else "unknown"
            row: dict[str, Any] = {
                "node": focus,
                "node_type": type_label,
                "message": message,
            }
            # Add context: mainText preview for captions/paragraphs
            if focus_uri and node_type in (DEO.Caption, DOCO.Paragraph):
                text = self.graph.value(focus_uri, KAG.mainText)
                if text:
                    row["text_preview"] = str(text)[:100]
            rows.append(row)
        return {"total": total, "rows": rows}

