"""Tool surface for KAG entity extraction over multi-graph workspace.

Combines:
  - 5 QA read tools (from kag_qa_tools.py) for navigating G_doc
  - 7 generic write tools routed to G_entity / G_claim via `graph` param
  - G_doc inspection (sections, node text) for provenance grounding

All tools return dicts. Errors return {"TOOL_ERROR": ...} instead of raising
(critical: re-raising crashes the Pyodide sandbox).
"""

from __future__ import annotations

from typing import Any

from rdflib import Namespace

from experiments.KAG.kag_entity_workspace import KagEntityWorkspace
from experiments.KAG.kag_qa_tools import KagQAToolset


DOCO = Namespace("http://purl.org/spar/doco/")
KAG = Namespace("http://la3d.local/kag#")


class KagEntityToolset:
    """Combined read + write tool surface for entity extraction.

    Read tools (from KagQAToolset): navigate G_doc to find source spans.
    Write tools (from KagEntityWorkspace): create entities/claims in G_entity/G_claim.
    """

    def __init__(
        self,
        workspace: KagEntityWorkspace,
        qa_toolset: KagQAToolset,
    ) -> None:
        self.ws = workspace
        self.qa = qa_toolset

    # ── Read tools (G_doc navigation, delegated to QA toolset) ───────

    def g_section_content(self, section_iri: str) -> list[dict[str, Any]]:
        """Children of a section: type, text preview, page.

        Returns list of dicts with keys: iri, types, text_preview, page.
        Use this to find content blocks to ground entities against.
        """
        return self.qa.g_section_content(section_iri)

    def g_node_detail(self, node_iri: str) -> dict[str, Any]:
        """Full properties of a single G_doc node (text truncated to 500 chars).

        Returns dict with keys: iri, properties.
        Use to read full text before creating entities.
        """
        return self.qa.g_node_detail(node_iri)

    def g_search(self, query: str, limit: int = 10) -> list[dict[str, Any]]:
        """Full-text search over G_doc kag:fullText content.

        Returns list of dicts with keys: iri, types, page, score, snippet, text_preview.
        Use to find mentions of chemical names, measurements, etc.
        """
        return self.qa.g_search(query, limit)

    def g_figure_info(self, figure_iri: str) -> dict[str, Any]:
        """Figure details from G_doc: caption, page, image description.

        Returns dict with keys: iri, page, caption, image_description, referring_paragraphs.
        """
        return self.qa.g_figure_info(figure_iri)

    def g_node_refs(self, node_iri: str) -> dict[str, Any]:
        """Bidirectional relationships in G_doc: citations, cross-references.

        Returns dict with keys: iri, types, plus cites/cited_by/refers_to/referred_by.
        """
        return self.qa.g_node_refs(node_iri)

    # ── Write tools (entity/claim creation, routed via workspace) ────

    def op_create_entity(
        self,
        entity_id: str,
        class_iri: str,
        graph: str = "entity",
    ) -> dict[str, Any]:
        """Create a new entity node with rdf:type in the target graph.

        Args:
            entity_id: Node IRI or local name (e.g., 'ex:tcne_01' or 'tcne_01')
            class_iri: SIO/QUDT class (e.g., 'sio:ChemicalEntity', 'qudt:QuantityValue')
            graph: Target graph - 'entity' or 'claim' (default: 'entity')

        Returns dict with keys: operator, node, class, graph.
        """
        try:
            return self.ws.op_create_entity(entity_id, class_iri, graph=graph)
        except Exception as exc:
            return {"TOOL_ERROR": f"{type(exc).__name__}: {exc}", "error": str(exc)}

    def op_assert_type(
        self,
        node_iri: str,
        class_iri: str,
        graph: str = "entity",
    ) -> dict[str, Any]:
        """Add rdf:type to an existing node in the target graph.

        Args:
            node_iri: Node IRI (e.g., 'ex:tcne_01')
            class_iri: Class IRI (e.g., 'sio:Molecule')
            graph: Target graph - 'entity' or 'claim' (default: 'entity')

        Returns dict with keys: operator, node, class, graph, already_present.
        """
        try:
            return self.ws.op_assert_type(node_iri, class_iri, graph=graph)
        except Exception as exc:
            return {"TOOL_ERROR": f"{type(exc).__name__}: {exc}", "error": str(exc)}

    def op_set_literal(
        self,
        node_iri: str,
        prop_iri: str,
        value: str,
        datatype_iri: str = "",
        graph: str = "entity",
    ) -> dict[str, Any]:
        """Set/replace a literal property on a node.

        Args:
            node_iri: Node IRI (e.g., 'ex:bond_01')
            prop_iri: Property IRI (e.g., 'rdfs:label', 'qudt:numericValue')
            value: Literal value as string
            datatype_iri: Optional XSD datatype (e.g., 'xsd:double')
            graph: Target graph - 'entity' or 'claim' (default: 'entity')

        Returns dict with keys: operator, node, property, value, removed, graph.
        """
        try:
            return self.ws.op_set_literal(node_iri, prop_iri, value, datatype_iri, graph=graph)
        except Exception as exc:
            return {"TOOL_ERROR": f"{type(exc).__name__}: {exc}", "error": str(exc)}

    def op_add_link(
        self,
        subject_iri: str,
        predicate_iri: str,
        object_iri: str,
        graph: str = "entity",
    ) -> dict[str, Any]:
        """Add an IRI-valued triple to the target graph.

        Args:
            subject_iri: Subject node (e.g., 'ex:tcne_01')
            predicate_iri: Predicate (e.g., 'prov:wasDerivedFrom', 'sio:has-measurement-value')
            object_iri: Object node (e.g., 'ex:b_p003_0005' for G_doc grounding)
            graph: Target graph - 'entity' or 'claim' (default: 'entity')

        Returns dict with keys: operator, subject, predicate, object, graph, already_present.
        """
        try:
            return self.ws.op_add_link(subject_iri, predicate_iri, object_iri, graph=graph)
        except Exception as exc:
            return {"TOOL_ERROR": f"{type(exc).__name__}: {exc}", "error": str(exc)}

    def op_set_link(
        self,
        subject_iri: str,
        predicate_iri: str,
        object_iri: str,
        graph: str = "entity",
    ) -> dict[str, Any]:
        """Replace all values for (subject, predicate) with a single new IRI.

        Args:
            subject_iri: Subject node
            predicate_iri: Predicate
            object_iri: New object value
            graph: Target graph - 'entity' or 'claim' (default: 'entity')

        Returns dict with keys: operator, subject, predicate, object, removed, graph.
        """
        try:
            return self.ws.op_set_link(subject_iri, predicate_iri, object_iri, graph=graph)
        except Exception as exc:
            return {"TOOL_ERROR": f"{type(exc).__name__}: {exc}", "error": str(exc)}

    def validate_graph(self, graph: str = "all") -> dict[str, Any]:
        """Validate one graph layer or all layers.

        Args:
            graph: 'entity', 'claim', or 'all' (default: 'all')

        Returns dict with conforms (bool) and per-layer violation details.
        Call with no arguments to validate everything.
        """
        try:
            return self.ws.validate_graph(graph)
        except Exception as exc:
            return {"TOOL_ERROR": f"{type(exc).__name__}: {exc}", "error": str(exc),
                    "conforms": False, "total_violations": -1}

    def finalize_graph(self, answer: str) -> dict[str, Any]:
        """Gate SUBMIT on SHACL conformance across all layers.

        Call before SUBMIT. Returns status='READY' if all graphs conform.

        Args:
            answer: Summary text for the extraction results.

        Returns dict with status ('READY' or 'NOT_READY') and layer details.
        """
        try:
            return self.ws.finalize_graph(answer)
        except Exception as exc:
            return {"TOOL_ERROR": f"{type(exc).__name__}: {exc}", "error": str(exc),
                    "conforms": False, "status": "NOT_READY"}

    # ── Tool surface for DSPy RLM ────────────────────────────────────

    def as_tools(self) -> list:
        """Return combined tool surface (5 read + 7 write) for DSPy RLM."""
        return [
            # Read tools (G_doc navigation)
            self.g_section_content,
            self.g_node_detail,
            self.g_search,
            self.g_figure_info,
            self.g_node_refs,
            # Write tools (entity/claim creation)
            self.op_create_entity,
            self.op_assert_type,
            self.op_set_literal,
            self.op_add_link,
            self.op_set_link,
            # Validation
            self.validate_graph,
            self.finalize_graph,
        ]
