"""Read-only QA toolset for exploring enriched KAG document graphs.

Provides progressive disclosure (L0-L3) over a pre-built TTL + content store.
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from rdflib import Graph, Namespace, RDF, URIRef
from rdflib.namespace import RDFS


DOCO = Namespace("http://purl.org/spar/doco/")
DEO = Namespace("http://purl.org/spar/deo/")
CITO = Namespace("http://purl.org/spar/cito/")
KAG = Namespace("http://la3d.local/kag#")
EX = Namespace("http://la3d.local/kag/doc/")


class KagQAToolset:
    """Read-only tools for answering questions about an enriched KAG document graph."""

    def __init__(self, ttl_path: str, content_store_path: str) -> None:
        self.graph = Graph()
        self.graph.parse(ttl_path, format="turtle")
        self.graph.bind("doco", DOCO)
        self.graph.bind("deo", DEO)
        self.graph.bind("cito", CITO)
        self.graph.bind("kag", KAG)
        self.graph.bind("ex", EX)
        self.graph.bind("rdfs", RDFS)
        self.content_store: dict[str, dict[str, Any]] = {}
        self._load_content_store(content_store_path)

    def _load_content_store(self, path: str) -> None:
        p = Path(path)
        if not p.exists():
            return
        for line in p.read_text(encoding="utf-8").strip().splitlines():
            entry = json.loads(line)
            self.content_store[entry["ref"]] = entry

    def _resolve_iri(self, iri: str) -> URIRef:
        if ":" in iri and not iri.startswith(("http://", "https://", "urn:")):
            prefix, local = iri.split(":", 1)
            for bound_prefix, ns_uri in self.graph.namespaces():
                if bound_prefix == prefix:
                    return URIRef(str(ns_uri) + local)
        return URIRef(iri)

    def _compact_iri(self, uri: URIRef) -> str:
        s = str(uri)
        for prefix, ns_uri in self.graph.namespaces():
            ns = str(ns_uri)
            if s.startswith(ns) and prefix:
                return f"{prefix}:{s[len(ns):]}"
        return s

    def _node_types(self, node: URIRef) -> list[str]:
        return [self._compact_iri(t) for t in self.graph.objects(node, RDF.type)]

    # ── L0: Overview ─────────────────────────────────────────────────

    def g_stats(self) -> dict[str, Any]:
        """Graph overview: triple count, section/figure/table/paragraph counts."""
        sections = sum(1 for _ in self.graph.subjects(RDF.type, DOCO.Section))
        figures = sum(1 for _ in self.graph.subjects(RDF.type, DOCO.Figure))
        tables = sum(1 for _ in self.graph.subjects(RDF.type, DOCO.Table))
        paragraphs = sum(1 for _ in self.graph.subjects(RDF.type, DOCO.Paragraph))
        formulas = sum(1 for _ in self.graph.subjects(RDF.type, DOCO.Formula))
        captions = sum(1 for _ in self.graph.subjects(RDF.type, DEO.Caption))
        bib_refs = sum(1 for _ in self.graph.subjects(RDF.type, DEO.BibliographicReference))
        return {
            "triples": len(self.graph),
            "sections": sections,
            "paragraphs": paragraphs,
            "figures": figures,
            "tables": tables,
            "formulas": formulas,
            "captions": captions,
            "bibliographic_references": bib_refs,
            "content_store_entries": len(self.content_store),
        }

    def g_sections(self) -> list[dict[str, Any]]:
        """List all sections with titles and DEO rhetorical roles."""
        rows: list[dict[str, Any]] = []
        for section in self.graph.subjects(RDF.type, DOCO.Section):
            header = self.graph.value(section, KAG.containsAsHeader)
            title = ""
            if header:
                title = str(self.graph.value(header, KAG.mainText) or "")
            page_lit = self.graph.value(section, KAG.pageNumber)
            page = int(page_lit) if page_lit is not None else None
            types = self._node_types(section)
            deo_roles = [t for t in types if t.startswith("deo:")]
            child_count = sum(1 for _ in self.graph.objects(section, KAG.contains))
            rows.append({
                "iri": self._compact_iri(section),
                "title": title,
                "page": page,
                "deo_roles": deo_roles,
                "child_count": child_count,
            })
        rows.sort(key=lambda r: (r["page"] or 0, r["title"]))
        return rows

    # ── L1: Navigation ───────────────────────────────────────────────

    def g_section_content(self, section_iri: str) -> dict[str, Any]:
        """List content nodes in a section: type, text preview, page."""
        section = self._resolve_iri(section_iri)
        if (section, RDF.type, DOCO.Section) not in self.graph:
            return {"error": f"Not a doco:Section: {section_iri}"}
        header = self.graph.value(section, KAG.containsAsHeader)
        title = str(self.graph.value(header, KAG.mainText) or "") if header else ""
        children: list[dict[str, Any]] = []
        for child in self.graph.objects(section, KAG.contains):
            types = self._node_types(child)
            main_text = str(self.graph.value(child, KAG.mainText) or "")
            page_lit = self.graph.value(child, KAG.pageNumber)
            children.append({
                "iri": self._compact_iri(child),
                "types": types,
                "text_preview": main_text[:150],
                "page": int(page_lit) if page_lit is not None else None,
            })
        children.sort(key=lambda c: (c["page"] or 0, c["iri"]))
        return {
            "section": self._compact_iri(section),
            "title": title,
            "child_count": len(children),
            "children": children,
        }

    def g_node_detail(self, node_iri: str) -> dict[str, Any]:
        """Full properties of a single node (text truncated to 500 chars)."""
        node = self._resolve_iri(node_iri)
        props: dict[str, Any] = {}
        for p, o in self.graph.predicate_objects(node):
            key = self._compact_iri(p)
            val = self._compact_iri(o) if isinstance(o, URIRef) else str(o)
            if key in ("kag:fullText", "kag:citationText") and len(val) > 500:
                val = val[:500] + "...<truncated>"
            if key in props:
                existing = props[key]
                if isinstance(existing, list):
                    existing.append(val)
                else:
                    props[key] = [existing, val]
            else:
                props[key] = val
        # Also show what contains this node
        contained_by = [self._compact_iri(s) for s in self.graph.subjects(KAG.contains, node)]
        if contained_by:
            props["_contained_by"] = contained_by
        return {
            "iri": self._compact_iri(node),
            "properties": props,
        }

    # ── L2: Search ───────────────────────────────────────────────────

    def g_search(self, query: str, limit: int = 10) -> list[dict[str, Any]]:
        """Full-text search over kag:fullText. Returns matching nodes with previews."""
        safe_limit = max(1, min(int(limit), 50))
        query_lower = query.lower()
        terms = query_lower.split()
        results: list[tuple[int, dict[str, Any]]] = []
        for s, _, full_text_lit in self.graph.triples((None, KAG.fullText, None)):
            text = str(full_text_lit).lower()
            score = sum(1 for t in terms if t in text)
            if score == 0:
                continue
            main_text = str(self.graph.value(s, KAG.mainText) or "")
            full_text = str(full_text_lit)
            types = self._node_types(s)
            page_lit = self.graph.value(s, KAG.pageNumber)
            # Find context snippet around first match
            snippet = self._extract_snippet(full_text, terms)
            results.append((score, {
                "iri": self._compact_iri(s),
                "types": types,
                "page": int(page_lit) if page_lit is not None else None,
                "score": score,
                "snippet": snippet,
                "text_preview": main_text[:120],
            }))
        results.sort(key=lambda x: -x[0])
        return [r[1] for r in results[:safe_limit]]

    @staticmethod
    def _extract_snippet(text: str, terms: list[str], window: int = 100) -> str:
        text_lower = text.lower()
        best_pos = len(text)
        for t in terms:
            pos = text_lower.find(t)
            if pos != -1 and pos < best_pos:
                best_pos = pos
        start = max(0, best_pos - window // 2)
        end = min(len(text), best_pos + window)
        snippet = text[start:end]
        if start > 0:
            snippet = "..." + snippet
        if end < len(text):
            snippet = snippet + "..."
        return snippet

    def g_figure_info(self, figure_iri: str) -> dict[str, Any]:
        """Figure details: caption text, page, image description."""
        node = self._resolve_iri(figure_iri)
        if (node, RDF.type, DOCO.Figure) not in self.graph:
            return {"error": f"Not a doco:Figure: {figure_iri}"}
        page_lit = self.graph.value(node, KAG.pageNumber)
        img_desc = str(self.graph.value(node, KAG.imageDescription) or "")
        img_path = str(self.graph.value(node, KAG.imagePath) or "")
        # Find caption via inverse kag:describes
        caption_text = ""
        for caption_node in self.graph.subjects(KAG.describes, node):
            ct = self.graph.value(caption_node, KAG.fullText) or self.graph.value(caption_node, KAG.mainText)
            if ct:
                caption_text = str(ct)
                break
        # Find which paragraphs refer to this figure
        referring = []
        for para in self.graph.subjects(KAG.refersTo, node):
            main = str(self.graph.value(para, KAG.mainText) or "")
            referring.append({
                "iri": self._compact_iri(para),
                "text_preview": main[:100],
            })
        return {
            "iri": self._compact_iri(node),
            "page": int(page_lit) if page_lit is not None else None,
            "caption": caption_text[:500] if caption_text else "",
            "image_description": img_desc[:500] if img_desc else "",
            "image_path": img_path,
            "referring_paragraphs": referring,
        }

    # ── L3: Relationships ────────────────────────────────────────────

    def g_citations(self, paragraph_iri: str) -> dict[str, Any]:
        """Bibliography entries cited by a paragraph (via cito:cites)."""
        para = self._resolve_iri(paragraph_iri)
        if (para, RDF.type, DOCO.Paragraph) not in self.graph:
            return {"error": f"Not a doco:Paragraph: {paragraph_iri}"}
        refs: list[dict[str, Any]] = []
        for bib_ref in self.graph.objects(para, CITO.cites):
            num_lit = self.graph.value(bib_ref, KAG.citationNumber)
            cite_text = str(self.graph.value(bib_ref, KAG.citationText) or
                           self.graph.value(bib_ref, KAG.fullText) or "")
            refs.append({
                "iri": self._compact_iri(bib_ref),
                "citation_number": int(num_lit) if num_lit is not None else None,
                "text_preview": cite_text[:200],
            })
        refs.sort(key=lambda r: r.get("citation_number") or 999)
        return {
            "paragraph": self._compact_iri(para),
            "citations": refs,
            "count": len(refs),
        }

    def g_citing_paragraphs(self, ref_iri: str) -> dict[str, Any]:
        """Paragraphs that cite a bibliography entry (inverse cito:cites)."""
        ref = self._resolve_iri(ref_iri)
        if (ref, RDF.type, DEO.BibliographicReference) not in self.graph:
            return {"error": f"Not a deo:BibliographicReference: {ref_iri}"}
        num_lit = self.graph.value(ref, KAG.citationNumber)
        cite_text = str(self.graph.value(ref, KAG.citationText) or "")
        paras: list[dict[str, Any]] = []
        for para in self.graph.subjects(CITO.cites, ref):
            main = str(self.graph.value(para, KAG.mainText) or "")
            page_lit = self.graph.value(para, KAG.pageNumber)
            paras.append({
                "iri": self._compact_iri(para),
                "text_preview": main[:150],
                "page": int(page_lit) if page_lit is not None else None,
            })
        return {
            "reference": self._compact_iri(ref),
            "citation_number": int(num_lit) if num_lit is not None else None,
            "text_preview": cite_text[:200],
            "citing_paragraphs": paras,
            "count": len(paras),
        }

    def g_cross_refs(self, paragraph_iri: str) -> dict[str, Any]:
        """Figures/tables referred to by a paragraph (via kag:refersTo)."""
        para = self._resolve_iri(paragraph_iri)
        if (para, RDF.type, DOCO.Paragraph) not in self.graph:
            return {"error": f"Not a doco:Paragraph: {paragraph_iri}"}
        refs: list[dict[str, Any]] = []
        for target in self.graph.objects(para, KAG.refersTo):
            types = self._node_types(target)
            page_lit = self.graph.value(target, KAG.pageNumber)
            # Get caption
            caption = ""
            for cap_node in self.graph.subjects(KAG.describes, target):
                ct = self.graph.value(cap_node, KAG.fullText) or self.graph.value(cap_node, KAG.mainText)
                if ct:
                    caption = str(ct)[:200]
                    break
            refs.append({
                "iri": self._compact_iri(target),
                "types": types,
                "page": int(page_lit) if page_lit is not None else None,
                "caption_preview": caption,
            })
        return {
            "paragraph": self._compact_iri(para),
            "cross_references": refs,
            "count": len(refs),
        }

    # ── Tool surface for DSPy RLM ────────────────────────────────────

    def as_tools(self) -> list:
        """Return all QA tools as callables for DSPy RLM."""
        return [
            self.g_stats,
            self.g_sections,
            self.g_section_content,
            self.g_node_detail,
            self.g_search,
            self.g_figure_info,
            self.g_citations,
            self.g_citing_paragraphs,
            self.g_cross_refs,
        ]
