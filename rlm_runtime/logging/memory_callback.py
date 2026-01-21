"""Memory event logging for ReasoningBank.

Logs memory retrieval, extraction, and usage events alongside trajectory
execution for observability.
"""

from __future__ import annotations

import json
from pathlib import Path
from datetime import datetime, timezone
from typing import Any, Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from rlm_runtime.memory import MemoryItem


class MemoryEventLogger:
    """Logger for memory-related events.

    Logs memory retrieval, judgment, extraction, and storage events to the
    same JSONL file as TrajectoryCallback for unified logging.

    Example:
        logger = MemoryEventLogger(Path("trajectory.jsonl"), run_id="r-001")
        logger.log_retrieval("What is Activity?", retrieved_memories)
        logger.log_extraction("t-001", extracted_memories)
        logger.close()
    """

    def __init__(
        self,
        log_path: Path | str,
        run_id: str,
        trajectory_id: Optional[str] = None,
    ):
        """Initialize memory event logger.

        Args:
            log_path: Path to JSONL output file (same as TrajectoryCallback)
            run_id: Run identifier for provenance
            trajectory_id: Optional trajectory identifier
        """
        self.log_path = Path(log_path)
        self.run_id = run_id
        self.trajectory_id = trajectory_id

        # Ensure parent directory exists
        self.log_path.parent.mkdir(parents=True, exist_ok=True)

        # Open log file in append mode (shared with TrajectoryCallback)
        self.log_file = open(self.log_path, "a")

    def _timestamp(self) -> str:
        """Get current timestamp in ISO 8601 format."""
        return datetime.now(timezone.utc).isoformat()

    def _write_event(self, event: dict[str, Any]) -> None:
        """Write event to JSONL log file.

        Args:
            event: Event dictionary to log
        """
        try:
            # Add common fields
            if "timestamp" not in event:
                event["timestamp"] = self._timestamp()
            if "run_id" not in event:
                event["run_id"] = self.run_id
            if self.trajectory_id and "trajectory_id" not in event:
                event["trajectory_id"] = self.trajectory_id

            # Write as JSON line
            json.dump(event, self.log_file, ensure_ascii=False)
            self.log_file.write("\n")
            self.log_file.flush()
        except Exception as e:
            print(f"Warning: Failed to write memory event: {e}")

    def log_retrieval(
        self,
        query: str,
        memories: list["MemoryItem"],
        k: int,
        filters: Optional[dict] = None,
    ) -> None:
        """Log memory retrieval event.

        Args:
            query: Query used for retrieval
            memories: List of retrieved memories
            k: Number of memories requested
            filters: Optional filters applied
        """
        self._write_event({
            "event": "memory_retrieval",
            "query": query,
            "k_requested": k,
            "k_retrieved": len(memories),
            "memory_ids": [m.memory_id for m in memories],
            "memory_titles": [m.title for m in memories],
            "filters": filters,
        })

    def log_judgment(
        self,
        trajectory_id: str,
        judgment: dict[str, Any],
    ) -> None:
        """Log trajectory judgment event.

        Args:
            trajectory_id: Trajectory that was judged
            judgment: Judgment dict (is_success, reason, confidence, missing)
        """
        self._write_event({
            "event": "trajectory_judgment",
            "trajectory_id": trajectory_id,
            "is_success": judgment.get("is_success"),
            "reason": judgment.get("reason"),
            "confidence": judgment.get("confidence"),
            "missing": judgment.get("missing", []),
        })

    def log_extraction(
        self,
        trajectory_id: str,
        memories: list["MemoryItem"],
        source_type: str,
    ) -> None:
        """Log memory extraction event.

        Args:
            trajectory_id: Trajectory memories were extracted from
            memories: List of extracted memories
            source_type: 'success' or 'failure'
        """
        self._write_event({
            "event": "memory_extraction",
            "trajectory_id": trajectory_id,
            "extracted_count": len(memories),
            "source_type": source_type,
            "memory_ids": [m.memory_id for m in memories],
            "memory_titles": [m.title for m in memories],
            "memory_tags": [m.tags for m in memories],
        })

    def log_storage(
        self,
        memory_id: str,
        title: str,
        was_duplicate: bool,
    ) -> None:
        """Log memory storage event.

        Args:
            memory_id: ID of stored memory
            title: Memory title
            was_duplicate: Whether memory already existed (skipped)
        """
        self._write_event({
            "event": "memory_storage",
            "memory_id": memory_id,
            "title": title,
            "was_duplicate": was_duplicate,
        })

    def log_usage_record(
        self,
        trajectory_id: str,
        memory_id: str,
        rank: int,
        score: Optional[float],
    ) -> None:
        """Log memory usage recording.

        Args:
            trajectory_id: Trajectory that used the memory
            memory_id: Memory that was used
            rank: Rank in retrieval (1 = top result)
            score: Optional retrieval score
        """
        self._write_event({
            "event": "memory_usage_record",
            "trajectory_id": trajectory_id,
            "memory_id": memory_id,
            "rank": rank,
            "score": score,
        })

    def log_stats_update(
        self,
        memory_id: str,
        accessed: bool = False,
        success: bool = False,
        failure: bool = False,
    ) -> None:
        """Log memory stats update.

        Args:
            memory_id: Memory whose stats were updated
            accessed: Whether access_count was incremented
            success: Whether success_count was incremented
            failure: Whether failure_count was incremented
        """
        updates = []
        if accessed:
            updates.append("accessed")
        if success:
            updates.append("success")
        if failure:
            updates.append("failure")

        if updates:
            self._write_event({
                "event": "memory_stats_update",
                "memory_id": memory_id,
                "updates": updates,
            })

    def close(self) -> None:
        """Close log file."""
        if hasattr(self, 'log_file') and self.log_file:
            self.log_file.close()

    def __del__(self):
        """Ensure log file is closed on deletion."""
        self.close()
