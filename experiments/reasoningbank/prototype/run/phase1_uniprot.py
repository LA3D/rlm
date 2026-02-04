"""Phase 1: Closed-Loop Learning with UniProt Remote SPARQL Endpoint.

Applies the same judge → extract → consolidate pipeline as phase1.py,
but uses remote UniProt endpoint instead of local PROV ontology.

Includes stochastic evaluation infrastructure with:
- Pass@1, Best-of-N, Pass@k metrics
- Trajectory diversity metrics (Vendi Score, Jaccard, edit distance)
- Prompt perturbation strategies for trajectory diversity
"""

import sys
# sys.path.insert(0, '/Users/cvardema/dev/git/LA3D/rlm')  # Not needed when running as module

import dspy
import random
from experiments.reasoningbank.core.mem import MemStore
from experiments.reasoningbank.run.rlm_uniprot import run_uniprot, Result
from experiments.reasoningbank.ctx.builder import Cfg, Layer

# Import judge/extract from phase1.py (ontology-agnostic)
from experiments.reasoningbank.run.phase1 import (
    TrajectoryJudge, SuccessExtractor, FailureExtractor,
    judge, extract, test_judge_extract
)


# =============================================================================
# Prompt Perturbation Strategies
# =============================================================================

THINKING_PROMPTS = [
    "Think step by step.",
    "Consider multiple approaches before deciding.",
    "Be thorough in your exploration.",
    "Try a different strategy than usual.",
    "Focus on the key constraints first.",
]


def perturb_query(query: str, rollout_id: int, strategy: str = 'none') -> str:
    """Apply perturbation strategy to query for trajectory diversity.

    Changing the INPUT rather than just the sampling creates different
    initial conditions, analogous to perturbing starting positions in MD.

    Args:
        query: Original query string
        rollout_id: Rollout number (0-indexed)
        strategy: Perturbation strategy:
            - 'none': Return original query unchanged
            - 'prefix': Add rollout attempt marker
            - 'thinking': Add different thinking prompt per rollout
            - 'shuffle': Randomly shuffle query words (not recommended for natural language)

    Returns:
        Perturbed query string
    """
    if strategy == 'none':
        return query
    elif strategy == 'prefix':
        return f"[Attempt {rollout_id + 1}] {query}"
    elif strategy == 'thinking':
        prompt = THINKING_PROMPTS[rollout_id % len(THINKING_PROMPTS)]
        return f"{prompt} {query}"
    elif strategy == 'rephrase':
        # Could use LLM to rephrase, but for now just add variety via prefix
        rephrases = [
            query,
            f"I need to find out: {query}",
            f"Help me answer: {query}",
            f"Query: {query}",
            f"Please determine: {query}",
        ]
        return rephrases[rollout_id % len(rephrases)]
    else:
        return query


