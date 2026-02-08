"""Agentic OWL+SHACL workspace with sprint-1 competency questions and operators."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

from pyshacl import validate
from rdflib import Graph, Literal, Namespace, RDF, URIRef
from rdflib.namespace import SH

from experiments.owl.symbolic_handles import SymbolicBlobStore


FABRIC = Namespace("https://w3id.org/fabric/core#")
PROF = Namespace("http://www.w3.org/ns/dx/prof/")
DCT = Namespace("http://purl.org/dc/terms/")
OWL = Namespace("http://www.w3.org/2002/07/owl#")
EX = Namespace("http://la3d.local/agent/")
EX_PREFIX = str(EX)
GENERATED_PREFIX = "http://la3d.local/agent/generated/"


@dataclass(frozen=True)
class CompetencyQuestion:
    cq_id: str
    title: str
    description: str
    ask_query: str
    expected: bool = True


def sprint1_competency_questions() -> list[CompetencyQuestion]:
    return [
        CompetencyQuestion(
            cq_id="CQ1",
            title="KnowledgeGraph base constraints",
            description=(
                "Ensure one KnowledgeGraph individual has canonical hash, status, and role "
                "matching shape constraints."
            ),
            ask_query="""
PREFIX fabric: <https://w3id.org/fabric/core#>
PREFIX ex: <http://la3d.local/agent/>
ASK {
  ex:kg1 a fabric:KnowledgeGraph ;
    fabric:hasCanonicalHash ?h ;
    fabric:hasStatus ?s ;
    fabric:hasRole ?r .
  FILTER regex(str(?h), "^z[0-9a-f]{64}$")
  FILTER (?s IN ("active","deprecated","revoked","suspended"))
  FILTER (?r IN ("main","metadata","provenance","secondary","primary","encounters","observations"))
}
""".strip(),
        ),
        CompetencyQuestion(
            cq_id="CQ2",
            title="KnowledgeDataset member constraints",
            description="Ensure one KnowledgeDataset links at least one KnowledgeGraph member.",
            ask_query="""
PREFIX fabric: <https://w3id.org/fabric/core#>
PREFIX ex: <http://la3d.local/agent/>
ASK {
  ex:ds1 a fabric:KnowledgeDataset ;
    fabric:hasDatasetHash ?dh ;
    fabric:hasCanonicalHash ?ch ;
    fabric:hasStatus ?s ;
    fabric:hasMember ex:kg1 .
  ex:kg1 a fabric:KnowledgeGraph .
  FILTER regex(str(?dh), "^z[0-9a-f]{64}$")
  FILTER regex(str(?ch), "^z[0-9a-f]{64}$")
  FILTER (?s IN ("active","deprecated","revoked","suspended"))
}
""".strip(),
        ),
        CompetencyQuestion(
            cq_id="CQ3",
            title="ServiceRegistration capabilities",
            description="Ensure one service registration provides at least one allowed capability.",
            ask_query="""
PREFIX fabric: <https://w3id.org/fabric/core#>
PREFIX ex: <http://la3d.local/agent/>
ASK {
  ex:svc1 a fabric:ServiceRegistration ;
    fabric:hasCapability ?c .
  FILTER regex(str(?c), "^(SPARQL\\\\.(Query|Update|Construct|Describe)|Validation|Governance)$")
}
""".strip(),
        ),
        CompetencyQuestion(
            cq_id="CQ4",
            title="VerifiableCredential attestation link",
            description="Ensure a verifiable credential attests integrity of a knowledge asset.",
            ask_query="""
PREFIX fabric: <https://w3id.org/fabric/core#>
PREFIX ex: <http://la3d.local/agent/>
ASK {
  ex:vc1 a fabric:VerifiableCredential ;
    fabric:attestsIntegrity ex:kg1 .
  ex:kg1 a fabric:VerifiableKnowledgeAsset .
}
""".strip(),
        ),
        CompetencyQuestion(
            cq_id="CQ5",
            title="PROF profile completeness",
            description=(
                "Ensure one profile has required metadata and two resource descriptors "
                "that satisfy SHACL profile/resource shapes."
            ),
            ask_query="""
