# ReasoningBank Implementation Gaps Analysis

**Date:** 2026-01-20
**Purpose:** Identify gaps between current `rlm/procedural_memory.py` and the ReasoningBank paper/trajectory_v2 requirements

---

## Executive Summary

The current `rlm/procedural_memory.py` implements **most of the ReasoningBank paper's core concepts** but has **critical infrastructure gaps** that prevent it from being production-ready and fully paper-aligned:

### ✅ What's Already Correct

1. **Memory Schema** - Has title, description, content (matches paper)
2. **Extraction from Success/Failure** - `judge_trajectory()` and `extract_memories()` implement this
3. **Closed Loop** - retrieve → inject → run → judge → extract → store pattern exists
4. **BM25 Retrieval** - Using `rank-bm25` (though paper uses embeddings)
5. **Minimal Consolidation** - Simple append strategy (matches paper)

### 🔴 Critical Gaps

| Gap | Current | Paper/Target | Impact |
|-----|---------|--------------|--------|
| **Storage Backend** | JSON file + in-memory MemoryStore | SQLite with provenance | Not durable across sessions, no observability |
| **Trajectory Storage** | Not stored | Required (full trajectory) | Can't reconstruct reasoning, no curriculum building |
| **Provenance Tracking** | Minimal (task_query, session_id) | Full lineage (run_id, trajectory_id, judgment) | Can't trace where memories came from |
| **Memory Usage Logging** | None | `memory_usage` table tracking what was retrieved | Can't measure memory effectiveness |
| **Retrieval Method** | BM25 only | Embedding similarity (paper), FTS5 BM25 (target) | Less semantically aware |
| **Memory ID Stability** | Random UUID | Content-based hash for dedup | Duplicates not prevented |
| **Scope Metadata** | Tags only | Scope JSON (ontology, task_types, tools) | Hard to filter by applicability |
| **Pack Import/Export** | None | JSONL with stable IDs | Can't ship curated memories with git |

---

## 1. Storage Architecture Gap

### Current Implementation

**File:** `rlm/procedural_memory.py:62-130`

```python
@dataclass
class MemoryStore:
    """Persistent storage for procedural memories."""
    memories: list[MemoryItem] = field(default_factory=list)
    path: Optional[Path] = None

    def save(self) -> str:
        """Persist memories to JSON file."""
        if self.path is None:
            return "No path configured - not saving"

        self.path.parent.mkdir(parents=True, exist_ok=True)
        data = [m.to_dict() for m in self.memories]

        with open(self.path, 'w') as f:
            json.dump(data, f, indent=2)

        return f"Saved {len(self.memories)} memories to {self.path}"
```

**Problems:**
- **Session-scoped only**: Data loaded/saved per run, not accumulated across sessions
- **No provenance**: Can't link memories back to the trajectories that created them
- **No observability**: Can't query "which memories helped query X?"
- **Scalability**: Loading entire JSON into memory doesn't scale

### Paper Specification

**From `reasoning_bank_paper.md:335-337`:**

> We maintain ReasoningBank in a JSON format, and each entry of ReasoningBank consists of a **task query, the original trajectory, and the corresponding memory items**. All memory items are stored with the schema {title, description, content}. The embedding is pre-computed for each given query and stored in another JSON file for efficient similarity search. We persist the memory pool for each independent run, enabling continual accumulation of experiences throughout test-time learning.

**Key difference:** Paper stores **trajectories with memories**, not just memories alone.

### Target Implementation (trajectory_v2 + SQLite architecture)

**Required Tables:**

