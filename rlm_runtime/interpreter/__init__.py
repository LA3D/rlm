"""NamespaceCodeInterpreter for bounded code execution.

Executes Python code in a persistent namespace with tool injection and SUBMIT protocol.
"""

from .namespace_interpreter import NamespaceCodeInterpreter

__all__ = ["NamespaceCodeInterpreter"]
