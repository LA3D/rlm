# RLM Test Suite

Comprehensive testing campaign for the RLM (Recursive Language Models) system with ontology and SPARQL integration.

## Overview

This test suite validates:

1. **Recently implemented features** (Stages 1.5, 2.5, & 3)
2. **Cross-component integration** (Dataset + Memory + SPARQL)
3. **Trajectory requirements** from `docs/planning/trajectory.md` (Stage 6)

## Test Organization

```
tests/
├── unit/                    # Unit tests for individual components
│   ├── test_sparql_handles.py       # SPARQLResultHandle, res_sample
│   ├── test_session_tracking.py     # Session ID generation & persistence
│   └── test_memory_store.py         # MemoryStore CRUD operations
│
├── integration/             # Cross-component integration tests
│   ├── test_dataset_memory.py       # Dataset + Memory + Session ID flow (P0)
│   ├── test_sparql_dataset.py       # SPARQL + Work graphs (P0)
│   ├── test_memory_closed_loop.py   # Procedural memory cycle (P0)
│   └── test_full_stack.py           # End-to-end smoke tests (P0)
│
├── trajectory/              # Stage 6 scenario tests (future)
│   ├── test_prov_trajectories.py
│   ├── test_dataset_trajectories.py
│   └── test_procedural_trajectories.py
│
├── live/                    # Tests requiring API calls (future)
│   └── test_live_memory_loop.py
│
└── conftest.py              # Shared fixtures
```

## Running Tests

### Quick Start

```bash
# Activate environment
source ~/uvws/.venv/bin/activate

# Install test dependencies
uv pip install pytest pytest-cov

# Run all tests (excluding live API tests)
pytest tests/ --ignore=tests/live/

# Run specific test categories
pytest tests/unit/           # Unit tests only
pytest tests/integration/    # Integration tests only
pytest tests/trajectory/     # Trajectory tests only
```

### Test Markers

Tests are marked by priority and category:

```bash
# P0 Critical Path Tests (blocking)
pytest -m p0

# P1 High Priority Tests (quality)
pytest -m p1

# P2 Medium Priority Tests (hardening)
pytest -m p2

# By category
pytest -m unit
pytest -m integration
pytest -m trajectory
```

### Coverage Reports

```bash
# Generate coverage report
pytest tests/ --cov=rlm --cov-report=html --ignore=tests/live/

# View report
open htmlcov/index.html
```

### Verbose Output

```bash
# Detailed output with test names
pytest tests/ -v

# Very verbose with full diff
pytest tests/ -vv

# Show local variables on failure
pytest tests/ -l
```

## Test Priority Levels

### P0: Critical Path (Blocking)

**Must pass before deployment**

- `test_dataset_memory.py::TestSessionIDPropagation` - Session ID flows correctly
- `test_sparql_dataset.py::TestSPARQLWorkGraphIntegration` - Work graphs created with provenance
- `test_memory_closed_loop.py::TestMemoryClosedLoopCycle` - Memory loop completes
- `test_full_stack.py::TestFullStackIntegration::test_end_to_end_minimal` - Smoke test

**Run with:**
```bash
pytest tests/integration/ -v
```

### P1: High Priority (Quality)

**Should complete for production quality**

- Session ID JSON roundtrip
- Trajectory artifact bounds
- Dataset snapshot roundtrip
- LLM JSON parsing edge cases

### P2: Medium Priority (Hardening)

**Nice to have for robustness**

- View function polymorphism
- Error recovery
- BM25 retrieval relevance
- Edge case handling

## Test Fixtures

Common fixtures are defined in `tests/conftest.py`:

### Dataset Fixtures

- `empty_dataset` - Empty RDF Dataset
- `dataset_meta` - DatasetMeta with empty dataset
- `dataset_with_data` - DatasetMeta with sample triples

### SPARQL Fixtures

- `select_result_handle` - SELECT result with 3 rows
- `ask_result_handle` - ASK result (True)
- `construct_result_handle` - CONSTRUCT result with 2 triples

### Memory Fixtures

- `empty_memory_store` - Empty MemoryStore
- `memory_store_with_items` - Store with 2 sample memories
- `memory_item_sample` - Single MemoryItem

### Utility Fixtures

