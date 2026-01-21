"""DSPy callback for trajectory logging to JSONL.

Captures tool calls, LLM invocations, and module execution for debugging
and analysis.
"""

from __future__ import annotations

import json
from pathlib import Path
from datetime import datetime, timezone
from typing import Any, Optional

from dspy.utils.callback import BaseCallback


class TrajectoryCallback(BaseCallback):
    """DSPy callback that logs execution trajectory to JSONL file.

    Captures:
    - Tool invocations and results
    - LLM calls and responses
    - Module start/end events
    - Adapter formatting/parsing

    Each event is written as a JSON line with:
    - event: Event type (tool_call, tool_result, lm_call, etc.)
    - timestamp: ISO 8601 timestamp
    - call_id: Unique call identifier
    - iteration: Iteration counter (for tools)
    - ... event-specific fields

    Example:
        callback = TrajectoryCallback(Path("trajectory.jsonl"), run_id="r-001")
        dspy.configure(callbacks=[callback])
        # Run your DSPy program
        # trajectory.jsonl now contains full execution log
    """

    def __init__(
        self,
        log_path: Path | str,
        run_id: str,
        trajectory_id: Optional[str] = None,
        log_llm_calls: bool = True,
        log_adapter_events: bool = False,  # Usually too verbose
    ):
        """Initialize trajectory logger.

        Args:
            log_path: Path to JSONL output file
            run_id: Run identifier for provenance
            trajectory_id: Optional trajectory identifier
            log_llm_calls: Whether to log LLM calls (default True)
            log_adapter_events: Whether to log adapter format/parse (default False, very verbose)
        """
        self.log_path = Path(log_path)
        self.run_id = run_id
        self.trajectory_id = trajectory_id
        self.log_llm_calls = log_llm_calls
        self.log_adapter_events = log_adapter_events

        # State tracking
        self.tool_iteration = 0
        self.lm_call_count = 0
        self.module_depth = 0

        # Ensure parent directory exists
        self.log_path.parent.mkdir(parents=True, exist_ok=True)

        # Open log file (append mode)
        self.log_file = open(self.log_path, "a")

        # Write session start marker
        self._write_event({
            "event": "session_start",
            "run_id": self.run_id,
            "trajectory_id": self.trajectory_id,
            "timestamp": self._timestamp()
        })

    def _timestamp(self) -> str:
        """Get current timestamp in ISO 8601 format."""
        return datetime.now(timezone.utc).isoformat()

    def _write_event(self, event: dict[str, Any]) -> None:
        """Write event to JSONL log file.

        Args:
            event: Event dictionary to log
        """
        try:
            # Add common fields if not present
            if "timestamp" not in event:
                event["timestamp"] = self._timestamp()
            if "run_id" not in event:
                event["run_id"] = self.run_id
            if self.trajectory_id and "trajectory_id" not in event:
                event["trajectory_id"] = self.trajectory_id

            # Write as JSON line
            json.dump(event, self.log_file, ensure_ascii=False)
            self.log_file.write("\n")
            self.log_file.flush()  # Ensure written immediately
        except Exception as e:
            # Don't crash the program due to logging errors
            print(f"Warning: Failed to write log event: {e}")

    def _serialize_value(self, value: Any, max_length: int = 500) -> Any:
        """Serialize value for logging, truncating if too long.

        Args:
            value: Value to serialize
            max_length: Maximum string length before truncation

        Returns:
            Serializable value (truncated if needed)
        """
        if value is None:
            return None

        # Convert to string for complex objects
        if not isinstance(value, (str, int, float, bool, list, dict)):
            value = str(value)

        # Truncate long strings
        if isinstance(value, str) and len(value) > max_length:
            return value[:max_length] + f"... (truncated, {len(value)} total chars)"

        # Recursively serialize dicts
        if isinstance(value, dict):
            return {k: self._serialize_value(v, max_length) for k, v in value.items()}

        # Recursively serialize lists (limit to first N items)
        if isinstance(value, list):
            if len(value) > 10:
                return [self._serialize_value(item, max_length) for item in value[:10]] + \
                       [f"... ({len(value) - 10} more items)"]
            return [self._serialize_value(item, max_length) for item in value]

        return value

    # === Tool Events ===

    def on_tool_start(self, call_id: str, instance: Any, inputs: dict[str, Any]) -> None:
        """Log tool invocation start.

        Args:
            call_id: Unique call identifier
            instance: Tool instance
            inputs: Tool input arguments
        """
        self._write_event({
            "event": "tool_call",
            "call_id": call_id,
            "iteration": self.tool_iteration,
            "tool_name": getattr(instance, "__name__", str(type(instance))),
            "inputs": self._serialize_value(inputs),
        })

    def on_tool_end(
        self,
        call_id: str,
        outputs: dict[str, Any] | None,
        exception: Exception | None = None
    ) -> None:
        """Log tool invocation end.

        Args:
            call_id: Unique call identifier
            outputs: Tool output
            exception: Exception if tool raised one
        """
        self._write_event({
            "event": "tool_result",
            "call_id": call_id,
            "iteration": self.tool_iteration,
            "outputs": self._serialize_value(outputs) if outputs else None,
            "exception": str(exception) if exception else None,
            "success": exception is None,
        })

        self.tool_iteration += 1

    # === LLM Events ===

    def on_lm_start(self, call_id: str, instance: Any, inputs: dict[str, Any]) -> None:
        """Log LLM call start.

        Args:
            call_id: Unique call identifier
            instance: LM instance
            inputs: LLM input (prompt)
        """
        if not self.log_llm_calls:
            return

        self._write_event({
            "event": "llm_call",
            "call_id": call_id,
            "llm_call_number": self.lm_call_count,
            "model": getattr(instance, "model", "unknown"),
            "inputs": self._serialize_value(inputs, max_length=1000),
        })

    def on_lm_end(
        self,
        call_id: str,
        outputs: dict[str, Any] | None,
        exception: Exception | None = None
    ) -> None:
        """Log LLM call end.

        Args:
            call_id: Unique call identifier
            outputs: LLM response
            exception: Exception if LLM call failed
        """
        if not self.log_llm_calls:
            return

        self._write_event({
            "event": "llm_response",
            "call_id": call_id,
            "llm_call_number": self.lm_call_count,
            "outputs": self._serialize_value(outputs, max_length=1000) if outputs else None,
            "exception": str(exception) if exception else None,
            "success": exception is None,
        })

        self.lm_call_count += 1

    # === Module Events ===

    def on_module_start(self, call_id: str, instance: Any, inputs: dict[str, Any]) -> None:
        """Log module execution start.

        Args:
            call_id: Unique call identifier
            instance: Module instance
            inputs: Module inputs
        """
        self._write_event({
            "event": "module_start",
            "call_id": call_id,
            "module_name": type(instance).__name__,
            "depth": self.module_depth,
            "inputs": self._serialize_value(inputs, max_length=500),
        })

        self.module_depth += 1

    def on_module_end(
        self,
        call_id: str,
        outputs: Any | None,
        exception: Exception | None = None
    ) -> None:
        """Log module execution end.

        Args:
            call_id: Unique call identifier
            outputs: Module outputs
            exception: Exception if module failed
        """
        self.module_depth -= 1

        self._write_event({
            "event": "module_end",
            "call_id": call_id,
            "depth": self.module_depth,
            "outputs": self._serialize_value(outputs, max_length=1000) if outputs else None,
            "exception": str(exception) if exception else None,
            "success": exception is None,
        })

    # === Adapter Events (usually disabled) ===

    def on_adapter_format_start(
        self,
        call_id: str,
        instance: Any,
        inputs: dict[str, Any]
    ) -> None:
        """Log adapter format start."""
        if self.log_adapter_events:
            self._write_event({
                "event": "adapter_format_start",
                "call_id": call_id,
                "inputs": self._serialize_value(inputs, max_length=300),
            })

    def on_adapter_format_end(
        self,
        call_id: str,
        outputs: dict[str, Any] | None,
        exception: Exception | None = None
    ) -> None:
        """Log adapter format end."""
        if self.log_adapter_events:
            self._write_event({
                "event": "adapter_format_end",
                "call_id": call_id,
                "outputs": self._serialize_value(outputs, max_length=300) if outputs else None,
                "exception": str(exception) if exception else None,
            })

    def on_adapter_parse_start(
        self,
        call_id: str,
        instance: Any,
        inputs: dict[str, Any]
    ) -> None:
        """Log adapter parse start."""
        if self.log_adapter_events:
            self._write_event({
                "event": "adapter_parse_start",
                "call_id": call_id,
                "inputs": self._serialize_value(inputs, max_length=300),
            })

    def on_adapter_parse_end(
        self,
        call_id: str,
        outputs: dict[str, Any] | None,
        exception: Exception | None = None
    ) -> None:
        """Log adapter parse end."""
        if self.log_adapter_events:
            self._write_event({
                "event": "adapter_parse_end",
                "call_id": call_id,
                "outputs": self._serialize_value(outputs, max_length=300) if outputs else None,
                "exception": str(exception) if exception else None,
            })

    # === Cleanup ===

    def close(self) -> None:
        """Close log file and write session end marker."""
        if hasattr(self, 'log_file') and self.log_file:
            self._write_event({
                "event": "session_end",
                "tool_calls": self.tool_iteration,
                "llm_calls": self.lm_call_count,
            })
            self.log_file.close()

    def __del__(self):
        """Ensure log file is closed on deletion."""
        self.close()
