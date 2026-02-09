"""Agentic OWL+SHACL workspace with sprint-1 competency questions and operators."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable

from pyshacl import validate
from rdflib import Graph, Literal, Namespace, RDF, URIRef
from rdflib.namespace import SH

from experiments.owl.symbolic_handles import SymbolicBlobStore


FABRIC = Namespace("https://w3id.org/fabric/core#")
PROF = Namespace("http://www.w3.org/ns/dx/prof/")
DCT = Namespace("http://purl.org/dc/terms/")
OWL = Namespace("http://www.w3.org/2002/07/owl#")
DCAT = Namespace("http://www.w3.org/ns/dcat#")
EX = Namespace("http://la3d.local/agent/")
EX_PREFIX = str(EX)
GENERATED_PREFIX = "http://la3d.local/agent/generated/"
KNOWN_PREFIXES = {
    "rdf": "http://www.w3.org/1999/02/22-rdf-syntax-ns#",
    "rdfs": "http://www.w3.org/2000/01/rdf-schema#",
    "owl": "http://www.w3.org/2002/07/owl#",
    "xsd": "http://www.w3.org/2001/XMLSchema#",
    "sh": "http://www.w3.org/ns/shacl#",
    "fabric": str(FABRIC),
    "prof": str(PROF),
    "dct": str(DCT),
    "ex": str(EX),
}


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

    def cq_query_symbols(self, cq_id: str) -> dict:
        cq = self.questions.get(cq_id)
        if cq is None:
            return {"error": f"unknown cq_id: {cq_id}"}
        triples = []
        filters = []
        variables = set()
        current_subject = ""
        in_ask = False
        for raw_line in cq.ask_query.splitlines():
            line = raw_line.strip()
            if not line:
                continue
            if line.startswith("PREFIX"):
                continue
            if line.startswith("ASK"):
                in_ask = True
                continue
            if not in_ask:
                continue
            if line == "{":
                continue
            if line.startswith("}"):
                break
            if line.startswith("FILTER"):
                filt = self._parse_filter(line)
                filters.append(filt)
                var_name = str(filt.get("variable", ""))
                if var_name.startswith("?"):
                    variables.add(var_name)
                continue

            core = line.rstrip(";.").strip()
            if not core:
                continue
            parts = core.split(None, 2)
            if len(parts) == 3:
                subj, pred, obj_raw = parts
                current_subject = subj
            elif len(parts) == 2 and current_subject:
                subj = current_subject
                pred, obj_raw = parts
            else:
                continue

            object_terms = [x.strip() for x in obj_raw.split(",") if x.strip()]
            for obj in object_terms:
                normalized_obj = self._clean_token(obj)
                triples.append(
                    {
                        "s": subj,
                        "p": pred,
                        "o": normalized_obj,
                        "s_expanded": self._expand_prefixed(subj),
                        "p_expanded": self._expand_prefixed(pred),
                        "o_expanded": self._expand_prefixed(normalized_obj),
                    }
                )
                for token in (subj, pred, normalized_obj):
                    normalized_var = self._normalize_variable(token)
                    if normalized_var:
                        variables.add(normalized_var)

        required_assertions = []
        for row in triples:
            if row["s"].startswith("ex:") and not row["o"].startswith("?"):
                required_assertions.append(
                    {
                        "s": row["s_expanded"],
                        "p": row["p_expanded"],
                        "o": row["o_expanded"],
                    }
                )
        return {
            "cq_id": cq_id,
            "anchors": self._cq_anchor_iris.get(cq_id, []),
            "variables": sorted(variables),
            "triple_patterns": triples,
            "filters": filters,
            "required_assertions": required_assertions,
        }

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
        focus_nodes: Iterable[str] | None = None,
        include_generated: bool = False,
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
        focus_set = {str(x) for x in (focus_nodes or []) if str(x)}
        scoped_rows = []
        for row in all_rows:
            if not focus_set and not include_generated:
                scoped_rows.append(row)
                continue
            focus_node = str(row.get("focus_node", ""))
            if focus_node in focus_set:
                scoped_rows.append(row)
                continue
            if include_generated and focus_node.startswith(GENERATED_PREFIX):
                scoped_rows.append(row)
                continue

        sig_index: dict[str, dict[str, Any]] = {}
        for row in scoped_rows:
            source_shape = row.get("source_shape", "")
            path = row.get("path", "")
            component = row.get("constraint_component", "")
            signature = "|".join([source_shape, path, component])
            entry = sig_index.get(signature)
            if entry is None:
                entry = {
                    "signature": signature,
                    "source_shape": source_shape,
                    "path": path,
                    "constraint_component": component,
                    "count": 0,
                    "focus_node_counts": {},
                }
                sig_index[signature] = entry
            entry["count"] += 1
            node_key = str(row.get("focus_node", ""))
            if node_key:
                node_counts = entry["focus_node_counts"]
                node_counts[node_key] = node_counts.get(node_key, 0) + 1

        signatures = []
        for entry in sig_index.values():
            node_counts = entry.pop("focus_node_counts")
            top_focus_nodes = sorted(node_counts.items(), key=lambda x: x[1], reverse=True)[:3]
            entry["top_focus_nodes"] = [
                {"node": node, "count": count}
                for node, count in top_focus_nodes
            ]
            signatures.append(entry)
        signatures.sort(key=lambda x: x["count"], reverse=True)

        out = {
            "conforms": bool(conforms),
            "validation_results_total": len(rows_all),
            "validation_results": len(scoped_rows),
            "focus_mode": bool(focus_set or include_generated),
            "focus_nodes": sorted(focus_set),
            "focus_include_generated": bool(include_generated),
            "signatures_total": len(signatures),
            "signatures_returned": min(len(signatures), safe_max),
            "signatures_clamped": len(signatures) > safe_max,
            "top_signatures": signatures[:safe_max],
        }
        if include_rows:
            out["results_returned"] = min(len(scoped_rows), safe_max)
            out["results_clamped"] = len(scoped_rows) > safe_max
            out["violations"] = scoped_rows[:safe_max]
        if store is not None:
            report_text_ref = store.put(str(report_text), kind="shacl_report_text")
            report_turtle = report_graph.serialize(format="turtle")
            if isinstance(report_turtle, bytes):
                report_turtle = report_turtle.decode("utf-8", errors="replace")
            report_ttl_ref = store.put(str(report_turtle), kind="shacl_report_ttl")
            violations_json = json.dumps(scoped_rows, ensure_ascii=True)
            violations_ref = store.put(violations_json, kind="shacl_violations_json")
            signatures_json = json.dumps(signatures, ensure_ascii=True)
            signatures_ref = store.put(signatures_json, kind="shacl_signatures_json")
            out["report_text_ref"] = report_text_ref.to_dict()
            out["report_ttl_ref"] = report_ttl_ref.to_dict()
            out["violations_ref"] = violations_ref.to_dict()
            out["signatures_ref"] = signatures_ref.to_dict()
        return out

    def validate_focus_for_cq(
        self,
        cq_id: str,
        store: SymbolicBlobStore | None = None,
        max_results: int = 25,
        include_rows: bool = False,
    ) -> dict:
        cq = self.questions.get(cq_id)
        if cq is None:
            return {"error": f"unknown cq_id: {cq_id}"}
        anchors = self._cq_anchor_iris.get(cq_id, [])
        return self.validate_graph(
            store=store,
            max_results=max_results,
            include_rows=include_rows,
            focus_nodes=anchors,
            include_generated=True,
        )

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
            {
                "operator_id": "op_profile_closure",
                "summary": "Apply deterministic profile/resource closure defaults for recurring SHACL failures.",
                "args": ["profile_iri", "resource_count", "resource_prefix"],
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

    def op_profile_closure(
        self,
        profile_iri: str,
        resource_count: int = 2,
        resource_prefix: str = "http://la3d.local/agent/generated/resource",
    ) -> dict:
        profile = URIRef(profile_iri)
        safe_count = max(1, min(int(resource_count), 10))
        self.working_graph.add((profile, RDF.type, PROF.Profile))
        self._ensure_literal(profile, DCT.title, "Profile")
        self._ensure_literal(
            profile,
            DCT.description,
            "Profile used for deterministic SHACL closure in sprint experiments.",
        )
        self._ensure_literal(profile, PROF.hasToken, "profile/v1.0.0")
        self._ensure_literal(profile, OWL.versionInfo, "1.0.0")
        self._ensure_iri(profile, DCT.publisher, EX.org1)
        self._ensure_iri(profile, DCT.license, EX.license1)

        mincount_out = self.op_ensure_mincount_links(
            node_iri=str(profile),
            prop_iri=str(PROF.hasResource),
            target_class_iri=str(PROF.ResourceDescriptor),
            n=safe_count,
            prefix=resource_prefix,
        )
        resources = [
            obj
            for obj in self.working_graph.objects(profile, PROF.hasResource)
            if isinstance(obj, URIRef)
        ]
        resources = sorted(resources, key=str)

        seeded = []
        for idx, resource in enumerate(resources):
            self.working_graph.add((resource, RDF.type, PROF.ResourceDescriptor))
            self._ensure_literal(resource, DCT.title, f"Resource {idx}")
            self._ensure_literal(resource, DCT.description, f"Descriptor for resource {idx}")
            self._ensure_iri(resource, PROF.hasRole, PROF.role)
            self._ensure_iri(resource, DCT["format"], EX.ttl)
            self._ensure_iri(resource, PROF.hasArtifact, URIRef(f"{EX}artifact{idx}"))
            self._ensure_literal(resource, DCAT.mediaType, "text/turtle")
            seeded.append(str(resource))

        return {
            "operator": "op_profile_closure",
            "profile": str(profile),
            "resource_count": len(resources),
            "resources_seeded": seeded,
            "mincount_created": mincount_out.get("created", []),
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

    def _ensure_literal(self, node: URIRef, prop: URIRef, value: str) -> None:
        for existing in self.working_graph.objects(node, prop):
            if isinstance(existing, Literal) and str(existing) == str(value):
                return
        self.working_graph.add((node, prop, Literal(str(value))))

    def _ensure_iri(self, node: URIRef, prop: URIRef, value: URIRef) -> None:
        iri = URIRef(str(value))
        if (node, prop, iri) in self.working_graph:
            return
        self.working_graph.add((node, prop, iri))

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

    @staticmethod
    def _parse_filter(line: str) -> dict:
        regex_match = re.search(
            r"FILTER\s+regex\s*\(\s*str\((\?[A-Za-z_][A-Za-z0-9_]*)\)\s*,\s*\"([^\"]+)\"",
            line,
            re.IGNORECASE,
        )
        if regex_match:
            return {
                "kind": "regex",
                "variable": regex_match.group(1),
                "pattern": regex_match.group(2),
            }
        in_match = re.search(
            r"FILTER\s*\(\s*(\?[A-Za-z_][A-Za-z0-9_]*)\s+IN\s*\(([^)]+)\)\s*\)",
            line,
            re.IGNORECASE,
        )
        if in_match:
            values = re.findall(r'"([^"]+)"', in_match.group(2))
            return {
                "kind": "enum",
                "variable": in_match.group(1),
                "values": values,
            }
        strlen_match = re.search(
            r"FILTER\s*\(\s*strlen\s*\(\s*str\((\?[A-Za-z_][A-Za-z0-9_]*)\)\s*\)\s*>=\s*([0-9]+)\s*\)",
            line,
            re.IGNORECASE,
        )
        if strlen_match:
            return {
                "kind": "strlen_min",
                "variable": strlen_match.group(1),
                "value": int(strlen_match.group(2)),
            }
        return {"kind": "raw", "text": line}

    @staticmethod
    def _normalize_variable(token: str) -> str:
        cleaned = AgenticOntologyWorkspace._clean_token(token)
        if cleaned.startswith("?"):
            return cleaned
        return ""

    @staticmethod
    def _clean_token(token: str) -> str:
        return token.strip().rstrip(",;")

    @staticmethod
    def _expand_prefixed(token: str) -> str:
        if token.startswith("?"):
            return token
        if token.startswith("<") and token.endswith(">"):
            return token[1:-1]
        if ":" in token:
            prefix, local = token.split(":", 1)
            base = KNOWN_PREFIXES.get(prefix)
            if base is not None:
                return base + local
        return token
