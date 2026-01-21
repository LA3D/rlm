# ReasoningBank Migration: SQLite-Backed Procedural Memory + Curriculum Packs

This document specifies the target architecture and implementation plan for migrating this repo’s “ReasoningBank” functionality to a **paper-aligned procedural memory loop** with a **SQLite-backed store**, plus **versioned curriculum memory packs** committed to git for reproducible bootstrapping.

Scope:
- Migrate “ReasoningBank” to mean **procedural memory** (learned strategies distilled from trajectories).
- Keep **RLM invariants** from `docs/planning/trajectory.md` (REPL-first, handles-not-dumps, bounded progressive disclosure).
- Implement a **SQLite memory service** that supports retrieval, provenance, trajectory logging, and import/export of curriculum packs.
- Define a test plan using local sample ontologies in `ontology/`.
- Prepare for an eventual “subagent/tool” interface (Codex CLI / Claude Code) with observability.

Non-goals (for this phase):
- Implementing MaTTS (memory-aware test-time scaling) end-to-end. We will design storage hooks so MaTTS can be added later.
- Changing the core RLM loop semantics (must remain `rlmpaper`-faithful).

---

## 1) Current State and Architectural Mismatch

This repo currently has:
- `rlm/core.py`: the RLM loop (REPL iteration protocol).
- `rlm/procedural_memory.py` (from `nbs/05_procedural_memory.ipynb`): a ReasoningBank-style closed loop:
  - `retrieve_memories()` → `format_memories_for_injection()` → `rlm_run()` → `judge_trajectory()` → `extract_memories()` → `store.add()`.
  - Retrieval uses `rank_bm25` (third-party) and an in-memory/JSON `MemoryStore`.
- `rlm/reasoning_bank.py` (from `nbs/06_reasoning_bank.ipynb`): ontology-specific *recipes* and context injection.

The “ReasoningBank paper” (`docs/reference/reasoning_bank_paper.md`) describes:
- Memory induction from **both success and failure**.
- Retrieval by similarity to the **task query** and prompt injection of memory items.
- Minimal consolidation (append) with a JSON persistence format.

The planned long-context system (`docs/planning/trajectory.md`) requires:
- Long context stays in the REPL (graphs/results as handles).
- Procedural memory stores “how to interact with handles,” not raw data.
- Strong observability (trajectories/logging) to drive extraction, debugging, and curriculum development.

### Decision: “ReasoningBank” = Procedural Memory

For clarity and alignment:
- **Procedural memory** (learned strategies) is the ReasoningBank memory loop.
- **Ontology recipes** remain a separate concept (authored, ontology-specific), injected only when appropriate.

We can keep the existing filenames for now to avoid churn, but the **SQLite store becomes the canonical backing store** for procedural memories and their provenance.

---

## 2) Target Architecture (Layered, Paper-Aligned, RLM-Compatible)

### 2.1 Four-layer context injection (unchanged conceptually)

1. **Layer 0: Sense card** (`rlm.ontology`): compact ontology metadata.
2. **Layer 1: Procedural memories (ReasoningBank)**: retrieved from SQLite store (learned/seeded).
3. **Layer 2: Ontology-specific recipes** (`rlm.reasoning_bank`): optional curated patterns.
4. **Layer 3: Base context**: GraphMeta summary / stats.

### 2.2 Closed loop (per query)

1. **RETRIEVE**: find top-k memory items relevant to the task query.
2. **INJECT**: add formatted memories to the RLM prompt with the “assess applicability” instruction.
3. **INTERACT**: run the RLM loop (REPL-first, bounded, uses handles + `llm_query` for chunk semantics).
4. **JUDGE**: success/failure + reason + confidence.
5. **EXTRACT**: distill up to N memory items (procedural, transferable) from the bounded artifact.
6. **STORE**: persist trajectory artifact, judgment, extracted items, and retrieval metadata.

This is already conceptually implemented in `rlm/procedural_memory.py`; the migration is primarily about **storage, retrieval, provenance, and packaging for curricula**.

---

## 3) SQLite Memory Store Design

### 3.1 Why SQLite

SQLite solves the requirements that JSON + in-memory stores struggle with:
- Persistent accumulation across sessions.
- Efficient retrieval as memories grow (FTS index).
- Provenance links: task → trajectory → judgment → extracted memories.
- Structured observability queries (“which memories helped reduce steps?”).
- Import/export to git-friendly curriculum packs (text).

