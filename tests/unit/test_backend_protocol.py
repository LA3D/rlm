"""Tests for RLM backend protocol.

Tests the backend abstraction interface.
"""

import pytest
from rlm_runtime.engine import RLMBackend, RLMResult, is_rlm_backend


class TestRLMResult:
    """Test RLMResult dataclass."""

    def test_result_creation(self):
        """RLMResult can be created with required fields."""
        result = RLMResult(
            answer="Test answer",
            trajectory=[{"step": 1}],
            iteration_count=1,
            converged=True,
            metadata={"backend": "test"},
        )

        assert result.answer == "Test answer"
        assert len(result.trajectory) == 1
        assert result.iteration_count == 1
        assert result.converged is True
        assert result.metadata["backend"] == "test"

    def test_result_defaults(self):
        """RLMResult handles None defaults."""
        result = RLMResult(
            answer="Test",
            trajectory=None,
            iteration_count=0,
            converged=True,
            metadata=None,
        )

        assert result.trajectory == []
        assert result.metadata == {}


class TestRLMBackendProtocol:
    """Test RLMBackend protocol."""

    def test_protocol_structure(self):
        """RLMBackend protocol has required methods."""
        assert hasattr(RLMBackend, "run")

    def test_valid_backend_implementation(self):
        """Valid implementation is recognized as RLMBackend."""

        class ValidBackend:
            def run(
                self,
                query: str,
                context: str,
                *,
                max_iterations: int = 8,
                max_llm_calls: int = 16,
                verbose: bool = False,
                **kwargs
            ) -> RLMResult:
                return RLMResult(
                    answer="test",
                    trajectory=[],
                    iteration_count=0,
                    converged=True,
                    metadata={},
                )

        backend = ValidBackend()
        assert is_rlm_backend(backend)
        assert isinstance(backend, RLMBackend)

    def test_invalid_backend_not_recognized(self):
        """Invalid implementation is not recognized as RLMBackend."""

        class InvalidBackend:
            def execute(self, query: str):  # Wrong method name
                pass

        backend = InvalidBackend()
        assert not is_rlm_backend(backend)

    def test_backend_without_methods_not_recognized(self):
        """Object without run method is not recognized."""

        class NotABackend:
            pass

        obj = NotABackend()
        assert not is_rlm_backend(obj)

    def test_backend_execution_works(self):
        """Backend implementation can execute queries."""

        class TestBackend:
            def run(
                self,
                query: str,
                context: str,
                *,
                max_iterations: int = 8,
                max_llm_calls: int = 16,
                verbose: bool = False,
                **kwargs
            ) -> RLMResult:
                return RLMResult(
                    answer=f"Answer to: {query}",
                    trajectory=[{"query": query, "context": context}],
                    iteration_count=1,
                    converged=True,
                    metadata={"max_iters": max_iterations},
                )

        backend = TestBackend()
        result = backend.run(
            query="What is X?",
            context="Context about X",
            max_iterations=5,
        )

        assert isinstance(result, RLMResult)
        assert "What is X?" in result.answer
        assert result.iteration_count == 1
        assert result.metadata["max_iters"] == 5
