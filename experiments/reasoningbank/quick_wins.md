# Quick Wins: Phase 1 Infrastructure for Closed-Loop Learning

**Goal**: Implement the core components for ReasoningBank closed-loop learning, aligned with the paper's approach.

**Time Estimate**: ~50 minutes total
**LLM Calls**: 2 (judge + extract tests only)

---

## Design Principles (from the Paper)

The ReasoningBank paper (arXiv:2509.25140) makes several important design choices we should follow:

### 1. Learn from BOTH Success AND Failure
> "ReasoningBank improved from 46.5 → 49.7 when failures were included. Synapse/AWM (success-only) actually degraded when failures added."

This is the core insight. We need different extraction strategies for success vs failure trajectories.

### 2. Minimal Consolidation (Append-Only)
> "We adopt a minimal consolidation strategy: newly generated items are directly added without additional pruning. This choice highlights the contribution of ReasoningBank itself without introducing confounding factors."

The paper **intentionally avoided** merge/dedupe/forget to isolate the effect of memory content quality. We should start the same way.

### 3. Quality > Quantity in Retrieval
> "1 experience: 49.7% → 2 experiences: 46.0% → 4 experiences: 44.4%"

More memories can actually **hurt** performance due to noise/conflicts. Default to k=1.

### 4. Memory Schema
Each memory item has three components:
- **Title**: Concise identifier (~10 words)
- **Description**: One-sentence summary
- **Content**: Distilled reasoning steps, decision rationales, operational insights

---

## RLM-Style Memory Access (Handles, Not Payloads)

### The Design Tension

**ReasoningBank Paper**: Injects retrieved memories directly into system prompt (auto-inject)

**RLM Methodology**: "Handles not payloads" - agent should explore incrementally via tools

### Resolution: Hybrid Approach

We support **both modes**, choosing based on context:

| Mode | When to Use | How It Works |
|------|-------------|--------------|
| **Auto-inject** | Small memory, known patterns | System retrieves top-k, packs into L2 context |
| **Tool-mediated** | Large memory, novel exploration | Agent calls `mem_search` → `mem_get` |

### Two-Phase Retrieval Pattern (RLM Invariant)

> "The agent should NEVER see the full memory bank dumped into context."

```
┌─────────────────────────────────────────────────────────────────┐
│  Phase 1: Search (Bounded Preview)                              │
│                                                                 │
│  mem_search("SPARQL query patterns", k=5)                       │
│  → [{id: "abc", title: "Use TYPE for class queries",            │
│      desc: "Always start with ?s rdf:type <Class>",             │
│      src: "success", score: 0.8}, ...]                          │
│                                                                 │
│  Returns: IDs + titles + descriptions (NOT full content)        │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│  Phase 2: Get (Capped Retrieval)                                │
│                                                                 │
│  mem_get(["abc", "def"], max_n=3)                               │
│  → [Item(id="abc", title="...", content="full procedure...")]   │
│                                                                 │
│  Returns: Full content for selected items only                  │
│  Hard cap enforced: refuse if len(ids) > max_n                  │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│  Phase 2b: Quote (Bounded Excerpt) - Optional                   │
│                                                                 │
│  mem_quote("abc", max_chars=500)                                │
│  → "First 500 chars of content..."                              │
│                                                                 │
│  For large memory items that shouldn't be fully loaded          │
└─────────────────────────────────────────────────────────────────┘
```

### Memory Indexing: SQLite FTS5

For RLM-friendly memory search, use **SQLite FTS5** (built-in, no dependencies):

```python
class MemStore:
    def __init__(self, db_path: str = ":memory:"):
        self.conn = sqlite3.connect(db_path)
        self._init_fts()

    def _init_fts(self):
        """Create FTS5 virtual table for memory search."""
        self.conn.execute("""
            CREATE VIRTUAL TABLE IF NOT EXISTS mem_fts USING fts5(
                id,
                title,
                desc,
                content,
                src,
                tokenize='porter'
            )
        """)

    def search(self, q: str, k: int = 5, polarity: str = None) -> list[dict]:
        """BM25-ranked search returning IDs + metadata (NOT full content).

        This is Phase 1: agent sees previews, decides what to load.
        """
        sql = """
            SELECT id, title, desc, src, bm25(mem_fts) as score
            FROM mem_fts
            WHERE mem_fts MATCH ?
        """
        if polarity:
            sql += f" AND src = '{polarity}'"
        sql += " ORDER BY score LIMIT ?"

        rows = self.conn.execute(sql, (q, k)).fetchall()
        return [{'id': r[0], 'title': r[1], 'desc': r[2],
                 'src': r[3], 'score': r[4]} for r in rows]

    def get(self, ids: list[str], max_n: int = 3) -> list[Item]:
        """Retrieve full items (hard cap enforced).

        This is Phase 2: agent explicitly requests full content.
        """
        if len(ids) > max_n:
            raise ValueError(f"Requested {len(ids)} items, max is {max_n}")
        # ... fetch and return full items
```

