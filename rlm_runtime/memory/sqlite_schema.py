"""SQLite schema for ReasoningBank procedural memory.

Schema includes 5 core tables:
1. runs - Metadata for each RLM execution session
2. trajectories - Full trajectory data (iterations, answer, artifact)
3. judgments - Success/failure judgments for trajectories
4. memory_items - Extracted procedural memories
5. memory_usage - Tracks which memories were retrieved for each trajectory

Plus FTS5 virtual table for efficient BM25 retrieval.
"""

import sqlite3
from pathlib import Path
from typing import Union

SCHEMA_VERSION = 1

# SQL for creating tables
RUNS_TABLE = """
CREATE TABLE IF NOT EXISTS runs (
    run_id TEXT PRIMARY KEY,
    created_at TEXT NOT NULL,
    model TEXT,
    ontology_name TEXT,
    ontology_path TEXT,
    notes TEXT
);
"""

TRAJECTORIES_TABLE = """
CREATE TABLE IF NOT EXISTS trajectories (
    trajectory_id TEXT PRIMARY KEY,
    run_id TEXT NOT NULL,
    task_query TEXT NOT NULL,
    final_answer TEXT,
    iteration_count INTEGER NOT NULL,
    converged INTEGER NOT NULL,
    artifact_json TEXT NOT NULL,
    rlm_log_path TEXT,
    created_at TEXT NOT NULL,
    FOREIGN KEY (run_id) REFERENCES runs(run_id)
);
"""

JUDGMENTS_TABLE = """
CREATE TABLE IF NOT EXISTS judgments (
    trajectory_id TEXT PRIMARY KEY,
    is_success INTEGER NOT NULL,
    reason TEXT NOT NULL,
    confidence TEXT NOT NULL,
    missing_json TEXT NOT NULL,
    FOREIGN KEY (trajectory_id) REFERENCES trajectories(trajectory_id)
);
"""

MEMORY_ITEMS_TABLE = """
CREATE TABLE IF NOT EXISTS memory_items (
    memory_id TEXT PRIMARY KEY,
    title TEXT NOT NULL,
    description TEXT NOT NULL,
    content TEXT NOT NULL,
    source_type TEXT NOT NULL,
    task_query TEXT,
    created_at TEXT NOT NULL,
    tags_json TEXT NOT NULL,
    scope_json TEXT NOT NULL,
    provenance_json TEXT NOT NULL,
    access_count INTEGER NOT NULL DEFAULT 0,
    success_count INTEGER NOT NULL DEFAULT 0,
    failure_count INTEGER NOT NULL DEFAULT 0
);
"""

MEMORY_USAGE_TABLE = """
CREATE TABLE IF NOT EXISTS memory_usage (
    trajectory_id TEXT NOT NULL,
    memory_id TEXT NOT NULL,
    rank INTEGER NOT NULL,
    score REAL,
    PRIMARY KEY (trajectory_id, memory_id),
    FOREIGN KEY (trajectory_id) REFERENCES trajectories(trajectory_id),
    FOREIGN KEY (memory_id) REFERENCES memory_items(memory_id)
);
"""

# FTS5 virtual table for fast BM25 retrieval
MEMORY_FTS_TABLE = """
CREATE VIRTUAL TABLE IF NOT EXISTS memory_fts USING fts5(
    memory_id UNINDEXED,
    document,
    tokenize='porter unicode61'
);
"""

# Indices for common queries
INDICES = [
    "CREATE INDEX IF NOT EXISTS idx_trajectories_run_id ON trajectories(run_id);",
    "CREATE INDEX IF NOT EXISTS idx_trajectories_created_at ON trajectories(created_at);",
    "CREATE INDEX IF NOT EXISTS idx_memory_items_created_at ON memory_items(created_at);",
    "CREATE INDEX IF NOT EXISTS idx_memory_items_source_type ON memory_items(source_type);",
    "CREATE INDEX IF NOT EXISTS idx_memory_usage_memory_id ON memory_usage(memory_id);",
]

# Schema version tracking
SCHEMA_VERSION_TABLE = """
CREATE TABLE IF NOT EXISTS schema_version (
    version INTEGER PRIMARY KEY,
    applied_at TEXT NOT NULL
);
"""


