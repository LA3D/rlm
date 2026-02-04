# Stochastic UniProt Evaluation for MaTTS

## Overview

This module implements stochastic evaluation for UniProt queries, computing Pass@1, Best-of-N, and Pass@k metrics to inform Memory-aware Test-Time Scaling (MaTTS) design decisions.

## Motivation

The ReasoningBank paper uses MaTTS:
- Run k parallel trajectories with temperature=0.7
- Judge each trajectory deterministically (temperature=0.0)
- Use contrastive extraction (success vs failure) for better memories
- Compute stochastic metrics: Pass@1, Best-of-N, Pass@k

This implementation enables evidence-based decisions about memory system design.

## Usage

### Basic Command

```bash
python -m experiments.reasoningbank.run.phase1_uniprot \
  --stochastic \
  --stochastic-k 5 \
  --temperature 0.7 \
  --tasks experiments/reasoningbank/uniprot_subset_tasks.json \
  --l0 --local
```

### Parameters

- `--stochastic`: Enable stochastic evaluation mode
- `--stochastic-k N`: Number of rollouts per task (default: 5)
- `--temperature T`: Temperature for LLM rollouts (default: 0.7)
- `--tasks FILE`: Path to task definitions JSON
- `--l0`: Enable L0 sense card layer
- `--l1`: Enable L1 schema constraints layer
- `--local`: Use LocalPythonInterpreter (avoids Deno sandbox issues)
- `--log-dir DIR`: Directory for trajectory logs

### Example: Smoke Test

Run 2 tasks with k=2 rollouts:

```bash
./experiments/reasoningbank/run_stochastic_test.sh
```

Or manually:

```bash
python -m experiments.reasoningbank.run.phase1_uniprot \
  --stochastic --stochastic-k 2 --temperature 0.7 \
  --tasks experiments/reasoningbank/test_stochastic_tasks.json \
  --l0 --local \
  --log-dir experiments/reasoningbank/results/stochastic_logs/
```

### Example: Full Evaluation

Run 10 tasks with k=5 rollouts:

```bash
python -m experiments.reasoningbank.run.phase1_uniprot \
  --stochastic --stochastic-k 5 --temperature 0.7 \
  --tasks experiments/reasoningbank/uniprot_subset_tasks.json \
  --l0 --local \
  --log-dir experiments/reasoningbank/results/stochastic_logs/
```

## Output Format

### Results JSON Structure

```json
{
  "experiment": {
    "type": "stochastic",
    "k": 5,
    "temperature": 0.7,
    "timestamp": "2026-02-03T...",
    "config": {
      "endpoint": "uniprot",
      "ontology": "ontology/uniprot",
      "layers": {
        "l0": true,
        "l1": false,
        "l2": true,
        "l3": false
      }
    }
  },
  "tasks": [
    {
      "task_id": "protein_lookup",
      "query": "...",
      "rollouts": [
        {
          "rollout_id": 1,
          "converged": true,
          "answer": "...",
          "sparql": "...",
          "judgment": {
            "success": true,
            "reason": "..."
          },
          "iters": 5
        }
      ],
      "metrics": {
        "pass_1": true,
        "best_of_n": true,
        "pass_k": 0.6,
        "n_success": 3,
        "n_total": 5
      }
    }
  ],
  "aggregate_metrics": {
    "mean_pass_1": 0.7,
    "mean_best_of_n": 0.9,
    "mean_pass_k": 0.65,
    "tasks_with_any_success": 9,
    "total_tasks": 10
  }
}
```

### Metrics Explained

**Per-task metrics:**
- `pass_1`: Was the first rollout successful? (boolean)
- `best_of_n`: Was at least one rollout successful? (boolean)
- `pass_k`: Fraction of successful rollouts (float 0.0-1.0)
- `n_success`: Number of successful rollouts (int)
- `n_total`: Total number of rollouts (int)

**Aggregate metrics:**
- `mean_pass_1`: Average Pass@1 across all tasks
- `mean_best_of_n`: Average Best-of-N across all tasks
- `mean_pass_k`: Average Pass@k across all tasks
- `tasks_with_any_success`: Number of tasks with at least one success
- `total_tasks`: Total number of tasks evaluated

## Output Files

### Results JSON
Location: `experiments/reasoningbank/results/stochastic_k{k}_t{temperature}.json`

