# Testing the Eval Harness (Phase 4)

This guide explains how to test the Phase 4 eval harness at different levels: unit tests, integration tests, and end-to-end validation.

## Quick Test (No API Keys Required)

Run the manual test script to validate CLI and core functionality:

```bash
cd /Users/cvardema/dev/git/LA3D/rlm
chmod +x tests/test_harness_manual.sh
./tests/test_harness_manual.sh
```

This tests:
- ✅ CLI command registration
- ✅ Task discovery
- ✅ Ablation config presets
- ✅ Grader instantiation
- ✅ Analysis tools with mock data
- ✅ Reasoning level filtering

## Unit Tests (pytest)

Run the full unit test suite:

```bash
source ~/uvws/.venv/bin/activate
pytest tests/test_eval_harness.py -v
```

**Test coverage:**
- **Rung 2**: SPARQL structural grader with various requirements
- **Rung 4**: Ablation config presets and serialization
- **Rung 7**: Affordance utilization grader (with mocked ontologies)
- **Rung 8**: Analysis summary generation with sample data

**Expected output:**
```
tests/test_eval_harness.py::TestSparqlStructuralGrader::test_requires_graph_passes PASSED
tests/test_eval_harness.py::TestSparqlStructuralGrader::test_requires_graph_fails PASSED
tests/test_eval_harness.py::TestSparqlStructuralGrader::test_requires_service PASSED
...
```

## CLI Smoke Tests

Test each CLI command independently:

```bash
# List available tasks
python -m evals.cli list

# Get help for each command
python -m evals.cli run --help
python -m evals.cli matrix --help
python -m evals.cli analyze --help

# Test task pattern matching
python -m evals.cli list | grep uniprot
python -m evals.cli list | grep reasoning
```

## Integration Tests (Requires API Key)

These tests actually execute RLM runs. Set your API key first:

```bash
export ANTHROPIC_API_KEY="your-key-here"
```

### Test Rung 1: DSPy Default + Artifact Capture

```bash
# Run a simple task (should use DSPy by default)
python -m evals.cli run 'regression/basic_search_001' --trials 1

# Check that result JSON contains new fields
cat evals/results/basic_search_001_*.json | jq '.trial_results[0] | {sparql, evidence, converged}'
```

**Expected:** JSON output showing `sparql`, `evidence`, and `converged` fields.

### Test Rung 2: SPARQL Structural Grader

Create a test task with structural requirements:

```bash
# Run a UniProt multi-graph task
python -m evals.cli run 'uniprot/multigraph/uniprot_genetic_disease_proteins_001' --trials 1

# Check grader output
cat evals/results/uniprot_genetic_disease_proteins_001_*.json | \
  jq '.trial_results[0].grader_results | keys'
```

**Expected:** Should include `sparql_structural` or `evidence_pattern` in grader results.

### Test Rung 3: MLflow Integration

```bash
# Run with MLflow tracking
python -m evals.cli run 'regression/*' --trials 1 \
  --mlflow --mlflow-experiment "Test-Harness" \
  --mlflow-tracking-uri "sqlite:///test_mlflow.db"

# Query MLflow
python -c "
import mlflow
mlflow.set_tracking_uri('sqlite:///test_mlflow.db')
runs = mlflow.search_runs(experiment_names=['Test-Harness'])
print(f'Found {len(runs)} runs')
print(runs[['params.task_id', 'metrics.pass_at_k', 'metrics.iteration_count']].head())
"
```

**Expected:** MLflow database created with tracked runs.

### Test Rung 4: Ablation Configuration

Test parametric sense card generation:

```bash
python -c "
from rlm_runtime.ontology import build_sense_card, format_sense_card_parametric
from evals.ablation_config import AblationConfig

# Build sense card for PROV ontology
card = build_sense_card('ontology/prov.ttl', 'prov')

# Test different ablation configs
for preset in ['baseline', 'minimal', 'full']:
    config = AblationConfig.from_preset(preset)
    features = {feat: True for feat in config.get_enabled_features()}
    formatted = format_sense_card_parametric(card, features)
    print(f'{preset}: {len(formatted)} chars')
"
```

**Expected:** Different character counts showing feature-selective formatting.

### Test Rung 5: Matrix Runner

