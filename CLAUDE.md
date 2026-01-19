# Project Context for Claude Code

This document provides context about this project's development environment and conventions for AI assistants working on the codebase.

## Project Overview

This is an nbdev-based project implementing RLM (Recursive Language Models) integration with RDF ontologies and SPARQL queries. The goal is to enable progressive disclosure over large RDF graphs while staying faithful to the rlmpaper protocol but using claudette as the LLM backend.

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
├── nbs/                    # nbdev notebooks (source of truth)
│   ├── 00_core.ipynb       # Core RLM implementation
│   ├── 01_repl_views.ipynb # (planned) Bounded view primitives
│   └── ...
├── rlm/                    # Generated Python library (DO NOT EDIT)
│   ├── core.py             # Generated from 00_core.ipynb
│   ├── _rlmpaper_compat.py # Protocol artifacts (manually maintained)
│   └── ...
├── rlmpaper/               # Git submodule (reference implementation)
├── docs/                   # Project documentation
│   ├── planning/trajectory.md              # Master plan
│   ├── tasks/00-core-alignment.md          # Implementation tasks
│   ├── design/                             # Architecture & design
│   ├── guides/                             # Usage guides
│   └── ...
├── ontology/               # RDF/OWL ontologies
├── settings.ini            # nbdev configuration
└── pyproject.toml          # Build configuration
```

## Development Workflow

### Setup (First Time)

```bash
source ~/uvws/.venv/bin/activate
uv pip install fastcore claudette dialoghelper mistletoe rdflib sparqlx
```

### nbdev (installed in ~/uvws/.venv)

**Edit notebooks in `nbs/`**, not generated Python files in `rlm/`.

```bash
nbdev_export  # Generate Python modules from notebooks
nbdev_test    # Run tests from notebooks
```

**DO NOT EDIT**: `rlm/*.py` (auto-generated from notebooks)
**EXCEPTION**: `rlm/_rlmpaper_compat.py` (manually maintained protocol artifacts)

**DO EDIT**: `nbs/*.ipynb`, `docs/*.md`, `settings.ini`

## Architecture Decisions

### RLM Implementation Strategy

We **do not** directly use the rlmpaper package as a dependency because:

1. **Name conflict**: Both packages are named `rlm`
2. **LLM backend choice**: We use **claudette** instead of rlmpaper's anthropic/openai clients
3. **Solveit compatibility**: We need local REPL execution compatible with Solveit

Instead, we:
- **Follow rlmpaper's protocol** (prompts, types, parsing, iteration semantics)
- **Replace LLM clients** with claudette `Chat`
- **Copy protocol artifacts** into `rlm/_rlmpaper_compat.py`
- **Reference rlmpaper** as a git submodule for consultation

See `docs/00-core-rlmpaper-alignment.md` for details.

### Key Dependencies

From `settings.ini`:
- `fastcore` - Fast.ai utilities
- `claudette` - Claude API wrapper (our LLM backend)
- `dialoghelper` - Solveit inspection tools
- `mistletoe` - Markdown parsing
- `rdflib` - RDF graph manipulation
- `sparqlx` - SPARQL query execution

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

1. **Trajectory document** (`docs/planning/trajectory.md`) - Master plan
2. **Task documents** (`docs/tasks/`) - Specific implementation tasks
3. **Design documents** (`docs/design/`) - Architecture and patterns
4. **Usage guides** (`docs/guides/`) - How-to documentation
5. **Notebook markdown cells** - Inline documentation
6. **Docstrings** - Fast.ai style docstrings in exported functions

## Code Style

Follow [fast.ai style guide](https://docs.fast.ai/dev/style.html):
- Short functions with strong names
- Docstrings, not inline comments
- Explicit return values (e.g., `"Stored 120 rows in 'res'"`)
- Simple data structures (dict, list, dataclasses)
- `**kwargs` only for extensibility

## Current Work

See `docs/00-core-rlmpaper-alignment.md` for the current task: aligning `nbs/00_core.ipynb` with rlmpaper protocol while keeping claudette as the LLM backend.

## References

- [rlmpaper repository](https://github.com/alexzhang13/rlm) - Reference implementation
- [nbdev documentation](https://nbdev.fast.ai/) - Literate programming framework
- [claudette documentation](https://claudette.answer.ai/) - Claude API wrapper
- [fast.ai style guide](https://docs.fast.ai/dev/style.html) - Code conventions