Example: `stochastic_k5_t0.7.json`

### Trajectory Logs
Location: `{log_dir}/{task_id}_rollout{i}.jsonl`

Example: `stochastic_logs/4_uniprot_mnemonic_id_rollout1.jsonl`

Each JSONL file contains event-by-event trajectory:
- `run_start`: Run initialization
- `iteration`: Each RLM iteration with reasoning/code/output
- `run_complete`: Final results with answer/sparql

## Questions Answered

1. **Variance**: How much does performance vary across rollouts? (Pass@k variance)
2. **Best-of-N value**: Is Best-of-N >> Pass@1? (If yes, MaTTS selection valuable)
3. **Baseline for memory**: What's Pass@1 without memory? (Baseline for improvement)
4. **Task difficulty**: Which tasks have low Pass@k? (Candidates for targeted memory)

## Analysis Workflow

1. **Run stochastic evaluation** with k=5 rollouts per task
2. **Analyze results JSON** to compute variance and identify patterns
3. **Compare Best-of-N vs Pass@1** to determine MaTTS value
4. **Identify low Pass@k tasks** for targeted memory extraction
5. **Compute baseline** for future memory-augmented comparisons

## Implementation Details

### Temperature Configuration

The `run_uniprot()` function now accepts a `temperature` parameter:

```python
def run_uniprot(
    task: str,
    ont_path: str,
    cfg: Cfg,
    mem: MemStore|None = None,
    endpoint: str = 'uniprot',
    max_iters: int = 12,
    max_calls: int = 25,
    temperature: float = 0.0,  # Default deterministic
    verbose: bool = True,
    log_path: str|None = None,
    use_local_interpreter: bool = False,
) -> Result:
```

When `temperature > 0.0`, DSPy LM is reconfigured with the specified temperature.

### Judgment

All rollouts are judged deterministically (temperature=0.0) using the `judge()` function from `phase1.py`.

### Metrics Computation

```python
def compute_stochastic_metrics(rollouts: list[dict]) -> dict:
    """Compute Pass@1, Best-of-N, Pass@k from rollout results."""
    judgments = [r['judgment']['success'] for r in rollouts]
    n_success = sum(judgments)
    n_total = len(judgments)

    return {
        'pass_1': judgments[0] if judgments else False,
        'best_of_n': any(judgments),
        'pass_k': n_success / n_total if n_total > 0 else 0.0,
        'n_success': n_success,
        'n_total': n_total,
    }
```

## Future Work

After analyzing stochastic evaluation results:

1. **Contrastive extraction**: Extract from success/failure pairs
2. **SQLite memory backend**: Integrate with ReasoningBank
3. **Curriculum learning**: Prioritize extraction from low Pass@k tasks
4. **MaTTS optimization**: Implement parallel rollout selection based on Best-of-N gap

## Files Modified

1. `experiments/reasoningbank/run/rlm_uniprot.py`
   - Added `temperature` parameter to `run_uniprot()`
   - Configure DSPy LM with temperature when `temperature > 0.0`

2. `experiments/reasoningbank/run/phase1_uniprot.py`
   - Added `compute_stochastic_metrics()` function
   - Added `run_stochastic_uniprot()` function
   - Added CLI flags: `--stochastic`, `--stochastic-k`, `--temperature`
   - Added stochastic mode handling in main block
   - Save results with aggregate metrics

## Testing

### Smoke Test
```bash
./experiments/reasoningbank/run_stochastic_test.sh
```

Expected output:
- 2 tasks × 2 rollouts = 4 total runs
- Per-task metrics printed during execution
- Aggregate metrics printed at end
- Results saved to `experiments/reasoningbank/results/stochastic_k2_t0.7.json`

### Full Evaluation
```bash
python -m experiments.reasoningbank.run.phase1_uniprot \
  --stochastic --stochastic-k 5 --temperature 0.7 \
  --tasks experiments/reasoningbank/uniprot_subset_tasks.json \
  --l0 --local \
  --log-dir experiments/reasoningbank/results/stochastic_logs/
```

Expected output:
- 10 tasks × 5 rollouts = 50 total runs
- Aggregate metrics showing Pass@1, Best-of-N, Pass@k means
- Results saved with k and temperature in filename
