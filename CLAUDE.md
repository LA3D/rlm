# Project Context for Claude Code

This document provides context about this project's development environment and conventions for AI assistants working on the codebase.

## Project Overview

This is a **hybrid nbdev project** implementing RLM (Recursive Language Models) integration with RDF ontologies and SPARQL queries. The goal is to enable progressive disclosure over large RDF graphs using ontology "affordances" (sense cards, meta-graphs, SHACL examples) to construct and execute SPARQL queries.

**Architecture (v2):**
- **Hybrid codebase**: nbdev notebooks for research/docs; stable runtime in handwritten `rlm_runtime/` package
- **DSPy RLM** for execution loop (typed `SUBMIT`, structured trajectories, tool-surface validation)
- **SQLite-backed ReasoningBank** for durable procedural memory with git-shipped memory packs
- Faithful to RLM progressive disclosure philosophy (handles-not-dumps)

## Development Environment

### Python Package Management: uv

This project uses **uv** for package management with a **shared environment** at `~/uvws/.venv`.

**Important**: `nbdev` is already installed in `~/uvws/.venv`.

```bash
# Activate the shared uv environment
source ~/uvws/.venv/bin/activate

# Install/update project dependencies from settings.ini
uv pip install fastcore claudette dialoghelper mistletoe rdflib sparqlx

# Or install in editable mode
uv pip install -e .
```

**Adding dependencies**: Update `settings.ini` `requirements` field, then run `uv pip install <package>` or `uv pip install -e .`

**Do not** create new venvs with `python -m venv` or similar.

## Project Structure

```
rlm/
├── nbs/                    # nbdev notebooks (docs/experiments)
│   ├── 00_core.ipynb       # Core RLM implementation
│   ├── 01_ontology.ipynb   # GraphMeta + bounded views
│   ├── 02_dataset_memory.ipynb  # RDF Dataset memory
│   ├── 05_procedural_memory.ipynb  # ReasoningBank loop
│   ├── 06_shacl_examples.ipynb  # SHACL indexing
│   └── ...
├── rlm/                    # Generated Python library (nbdev-generated)
│   ├── core.py             # RLM loop (claudette-backed, legacy)
│   ├── ontology.py         # GraphMeta + bounded views
│   ├── dataset.py          # RDF Dataset memory
│   ├── procedural_memory.py # ReasoningBank (being migrated)
│   ├── shacl_examples.py   # SHACL shape/query indexing
│   ├── _rlmpaper_compat.py # Protocol artifacts (manually maintained)
│   └── ...
├── rlm_runtime/            # (v2) Handwritten runtime package
│   ├── engine/             # DSPy RLM execution engine
│   ├── memory/             # SQLite-backed ReasoningBank
│   ├── tools/              # Bounded tool surface wrappers
│   ├── logging/            # Observability (trajectory logs, MLflow integration)
│   └── cli.py              # CLI entrypoint
├── rlmpaper/               # Git submodule (reference implementation)
├── docs/                   # Project documentation
│   ├── planning/trajectory_v2.md           # Master plan (v2, active)
│   ├── planning/trajectory.md              # Original plan (superseded)
│   ├── design/                             # Architecture & design
│   ├── tasks/                              # Implementation tasks
│   └── guides/                             # Usage guides
├── evals/                  # Evaluation framework
├── ontology/               # RDF/OWL ontologies (32 files)
├── tests/                  # Unit/integration/live tests
├── settings.ini            # nbdev configuration
└── pyproject.toml          # Build configuration
```

## Development Workflow

### Setup (First Time)

```bash
source ~/uvws/.venv/bin/activate
uv pip install fastcore claudette dialoghelper mistletoe rdflib sparqlx
```

### Working with nbdev Notebooks

**Edit notebooks in `nbs/`**, not generated Python files in `rlm/`.

**DO NOT EDIT**: `rlm/*.py` (auto-generated from notebooks)
**EXCEPTION**: `rlm/_rlmpaper_compat.py` (manually maintained protocol artifacts)

**DO EDIT**: `nbs/*.ipynb`, `docs/*.md`, `settings.ini`

#### nbdev Commands

```bash
nbdev_export             # Generate Python modules from notebooks
nbdev_test               # Run tests from notebooks
nbdev_docs               # Generate documentation website (_docs/)
nbdev_clean              # Strip metadata/outputs (for CI compatibility)
nbdev_prepare            # Run export + test + clean (CI check)
```