### Integration with Layer Cake

```
L0: Sense Card       → Auto-inject (~600 chars)
L1: Schema Constraints → Auto-inject (~1000 chars)
L2: Procedural Memory  → Hybrid approach:
    ├── Auto-inject: top-1 success + top-1 failure (paper's k=1)
    └── Tools: mem_search, mem_get, mem_quote for agent exploration
L3: Guide Summary    → Auto-inject (~1000 chars)
```

### Indexing Strategy Roadmap

| Phase | Method | Notes |
|-------|--------|-------|
| **Now** | Word overlap | Simple, already implemented |
| **Next** | SQLite FTS5 | Better ranking, built-in BM25 |
| **Later** | Embeddings | Semantic matching (if needed) |

---

## Overview

Phase 1 requires these components (simplified from original plan):

| Component | LLM Required? | Est. Time | Priority |
|-----------|---------------|-----------|----------|
| Judge | Yes (1 call) | 15 min | 1 |
| Extract | Yes (1 call) | 20 min | 2 |
| Consolidate | No | 5 min | 3 |
| Memory Store Update | No | 10 min | 4 |

**Note**: Forgetting/eviction deferred per paper's approach. Add later if memory bloat becomes an issue.

---

## 1. Judge Function (1 LLM Call)

**Purpose**: Determine if trajectory succeeded or failed (binary signal).

**Location**: `run/phase1.py`

**Key Insight from Paper**: Use LLM-as-a-Judge with temperature 0.0 for determinism.

**Interface**:
```python
def judge(res: Result, task: str) -> dict:
    """Judge trajectory success/failure.

    Returns:
        {
            'success': bool,      # Binary signal
            'reason': str,        # Brief explanation
        }
    """
```

**Implementation** (using DSPy):
```python
import dspy

class TrajectoryJudge(dspy.Signature):
    """Judge whether an RLM trajectory successfully completed the task.

    Output only Success or Failure based on whether the task was resolved.
    """
    task: str = dspy.InputField(desc="The original question/task")
    answer: str = dspy.InputField(desc="The agent's final answer")
    sparql: str = dspy.InputField(desc="The SPARQL query produced (if any)")

    success: bool = dspy.OutputField(desc="True if task was successfully completed")
    reason: str = dspy.OutputField(desc="Brief explanation of judgment")

def judge(res: Result, task: str) -> dict:
    """Binary success/failure judgment."""
    # Use temperature 0.0 for deterministic judgment (per paper)
    judge_fn = dspy.Predict(TrajectoryJudge)
    j = judge_fn(
        task=task,
        answer=res.answer or "",
        sparql=res.sparql or ""
    )
    return {
        'success': j.success,
        'reason': j.reason,
    }
```

**Quick Test** (1 LLM call):
```python
# Mock successful result
mock_result = Result(
    answer="Activity is a class in PROV representing something that occurs over time.",
    sparql="SELECT ?s WHERE { ?s a prov:Activity }",
    converged=True,
    iters=5,
    leakage=Metrics(),
    trace=[]
)

judgment = judge(mock_result, "What is Activity in PROV?")
print(f"Success: {judgment['success']}")
print(f"Reason: {judgment['reason']}")
```

---

## 2. Extract Function (1 LLM Call)

**Purpose**: Extract reusable memory items from trajectory.

**Key Insights from Paper**:
- Extract up to **3 items** per trajectory
- **Different prompts** for success vs failure
- Success: "analyze why the trajectory led to success, summarize transferable strategies"
- Failure: "reflect on causes of failure, articulate lessons or preventive strategies"

**Location**: `run/phase1.py`

**Interface**:
```python
def extract(res: Result, task: str, judgment: dict) -> list[Item]:
    """Extract memory items from trajectory.

    Returns up to 3 items. Empty list if extraction fails.
    """
```