### 3.2 Tables (minimum viable schema)

**`runs`**
- `run_id TEXT PRIMARY KEY` (uuid-ish, short ok)
- `created_at TEXT` (ISO)
- `model TEXT NULL`
- `ontology_name TEXT NULL` (e.g., `prov`, `sio`)
- `ontology_path TEXT NULL`
- `notes TEXT NULL`

**`trajectories`**
- `trajectory_id TEXT PRIMARY KEY`
- `run_id TEXT NOT NULL`
- `task_query TEXT NOT NULL`
- `final_answer TEXT`
- `iteration_count INTEGER NOT NULL`
- `converged INTEGER NOT NULL` (0/1)
- `artifact_json TEXT NOT NULL` (bounded `extract_trajectory_artifact` output)
- `rlm_log_path TEXT NULL` (JSONL from `rlm/logger.py`)
- `created_at TEXT NOT NULL`

**`judgments`**
- `trajectory_id TEXT PRIMARY KEY` (1:1 with trajectory)
- `is_success INTEGER NOT NULL`
- `reason TEXT NOT NULL`
- `confidence TEXT NOT NULL` (`high|medium|low`)
- `missing_json TEXT NOT NULL` (JSON array)

**`memory_items`**
- `memory_id TEXT PRIMARY KEY` (stable ID recommended; see §5)
- `title TEXT NOT NULL`
- `description TEXT NOT NULL`
- `content TEXT NOT NULL`
- `source_type TEXT NOT NULL` (`success|failure|human|pack`)
- `task_query TEXT NULL` (source task)
- `created_at TEXT NOT NULL`
- `tags_json TEXT NOT NULL`
- `scope_json TEXT NOT NULL` (see below)
- `provenance_json TEXT NOT NULL` (see below)
- `access_count INTEGER NOT NULL DEFAULT 0`
- `success_count INTEGER NOT NULL DEFAULT 0`
- `failure_count INTEGER NOT NULL DEFAULT 0`

**`memory_usage`** (observability: what was retrieved/injected for a given run)
- `trajectory_id TEXT NOT NULL`
- `memory_id TEXT NOT NULL`
- `rank INTEGER NOT NULL` (1..k)
- `score REAL NULL` (retriever-specific)

#### Scope JSON
Used to support curricula and ontology-specific strategies while keeping memories procedural:
```json
{
  "ontology": null,
  "task_types": ["entity_description", "hierarchy"],
  "tools": ["search_entity", "describe_entity", "probe_relationships"],
  "transferable": true
}
```

#### Provenance JSON
```json
{
  "source": "extracted|pack|human",
  "curriculum_id": "prov_curriculum_v1",
  "trajectory_id": "t-...",
  "run_id": "r-...",
  "exported_in_pack": "prov_v1"
}
```

### 3.3 Retrieval (FTS5 BM25 + fallback)

Preferred: **SQLite FTS5** virtual table over a “document” text combining:
- `title + description + tags + (optional) scope keywords`

Use:
- `WHERE fts MATCH ?`
- `ORDER BY bm25(fts)` (SQLite bm25 returns “lower is better”).

Fallbacks if FTS5 is unavailable:
- stdlib BM25 (Okapi) over an in-memory corpus loaded from SQLite.
- stdlib TF-IDF cosine (simpler, usually sufficient for small corpora).

Important: retrieval must be **offline** and **deterministic enough** for tests.

### 3.4 Consolidation and dedup

Keep the paper’s minimal consolidation as default (append), but add safe gates:
- Dedup by stable `memory_id` (see §5.2).
- Optional similarity-based merge (title/content similarity) can be a future enhancement.

---

## 4) Curriculum “Teaching” Workflow

Curricula are how you intentionally generate trajectories to teach strategies.

### 4.1 Curriculum spec (YAML)

Add `docs/curricula/*.yaml`, e.g. `docs/curricula/prov_v1.yaml`:
```yaml
id: prov_curriculum_v1
ontology:
  name: prov
  path: ontology/prov.ttl
tasks:
  - id: prov-orient-01
    query: "What namespaces are bound in this ontology?"
    tags: ["orientation"]
  - id: prov-entity-01
    query: "What is the Activity class?"
    tags: ["entity_description"]
  - id: prov-hierarchy-01
    query: "Find all subclasses of Activity."
    tags: ["hierarchy"]
```

