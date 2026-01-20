"""Memory backend protocol and data structures.

Defines the protocol for memory storage backends and the MemoryItem structure.
"""

from __future__ import annotations

from dataclasses import dataclass, field, asdict
from typing import Protocol, Any, Optional, runtime_checkable
from datetime import datetime, timezone
import json


@dataclass
class MemoryItem:
    """A reusable procedural memory extracted from an RLM trajectory.

    Attributes:
        memory_id: Stable identifier (content-based hash recommended)
        title: Concise identifier (≤10 words)
        description: One-sentence summary
        content: Procedural steps/checklist/template (Markdown)
        source_type: 'success', 'failure', 'human', or 'pack'
        task_query: Original task that produced this memory
        created_at: ISO timestamp
        tags: Keywords for retrieval
        scope: Applicability scope (ontology, task_types, tools, transferable)
        provenance: Origin tracking (trajectory_id, run_id, curriculum_id, etc.)
        access_count: Number of times retrieved
        success_count: Number of successful trajectories that used this
        failure_count: Number of failed trajectories that used this
    """

    memory_id: str
    title: str
    description: str
    content: str
    source_type: str  # 'success' | 'failure' | 'human' | 'pack'
    task_query: str
    created_at: str
    tags: list[str] = field(default_factory=list)
    scope: dict[str, Any] = field(default_factory=dict)
    provenance: dict[str, Any] = field(default_factory=dict)
    access_count: int = 0
    success_count: int = 0
    failure_count: int = 0

    def to_dict(self) -> dict:
        """Convert to dictionary for JSON serialization."""
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict) -> 'MemoryItem':
        """Create MemoryItem from dictionary."""
        # Handle old format from rlm/procedural_memory.py
        if 'tags' in data and data['tags'] is None:
            data['tags'] = []
        if 'scope' not in data:
            data['scope'] = {}
        if 'provenance' not in data:
            data['provenance'] = {}

        return cls(**data)

    @staticmethod
    def compute_id(title: str, content: str) -> str:
        """Compute stable content-based ID for deduplication.

        Args:
            title: Memory title
            content: Memory content

        Returns:
            16-character hex hash of title+content
        """
        import hashlib
        text = f"{title}\n{content}"
        return hashlib.sha256(text.encode()).hexdigest()[:16]


@runtime_checkable
class MemoryBackend(Protocol):
    """Protocol for memory storage backends.

    Backends must implement methods for storing trajectories, judgments,
    and memories, as well as retrieving relevant memories and tracking usage.
    """

    def add_run(
        self,
        run_id: str,
        model: Optional[str] = None,
        ontology_name: Optional[str] = None,
        ontology_path: Optional[str] = None,
        notes: Optional[str] = None,
    ) -> str:
        """Record a new RLM run.

        Args:
            run_id: Unique run identifier
            model: Model used (e.g., "claude-sonnet-4-5")
            ontology_name: Name of ontology (e.g., "prov")
            ontology_path: Path to ontology file
            notes: Optional notes

        Returns:
            run_id
        """
        ...

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
        """Store a trajectory from an RLM run.

        Args:
            trajectory_id: Unique trajectory identifier
            run_id: Associated run ID
            task_query: Task query that was executed
            final_answer: Final answer produced
            iteration_count: Number of iterations taken
            converged: Whether RLM converged properly
            artifact: Bounded trajectory artifact (from extract_trajectory_artifact)
            rlm_log_path: Optional path to JSONL log file

        Returns:
            trajectory_id
        """
        ...

    def add_judgment(
        self,
        trajectory_id: str,
        is_success: bool,
        reason: str,
        confidence: str,
        missing: list[str],
    ) -> None:
        """Store a judgment for a trajectory.

        Args:
            trajectory_id: Trajectory being judged
            is_success: Whether trajectory was successful
            reason: Explanation of judgment
            confidence: 'high', 'medium', or 'low'
            missing: List of missing evidence/requirements
        """
        ...

    def add_memory(
        self,
        memory: MemoryItem,
    ) -> str:
        """Store a memory item.

        Args:
            memory: MemoryItem to store

        Returns:
            memory_id

        Note:
            If memory_id already exists, this may update or skip depending on implementation.
        """
        ...

    def retrieve(
        self,
        task: str,
        k: int = 3,
        filters: Optional[dict] = None,
    ) -> list[MemoryItem]:
        """Retrieve top-k relevant memories for a task.

        Args:
            task: Task query string
            k: Number of memories to retrieve
            filters: Optional filters (e.g., {"source_type": "success", "ontology": "prov"})

        Returns:
            List of top-k MemoryItem objects ordered by relevance
        """
        ...

    def record_usage(
        self,
        trajectory_id: str,
        memory_id: str,
        rank: int,
        score: Optional[float] = None,
    ) -> None:
        """Record that a memory was retrieved and used for a trajectory.

        Args:
            trajectory_id: Trajectory that used the memory
            memory_id: Memory that was retrieved
            rank: Rank in retrieval (1 = top result)
            score: Optional retrieval score (BM25, cosine similarity, etc.)
        """
        ...

    def has_memory(self, memory_id: str) -> bool:
        """Check if a memory with the given ID exists.

        Args:
            memory_id: Memory ID to check

        Returns:
            True if memory exists, False otherwise
        """
        ...

    def get_memory(self, memory_id: str) -> Optional[MemoryItem]:
        """Retrieve a specific memory by ID.

        Args:
            memory_id: Memory ID to retrieve

        Returns:
            MemoryItem if found, None otherwise
        """
        ...

    def get_all_memories(
        self,
        filters: Optional[dict] = None,
    ) -> list[MemoryItem]:
        """Get all memories, optionally filtered.

        Args:
            filters: Optional filters (e.g., {"source_type": "pack"})

        Returns:
            List of all matching MemoryItem objects
        """
        ...

    def update_memory_stats(
        self,
        memory_id: str,
        accessed: bool = False,
        success: bool = False,
        failure: bool = False,
    ) -> None:
        """Update memory usage statistics.

        Args:
            memory_id: Memory to update
            accessed: Whether to increment access_count
            success: Whether to increment success_count
            failure: Whether to increment failure_count
        """
        ...


def is_memory_backend(obj: Any) -> bool:
    """Check if an object implements the MemoryBackend protocol.

    Args:
        obj: Object to check

    Returns:
        True if obj implements MemoryBackend protocol
    """
    return isinstance(obj, MemoryBackend)
