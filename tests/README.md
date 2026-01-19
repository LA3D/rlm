# RLM Test Suite

Comprehensive testing for the RLM (Recursive Language Models) system with ontology, SPARQL, and procedural memory integration.

## Test Organization

The test suite is organized by test type and API dependency:

```
tests/
├── helpers/                 # Test utilities and assertions
│   ├── protocol_assertions.py   # RLM protocol invariant checks
│   └── __init__.py
│
├── unit/                    # Deterministic unit tests (NO API calls)
│   ├── test_shacl_examples.py   # SHACL indexing and detection
│   ├── test_sparql_handles.py   # SPARQL result handles
│   ├── test_session_tracking.py # Session ID generation
│   └── test_memory_store.py     # MemoryStore CRUD operations
│
├── integration/             # Deterministic integration tests (NO API calls)
│   ├── test_memory_closed_loop.py   # Procedural memory cycle (mocked)
│   ├── test_sparql_dataset.py       # SPARQL + Dataset integration
│   ├── test_full_stack.py           # End-to-end smoke tests (mocked)
│   └── test_dataset_memory.py       # Dataset + Memory integration
│
├── live/                    # Live tests (REQUIRE API key)
│   ├── test_quick_e2e.py                    # Fast sanity check
│   ├── test_rlm_ontology_integration.py     # RLM + ontology w/ assertions
│   ├── test_rlm_with_memory.py              # RLM + dataset memory
│   ├── test_rlm_with_memory_closed_loop.py  # Full memory loop
│   ├── test_judge_trajectory_live.py        # Trajectory judging
│   ├── test_extract_memories_live.py        # Memory extraction
│   ├── test_llm_query_final_var.py          # FINAL_VAR patterns
│   ├── test_comprehensive_final.py          # Comprehensive features
│   ├── test_final_var_executable.py         # FINAL_VAR as function
│   ├── test_final_var_as_function.py        # FINAL_VAR testing
│   ├── test_namespace_persistence.py        # Namespace persistence
│   └── test_progressive_disclosure_minimal.py # Progressive disclosure
│
└── conftest.py              # Shared fixtures
```

## Running Tests

### CI-Safe Tests (No API Calls Required)

These tests are **fast and deterministic** - suitable for CI/CD pipelines:

```bash
# Activate environment
source ~/uvws/.venv/bin/activate

# Install test dependencies
uv pip install pytest pytest-cov

# Run all deterministic tests (unit + integration)
pytest tests/ --ignore=tests/live/ -v

# Run unit tests only
pytest tests/unit/ -v

# Run integration tests only
pytest tests/integration/ -v

# With coverage
pytest tests/ --ignore=tests/live/ --cov=rlm --cov-report=html
```

**These tests should always pass without an API key.**

### Live Tests (Require API Key)

These tests make **real API calls** to Claude and are **opt-in only**:

```bash
# Set API key
export ANTHROPIC_API_KEY=your-key-here

# Run all live tests
pytest tests/live/ -v

# Run specific live test file
pytest tests/live/test_quick_e2e.py -v

# Run with protocol assertions
pytest tests/live/test_rlm_ontology_integration.py -v
```

**Live tests are marked with `@pytest.mark.live`** and are automatically **skipped** in CI unless the API key is present.

## Protocol Assertions

All live RLM tests verify **protocol invariants** using helper functions from `tests/helpers/protocol_assertions.py`:

### Available Assertions

- `assert_code_blocks_present(iterations, min_blocks=1)` - Verifies REPL usage
- `assert_converged_properly(answer, iterations)` - Verifies FINAL/FINAL_VAR convergence
- `assert_bounded_views(iterations, max_output_chars=10000)` - Verifies no full graph dumps
- `assert_grounded_answer(answer, iterations, min_score=0.3)` - Verifies answer grounding
- `assert_tool_called(iterations, function_pattern, at_least=1)` - Verifies tool usage

### Example Usage

```python
from tests.helpers.protocol_assertions import (
    assert_code_blocks_present,
    assert_converged_properly,
    assert_bounded_views,
)

# After running rlm_run()
answer, iterations, ns = rlm_run(query, context, ns=ns, max_iters=5)

# Verify protocol invariants
assert_code_blocks_present(iterations, min_blocks=1)
assert_converged_properly(answer, iterations)
assert_bounded_views(iterations)
```

## Test Categories

### Unit Tests

**Fast, isolated component tests with no external dependencies:**

- SPARQL result handle operations
- Session ID generation and persistence
- Memory store CRUD operations
- SHACL shape detection and indexing

### Integration Tests

**Cross-component tests with mocked LLM calls:**

- Dataset + Memory integration
- SPARQL + Work graphs
- Procedural memory cycle (extract, judge, store)
- Full stack workflows

### Live Tests

