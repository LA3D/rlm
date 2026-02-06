# Getting Started with ReasoningBank Experiments

**Quick Start**: Read `INDEX.md` for directory overview, then `STATUS.md` for current work.

---

## First Time Setup

1. **Activate environment**:
   ```bash
   source ~/uvws/.venv/bin/activate
   cd experiments/reasoningbank
   ```

2. **Verify tests pass**:
   ```bash
   # Smoke tests (fast, basic functionality)
   python tests/smoke/test_basic.py

   # All tests
   python -m pytest tests/
   ```

3. **Read the context**:
   - `INDEX.md` - Directory structure and navigation
   - `STATUS.md` - Current experiments, validated patterns, priorities
   - `WORK_LOG.md` - Session-by-session history

---

## Common Workflows

### Running the Current Experiment (S3 Full Run)

From `STATUS.md` Priority 1:

```bash
source ~/uvws/.venv/bin/activate
python experiments_archive/2026-02-03_s3_prompt_perturbation/run_experiment_s3.py \
  --full --output experiments_archive/2026-02-03_s3_prompt_perturbation/results/
```

Expected: 2-3 hours, 100 runs (5 tasks × 5 rollouts × 4 strategies)

### Running Individual Tests

```bash
# Smoke tests (basic functionality)
python tests/smoke/test_basic.py

# Integration tests (full system)
python tests/integration/test_enhanced_l0_all.py

# Unit tests (specific modules)
python tests/unit/test_l0_comparison.py

# Debug tests (troubleshooting)
python tests/debug/test_sparql_basic.py
```

### Analyzing Results

```bash
# Trajectory analysis (after experiment completes)
python experiments_archive/2026-02-03_s3_prompt_perturbation/analysis/analyze_s3_trajectories.py \
  --results experiments_archive/2026-02-03_s3_prompt_perturbation/results/

# Diversity metrics
python prototype/metrics/diversity.py --help
```

### Creating a New Experiment

1. **Create timestamped directory**:
   ```bash
   mkdir -p experiments_archive/2026-02-XX_experiment_name/{results,analysis}
   ```

2. **Create EXPERIMENT.md** (copy template from `experiments_archive/README.md`)

3. **Write experiment script**:
   ```python
   # experiments_archive/2026-02-XX_experiment_name/run_experiment.py
   from experiments.reasoningbank.prototype.run import phase0_uniprot
   # ... experiment logic
   ```

4. **Document in STATUS.md**:
   - Add to "In Progress" experiments table
   - Update "Active Work" section

---

## Understanding the Code

### Key Modules

**Core primitives** (`prototype/core/`):
- `blob.py` - BlobRef (handle pattern for large data)
- `mem.py` - Memory store and retrieval

**Packers** (`prototype/packers/`):
- `l0_sense.py` - Ontology sense cards (~600 chars, 100% URI grounding)
- `l1_schema.py` - Schema constraints and anti-patterns
- `l2_memories.py` - Procedural memory formatting

**Context builder** (`prototype/ctx/`):
- `builder.py` - Multi-layer context assembly

**Tools** (`prototype/tools/`):
- `sparql.py` - Bounded SPARQL execution
- `endpoint.py` - Remote endpoint wrappers

**Runners** (`prototype/run/`):
- `phase0_uniprot.py` - Closed-loop experiments
- `phase1_stochastic.py` - Stochastic evaluation

### Import Convention

All imports use `experiments.reasoningbank.prototype.*`:

```python
from experiments.reasoningbank.prototype.core.blob import Store, Ref
from experiments.reasoningbank.prototype.packers import l0_sense
from experiments.reasoningbank.prototype.ctx.builder import build_context
```

### DSPy RLM Tool Calling

Tools use `lambda args, kwargs:` signature (not `*args, **kwargs`):

```python
def my_tool(g, limit=10):
    """Tool docstring."""
    return results

# Exposed as:
ns['my_tool'] = lambda args, kwargs: my_tool(*args, **kwargs)
```

---

## Progressive Disclosure Approach

This directory is organized for **Claude Code sessions**:

1. **START HERE**: `INDEX.md` → High-level navigation
2. **CURRENT STATE**: `STATUS.md` → What's working, what's next
3. **HISTORY**: `WORK_LOG.md` → Session-by-session decisions
4. **DEEP DIVES**: Follow links to specific areas

Each subdirectory has its own README explaining purpose and contents.

---

## Research-to-Production Pipeline

This is **research code** (exploratory, not production):

1. **Explore** → Write code in `prototype/`
2. **Experiment** → Run in `experiments_archive/YYYY-MM-DD_name/`
3. **Validate** → Document in `findings/validated_patterns/`
4. **Extract** → Follow `extraction_guide/` to reimplement in production

**DO NOT**:
- Refactor prototype code for production use
- Import prototype modules into production packages

**DO**:
- Extract patterns and principles
- Rewrite from scratch for production
- Document lessons learned in `findings/`

---

## Key Files

| File | Purpose |
|------|---------|
| `INDEX.md` | Directory navigation (start here) |
| `STATUS.md` | Current experiments, priorities, validated patterns |
| `WORK_LOG.md` | Session-by-session journal |
| `README.md` | Experiment design and architecture |
| `tasks/*.json` | 750+ evaluation tasks (5 files) |

---

## Session Handoff Protocol

When starting a new session:

1. **Read STATUS.md** - Current state, active work, next priorities
2. **Read WORK_LOG.md** - Recent session history (last 2-3 entries)
3. **Check experiments_archive/** - Latest experiment status
4. **Run smoke tests** - Verify environment works

When ending a session:

1. **Update STATUS.md** - Reflect current state changes
2. **Add WORK_LOG.md entry** - Document what was done, decisions, next steps
3. **Create TODO.md** (optional) - Explicit next actions if needed

---

## Troubleshooting

### Import errors

```bash
# Verify you're in the right directory
pwd  # Should be .../rlm/experiments/reasoningbank

# Verify environment is activated
which python  # Should be ~/uvws/.venv/bin/python

# Check import paths
python -c "from experiments.reasoningbank.prototype.core.blob import Store; print('OK')"
```

### Tests fail

```bash
# Run individual test to see full error
python tests/smoke/test_basic.py

# Check Python path
python -c "import sys; print('\n'.join(sys.path))"
```

### Experiment crashes

```bash
# Check recent logs
ls -lt experiments_archive/*/results/*.jsonl | head -5

# Run minimal test first
python experiments_archive/*/run_experiment.py --minimal
```

---

## Next Steps

See `STATUS.md` section "Next Steps (Priority Order)" for current priorities.

Current active work (as of 2026-02-04):
- **Priority 1**: Complete S3 full run (100 rollouts, ~2-3 hours)
- **Priority 2**: Extract S3 results if validated
- **Priority 3**: Run E6 (full layer cake test)

---

**Last updated**: 2026-02-04
