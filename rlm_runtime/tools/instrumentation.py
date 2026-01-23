"""Tool instrumentation for trajectory logging.

Wraps tool functions to emit callback events for timing and observability.
"""

from __future__ import annotations

import uuid
from typing import Callable, Any
from functools import wraps

import dspy


def instrument_tool(tool_func: Callable, tool_name: str, iteration_counter: dict) -> Callable:
    """Wrap a tool function to emit callback events.

    Args:
        tool_func: Original tool function to wrap
        tool_name: Name of the tool for logging
        iteration_counter: Shared dict with 'value' key for tracking iteration number

    Returns:
        Wrapped function that emits on_tool_start/on_tool_end events
    """

    @wraps(tool_func)
    def instrumented_tool(*args, **kwargs):
        # Get active callbacks from DSPy settings
        callbacks = dspy.settings.get('callbacks', [])

        # Debug: Log that tool was called
        print(f"[TOOL] {tool_name} called, callbacks={len(callbacks) if callbacks else 0}")

        if not callbacks:
            # No callbacks, just run the tool
            return tool_func(*args, **kwargs)

        # Generate unique call ID
        call_id = f"tool-{uuid.uuid4().hex[:8]}"

        # Prepare inputs dict (serialize args/kwargs)
        inputs = {
            'args': args,
            'kwargs': kwargs,
        }

        # Create a mock tool instance for callback API
        # (callbacks expect an 'instance' parameter)
        class ToolInstance:
            __name__ = tool_name

        instance = ToolInstance()

        # Emit on_tool_start
        for callback in callbacks:
            if hasattr(callback, 'on_tool_start'):
                try:
                    # Pass current iteration number
                    callback.on_tool_start(call_id, instance, inputs)
                except Exception as e:
                    print(f"Warning: Callback on_tool_start failed: {e}")

        # Execute tool
        exception = None
        outputs = None
        try:
            outputs = tool_func(*args, **kwargs)
        except Exception as e:
            exception = e

        # Emit on_tool_end
        for callback in callbacks:
            if hasattr(callback, 'on_tool_end'):
                try:
                    callback.on_tool_end(call_id, {'result': outputs}, exception)
                except Exception as e2:
                    print(f"Warning: Callback on_tool_end failed: {e2}")

        # Re-raise exception if tool failed
        if exception:
            raise exception

        return outputs

    return instrumented_tool


def instrument_tools(tools: dict[str, Callable], iteration_counter: dict | None = None) -> dict[str, Callable]:
    """Wrap all tools in a dict with instrumentation.

    Args:
        tools: Dict mapping tool names to tool functions
        iteration_counter: Optional shared counter for iteration tracking

    Returns:
        Dict with same keys, but instrumented tool functions
    """
    if iteration_counter is None:
        iteration_counter = {'value': 0}

    return {
        name: instrument_tool(func, name, iteration_counter)
        for name, func in tools.items()
    }
