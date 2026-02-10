"""CLI entrypoint for KAG entity extraction.

Usage:
    python experiments/KAG/run_kag_entity.py \
      --graph-dir experiments/KAG/results/sprint4b_chemrxiv_20260210T152308Z \
      --out-dir experiments/KAG/results
"""

from __future__ import annotations

import argparse
import json
import sys

sys.path.insert(0, ".")

from experiments.KAG.rlm_kag_entity_runner import run_rlm_kag_entity


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Run KAG entity extraction over an enriched document graph."
    )
    parser.add_argument(
        "--graph-dir",
        required=True,
        help="Directory containing knowledge_graph.ttl + content_store.jsonl",
    )
    parser.add_argument(
        "--out-dir",
        default="experiments/KAG/results",
        help="Output directory for results (default: experiments/KAG/results)",
    )
    parser.add_argument(
        "--run-name",
        default="kag_entity",
        help="Run name prefix (default: kag_entity)",
    )
    parser.add_argument(
        "--model",
        default="anthropic/claude-sonnet-4-5-20250929",
        help="Main LLM model",
    )
    parser.add_argument(
        "--sub-model",
        default="anthropic/claude-haiku-4-5-20251001",
        help="Sub LLM for code execution",
    )
    parser.add_argument(
        "--max-iters",
        type=int,
        default=20,
        help="Max RLM iterations (default: 20)",
    )
    parser.add_argument(
        "--max-calls",
        type=int,
        default=50,
        help="Max LLM calls (default: 50)",
    )
    args = parser.parse_args()

    summary = run_rlm_kag_entity(
        graph_dir=args.graph_dir,
        out_dir=args.out_dir,
        run_name=args.run_name,
        model=args.model,
        sub_model=args.sub_model,
        max_iters=args.max_iters,
        max_calls=args.max_calls,
    )

    conforms = summary.get("validation", {}).get("conforms", False)
    stats = summary.get("stats", {})
    entity_triples = stats.get("entity", {}).get("triples", 0)
    claim_triples = stats.get("claim", {}).get("triples", 0)
    cost = summary.get("lm_usage", {}).get("total_cost", 0.0)
    iters = summary.get("iterations", 0)

    print(f"\n{'='*60}")
    print(f"Entity extraction complete:")
    print(f"  Conforms: {conforms}")
    print(f"  G_entity: {entity_triples} triples")
    print(f"  G_claim:  {claim_triples} triples")
    print(f"  Iterations: {iters}")
    print(f"  Cost: ${cost:.3f}")
    print(f"  Output: {summary.get('out_dir', '')}")
    print(f"{'='*60}")


if __name__ == "__main__":
    main()
