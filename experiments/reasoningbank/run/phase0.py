"""Phase 0: Layer Ablation Experiments (E1-E8).

Tests which layers help:
- E1: Baseline (no layers)
- E2: L0 only (sense card)
- E3: L1 only (schema constraints)
- E4: L3 only (guide summary)
- E5: L2 only (seeded memories)
- E6: Full layer cake (L0+L1+L2+L3)
- E7a/b: Prompt leakage ablation (naive vs handle-based tools)
- E8a/b: Retrieval policy ablation (auto-inject vs tool-mediated)
"""

import sys
sys.path.insert(0, '/Users/cvardema/dev/git/LA3D/rlm')

from pathlib import Path
import json
from experiments.reasoningbank.ctx.builder import Cfg, Layer
from experiments.reasoningbank.run.rlm import run, Result

# Experiment configurations
EXPS = {
    'E1': Cfg(),  # Baseline - no layers
    'E2': Cfg(l0=Layer(True, 600)),  # L0 only (sense card)
    'E3': Cfg(l1=Layer(True, 1000)), # L1 only (constraints)
    'E4': Cfg(l3=Layer(True, 1000)), # L3 only (guide summary)
    'E5': Cfg(l2=Layer(True, 2000)), # L2 only (seeded memories)
    'E6': Cfg(l0=Layer(True,600), l1=Layer(True,1000),
              l2=Layer(True,2000), l3=Layer(True,1000)),  # Full layer cake
}

# E7: Prompt leakage ablation - compare naive vs handle-based tools
# Run separately with different tool implementations:
#   E7a: Naive tools (return full payloads, verbose stdout)
#   E7b: Handle-based tools (Ref pattern, two-phase retrieval)
# Measure: context size per iteration, total iterations, cost, convergence

# E8: Retrieval policy ablation - compare injection modes:
#   E8a: Auto-inject (system retrieves + packs + injects L2)
#   E8b: Tool-mediated (agent calls mem_search/mem_get explicitly)
# Use identical budgets; measure convergence and answer quality

def run_phase0(exps:list[str], tasks:list[dict], ont:str, out:str, verbose:bool=True):
    "Run layer ablation experiments."
    from pathlib import Path
    Path(out).mkdir(parents=True, exist_ok=True)

    results = []
    for exp in exps:
        if exp not in EXPS:
            print(f"Unknown experiment: {exp}")
            continue

        cfg = EXPS[exp]
        print(f"\n{'='*60}")
        print(f"Running {exp}...")
        print(f"{'='*60}")

        for t in tasks:
            print(f"\n[{exp}] Task: {t['id']} - {t['query']}")
            log_path = f"{out}/{exp}_{t['id']}_trajectory.jsonl"

            res = run(t['query'], ont, cfg, verbose=verbose, log_path=log_path)
            print(f"  ✓ Completed: {res.iters} iters, converged={res.converged}")
            results.append({
                'exp': exp, 'task': t['id'],
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
    with open(f"{out}/phase0_results.json", 'w') as f:
        json.dump(results, f, indent=2)

    print(f"\nResults saved to {out}/phase0_results.json")


if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser(description='Run Phase 0 layer ablation experiments')
    parser.add_argument('--exp', default='E1,E2,E3,E4,E5,E6', help='Experiments to run (comma-separated)')
    parser.add_argument('--ont', default='ontology/prov.ttl', help='Ontology path')
    parser.add_argument('--out', default='experiments/reasoningbank/results', help='Output directory')
    args = parser.parse_args()

    # Test tasks
    tasks = [
        {'id': 'entity_lookup', 'query': 'What is Activity?'},
        {'id': 'property_find', 'query': 'What properties does Activity have?'},
        {'id': 'hierarchy', 'query': 'What are the subclasses of Entity?'},
    ]

    exps = args.exp.split(',')
    run_phase0(exps, tasks, args.ont, args.out)
