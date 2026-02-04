# Handle Pattern (BlobRef)

**Status**: ✅ Validated (E7b, E2)
**Evidence**: [E7b: 52% leakage reduction](../metrics/leakage_comparison.md), [E2: Tool usage enabled](../metrics/e2_validation.md)
**Extraction Priority**: 🔥 High

## Problem

Large data in REPL variables bloats prompt history. DSPy RLM re-prompts each iteration with `variables_info` metadata. If `repr()` returns full content, context window fills quickly:

```python
# ❌ Bad: Full payload in repr
results = "... 400KB of SPARQL results ..."
# variables_info includes: results: "...400KB..." (bloats every iteration)
```

This violates RLM v2 principle: **REPL state, not chat history**.

## Solution

Wrap large data in `BlobRef` with metadata-only `repr()`:

```python
@dataclass
class Ref:
    """Handle for large data - REPL sees metadata, not payload."""
    key: str        # Storage key
    dtype: str      # 'graph', 'results', 'mem', 'text'
    sz: int         # Character count
    prev: str       # First 80 chars preview

    def __repr__(self):
        return f"Ref({self.key!r}, {self.dtype}, {self.sz} chars)"

# ✅ Good: Metadata only
results = Ref('results_001', 'results', 400000, '?s ?p ?o...')
# variables_info includes: results: Ref('results_001', 'results', 400000 chars)
```

Actual payload lives in `Store`, accessed via bounded tools:
- `ctx_stats(ref)` → metadata
- `ctx_peek(ref, n=200)` → short preview
- `ctx_slice(ref, start, end)` → bounded excerpt
- `ctx_find(ref, pattern)` → search with snippets

## Validation

### E7b: Prompt Leakage Comparison

| Condition | Large Returns (>1K chars) | Avg Iterations | Convergence |
|-----------|---------------------------|----------------|-------------|
| **E7a (Naive)** | 23 | 8.2 | 85% |
| **E7b (Handle)** | 11 | 6.7 | 92% |
| **Improvement** | **-52%** | **-18%** | **+7pp** |

**Finding**: Handle pattern cuts prompt leakage in half while improving convergence.

### E2: Tool Usage Enabled

| Experiment | Context | Tool Calls | Convergence |
|------------|---------|------------|-------------|
| **E1** | Empty | 0 | 67% (guessing) |
| **E2** | Sense card (handle-based) | 5-7 | 100% |

**Finding**: Sense card (which uses handles for graphs) enables proper tool usage.

## Production Implications

### Must-Have

This is a **core abstraction** for production RLM. All large data must use handle pattern:
- RDF graphs
- SPARQL results
- Retrieved memories
- Generated documents

### Performance

- **Memory**: O(1) in prompt, O(N) in store (acceptable)
- **Latency**: Negligible (metadata extraction is fast)
- **Scaling**: Linear with data size (store growth), constant in prompt

### API Design

```python
# Public API
class DataStore:
    def put(self, content: str, dtype: str) -> Ref: ...
    def get(self, key: str) -> str: ...
    def peek(self, key: str, n: int = 200) -> str: ...
    def slice(self, key: str, start: int, end: int) -> str: ...
    def stats(self, key: str) -> dict: ...

# Tool wrappers return Refs
def load_graph(path: str) -> Ref: ...
def execute_query(sparql: str) -> Ref: ...
def retrieve_memories(query: str) -> Ref: ...
```

### Dependencies

- None (pure Python dataclass)
- Optional: pickle/json serialization for persistence

## Code Reference

See `01_PROTOTYPE/core/blob.py` (lines 5-30):

```python
@dataclass
class Ref:
    key: str
    dtype: str
    sz: int
    prev: str
    def __repr__(self): return f"Ref({self.key!r}, {self.dtype}, {self.sz} chars)"

class Store:
    def __init__(self): self._blobs,self._counter = {},0

    def put(self, content:str, dtype:str) -> Ref:
        k = f"{dtype}_{self._counter}"; self._counter += 1
        self._blobs[k] = content
        return Ref(k, dtype, len(content), content[:80])

    def get(self, k:str) -> str: return self._blobs[k]
    def peek(self, k:str, n:int=200) -> str: return self._blobs[k][:n]
    def slice(self, k:str, start:int, end:int) -> str: return self._blobs[k][start:end]
```

## Related Patterns

- **Enables**: Two-phase retrieval (search returns IDs, get returns content)
- **Complements**: Bounded tools (tools enforce limits on Ref access)
- **Required by**: All memory patterns (L2, L3)

## Extraction Checklist

- [ ] Implement `Ref` dataclass with metadata-only `repr()`
- [ ] Implement `Store` with put/get/peek/slice/stats
- [ ] Wrap all large-data tools to return `Ref`
- [ ] Add bounded access tools (peek, slice, stats)
- [ ] Validate: Check `variables_info` size stays constant
- [ ] Benchmark: Compare E7a (naive) vs E7b (handle) metrics

---

**References**:
- [00_FOUNDATIONS/rlm_notes.md](../../00_FOUNDATIONS/rlm_notes.md) - "Treat REPL variables as handles, never as payloads"
- [00_FOUNDATIONS/IMPLEMENTATION_PLAN.md](../../00_FOUNDATIONS/IMPLEMENTATION_PLAN.md) - Module spec (lines 116-145)
- [05_ARCHIVE/implementation_notes/IMPLEMENTATION_SUMMARY.md](../../05_ARCHIVE/implementation_notes/IMPLEMENTATION_SUMMARY.md) - E7 results
