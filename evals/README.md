# RLM Evaluation Framework

This directory contains the evaluation harness for measuring RLM performance on ontology-based query construction tasks.

## Environment Setup

This project uses the **uvws shared environment**. Always activate it before running commands:

```bash
# Activate the shared uv environment
source ~/uvws/.venv/bin/activate

# Verify activation
python --version  # Should show Python 3.12+
```

## Quick Start

```bash
# Activate environment first!
source ~/uvws/.venv/bin/activate

# Run a single task
python -m evals.cli run 'uniprot/taxonomy/uniprot_bacteria_taxa_001'

# Run all UniProt tasks
python -m evals.cli run 'uniprot/*'

# List available tasks
python -m evals.cli list

# Run with memory enabled
python -m evals.cli run 'uniprot/*' --enable-memory --memory-db evals/memory.db

# Generate report
python -m evals.cli report evals/results
```

---

## Directory Structure

```
evals/
├── experiments/              # Structured experiment tracking (NEW)
│   ├── registry.yaml        # Index of all experiments
│   └── EXXX_name/           # Individual experiment directories
│       ├── experiment.yaml  # Full metadata, hypothesis, changes
│       ├── cohorts/         # Experimental conditions
│       │   ├── baseline/
│       │   └── experimental/
│       ├── summary.json     # Aggregated results
│       └── ANALYSIS.md      # Human notes, findings
│
├── tasks/                   # Task definitions (YAML)
│   ├── entity_discovery/
│   ├── hierarchy/
│   ├── uniprot/
│   │   ├── taxonomy/
│   │   ├── multigraph/
│   │   ├── federated/
│   │   └── complex/
│   └── ...
│
├── graders/                 # Grading logic
│   ├── base.py
│   ├── convergence.py
│   ├── outcome_verification.py
│   ├── llm_judge.py
│   ├── sparql_structural.py
│   └── ...
│
├── runners/                 # Execution runners
│   ├── task_runner.py       # Single task execution
│   └── matrix_runner.py     # Ablation matrix experiments
│
├── results/                 # Legacy flat results (being phased out)
├── cli.py                   # CLI entrypoint
├── experiment_template.yaml # Template for new experiments
├── registry_template.yaml   # Template for registry
└── README.md               # This file
```

---

## Experiment Management (NEW)

### Philosophy

Experiments are **first-class entities** with:
- **Unique ID**: E001, E002, etc.
- **Git traceability**: Exact commit that produced results
- **Hypothesis**: What are you testing?
- **Cohorts**: Baseline vs experimental conditions
- **Metadata**: Tasks, metrics, statistical tests
- **Analysis**: Human notes, findings, next steps

### Why This Structure?

**Problems with flat results directory:**
- Can't tell which git commit produced which results
- No way to compare baseline vs experimental
- No documentation of hypothesis or changes
- Hard to find related results
- Impossible to reproduce experiments

**Benefits of experiment structure:**
- Git-friendly: Each experiment is a unit of work
- Self-documenting: experiment.yaml has all context
- Comparable: Easy to find baseline and run statistical tests
- Reproducible: Git commit + config = exact reproduction
- Analysis-ready: Claude can read experiment.yaml to understand context

---

## Creating a New Experiment

### Step 1: Design the Experiment

Before writing code, document:
1. **Hypothesis**: What do you expect to happen?
2. **Changes**: What code/prompts are different from baseline?
3. **Metrics**: How will you measure success?
4. **Comparison**: Which experiment is the baseline?

### Step 2: Create Experiment Directory

```bash
# Create directory
mkdir -p evals/experiments/E003_rung2_exploration_planning/cohorts/{baseline,rung2}

# Copy template
cp evals/experiment_template.yaml evals/experiments/E003_rung2_exploration_planning/experiment.yaml

# Edit experiment.yaml with your details
```

### Step 3: Implement Changes

Make your code changes and **commit them**:

```bash
git add rlm_runtime/engine/dspy_rlm.py
git commit -m "Add exploration_summary and plan fields to QueryConstructionSig"

# Record commit hash in experiment.yaml
git rev-parse HEAD  # Copy this into experiment.yaml
```

### Step 4: Run Baseline (Control)

Run the baseline condition first (previous best approach):

```bash
# Activate environment
source ~/uvws/.venv/bin/activate

# Checkout baseline commit
git checkout 9efd8204  # E002 commit (Rung 1)

# Run baseline trials
python -m evals.cli run 'uniprot/taxonomy/*' --trials 10 \
  --output evals/experiments/E003_rung2_exploration_planning/cohorts/baseline/results

# Return to experiment branch
git checkout main
```

### Step 5: Run Experimental Condition

Run with your new changes:

```bash
# Environment should still be activated
python -m evals.cli run 'uniprot/taxonomy/*' --trials 10 \
  --output evals/experiments/E003_rung2_exploration_planning/cohorts/rung2/results
```

### Step 6: Analyze Results

```bash
# Compare cohorts
python -m evals.cli experiment compare E003 \
  --cohorts baseline rung2 \
  --output evals/experiments/E003_rung2_exploration_planning/comparison.json

# Write analysis notes
vim evals/experiments/E003_rung2_exploration_planning/ANALYSIS.md
```