#### nbdev Directives

Use special comments in notebook cells to control nbdev behavior:

```python
#| export
# Exports this cell to the module file (e.g., rlm/core.py)

#| hide
# Hides this cell from documentation (but runs in tests)

#| eval: false
# Don't execute during nbdev_test (but show in docs)
# Use for: cells requiring external state, Solveit-specific code, expensive operations

#| default_exp core
# Declares which module this notebook exports to (first cell only)
```

#### Executing Notebooks with Outputs

For documentation notebooks (like `index.ipynb` or eval reports), you may want to show actual execution results:

```bash
# Execute notebook and capture outputs
nbdev exec_nb --path nbs/index.ipynb

# Or with jupyter-based exec_nb (alternative)
# exec_nb --dest nbs/index.ipynb nbs/index.ipynb
```

**Important**: Use `#| eval: false` for cells that depend on previous state, otherwise `nbdev_test` will fail when running cells in isolation:

```python
# Cell 1: Setup (runs in tests)
ns = {}
setup_dataset_context(ns)

#| eval: false
# Cell 2: Depends on ns from Cell 1 (skip in tests)
ns['mount_ontology']('ontology/prov.ttl', 'prov')
```

This allows:
- Outputs visible in rendered docs
- Tests pass (cells with eval: false are skipped)
- CI passes (notebooks remain "clean")

#### Documentation Generation

Documentation is generated by Quarto via `nbdev_docs`:

```bash
nbdev_docs  # Creates _docs/ directory with HTML

# Configuration files (auto-generated):
# - nbs/nbdev.yml    : Quarto project config
# - nbs/sidebar.yml  : Sidebar navigation
```

The `_docs/` directory is deployed to GitHub Pages by `.github/workflows/deploy.yaml`.

#### CI/CD Compatibility

GitHub Actions CI expects notebooks to be "clean" (no execution metadata). The CI runs:

```bash
nbdev_export  # Export modules
git diff --exit-code  # Fail if notebooks changed
```

**How to maintain compatibility:**

1. **For implementation notebooks** (00_core.ipynb, etc.):
   - Keep cells unexecuted (no outputs)
   - OR run `nbdev_clean` before committing
   - Tests run via `nbdev_test` (isolated cell execution)

2. **For documentation notebooks** (index.ipynb, eval reports):
   - Execute with `nbdev exec_nb` to show outputs
   - Mark stateful cells with `#| eval: false`
   - Run `nbdev_prepare` to verify CI will pass

3. **Common error**: "Notebooks and library are not in sync"
   - Cause: Notebook has execution metadata that nbdev_export would strip
   - Fix: Add `#| eval: false` to cells that depend on state, or run `nbdev_clean`

#### Common Workflows

**Adding a new module:**
```bash
# 1. Create notebook
jupyter notebook nbs/07_new_module.ipynb

# 2. Add to first cell:
#| default_exp new_module

# 3. Export functions with #| export
#| export
def my_function():
    """Docstring here."""
    pass

# 4. Generate module
nbdev_export
# Creates rlm/new_module.py

# 5. Test
nbdev_test --path nbs/07_new_module.ipynb
```

**Running examples with outputs:**
```bash
# Execute and capture outputs
nbdev exec_nb --path nbs/index.ipynb

# Regenerate docs
nbdev_docs

# Verify CI compatibility
nbdev_prepare

# Commit if all passes
git add nbs/index.ipynb README.md
git commit -m "Add executed examples to index"
```

**Updating documentation:**
```bash
# Edit markdown cells in notebooks
# ... make changes ...

# Regenerate docs
nbdev_docs

# Commit
git add nbs/*.ipynb _docs/
git commit -m "Update documentation"
```

## Architecture Decisions

### Non-Negotiable Invariants

These principles from the RLM paper must be preserved across all implementations:

1. **Context externalization** - Large context (graphs, results) stays in REPL; model sees bounded summaries
2. **REPL-first discovery** - Agent explores via bounded view functions before answering
3. **Recursive delegation** - Sub-LLM calls for meaning extraction; root model orchestrates
4. **Handles-not-dumps** - Results/graphs stored as handles; inspection via bounded views
5. **Bounded iteration** - Max iterations and call budgets enforced; fallback behaviors explicit

### v2 Architecture (DSPy + SQLite ReasoningBank)

