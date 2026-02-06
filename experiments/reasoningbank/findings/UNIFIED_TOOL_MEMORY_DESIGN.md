# Unified Tool + Memory Design for RLM

**Date**: 2026-02-04
**Reconciles**: SPARQL tool redesign + RLM memory architecture + Claude Code patterns

---

## Core Principle: Everything is a Handle

The RLM paper's key insight is that **prompts should contain handles, not payloads**. This applies to both:

1. **SPARQL results** → `Ref(key='results_0', dtype='results', 3000 chars)`
2. **Memory items** → `{id: 'abc123', title: '...', desc: '...'}`
3. **Ontology content** → `Ref(key='graph_0', dtype='graph', 50000 chars)`

The REPL sees metadata. Payloads live in storage. Tools fetch on demand.

---

## The Unified Two-Phase Pattern

Both SPARQL and Memory follow the same retrieval pattern:

```
Phase 1: SEARCH (cheap, bounded, metadata only)
         Returns: IDs/keys + titles/previews + counts

Phase 2: GET (targeted, capped, full content)
         Returns: Actual data, but bounded
```

### Memory Tools (existing)
```python
mem_search(q, k=6)     # → [{id, title, desc}]      # Phase 1
mem_get(ids, max_n=3)  # → [Item(...)]              # Phase 2
mem_quote(id, max=500) # → bounded excerpt          # (shortcut)
```

### SPARQL Tools (proposed)
```python
sparql_schema('classes', k=20)  # → [{uri, label, count}]    # Phase 1
sparql_peek(class, limit=5)     # → [{uri, properties...}]   # Phase 1.5
sparql_query(q, limit=100)      # → Ref(key, rows, preview)  # Phase 2a
sparql_slice(key, limit=50)     # → [row dicts]              # Phase 2b
```

### Unified Pattern
```
┌─────────────────────────────────────────────────────────────┐
│                    SEARCH (Phase 1)                         │
│  mem_search(q)        sparql_schema()      sparql_peek()   │
│  → IDs + metadata     → classes + counts   → samples       │
│  (NO content)         (NO instances)       (LIMITED)       │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│                    GET (Phase 2)                            │
│  mem_get(ids)         sparql_query()       sparql_slice()  │
│  → full Items         → Ref handle         → actual rows   │
│  (CAPPED at 3)        (LIMIT enforced)     (bounded)       │
└─────────────────────────────────────────────────────────────┘
```

---

## The Handle Types

### 1. BlobRef (for large content)
```python
@dataclass
class Ref:
    key: str      # 'results_0', 'graph_1'
    dtype: str    # 'results', 'graph', 'text'
    sz: int       # character count
    prev: str     # first 80 chars preview

    def __repr__(self):
        return f"Ref({self.key!r}, {self.dtype}, {self.sz} chars)"
```

**REPL sees**: `Ref('results_0', 'results', 3000 chars)`
**REPL does NOT see**: The actual 3000 characters

### 2. Memory Handle (for procedures)
```python
# From mem_search():
{
    'id': 'abc123',
    'title': 'Query proteins by mnemonic',
    'desc': 'Use up:mnemonic predicate with exact string match',
    'src': 'success'
}
```

**REPL sees**: Title + one-line description
**REPL does NOT see**: Full procedure content

### 3. SPARQL Schema Handle (NEW)
```python
# From sparql_schema():
{
    'uri': 'up:Protein',
    'label': 'Protein',
    'count': 3116860,
    'common_properties': ['up:mnemonic', 'up:organism', 'up:annotation']
}
```

**REPL sees**: Class metadata + sample properties
**REPL does NOT see**: 3M protein instances

---

## Integration: Memory-Augmented SPARQL

### The Closed Loop

