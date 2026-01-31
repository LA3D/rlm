"""Phase 1: Closed-Loop Learning with UniProt Remote SPARQL Endpoint.

Applies the same judge → extract → consolidate pipeline as phase1.py,
but uses remote UniProt endpoint instead of local PROV ontology.
"""

import sys
# sys.path.insert(0, '/Users/cvardema/dev/git/LA3D/rlm')  # Not needed when running as module

import dspy
from experiments.reasoningbank.core.mem import MemStore
from experiments.reasoningbank.run.rlm_uniprot import run_uniprot, Result
from experiments.reasoningbank.ctx.builder import Cfg, Layer

# Import judge/extract from phase1.py (ontology-agnostic)
from experiments.reasoningbank.run.phase1 import (
    TrajectoryJudge, SuccessExtractor, FailureExtractor,
    judge, extract, test_judge_extract
)


def run_closed_loop_uniprot(
    tasks: list[dict],
    ont_path: str,
    mem: MemStore,
    cfg: Cfg = None,
    endpoint: str = 'uniprot',
    do_extract: bool = True,
    verbose: bool = False,
    dedup: bool = True,
) -> list[dict]:
    """Run E9-E12 closed-loop learning with UniProt endpoint.

    Flow: for each task → run → judge → extract → consolidate

    Args:
        tasks: List of dicts with 'id' and 'query' keys
        ont_path: Path to UniProt ontology directory (for L0/L1 metadata)
        mem: MemStore instance for procedural memory
        cfg: Layer configuration (defaults to L2-only if None)
        endpoint: SPARQL endpoint name ('uniprot', 'wikidata', etc.)
        do_extract: If True, extract procedures from trajectories
        verbose: If True, print detailed LLM inputs/outputs
        dedup: If True, deduplicate during consolidation (default: True)

    Returns:
        List of result dicts for each task with keys:
        - task_id, query, converged, answer, sparql
        - judgment: {success, reason}
        - items: list of extracted Item objects
    """
    if cfg is None:
        cfg = Cfg(l2=Layer(True, 2000))
    results = []

    for t in tasks:
        print(f"\nTask: {t['id']}")
        res = run_uniprot(t['query'], ont_path, cfg, mem, endpoint=endpoint, verbose=False)

        # Step 1: Judge with task context
        j = judge(res, t['query'], verbose=verbose)
        status = '✓' if j['success'] else '✗'
        print(f"  {status} Judgment: {j['reason'][:60]}")

        # Build result record
        record = {
            'task_id': t['id'],
            'query': t['query'],
            'converged': res.converged,
            'answer': res.answer,
            'sparql': res.sparql,
            'judgment': j,
            'items': [],
        }

        # Step 2-3: Extract and consolidate
        if do_extract:
            items = extract(res, t['query'], j, verbose=verbose)
            if items:
                added_ids = mem.consolidate(items, dedup=dedup)
                record['items'] = items
                for item in items:
                    polarity = f"[{item.src}]"
                    print(f"  {polarity} Extracted: {item.title[:50]}")

        results.append(record)

    return results