**Execution Engine:**
- Migrating from claudette-backed `rlm_run()` to **DSPy RLM** with typed `SUBMIT`
- Custom `NamespaceCodeInterpreter` executes code in host Python with persistent state
- Tool-only access pattern: bounded view functions exposed, raw graphs hidden

**Query Construction Contract:**
Every run must produce structured output via `SUBMIT(sparql=..., answer=..., evidence=...)`:
- `sparql: str` - Exact executed query
- `answer: str` - Grounded answer
- `evidence: dict` - URIs used, result samples, handle summaries

**ReasoningBank (Procedural Memory):**
- SQLite-backed storage replacing JSON/in-memory store
- FTS5 BM25 retrieval (replaces `rank-bm25` dependency)
- Memory packs: JSONL files with stable IDs, committed to git
- Closed loop: retrieve → inject → run → judge → extract → store
- **Chain-of-Thought extension** (Phase 3.5):
  - Reasoning chain exemplars with curriculum levels (L1-L5)
  - Curriculum-aware retrieval (level-based prioritization)
  - Verification feedback via AGENT_GUIDE.md metadata
  - Quality threshold extraction from high-quality trajectories

**Five-Layer Context Injection:**
1. Sense card (~600 chars) - Compact ontology metadata with 100% URI grounding
2. Reasoning chain exemplars - Structured CoT examples with state tracking (optional, Phase 3.5)
3. Procedural memories - Retrieved strategies from SQLite
4. Ontology-specific recipes - Curated patterns (optional)
5. Base context - GraphMeta summary/stats

**Observability & Experiment Tracking:**
- **Dual logging**: JSONL trajectory logs (real-time debugging) + MLflow (structured analysis)
- **MLflow integration**: Parameters, metrics, tags, and artifacts for programmatic querying
- **DSPy callbacks**: Capture LLM calls, module execution, and tool usage
- **Memory event logging**: Track retrieval, extraction, judgment, and storage operations
- Optional custom tracking URIs for isolated experiment databases

See design documents in `docs/design/` for details.

### RLM Implementation Strategy

We **do not** directly use the rlmpaper package as a dependency because:

1. **Name conflict**: Both packages are named `rlm`
2. **LLM backend choice**: Migrating from claudette to DSPy RLM
3. **Solveit compatibility**: Need local REPL execution compatible with Solveit

Instead, we:
- **Follow rlmpaper's protocol** (prompts, types, parsing, iteration semantics)
- **Copy protocol artifacts** into `rlm/_rlmpaper_compat.py`
- **Reference rlmpaper** as a git submodule for consultation

### Key Dependencies

From `settings.ini`:
- `fastcore` - Fast.ai utilities
- `claudette` - Claude API wrapper (legacy backend)
- `dspy-ai` - DSPy framework (v2 backend)
- `dialoghelper` - Solveit inspection tools
- `mistletoe` - Markdown parsing
- `rdflib` - RDF graph manipulation
- `sparqlx` - SPARQL query execution

**Optional dependencies:**
- `mlflow` >= 2.17.0 - Experiment tracking and observability
  - Provides structured tracking, programmatic querying, artifact storage
  - Requires DSPy integration (mlflow.dspy.autolog)
  - Install: `uv pip install mlflow`
  - The system gracefully degrades if MLflow is not installed

## Observability and Experiment Tracking

The project provides comprehensive observability through dual logging systems:

### JSONL Trajectory Logs (Real-time)

Real-time event stream for debugging and inspection:

```python
from rlm_runtime.engine.dspy_rlm import run_dspy_rlm

result = run_dspy_rlm(
    "What is Activity?",
    "ontology/prov.ttl",
    log_path="trajectory.jsonl",  # JSONL event stream
    log_llm_calls=True             # Include LLM calls in log
)
```

**Logged events:**
- `session_start` / `session_end` - Run boundaries
- `module_start` / `module_end` - DSPy module execution
- `llm_call` / `llm_response` - LLM interactions
- `run_creation` / `trajectory_creation` - Memory backend provenance
- `memory_retrieval` / `memory_extraction` / `memory_storage` - Memory operations
- `trajectory_judgment` - Success/failure assessment

### MLflow Integration (Structured Analysis)

Structured experiment tracking for programmatic querying and comparison:

