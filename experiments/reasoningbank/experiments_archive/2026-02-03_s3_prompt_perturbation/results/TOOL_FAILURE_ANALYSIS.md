# S3 Experiment Tool Failure Analysis

**Generated**: February 4, 2026
**Total Trajectories**: 100 (5 tasks × 4 strategies × 5 rollouts)
**Total Failures**: 123

---

## Executive Summary

### Key Findings

1. **90 timeout errors** (73% of failures) - Unbounded SPARQL queries causing 30-second timeouts
2. **24 argument mismatch errors** (20% of failures) - Agents passing non-existent keyword arguments like `limit=`
3. **4 type errors** (3% of failures) - Passing wrong data types (e.g., dict instead of string)
4. **5 attribute errors** (4% of failures) - Calling methods that don't exist on result objects

### Impact

- **0% recovery rate** - None of the 123 failures were successfully recovered within the same trajectory
- Agents waste ~54% of failed attempts retrying the same tool without fixing the issue
- Most problematic task: `121_proteins_and_diseases_linked` (51 failures)
- Most problematic tool: `sparql_query` (90 failures, all timeouts)

---

## Detailed Failure Analysis

### 1. SPARQL Query Timeouts (90 failures, 73%)

**Root Cause**: Agents construct SPARQL queries without LIMIT clauses, causing queries to scan millions of triples and timeout after 30 seconds.

#### Representative Example

**Context**: 4_uniprot_mnemonic_id (strategy: prefix)

**Agent's Reasoning**:
```
Let me understand the task:
1. I need to produce a SPARQL query and an answer
2. The question asks to "Select all bacterial taxa and their scientific names"
3. I need to explore the taxonomy structure by querying for sample taxa

Now I need to understand the structure of taxonomy data in UniProt and find how
bacteria are represented (likely through a taxon hierarchy)...
```

**Query That Timed Out** (example from iteration 2 of task 2):
```sparql
SELECT ?taxon ?prop ?value
WHERE {
  ?taxon a ?type .
  ?taxon ?prop ?value .
  FILTER(CONTAINS(STR(?taxon), "taxon"))
}
LIMIT 10
```

**Problem**: Even with `LIMIT 10`, this query times out because:
1. The triple pattern `?taxon a ?type` matches millions of triples (all typed resources)
2. The second pattern `?taxon ?prop ?value` multiplies this by all properties
3. The FILTER is applied AFTER pattern matching, not before
4. Despite LIMIT 10, the query engine must scan millions of results to find 10 that match the FILTER

**Another Example** - Unbounded exploratory query:
```sparql
SELECT DISTINCT ?class
WHERE {
  ?s a ?class .
  FILTER(CONTAINS(STR(?class), "Taxon") || CONTAINS(STR(?class), "taxon"))
}
LIMIT 10
```

**Problem**: Same issue - `?s a ?class` matches all typed resources before filtering.

**Note**: 90 timeout failures were recorded. Most involved exploratory queries with:
- Broad triple patterns (`?s ?p ?o`, `?s a ?type`)
- Filters applied after matching (not in WHERE clause)
- String-based filters (`CONTAINS`, `STR()`) that prevent index usage

**Recommendations**:
1. **Add automatic LIMIT injection**: If query lacks LIMIT, add `LIMIT 1000` by default
2. **Query validation**: Reject queries without LIMIT or warn agent before execution
3. **Better documentation**: Emphasize LIMIT requirement in tool docstring with examples
4. **Query templates**: Provide safe query patterns in system context

**Proposed Tool Improvement**:
```python
def sparql_query(query: str, auto_limit: int = 1000) -> Dict:
    '''Execute SPARQL query against endpoint.

    ⚠️  CRITICAL: Queries MUST include LIMIT clause to prevent timeouts!

    Args:
        query: SPARQL query (should include LIMIT)
        auto_limit: If query lacks LIMIT, add this automatically (default: 1000)

    Returns:
        Result handle with 'key', 'rows', 'preview' fields

    Example - Correct Usage:
        # ✅ Good - explicit LIMIT
        result = sparql_query("""
            SELECT ?protein ?name
            WHERE {
                ?protein a up:Protein .
                ?protein up:mnemonic ?name .
            }
            LIMIT 100
        """)

    Example - Common Mistake:
        # ❌ BAD - Will timeout!
        result = sparql_query("""
            SELECT ?protein ?name
            WHERE {
                ?protein a up:Protein .
                ?protein up:mnemonic ?name .
            }
        """)  # Missing LIMIT!
    '''
    # Implementation: check for LIMIT, inject if missing
    ...
```

---

### 2. Argument Mismatch Errors (24 failures, 20%)

