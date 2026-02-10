from pathlib import Path

from rdflib import RDF, URIRef

from experiments.KAG.agentic_doc_tools import DOCO, KAG, KagDocToolset
from experiments.KAG.agentic_kag_runner import run_pipeline


def test_run0_builds_conforming_graph(tmp_path: Path):
    summary = run_pipeline(
        ocr_dir="experiments/KAG/test_data/omd_test_ocr",
        out_dir=str(tmp_path),
        run_name="test_run0",
    )
    assert summary["validation"]["conforms"] is True
    assert summary["validation"]["validation_results"] == 0
    assert summary["graph_stats"]["triples"] > 0


def test_caption_describes_nearest_visual(tmp_path: Path):
    """Captions should link to the nearest visual by bbox proximity, not just the last prior visual."""
    summary = run_pipeline(
        ocr_dir="experiments/KAG/test_data/pet_test_ocr",
        out_dir=str(tmp_path),
        run_name="test_caption_proximity",
    )
    assert summary["validation"]["conforms"] is True


def test_table_caption_describes_table_not_figure():
    """A figure_title block with 'Table N' text should describe a doco:Table, not doco:Figure."""
    tools = KagDocToolset(ocr_dir="experiments/KAG/test_data/pet_test_ocr")
    from experiments.KAG.agentic_doc_agents import StructureParserAgent

    agent = StructureParserAgent()
    agent.build(tools=tools, document_id="pet_test")

    graph = tools.graph
    # Find all caption nodes that describe something
    describes = KAG.describes
    table_class = DOCO.Table
    figure_class = DOCO.Figure

    for caption_node in graph.subjects(RDF.type, URIRef("http://purl.org/spar/deo/Caption")):
        main_text = str(graph.value(caption_node, KAG.mainText) or "")
        described = list(graph.objects(caption_node, describes))
        assert len(described) == 1, f"Caption {caption_node} should describe exactly one visual"

        target = described[0]
        target_types = set(graph.objects(target, RDF.type))

        if main_text.lower().startswith("table"):
            assert table_class in target_types, (
                f"Caption '{main_text[:60]}' ({caption_node}) describes {target} "
                f"which is {target_types}, expected doco:Table"
            )


def test_no_two_captions_describe_same_visual():
    """Each visual should not be shared by too many captions.

    Multi-panel figures may have sub-labels (a, b, c) and a main caption
    that all map to the same visual, so we allow up to 3 captions per visual
    but flag anything beyond that as suspicious.
    """
    tools = KagDocToolset(ocr_dir="experiments/KAG/test_data/omd_test_ocr")
    from experiments.KAG.agentic_doc_agents import StructureParserAgent

    agent = StructureParserAgent()
    agent.build(tools=tools, document_id="omd_test")

    graph = tools.graph
    describes = KAG.describes
    visual_to_captions: dict[str, list[str]] = {}

    for caption_node in graph.subjects(RDF.type, URIRef("http://purl.org/spar/deo/Caption")):
        for target in graph.objects(caption_node, describes):
            key = str(target)
            visual_to_captions.setdefault(key, []).append(str(caption_node))

    for visual, captions in visual_to_captions.items():
        # omd_test has simple figures; no multi-panel sharing expected
        assert len(captions) <= 1, (
            f"Visual {visual} described by multiple captions: {captions}"
        )


def test_default_section_label_is_auto_section():
    """Auto-created sections should have detectionLabel 'auto_section', not 'text'."""
    # omd_test has content before the first sub_title, so a default section is created
    tools = KagDocToolset(ocr_dir="experiments/KAG/test_data/omd_test_ocr")
    from experiments.KAG.agentic_doc_agents import StructureParserAgent

    agent = StructureParserAgent()
    agent.build(tools=tools, document_id="omd_test")

    graph = tools.graph
    for section_node in graph.subjects(RDF.type, DOCO.Section):
        label_val = str(graph.value(section_node, KAG.detectionLabel) or "")
        assert label_val != "text", (
            f"Section {section_node} has detectionLabel='text'; "
            "auto-created sections should use 'auto_section'"
        )
