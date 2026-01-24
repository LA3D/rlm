# RLM Non-Convergence Analysis

## Issue Summary

Two tests are non-deterministically failing by hitting `max_iters` without convergence:
- `test_uses_repl_not_direct_graph_access` (max_iters=3)
- `test_rlm_ontology_integration` in quick_e2e (max_iters=3)

## Root Cause: Insufficient Iterations

The LLM requires **4-5 iterations** for ontology exploration queries, but these tests only allow **3 iterations**.

## Actual Behavior (max_iters=3)

For query: "What is prov:Activity?"

### Iteration 1: Context Understanding
```python
# LLM explores the context
print(context)  # Shows: 59 classes, 89 properties, etc.
```
**Outcome:** Understands what's available but hasn't answered yet.

### Iteration 2: Initial Exploration
```python
# LLM tries to get entity info
prov_describe_entity("prov:Activity")
# Returns: {'uri': 'prov:Activity', 'label': 'prov:Activity',
#           'types': [], 'comment': None, 'outgoing_sample': []}
```
**Outcome:** Gets limited info, needs to try other approaches.

### Iteration 3: Alternative Approaches
```python
# LLM tries search and relationships
prov_search_by_label("Activity")
prov_probe_relationships("prov:Activity")
# Returns: List of related classes, relationship data
```
**Outcome:** Gathers more data but **RUNS OUT OF ITERATIONS** before formulating answer.

### Result: `[Max iterations] Last output: Search by label 'Activity': [(...)]`

## Expected Behavior (max_iters=5)

### Iterations 1-3: Same as above

### Iteration 4: Synthesis (MISSING in failing tests)
```python
# LLM processes gathered information
# Combines describe_entity, search, relationships data
# Formulates a coherent answer
```

### Iteration 5: Convergence
```
FINAL("""prov:Activity represents something that occurs over a period
of time and acts upon or with entities. It is one of the three core
classes in the PROV ontology...""")
```
**Outcome:** ✅ Successfully converges with complete answer.

## Why This Happens

### RLM Protocol Exploration Pattern:
1. **Understand** - Examine context/available tools
2. **Explore** - Try primary approach (describe_entity)
3. **Adapt** - Try alternative approaches when primary fails/incomplete
4. **Synthesize** - Combine findings into coherent answer
5. **Return** - Call FINAL() or FINAL_VAR()

### The Math:
- Simple queries (variable lookup): 2-3 iterations
- **Ontology exploration**: 4-5 iterations ← These tests
- Complex multi-step reasoning: 6-8 iterations

## Validation

### With max_iters=3:
```bash
python debug_convergence.py
# Result: [Max iterations] Last output: Search by label...
# Converged: False
# Iterations used: 3/3
```

### With max_iters=5:
```bash
python debug_convergence_fixed.py
# Result: prov:Activity represents something that occurs...
# Converged: True
# Iterations used: 5/5 (FINAL in iteration 5)
```

## Is This a Bug?

**No.** This is expected LLM behavior:
- The protocol assertions are working correctly (detecting non-convergence)
- The LLM is exploring systematically (not getting stuck)
- The queries require more exploration than 3 iterations allow
- Other tests with max_iters=5 pass consistently

## The Tradeoff

### max_iters=3 (current failing tests):
- ✅ Fast (15-20 seconds)
- ✅ Low API cost (~15 API calls)
- ❌ May not converge for exploration queries
- ❌ Non-deterministic (depends on LLM's first approach)

### max_iters=5 (working tests):
- ✅ Reliable convergence
- ✅ Allows full exploration pattern
- ⚠️ Slower (25-35 seconds)
- ⚠️ Higher API cost (~25 API calls)

## Recommendations

### Option 1: Increase max_iters (Recommended)
```python
# In test_quick_e2e.py line 126
max_iters=5  # Changed from 3

# In test_rlm_ontology_integration.py line 192
max_iters=5  # Changed from 3
```
**Pros:** Tests become reliable
**Cons:** Slightly longer test time

### Option 2: Simplify Queries
```python
# Instead of: "What is prov:Activity?"
# Use: "Describe prov:Activity briefly"
```
**Pros:** May converge faster
**Cons:** Doesn't test realistic usage

### Option 3: Accept Non-Determinism
- Mark tests as `@pytest.mark.flaky(max_runs=3)`
- Accept that ontology exploration may need 4-5 iterations
**Pros:** Tests real-world behavior
**Cons:** CI flakiness

## Related Tests (max_iters=5, all passing)

- ✅ `test_simple_exploration_with_progressive_disclosure`
- ✅ `test_complex_query_with_sense_document`
- ✅ `test_progressive_disclosure_with_hierarchy_navigation`
- ✅ `test_convergence_metrics`

## Conclusion

The "failures" are actually **protocol assertions working correctly**:
- `assert_converged_properly()` correctly detected max_iters fallback
- The LLM is behaving normally (systematic exploration)
- The issue is test configuration: **max_iters=3 is insufficient for these queries**

**Recommended fix:** Change both tests to `max_iters=5`