### Step 7: Update Registry

Add your experiment to `experiments/registry.yaml`:

```yaml
- id: "E003"
  name: "rung2_exploration_planning"
  date: "2026-01-23"
  status: "completed"
  description: "Rung 2: Add exploration_summary and plan fields"
  git_commit: "<your-commit-hash>"
  path: "experiments/E003_rung2_exploration_planning"
  parent: "E002"
  results_summary:
    bacteria_taxa: "XX% pass rate (X/X trials)"
    ecoli_k12: "XX% pass rate (X/X trials)"
```

---

## Experiment Templates

### Comparing Agentic Patterns

Example: Think-Act-Verify-Reflect vs Chain-of-Thought

```yaml
experiment:
  id: "E006"
  name: "reasoning_pattern_comparison"
  hypothesis: "TAVR outperforms CoT for SPARQL construction"

  cohorts:
    - name: "chain_of_thought"
      config:
        reasoning_pattern: "cot"
        git_commit: "abc1234"

    - name: "think_act_verify_reflect"
      config:
        reasoning_pattern: "tavr"
        git_commit: "def5678"

  metrics:
    primary: ["pass_rate", "evidence_format_correctness"]
    secondary: ["avg_iterations", "sparql_structural_compliance"]

  comparison:
    statistical_test: "paired_t_test"
```

### Affordance Ablation

Example: Which sense card features help?

```yaml
experiment:
  id: "E004"
  name: "affordance_ablation"
  hypothesis: "Domain/range info specifically helps with JOIN construction"

  cohorts:
    - name: "minimal"
      config: {sense_features: {basic_stats: true}}
    - name: "structural"
      config: {sense_features: {basic_stats: true, domain_range: true, hierarchy: true}}
    - name: "semantic"
      config: {sense_features: {basic_stats: true, domain_range: true, hierarchy: true,
                                  materialization_hints: true, property_characteristics: true}}
    - name: "full"
      config: {sense_features: {all: true}}

  metrics:
    primary: ["pass_rate"]
    secondary: ["affordance_utilization_rate", "join_correctness"]
```

### Learning Curves

Example: Does memory improve over time?

```yaml
experiment:
  id: "E005"
  name: "memory_learning_curves"
  hypothesis: "ReasoningBank reduces iteration count over sequential runs"

  cohorts:
    - name: "no_memory"
      config: {enable_memory: false}
    - name: "memory_enabled"
      config: {enable_memory: true, memory_db: "evals/experiments/E005/memory.db"}

  # Run tasks sequentially to observe learning
  task_order: "sequential"  # Not random
  trials_per_task: 20       # Long sequence

  metrics:
    primary: ["pass_rate", "avg_iterations"]
    learning_curve: ["iteration_count vs cumulative_tasks", "memory_size vs cumulative_tasks"]
```

---

## CLI Commands (Planned Enhancements)

### Experiment Management

```bash
# Create new experiment from template
python -m evals.cli experiment create \
  --name "rung2_exploration_planning" \
  --hypothesis "Explicit exploration phase improves discovery" \
  --parent E002

# List all experiments
python -m evals.cli experiment list

# Show experiment details
python -m evals.cli experiment show E003

# Run specific experiment
python -m evals.cli experiment run E003 \
  --cohorts baseline rung2 \
  --trials 10

# Compare experiments
python -m evals.cli experiment compare E002 E003 \
  --metric pass_rate \
  --test paired_t_test

# Update experiment status
python -m evals.cli experiment status E003 completed
```

### Analysis Commands

```bash
# Generate structured analysis for Claude Code
python -m evals.cli analyze evals/experiments/E003 \
  --format json \
  --output analysis.json

# Learning curve analysis
python -m evals.cli analyze learning-curve \
  evals/experiments/E005 \
  --plot-to curves.png
```

---

## Working with Claude Code

### Context for Claude

When asking Claude to help with eval analysis:

1. **Point to experiment directory**:
   ```
   "Look at evals/experiments/E002_rung1_think_act_verify_reflect/"
   ```

2. **Claude can read**:
   - `experiment.yaml` - Understand hypothesis, changes, metrics
   - `cohorts/*/summary.json` - Aggregated statistics
   - `comparison.json` - Statistical test results
   - `ANALYSIS.md` - Previous human notes

3. **Claude will understand**:
   - What changed between experiments (git commits)
   - What hypothesis was being tested
   - Which metrics matter
   - How to compare results

### Example Interactions

**Good:**
```
"Compare E002 and E003. Did adding the exploration phase improve pass rate
on E. coli K12 tasks? Show statistical significance."
```

Claude can:
- Read both experiment.yaml files to understand changes
- Load results from cohorts/
- Run statistical comparison
- Interpret in context of hypothesis

**Also good:**
```
"I just ran E004 (affordance ablation). Which sense card features correlate
with correct JOIN construction?"
```

Claude can:
- Read experiment.yaml to understand cohorts
- Load results for each affordance level
- Correlate with JOIN correctness metric
- Recommend next experiments

---

## Task Definitions

