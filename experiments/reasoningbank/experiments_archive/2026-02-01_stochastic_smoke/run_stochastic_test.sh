#!/bin/bash
# Test script for stochastic UniProt evaluation

# Smoke test (2 tasks, k=2 rollouts)
echo "=== Smoke Test: 2 tasks, k=2 rollouts ==="
python -m experiments.reasoningbank.run.phase1_uniprot \
  --stochastic --stochastic-k 2 --temperature 0.7 \
  --tasks experiments/reasoningbank/test_stochastic_tasks.json \
  --l0 --local \
  --log-dir experiments/reasoningbank/results/stochastic_logs/

echo ""
echo "=== Results saved to: experiments/reasoningbank/results/stochastic_k2_t0.7.json ==="
