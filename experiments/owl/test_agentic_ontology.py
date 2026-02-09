"""Tests for agentic OWL+SHACL workspace operators and CQ checks."""

from experiments.owl.agentic_ontology import (
    DCT,
    FABRIC,
    OWL,
    PROF,
    EX,
    AgenticOntologyWorkspace,
)
from experiments.owl.agentic_tools import AgenticOwlToolset
from rdflib import RDF


def _workspace() -> AgenticOntologyWorkspace:
    return AgenticOntologyWorkspace(
        ontology_path="ontology/core-vocabulary.ttl",
        shapes_path="ontology/core-shapes.ttl",
    )


def test_cq1_with_minimal_operator_sequence_conforms():
    ws = _workspace()
    ws.op_assert_type(str(EX.kg1), str(FABRIC.KnowledgeGraph))
    ws.op_set_single_literal(str(EX.kg1), str(FABRIC.hasCanonicalHash), "z" + "a" * 64)
    ws.op_set_single_literal(str(EX.kg1), str(FABRIC.hasStatus), "active")
    ws.op_set_single_literal(str(EX.kg1), str(FABRIC.hasRole), "main")

    cq = ws.evaluate_cq("CQ1")
    report = ws.validate_graph(max_results=20, include_rows=True)

    assert cq["passed"] is True
    focus_nodes = [row["focus_node"] for row in report["violations"]]
    assert str(EX.kg1) not in focus_nodes


def test_ensure_mincount_links_creates_typed_nodes():
    ws = _workspace()
    ws.op_assert_type(str(EX.prof1), str(PROF.Profile))
    out = ws.op_ensure_mincount_links(
        node_iri=str(EX.prof1),
        prop_iri=str(PROF.hasResource),
        target_class_iri=str(PROF.ResourceDescriptor),
        n=2,
        prefix="http://la3d.local/agent/generated/profile",
    )
    assert out["count_after"] >= 2
    for iri in out["created"]:
        facts = ws.node_outgoing(iri, limit=10)
        types = [row["o"] for row in facts["rows"] if row["p"] == str(RDF.type)]
        assert str(PROF.ResourceDescriptor) in types


def test_cq5_becomes_true_after_profile_fields_and_resources():
    ws = _workspace()
    ws.op_assert_type(str(EX.prof1), str(PROF.Profile))
    ws.op_set_single_literal(str(EX.prof1), str(DCT.title), "Profile Alpha")
    ws.op_set_single_literal(str(EX.prof1), str(DCT.description), "A profile used for sprint one validation.")
    ws.op_set_single_literal(str(EX.prof1), str(PROF.hasToken), "alpha/v1.0.0")
    ws.op_set_single_literal(str(EX.prof1), str(OWL.versionInfo), "1.0.0")
    ws.op_set_single_iri(str(EX.prof1), str(DCT.publisher), str(EX.org1))
    ws.op_set_single_iri(str(EX.prof1), str(DCT.license), str(EX.license1))
    ws.op_ensure_mincount_links(
        node_iri=str(EX.prof1),
        prop_iri=str(PROF.hasResource),
        target_class_iri=str(PROF.ResourceDescriptor),
        n=2,
        prefix="http://la3d.local/agent/generated/resource",
    )

    for idx in range(2):
        res = f"http://la3d.local/agent/generated/resource/n{idx}"
        ws.op_set_single_literal(res, str(DCT.title), f"Resource {idx}")
        ws.op_set_single_literal(res, str(DCT.description), f"Descriptor for resource {idx}")
        ws.op_set_single_iri(res, str(PROF.hasRole), str(PROF.role))
        ws.op_set_single_iri(res, str(DCT.format), str(EX.ttl))
        ws.op_set_single_iri(res, str(PROF.hasArtifact), str(EX[f"artifact{idx}"]))
        ws.op_set_single_literal(res, "http://www.w3.org/ns/dcat#mediaType", "text/turtle")

    cq = ws.evaluate_cq("CQ5")
    assert cq["passed"] is True


def test_add_iri_link_is_non_destructive():
    ws = _workspace()
    ws.op_assert_type(str(EX.prof1), str(PROF.Profile))
    ws.op_add_iri_link(str(EX.prof1), str(PROF.hasResource), str(EX.res1))
    ws.op_add_iri_link(str(EX.prof1), str(PROF.hasResource), str(EX.res2))
    facts = ws.node_outgoing(str(EX.prof1), limit=20)
    resources = [row["o"] for row in facts["rows"] if row["p"] == str(PROF.hasResource)]
    assert str(EX.res1) in resources
    assert str(EX.res2) in resources


def test_cq2_anchor_nodes_include_ds1_and_kg1():
    ws = _workspace()
    anchors = ws.cq_anchor_nodes("CQ2")
    assert str(EX.ds1) in anchors["anchors"]
    assert str(EX.kg1) in anchors["anchors"]


def test_cq4_query_symbols_exposes_attests_integrity_pattern():
    ws = _workspace()
    symbols = ws.cq_query_symbols("CQ4")
    triples = symbols["triple_patterns"]
    assert any(
        row["s"] == "ex:vc1"
        and row["p"] == "fabric:attestsIntegrity"
        and row["o"] == "ex:kg1"
        for row in triples
    )


def test_agentic_toolset_blocks_non_anchor_mutation_for_current_cq():
    ws = _workspace()
    ts = AgenticOwlToolset(
        prompt_text="cq2 test",
        workspace=ws,
        current_cq_id="CQ2",
    )
    blocked = ts.op_set_single_literal(
        "http://la3d.local/agent/kd1",
        str(FABRIC.hasStatus),
        "active",
    )
    assert blocked["error"] == "node_not_allowed_for_current_cq"


def test_agentic_toolset_blocks_repeated_handle_reads():
    ws = _workspace()
    ts = AgenticOwlToolset(
        prompt_text="cq1 test",
        workspace=ws,
        current_cq_id="CQ1",
    )
    window = ts.cq_query_read_window("CQ1", start=0, size=32)
    ref = window["window_ref"]
    for _ in range(3):
        out = ts.handle_read_window(ref, start=0, size=16)
        assert "error" not in out
    blocked = ts.handle_read_window(ref, start=0, size=16)
    assert blocked["error"] == "repeated_handle_read_blocked"


def test_agentic_toolset_blocks_repeated_validation_without_delta():
    ws = _workspace()
    ts = AgenticOwlToolset(
        prompt_text="cq2 test",
        workspace=ws,
        current_cq_id="CQ2",
    )
    for _ in range(3):
        out = ts.ontology_signature_index(max_signatures=5)
        assert "error" not in out
    blocked = ts.ontology_signature_index(max_signatures=5)
    assert blocked["error"] == "validation_without_graph_delta"
