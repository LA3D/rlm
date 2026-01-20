"""SQLite-backed memory storage implementation.

Implements the MemoryBackend protocol with:
- Persistent storage across sessions
- FTS5 BM25 retrieval (with fallback to rank-bm25)
- Full provenance tracking
- Memory usage logging
"""

from __future__ import annotations

import sqlite3
import json
from pathlib import Path
from typing import Optional, Union
from datetime import datetime, timezone

from .backend import MemoryBackend, MemoryItem
from .sqlite_schema import ensure_schema_on_conn, has_fts5_support


class SQLiteMemoryBackend:
    """SQLite-backed implementation of MemoryBackend protocol.

    Provides persistent storage with full provenance tracking and efficient retrieval.

    Attributes:
        db_path: Path to SQLite database file
        conn: SQLite connection (persistent)
        has_fts5: Whether FTS5 is available for retrieval
    """

    def __init__(self, db_path: Union[str, Path]):
        """Initialize SQLite backend.

        Args:
            db_path: Path to SQLite database file (or ":memory:" for in-memory)
        """
        self.db_path = str(db_path)
        self.conn = sqlite3.connect(self.db_path)
        self.conn.row_factory = sqlite3.Row  # Access columns by name

        # Create schema on the connection we just opened
        ensure_schema_on_conn(self.conn)

        # Check FTS5 support on this connection
        try:
            cursor = self.conn.cursor()
            cursor.execute("CREATE VIRTUAL TABLE IF NOT EXISTS _fts_test USING fts5(test)")
            cursor.execute("DROP TABLE IF EXISTS _fts_test")
            self.has_fts5 = True
        except sqlite3.OperationalError:
            self.has_fts5 = False

    def close(self) -> None:
        """Close the database connection."""
        if self.conn:
            self.conn.close()

    def __enter__(self):
        """Context manager support."""
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager cleanup."""
        self.close()

    # ===== Run Management =====

    def add_run(
        self,
        run_id: str,
        model: Optional[str] = None,
        ontology_name: Optional[str] = None,
        ontology_path: Optional[str] = None,
        notes: Optional[str] = None,
    ) -> str:
        """Record a new RLM run."""
        cursor = self.conn.cursor()
        cursor.execute(
            """
            INSERT INTO runs (run_id, created_at, model, ontology_name, ontology_path, notes)
            VALUES (?, datetime('now'), ?, ?, ?, ?)
            """,
            (run_id, model, ontology_name, ontology_path, notes)
        )
        self.conn.commit()
        return run_id

    # ===== Trajectory Management =====

    def add_trajectory(
        self,
        trajectory_id: str,
        run_id: str,
        task_query: str,
        final_answer: str,
        iteration_count: int,
        converged: bool,
        artifact: dict,
        rlm_log_path: Optional[str] = None,
    ) -> str:
        """Store a trajectory from an RLM run."""
        cursor = self.conn.cursor()
        cursor.execute(
            """
            INSERT INTO trajectories (
                trajectory_id, run_id, task_query, final_answer,
                iteration_count, converged, artifact_json, rlm_log_path, created_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, datetime('now'))
            """,
            (
                trajectory_id,
                run_id,
                task_query,
                final_answer,
                iteration_count,
                1 if converged else 0,
                json.dumps(artifact),
                rlm_log_path,
            )
        )
        self.conn.commit()
        return trajectory_id

    def get_trajectory(self, trajectory_id: str) -> Optional[dict]:
        """Retrieve a trajectory by ID.

        Returns:
            Dict with trajectory data, or None if not found
        """
        cursor = self.conn.cursor()
        cursor.execute(
            "SELECT * FROM trajectories WHERE trajectory_id = ?",
            (trajectory_id,)
        )
        row = cursor.fetchone()
        if not row:
            return None

        return {
            "trajectory_id": row["trajectory_id"],
            "run_id": row["run_id"],
            "task_query": row["task_query"],
            "final_answer": row["final_answer"],
            "iteration_count": row["iteration_count"],
            "converged": bool(row["converged"]),
            "artifact": json.loads(row["artifact_json"]),
            "rlm_log_path": row["rlm_log_path"],
            "created_at": row["created_at"],
        }

    # ===== Judgment Management =====

    def add_judgment(
        self,
        trajectory_id: str,
        is_success: bool,
        reason: str,
        confidence: str,
        missing: list[str],
    ) -> None:
        """Store a judgment for a trajectory."""
        cursor = self.conn.cursor()
        cursor.execute(
            """
            INSERT INTO judgments (trajectory_id, is_success, reason, confidence, missing_json)
            VALUES (?, ?, ?, ?, ?)
            """,
            (
                trajectory_id,
                1 if is_success else 0,
                reason,
                confidence,
                json.dumps(missing),
            )
        )
        self.conn.commit()

    def get_judgment(self, trajectory_id: str) -> Optional[dict]:
        """Retrieve judgment for a trajectory.

        Returns:
            Dict with judgment data, or None if not found
        """
        cursor = self.conn.cursor()
        cursor.execute(
            "SELECT * FROM judgments WHERE trajectory_id = ?",
            (trajectory_id,)
        )
        row = cursor.fetchone()
        if not row:
            return None

        return {
            "trajectory_id": row["trajectory_id"],
            "is_success": bool(row["is_success"]),
            "reason": row["reason"],
            "confidence": row["confidence"],
            "missing": json.loads(row["missing_json"]),
        }

    # ===== Memory Management =====

    def add_memory(self, memory: MemoryItem) -> str:
        """Store a memory item.

        If memory_id already exists, skips insertion.

        Returns:
            memory_id
        """
        cursor = self.conn.cursor()

        # Check if exists
        if self.has_memory(memory.memory_id):
            return memory.memory_id

        # Insert into memory_items table
        cursor.execute(
            """
            INSERT INTO memory_items (
                memory_id, title, description, content, source_type,
                task_query, created_at, tags_json, scope_json, provenance_json,
                access_count, success_count, failure_count
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                memory.memory_id,
                memory.title,
                memory.description,
                memory.content,
                memory.source_type,
                memory.task_query,
                memory.created_at,
                json.dumps(memory.tags),
                json.dumps(memory.scope),
                json.dumps(memory.provenance),
                memory.access_count,
                memory.success_count,
                memory.failure_count,
            )
        )

        # Update FTS5 index if available
        if self.has_fts5:
            document = self._build_fts_document(memory)
            cursor.execute(
                "INSERT INTO memory_fts (memory_id, document) VALUES (?, ?)",
                (memory.memory_id, document)
            )

        self.conn.commit()
        return memory.memory_id

    def has_memory(self, memory_id: str) -> bool:
        """Check if a memory with the given ID exists."""
        cursor = self.conn.cursor()
        cursor.execute(
            "SELECT 1 FROM memory_items WHERE memory_id = ?",
            (memory_id,)
        )
        return cursor.fetchone() is not None

    def get_memory(self, memory_id: str) -> Optional[MemoryItem]:
        """Retrieve a specific memory by ID."""
        cursor = self.conn.cursor()
        cursor.execute(
            "SELECT * FROM memory_items WHERE memory_id = ?",
            (memory_id,)
        )
        row = cursor.fetchone()
        if not row:
            return None

        return self._row_to_memory(row)

    def get_all_memories(self, filters: Optional[dict] = None) -> list[MemoryItem]:
        """Get all memories, optionally filtered."""
        cursor = self.conn.cursor()

        # Build query with filters
        query = "SELECT * FROM memory_items"
        params = []

        if filters:
            conditions = []
            if "source_type" in filters:
                conditions.append("source_type = ?")
                params.append(filters["source_type"])
            if "ontology" in filters:
                conditions.append("scope_json LIKE ?")
                params.append(f'%"ontology": "{filters["ontology"]}"%')

            if conditions:
                query += " WHERE " + " AND ".join(conditions)

        query += " ORDER BY created_at DESC"

        cursor.execute(query, params)
        return [self._row_to_memory(row) for row in cursor.fetchall()]

    def update_memory_stats(
        self,
        memory_id: str,
        accessed: bool = False,
        success: bool = False,
        failure: bool = False,
    ) -> None:
        """Update memory usage statistics."""
        cursor = self.conn.cursor()

        updates = []
        if accessed:
            updates.append("access_count = access_count + 1")
        if success:
            updates.append("success_count = success_count + 1")
        if failure:
            updates.append("failure_count = failure_count + 1")

        if updates:
            query = f"UPDATE memory_items SET {', '.join(updates)} WHERE memory_id = ?"
            cursor.execute(query, (memory_id,))
            self.conn.commit()

    # ===== Retrieval =====

    def retrieve(
        self,
        task: str,
        k: int = 3,
        filters: Optional[dict] = None,
    ) -> list[MemoryItem]:
        """Retrieve top-k relevant memories for a task.

        Uses FTS5 BM25 if available, otherwise falls back to rank-bm25.
        """
        if self.has_fts5:
            return self._retrieve_fts5(task, k, filters)
        else:
            return self._retrieve_fallback(task, k, filters)

    def _retrieve_fts5(
        self,
        task: str,
        k: int,
        filters: Optional[dict] = None,
    ) -> list[MemoryItem]:
        """Retrieve using FTS5 BM25."""
        cursor = self.conn.cursor()

        # FTS5 query (BM25 ranking built-in)
        # Note: bm25() returns negative scores, lower is better
        query = """
            SELECT m.*, bm25(f.memory_fts) as score
            FROM memory_fts f
            JOIN memory_items m ON f.memory_id = m.memory_id
            WHERE f.document MATCH ?
            ORDER BY score
            LIMIT ?
        """

        # Tokenize query and join with OR for flexible matching
        # Remove common stop words and punctuation
        import re
        tokens = re.findall(r'\b\w+\b', task.lower())
        stop_words = {'what', 'is', 'the', 'how', 'to', 'a', 'an', 'and', 'or', 'for', 'in', 'on', 'at'}
        tokens = [t for t in tokens if t not in stop_words and len(t) > 2]

        if not tokens:
            # If no tokens after filtering, return empty
            return []

        # Build FTS5 query: token1 OR token2 OR token3
        fts_query = ' OR '.join(tokens)

        cursor.execute(query, (fts_query, k))
        return [self._row_to_memory(row) for row in cursor.fetchall()]

    def _retrieve_fallback(
        self,
        task: str,
        k: int,
        filters: Optional[dict] = None,
    ) -> list[MemoryItem]:
        """Fallback retrieval using rank-bm25."""
        try:
            from rank_bm25 import BM25Okapi
        except ImportError:
            # If rank-bm25 not available, return empty
            return []

        # Get all memories
        memories = self.get_all_memories(filters)
        if not memories:
            return []

        # Build corpus
        corpus = []
        for mem in memories:
            doc = self._build_fts_document_for_memory(mem)
            corpus.append(doc.lower().split())

        # BM25 retrieval
        bm25 = BM25Okapi(corpus)
        query_tokens = task.lower().split()
        scores = bm25.get_scores(query_tokens)

        # Get top-k
        scored = [(i, score) for i, score in enumerate(scores)]
        scored.sort(key=lambda x: x[1], reverse=True)

        return [memories[i] for i, _ in scored[:k]]

    def _build_fts_document(self, memory: MemoryItem) -> str:
        """Build searchable document from memory for FTS5."""
        parts = [memory.title, memory.description]
        parts.extend(memory.tags)
        if memory.scope.get("task_types"):
            parts.extend(memory.scope["task_types"])
        return " ".join(parts)

    def _build_fts_document_for_memory(self, memory: MemoryItem) -> str:
        """Build document for fallback retrieval (same as FTS but returns string)."""
        return self._build_fts_document(memory)

    # ===== Memory Usage Tracking =====

    def record_usage(
        self,
        trajectory_id: str,
        memory_id: str,
        rank: int,
        score: Optional[float] = None,
    ) -> None:
        """Record that a memory was retrieved and used for a trajectory."""
        cursor = self.conn.cursor()
        cursor.execute(
            """
            INSERT OR IGNORE INTO memory_usage (trajectory_id, memory_id, rank, score)
            VALUES (?, ?, ?, ?)
            """,
            (trajectory_id, memory_id, rank, score)
        )
        self.conn.commit()

    def get_usage_for_trajectory(self, trajectory_id: str) -> list[dict]:
        """Get all memories that were used for a trajectory.

        Returns:
            List of dicts with keys: memory_id, rank, score
        """
        cursor = self.conn.cursor()
        cursor.execute(
            "SELECT * FROM memory_usage WHERE trajectory_id = ? ORDER BY rank",
            (trajectory_id,)
        )
        return [
            {
                "memory_id": row["memory_id"],
                "rank": row["rank"],
                "score": row["score"],
            }
            for row in cursor.fetchall()
        ]

    def get_usage_for_memory(self, memory_id: str) -> list[dict]:
        """Get all trajectories that used a memory.

        Returns:
            List of dicts with keys: trajectory_id, rank, score
        """
        cursor = self.conn.cursor()
        cursor.execute(
            "SELECT * FROM memory_usage WHERE memory_id = ? ORDER BY rank",
            (memory_id,)
        )
        return [
            {
                "trajectory_id": row["trajectory_id"],
                "rank": row["rank"],
                "score": row["score"],
            }
            for row in cursor.fetchall()
        ]

    # ===== Utility Methods =====

    def _row_to_memory(self, row: sqlite3.Row) -> MemoryItem:
        """Convert database row to MemoryItem."""
        return MemoryItem(
            memory_id=row["memory_id"],
            title=row["title"],
            description=row["description"],
            content=row["content"],
            source_type=row["source_type"],
            task_query=row["task_query"],
            created_at=row["created_at"],
            tags=json.loads(row["tags_json"]),
            scope=json.loads(row["scope_json"]),
            provenance=json.loads(row["provenance_json"]),
            access_count=row["access_count"],
            success_count=row["success_count"],
            failure_count=row["failure_count"],
        )

    def get_stats(self) -> dict:
        """Get database statistics.

        Returns:
            Dict with counts of runs, trajectories, judgments, memories
        """
        cursor = self.conn.cursor()

        stats = {}
        for table in ["runs", "trajectories", "judgments", "memory_items", "memory_usage"]:
            cursor.execute(f"SELECT COUNT(*) FROM {table}")
            stats[table] = cursor.fetchone()[0]

        return stats