```
┌─────────────────────────────────────────────────────────────┐
│                    NEW QUERY TASK                           │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│   1. RETRIEVE RELEVANT MEMORIES                             │
│      mem_search("protein disease annotation", k=3)          │
│      → [{id, title: "Query protein-disease links", ...}]    │
│      mem_quote(id, max=300) → bounded procedure             │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│   2. EXPLORE SCHEMA (if needed)                             │
│      sparql_schema('classes', filter='up:')                 │
│      sparql_peek('up:Disease_Annotation', output='schema')  │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│   3. CONSTRUCT & EXECUTE QUERY                              │
│      (informed by memory + schema)                          │
│      sparql_query(query, limit=100) → Ref                   │
│      sparql_slice(ref, limit=10) → sample rows              │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│   4. VALIDATE & SUBMIT                                      │
│      SUBMIT(sparql=query, answer=answer)                    │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│   5. JUDGE & EXTRACT (if successful)                        │
│      judge(result, task) → {success, reason}                │
│      extract(trajectory) → Item(title, content, src)        │
│      mem_add(item) → stored for future                      │
└─────────────────────────────────────────────────────────────┘
```

### Context Injection (L2 Layer)

The L2 layer injects retrieved memories into context:

```python
def build_context(task: str, ont_path: str, mem: MemStore) -> str:
    parts = []

    # L0: Sense card (ontology summary)
    parts.append(l0_sense.pack(ont_path, budget=600))

    # L1: Schema constraints (anti-patterns, domain/range)
    parts.append(l1_schema.pack(ont_path, budget=400))

    # L2: Retrieved procedures (from memory)
    relevant = mem.search(task, k=3)
    if relevant:
        procedures = []
        for hit in relevant[:2]:  # Cap at 2 full procedures
            quote = mem.quote(hit['id'], max_chars=300)
            procedures.append(f"**{hit['title']}**: {quote}")
        parts.append("## Relevant Procedures\n" + "\n\n".join(procedures))

    # L3: Guide summary (optional)
    if guide_available:
        parts.append(l3_guide.pack(budget=200))

    return "\n\n---\n\n".join(parts)
```

**Key constraints**:
- L2 injects **at most 2 procedures**
- Each procedure is **capped at 300 chars**
- Total L2 budget: ~600 chars
- Prevents "dump 20 strategies into prompt"

---

## Unified Tool API

### SPARQL Tools (Memory-Aware)

```python
def sparql_query(
    query: str,
    limit: int = 100,
    explain: bool = False,
    store_pattern: bool = True  # NEW: Auto-store successful patterns
) -> Ref:
    """Execute SPARQL query, return handle.

    If store_pattern=True and query succeeds, the pattern is
    automatically extracted and stored in procedural memory.
    """

def sparql_schema(
    output_mode: str = 'overview',
    filter_prefix: str = None,
    limit: int = 50,
    use_cache: bool = True  # NEW: Cache schema in memory
) -> dict:
    """Get schema info. Cached for efficiency."""

def sparql_peek(
    resource: str,
    limit: int = 5,
    output_mode: str = 'sample',
    related_memories: bool = True  # NEW: Show related procedures
) -> dict:
    """Peek at resource. Optionally show related memory items."""
    result = _peek_impl(resource, limit, output_mode)

    if related_memories:
        # Search memory for related procedures
        related = mem_search(resource, k=2)
        result['related_procedures'] = [
            {'id': r['id'], 'title': r['title']}
            for r in related
        ]

    return result
```

### Memory Tools (SPARQL-Aware)

```python
def mem_search(
    q: str,
    k: int = 6,
    polarity: str = None,
    domain: str = None  # NEW: Filter by ontology domain
) -> list[dict]:
    """Search memory. Can filter by domain (e.g., 'uniprot', 'prov')."""

def mem_extract(
    result: Ref,
    task: str,
    judgment: dict,
    auto_store: bool = True  # NEW: Auto-add to memory
) -> Item:
    """Extract procedure from successful SPARQL result.

    Analyzes the query pattern and creates a reusable procedure.
    If auto_store=True, adds to memory immediately.
    """

def mem_learn_from_failure(
    result: Ref,
    task: str,
    error: str
) -> Item:
    """Extract anti-pattern from failed query.

    Creates a 'pitfall' memory to avoid repeating mistakes.
    """
```

