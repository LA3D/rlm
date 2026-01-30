"""Minimal E1 test - single task with debug output."""

import sys
sys.path.insert(0, '/Users/cvardema/dev/git/LA3D/rlm')

print("Imports...")
from experiments.reasoningbank.run.rlm import run
from experiments.reasoningbank.ctx.builder import Cfg

print("Running task...")
result = run(
    task="What is Activity?",
    graph_path="ontology/prov.ttl",
    cfg=Cfg(),  # Baseline - no layers
    max_iters=3,
    max_calls=10,
)

print(f"\nResult:")
print(f"  Converged: {result.converged}")
print(f"  Iterations: {result.iters}")
print(f"  Answer: {result.answer[:200]}...")
print(f"  SPARQL: {result.sparql}")
print(f"  Leakage: {result.leakage}")