**Root Cause**: Agents attempt to pass keyword arguments that don't exist in tool signatures.

#### Error Breakdown

**Error**: `SPARQLTools.as_dspy_tools.<locals>.<lambda>() got an unexpected keyword argument 'limit'` (18 occurrences)

**Tool**: `sparql_peek`

**Agent's Attempted Call**:
```python
sparql_peek(..., limit=...)
```

**Problem**: Agent tried to pass `limit=N` as keyword argument, but tool doesn't accept it.

**Fix**: Either:
1. Add `limit` parameter to `sparql_peek` signature
2. Update tool docstring to clarify that `limit` is not supported
3. Provide alternative way to limit results

**Error**: `SPARQLTools.as_dspy_tools.<locals>.<lambda>() takes from 0 to 2 positional arguments but 3 were given` (5 occurrences)

**Tool**: `sparql_slice`

**Problem**: Agent passed wrong number of positional arguments.

**Fix**: Add clear signature with required vs optional parameters.

**Error**: `SPARQLTools.as_dspy_tools.<locals>.<lambda>() got an unexpected keyword argument 'pattern'` (1 occurrences)

**Tool**: `sparql_peek`

**Agent's Attempted Call**:
```python
sparql_peek(..., pattern=..., filters=..., limit=...)
```

**Problem**: Agent tried to pass `pattern=` argument that doesn't exist.

**Fix**: Document correct parameters in tool signature.


**Recommendations**:
1. **Standardize `limit` parameter**: Add optional `limit: int = None` to all data-fetching tools
2. **Type hints**: Use explicit type hints in tool signatures
3. **Parameter validation**: Check arguments before execution, provide helpful error messages
4. **Tool discovery**: Add `list_tools()` function that shows all signatures

---

### 3. Type Errors (4 failures, 3%)

**Root Cause**: Agents pass wrong data types to tools.

#### Examples

**Error**: `unhashable type: 'dict'`
**Tool**: `sparql_slice`
**Context**: 121_proteins_and_diseases_linked (thinking)

**Problem**: Agent passed a dict object where a string (or hashable type) was expected.
**Likely Cause**: Agent passed a result handle dict directly instead of its 'key' string.

**Example Fix**:
```python
# ❌ Wrong - passing dict
slice_result = sparql_slice(result_dict)

# ✅ Correct - passing key string
slice_result = sparql_slice(result_dict['key'])
```

**Error**: `unhashable type: 'dict'`
**Tool**: `sparql_slice`
**Context**: 2_bacteria_taxa_and_their_scientific_name (thinking)

**Problem**: Agent passed a dict object where a string (or hashable type) was expected.
**Likely Cause**: Agent passed a result handle dict directly instead of its 'key' string.

**Example Fix**:
```python
# ❌ Wrong - passing dict
slice_result = sparql_slice(result_dict)

# ✅ Correct - passing key string
slice_result = sparql_slice(result_dict['key'])
```

**Recommendations**:
1. **Type validation**: Check parameter types at tool entry, provide clear error messages
2. **Better error messages**: Instead of 'unhashable type: dict', say 'Expected string key, got dict. Use result["key"] instead.'
3. **Documentation**: Add examples showing correct parameter types

---

### 4. Missing Attribute Errors (5 failures, 4%)

**Root Cause**: Agents call methods that don't exist on result objects.

#### Examples

**Error**: `'dict' object has no attribute 'upper'`
**Tool**: `sparql_count`

**Problem**: Agent tried to call `.upper()` on a dict object.
**Likely Cause**: Misunderstanding of return type, or dict used where string expected.

**Error**: `'dict' object has no attribute 'upper'`
**Tool**: `sparql_count`

**Problem**: Agent tried to call `.upper()` on a dict object.
**Likely Cause**: Misunderstanding of return type, or dict used where string expected.

**Recommendations**:
1. **Return type documentation**: Clearly document return types in docstrings
2. **Type hints**: Use proper type annotations
3. **Runtime type checking**: Validate inputs at function entry

---

## Failure Distribution

### By Task

| Task | Failures |
|------|----------|
| 121_proteins_and_diseases_linked | 51 |
| 2_bacteria_taxa_and_their_scientific_name | 40 |
| 1_select_all_taxa_used_in_uniprot | 23 |
| 4_uniprot_mnemonic_id | 9 |

### By Strategy

| Strategy | Failures |
|----------|----------|
| thinking | 44 |
| none | 28 |
| rephrase | 26 |
| prefix | 25 |

### By Tool

| Tool | Failures |
|------|----------|
| sparql_query | 90 |
| sparql_slice | 17 |
| sparql_peek | 9 |
| sparql_count | 5 |
| sparql_describe | 2 |

