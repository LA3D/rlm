"""Prompt leakage instrumentation.

Tracks whether context leaks into iterative history by measuring:
- stdout_chars: Total characters printed to stdout
- large_returns: Number of tool returns > 1000 chars
- subcalls: Number of llm_query calls made
- vars_n: Number of variables in REPL state
"""

from dataclasses import dataclass, field
from functools import wraps
from typing import Callable

@dataclass
class Metrics:
    "Tracks prompt leakage during RLM execution."
    stdout_chars: int = 0
    large_returns: int = 0   # returns > 1000 chars
    subcalls: int = 0
    vars_n: int = 0

@dataclass
class Instrumented:
    "Wraps tools to capture leakage `metrics` and optionally log tool calls."
    tools: dict[str, Callable]
    metrics: Metrics = field(default_factory=Metrics)
    log_callback: Callable[[str, dict], None] = None  # Optional callback for tool logging

    def wrap(self) -> dict[str, Callable]:
        "Return wrapped tools that track `metrics` and log calls."
        wrapped = {}
        for name, fn in self.tools.items():
            def make_wrapper(tool_name, f):
                @wraps(f)  # Preserve original function signature for DSPy
                def wrapper(*args, **kwargs):
                    # Log tool call if callback provided
                    if self.log_callback:
                        self.log_callback('tool_call', {
                            'tool': tool_name,
                            'args_type': type(args).__name__,
                            'kwargs_keys': list(kwargs.keys()) if isinstance(kwargs, dict) else []
                        })

                    # Execute tool with exception handling
                    try:
                        res = f(*args, **kwargs)
                        error = None
                    except Exception as e:
                        res = {'error': str(e), 'exception_type': type(e).__name__}
                        error = str(e)

                    # Track large returns
                    res_len = len(str(res))
                    if res_len > 1000:
                        self.metrics.large_returns += 1

                    # Log tool result if callback provided (always, even on error)
                    if self.log_callback:
                        result_data = {
                            'tool': tool_name,
                            'result_type': type(res).__name__,
                            'result_size': res_len,
                            'result_preview': str(res)[:200]
                        }
                        if error:
                            result_data['error'] = error
                        self.log_callback('tool_result', result_data)

                    return res
                return wrapper
            wrapped[name] = make_wrapper(name, fn)
        return wrapped