```bash
# Run matrix with multiple cohorts
python -m evals.cli matrix 'regression/basic_search_001' \
  --cohorts baseline minimal structural \
  --trials 1

# Check matrix summary
cat evals/matrix_results/matrix_summary.json | jq '.by_cohort | keys'
```

**Expected:** Matrix results directory with subdirectories per cohort and `matrix_summary.json`.

### Test Rung 6: Reasoning Boundary Tasks

```bash
# List reasoning tasks
python -m evals.cli list | grep reasoning

# Run materialization detection task
python -m evals.cli run 'reasoning/materialization_detection/*' --trials 1

# Filter by reasoning level
python -m evals.cli run 'reasoning/*' --reasoning-level L3_materialized --trials 1
```

**Expected:** Tasks categorized by reasoning level, structural grader validates correct operators.

### Test Rung 7: Affordance Utilization Grader

Add grader to an existing task temporarily:

```python
# In a test task YAML, add:
graders:
  - type: affordance_utilization
    min_utilization_rate: 0.3
    max_hallucination_rate: 0.1
```

Then run and check utilization metrics:

```bash
cat evals/results/task_*.json | \
  jq '.trial_results[0].grader_results.affordance_utilization.details | {utilization_rate, hallucination_rate}'
```

**Expected:** Utilization and hallucination rates in grader details.

### Test Rung 8: Analysis Tools

```bash
# Generate analysis from results
python -m evals.cli analyze evals/results --format json | jq '.recommendations'

# Analyze matrix results
python -m evals.cli analyze evals/matrix_results/matrix_summary.json \
  --format markdown
```

**Expected:** Structured summary with recommendations.

## End-to-End Validation

Run a complete ablation experiment:

```bash
# 1. Run matrix experiment
python -m evals.cli matrix 'regression/*' \
  --cohorts baseline minimal structural full \
  --trials 2 \
  --mlflow --mlflow-experiment "E2E-Test"

# 2. Analyze results
python -m evals.cli analyze evals/matrix_results/matrix_summary.json \
  --format json --output e2e_analysis.json

# 3. Read analysis
cat e2e_analysis.json | jq '.recommendations'

# 4. Query MLflow for comparison
python -c "
import mlflow
runs = mlflow.search_runs(experiment_names=['E2E-Test'])
print(runs.groupby('tags.cohort')['metrics.pass_at_k'].mean())
"
```

**Expected:**
1. Matrix results with 4 cohorts
2. Analysis JSON with feature impact
3. MLflow runs showing cohort comparison

## Troubleshooting

### "No tasks found"
- Ensure you're in the project root: `cd /Users/cvardema/dev/git/LA3D/rlm`
- Check tasks exist: `ls evals/tasks/**/*.yaml`

### "ANTHROPIC_API_KEY must be set"
- Export your key: `export ANTHROPIC_API_KEY="sk-ant-..."`
- Or use `--claudette` flag (legacy mode, still requires key)

### "MLflow not available"
- Install: `uv pip install mlflow`
- Or run without `--mlflow` flag

### Import errors
- Activate environment: `source ~/uvws/.venv/bin/activate`
- Install dependencies: `uv pip install -e .`

## Test Success Criteria

✅ **All rungs validated** when:
1. Unit tests pass (pytest)
2. CLI commands execute without errors
3. Tasks run with DSPy backend by default
4. New graders produce structured output
5. MLflow captures metrics
6. Ablation configs format sense cards differently
7. Matrix runner produces cross-cohort comparison
8. Analysis tools generate actionable recommendations

## CI/CD Integration

To add these tests to CI:

```yaml
# .github/workflows/test-eval-harness.yml
name: Test Eval Harness
on: [push, pull_request]
jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      - name: Setup Python
        uses: actions/setup-python@v4
        with:
          python-version: '3.11'
      - name: Install dependencies
        run: |
          pip install uv
          uv pip install -e .
          uv pip install pytest
      - name: Run unit tests
        run: pytest tests/test_eval_harness.py -v
      - name: Run smoke tests
        run: bash tests/test_harness_manual.sh
```

## Next Steps

After validating the harness:
1. **Create task suites** for your ontologies
2. **Run ablation experiments** to identify critical features
3. **Analyze reasoning boundaries** with L3-L7 tasks
4. **Iterate on affordances** based on utilization metrics
