"""Run 0 baseline entrypoint for KAG experiments."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

if __package__ in {None, ""}:
    sys.path.append(str(Path(__file__).resolve().parents[2]))

from experiments.KAG.agentic_kag_runner import run_pipeline


def main() -> int:
    parser = argparse.ArgumentParser(description="Run KAG baseline StructureParser experiment.")
    parser.add_argument(
        "--ocr-dir",
        type=str,
        default="experiments/KAG/test_data/chemrxiv_ocr",
        help="OCR directory with page_*.md files.",
    )
    parser.add_argument(
        "--out-dir",
        type=str,
        default="experiments/KAG/results",
        help="Output base directory.",
    )
    args = parser.parse_args()

    summary = run_pipeline(ocr_dir=args.ocr_dir, out_dir=args.out_dir, run_name="run_kag_0")
    print(json.dumps(summary, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