### 4.2 Training run (curriculum execution)

Command concept (eventual CLI):
- `rlm memory train --db ~/.rlm/memory.db --curriculum docs/curricula/prov_v1.yaml --log-dir ./logs`

For each task:
- `retrieve` (top-k from DB)
- `inject` (bounded formatting)
- run `rlm_run` with ontology context set up in the namespace
- `log` trajectory via `RLMLogger` (JSONL)
- `judge` and `extract` (existing pipeline)
- write artifacts + extracted memories to SQLite with provenance:
  - `curriculum_id`, `task_id`, `ontology_name`

### 4.3 Curating: selecting memories to “ship”

Export criteria (initial defaults):
- `source_type in ('success','human','pack')` OR `judgment.confidence == 'high'`
- `score_generalization(memory) >= threshold` unless the pack is explicitly ontology-specific
- no hardcoded URIs for “universal” packs
- deduped by stable ID

Support a manual review loop by exporting “candidates” to a file for editing and re-import.

---

## 5) Memory Packs (Git-friendly, Shippable)

### 5.1 Why packs are text files (not a DB in git)

Packs must:
- merge/diff cleanly in PRs,
- be inspectable by humans,
- be easy to sign/version.

Therefore: **JSONL** (one memory item per line) or YAML.

Recommended: **JSONL** for stability and streaming.

### 5.2 Stable IDs

To keep diffs stable and make imports idempotent, use a deterministic ID:
- `memory_id = sha256(normalize(title) + "\n" + normalize(content) + "\n" + normalize(scope))[:16]`

This prevents churn when re-exporting the same memory set.

### 5.3 Pack format (JSONL)

`rlm/data/memory_packs/prov_v1.jsonl`:
```json
{"memory_id":"a1b2c3d4e5f6a7b8","title":"Describe Entity by Label","description":"...","content":"...","tags":["entity","universal"],"scope":{"ontology":null,"task_types":["entity_description"],"transferable":true},"provenance":{"source":"pack","pack":"core_v1"}}
```

### 5.4 Packaging

Update packaging so packs ship with the library:
- Add pack files under `rlm/` (not `docs/`) so they can be included as package data.
- Update `settings.ini` `package_data` (preferred with nbdev) and/or `MANIFEST.in`.

Example intent:
- `rlm/data/memory_packs/*.jsonl` included in distributions.

### 5.5 Import behavior

At runtime:
- `import_pack(pack_path, db)` inserts items if `memory_id` not present.
- Mark `source_type='pack'` and set provenance `{source:'pack', pack:'prov_v1'}`.

---

## 6) Tool/Subagent Interface (Codex / Claude Code)

We want a stable, scriptable interface that a coding agent can call as a tool.

### 6.1 Minimal CLI (recommended)

Add a CLI entrypoint (conceptual):
- `rlm-agent run --ontology ontology/prov.ttl --ontology-name prov --query "..." --db ~/.rlm/memory.db --json`

Return JSON:
```json
{
  "answer": "...",
  "iterations": 4,
  "run_id": "r-...",
  "trajectory_id": "t-...",
  "log_path": "logs/rlm_...jsonl",
  "memories_used": [{"memory_id":"...","rank":1,"score":-3.2e-6}]
}
```

This is the easiest integration point for Codex CLI / Claude Code “subagents”:
- deterministic invocation,
- clear artifacts and observability,
- no need for in-process object passing.

### 6.2 Python API (library users)

Provide a high-level call:
- `rlm.agent.run(query, ontology_path, db_path, *, memory_k=3, enable_extraction=True, log_dir=...)`

---

## 7) Observability and Logging

We need both:
- **trajectory-level logging** (RLM iterations, code blocks, stdout/stderr),
- **memory-level logging** (retrieval results, injection, extraction outputs).

### 7.1 RLM trajectory logging

Use `rlm/logger.py`:
- Create `RLMLogger(log_dir=...)`
- Log metadata (query, max_iters, ontology name/path, memory_k, pack(s) loaded)
- Log each iteration (prompt/response + code blocks)
- Store `rlm_log_path` in SQLite `trajectories`.

