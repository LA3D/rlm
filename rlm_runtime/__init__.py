"""RLM Runtime - Stable runtime package for DSPy-backed RLM execution.

This package provides a stable runtime surface for RLM query construction,
separate from the research-oriented nbdev notebooks.

Architecture:
- engine/: DSPy RLM execution engine with backend abstraction
- interpreter/: NamespaceCodeInterpreter for bounded code execution
- memory/: SQLite-backed ReasoningBank for procedural memory
- tools/: Bounded tool surface wrappers for ontology exploration
"""

__version__ = "0.1.0"
