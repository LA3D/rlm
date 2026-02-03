# Stochastic Evaluation Quick Start

## Run Smoke Test (2 tasks, k=2)

```bash
./experiments/reasoningbank/run_stochastic_test.sh
```

Expected output:
- 4 total runs (2 tasks × 2 rollouts)
- Per-task metrics during execution
- Aggregate metrics at end
- Results saved to `experiments/reasoningbank/results/stochastic_k2_t0.7.json`

## Run Full Evaluation (10 tasks, k=5)

```bash
python -m experiments.reasoningbank.run.phase1_uniprot \
  --stochastic --stochastic-k 5 --temperature 0.7 \
  --tasks experiments/reasoningbank/uniprot_subset_tasks.json \
  --l0 --local \
  --log-dir experiments/reasoningbank/results/stochastic_logs/
```

Expected output:
- 50 total runs (10 tasks × 5 rollouts)
- Aggregate metrics: mean_pass_1, mean_best_of_n, mean_pass_k
- Results saved to `experiments/reasoningbank/results/stochastic_k5_t0.7.json`

## Analyze Results

```bash
# View aggregate metrics
python -c "
import json
with open('experiments/reasoningbank/results/stochastic_k5_t0.7.json') as f:
    data = json.load(f)
    agg = data['aggregate_metrics']
    print(f'Pass@1: {agg[\"mean_pass_1\"]:.3f}')
    print(f'Best-of-N: {agg[\"mean_best_of_n\"]:.3f}')
    print(f'Pass@k: {agg[\"mean_pass_k\"]:.3f}')
    print(f'Tasks with success: {agg[\"tasks_with_any_success\"]}/{agg[\"total_tasks\"]}')
"

# Find difficult tasks (pass_k < 0.5)
python -c "
import json
with open('experiments/reasoningbank/results/stochastic_k5_t0.7.json') as f:
    data = json.load(f)
    difficult = [t for t in data['tasks'] if t['metrics']['pass_k'] < 0.5]
    print('Difficult tasks (pass_k < 0.5):')
    for t in difficult:
        print(f'  {t[\"task_id\"]}: pass_k={t[\"metrics\"][\"pass_k\"]:.2f}')
"
```

## Files

- **Documentation**: `experiments/reasoningbank/STOCHASTIC_EVALUATION.md`
- **Implementation**: `experiments/reasoningbank/IMPLEMENTATION_SUMMARY.md`
- **Test tasks**: `experiments/reasoningbank/test_stochastic_tasks.json`
- **Full tasks**: `experiments/reasoningbank/uniprot_subset_tasks.json`

## Key Metrics

- **Pass@1**: First rollout success rate (baseline)
- **Best-of-N**: At least one success rate (upper bound)
- **Pass@k**: Average success rate (expected performance)

If Best-of-N >> Pass@1, MaTTS selection is valuable.