```python
# Basic MLflow tracking
result = run_dspy_rlm(
    "What is Activity?",
    "ontology/prov.ttl",
    enable_mlflow=True
)

# With experiment organization
result = run_dspy_rlm(
    "What is Activity?",
    "ontology/prov.ttl",
    enable_mlflow=True,
    mlflow_experiment="PROV Ontology Queries",
    mlflow_run_name="activity-discovery-v1",
    mlflow_tags={"experiment": "v2", "user": "researcher"}
)

# Custom SQLite tracking backend
result = run_dspy_rlm(
    "What is Activity?",
    "ontology/prov.ttl",
    enable_mlflow=True,
    mlflow_tracking_uri="sqlite:///experiments/mlflow.db"
)

# Query results programmatically
import mlflow
runs = mlflow.search_runs(
    filter_string="params.ontology = 'prov' AND metrics.converged = 1",
    order_by=["metrics.iteration_count ASC"]
)
```

**Logged data:**

- **Parameters** (searchable): `query`, `ontology`, `max_iterations`, `model`, `sub_model`, `has_memory`
- **Metrics** (aggregatable): `iteration_count`, `converged`, `memories_retrieved`, `memories_extracted`, `judgment_success`
- **Tags** (filterable): `ontology`, custom tags
- **Artifacts**: Trajectory JSONL, SPARQL queries, evidence JSON

**MLflow features:**
- Graceful degradation (warnings on failure, never crashes)
- Opt-in (disabled by default)
- Custom tracking URIs for isolated experiments
- Integration with DSPy autolog for optimizer traces
- UI available via `mlflow ui` command

See `rlm_runtime/logging/mlflow_integration.py` for implementation details.

## Testing

Use **inline cell testing** in notebooks, not separate test files.

```bash
# Ensure dependencies are installed first
source ~/uvws/.venv/bin/activate
uv pip install fastcore claudette dialoghelper mistletoe rdflib sparqlx

# Run tests
nbdev_test                              # All notebook tests
nbdev_test --path nbs/00_core.ipynb    # Specific notebook
```

### Solveit-Specific Test Cells

Some test cells require the **Solveit runtime environment** (`dialoghelper.inspecttools` needs `__msg_id` in scope). These will fail when run outside Solveit.

**Mark Solveit-specific tests with `#| eval: false`**:

```python
#| eval: false
# Test symget (requires Solveit environment)
test_dict = {'a': 1, 'b': 2}
symset('test_dict')  # Fails outside Solveit: "Could not find __msg_id"
```

This prevents execution during `nbdev_test` while keeping the example visible in documentation.

## Git Submodules

The `rlmpaper/` directory is a git submodule pointing to the reference implementation:

```bash
# Initialize submodules (if not already done)
git submodule update --init --recursive

# Update submodule to latest
cd rlmpaper
git pull origin main
cd ..
git add rlmpaper
git commit -m "Update rlmpaper submodule"
```

## Documentation

The project follows a documentation-driven approach:

1. **Trajectory document** (`docs/planning/trajectory_v3.md`) - Master plan (active, supersedes v2)
2. **Design documents** (`docs/design/`) - Architecture and patterns:
   - `reasoningbank-sqlite-architecture.md` - SQLite memory store design
   - `claudette-to-dspy-migration.md` - DSPy migration plan
   - `dspy-migration-system-analysis.md` - Module-by-module impact
   - `ontology-query-construction-with-rlm-reasoningbank-dspy.md` - Query construction requirements
   - `hybrid-nbdev-runtime-refactor.md` - Hybrid codebase approach
   - `instruction-tuning-via-reasoning-chains.md` - Chain-of-Thought instruction tuning design
3. **Task documents** (`docs/tasks/`) - Specific implementation tasks:
   - `00-core-alignment.md` - Core RLM alignment with rlmpaper protocol
   - `04-shacl-summary.md` - SHACL integration implementation
   - `05-cot-instruction-tuning.md` - Chain-of-Thought instruction tuning implementation
4. **Usage guides** (`docs/guides/`) - How-to documentation
5. **Experiment documentation** (`experiments/*/README.md`) - Experiment designs and results
6. **Notebook markdown cells** - Inline documentation
7. **Docstrings** - Fast.ai style docstrings in exported functions

### Documentation Philosophy

When adding new documentation:

