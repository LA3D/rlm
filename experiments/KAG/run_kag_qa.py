#!/usr/bin/env python
"""CLI for KAG QA agent: answer competency questions over enriched graphs."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

if __package__ in {None, ""}:
    sys.path.append(str(Path(__file__).resolve().parents[2]))


def main() -> None:
    parser = argparse.ArgumentParser(description="KAG QA Agent — answer questions over enriched document graphs")
    parser.add_argument("--graph-dir", required=True, help="Path to sprint4 result dir (has knowledge_graph.ttl + content_store.jsonl)")
    parser.add_argument("--questions", required=True, help="Path to kag_qa_tasks.json")
    parser.add_argument("--paper", default=None, help="Filter questions to this paper (chemrxiv or pet)")
    parser.add_argument("--max-iters", type=int, default=10, help="Per-question iteration budget (default: 10)")
    parser.add_argument("--max-calls", type=int, default=30, help="Per-question LLM call budget (default: 30)")
    parser.add_argument("--out-dir", default="experiments/KAG/results", help="Output directory")
    parser.add_argument("--run-name", default="kag_qa", help="Run name prefix")
    parser.add_argument("--model", default=None, help="Main model (default: claude-sonnet-4-5)")
    parser.add_argument("--sub-model", default=None, help="Sub model for code execution (default: claude-haiku-4-5)")
    args = parser.parse_args()

    # Import here to avoid slow imports during --help
    from experiments.KAG.rlm_kag_qa_runner import MAIN_MODEL, SUB_MODEL, run_rlm_kag_qa

    kwargs: dict = {
        "graph_dir": args.graph_dir,
        "questions_path": args.questions,
        "paper": args.paper,
        "out_dir": args.out_dir,
        "run_name": args.run_name,
        "max_iters": args.max_iters,
        "max_calls": args.max_calls,
    }
    if args.model:
        kwargs["model"] = args.model
    if args.sub_model:
        kwargs["sub_model"] = args.sub_model

    summary = run_rlm_kag_qa(**kwargs)
    print(f"\nSummary: {summary['questions_answered']} questions, ${summary['total_cost']:.3f}")


if __name__ == "__main__":
    main()