Tasks are defined in YAML under `tasks/`. Each task specifies:

```yaml
task:
  id: "uniprot_ecoli_k12_sequences_001"
  category: "uniprot/taxonomy"
  difficulty: "medium"
  query: "Select UniProtKB proteins and amino acid sequences for E. coli K12 strains."

  context:
    ontologies:
      - name: uniprot_core
        source: ontology/uniprot/core.ttl
    sparql:
      endpoint: "https://sparql.uniprot.org/sparql/"

  graders:
    - type: convergence
      max_iterations: 16
    - type: outcome_verification
      result_type: "present"
      min_results: 3
      required_fields: ["protein", "sequence"]
    - type: llm_judge
      use_exemplar_patterns: true

  trials: 3
```

See `docs/guides/uniprot-evals.md` for full task suite documentation.

---

## Graders

Graders evaluate agent performance:

### outcome_verification
Checks actual results, not execution path (Anthropic best practice: "grade outcomes, not paths").

```yaml
- type: outcome_verification
  result_type: "present"        # present | absent | contains | count
  min_results: 3
  required_fields: ["protein", "sequence"]
  verification_patterns:
    - field: "sequence"
      pattern: "[A-Z]{10,}"     # Amino acids, not sequence_length!
      matches: "all"
```

### llm_judge
LLM-based semantic evaluation with exemplar patterns.

```yaml
- type: llm_judge
  use_exemplar_patterns: true
  strict: false
```

### convergence
Checks if agent finished within iteration budget.

```yaml
- type: convergence
  max_iterations: 16
```

### sparql_structural
Checks for required SPARQL operators (GRAPH, SERVICE, property paths).

```yaml
- type: sparql_structural
  required_patterns:
    - "GRAPH"
    - "SERVICE"
```

### affordance_utilization
Measures which affordances were used vs provided.

```yaml
- type: affordance_utilization
  sense_card_path: "..."
```

---

## Migration Plan

### Current State (2026-01-22)

- ✅ Flat `results/` directory with 26 result files
- ✅ No experiment structure
- ✅ Git commits exist but not linked to results
- ✅ Think-Act-Verify-Reflect implementation complete

### Migration Steps

1. **Phase 1: Structure** (This PR)
   - Create `experiments/` directory
   - Add templates and README
   - Add CLI commands for experiment management

2. **Phase 2: Backfill** (Next)
   - Create E001 (baseline before reasoning)
   - Create E002 (Rung 1 Think-Act-Verify-Reflect)
   - Migrate existing results into experiment directories

3. **Phase 3: Workflow** (Future)
   - Update CLI to default to experiment structure
   - Deprecate flat `results/` directory
   - Add analysis automation

4. **Phase 4: Advanced** (Future)
   - MLflow integration for experiment tracking
   - Automated statistical comparison
   - Learning curve visualization

---

## Best Practices

### Experiment Design

1. **One hypothesis per experiment**: Don't test multiple changes at once
2. **Always run baseline**: Compare against previous best, not absolute zero
3. **Sufficient trials**: Minimum 10 trials per task for statistical power
4. **Commit before running**: Lock in the code state before collecting data
5. **Document as you go**: Write ANALYSIS.md notes during the experiment

### Git Workflow

1. **Branch per experiment**: `git checkout -b experiment/E003-rung2`
2. **Commit changes**: Lock in code state before running trials
3. **Tag experiments**: `git tag E003-rung2-complete`
4. **Include commit hash**: Always record in experiment.yaml

### Statistical Rigor

1. **Paired comparisons**: Run same tasks before/after
2. **Random seeds**: Fix seeds for reproducibility
3. **Multiple trials**: 10+ for significance testing
4. **Correction for multiple comparisons**: Bonferroni if testing many hypotheses

### Documentation

1. **Hypothesis first**: Write it before implementing
2. **Document failures**: Negative results are valuable
3. **Next steps**: Always conclude with "what's next"
4. **Link to plan**: Reference trajectory_v3.md phases/rungs

---

## Research Questions Map

Map experiments to research questions from `docs/planning/trajectory_v3.md`:

| RQ | Question | Experiments |
|----|----------|-------------|
| RQ1 | Can LMs discover ontology affordances? | E004 (affordance ablation), E008 (dynamic discovery) |
| RQ2 | Multi-hop SPARQL composition? | E007 (federation), E009 (property paths) |
| RQ3 | Uses ontology logic vs blind retrieval? | E010 (structural grading), E011 (hallucination rate) |
| RQ4 | Learning dynamics? | E005 (memory learning curves), E006 (transfer) |
| RQ5 | Representation utility? | E004 (affordance ablation), E012 (feature correlation) |
| RQ6 | Reasoning boundaries? | E013 (L0-L7 tasks), E014 (tool gap analysis) |

---

## References

- Master plan: `docs/planning/trajectory_v3.md`
- UniProt task guide: `docs/guides/uniprot-evals.md`
- Think-Act-Verify-Reflect plan: `~/.claude/plans/ethereal-wobbling-clover.md`
- Anthropic eval best practices: https://docs.anthropic.com/en/docs/build-with-claude/develop-tests