def ensure_schema_on_conn(conn: sqlite3.Connection) -> None:
    """Create schema on an existing connection.

    Args:
        conn: SQLite connection

    Raises:
        sqlite3.Error: If schema creation fails
    """
    cursor = conn.cursor()

    try:
        # Create core tables
        cursor.execute(RUNS_TABLE)
        cursor.execute(TRAJECTORIES_TABLE)
        cursor.execute(JUDGMENTS_TABLE)
        cursor.execute(MEMORY_ITEMS_TABLE)
        cursor.execute(MEMORY_USAGE_TABLE)

        # Create FTS5 table (may fail if FTS5 not available)
        try:
            cursor.execute(MEMORY_FTS_TABLE)
        except sqlite3.OperationalError as e:
            # FTS5 not available - will use fallback retrieval
            print(f"Warning: FTS5 not available ({e}). Retrieval will use fallback method.")

        # Create indices
        for idx_sql in INDICES:
            cursor.execute(idx_sql)

        # Create schema version table
        cursor.execute(SCHEMA_VERSION_TABLE)

        # Record schema version
        cursor.execute(
            "INSERT OR IGNORE INTO schema_version (version, applied_at) VALUES (?, datetime('now'))",
            (SCHEMA_VERSION,)
        )

        conn.commit()
    except Exception as e:
        conn.rollback()
        raise


def ensure_schema(db_path: Union[str, Path]) -> None:
    """Create all tables and indices if they don't exist.

    Args:
        db_path: Path to SQLite database file (or ":memory:" for in-memory)

    Raises:
        sqlite3.Error: If schema creation fails
    """
    conn = sqlite3.connect(str(db_path))
    try:
        ensure_schema_on_conn(conn)
    finally:
        conn.close()


def get_schema_version(db_path: Union[str, Path]) -> int:
    """Get the current schema version of the database.

    Args:
        db_path: Path to SQLite database file

    Returns:
        Schema version number, or 0 if not initialized
    """
    conn = sqlite3.connect(str(db_path))
    cursor = conn.cursor()

    try:
        cursor.execute("SELECT version FROM schema_version ORDER BY version DESC LIMIT 1")
        result = cursor.fetchone()
        return result[0] if result else 0
    except sqlite3.OperationalError:
        # schema_version table doesn't exist
        return 0
    finally:
        conn.close()


def has_fts5_support(db_path: Union[str, Path]) -> bool:
    """Check if FTS5 is available in this SQLite.

    Args:
        db_path: Path to SQLite database file

    Returns:
        True if FTS5 is available, False otherwise
    """
    conn = sqlite3.connect(str(db_path))
    cursor = conn.cursor()

    try:
        # Try to create a temporary FTS5 table
        cursor.execute("CREATE VIRTUAL TABLE IF NOT EXISTS _fts_test USING fts5(test)")
        cursor.execute("DROP TABLE IF EXISTS _fts_test")
        return True
    except sqlite3.OperationalError:
        return False
    finally:
        conn.close()


def list_tables(db_path: Union[str, Path]) -> list[str]:
    """List all tables in the database.

    Args:
        db_path: Path to SQLite database file

    Returns:
        List of table names
    """
    conn = sqlite3.connect(str(db_path))
    cursor = conn.cursor()

    try:
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name")
        return [row[0] for row in cursor.fetchall()]
    finally:
        conn.close()


def get_table_info(db_path: Union[str, Path], table_name: str) -> list[dict]:
    """Get column information for a table.

    Args:
        db_path: Path to SQLite database file
        table_name: Name of table to inspect

    Returns:
        List of column info dicts with keys: cid, name, type, notnull, dflt_value, pk
    """
    conn = sqlite3.connect(str(db_path))
    cursor = conn.cursor()

    try:
        cursor.execute(f"PRAGMA table_info({table_name})")
        columns = cursor.fetchall()
        return [
            {
                "cid": col[0],
                "name": col[1],
                "type": col[2],
                "notnull": bool(col[3]),
                "dflt_value": col[4],
                "pk": bool(col[5])
            }
            for col in columns
        ]
    finally:
        conn.close()
