from pathlib import Path

from experiments.KAG.agentic_kag_runner import run_pipeline


def test_run0_keeps_returns_bounded(tmp_path: Path):
    summary = run_pipeline(
        ocr_dir="experiments/KAG/test_data/pet_test_ocr",
        out_dir=str(tmp_path),
        run_name="test_rlm",
    )
    assert summary["leakage"]["stdout_chars"] == 0
    assert summary["leakage"]["large_returns"] == 0
    assert summary["validation"]["conforms"] is True


def test_run0_semantic_correctness(tmp_path: Path):
    """Baseline should produce semantically correct caption→visual links."""
    summary = run_pipeline(
        ocr_dir="experiments/KAG/test_data/pet_test_ocr",
        out_dir=str(tmp_path),
        run_name="test_semantic",
    )
    assert summary["validation"]["conforms"] is True
    assert summary["graph_stats"]["triples"] > 0
    # Captions should be present
    assert summary["parse_result"]["node_counts"].get("caption", 0) > 0