def run_closed_loop_uniprot(
    tasks: list[dict],
    ont_path: str,
    mem: MemStore,
    cfg: Cfg = None,
    endpoint: str = 'uniprot',
    do_extract: bool = True,
    verbose: bool = False,
    dedup: bool = True,
    log_dir: str = None,
    use_local_interpreter: bool = False,
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
        log_dir: Directory for trajectory logs (creates {task_id}.jsonl files)
        use_local_interpreter: If True, use LocalPythonInterpreter instead of Deno sandbox

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
        log_path = f"{log_dir}/{t['id']}.jsonl" if log_dir else None
        res = run_uniprot(t['query'], ont_path, cfg, mem, endpoint=endpoint, verbose=False,
                         log_path=log_path, use_local_interpreter=use_local_interpreter)

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


def compute_stochastic_metrics(rollouts: list[dict]) -> dict:
    """Compute Pass@1, Best-of-N, Pass@k from rollout results.

    Args:
        rollouts: List of rollout dicts with 'judgment' key

    Returns:
        Metrics dict with pass_1, best_of_n, pass_k, n_success, n_total
    """
    judgments = [r['judgment']['success'] for r in rollouts]
    n_success = sum(judgments)
    n_total = len(judgments)

    return {
        'pass_1': judgments[0] if judgments else False,  # First rollout
        'best_of_n': any(judgments),  # At least one success
        'pass_k': n_success / n_total if n_total > 0 else 0.0,  # Fraction
        'n_success': n_success,
        'n_total': n_total,
    }


def run_stochastic_uniprot(
    task: dict,
    ont_path: str,
    cfg: Cfg,
    mem: MemStore,
    k: int = 5,
    temperature: float = 0.7,
    endpoint: str = 'uniprot',
    verbose: bool = False,
    log_dir: str = None,
    use_local_interpreter: bool = False,
    perturb: str = 'none',
    use_seed: bool = False,
    compute_diversity: bool = False,
) -> dict:
    """Run k stochastic rollouts for a single task.

    Args:
        task: Task dict with 'id' and 'query' keys
        ont_path: Path to UniProt ontology directory
        cfg: Layer configuration
        mem: Memory store (for L2)
        k: Number of rollouts per task
        temperature: LLM temperature for rollouts
        endpoint: SPARQL endpoint name
        verbose: Print detailed output
        log_dir: Directory for trajectory logs
        use_local_interpreter: Use LocalPythonInterpreter instead of Deno
        perturb: Perturbation strategy ('none', 'prefix', 'thinking', 'rephrase')
        use_seed: Use explicit different seeds per rollout
        compute_diversity: Compute trajectory diversity metrics

    Returns:
        dict with keys:
        - task_id, query
        - rollouts: list of {converged, answer, sparql, judgment, iters, log_path}
        - metrics: {pass_1, best_of_n, pass_k, n_success, n_total}
        - diversity: {sparql_vendi, trajectory_vendi, ...} (if compute_diversity=True)
    """
    print(f"\nTask: {task['id']} ({k} rollouts)")
    if perturb != 'none':
        print(f"  Perturbation: {perturb}")
    if use_seed:
        print(f"  Using explicit seeds per rollout")

    rollouts = []

    for i in range(k):
        print(f"  Rollout {i+1}/{k}...", end='', flush=True)

        # Create log path for this rollout
        log_path = f"{log_dir}/{task['id']}_rollout{i+1}.jsonl" if log_dir else None

        # Apply perturbation to query
        perturbed_query = perturb_query(task['query'], i, strategy=perturb)

        # Determine seed for this rollout
        seed = (i + 1) * 42 if use_seed else None  # Use deterministic seed based on rollout id

        # Run with temperature and optional seed
        # Pass rollout_id to prevent prompt caching (makes each prompt unique)
        res = run_uniprot(
            perturbed_query, ont_path, cfg, mem,
            endpoint=endpoint,
            temperature=temperature,
            seed=seed,
            verbose=False,
            log_path=log_path,
            use_local_interpreter=use_local_interpreter,
            rollout_id=i  # Unique ID prevents caching
        )

        # Judge with deterministic temperature (temperature=0.0 is default for judge)
        j = judge(res, task['query'], verbose=False)  # Use original query for judging

        status = '✓' if j['success'] else '✗'
        print(f" {status}")

        # Record rollout
        rollouts.append({
            'rollout_id': i + 1,
            'converged': res.converged,
            'answer': res.answer,
            'sparql': res.sparql,
            'judgment': j,
            'iters': res.iters,
            'log_path': log_path,
            'perturbed_query': perturbed_query if perturb != 'none' else None,
            'seed': seed,
        })

    # Compute stochastic metrics
    metrics = compute_stochastic_metrics(rollouts)

    # Print summary
    print(f"  Metrics: Pass@1={metrics['pass_1']}, Best-of-N={metrics['best_of_n']}, Pass@k={metrics['pass_k']:.2f} ({metrics['n_success']}/{metrics['n_total']})")

    result = {
        'task_id': task['id'],
        'query': task['query'],
        'rollouts': rollouts,
        'metrics': metrics,
    }

    # Compute diversity metrics if requested
    if compute_diversity and log_dir:
        try:
            from experiments.reasoningbank.metrics.diversity import (
                compute_diversity_report,
                load_trajectory,
            )

            # Load trajectories from log files
            trajectories = []
            queries = []
            for rollout in rollouts:
                if rollout.get('log_path'):
                    try:
                        traj = load_trajectory(rollout['log_path'])
                        trajectories.append(traj)
                    except Exception as e:
                        if verbose:
                            print(f"    Warning: Could not load trajectory: {e}")
                        trajectories.append([])
                if rollout.get('sparql'):
                    queries.append(rollout['sparql'])

            # Compute diversity report
            if len(trajectories) >= 2:
                report = compute_diversity_report(trajectories, queries=queries)
                result['diversity'] = report.to_dict()
                print(f"  Diversity: Vendi={report.trajectory_vendi_score:.2f}, "
                      f"Jaccard={report.mean_pairwise_jaccard:.2f}, "
                      f"Efficiency={report.sampling_efficiency:.1%}")

        except ImportError as e:
            if verbose:
                print(f"  Warning: Could not compute diversity metrics: {e}")
        except Exception as e:
            if verbose:
                print(f"  Warning: Diversity computation failed: {e}")

    return result


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

    # Stochastic evaluation options
    parser.add_argument('--stochastic', action='store_true', help='Run stochastic evaluation (k rollouts per task)')
    parser.add_argument('--stochastic-k', type=int, default=5, help='Number of rollouts per task (default: 5)')
    parser.add_argument('--temperature', type=float, default=0.7, help='Temperature for stochastic rollouts (default: 0.7)')

    # Trajectory diversity options
    parser.add_argument('--perturb', choices=['none', 'prefix', 'thinking', 'rephrase'],
                        default='none', help='Prompt perturbation strategy for trajectory diversity')
    parser.add_argument('--use-seed', action='store_true',
                        help='Use explicit different seeds per rollout (Anthropic beta support)')
    parser.add_argument('--compute-diversity', action='store_true',
                        help='Compute trajectory diversity metrics (requires sentence-transformers, vendi-score)')

    # Deduplication control
    parser.add_argument('--no-dedup', action='store_true', help='Disable deduplication during consolidation')

    # Logging
    parser.add_argument('--log-dir', metavar='DIR', help='Directory for trajectory logs (creates {task_id}.jsonl files)')

    # Interpreter
    parser.add_argument('--local', action='store_true',
                        help='Use LocalPythonInterpreter instead of Deno sandbox (avoids sandbox corruption)')

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
        if args.local:
            print("Interpreter: LocalPythonInterpreter (no Deno sandbox)")

        # Dedup flag
        dedup = not args.no_dedup
        if not dedup:
            print("Deduplication: DISABLED")

        # Create log directory if specified
        log_dir = args.log_dir
        if log_dir:
            import os
            os.makedirs(log_dir, exist_ok=True)
            print(f"Logging trajectories to: {log_dir}/")

        # Load tasks
        with open(args.tasks) as f:
            tasks = json.load(f)
        print(f"Loaded {len(tasks)} tasks from {args.tasks}")

        if args.stochastic:
            # Stochastic evaluation mode
            print(f"Stochastic mode: {args.stochastic_k} rollouts per task, temperature={args.temperature}")
            if args.perturb != 'none':
                print(f"Perturbation strategy: {args.perturb}")
            if args.use_seed:
                print("Using explicit seeds per rollout")
            if args.compute_diversity:
                print("Trajectory diversity metrics: ENABLED")

            results = []
            for task in tasks:
                result = run_stochastic_uniprot(
                    task, args.ont, cfg, mem,
                    k=args.stochastic_k,
                    temperature=args.temperature,
                    endpoint=args.endpoint,
                    verbose=args.verbose,
                    log_dir=log_dir,
                    use_local_interpreter=args.local,
                    perturb=args.perturb,
                    use_seed=args.use_seed,
                    compute_diversity=args.compute_diversity,
                )
                results.append(result)

            # Compute aggregate metrics
            all_metrics = [r['metrics'] for r in results]
            aggregate = {
                'mean_pass_1': sum(m['pass_1'] for m in all_metrics) / len(all_metrics),
                'mean_best_of_n': sum(m['best_of_n'] for m in all_metrics) / len(all_metrics),
                'mean_pass_k': sum(m['pass_k'] for m in all_metrics) / len(all_metrics),
                'tasks_with_any_success': sum(m['best_of_n'] for m in all_metrics),
                'total_tasks': len(tasks),
            }

            # Compute aggregate diversity metrics if available
            diversity_results = [r.get('diversity') for r in results if r.get('diversity')]
            if diversity_results:
                aggregate['diversity'] = {
                    'mean_sparql_vendi': sum(d['sparql_vendi_score'] for d in diversity_results) / len(diversity_results),
                    'mean_trajectory_vendi': sum(d['trajectory_vendi_score'] for d in diversity_results) / len(diversity_results),
                    'mean_sampling_efficiency': sum(d['sampling_efficiency'] for d in diversity_results) / len(diversity_results),
                    'mean_pairwise_jaccard': sum(d['mean_pairwise_jaccard'] for d in diversity_results) / len(diversity_results),
                    'tasks_with_diversity_data': len(diversity_results),
                }

            # Save results
            import os
            from datetime import datetime
            output = {
                'experiment': {
                    'type': 'stochastic',
                    'k': args.stochastic_k,
                    'temperature': args.temperature,
                    'perturb': args.perturb,
                    'use_seed': args.use_seed,
                    'compute_diversity': args.compute_diversity,
                    'timestamp': datetime.now().isoformat(),
                    'config': {
                        'endpoint': args.endpoint,
                        'ontology': args.ont,
                        'layers': {
                            'l0': cfg.l0.on,
                            'l1': cfg.l1.on,
                            'l2': cfg.l2.on,
                            'l3': cfg.l3.on,
                        }
                    }
                },
                'tasks': results,
                'aggregate_metrics': aggregate,
            }

            # Save to results directory
            results_dir = 'experiments/reasoningbank/results'
            os.makedirs(results_dir, exist_ok=True)
            output_path = f"{results_dir}/stochastic_k{args.stochastic_k}_t{args.temperature}.json"
            with open(output_path, 'w') as f:
                json.dump(output, f, indent=2)

            print(f"\n=== Aggregate Metrics ===")
            print(f"Mean Pass@1: {aggregate['mean_pass_1']:.3f}")
            print(f"Mean Best-of-N: {aggregate['mean_best_of_n']:.3f}")
            print(f"Mean Pass@k: {aggregate['mean_pass_k']:.3f}")
            print(f"Tasks with any success: {aggregate['tasks_with_any_success']}/{aggregate['total_tasks']}")

            if 'diversity' in aggregate:
                print(f"\n=== Aggregate Diversity ===")
                print(f"Mean SPARQL Vendi Score: {aggregate['diversity']['mean_sparql_vendi']:.2f}")
                print(f"Mean Trajectory Vendi Score: {aggregate['diversity']['mean_trajectory_vendi']:.2f}")
                print(f"Mean Sampling Efficiency: {aggregate['diversity']['mean_sampling_efficiency']:.1%}")
                print(f"Tasks with diversity data: {aggregate['diversity']['tasks_with_diversity_data']}")

            print(f"\nResults saved to: {output_path}")

        elif args.matts:
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
                dedup=dedup,
                log_dir=log_dir,
                use_local_interpreter=args.local
            )

        # Save memory if specified (not needed for stochastic mode)
        if not args.stochastic:
            save_path = args.save_mem or (
                'experiments/reasoningbank/results/phase1_uniprot_memory.json'
                if args.extract or args.matts else None
            )
            if save_path:
                mem.save(save_path)
                print(f"\nMemory saved: {len(mem.all())} items → {save_path}")

        # Print summary (different for stochastic vs standard mode)
        if not args.stochastic:
            print(f"\n=== Results Summary ===")
            for r in results:
                status = '✓' if r.get('judgment', {}).get('success', r.get('converged', False)) else '✗'
                print(f"{status} {r['task_id']}: {len(r['items'])} items extracted")