```sql
CREATE TABLE runs (
    run_id TEXT PRIMARY KEY,
    created_at TEXT NOT NULL,
    model TEXT,
    ontology_name TEXT,
    ontology_path TEXT,
    notes TEXT
);

CREATE TABLE trajectories (
    trajectory_id TEXT PRIMARY KEY,
    run_id TEXT NOT NULL,
    task_query TEXT NOT NULL,
    final_answer TEXT,
    iteration_count INTEGER NOT NULL,
    converged INTEGER NOT NULL,
    artifact_json TEXT NOT NULL,  -- extract_trajectory_artifact() output
    rlm_log_path TEXT,
    created_at TEXT NOT NULL,
    FOREIGN KEY (run_id) REFERENCES runs(run_id)
);

CREATE TABLE judgments (
    trajectory_id TEXT PRIMARY KEY,
    is_success INTEGER NOT NULL,
    reason TEXT NOT NULL,
    confidence TEXT NOT NULL,  -- high|medium|low
    missing_json TEXT NOT NULL,
    FOREIGN KEY (trajectory_id) REFERENCES trajectories(trajectory_id)
);

CREATE TABLE memory_items (
    memory_id TEXT PRIMARY KEY,  -- stable hash (see §2)
    title TEXT NOT NULL,
    description TEXT NOT NULL,
    content TEXT NOT NULL,
    source_type TEXT NOT NULL,  -- success|failure|human|pack
    task_query TEXT,
    created_at TEXT NOT NULL,
    tags_json TEXT NOT NULL,
    scope_json TEXT NOT NULL,
    provenance_json TEXT NOT NULL,
    access_count INTEGER NOT NULL DEFAULT 0,
    success_count INTEGER NOT NULL DEFAULT 0,
    failure_count INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE memory_usage (
    trajectory_id TEXT NOT NULL,
    memory_id TEXT NOT NULL,
    rank INTEGER NOT NULL,
    score REAL,
    FOREIGN KEY (trajectory_id) REFERENCES trajectories(trajectory_id),
    FOREIGN KEY (memory_id) REFERENCES memory_items(memory_id)
);
```

**Benefits:**
- ✅ Durable across sessions (SQLite persists on disk)
- ✅ Full provenance (can trace memory back to trajectory)
- ✅ Observability queries ("show me all failures that extracted memory X")
- ✅ Scales better (SQL queries, indices, FTS)

---

## 2. Provenance Tracking Gap

### Current Implementation

**`MemoryItem` fields:**

```python
@dataclass
class MemoryItem:
    id: str                    # Random UUID
    title: str
    description: str
    content: str
    source_type: str           # 'success' or 'failure'
    task_query: str
    created_at: str
    access_count: int = 0
    tags: Optional[list[str]] = None
    session_id: Optional[str] = None  # Links to DatasetMeta.session_id
```

**What's missing:**
- No `trajectory_id` or `run_id` linking
- Can't find "the trajectory that created this memory"
- Can't find "all memories extracted from run X"

### Target Implementation

**`memory_items` table includes `provenance_json`:**

```json
{
  "source": "extracted",
  "curriculum_id": "prov_curriculum_v1",
  "trajectory_id": "t-abc123",
  "run_id": "r-xyz789",
  "exported_in_pack": "prov_v1"
}
```

**Benefits:**
- ✅ Bidirectional navigation (memory → trajectory, trajectory → memories)
- ✅ Reproducibility (can recreate the conditions that produced a memory)
- ✅ Curriculum tracking (which curriculum created this?)
- ✅ Pack management (which pack is this from?)

---

## 3. Trajectory Storage Gap

### Current Implementation

**Does NOT store trajectories.** Only stores extracted `MemoryItem` objects.

**From `rlm_run_with_memory():`**

```python
def rlm_run_with_memory(
    query: str,
    context: str,
    memory_store: MemoryStore,
    ...
) -> tuple[str, list, dict, list[MemoryItem]]:
    # ... runs rlm_run() ...
    answer, iterations, ns = rlm_run(query, enhanced_context, ns=ns, **kwargs)

    # ... extracts memories ...
    new_memories = extract_memories(artifact, judgment, ns)

    # ONLY stores memories, NOT the trajectory/judgment
    for mem in new_memories:
        memory_store.add(mem)
    if memory_store.path:
        memory_store.save()

    return answer, iterations, ns, new_memories
```

**Problem:** The trajectory (`iterations`) and judgment are **discarded** after memory extraction.

### Paper Requirement

**From paper:335:**

> each entry of ReasoningBank consists of a **task query, the original trajectory, and the corresponding memory items**.

**Target Implementation:**

```python
# Store trajectory first
trajectory_id = store.add_trajectory(
    run_id=run_id,
    task_query=query,
    final_answer=answer,
    iterations=iterations,
    artifact=artifact,
    rlm_log_path=log_path
)

# Store judgment
store.add_judgment(
    trajectory_id=trajectory_id,
    judgment=judgment
)

# Store extracted memories with provenance
for mem in extracted_memories:
    memory_id = store.add_memory(
        mem,
        provenance={
            "trajectory_id": trajectory_id,
            "run_id": run_id,
            "source": "extracted"
        }
    )
```