---

## Handle Flow Diagram

```
┌──────────────────────────────────────────────────────────────────┐
│                         REPL STATE                                │
│                                                                  │
│  Variables (what agent sees):                                    │
│    context = "...600 char sense card..."                        │
│    question = "Find proteins linked to diseases"                │
│    schema_info = {'classes': [...], 'count': 47}                │
│    query_result = Ref('results_0', 'results', 3000 chars)       │
│    memories = [{'id': 'abc', 'title': '...'}]                   │
│                                                                  │
│  NOT in variables (in storage):                                  │
│    Store._blobs['results_0'] = "...3000 chars of SPARQL rows..."│
│    MemStore._items['abc'] = Item(content="...full procedure...")│
│    Graph data (50k chars)                                       │
│                                                                  │
└──────────────────────────────────────────────────────────────────┘
                              │
                              │ Agent calls tools
                              ▼
┌──────────────────────────────────────────────────────────────────┐
│                         TOOLS                                     │
│                                                                  │
│  sparql_slice('results_0', limit=10)                            │
│    → fetches from Store, returns 10 rows (bounded)              │
│                                                                  │
│  mem_get(['abc'], max_n=1)                                      │
│    → fetches from MemStore, returns 1 Item (capped)             │
│                                                                  │
│  sparql_peek('up:Protein', limit=5)                             │
│    → executes bounded query, returns 5 instances                │
│                                                                  │
└──────────────────────────────────────────────────────────────────┘
```

---

## Preventing "Algorithm-2" Drift

The RLM notes warn about drifting back into "agent with summarization." Here's how the unified design prevents that:

### 1. **No Large Returns**

| Tool | Returns | NOT Returns |
|------|---------|-------------|
| `sparql_query` | `Ref(key, 100 rows)` | Raw 3000 chars |
| `mem_search` | `[{id, title, desc}]` | Full procedure text |
| `sparql_schema` | `{class_count: 47}` | All 47 class definitions |
| `sparql_peek` | 5 sample instances | All 3M proteins |

### 2. **Forced Two-Phase**

```python
# WRONG: Dump everything
result = sparql_query("SELECT * WHERE {?s ?p ?o}")  # Returns Ref
print(store.get(result.key))  # ❌ 3000 chars in REPL history!

# RIGHT: Bounded retrieval
result = sparql_query("SELECT ...", limit=100)  # Returns Ref
sample = sparql_slice(result, limit=10)  # Only 10 rows
# Agent inspects sample, decides if needs more
```

### 3. **Memory Caps**

```python
mem_get(ids, max_n=3)  # Hard cap: 3 items max
mem_quote(id, max_chars=500)  # Hard cap: 500 chars
```

### 4. **Prompt Leakage Metrics**

Track these in every run:
- `total_chars_returned` - Sum of all tool return sizes
- `max_single_return` - Largest single tool return
- `memory_items_injected` - How many L2 procedures
- `context_size` - Total context including L0-L3

Red flags:
- `max_single_return > 1000` → Tool returned too much
- `memory_items_injected > 3` → Too many procedures in context
- `context_size > 4000` → Context getting bloated

---

## Implementation Mapping

### Existing Code (keep)

| File | What It Does | Status |
|------|--------------|--------|
| `core/blob.py` | `Ref` + `Store` for handles | ✅ Keep |
| `core/mem.py` | `Item` + `MemStore` for memory | ✅ Keep |
| `packers/l0_sense.py` | Sense card generation | ✅ Keep |
| `packers/l1_schema.py` | Schema constraints | ✅ Keep |
| `packers/l2_memories.py` | Memory formatting for context | ✅ Keep |

### Tools to Modify

| File | Changes Needed |
|------|----------------|
| `tools/sparql.py` | Add `limit` params, `output_mode`, auto-LIMIT, accept dict |
| `tools/endpoint.py` | Add `sparql_schema` tool |
| `run/rlm_uniprot.py` | Wire up memory integration |

