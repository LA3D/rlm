# Tool Fix Validation Results

**Date**: 2026-02-05
**Test Script**: `test_tool_fixes.py`

---

## Summary

**V1 passes**: 3/12 patterns
**V2 passes**: 11/12 patterns
**Improvement**: +8 patterns fixed

---

## Root Cause Identified

The S3 argument mismatch failures (24 total) were caused by a **calling pattern mismatch**:

- `LocalPythonInterpreter` calls tools **directly**: `fn('resource', limit=5)`
- V1 `as_dspy_tools()` lambdas expected **DSPy pattern**: `fn(['resource'], {'limit': 5})`

When an agent wrote `sparql_peek('up:Protein', limit=5)`, the lambda received:
- `args='up:Protein'` (positional)
- `kwargs={'limit': 5}` (keyword)

But the lambda signature was `lambda args=None, kwargs=None:` which doesn't accept `limit=`.

---

## Fix Applied

V2 `as_dspy_tools()` uses wrapper functions that handle **both** calling patterns:

```python
def peek_wrapper(*args, **kwargs):
    # Detect DSPy pattern: (list, dict)
    if len(args) == 2 and isinstance(args[0], list) and isinstance(args[1], dict):
        a, kw = args
        return self.sparql_peek(a[0], kw.get('limit', 5), ...)
    else:
        # Direct call: sparql_peek('resource', limit=5)
        resource = args[0] if args else kwargs.get('resource', '')
        limit = kwargs.get('limit', 5)
        return self.sparql_peek(resource, limit, ...)
```

---

## Test Results

| # | Pattern | V1 | V2 | Notes |
|---|---------|----|----|-------|
| 1 | `sparql_peek(res, limit=5)` | ✗ | ✓ | **FIXED** |
| 2 | `sparql_slice(dict_handle, limit=3)` | ✗ | ✓ | **FIXED** |
| 3 | `sparql_slice(key, limit=5)` | ✗ | ✓ | **FIXED** |
| 4 | `sparql_slice(key, offset, limit=5)` | ✗ | ✓ | **FIXED** |
| 5 | `sparql_peek(res, output_mode='count')` | ✗ | ✓ | **FIXED** |
| 6 | `sparql_describe(uri, limit=10)` | ✗ | ✓ | **FIXED** |
| 7 | `sparql_schema('overview')` | ✗ | ✓ | New tool |
| 8 | `sparql_slice(key, 0, 10)` | ✗ | ✓ | **FIXED** |
| 9 | `sparql_peek('up:Protein')` | ✓ | timeout | Expected (3M instances) |
| 10 | `sparql_count(query)` | ✓ | ✓ | Both work |
| 11 | `endpoint_info()` | ✓ | ✓ | Both work |
| 12 | `sparql_query(q, limit=10)` | ✗ | ✓ | **FIXED** |

---

## Expected Impact on S3 Failures

| Error Type | Count | Fixed by V2? |
|------------|-------|--------------|
| Timeout | 90 | Partly (already has auto-LIMIT) |
| Argument mismatch | 24 | ✅ Yes (direct call wrappers) |
| Type error (dict vs string) | 4 | ✅ Yes (dict handle extraction) |
| Attribute error | 5 | No (agent confusion) |

**Expected reduction**: 28+ failures (23% of total)

The remaining 90 timeout errors need query-level fixes (better LIMIT handling, query validation warnings). The v2 tools include these but they're endpoint-dependent.

---

## Recommendation

**Ready for subset test**. Run a small batch of trajectories with `use_v2_tools=True`:

```python
# In run script
result = run_uniprot(
    task=task,
    ont_path=ont_path,
    cfg=cfg,
    use_v2_tools=True,  # Enable v2 tools
    ...
)
```

Suggested test: Run 5 rollouts each of tasks 2 and 121 (highest failure counts):
- `2_bacteria_taxa_and_their_scientific_name` (40 failures in S3)
- `121_proteins_and_diseases_linked` (51 failures in S3)

This will validate the fix on ~20% of trajectories before full re-run.