**Benefits:**
- ✅ Can review full trajectories later for analysis
- ✅ Can build curricula from successful trajectories
- ✅ Can implement MaTTS (needs multiple trajectories per query)
- ✅ Can track "why did this memory get extracted?"

---

## 4. Memory Usage Logging Gap

### Current Implementation

**None.** There's no record of which memories were retrieved and used for a given query.

**Current `retrieve_memories()` only increments `access_count`:**

```python
def retrieve_memories(store: MemoryStore, task: str, k: int = 3) -> list[MemoryItem]:
    # ... BM25 retrieval ...
    for i, _ in scored[:k]:
        store.memories[i].access_count += 1  # Global counter only
        results.append(store.memories[i])

    return results
```

**Problems:**
- Can't answer "which memories were retrieved for trajectory X?"
- Can't measure "did memory Y help or hurt?"
- No ranking/scoring metadata preserved

### Target Implementation

**`memory_usage` table:**

```sql
CREATE TABLE memory_usage (
    trajectory_id TEXT NOT NULL,
    memory_id TEXT NOT NULL,
    rank INTEGER NOT NULL,      -- 1st, 2nd, 3rd retrieved
    score REAL,                  -- BM25/similarity score
    FOREIGN KEY (trajectory_id) REFERENCES trajectories(trajectory_id),
    FOREIGN KEY (memory_id) REFERENCES memory_items(memory_id)
);
```

**Usage:**

```python
# During retrieval
retrieved = retrieve_memories(store, query, k=3)

# Later, after run completes
for rank, (memory, score) in enumerate(zip(retrieved, scores), start=1):
    store.record_usage(
        trajectory_id=trajectory_id,
        memory_id=memory.id,
        rank=rank,
        score=score
    )
```

**Enables queries like:**
- "Show me all trajectories that used memory X"
- "Which memories co-occur in successful vs failed trajectories?"
- "What's the success rate when memory Y is in top-3?"

---

## 5. Retrieval Method Gap

### Current Implementation

**BM25 over title + description + tags:**

```python
def retrieve_memories(store: MemoryStore, task: str, k: int = 3) -> list[MemoryItem]:
    if not store.memories:
        return []

    # Build BM25 index
    corpus = store.get_corpus_for_bm25()
    bm25 = BM25Okapi(corpus)

    # Query
    query_tokens = task.lower().split()
    scores = bm25.get_scores(query_tokens)
    # ...
```

**Pros:**
- ✅ Fast, deterministic, offline
- ✅ Works without embeddings

