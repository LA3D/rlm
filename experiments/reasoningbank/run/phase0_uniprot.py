"""Phase 0: Layer Ablation Experiments with UniProt Remote SPARQL Endpoint.

Tests same layers as phase0.py but with remote UniProt endpoint:
- E1: Baseline (no layers)
- E2: L0 only (UniProt sense card)
- E3: L1 only (schema constraints)
- E4: L3 only (guide summary)
- E5: L2 only (seeded memories)
- E6: Full layer cake (L0+L1+L2+L3)

Key differences from phase0.py:
1. Uses SPARQLTools for remote endpoint instead of local graph
2. Loads tasks from SHACL examples via shacl_tasks.py
3. Uses endpoint-specific context builder
"""

import sys
sys.path.insert(0, '/Users/cvardema/dev/git/LA3D/rlm')

from pathlib import Path
import json
from experiments.reasoningbank.ctx.builder import Cfg, Layer
from experiments.reasoningbank.run.rlm_uniprot import run_uniprot, Result

# Same experiment configurations as phase0.py
EXPS = {
    'E1': Cfg(),  # Baseline - no layers
    'E2': Cfg(l0=Layer(True, 600)),  # L0 only (sense card)
    'E3': Cfg(l1=Layer(True, 1000)), # L1 only (constraints)
    'E4': Cfg(l3=Layer(True, 1000)), # L3 only (guide summary)
    'E5': Cfg(l2=Layer(True, 2000)), # L2 only (seeded memories)
    'E6': Cfg(l0=Layer(True,600), l1=Layer(True,1000),
              l2=Layer(True,2000), l3=Layer(True,1000)),  # Full layer cake
}

def run_phase0_uniprot(exps:list[str], tasks:list[dict], ont_path:str, out:str, verbose:bool=True,
                       use_local_interpreter:bool=False):
    """Run layer ablation experiments with UniProt remote endpoint.

    Args:
        exps: List of experiment names (E1-E6)
        tasks: List of task dicts with 'id' and 'query' keys
        ont_path: Path to UniProt ontology directory (for L0/L1 metadata)
        out: Output directory for results
        verbose: Print progress messages
        use_local_interpreter: If True, use LocalPythonInterpreter instead of Deno sandbox
    """
    from pathlib import Path
    from experiments.reasoningbank.core.mem import MemStore
    Path(out).mkdir(parents=True, exist_ok=True)

    # Load seed memory for E5 and E6
    mem = MemStore()
    seed_path = 'experiments/reasoningbank/seed/strategies.json'
    if Path(seed_path).exists():
        mem.load(seed_path)
        print(f"Loaded {len(mem.all())} seed strategies from {seed_path}")
    else:
        print(f"Warning: Seed strategies not found at {seed_path}")

    results = []
    for exp in exps:
        if exp not in EXPS:
            print(f"Unknown experiment: {exp}")
            continue

        cfg = EXPS[exp]
        print(f"\n{'='*60}")
        print(f"Running {exp} with UniProt remote endpoint...")
        print(f"{'='*60}")

        for t in tasks:
            print(f"\n[{exp}] Task: {t['id']} - {t['query'][:80]}")
            log_path = f"{out}/{exp}_{t['id']}_trajectory.jsonl"

            # Pass memory for E5 and E6 (experiments with L2 enabled)
            exp_mem = mem if cfg.l2.on else None
            res = run_uniprot(t['query'], ont_path, cfg, mem=exp_mem, verbose=verbose, log_path=log_path,
                              use_local_interpreter=use_local_interpreter)
            print(f"  ✓ Completed: {res.iters} iters, converged={res.converged}")
            results.append({
                'exp': exp, 'task': t['id'],
                'query': t['query'],
                'converged': res.converged, 'iters': res.iters,
                'answer': res.answer, 'sparql': res.sparql,
                'leakage': {
                    'stdout_chars': res.leakage.stdout_chars,
                    'large_returns': res.leakage.large_returns,
                    'subcalls': res.leakage.subcalls,
                    'vars_n': res.leakage.vars_n,
                },
            })
            status = '✓' if res.converged else '✗'
            print(f"  {status} {t['id']}: {res.iters} iters, {res.leakage.large_returns} large returns")

    # Save results
    Path(out).mkdir(parents=True, exist_ok=True)
    with open(f"{out}/phase0_uniprot_results.json", 'w') as f:
        json.dump(results, f, indent=2)

    print(f"\nResults saved to {out}/phase0_uniprot_results.json")


if __name__ == '__main__':
    import argparse

    parser = argparse.ArgumentParser(description='Run Phase 0 layer ablation with UniProt')
    parser.add_argument('--exp', default='E1,E2,E3,E4,E5,E6', help='Experiments to run (comma-separated)')
    parser.add_argument('--ont', default='ontology/uniprot', help='UniProt ontology directory')
    parser.add_argument('--out', default='experiments/reasoningbank/results_uniprot', help='Output directory')
    parser.add_argument('--tasks-file', default='experiments/reasoningbank/uniprot_test_tasks.json',
                        help='JSON file with test tasks')
    parser.add_argument('--local', action='store_true',
                        help='Use LocalPythonInterpreter instead of Deno sandbox')
    args = parser.parse_args()

    # Load test tasks (custom questions analogous to PROV experiments)
    print(f"Loading tasks from {args.tasks_file}...")
    with open(args.tasks_file) as f:
        tasks = json.load(f)

    if not tasks:
        print("No tasks found! Check tasks file.")
        sys.exit(1)

    print(f"Selected {len(tasks)} tasks (analogous to PROV experiments):")
    for t in tasks:
        print(f"  - {t['id']}: {t['query']}")
        print(f"    ({t['description']})")

    exps = args.exp.split(',')
    if args.local:
        print("Interpreter: LocalPythonInterpreter (no Deno sandbox)")
    run_phase0_uniprot(exps, tasks, args.ont, args.out, use_local_interpreter=args.local)
