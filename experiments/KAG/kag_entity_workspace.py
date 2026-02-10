"""Multi-graph workspace for KAG entity extraction.

Manages three graph layers:
  G_doc   (read-only)  — DoCO + DEO document structure (loaded from Sprint 4 output)
  G_entity (mutable)   — SIO + QUDT entities and measurements
  G_claim  (mutable)   — SIO + PROV + CiTO claims and evidence

Each layer has a GraphProfile that enforces namespace purity via prefix checks
on mutations. SHACL validation runs per-layer plus cross-graph grounding checks.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from pyshacl import validate
from rdflib import Graph, Literal, Namespace, RDF, URIRef
from rdflib.namespace import RDFS, XSD


# ── Namespace declarations ───────────────────────────────────────────

DOCO = Namespace("http://purl.org/spar/doco/")
DEO = Namespace("http://purl.org/spar/deo/")
CITO = Namespace("http://purl.org/spar/cito/")
KAG = Namespace("http://la3d.local/kag#")
EX = Namespace("http://la3d.local/kag/doc/")
SIO = Namespace("http://semanticscience.org/resource/")
QUDT = Namespace("http://qudt.org/schema/qudt/")
QUANTITYKIND = Namespace("http://qudt.org/vocab/quantitykind/")
UNIT = Namespace("http://qudt.org/vocab/unit/")
PROV = Namespace("http://www.w3.org/ns/prov#")

# Prefix -> URI for CURIE resolution
KNOWN_PREFIXES: dict[str, str] = {
    "doco": str(DOCO),
    "deo": str(DEO),
    "cito": str(CITO),
    "kag": str(KAG),
    "ex": str(EX),
    "sio": str(SIO),
    "qudt": str(QUDT),
    "quantitykind": str(QUANTITYKIND),
    "unit": str(UNIT),
    "prov": str(PROV),
    "rdfs": str(RDFS),
    "xsd": str(XSD),
    "rdf": str(RDF),
}


@dataclass(frozen=True)
class GraphProfile:
    """Per-graph contract: allowed namespaces and SHACL shapes."""

    name: str
    allowed_namespace_prefixes: tuple[str, ...]
    shapes_paths: tuple[str, ...]
    ontology_paths: tuple[str, ...]
    read_only: bool = False

    def is_namespace_allowed(self, uri: str) -> bool:
        """Check if a URI belongs to an allowed namespace."""
        for prefix in self.allowed_namespace_prefixes:
            ns = KNOWN_PREFIXES.get(prefix, "")
            if ns and uri.startswith(ns):
                return True
        return False


# ── Default profiles ─────────────────────────────────────────────────

DOC_PROFILE = GraphProfile(
    name="doc",
    allowed_namespace_prefixes=("doco", "deo", "kag", "ex", "rdfs", "cito"),
    shapes_paths=("experiments/KAG/kag_ontology/kag_document_shapes.ttl",),
    ontology_paths=(
        "ontology/doco.ttl",
        "ontology/deo.ttl",
        "experiments/KAG/kag_ontology/kag_document_ext.ttl",
    ),
    read_only=True,
)

ENTITY_PROFILE = GraphProfile(
    name="entity",
    allowed_namespace_prefixes=("sio", "qudt", "quantitykind", "unit", "ex", "prov", "rdfs", "rdf", "xsd"),
    shapes_paths=("experiments/KAG/kag_ontology/kag_entity_shapes.ttl",),
    ontology_paths=(
        "experiments/KAG/kag_ontology/sio_subset.ttl",
        "experiments/KAG/kag_ontology/qudt_subset.ttl",
    ),
)

CLAIM_PROFILE = GraphProfile(
    name="claim",
    allowed_namespace_prefixes=("sio", "prov", "cito", "ex", "rdfs", "rdf", "xsd"),
    shapes_paths=("experiments/KAG/kag_ontology/kag_claim_shapes.ttl",),
    ontology_paths=(
        "experiments/KAG/kag_ontology/sio_subset.ttl",
    ),
)


class KagEntityWorkspace:
    """Multi-graph workspace for entity-centric knowledge graph construction.

    Loads an existing G_doc graph (read-only) and provides mutable G_entity
    and G_claim graphs for entity extraction, with SHACL validation per layer.
    """

    PROFILES: dict[str, GraphProfile] = {
        "doc": DOC_PROFILE,
        "entity": ENTITY_PROFILE,
        "claim": CLAIM_PROFILE,
    }

    def __init__(
        self,
        doc_ttl_path: str,
        content_store_path: str | None = None,
    ) -> None:
        # G_doc: read-only base loaded from Sprint 4 output
        self.g_doc = Graph()
        self.g_doc.parse(doc_ttl_path, format="turtle")
        self._bind_all(self.g_doc)

        # G_entity: mutable entity extraction graph
        self.g_entity = Graph()
        self._bind_all(self.g_entity)

        # G_claim: mutable claim extraction graph
        self.g_claim = Graph()
        self._bind_all(self.g_claim)

        # Graph registry
        self._graphs: dict[str, Graph] = {
            "doc": self.g_doc,
            "entity": self.g_entity,
            "claim": self.g_claim,
        }

        # Validation cache per graph
        self._validated: dict[str, bool] = {
            "doc": True,  # loaded, assumed valid
            "entity": False,
            "claim": False,
        }

        # Content store for full text lookups
        self.content_store: dict[str, dict[str, Any]] = {}
        if content_store_path:
            self._load_content_store(content_store_path)

    def _bind_all(self, g: Graph) -> None:
        """Bind all known namespace prefixes to a graph."""
        g.bind("doco", DOCO)
        g.bind("deo", DEO)
        g.bind("cito", CITO)
        g.bind("kag", KAG)
        g.bind("ex", EX)
        g.bind("sio", SIO)
        g.bind("qudt", QUDT)
        g.bind("quantitykind", QUANTITYKIND)
        g.bind("unit", UNIT)
        g.bind("prov", PROV)
        g.bind("rdfs", RDFS)

    def _load_content_store(self, path: str) -> None:
        p = Path(path)
        if not p.exists():
            return
        for line in p.read_text(encoding="utf-8").strip().splitlines():
            entry = json.loads(line)
            self.content_store[entry["ref"]] = entry

    # ── Graph access ─────────────────────────────────────────────────

    def get_graph(self, name: str) -> Graph:
        """Get a graph by name. Raises ValueError for unknown names."""
        g = self._graphs.get(name)
        if g is None:
            raise ValueError(f"Unknown graph: {name!r}. Valid: {list(self._graphs.keys())}")
        return g

    def get_profile(self, name: str) -> GraphProfile:
        """Get the GraphProfile for a named graph."""
        p = self.PROFILES.get(name)
        if p is None:
            raise ValueError(f"Unknown graph profile: {name!r}")
        return p

    # ── IRI resolution ───────────────────────────────────────────────

    def resolve_iri(self, iri: str) -> URIRef:
        """Expand CURIE prefixes (e.g. 'sio:ChemicalEntity') to full URIs.

        Bare names without a prefix or scheme are auto-prefixed with ex:
        to prevent accidental creation of relative URI nodes.
        """
        if ":" in iri and not iri.startswith(("http://", "https://", "urn:")):
            prefix, local = iri.split(":", 1)
            ns = KNOWN_PREFIXES.get(prefix)
            if ns:
                return URIRef(ns + local)
        # Bare name (no prefix, no scheme) -> auto-prefix with ex:
        if ":" not in iri and "/" not in iri:
            return EX[iri]
        return URIRef(iri)

    def compact_iri(self, uri: URIRef) -> str:
        """Compact a full URI to CURIE form."""
        s = str(uri)
        for prefix, ns in KNOWN_PREFIXES.items():
            if s.startswith(ns) and prefix:
                return f"{prefix}:{s[len(ns):]}"
        return s

    # ── Guard: namespace purity ──────────────────────────────────────

    def _check_mutation_allowed(self, graph_name: str, predicate: URIRef) -> str | None:
        """Return error message if mutation violates profile, else None."""
        profile = self.PROFILES.get(graph_name)
        if profile is None:
            return f"Unknown graph: {graph_name!r}"
        if profile.read_only:
            return f"Graph '{graph_name}' is read-only. Cannot mutate."
        if not profile.is_namespace_allowed(str(predicate)):
            return (
                f"Predicate {self.compact_iri(predicate)} not in allowed namespaces "
                f"for graph '{graph_name}'. Allowed: {profile.allowed_namespace_prefixes}"
            )
        return None

    # ── Mutation operators ───────────────────────────────────────────

    def op_create_entity(
        self,
        entity_id: str,
        class_iri: str,
        graph: str = "entity",
    ) -> dict[str, Any]:
        """Create an entity node with rdf:type in the target graph."""
        g = self.get_graph(graph)
        profile = self.get_profile(graph)
        if profile.read_only:
            return {"TOOL_ERROR": f"Graph '{graph}' is read-only.", "error": "read_only"}

        node = self.resolve_iri(entity_id) if ":" in entity_id else EX[entity_id]
        cls = self.resolve_iri(class_iri)
        g.add((node, RDF.type, cls))
        self._validated[graph] = False

        return {
            "operator": "op_create_entity",
            "node": str(node),
            "class": str(cls),
            "graph": graph,
        }

    def op_assert_type(
        self,
        node_iri: str,
        class_iri: str,
        graph: str = "entity",
    ) -> dict[str, Any]:
        """Add rdf:type to a node in the target graph."""
        g = self.get_graph(graph)
        profile = self.get_profile(graph)
        if profile.read_only:
            return {"TOOL_ERROR": f"Graph '{graph}' is read-only.", "error": "read_only"}

        node = self.resolve_iri(node_iri)
        cls = self.resolve_iri(class_iri)
        already = (node, RDF.type, cls) in g
        g.add((node, RDF.type, cls))
        self._validated[graph] = False

        return {
            "operator": "op_assert_type",
            "node": str(node),
            "class": str(cls),
            "graph": graph,
            "already_present": already,
        }

    def op_set_literal(
        self,
        node_iri: str,
        prop_iri: str,
        value: str,
        datatype_iri: str = "",
        graph: str = "entity",
    ) -> dict[str, Any]:
        """Set/replace a literal property on a node."""
        g = self.get_graph(graph)
        profile = self.get_profile(graph)
        if profile.read_only:
            return {"TOOL_ERROR": f"Graph '{graph}' is read-only.", "error": "read_only"}

        node = self.resolve_iri(node_iri)
        prop = self.resolve_iri(prop_iri)
        error = self._check_mutation_allowed(graph, prop)
        if error:
            return {"TOOL_ERROR": error, "error": error}

        # Remove existing values for this property
        removed = 0
        for _, _, old in list(g.triples((node, prop, None))):
            g.remove((node, prop, old))
            removed += 1

        dt = self.resolve_iri(datatype_iri) if datatype_iri else None
        lit = Literal(value, datatype=dt) if dt else Literal(value)
        g.add((node, prop, lit))
        self._validated[graph] = False

        return {
            "operator": "op_set_literal",
            "node": self.compact_iri(node),
            "property": self.compact_iri(prop),
            "value": str(lit),
            "removed": removed,
            "graph": graph,
        }

    def op_add_link(
        self,
        subject_iri: str,
        predicate_iri: str,
        object_iri: str,
        graph: str = "entity",
    ) -> dict[str, Any]:
        """Add an IRI-valued triple to the target graph."""
        g = self.get_graph(graph)
        profile = self.get_profile(graph)
        if profile.read_only:
            return {"TOOL_ERROR": f"Graph '{graph}' is read-only.", "error": "read_only"}

        s = self.resolve_iri(subject_iri)
        p = self.resolve_iri(predicate_iri)
        o = self.resolve_iri(object_iri)

        error = self._check_mutation_allowed(graph, p)
        if error:
            return {"TOOL_ERROR": error, "error": error}

        already = (s, p, o) in g
        g.add((s, p, o))
        self._validated[graph] = False

        return {
            "operator": "op_add_link",
            "subject": self.compact_iri(s),
            "predicate": self.compact_iri(p),
            "object": self.compact_iri(o),
            "graph": graph,
            "already_present": already,
        }

    def op_set_link(
        self,
        subject_iri: str,
        predicate_iri: str,
        object_iri: str,
        graph: str = "entity",
    ) -> dict[str, Any]:
        """Replace all values for (subject, predicate) with a single new IRI."""
        g = self.get_graph(graph)
        profile = self.get_profile(graph)
        if profile.read_only:
            return {"TOOL_ERROR": f"Graph '{graph}' is read-only.", "error": "read_only"}

        s = self.resolve_iri(subject_iri)
        p = self.resolve_iri(predicate_iri)
        o = self.resolve_iri(object_iri)

        error = self._check_mutation_allowed(graph, p)
        if error:
            return {"TOOL_ERROR": error, "error": error}

        removed = 0
        for _, _, old in list(g.triples((s, p, None))):
            g.remove((s, p, old))
            removed += 1
        g.add((s, p, o))
        self._validated[graph] = False

        return {
            "operator": "op_set_link",
            "subject": self.compact_iri(s),
            "predicate": self.compact_iri(p),
            "object": self.compact_iri(o),
            "removed": removed,
            "graph": graph,
        }

    # ── Validation ───────────────────────────────────────────────────

    def validate_graph(
        self,
        graph_name: str = "all",
        max_results: int = 25,
    ) -> dict[str, Any]:
        """Validate one graph layer or all layers + cross-graph checks.

        Returns dict with per-graph conformance and violation summaries.
        Call with no arguments to validate all graphs.
        """
        if graph_name != "all" and graph_name not in self._graphs:
            return {"TOOL_ERROR": f"Unknown graph: {graph_name!r}", "error": "unknown_graph"}

        targets = [graph_name] if graph_name != "all" else ["entity", "claim"]
        results: dict[str, Any] = {}

        for name in targets:
            g = self._graphs[name]
            profile = self.PROFILES[name]

            # Skip empty graphs
            if len(g) == 0:
                results[name] = {"conforms": True, "total_violations": 0, "empty": True}
                self._validated[name] = True
                continue

            # Load shapes and ontology
            shapes_graph = Graph()
            for sp in profile.shapes_paths:
                shapes_graph.parse(sp)
            ont_graph = Graph()
            for op in profile.ontology_paths:
                ont_graph.parse(op)

            conforms, results_graph, report_text = validate(
                data_graph=g,
                shacl_graph=shapes_graph,
                ont_graph=ont_graph,
                inference="rdfs",
                abort_on_first=False,
                meta_shacl=False,
                advanced=False,
                debug=False,
            )
            violations = self._collect_violations(results_graph, max_results)
            self._validated[name] = bool(conforms)

            entry: dict[str, Any] = {
                "conforms": bool(conforms),
                "total_violations": violations["total"],
            }
            if not conforms:
                entry["violations"] = violations["rows"]
                if violations["total"] > max_results:
                    entry["truncated_to"] = max_results
            results[name] = entry

        # Cross-graph grounding check
        if graph_name == "all":
            results["cross_graph"] = self._validate_cross_graph()

        all_conform = all(
            r.get("conforms", True) for r in results.values()
            if isinstance(r, dict)
        )
        return {
            "conforms": all_conform,
            "layers": results,
        }

    def _validate_cross_graph(self) -> dict[str, Any]:
        """Check cross-graph grounding invariants.

        Every entity and claim must have prov:wasDerivedFrom pointing to
        a node that exists in G_doc.
        """
        doc_nodes = set(self.g_doc.subjects()) | set(self.g_doc.objects())
        ungrounded: list[dict[str, str]] = []

        for graph_name in ("entity", "claim"):
            g = self._graphs[graph_name]
            for s in g.subjects(PROV.wasDerivedFrom, None):
                targets = list(g.objects(s, PROV.wasDerivedFrom))
                for t in targets:
                    if isinstance(t, URIRef) and t not in doc_nodes:
                        ungrounded.append({
                            "graph": graph_name,
                            "node": self.compact_iri(s),
                            "wasDerivedFrom": self.compact_iri(t),
                            "message": f"Target {self.compact_iri(t)} not found in G_doc.",
                        })

        return {
            "conforms": len(ungrounded) == 0,
            "ungrounded": ungrounded[:25],
            "total_ungrounded": len(ungrounded),
        }

    def finalize_graph(self, answer: str) -> dict[str, Any]:
        """Gate SUBMIT on SHACL conformance across all layers.

        Call before SUBMIT. Returns status='READY' if all graphs conform,
        or status='NOT_READY' with violations per layer.
        """
        result = self.validate_graph("all")
        if result["conforms"]:
            return {
                "status": "READY",
                "message": f"All graphs conform. Call SUBMIT(answer='{answer[:80]}...')",
                "conforms": True,
                "layers": result["layers"],
            }
        else:
            return {
                "status": "NOT_READY",
                "message": "Fix violations, then call finalize_graph again.",
                "conforms": False,
                "layers": result["layers"],
            }

    # ── Stats & Inspection ───────────────────────────────────────────

    def stats(self) -> dict[str, Any]:
        """Triple counts and node type summaries per graph."""
        result: dict[str, Any] = {}
        for name, g in self._graphs.items():
            types: dict[str, int] = {}
            for _, _, cls in g.triples((None, RDF.type, None)):
                label = self.compact_iri(cls)
                types[label] = types.get(label, 0) + 1
            result[name] = {
                "triples": len(g),
                "types": types,
            }
        return result

    def doc_sections(self) -> list[dict[str, Any]]:
        """List G_doc sections with titles for agent context."""
        rows: list[dict[str, Any]] = []
        for section in self.g_doc.subjects(RDF.type, DOCO.Section):
            header = self.g_doc.value(section, KAG.containsAsHeader)
            title = str(self.g_doc.value(header, KAG.mainText) or "") if header else ""
            page_lit = self.g_doc.value(section, KAG.pageNumber)
            child_count = sum(1 for _ in self.g_doc.objects(section, KAG.contains))
            rows.append({
                "iri": self.compact_iri(section),
                "title": title,
                "page": int(page_lit) if page_lit is not None else None,
                "children": child_count,
            })
        rows.sort(key=lambda r: (r["page"] or 0, r["title"]))
        return rows

    def doc_node_text(self, node_iri: str) -> dict[str, Any]:
        """Get full text of a G_doc node (for provenance grounding)."""
        node = self.resolve_iri(node_iri)
        full_text = str(self.g_doc.value(node, KAG.fullText) or "")
        main_text = str(self.g_doc.value(node, KAG.mainText) or "")
        types = [self.compact_iri(t) for t in self.g_doc.objects(node, RDF.type)]
        page_lit = self.g_doc.value(node, KAG.pageNumber)
        return {
            "iri": self.compact_iri(node),
            "types": types,
            "page": int(page_lit) if page_lit is not None else None,
            "main_text": main_text,
            "full_text": full_text[:500] if full_text else "",
        }

    # ── Export ────────────────────────────────────────────────────────

    def serialize(self, out_dir: str) -> dict[str, str]:
        """Serialize all mutable graphs to TTL files."""
        out = Path(out_dir)
        out.mkdir(parents=True, exist_ok=True)
        paths: dict[str, str] = {}
        for name in ("entity", "claim"):
            g = self._graphs[name]
            if len(g) > 0:
                p = out / f"g_{name}.ttl"
                g.serialize(destination=str(p), format="turtle")
                paths[name] = str(p)
        return paths

    # ── Private helpers ──────────────────────────────────────────────

    def _collect_violations(
        self, results_graph: Graph, max_results: int = 25,
    ) -> dict[str, Any]:
        """Extract SHACL violations as actionable dicts."""
        from rdflib.namespace import SH
        rows: list[dict[str, Any]] = []
        total = 0
        for result in results_graph.subjects(RDF.type, SH.ValidationResult):
            total += 1
            if len(rows) >= max_results:
                continue
            focus = str(results_graph.value(result, SH.focusNode) or "")
            message = str(results_graph.value(result, SH.resultMessage) or "")
            rows.append({"node": focus, "message": message})
        return {"total": total, "rows": rows}
