"""SQLite-backed ReasoningBank for procedural memory.

Provides durable storage for RLM trajectories, judgments, and extracted memories
with FTS5 BM25 retrieval.
"""

from .sqlite_schema import ensure_schema, ensure_schema_on_conn, get_schema_version, has_fts5_support
from .backend import MemoryBackend, MemoryItem, is_memory_backend
from .sqlite_backend import SQLiteMemoryBackend
from .pack import export_pack, import_pack, validate_pack, merge_packs
from .extraction import format_memories_for_context, judge_trajectory_dspy, extract_memories_dspy

__all__ = [
    "ensure_schema",
    "ensure_schema_on_conn",
    "get_schema_version",
    "has_fts5_support",
    "MemoryBackend",
    "MemoryItem",
    "is_memory_backend",
    "SQLiteMemoryBackend",
    "export_pack",
    "import_pack",
    "validate_pack",
    "merge_packs",
    "format_memories_for_context",
    "judge_trajectory_dspy",
    "extract_memories_dspy",
]