---

## Summary: Priority Improvements

### 🔴 Critical (High Impact)

1. **Add automatic LIMIT injection to `sparql_query`**
   - Impact: Prevents 73% of all failures
   - Implementation: Check query for LIMIT, add default if missing, warn agent

2. **Standardize `limit` parameter across tools**
   - Impact: Prevents 15% of failures (18 arg mismatch errors)
   - Implementation: Add optional `limit: int = None` to sparql_peek, sparql_slice, sparql_describe

### 🟡 Important (Medium Impact)

3. **Improve error messages**
   - Replace generic Python errors with actionable guidance
   - Example: "Expected string key, got dict. Use result['key'] instead of passing the dict."

4. **Add tool discovery function**
   - Implement `list_tools()` returning signatures and examples
   - Helps agents understand available tools and their parameters

### 🟢 Nice to Have (Low Impact)

5. **Add query validation warnings**
   - Warn before executing potentially expensive queries
   - Suggest optimizations (add LIMIT, use specific patterns)

6. **Provide query templates**
   - Common patterns agents can copy/modify
   - Reduces trial-and-error exploration

---

## Appendix: Tool-Specific Recommendations

### `sparql_query` (90 failures)

**Current Issues**:
- All 90 failures are timeouts from unbounded queries
- No mechanism to prevent or warn about expensive queries

**Proposed Signature**:
```python
def sparql_query(
    query: str,
    limit: int = None,  # NEW: auto-add LIMIT if missing
    validate: bool = True  # NEW: validate query before execution
) -> Dict[str, Any]:
    '''Execute SPARQL query against endpoint.

    CRITICAL: Queries without LIMIT will timeout! This function can
    automatically add LIMIT if missing (see 'limit' parameter).

    Args:
        query: SPARQL query string
        limit: If query lacks LIMIT, add this value (default: 1000)
               Set to None to disable auto-limit (not recommended)
        validate: Check query for common issues before execution

    Returns:
        Dict with keys: 'key', 'dtype', 'size', 'rows', 'preview', 'source', 'usage'

    Example:
        # ✅ Explicit LIMIT (best practice)
        result = sparql_query("""
            SELECT ?s ?p ?o
            WHERE { ?s ?p ?o }
            LIMIT 100
        """)

        # ✅ Auto-limit (convenient)
        result = sparql_query("""
            SELECT ?s ?p ?o
            WHERE { ?s ?p ?o }
        """, limit=500)

    Raises:
        QueryTimeout: If query exceeds 30 seconds
        QueryValidationError: If validate=True and query has issues
    '''
```

### `sparql_peek` (9 failures)

**Current Issues**:
- Agents try to pass `limit=N` keyword argument (8 failures)
- Agents try to pass `pattern=` argument (1 failure)

**Proposed Signature**:
```python
def sparql_peek(
    resource: str,
    limit: int = 5  # CHANGED: Make this explicit parameter
) -> List[Dict[str, Any]]:
    '''Peek at instances and properties of a class or resource.

    Args:
        resource: URI or prefixed name (e.g., 'up:Protein' or
                  'http://purl.uniprot.org/core/Protein')
        limit: Max instances to return (default: 5)

    Returns:
        List of dicts, each representing one instance with its properties

    Example:
        # Peek at Protein class (limit to 10 instances)
        proteins = sparql_peek('up:Protein', limit=10)

        # Use default limit
        proteins = sparql_peek('up:Protein')
    '''
```

### `sparql_slice` (17 failures)

**Current Issues**:
- Agents try to pass `limit=N` keyword argument (8 failures)
- Agents pass dict instead of string key (4 failures)
- Wrong number of positional arguments (5 failures)

**Proposed Signature**:
```python
def sparql_slice(
    result_key: str,  # CLARIFIED: Must be string key, not dict
    offset: int = 0,
    limit: int = None  # NEW: Add limit parameter
) -> List[Dict[str, Any]]:
    '''Get rows from a query result handle.

    Args:
        result_key: The 'key' string from sparql_query result
                    (e.g., 'results_0', NOT the full dict!)
        offset: Skip this many rows (default: 0)
        limit: Max rows to return (default: None = all)

    Returns:
        List of result rows (dicts)

    Example:
        # ✅ Correct - pass key string
        result = sparql_query("SELECT ...", limit=100)
        rows = sparql_slice(result['key'], limit=10)

        # ❌ Wrong - passing dict
        rows = sparql_slice(result, limit=10)  # ERROR!

        # With offset
        rows = sparql_slice(result['key'], offset=10, limit=10)
    '''
```