if __name__ == '__main__':
    import argparse
    import json
    from pathlib import Path

    parser = argparse.ArgumentParser(description='Run Phase 1 closed-loop experiments with UniProt')
    parser.add_argument('--ont', default='ontology/uniprot', help='UniProt ontology directory path')
    parser.add_argument('--endpoint', default='uniprot', help='SPARQL endpoint name')
    parser.add_argument('--tasks', default='experiments/reasoningbank/uniprot_test_tasks.json',
                        help='Path to task definitions JSON')
    parser.add_argument('--extract', action='store_true', help='Enable extraction')
    parser.add_argument('--verbose', '-v', action='store_true', help='Verbose output')
    parser.add_argument('--test', action='store_true', help='Run mock test (no RLM calls)')

    # Layer configuration
    parser.add_argument('--l0', action='store_true', help='Enable L0 sense card (~600 chars)')
    parser.add_argument('--l1', action='store_true', help='Enable L1 schema constraints (~1000 chars)')
    parser.add_argument('--l3', action='store_true', help='Enable L3 guide summary (~1000 chars)')

    # Memory persistence
    parser.add_argument('--load-mem', metavar='FILE', help='Load memory from JSON file')
    parser.add_argument('--save-mem', metavar='FILE', help='Save memory to JSON file')

    # MaTTS options
    parser.add_argument('--matts', action='store_true', help='Enable MaTTS parallel scaling')
    parser.add_argument('--matts-k', type=int, default=3, help='Number of MaTTS rollouts (default: 3)')

    # Deduplication control
    parser.add_argument('--no-dedup', action='store_true', help='Disable deduplication during consolidation')

    args = parser.parse_args()

    if args.test:
        # Test judge/extract with mock data (cheap, no RLM)
        test_judge_extract(verbose=args.verbose)
    else:
        # Initialize memory
        mem = MemStore()

        # Load existing memory if specified
        if args.load_mem:
            mem.load(args.load_mem)
            print(f"Loaded {len(mem.all())} items from {args.load_mem}")

        # Build layer configuration from CLI args
        cfg = Cfg(
            l0=Layer(args.l0, 600),
            l1=Layer(args.l1, 1000),
            l2=Layer(True, 2000),  # Always on for memory retrieval
            l3=Layer(args.l3, 1000),
        )

        # Show active layers
        active = []
        if cfg.l0.on: active.append('L0:sense')
        if cfg.l1.on: active.append('L1:schema')
        if cfg.l2.on: active.append('L2:memory')
        if cfg.l3.on: active.append('L3:guide')
        print(f"Active layers: {', '.join(active) if active else 'L2:memory (default)'}")
        print(f"Endpoint: {args.endpoint}")

        # Dedup flag
        dedup = not args.no_dedup
        if not dedup:
            print("Deduplication: DISABLED")

        # Load tasks
        with open(args.tasks) as f:
            tasks = json.load(f)
        print(f"Loaded {len(tasks)} tasks from {args.tasks}")

        if args.matts:
            # MaTTS mode: import and use from phase1
            from experiments.reasoningbank.run.phase1 import run_matts_parallel
            from experiments.reasoningbank.run.rlm_uniprot import run_uniprot

            print(f"MaTTS mode: {args.matts_k} rollouts per task")
            print("Note: MaTTS for UniProt uses local ontology runner")

            results = []
            for t in tasks:
                print(f"\nTask: {t['id']}")
                # MaTTS uses local ontology path - for UniProt, use the ontology dir
                res, items = run_matts_parallel(
                    t['query'], args.ont, mem, cfg,
                    k=args.matts_k, verbose=args.verbose, dedup=dedup
                )
                status = '✓' if res.converged else '✗'
                print(f"  {status} Answer: {res.answer[:80]}...")
                for item in items:
                    print(f"  [{item.src}] Extracted: {item.title[:50]}")
                results.append({
                    'task_id': t['id'],
                    'query': t['query'],
                    'converged': res.converged,
                    'answer': res.answer,
                    'sparql': res.sparql,
                    'items': items,
                })
        else:
            # Standard closed-loop mode
            results = run_closed_loop_uniprot(
                tasks, args.ont, mem, cfg,
                endpoint=args.endpoint,
                do_extract=args.extract,
                verbose=args.verbose,
                dedup=dedup
            )

        # Save memory if specified
        save_path = args.save_mem or (
            'experiments/reasoningbank/results/phase1_uniprot_memory.json'
            if args.extract or args.matts else None
        )
        if save_path:
            mem.save(save_path)
            print(f"\nMemory saved: {len(mem.all())} items → {save_path}")

        # Print summary
        print(f"\n=== Results Summary ===")
        for r in results:
            status = '✓' if r.get('judgment', {}).get('success', r.get('converged', False)) else '✗'
            print(f"{status} {r['task_id']}: {len(r['items'])} items extracted")