**Implementation** (using DSPy):
```python
class SuccessExtractor(dspy.Signature):
    """Extract transferable strategies from a successful trajectory.

    Analyze why this trajectory succeeded and distill reusable reasoning patterns.
    Focus on strategies that would generalize to similar tasks.
    """
    task: str = dspy.InputField(desc="The original question/task")
    answer: str = dspy.InputField(desc="The successful answer")
    sparql: str = dspy.InputField(desc="The SPARQL query that worked")

    items: list[dict] = dspy.OutputField(
        desc="List of 1-3 memory items, each with 'title', 'description', 'content'"
    )

class FailureExtractor(dspy.Signature):
    """Extract lessons from a failed trajectory.

    Reflect on why this trajectory failed and articulate preventive strategies.
    Focus on pitfalls to avoid and guardrails for future attempts.
    """
    task: str = dspy.InputField(desc="The original question/task")
    answer: str = dspy.InputField(desc="The failed answer (if any)")
    sparql: str = dspy.InputField(desc="The SPARQL query attempted (if any)")

    items: list[dict] = dspy.OutputField(
        desc="List of 1-3 memory items, each with 'title', 'description', 'content'"
    )

def extract(res: Result, task: str, judgment: dict) -> list[Item]:
    """Extract memory items from trajectory (success or failure)."""
    # Choose extractor based on judgment
    if judgment.get('success'):
        ext = dspy.Predict(SuccessExtractor)
        src = 'success'
    else:
        ext = dspy.Predict(FailureExtractor)
        src = 'failure'

    # Extract (temperature 1.0 per paper)
    result = ext(
        task=task,
        answer=res.answer or "",
        sparql=res.sparql or ""
    )

    # Convert to Item objects
    items = []
    for item_dict in result.items[:3]:  # Cap at 3
        item = Item(
            id=Item.make_id(item_dict['title'], item_dict['content']),
            title=item_dict['title'],
            desc=item_dict['description'],
            content=item_dict['content'],
            src=src,
            tags=[],
        )
        items.append(item)

    return items
```

**Quick Test** (1 LLM call):
```python
# Test success extraction
items = extract(mock_result, "What is Activity in PROV?", {'success': True})
for item in items:
    print(f"[{item.src}] {item.title}")
    print(f"  {item.content[:100]}...")
```

---

## 3. Consolidate Function (No LLM)

**Purpose**: Add new items to memory store.

**Key Insight from Paper**: Use simple append. No merging, no deduplication.

> "This choice highlights the contribution of ReasoningBank itself without introducing confounding factors."

**Location**: `core/mem.py` (extend existing `MemStore`)

**Implementation**:
```python
def consolidate(self, items: list[Item]) -> list[str]:
    """Add items to memory store (append-only).

    Per ReasoningBank paper: minimal consolidation strategy.
    No deduplication, no merging - just append.

    Returns: List of added item IDs
    """
    added = []
    for item in items:
        self._items[item.id] = item
        added.append(item.id)
    return added
```

That's it. The paper explicitly avoided complexity here.

**Unit Test**:
```python
def test_consolidate_appends():
    mem = MemStore()
    item1 = Item.make("Strategy A", "Do X then Y", "success")
    item2 = Item.make("Strategy B", "Do Z", "success")

    added = mem.consolidate([item1, item2])

    assert len(added) == 2
    assert len(mem.all()) == 2
```

---

## 4. Closed-Loop Integration

**Purpose**: Wire judge → extract → consolidate into the run loop.

**Location**: `run/phase1.py`

**Implementation**:
```python
def run_closed_loop(
    tasks: list[dict],
    ont: str,
    mem: MemStore,
    cfg: Cfg,
) -> list[dict]:
    """Run closed-loop learning on tasks.

    For each task:
    1. Retrieve relevant memories (k=1 default)
    2. Run with context
    3. Judge success/failure
    4. Extract memory items (different strategy for success vs failure)
    5. Consolidate into memory store
    """
    results = []

    for t in tasks:
        # Run with memory-augmented context
        res = run(t['query'], ont, cfg, mem)

        # Judge
        j = judge(res, t['query'])
        print(f"{t['id']}: {'✓' if j['success'] else '✗'} - {j['reason'][:50]}")

        # Extract (from both success AND failure per paper)
        items = extract(res, t['query'], j)
        print(f"  Extracted {len(items)} items")

        # Consolidate (simple append)
        if items:
            added = mem.consolidate(items)
            for item in items:
                print(f"  + [{item.src}] {item.title}")

        results.append({
            'task': t['id'],
            'success': j['success'],
            'reason': j['reason'],
            'items_extracted': len(items),
        })

    return results
```

---

## Implementation Order

### Step 1: Judge (15 min)
1. Add `TrajectoryJudge` signature to `run/phase1.py`
2. Implement `judge()` function
3. Quick test with mock result (1 LLM call)

### Step 2: Extract (20 min)
1. Add `SuccessExtractor` and `FailureExtractor` signatures
2. Implement `extract()` function
3. Quick test with mock result (1 LLM call)

### Step 3: Consolidate (5 min)
1. Add `consolidate()` method to `core/mem.py`
2. Write unit test
3. Run test

