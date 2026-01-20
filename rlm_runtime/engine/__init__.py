"""RLM execution engine with backend abstraction.

Provides DSPy RLM and claudette-backed implementations with a common interface.
"""

from .backend import RLMBackend, RLMResult, is_rlm_backend
from .claudette_backend import ClaudetteBackend
from .dspy_rlm import DSPyRLMResult, run_dspy_rlm

__all__ = [
    "RLMBackend",
    "RLMResult",
    "is_rlm_backend",
    "ClaudetteBackend",
    "DSPyRLMResult",
    "run_dspy_rlm",
]
