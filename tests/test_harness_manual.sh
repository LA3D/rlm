#!/bin/bash
# Manual test script for eval harness
# Tests CLI functionality without requiring API keys or real ontologies

set -e

echo "=== Eval Harness Test Suite ==="
echo ""

# Activate environment
source ~/uvws/.venv/bin/activate

echo "1. Testing CLI help and command registration..."
python -m evals.cli --help > /dev/null
python -m evals.cli list --help > /dev/null
python -m evals.cli run --help > /dev/null
python -m evals.cli matrix --help > /dev/null
python -m evals.cli analyze --help > /dev/null
echo "   ✓ All CLI commands registered"

echo ""
echo "2. Testing task discovery..."
# Count tasks from the "Found X tasks" line
TASK_OUTPUT=$(python -m evals.cli list 2>/dev/null | head -1)
TASK_COUNT=$(echo "$TASK_OUTPUT" | grep -o "[0-9]\+" | head -1)
echo "   Found $TASK_COUNT tasks"
if [ "$TASK_COUNT" -gt 0 ]; then
    echo "   ✓ Task discovery works"
else
    echo "   ✗ No tasks found"
    exit 1
fi

echo ""
echo "3. Testing ablation config presets..."
python -c "
from evals.ablation_config import AblationConfig
presets = ['baseline', 'minimal', 'structural', 'semantic', 'full', 'full_with_memory']
for preset in presets:
    config = AblationConfig.from_preset(preset)
    print(f'   ✓ {preset}: {len(config.get_enabled_features())} features')
"

echo ""
echo "4. Testing graders..."
python -c "
from evals.graders import SparqlStructuralGrader, AffordanceUtilizationGrader

# Test SPARQL structural grader
grader = SparqlStructuralGrader(requires_graph=True)
print('   ✓ SparqlStructuralGrader instantiated')

# Test affordance utilization grader
grader = AffordanceUtilizationGrader()
print('   ✓ AffordanceUtilizationGrader instantiated')
"

echo ""
echo "5. Testing analysis tools with mock data..."
python -c "
import json
import tempfile
from pathlib import Path
from evals.analysis.summary import generate_summary

# Create temp dir with sample results
with tempfile.TemporaryDirectory() as tmpdir:
    results_dir = Path(tmpdir)

    # Create sample result
    result = {
        'task_id': 'test_001',
        'task_query': 'Test query',
        'total_trials': 3,
        'passed_trials': 2,
        'pass_at_k': 0.67,
        'avg_iterations': 5.0,
        'avg_groundedness': 0.8
    }

    with open(results_dir / 'test.json', 'w') as f:
        json.dump(result, f)

    # Generate summary
    summary = generate_summary(str(results_dir))

    if 'error' not in summary:
        print(f'   ✓ Summary generated: {summary[\"total_tasks\"]} tasks')
    else:
        print(f'   ✗ Summary failed: {summary[\"error\"]}')
        exit(1)
"

echo ""
echo "6. Testing reasoning level filtering..."
python -c "
import yaml
from pathlib import Path

# Check if reasoning tasks have reasoning_level field
reasoning_tasks = list(Path('evals/tasks/reasoning').rglob('*.yaml'))
if reasoning_tasks:
    task_path = reasoning_tasks[0]
    with open(task_path) as f:
        raw = yaml.safe_load(f)
        task = raw.get('task', raw)
        if 'reasoning_level' in task:
            print(f'   ✓ Reasoning level field present: {task[\"reasoning_level\"]}')
        else:
            print('   ⚠ Reasoning level field missing')
else:
    print('   ⚠ No reasoning tasks found')
"

echo ""
echo "=== All Tests Passed ==="
echo ""
echo "Next steps:"
echo "1. Run unit tests: pytest tests/test_eval_harness.py -v"
echo "2. Try a real eval (requires ANTHROPIC_API_KEY):"
echo "   python -m evals.cli run 'regression/basic_search_001' --trials 1"
echo "3. Try matrix run:"
echo "   python -m evals.cli matrix 'regression/*' --cohorts baseline minimal --trials 1"