1. **Planning docs** (`docs/planning/`) - Major architectural changes and master plans
2. **Design docs** (`docs/design/`) - Significant design decisions and architecture
3. **Task docs** (`docs/tasks/`) - Implementation stage summaries (what was built, how it works)
4. **Guides** (`docs/guides/`) - Practical how-to documentation for users
5. **Experiments** (`experiments/*/`) - Experiment designs, results, and analysis
6. **Archive** (`docs/archive/`) - Completed session notes and outdated content

Keep documentation:
- **Concise** - Remove redundancy, focus on key information
- **Actionable** - Include concrete examples and code snippets
- **Current** - Archive or update outdated content
- **Cross-referenced** - Link to related documents

## Code Style

Follow [fast.ai style guide](https://docs.fast.ai/dev/style.html):
- Short functions with strong names
- Docstrings, not inline comments
- Explicit return values (e.g., `"Stored 120 rows in 'res'"`)
- Simple data structures (dict, list, dataclasses)
- `**kwargs` only for extensibility

## Evaluation Framework

The `evals/` directory contains a task-based evaluation framework for RLM performance:

```
evals/
├── tasks/                   # YAML task definitions
│   ├── regression/          # Must-pass tests (100% pass rate)
│   ├── entity_discovery/    # Entity search capabilities
│   ├── hierarchy/           # Class hierarchy navigation
│   ├── memory/              # Dataset memory persistence
│   └── negative/            # Error handling, hallucination detection
├── graders/                 # Grading logic
│   ├── answer_contains.py   # String matching
│   ├── tool_called.py       # Tool usage verification
│   ├── convergence.py       # Iteration limit checks
│   └── groundedness.py      # Evidence-based grading
├── runners/                 # Task execution
│   └── task_runner.py       # TaskRunner, EvalResult
├── results/                 # JSON outputs (gitignored, generated)
└── config.yaml              # Framework configuration
```

### Running Evals

```bash
# List available tasks
python -m evals.cli list

# Run all tasks
python -m evals.cli run

# Run specific category
python -m evals.cli run 'regression/*'

# Generate report
python -m evals.cli report evals/results
```

### Eval Reports in Notebooks

Eval reports are generated in notebooks (`nbs/eval_reports.ipynb`) for GitHub Pages deployment:

1. Run evals → generate `evals/results/*.json`
2. Create notebook that loads results and visualizes
3. Execute notebook with `nbdev exec_nb`
4. Deploy to GitHub Pages via `nbdev_docs`

See section "Executing Notebooks with Outputs" for workflow details.

## Current Work (v3 Trajectory)

The project is implementing trajectory v3. See `docs/planning/trajectory_v3.md` for the full roadmap.

**Status:** Phases 1-3 complete, Phase 3.5 complete, Phases 4-7 planned

**Completed:**
- ✅ Phase 1: Foundation correctness (dataset snapshots, tool bounding)
- ✅ Phase 2: Remote SPARQL integration (UniProt endpoint support)
- ✅ Phase 3: Procedural memory model (ReasoningBank, sense cards, extraction)
- ✅ Phase 3.5: Chain-of-Thought instruction tuning (exemplars, verification, curriculum)
- ✅ v1 work: Ontology handles, GraphMeta, bounded views, SHACL indexing, eval framework

**Phase 3.5 Highlights (Instruction Tuning):**
- Reasoning chain exemplars with curriculum levels (L1-L5)
- AGENT_GUIDE.md parsing for verification feedback
- Domain/range constraint checking and anti-pattern detection
- Curriculum-aware retrieval (level-based prioritization)
- E-RC-001 experiment: baseline vs schema vs exemplar3 conditions
- 57 tests passing, all features backward compatible

**Planned (v3 Phases):**
- 🔄 Phase 4: Eval harness + learning metrics + representation ablation
- 🔄 Phase 5: Human feedback integration + curriculum runner
- 🔄 Phase 6: Retire claudette and stabilize
- 🔄 Phase 7: SHACL-driven query construction (template-guided)

**Research Dimensions (Phase 4):**
1. **Affordance granularity ablation** - Which specific knowledge representations help?
2. **Reasoning complexity boundaries** - Where do LM capabilities end? What tools extend them?
3. **Learning dynamics** - Does the system improve with experience?

## References

- [rlmpaper repository](https://github.com/alexzhang13/rlm) - Reference implementation
- [nbdev documentation](https://nbdev.fast.ai/) - Literate programming framework
- [claudette documentation](https://claudette.answer.ai/) - Claude API wrapper
- [fast.ai style guide](https://docs.fast.ai/dev/style.html) - Code conventions
