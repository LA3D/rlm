# Task Definitions

Task definition files for experiments. Each file contains JSON-formatted queries with expected SPARQL and metadata.

## Purpose

These are **evaluation task suites** used to:
- Test RLM query construction capabilities
- Benchmark across different configurations (E1-E12)
- Validate memory/layer improvements
- Compute metrics (Pass@1, Pass@k, convergence)

**Not to be confused with**:
- `seed/` - Bootstrap memory (strategies, constraints)
- `02_EXPERIMENTS/*/results/` - Actual run outputs

## Files

### UniProt Task Suites

| File | Tasks | Purpose | Used In |
|------|-------|---------|---------|
| `uniprot_subset_tasks.json` | 10 | Small representative set | Phase 1, E2-E5 |
| `uniprot_test_tasks.json` | 3 | Quick smoke tests | Development |
| `uniprot_pure_tasks.json` | 100+ | Non-federated queries only | Full evaluation |
| `uniprot_shacl_tasks.json` | 636 | All SHACL examples | Comprehensive eval |

### Stochastic Task Suites

| File | Tasks | Purpose | Used In |
|------|-------|---------|---------|
| `test_stochastic_tasks.json` | 2 | Minimal test suite | S1, S3 smoke tests |

## Task Format

Each task has:
```json
{
  "id": "4_uniprot_mnemonic_id",
  "query": "Select the UniProtKB entry with the mnemonic 'A4_HUMAN'",
  "expected_sparql": "PREFIX up: ...",
  "complexity": "simple|moderate|complex",
  "keywords": ["identifier", "lookup"]
}
```

## Usage

```python
# Load tasks
import json
with open('tasks/uniprot_subset_tasks.json') as f:
    tasks = json.load(f)

# Run experiment
for task in tasks:
    result = run_experiment(task['query'], ...)
    judge(result, task['expected_sparql'])
```

## Task Suite Selection

**For quick tests:**
- `uniprot_test_tasks.json` (3 tasks, ~2 min)

**For development:**
- `uniprot_subset_tasks.json` (10 tasks, ~10 min)

**For full evaluation:**
- `uniprot_pure_tasks.json` (100+ tasks, ~2 hours)
- `uniprot_shacl_tasks.json` (636 tasks, ~12 hours)

## Creating New Task Suites

1. Create `experiment_name_tasks.json`
2. Follow format above
3. Add complexity levels for filtering
4. Document in this README
5. Commit with experiment

---

**Last updated**: 2026-02-04