### 7.2 Memory retrieval/injection logging

For each run, store:
- retrieved memory IDs + ranks + scores in `memory_usage`
- optionally store an “injection preview” (bounded) in `trajectories.artifact_json` or a separate table.

### 7.3 Debugging queries enabled by SQLite

Examples:
- “Which memory items correlate with reduced iteration_count?”
- “Which memories are retrieved frequently but lead to failures?”
- “Which curriculum tasks produce the most reusable memories?”

---

## 8) Migration Plan (Incremental, Low-Risk)

### Phase A — Add SQLite store behind a backend interface

1. Introduce a backend abstraction (conceptual):
   - `MemoryBackend.retrieve(task, k) -> list[(MemoryItem, score)]`
   - `MemoryBackend.add(memory)`
   - `MemoryBackend.record_usage(trajectory_id, retrieved)`
   - `MemoryBackend.save_artifacts(...)`
2. Implement `SQLiteMemoryBackend`.
3. Keep the current JSON `MemoryStore` as a fallback backend (for minimal environments).

### Phase B — Switch `rlm_run_with_memory` to use the backend

1. Replace direct `retrieve_memories(store, ...)` calls with backend retrieval.
2. Keep `format_memories_for_injection()` unchanged (it formats a list of MemoryItems).
3. Ensure the loop writes trajectory artifacts + judgments into SQLite.

### Phase C — Add curriculum runner + pack import/export

1. Curriculum runner reads YAML, executes tasks, stores runs.
2. Pack exporter selects memories and writes JSONL with stable IDs.
3. Pack importer loads JSONL into SQLite.

### Phase D — Deprecate `rank-bm25`

1. Default to SQLite FTS5 bm25 retrieval.
2. Provide stdlib fallback.
3. Remove `rank-bm25` from `settings.ini` requirements once parity is validated.

---

## 9) Testing Plan

We will keep tests **offline** by default and only gate “live” LLM calls behind markers/env vars.

### 9.1 Unit tests (no LLM calls)

Add `tests/unit/test_sqlite_memory_store.py`:
- schema creation/migrations
- insert/retrieve memory items
- FTS retrieval returns expected item for queries like “SPARQL entity search”
- import/export pack roundtrip (JSONL)
- stable ID determinism
- dedup behavior on re-import

### 9.2 Integration tests (no live API calls)

Add `tests/integration/test_memory_sqlite_closed_loop.py`:
- monkeypatch `llm_query` to return deterministic JSON for judge/extractor
- feed a synthetic `RLMIteration` list (or monkeypatch `rlm_run`) so the pipeline runs end-to-end without network:
  - retrieve → inject → interact (stub) → judge (stub) → extract (stub) → store (sqlite)
- assert:
  - `trajectories`, `judgments`, `memory_items`, `memory_usage` rows exist
  - exported pack contains expected items

### 9.3 Ontology fixtures (local sample ontologies)

Use `ontology/` assets to validate “handles not dumps” surfaces:
- `setup_ontology_context()` loads ontology, builds GraphMeta, and bounded view functions exist.
- Confirm curriculum tasks can mount ontologies and run without dumping triples to prompt (test by checking injected context length bounds).

### 9.4 Live tests (optional)

Keep existing `tests/live/*` for:
- end-to-end run with real LLM backend
- ensure retrieval reduces iterations on known tasks

---

## 10) Open Decisions (to resolve before coding)

1. **Naming**: keep `procedural_memory.py` / `reasoning_bank.py` as-is vs. rename to reduce conceptual confusion.
2. **FTS5 requirement**: require FTS5 (preferred) vs. best-effort fallback.
3. **Pack scope**: do we want packs per ontology (`prov_v1`) plus a universal pack (`core_v1`), or a single combined pack with scopes?
4. **Judgment model**: keep LLM-judge only vs. allow deterministic verifiers for some curricula tasks.
5. **Policy**: when to write extracted memories (always append vs. gated by confidence/generalization score).

---

## Appendix: How this supports a future “subagent/tool”

Once the SQLite store + CLI exist:
- A coding agent can call `rlm-agent run ...` as a subagent/tool.
- It receives a structured JSON response + artifact paths.
- Observability is built-in (JSONL logs + DB rows), enabling debugging and curriculum iteration.