### New Code Needed

| Component | Purpose |
|-----------|---------|
| `tools/sparql_v2.py` | Redesigned SPARQL tools with unified API |
| `tools/memory_tools.py` | `mem_extract`, `mem_learn_from_failure` |
| `ctx/builder_v2.py` | Memory-aware context builder |

---

## Example: Full Memory-Augmented Run

```python
# === SETUP ===
store = Store()
mem = MemStore()
mem.load("seed_procedures.json")  # Pre-seeded with 10 procedures

# === CONTEXT BUILDING ===
# L0: Sense card (600 chars)
# L1: Schema constraints (400 chars)
# L2: Retrieved procedures (2 items × 300 chars = 600 chars)
# Total: ~1600 chars

context = build_context(
    task="List proteins linked to diseases",
    ont_path="ontology/uniprot.ttl",
    mem=mem
)

# === AGENT EXECUTION ===
# Iteration 1: Agent sees context + question
# Agent calls: sparql_schema('overview')
#   → {'class_count': 47, 'top_classes': [...]}

# Iteration 2: Agent explores
# Agent calls: sparql_peek('up:Disease_Annotation', output_mode='schema')
#   → {'properties': ['up:disease', ...], 'related_procedures': [{id, title}]}

# Iteration 3: Agent constructs query (informed by memory + schema)
# Agent calls: sparql_query(query, limit=100)
#   → Ref('results_0', 'results', 2500 chars)

# Iteration 4: Agent validates
# Agent calls: sparql_slice('results_0', limit=10)
#   → [{'protein': '...', 'disease': '...'}, ...]

# Iteration 5: Agent submits
# SUBMIT(sparql=query, answer=answer)

# === POST-RUN ===
# Judge: success=True
# Extract: Item(title="Query protein-disease annotations", ...)
# Store: mem.add(item) → memory grows for next run
```

---

## Summary: The Unified Vision

```
┌─────────────────────────────────────────────────────────────────┐
│                     RLM MEMORY SYSTEM                           │
│                                                                 │
│  ┌─────────────┐     ┌─────────────┐     ┌─────────────┐       │
│  │ Procedural  │     │   SPARQL    │     │   Blob      │       │
│  │   Memory    │     │   Results   │     │   Store     │       │
│  │  (Items)    │     │  (Ref keys) │     │  (content)  │       │
│  └─────────────┘     └─────────────┘     └─────────────┘       │
│        ▲                   ▲                   ▲                │
│        │                   │                   │                │
│        │ two-phase         │ handle            │ on-demand      │
│        │ retrieval         │ pattern           │ fetch          │
│        │                   │                   │                │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │                      TOOLS                               │   │
│  │  mem_search → mem_get    sparql_query → sparql_slice    │   │
│  │  (IDs first)             (Ref first)                    │   │
│  └─────────────────────────────────────────────────────────┘   │
│                              │                                  │
│                              ▼                                  │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │                    REPL STATE                            │   │
│  │  (handles + metadata only, NO large payloads)           │   │
│  └─────────────────────────────────────────────────────────┘   │
│                              │                                  │
│                              ▼                                  │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │                   CONTEXT (L0-L3)                        │   │
│  │  L0: Sense card (600 chars)                             │   │
│  │  L1: Schema constraints (400 chars)                     │   │
│  │  L2: Retrieved procedures (600 chars, 2 items max)      │   │
│  │  L3: Guide summary (200 chars)                          │   │
│  │  Total: ~1800 chars (bounded)                           │   │
│  └─────────────────────────────────────────────────────────┘   │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

**The key unifying principle**: Everything flows through handles. Memory items have IDs. SPARQL results have keys. Ontologies have refs. The agent sees metadata. Payloads live in storage. Tools fetch bounded slices on demand.

This is what keeps us in "Algorithm-1 land" instead of drifting back to "agent with summarization."
