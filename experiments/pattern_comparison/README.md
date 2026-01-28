# Pattern Comparison Experiment

## Overview

This experiment compares different DSPy execution patterns (RLM, ReAct) with shared scratchpad infrastructure. All patterns use:

- **Rich sense cards** (AGENT_GUIDE.md, ~10K+ chars)
- **Result truncation** (10K char limit, like Daytona)
- **Verification feedback** (CoT anti-pattern detection)
- **Shared interpreter** (FINAL/FINAL_VAR interface)

## Execution Patterns

### 1. dspy.RLM (Enhanced)
- Code generation + execution in persistent namespace
- DSPy RLM with typed SUBMIT
- Tool-only access pattern

### 2. dspy.ReAct
- Simpler Thought → Action → Observation loop
- Direct tool calls (no code generation)
- Same interpreter features (truncation, verification)

## Test Tasks

Tasks span curriculum levels L1-L5:

| Level | Description | Example |
|-------|-------------|---------|
| L1 | Simple entity discovery | "What is the Protein class?" |
| L2 | Property exploration | "What properties connect proteins to annotations?" |
| L3 | Multi-hop queries | "Find proteins with disease associations and their EC numbers" |
| L4 | Complex filtering | "Find kinase proteins in humans with their GO annotations" |
| L5 | Aggregation | "Compare protein counts across taxonomic families" |

## Running the Experiment

### Basic Usage

```bash
# Compare all patterns on UniProt
python experiments/pattern_comparison/run_comparison.py

# Specific ontology
python experiments/pattern_comparison/run_comparison.py \\
    --ontology prov \\
    --ontology-path ontology/prov/prov.ttl

# Test specific patterns
python experiments/pattern_comparison/run_comparison.py \\
    --patterns dspy_rlm dspy_react

# Limit task count
python experiments/pattern_comparison/run_comparison.py \\
    --tasks 3 \\
    --verbose
```

### Expected Output

```
======================================================================
Pattern Comparison: uniprot
Patterns: dspy_rlm, dspy_react
Tasks: 7 across levels {'L1', 'L2', 'L3', 'L4', 'L5'}
======================================================================

----------------------------------------------------------------------
Pattern: DSPY_RLM
----------------------------------------------------------------------

[1/7] L1: What is the Protein class?
  ✓ Converged: True
  Iterations: 3
  Time: 12.4s
  Answer: The Protein class represents protein entries in UniProt...

...

======================================================================
Results Summary
======================================================================

Overall Performance:
Pattern         | Conv   | Iters  | Time     | Rate
----------------------------------------------------------------------
dspy_rlm        | 6/7    | 3.8    | 14.2s    | 86%
dspy_react      | 7/7    | 2.9    | 11.5s    | 100%

By Curriculum Level:

DSPY_RLM:
  L1: 2/2    (100%)
  L2: 2/2    (100%)
  L3: 1/1    (100%)
  L4: 0/1    (0%)
  L5: 1/1    (100%)

DSPY_REACT:
  L1: 2/2    (100%)
  L2: 2/2    (100%)
  L3: 1/1    (100%)
  L4: 1/1    (100%)
  L5: 1/1    (100%)

======================================================================
Winner: dspy_react (best convergence + efficiency)
======================================================================
```

## Metrics

For each pattern, we measure:

1. **Convergence rate**: % of tasks that successfully SUBMIT
2. **Average iterations**: Mean iteration count for converged runs
3. **Average time**: Mean elapsed time per task
4. **Performance by level**: Convergence rate breakdown by curriculum level

## Results Interpretation

### Convergence Rate
- **>90%**: Excellent - pattern handles diverse queries
- **70-90%**: Good - pattern works for most queries
- **<70%**: Poor - pattern struggles with complexity

### Iteration Count
- **Lower is better** - fewer iterations = more efficient reasoning
- L1-L2 tasks should converge in 2-4 iterations
- L3-L5 tasks may need 5-8 iterations

### Time per Task
- **Lower is better** - faster reasoning
- Includes: LLM calls, tool execution, verification
- ReAct typically faster (direct tool calls vs code generation)

## Architecture

```
run_comparison.py
├── RUNNERS (pattern → function mapping)
│   ├── dspy_rlm → run_dspy_rlm()
│   └── dspy_react → run_dspy_react()
│
├── COMMON_CONFIG (shared scratchpad features)
│   ├── result_truncation_limit: 10000
│   ├── enable_verification: True
│   ├── require_agent_guide: False (fallback allowed)
│   └── max_iterations: 8
│
└── TEST_TASKS (curriculum levels L1-L5)
    ├── L1: Simple entity discovery
    ├── L2: Property exploration
    ├── L3: Multi-hop queries
    ├── L4: Complex filtering
    └── L5: Aggregation
```

## Files

- `run_comparison.py` - Main experiment runner
- `results/comparison_[ontology]_[timestamp].json` - Detailed results
- `README.md` - This file

## Next Steps

1. **Run baseline comparison** - Establish performance baselines
2. **Add custom loop** (optional) - If RLM/ReAct insufficient
3. **Ablation studies** - Test impact of scratchpad features:
   - Rich vs minimal sense cards
   - Truncation on/off
   - Verification on/off
4. **Memory integration** - Compare with/without procedural memory