**Cons:**
- ❌ Lexical matching only (can't match synonyms)
- ❌ No semantic understanding
- ❌ Rebuilt every retrieval (inefficient for large corpora)

### Paper Method

**From paper:64:**

> During memory retrieval, the agent queries ReasoningBank with the current query context to identify the top-k relevant experiences and their corresponding memory items using **embedding-based similarity search**.

**Method:** Cosine similarity of query embedding vs pre-computed memory embeddings.

### Target Implementation

**Hybrid approach (best of both):**

1. **Primary:** SQLite FTS5 with BM25 ranking
   ```sql
   CREATE VIRTUAL TABLE memory_fts USING fts5(
       memory_id UNINDEXED,
       document,  -- title + description + tags
       tokenize='porter unicode61'
   );

   -- Retrieval
   SELECT memory_id, bm25(memory_fts) as score
   FROM memory_fts
   WHERE memory_fts MATCH ?
   ORDER BY score
   LIMIT ?;
   ```

2. **Fallback:** `rank-bm25` if FTS5 unavailable

3. **Future:** Add embedding-based retrieval with vector extension

**Benefits:**
- ✅ Indexed in SQLite (fast, scales)
- ✅ Deterministic (important for tests)
- ✅ Can upgrade to embeddings later without breaking API

---

## 6. Memory ID Stability Gap

### Current Implementation

**Random UUIDs:**

```python
memory = MemoryItem(
    id=str(uuid.uuid4()),  # Random on every extraction
    title=item['title'],
    # ...
)
```

**Problem:** Same memory extracted twice gets different IDs → duplicates.

### Target Implementation

**Content-based hash for deduplication:**

```python
import hashlib

def compute_memory_id(title: str, content: str) -> str:
    """Stable ID based on content hash."""
    text = f"{title}\n{content}"
    return hashlib.sha256(text.encode()).hexdigest()[:16]

# Usage
memory_id = compute_memory_id(title, content)

# Before adding, check if exists
if not store.has_memory(memory_id):
    store.add_memory(memory)
else:
    # Skip or merge
    pass
```

**Benefits:**
- ✅ Same strategy extracted twice = same ID
- ✅ Automatic deduplication
- ✅ Deterministic (important for packs)

---

## 7. Scope Metadata Gap

### Current Implementation

**Tags only:**

```python
memory = MemoryItem(
    # ...
    tags=['entity', 'search', 'describe', 'universal']
)
```

**No structured scope information.**

### Target Implementation

**Scope JSON:**

```json
{
  "ontology": null,           // null = universal, "prov" = PROV-specific
  "task_types": ["entity_description", "hierarchy"],
  "tools": ["search_entity", "describe_entity"],
  "transferable": true
}
```

**Enables:**
- Filtering: "Show me universal strategies only"
- Validation: "This memory requires tool X, do we have it?"
- Curriculum design: "Generate tasks for hierarchy strategies"

---

## 8. Pack Import/Export Gap

### Current Implementation

**None.** JSON file is the only persistence format, not designed for sharing.

### Target Implementation

**JSONL pack format:**

```jsonl
{"type": "meta", "curriculum_id": "prov_v1", "version": 1, "created_at": "2026-01-20T..."}
{"type": "memory", "memory_id": "a1b2c3...", "title": "...", "description": "...", "content": "...", "tags": [...], "scope": {...}}
{"type": "memory", "memory_id": "d4e5f6...", "title": "...", ...}
```

**Usage:**

```bash
# Export memories to pack
python -m rlm_runtime.cli export-pack --db memory.db --output packs/prov_v1.jsonl

# Import pack into database
python -m rlm_runtime.cli import-pack --db memory.db --pack packs/prov_v1.jsonl

# Commit to git
git add packs/prov_v1.jsonl
git commit -m "Add PROV curriculum memory pack v1"
```

**Benefits:**
- ✅ Git-friendly (text, line-by-line diffs)
- ✅ Shareable (ship curated memories with the package)
- ✅ Versioned (v1, v2, ...)
- ✅ Stable IDs prevent duplicates on import

---

## 9. Implementation Priority

### Must-Have for Phase 5 (SQLite ReasoningBank)

1. **SQLite schema with 5 tables** (runs, trajectories, judgments, memory_items, memory_usage)
2. **Store trajectories, not just memories**
3. **Provenance tracking** (trajectory_id, run_id in memory items)
4. **Memory usage logging** (what was retrieved for each query)
5. **FTS5 retrieval** with BM25 ranking
6. **Stable memory IDs** (content hash)
7. **Pack import/export** (JSONL format)

### Nice-to-Have (Can Defer)

8. **Embedding-based retrieval** (SQLite vector extension)
9. **Scope JSON** (can use tags for now)
10. **Advanced consolidation** (merging similar memories)
11. **MaTTS integration** (parallel/sequential scaling)

---

## 10. Migration Strategy

### Step 1: Create SQLite backend (Phase 5.1)

**File:** `rlm_runtime/memory/sqlite_schema.py`

```python
def ensure_schema(db_path: str) -> None:
    """Create tables if they don't exist."""
    conn = sqlite3.connect(db_path)
    # CREATE TABLE runs...
    # CREATE TABLE trajectories...
    # ...
    conn.commit()
    conn.close()
```

### Step 2: Implement MemoryBackend protocol (Phase 5.2)

**File:** `rlm_runtime/memory/sqlite_backend.py`

```python
class SQLiteMemoryBackend:
    def __init__(self, db_path: str):
        ensure_schema(db_path)
        self.conn = sqlite3.connect(db_path)

    def add_trajectory(self, run_id, task_query, iterations, ...) -> str:
        """Returns trajectory_id."""

    def add_judgment(self, trajectory_id, judgment) -> None:
        pass

    def add_memory(self, memory, provenance) -> str:
        """Returns memory_id."""

    def retrieve(self, task: str, k: int = 3) -> list[MemoryItem]:
        """FTS5 BM25 retrieval."""

    def record_usage(self, trajectory_id, memory_id, rank, score):
        """Log memory usage."""
```

### Step 3: Add FTS5 retrieval (Phase 5.3)

```python
def _create_fts_table(conn):
    conn.execute("""
        CREATE VIRTUAL TABLE IF NOT EXISTS memory_fts USING fts5(
            memory_id UNINDEXED,
            document,
            tokenize='porter unicode61'
        )
    """)

def retrieve(self, task: str, k: int = 3) -> list[MemoryItem]:
    cursor = self.conn.execute("""
        SELECT memory_id, bm25(memory_fts) as score
        FROM memory_fts
        WHERE memory_fts MATCH ?
        ORDER BY score
        LIMIT ?
    """, (task, k))
    # ...
```

### Step 4: Pack import/export (Phase 5.4)

```python
def export_pack(backend: SQLiteMemoryBackend, output_path: Path) -> str:
    """Export memories to JSONL pack."""
    memories = backend.get_all_memories()
    with open(output_path, 'w') as f:
        f.write(json.dumps({"type": "meta", ...}) + "\n")
        for mem in memories:
            f.write(json.dumps({"type": "memory", ...}) + "\n")

def import_pack(backend: SQLiteMemoryBackend, pack_path: Path) -> str:
    """Import JSONL pack, skip duplicates."""
    with open(pack_path) as f:
        for line in f:
            item = json.loads(line)
            if item["type"] == "memory":
                if not backend.has_memory(item["memory_id"]):
                    backend.add_memory(item)
```

---

## 11. Testing Strategy

### Unit Tests (Offline)

```python
def test_sqlite_schema_creation():
    """Schema creates all 5 tables."""
    ensure_schema(":memory:")
    conn = sqlite3.connect(":memory:")
    # Check tables exist

def test_memory_roundtrip():
    """Add memory, retrieve by ID."""
    backend = SQLiteMemoryBackend(":memory:")
    mem_id = backend.add_memory(memory, provenance={})
    retrieved = backend.get_memory(mem_id)
    assert retrieved.title == memory.title

def test_fts5_retrieval():
    """FTS5 returns relevant memories."""
    backend = SQLiteMemoryBackend(":memory:")
    backend.add_memory(MemoryItem(title="Search Entity", ...))
    results = backend.retrieve("how to find entities", k=3)
    assert len(results) > 0
```

### Integration Tests (With RLM)

```python
def test_full_loop_with_sqlite(prov_ontology):
    """Run query, extract memories, store in SQLite."""
    backend = SQLiteMemoryBackend("test.db")
    result = run_with_memory(
        query="What is Activity?",
        backend=backend,
        ontology_path=prov_ontology
    )
    # Check trajectory was stored
    # Check judgment was stored
    # Check memories were extracted
```

### Live Tests (API calls)

```python
@pytest.mark.live
def test_memory_improves_convergence(prov_ontology):
    """Second query converges faster with memory."""
    backend = SQLiteMemoryBackend("live.db")

    # First query (no memory)
    result1 = run_with_memory("What is Activity?", backend, prov_ontology)
    iters1 = result1.iteration_count

    # Second similar query (with memory)
    result2 = run_with_memory("What is Entity?", backend, prov_ontology)
    iters2 = result2.iteration_count

    # Should converge faster
    assert iters2 <= iters1
```

---

## 12. Summary: What Needs to Change

| Component | Current | Target | Effort |
|-----------|---------|--------|--------|
| **Storage** | JSON file | SQLite (5 tables) | 🔴 High |
| **Trajectory storage** | Not stored | Required | 🔴 High |
| **Provenance** | Minimal | Full lineage | 🟡 Medium |
| **Usage logging** | None | `memory_usage` table | 🟡 Medium |
| **Retrieval** | BM25 in-memory | FTS5 indexed | 🟡 Medium |
| **Memory IDs** | Random UUID | Content hash | 🟢 Low |
| **Packs** | None | JSONL import/export | 🟡 Medium |
| **API** | MemoryStore methods | Protocol-based backend | 🟡 Medium |

**Total Effort:** ~2-3 phases of focused work (Phase 5.1-5.4)

---

## 13. Conclusion

The current `rlm/procedural_memory.py` has the **right conceptual model** (closed loop, judge+extract, success/failure) but lacks the **infrastructure for production use**:

- ❌ Not durable across sessions
- ❌ No observability (can't measure effectiveness)
- ❌ No provenance (can't trace origins)
- ❌ Not shareable (no pack format)

**Phase 5 will fix these gaps** by migrating to SQLite with full provenance tracking, making ReasoningBank production-ready and aligned with the paper's vision.

**Next:** Implement Phase 5.1 (SQLite schema).
