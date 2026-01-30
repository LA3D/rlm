"""Prompt leakage instrumentation.

Tracks whether context leaks into iterative history by measuring:
- stdout_chars: Total characters printed to stdout
- large_returns: Number of tool returns > 1000 chars
- subcalls: Number of llm_query calls made
- vars_n: Number of variables in REPL state
"""

from dataclasses import dataclass, field
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
    "Wraps tools to capture leakage `metrics`."
    tools: dict[str, Callable]
    metrics: Metrics = field(default_factory=Metrics)

    def wrap(self) -> dict[str, Callable]:
        "Return wrapped tools that track `metrics`."
        wrapped = {}
        for name, fn in self.tools.items():
            def make_wrapper(f):
                def wrapper(*args, **kwargs):
                    res = f(*args, **kwargs)
                    # Track large returns
                    if isinstance(res, str) and len(res) > 1000:
                        self.metrics.large_returns += 1
                    return res
                wrapper.__name__ = f.__name__
                return wrapper
            wrapped[name] = make_wrapper(fn)
        return wrapped
