"""Run 1 entrypoint: DSPy RLM agent for KAG document graph construction."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

if __package__ in {None, ""}:
    sys.path.append(str(Path(__file__).resolve().parents[2]))

from experiments.KAG.rlm_kag_runner import run_rlm_kag, MAIN_MODEL, SUB_MODEL


def main() -> int:
    parser = argparse.ArgumentParser(description="Run KAG DSPy RLM agent experiment.")
    parser.add_argument(
        "--ocr-dir",
        type=str,
        default="experiments/KAG/test_data/chemrxiv_ocr",
        help="Directory containing page_*.md OCR outputs and document.md.",
    )
    parser.add_argument(
        "--out-dir",
        type=str,
        default="experiments/KAG/results",
        help="Output base directory.",
    )
    parser.add_argument(
        "--run-name",
        type=str,
        default="run_kag_1",
        help="Run prefix.",
    )
    parser.add_argument("--model", default=MAIN_MODEL, help="Main LM model.")
    parser.add_argument("--sub-model", default=SUB_MODEL, help="Sub LM model.")
    parser.add_argument("--max-iters", type=int, default=20, help="Max RLM iterations.")
    parser.add_argument("--max-calls", type=int, default=50, help="Max LLM calls.")
    parser.add_argument("--figures-dir", default=None,
        help="Figure PNGs directory (auto-discovered from --ocr-dir if not set).")
    parser.add_argument("--vision-model", default=None,
        help="Vision model for figure description (default: sub-model).")
    parser.add_argument("--enable-figure-indexing", action="store_true",
        help="Enable vision-based figure description indexing.")
    args = parser.parse_args()

    summary = run_rlm_kag(
        ocr_dir=args.ocr_dir,
        out_dir=args.out_dir,
        run_name=args.run_name,
        model=args.model,
        sub_model=args.sub_model,
        max_iters=args.max_iters,
        max_calls=args.max_calls,
        figures_dir=args.figures_dir,
        vision_model=args.vision_model,
        enable_figure_indexing=args.enable_figure_indexing,
    )
    print(json.dumps(summary["artifacts"], indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
