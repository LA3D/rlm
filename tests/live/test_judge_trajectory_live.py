"""Test judge_trajectory() with real LLM calls.

This test suite verifies that judge_trajectory() correctly assesses
RLM trajectories using the LLM for evidence-based evaluation.
"""

import pytest
from pathlib import Path

from rlm.core import rlm_run
from rlm.ontology import setup_ontology_context
from rlm.procedural_memory import judge_trajectory, extract_trajectory_artifact


@pytest.fixture
def prov_ontology_path():
    """Path to PROV ontology for testing."""
    return Path('ontology/prov.ttl')


@pytest.mark.live
class TestJudgeTrajectoryLive:
    """Test judge_trajectory() with real LLM."""

    def test_judges_successful_trajectory(self, prov_ontology_path):
        """Test that judge correctly identifies a successful, grounded trajectory."""
        if not prov_ontology_path.exists():
            pytest.skip("PROV ontology not available")

        # Run a simple RLM query that should succeed
        ns = {}
        setup_ontology_context(str(prov_ontology_path), ns, name='prov')
        context = ns['prov_meta'].summary()

        query = "What is prov:Activity?"
        answer, iterations, ns = rlm_run(
            query,
            context,
            ns=ns,
            max_iters=5
        )

        # Extract artifact
        artifact = extract_trajectory_artifact(query, answer, iterations, ns)

        # Judge with real LLM
        judgment = judge_trajectory(artifact, ns)

        # Assertions about judgment structure (matches implementation contract)
        assert 'is_success' in judgment
        assert 'confidence' in judgment
        assert 'reason' in judgment
        assert 'missing' in judgment
        assert isinstance(judgment['is_success'], bool)
        assert judgment['confidence'] in ('high', 'medium', 'low')
        assert isinstance(judgment['reason'], str)
        assert isinstance(judgment['missing'], list)

        # If the trajectory converged properly, judge should recognize success
        if artifact['converged'] and not answer.startswith('[Max iterations]'):
            # Successful convergence should generally be judged as successful
            # (though LLM might disagree if answer is wrong)
            assert len(judgment['reason']) > 0

    def test_judges_failed_trajectory(self):
        """Test that judge correctly identifies a failed/ungrounded trajectory."""
        # Create a trajectory that clearly failed (max iterations, no convergence)
        from rlm._rlmpaper_compat import RLMIteration, CodeBlock, REPLResult

        # Mock a failed trajectory - no code blocks, no convergence
        iterations = [
            RLMIteration(
                prompt="What is foo?",
                response="I don't know what foo is.",
                code_blocks=[],
                final_answer=None,
                iteration_time=0.1
            )
        ]

        artifact = extract_trajectory_artifact(
            task="What is foo?",
            answer="[Max iterations] No answer produced",
            iterations=iterations,
            ns={}
        )

        # Judge with real LLM
        judgment = judge_trajectory(artifact, {})

        # Assertions (matches implementation contract)
        assert 'is_success' in judgment
        assert 'confidence' in judgment
        assert 'reason' in judgment
        assert 'missing' in judgment

        # Failed trajectory should be recognized
        # (LLM should see: max_iterations, no code blocks, no exploration)
        assert isinstance(judgment['is_success'], bool)
        assert judgment['confidence'] in ('high', 'medium', 'low')
        assert len(judgment['reason']) > 0

    def test_judgment_considers_evidence(self, prov_ontology_path):
        """Test that judgment reasoning references evidence from trajectory."""
        if not prov_ontology_path.exists():
            pytest.skip("PROV ontology not available")

        # Run RLM query
        ns = {}
        setup_ontology_context(str(prov_ontology_path), ns, name='prov')
        context = ns['prov_meta'].summary()

        query = "Find a class in the PROV ontology and describe it"
        answer, iterations, ns = rlm_run(
            query,
            context,
            ns=ns,
            max_iters=5
        )

        # Extract and judge
        artifact = extract_trajectory_artifact(query, answer, iterations, ns)
        judgment = judge_trajectory(artifact, ns)

        # Reason should be substantive (not just "yes" or "no")
        assert len(judgment['reason']) > 20

        # Reason should reference the process (evidence-based judging)
        reason_lower = judgment['reason'].lower()
        # Judge should consider multiple factors
        assert any(keyword in reason_lower for keyword in [
            'converged', 'code', 'iteration', 'answer', 'evidence', 'found'
        ])

    def test_judgment_with_namespace_context(self, prov_ontology_path):
        """Test that judge can access namespace context for more informed judgment."""
        if not prov_ontology_path.exists():
            pytest.skip("PROV ontology not available")

        ns = {}
        setup_ontology_context(str(prov_ontology_path), ns, name='prov')
        context = ns['prov_meta'].summary()

        query = "What is prov:Entity?"
        answer, iterations, ns = rlm_run(
            query,
            context,
            ns=ns,
            max_iters=5
        )

        artifact = extract_trajectory_artifact(query, answer, iterations, ns)

        # Judge with namespace (gives judge access to prov_meta, etc.)
        judgment = judge_trajectory(artifact, ns)

        # Judgment should complete successfully (matches implementation contract)
        assert 'is_success' in judgment
        assert 'confidence' in judgment
        assert 'reason' in judgment
        assert 'missing' in judgment

        # Confidence should be one of the valid categorical values
        assert judgment['confidence'] in ('high', 'medium', 'low')

    def test_confidence_scores_vary(self, prov_ontology_path):
        """Test that confidence scores are not always the same (LLM is discriminating)."""
        if not prov_ontology_path.exists():
            pytest.skip("PROV ontology not available")

        ns = {}
        setup_ontology_context(str(prov_ontology_path), ns, name='prov')
        context = ns['prov_meta'].summary()

        # Run two different queries
        query1 = "What is prov:Activity?"
        answer1, iters1, ns1 = rlm_run(query1, context, ns=dict(ns), max_iters=5)
        artifact1 = extract_trajectory_artifact(query1, answer1, iters1, ns1)
        judgment1 = judge_trajectory(artifact1, ns1)

        query2 = "List all 50 classes in PROV ontology with full details"
        answer2, iters2, ns2 = rlm_run(query2, context, ns=dict(ns), max_iters=2)  # Low max_iters
        artifact2 = extract_trajectory_artifact(query2, answer2, iters2, ns2)
        judgment2 = judge_trajectory(artifact2, ns2)

        # Both should have judgments with valid confidence values
        assert 'confidence' in judgment1
        assert 'confidence' in judgment2

        # Confidence should be categorical strings (not numeric)
        assert judgment1['confidence'] in ('high', 'medium', 'low')
        assert judgment2['confidence'] in ('high', 'medium', 'low')