### Step 4: Integration (10 min)
1. Update `run_closed_loop()` to use new functions
2. Test end-to-end with one task

---

## Validation Checklist

After implementation:

- [x] `judge()` returns binary success/failure with reason
- [x] `extract()` produces 1-3 `Item` objects with title/description/content
- [x] `extract()` uses different prompts for success vs failure
- [x] `consolidate()` simply appends (no dedup/merge)
- [x] Integration test: single task → judge → extract → consolidate

---

## Implementation Status (2026-01-31)

### Completed

All four steps implemented and tested:

| Component | File | Status |
|-----------|------|--------|
| `TrajectoryJudge` signature | `run/phase1.py:22-29` | Done |
| `SuccessExtractor` signature | `run/phase1.py:32-39` | Done |
| `FailureExtractor` signature | `run/phase1.py:42-50` | Done |
| `judge()` function | `run/phase1.py:53-75` | Done |
| `extract()` function | `run/phase1.py:78-136` | Done |
| `consolidate()` method | `core/mem.py:63-79` | Done |
| `run_closed_loop()` integration | `run/phase1.py:138-167` | Done |
| `test_judge_extract()` mock test | `run/phase1.py:170-220` | Done |

### Test Results

**Mock Test** (no RLM, just judge/extract):
```
success_case   → [success] Class Discovery via String Pattern Matching
failure_case   → [failure] Failed to Query Ontology for Basic Concepts
nonconverged   → [failure] Vague Question Leading to Non-Convergent Search
Memory store: 3 items
```

**Full Pipeline Test** (RLM + judge + extract):
- Query: "What is Activity?" on `ontology/prov.ttl`
- With L0: Correctly identified PROV-O, extracted "Query Class Labels for Concept Definitions"
- Without L0: Hallucinated "Brick schema" - judge still passed on wrong answer

### Key Finding: L0 Sense Card is Critical

| Condition | context_size | Ontology Identified | Answer Quality |
|-----------|--------------|---------------------|----------------|
| L0 OFF | 0 | "Brick schema" (hallucinated) | Wrong domain |
| L0 ON | 473 | "W3C PROV ontology" | Correct |

**Implication**: The closed-loop (judge → extract → consolidate) works correctly, but **garbage in → garbage out**. Without L0, the LLM hallucinates the ontology identity, and the judge "succeeds" on a wrong answer. This pollutes the memory with incorrect procedures.

**Recommendation**: Always enable L0 sense card for closed-loop learning to ensure ontology grounding.

### CLI Usage

```bash
# Mock test (cheap, no RLM)
python -m experiments.reasoningbank.run.phase1 --test -v

# Full pipeline (with L0 sense card)
# Currently requires modifying cfg in code - see next steps
python -m experiments.reasoningbank.run.phase1 --ont ontology/prov.ttl --extract -v
```

---

## Deferred (Per Paper's Approach)

The following are explicitly deferred based on the paper's design choices:

1. **Complex Consolidation** (merge/dedupe): Paper says "minimal consolidation strategy"
2. **Forgetting/Eviction**: Not implemented in paper, mentioned as future work
3. **MaTTS (Test-Time Scaling)**: Phase 2 feature after basic loop works

### Near-Term Upgrades (After Phase 1 Works)

1. **SQLite FTS5 Indexing**: Replace word overlap with BM25-ranked search
2. **Embedding-based Retrieval**: For semantic matching if keyword search insufficient
3. **Memory Tools for Agent**: Expose `mem_search`, `mem_get`, `mem_quote` in tool surface

---

## Why This Matters

The paper's key finding: **memory content quality matters more than memory infrastructure**.

By keeping consolidation simple (append-only), we can:
1. Implement quickly
2. Isolate the effect of judge/extract quality
3. Add complexity later if needed

The paper achieved strong results (up to 34.2% improvement) with this minimal approach.

---

## Next Steps

### Immediate (Before More Experiments)

1. **Add `--l0` flag to CLI** - Enable L0 sense card from command line
2. **Add `--cfg` parameter to `run_closed_loop()`** - Allow passing layer configuration
3. **Persist memory across runs** - Load/save memory to enable cumulative learning

### Near-Term

1. **Run multi-task closed-loop** - Process several tasks, observe memory growth
2. **Test memory retrieval** - Verify extracted procedures help subsequent queries
3. **Add L1 schema layer** - Test if schema constraints improve grounding further

### Experiments to Run

| Experiment | Question | Layers |
|------------|----------|--------|
| E9a | Does memory accumulation help? | L0 + L2 (memory) |
| E9b | L0 vs L0+L1 grounding | Compare sense card alone vs with schema |
| E9c | Success vs failure memory | Retrieve only success, only failure, or both |