**End-to-end tests with real LLM calls:**

- RLM + ontology exploration
- RLM + dataset memory integration
- Memory closed loop (retrieve, inject, interact, extract, store)
- Trajectory judging and memory extraction
- Progressive disclosure patterns

## Running Specific Test Scenarios

### Quick Smoke Test

```bash
# Fast sanity check (requires API key)
ANTHROPIC_API_KEY=... pytest tests/live/test_quick_e2e.py -v
```

### Protocol Compliance Tests

```bash
# Verify RLM follows protocol invariants
ANTHROPIC_API_KEY=... pytest tests/live/test_rlm_ontology_integration.py -v
```

### Memory Loop Tests

```bash
# Test full procedural memory closed loop
ANTHROPIC_API_KEY=... pytest tests/live/test_rlm_with_memory_closed_loop.py -v
```

### Deterministic Tests Only

```bash
# Run without API key (CI-safe)
pytest tests/unit/ tests/integration/ -v
```

## Test Fixtures

Common fixtures are defined in `tests/conftest.py`:

### Dataset Fixtures

- `empty_dataset` - Empty RDF Dataset
- `dataset_meta` - DatasetMeta with empty dataset
- `dataset_with_data` - DatasetMeta with sample triples

### Memory Fixtures

- `empty_memory_store` - Empty MemoryStore
- `memory_store_with_items` - Store with sample memories
- `memory_item_sample` - Single MemoryItem

### Ontology Fixtures

- `prov_ontology_path` - Path to PROV ontology (returns Path object)

### Utility Fixtures

- `tmp_test_dir` - Temporary directory for test artifacts
- `test_namespace` - Empty namespace dict for REPL simulation

## Success Criteria

### CI Tests (Deterministic)

✅ All unit tests pass
✅ All integration tests pass
✅ Test suite runs in <2 minutes
✅ Coverage ≥70% for core modules

### Live Tests (Opt-in)

✅ Quick E2E test passes
✅ Protocol invariants hold across all tests
✅ Memory closed loop completes successfully
✅ No hallucinations detected (grounding checks)

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
```

### Live Test Template

```python
"""Live tests for <feature> with real LLM calls."""

import pytest
from rlm.core import rlm_run
from tests.helpers.protocol_assertions import (
    assert_code_blocks_present,
    assert_converged_properly,
)


@pytest.mark.live
class TestFeatureLive:
    """Live tests for <feature>."""

    def test_feature_works(self):
        """Feature works with real LLM."""
        answer, iterations, ns = rlm_run(query, context, max_iters=5)

        # Protocol invariants
        assert_code_blocks_present(iterations)
        assert_converged_properly(answer, iterations)

        # Feature-specific checks
        assert 'expected_result' in answer
```

## Troubleshooting

### Import Errors

```bash
# Ensure all dependencies are installed
source ~/uvws/.venv/bin/activate
uv pip install fastcore claudette dialoghelper mistletoe rdflib sparqlx rank-bm25
```

### Live Tests Failing

```bash
# Check API key is set
echo $ANTHROPIC_API_KEY

# Verify network connectivity
curl -I https://api.anthropic.com/
```

### Skipped Tests

If tests are being skipped:

- **"PROV ontology not available"** - Expected if `ontology/prov.ttl` doesn't exist
- **"SIO ontology not available"** - Expected if `ontology/sio/` doesn't exist
- **Live tests skipped** - Expected if `ANTHROPIC_API_KEY` not set

### Debugging

```bash
# Drop into debugger on failure
pytest tests/ --pdb

# Stop on first failure
pytest tests/ -x

# Show print statements
pytest tests/ -s

# Very verbose output
pytest tests/ -vv
```

## Environment Variables

- `ANTHROPIC_API_KEY` - Required for live tests (tests/live/)
- No API key needed for unit/integration tests

## Continuous Integration

### GitHub Actions

The CI pipeline should run:

```bash
# In CI (no API key)
pytest tests/ --ignore=tests/live/ --cov=rlm -v
```

### Local Pre-commit

Before committing:

```bash
# Quick check (deterministic tests only)
pytest tests/unit/ tests/integration/ -x
```

## References

- [pytest Documentation](https://docs.pytest.org/)
- [RLM Protocol Specification](../docs/design/rlm-protocol.md)
- [Procedural Memory Design](../docs/design/procedural-memory.md)
- [Testing Best Practices](https://docs.pytest.org/en/stable/goodpractices.html)

## Contributing

When adding new features:

1. **Write unit tests first** (deterministic, no API calls)
2. **Add integration tests** if multiple components interact
3. **Add live tests** if LLM behavior needs verification
4. **Use protocol assertions** in all RLM live tests
5. **Update this README** if new test categories are added

## Questions?

See individual test file docstrings for detailed test descriptions and expected behavior.
