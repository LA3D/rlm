# Eval Harness Testing - Quick Start

## Status: ✅ All Components Validated

The Phase 4 eval harness has been implemented and validated. Here's how to test it:

## 🚀 Quick Test (30 seconds, no API key needed)

```bash
cd /Users/cvardema/dev/git/LA3D/rlm
source ~/uvws/.venv/bin/activate

# Run automated smoke tests
./tests/test_harness_manual.sh
```

This validates:
- ✅ CLI commands registered (run, list, matrix, analyze)
- ✅ Task discovery (14 tasks found)
- ✅ Ablation configs (6 presets: baseline → full_with_memory)
- ✅ New graders (SPARQL structural, affordance utilization)
- ✅ Analysis tools with mock data

## 📋 Unit Tests (pytest)

```bash
# Run full test suite
pytest tests/test_eval_harness.py -v

# Run specific test class
pytest tests/test_eval_harness.py::TestSparqlStructuralGrader -v
```

**Coverage:**
- 15+ test cases for Rungs 2, 4, 7, 8
- Mock data for isolated testing
- No API keys required

## 🔬 Integration Tests (requires ANTHROPIC_API_KEY)

### Level 1: Single Task Run

```bash
export ANTHROPIC_API_KEY="your-key"

# Test Rung 1: DSPy default with artifact capture
python -m evals.cli run 'regression/basic_search_001' --trials 1

# Verify artifacts captured
cat evals/results/basic_search_001_*.json | \
  jq '.trial_results[0] | {sparql, evidence, converged}'
```

**Expected:** JSON with `sparql`, `evidence`, `converged` fields populated.

### Level 2: Matrix Run

```bash
# Test Rungs 4-5: Ablation matrix across cohorts
python -m evals.cli matrix 'regression/basic_search_001' \
  --cohorts baseline minimal full \
  --trials 1

# Check results
ls evals/matrix_results/
cat evals/matrix_results/matrix_summary.json | jq '.by_cohort'
```

**Expected:** 3 cohort directories + `matrix_summary.json` with cross-cohort comparison.

### Level 3: Full Pipeline

```bash
# Run with MLflow tracking (Rung 3)
python -m evals.cli matrix 'regression/*' \
  --cohorts baseline structural full \
  --trials 2 \
  --mlflow --mlflow-experiment "Test-Run"

# Analyze results (Rung 8)
python -m evals.cli analyze evals/matrix_results/matrix_summary.json \
  --format json --output analysis.json

# View recommendations
cat analysis.json | jq '.recommendations'
```

**Expected:** MLflow DB created, structured analysis with actionable recommendations.

## 📊 What Each Test Validates

| Rung | Feature | Test Command | Expected Output |
|------|---------|--------------|-----------------|
| 1 | DSPy Default | `run 'regression/*'` | `sparql`, `evidence`, `converged` in results |
| 2 | SPARQL Structural Grader | `run 'uniprot/multigraph/*'` | Structural checks in grader_results |
| 3 | MLflow Integration | `run --mlflow` | MLflow DB with tracked metrics |
| 4 | Ablation Config | Python import test | 6 presets load correctly |
| 5 | Matrix Runner | `matrix --cohorts baseline full` | Cross-cohort comparison |
| 6 | Reasoning Tasks | `run 'reasoning/*'` | Tasks with reasoning_level field |
| 7 | Affordance Utilization | Check grader output | Utilization/hallucination rates |
| 8 | Analysis Tools | `analyze evals/results` | Structured summary + recommendations |

## 🎯 Verification Checklist

Run this checklist to confirm everything works:

```bash
# 1. CLI smoke test
python -m evals.cli --help | grep -q "matrix" && echo "✅ Matrix command registered"

# 2. Task discovery
TASKS=$(python -m evals.cli list 2>/dev/null | grep -c "yaml")
[ "$TASKS" -gt 10 ] && echo "✅ Found $TASKS tasks"

# 3. Ablation presets
python -c "from evals.ablation_config import AblationConfig; \
  [AblationConfig.from_preset(p) for p in ['baseline','minimal','structural','semantic','full','full_with_memory']]" \
  && echo "✅ All 6 ablation presets load"

# 4. Graders instantiate
python -c "from evals.graders import SparqlStructuralGrader, AffordanceUtilizationGrader; \
  SparqlStructuralGrader(); AffordanceUtilizationGrader()" \
  && echo "✅ New graders instantiate"

# 5. Analysis tools work
python -c "from evals.analysis import generate_summary" \
  && echo "✅ Analysis tools import"

# 6. Reasoning tasks exist
ls evals/tasks/reasoning/**/*.yaml >/dev/null 2>&1 \
  && echo "✅ Reasoning tasks created"
```

## 🐛 Common Issues

### "No tasks found"
```bash
# Check you're in project root
pwd  # Should be /Users/cvardema/dev/git/LA3D/rlm
ls evals/tasks  # Should show directories
```

### "Module not found"
```bash
# Activate environment
source ~/uvws/.venv/bin/activate

# Install in editable mode
uv pip install -e .
```

### "MLflow not available"
```bash
# Install MLflow (optional)
uv pip install mlflow

# Or run without --mlflow flag
python -m evals.cli run 'regression/*' --trials 1
```

## 📈 Next Steps

After validation:

1. **Create ontology-specific tasks** in `evals/tasks/`
2. **Run ablation experiments**: `matrix --cohorts baseline full`
3. **Analyze results**: `analyze evals/matrix_results/matrix_summary.json`
4. **Iterate on sense cards** based on affordance utilization metrics

## 📚 Detailed Documentation

See [testing_eval_harness.md](./testing_eval_harness.md) for:
- Detailed test procedures for each rung
- End-to-end validation scenarios
- CI/CD integration examples
- Troubleshooting guide

## 📞 Support

If tests fail:
1. Check [testing_eval_harness.md](./testing_eval_harness.md) troubleshooting section
2. Run with `-v` flag for verbose output
3. Check `evals/results/` for error details