- `tmp_test_dir` - Temporary directory for test artifacts
- `prov_ontology_path` - Path to PROV ontology (if available)
- `test_namespace` - Empty namespace dict for REPL simulation

## Writing New Tests

### Unit Test Template

```python
"""Unit tests for <module>."""

import pytest
from rlm.<module> import <function>


class TestFeatureName:
    """Tests for <feature>."""

    def test_basic_usage(self):
        """Feature works in basic case."""
        result = function()
        assert result is not None

    def test_edge_case(self):
        """Feature handles edge case."""
        result = function(edge_input)
        assert result == expected
```

### Integration Test Template

```python
"""Integration tests for <component1> + <component2>."""

import pytest
from rlm.component1 import func1
from rlm.component2 import func2


class TestCrossComponentFlow:
    """Tests data flow between components."""

    def test_component1_to_component2(self, fixture1, fixture2):
        """Data flows correctly from component1 to component2."""
        # Setup
        data = func1(fixture1)

        # Execute
        result = func2(data, fixture2)

        # Verify
        assert result.contains_expected_data
```

## Success Criteria

The test campaign is **successful** when:

- ✅ All P0 tests pass (4 critical path tests)
- ✅ ≥80% of P1 tests pass (at least 7 of 9 high-priority tests)
- ✅ Test suite runs in <5 minutes (excluding live API tests)
- ✅ Zero regressions in existing tests
- ✅ Coverage ≥70% for new modules

## Current Test Coverage

### Implemented Tests

**Unit Tests:**
- ✅ `test_sparql_handles.py` - 25+ tests for SPARQLResultHandle
- ✅ `test_session_tracking.py` - 15+ tests for session ID tracking
- ✅ `test_memory_store.py` - 25+ tests for MemoryStore

**Integration Tests (P0):**
- ✅ `test_dataset_memory.py` - 10+ tests for Dataset + Memory
- ✅ `test_sparql_dataset.py` - 10+ tests for SPARQL + Dataset
- ✅ `test_memory_closed_loop.py` - 10+ tests for memory loop
- ✅ `test_full_stack.py` - 5+ tests for end-to-end workflows

**Total: 100+ tests implemented**

### Coverage Gaps (Future Work)

- ❌ Trajectory tests (Stage 6 scenarios)
- ❌ Live API tests with real LLM calls
- ❌ Error recovery edge cases
- ❌ Performance/load tests

## Troubleshooting

### Test Failures

**Import Errors:**
```bash
# Ensure dependencies installed
source ~/uvws/.venv/bin/activate
uv pip install fastcore claudette dialoghelper mistletoe rdflib sparqlx rank-bm25
```

**Missing Fixtures:**
```bash
# Check conftest.py is in tests/ directory
ls tests/conftest.py
```

**PROV Ontology Tests Skipped:**
```bash
# PROV ontology tests skip if ontology/prov.ttl not found
# This is expected if ontology files not yet added
```

### Performance Issues

If tests are slow:

1. Run unit tests only: `pytest tests/unit/`
2. Skip trajectory tests: `pytest tests/ --ignore=tests/trajectory/`
3. Run with `-n auto` for parallel execution (requires pytest-xdist)

### Debugging Tests

```bash
# Drop into debugger on failure
pytest tests/ --pdb

# Stop on first failure
pytest tests/ -x

# Show print statements
pytest tests/ -s
```

## Continuous Integration

### GitHub Actions (Future)

```yaml
# .github/workflows/test.yml
name: Test Suite
on: [push, pull_request]
jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v2
      - name: Run tests
        run: |
          pytest tests/ --ignore=tests/live/ --cov=rlm
```

### Pre-commit Hook (Future)

```bash
# .git/hooks/pre-commit
#!/bin/bash
pytest tests/unit/ -x || exit 1
```

## References

- [Testing Campaign Plan](../docs/testing-campaign-plan.md)
- [pytest Documentation](https://docs.pytest.org/)
- [Coverage.py Documentation](https://coverage.readthedocs.io/)
- [nbdev Testing](https://nbdev.fast.ai/tutorials/tutorial.html#tests)

## Contributing

When adding new features:

1. Write tests **before** implementation (TDD)
2. Ensure P0 tests pass before merging
3. Update this README with new test files
4. Add fixtures to conftest.py for reuse

## Questions?

See test docstrings for detailed test descriptions and expected behavior.