PREFIX prof: <http://www.w3.org/ns/dx/prof/>
PREFIX dct: <http://purl.org/dc/terms/>
PREFIX owl: <http://www.w3.org/2002/07/owl#>
PREFIX ex: <http://la3d.local/agent/>
ASK {
  ex:prof1 a prof:Profile ;
    dct:title ?t ;
    dct:description ?d ;
    prof:hasToken ?tok ;
    owl:versionInfo ?v ;
    dct:publisher ?pub ;
    dct:license ?lic ;
    prof:hasResource ?r1, ?r2 .
  FILTER (strlen(str(?t)) >= 5)
  FILTER (strlen(str(?d)) >= 20)
  FILTER regex(str(?tok), "^[a-z0-9\\\\-]+/v[0-9]+\\\\.[0-9]+\\\\.[0-9]+$")
  FILTER regex(str(?v), "^[0-9]+\\\\.[0-9]+\\\\.[0-9]+$")
}
""".strip(),
        ),
    ]


class AgenticOntologyWorkspace:
    """Mutable ontology workspace with SHACL validation and operator-based repair."""

    def __init__(
        self,
        ontology_path: str,
        shapes_path: str,
        questions: Iterable[CompetencyQuestion] | None = None,
    ) -> None:
        self.ontology_path = str(ontology_path)
        self.shapes_path = str(shapes_path)
        self.base_graph = Graph().parse(self.ontology_path)
        self.shapes_graph = Graph().parse(self.shapes_path)
        self.working_graph = Graph()
        self.working_graph += self.base_graph
        q_list = list(questions) if questions is not None else sprint1_competency_questions()
        self.questions = {q.cq_id: q for q in q_list}
        self._cq_anchor_iris = {
            cq.cq_id: self._extract_ex_anchor_iris(cq.ask_query) for cq in q_list
        }

    def reset(self) -> dict:
        self.working_graph = Graph()
        self.working_graph += self.base_graph
        return self.ontology_stats()

    def ontology_stats(self) -> dict:
        return {
            "ontology_path": self.ontology_path,
            "shapes_path": self.shapes_path,
            "base_triples": len(self.base_graph),
            "working_triples": len(self.working_graph),
            "shapes_triples": len(self.shapes_graph),
            "cq_count": len(self.questions),
        }

    def node_outgoing(self, node_iri: str, limit: int = 20) -> dict:
        safe_limit = max(1, min(int(limit), 100))
        node = URIRef(node_iri)
        rows = []
        for idx, (_, pred, obj) in enumerate(self.working_graph.triples((node, None, None))):
            if idx >= safe_limit:
                break
            rows.append({"p": str(pred), "o": self._term_to_str(obj)})
        return {
            "node": str(node),
            "count": len(rows),
            "limit": safe_limit,
            "rows": rows,
            "clamped": int(limit) > 100,
        }

    def node_incoming(self, node_iri: str, limit: int = 20) -> dict:
        safe_limit = max(1, min(int(limit), 100))
        node = URIRef(node_iri)
        rows = []
        for idx, (subj, pred, _) in enumerate(self.working_graph.triples((None, None, node))):
            if idx >= safe_limit:
                break
            rows.append({"s": str(subj), "p": str(pred)})
        return {
            "node": str(node),
            "count": len(rows),
            "limit": safe_limit,
            "rows": rows,
            "clamped": int(limit) > 100,
        }

    def list_cqs(self) -> list[dict]:
        out = []
        for cq_id in sorted(self.questions.keys()):
            cq = self.questions[cq_id]
            out.append(
                {
                    "cq_id": cq.cq_id,
                    "title": cq.title,
                    "description": cq.description,
                    "expected": cq.expected,
                }
            )
        return out

    def cq_details(self, cq_id: str) -> dict:
        cq = self.questions.get(cq_id)
        if cq is None:
            return {"error": f"unknown cq_id: {cq_id}"}
        return {
            "cq_id": cq.cq_id,
            "title": cq.title,
            "description": cq.description,
            "expected": cq.expected,
            "ask_query": cq.ask_query,
        }

    def cq_anchor_nodes(self, cq_id: str) -> dict:
        cq = self.questions.get(cq_id)
        if cq is None:
            return {"error": f"unknown cq_id: {cq_id}"}
        anchors = self._cq_anchor_iris.get(cq_id, [])
        return {
            "cq_id": cq_id,
            "anchors": anchors,
            "allowed_node_prefixes": [GENERATED_PREFIX],
            "notes": "Mutating operators should target CQ anchors or generated nodes.",
        }

    def node_allowed_for_cq(self, cq_id: str, node_iri: str) -> dict:
        cq = self.questions.get(cq_id)
        if cq is None:
            return {"error": f"unknown cq_id: {cq_id}"}
        anchors = self._cq_anchor_iris.get(cq_id, [])
        if node_iri in anchors:
            return {"cq_id": cq_id, "node": node_iri, "allowed": True, "reason": "anchor_node"}
        if node_iri.startswith(GENERATED_PREFIX):
            return {"cq_id": cq_id, "node": node_iri, "allowed": True, "reason": "generated_node"}
        return {
            "cq_id": cq_id,
            "node": node_iri,
            "allowed": False,
            "reason": "node_not_in_cq_anchor_set",
            "anchors": anchors,
            "allowed_node_prefixes": [GENERATED_PREFIX],
        }

    def cq_query(self, cq_id: str) -> str:
        cq = self.questions.get(cq_id)
        if cq is None:
            raise ValueError(f"unknown cq_id: {cq_id}")
        return cq.ask_query

    def evaluate_cq(self, cq_id: str) -> dict:
        cq = self.questions.get(cq_id)
        if cq is None:
            return {"error": f"unknown cq_id: {cq_id}"}
        result = self.working_graph.query(cq.ask_query)
        passed = bool(getattr(result, "askAnswer", False))
        return {
            "cq_id": cq.cq_id,
            "title": cq.title,
            "passed": passed,
            "expected": cq.expected,
            "matches_expected": passed == cq.expected,
        }

    def validate_graph(
        self,
        store: SymbolicBlobStore | None = None,
        max_results: int = 25,
        include_rows: bool = False,
    ) -> dict:
        conforms, report_graph, report_text = validate(
            self.working_graph,
            shacl_graph=self.shapes_graph,
            inference="rdfs",
            abort_on_first=False,
            allow_infos=True,
            allow_warnings=True,
            advanced=True,
            meta_shacl=False,
        )
        rows_all = list(report_graph.subjects(RDF.type, SH.ValidationResult))
        safe_max = max(1, min(int(max_results), 200))
        all_rows = []
        for row in rows_all:
            all_rows.append(
                {
                    "focus_node": self._term_to_str(report_graph.value(row, SH.focusNode)),
                    "source_shape": self._term_to_str(report_graph.value(row, SH.sourceShape)),
                    "path": self._term_to_str(report_graph.value(row, SH.resultPath)),
                    "constraint_component": self._term_to_str(
                        report_graph.value(row, SH.sourceConstraintComponent)
                    ),
                    "message": self._term_to_str(report_graph.value(row, SH.resultMessage)),
                    "severity": self._term_to_str(report_graph.value(row, SH.resultSeverity)),
                }
            )
        sig_counts: dict[str, int] = {}
        for row in all_rows:
            signature = "|".join(
                [
                    row.get("source_shape", ""),
                    row.get("path", ""),
                    row.get("constraint_component", ""),
                ]
            )
            sig_counts[signature] = sig_counts.get(signature, 0) + 1
        signatures = [
            {"signature": sig, "count": count}
            for sig, count in sorted(sig_counts.items(), key=lambda x: x[1], reverse=True)
        ]

        out = {
            "conforms": bool(conforms),
            "validation_results": len(rows_all),
            "signatures_total": len(signatures),
            "signatures_returned": min(len(signatures), safe_max),
            "signatures_clamped": len(signatures) > safe_max,
            "top_signatures": signatures[:safe_max],
        }
        if include_rows:
            out["results_returned"] = min(len(all_rows), safe_max)
            out["results_clamped"] = len(all_rows) > safe_max
            out["violations"] = all_rows[:safe_max]
        if store is not None:
            report_text_ref = store.put(str(report_text), kind="shacl_report_text")
            report_turtle = report_graph.serialize(format="turtle")
            if isinstance(report_turtle, bytes):
                report_turtle = report_turtle.decode("utf-8", errors="replace")
            report_ttl_ref = store.put(str(report_turtle), kind="shacl_report_ttl")
            violations_json = json.dumps(all_rows, ensure_ascii=True)
            violations_ref = store.put(violations_json, kind="shacl_violations_json")
            signatures_json = json.dumps(signatures, ensure_ascii=True)
            signatures_ref = store.put(signatures_json, kind="shacl_signatures_json")
            out["report_text_ref"] = report_text_ref.to_dict()
            out["report_ttl_ref"] = report_ttl_ref.to_dict()
            out["violations_ref"] = violations_ref.to_dict()
            out["signatures_ref"] = signatures_ref.to_dict()
        return out

    def operator_catalog(self) -> list[dict]:
        return [
            {
                "operator_id": "op_assert_type",
                "summary": "Add rdf:type assertion for one node.",
                "args": ["node_iri", "class_iri"],
            },
            {
                "operator_id": "op_set_single_literal",
                "summary": "Replace all values for a property with one literal.",
                "args": ["node_iri", "prop_iri", "value"],
            },
            {
                "operator_id": "op_set_single_iri",
                "summary": "Replace all values for a property with one IRI object.",
                "args": ["node_iri", "prop_iri", "value_iri"],
            },
            {
                "operator_id": "op_add_literal",
                "summary": "Add one literal value for a property without removing existing values.",
                "args": ["node_iri", "prop_iri", "value"],
            },
            {
                "operator_id": "op_add_iri_link",
                "summary": "Add one IRI object value for a property without removing existing values.",
                "args": ["node_iri", "prop_iri", "value_iri"],
            },
            {
                "operator_id": "op_remove_literal",
                "summary": "Remove matching literal values for a property.",
                "args": ["node_iri", "prop_iri", "value"],
            },
            {
                "operator_id": "op_remove_iri_link",
                "summary": "Remove an exact IRI link for a property.",
                "args": ["node_iri", "prop_iri", "value_iri"],
            },
            {
                "operator_id": "op_ensure_mincount_links",
                "summary": "Ensure at least n linked nodes for a property and type them.",
                "args": ["node_iri", "prop_iri", "target_class_iri", "n", "prefix"],
            },
            {
                "operator_id": "op_normalize_cardinality",
                "summary": "Reduce property values to exactly one value (deterministic keep).",
                "args": ["node_iri", "prop_iri", "keep_value"],
            },
        ]

    def op_assert_type(self, node_iri: str, class_iri: str) -> dict:
        node = URIRef(node_iri)
        cls = URIRef(class_iri)
        before = (node, RDF.type, cls) in self.working_graph
        self.working_graph.add((node, RDF.type, cls))
        return {"operator": "op_assert_type", "added": not before, "node": str(node), "class": str(cls)}

    def op_set_single_literal(self, node_iri: str, prop_iri: str, value: str) -> dict:
        node = URIRef(node_iri)
        prop = URIRef(prop_iri)
        existing = list(self.working_graph.objects(node, prop))
        for obj in existing:
            self.working_graph.remove((node, prop, obj))
        self.working_graph.add((node, prop, Literal(str(value))))
        return {
            "operator": "op_set_single_literal",
            "node": str(node),
            "property": str(prop),
            "removed": len(existing),
            "new_value": str(value),
        }

    def op_set_single_iri(self, node_iri: str, prop_iri: str, value_iri: str) -> dict:
        node = URIRef(node_iri)
        prop = URIRef(prop_iri)
        existing = list(self.working_graph.objects(node, prop))
        for obj in existing:
            self.working_graph.remove((node, prop, obj))
        self.working_graph.add((node, prop, URIRef(value_iri)))
        return {
            "operator": "op_set_single_iri",
            "node": str(node),
            "property": str(prop),
            "removed": len(existing),
            "new_value": str(value_iri),
        }

    def op_add_literal(self, node_iri: str, prop_iri: str, value: str) -> dict:
        node = URIRef(node_iri)
        prop = URIRef(prop_iri)
        literal = Literal(str(value))
        before = (node, prop, literal) in self.working_graph
        self.working_graph.add((node, prop, literal))
        total = len(list(self.working_graph.objects(node, prop)))
        return {
            "operator": "op_add_literal",
            "node": str(node),
            "property": str(prop),
            "added": not before,
            "value": str(value),
            "count_after": total,
        }

    def op_add_iri_link(self, node_iri: str, prop_iri: str, value_iri: str) -> dict:
        node = URIRef(node_iri)
        prop = URIRef(prop_iri)
        value = URIRef(value_iri)
        before = (node, prop, value) in self.working_graph
        self.working_graph.add((node, prop, value))
        total = len(list(self.working_graph.objects(node, prop)))
        return {
            "operator": "op_add_iri_link",
            "node": str(node),
            "property": str(prop),
            "added": not before,
            "value": str(value),
            "count_after": total,
        }

    def op_remove_literal(self, node_iri: str, prop_iri: str, value: str) -> dict:
        node = URIRef(node_iri)
        prop = URIRef(prop_iri)
        removed = 0
        for obj in list(self.working_graph.objects(node, prop)):
            if isinstance(obj, Literal) and str(obj) == str(value):
                self.working_graph.remove((node, prop, obj))
                removed += 1
        total = len(list(self.working_graph.objects(node, prop)))
        return {
            "operator": "op_remove_literal",
            "node": str(node),
            "property": str(prop),
            "value": str(value),
            "removed": removed,
            "count_after": total,
        }

    def op_remove_iri_link(self, node_iri: str, prop_iri: str, value_iri: str) -> dict:
        node = URIRef(node_iri)
        prop = URIRef(prop_iri)
        value = URIRef(value_iri)
        removed = 1 if (node, prop, value) in self.working_graph else 0
        self.working_graph.remove((node, prop, value))
        total = len(list(self.working_graph.objects(node, prop)))
        return {
            "operator": "op_remove_iri_link",
            "node": str(node),
            "property": str(prop),
            "value": str(value),
            "removed": removed,
            "count_after": total,
        }

    def op_ensure_mincount_links(
        self,
        node_iri: str,
        prop_iri: str,
        target_class_iri: str,
        n: int,
        prefix: str = "http://la3d.local/agent/generated/",
    ) -> dict:
        node = URIRef(node_iri)
        prop = URIRef(prop_iri)
        target_class = URIRef(target_class_iri)
        safe_n = max(0, min(int(n), 50))
        existing = [obj for obj in self.working_graph.objects(node, prop) if isinstance(obj, URIRef)]
        created = []
        idx = 0
        while len(existing) < safe_n:
            candidate = URIRef(f"{prefix.rstrip('/')}/n{idx}")
            idx += 1
            if candidate in existing:
                continue
            self.working_graph.add((node, prop, candidate))
            self.working_graph.add((candidate, RDF.type, target_class))
            existing.append(candidate)
            created.append(str(candidate))
        return {
            "operator": "op_ensure_mincount_links",
            "node": str(node),
            "property": str(prop),
            "target_class": str(target_class),
            "count_after": len(existing),
            "created": created,
        }

    def op_normalize_cardinality(self, node_iri: str, prop_iri: str, keep_value: str = "") -> dict:
        node = URIRef(node_iri)
        prop = URIRef(prop_iri)
        existing = list(self.working_graph.objects(node, prop))
        if len(existing) <= 1:
            return {
                "operator": "op_normalize_cardinality",
                "node": str(node),
                "property": str(prop),
                "removed": 0,
                "kept": self._term_to_str(existing[0]) if existing else "",
            }
        keep = None
        if keep_value:
            for obj in existing:
                if self._term_to_str(obj) == keep_value:
                    keep = obj
                    break
        if keep is None:
            keep = sorted(existing, key=self._term_to_str)[0]
        removed = 0
        for obj in existing:
            if obj == keep:
                continue
            self.working_graph.remove((node, prop, obj))
            removed += 1
        return {
            "operator": "op_normalize_cardinality",
            "node": str(node),
            "property": str(prop),
            "removed": removed,
            "kept": self._term_to_str(keep),
        }

    def snapshot(self, store: SymbolicBlobStore | None = None, label: str = "working") -> dict:
        ttl = self.working_graph.serialize(format="turtle")
        if isinstance(ttl, bytes):
            ttl = ttl.decode("utf-8", errors="replace")
        out = {"label": label, "triples": len(self.working_graph)}
        if store is not None:
            graph_ref = store.put(str(ttl), kind=f"graph_{label}")
            out["graph_ref"] = graph_ref.to_dict()
        return out

    def save_snapshot(self, path: str) -> dict:
        out_path = Path(path)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        self.working_graph.serialize(destination=str(out_path), format="turtle")
        return {"path": str(out_path), "triples": len(self.working_graph)}

    @staticmethod
    def _term_to_str(term) -> str:
        if term is None:
            return ""
        return str(term)

    @staticmethod
    def _extract_ex_anchor_iris(query: str) -> list[str]:
        anchors = []
        seen = set()
        for local in re.findall(r"\bex:([A-Za-z_][A-Za-z0-9_]*)", query):
            iri = str(EX[local])
            if iri in seen:
                continue
            seen.add(iri)
            anchors.append(iri)
        return anchors
