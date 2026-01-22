"""Tests for Phase 4 eval harness features."""

import pytest
import json
from pathlib import Path
from evals.graders.sparql_structural import SparqlStructuralGrader
from evals.graders.affordance_utilization import AffordanceUtilizationGrader
from evals.ablation_config import AblationConfig
from evals.analysis.summary import generate_summary


class TestSparqlStructuralGrader:
    """Tests for SPARQL structural grader (Rung 2)."""

    def test_requires_graph_passes(self):
        """Test that GRAPH requirement passes when present."""
        grader = SparqlStructuralGrader(requires_graph=True)

        transcript = [{
            'iteration': 1,
            'code_blocks': [{
                'code': '''
                SELECT ?s ?p ?o WHERE {
                    GRAPH <http://example.org/graph> {
                        ?s ?p ?o
                    }
                }
                ''',
                'result': {'stdout': 'Query executed', 'stderr': ''}
            }]
        }]

        result = grader.grade(transcript, "answer", {})
        assert result.passed, f"Expected pass but got: {result.reason}"
        assert result.details['checks']['has_graph']

    def test_requires_graph_fails(self):
        """Test that GRAPH requirement fails when missing."""
        grader = SparqlStructuralGrader(requires_graph=True)

        transcript = [{
            'iteration': 1,
            'code_blocks': [{
                'code': 'SELECT ?s ?p ?o WHERE { ?s ?p ?o }',
                'result': {'stdout': 'Query executed', 'stderr': ''}
            }]
        }]

        result = grader.grade(transcript, "answer", {})
        assert not result.passed
        assert "Missing required GRAPH clause" in result.reason

    def test_requires_service(self):
        """Test SERVICE requirement checking."""
        grader = SparqlStructuralGrader(
            requires_service=["sparql.rhea-db.org"]
        )

        transcript = [{
            'iteration': 1,
            'code_blocks': [{
                'code': '''
                SELECT ?s ?p ?o WHERE {
                    SERVICE <https://sparql.rhea-db.org/sparql> {
                        ?s ?p ?o
                    }
                }
                ''',
                'result': {'stdout': 'Query executed', 'stderr': ''}
            }]
        }]

        result = grader.grade(transcript, "answer", {})
        assert result.passed, f"Expected pass but got: {result.reason}"

    def test_forbids_closure(self):
        """Test that forbidden property paths are detected."""
        grader = SparqlStructuralGrader(
            forbids_closure=["rdfs:subClassOf+"]
        )

        transcript = [{
            'iteration': 1,
            'code_blocks': [{
                'code': '''
                SELECT ?subclass WHERE {
                    ?subclass rdfs:subClassOf+ <http://example.org/BaseClass>
                }
                ''',
                'result': {'stdout': 'Query executed', 'stderr': ''}
            }]
        }]

        result = grader.grade(transcript, "answer", {})
        assert not result.passed
        assert "forbidden patterns" in result.reason

    def test_required_patterns(self):
        """Test that required patterns are detected."""
        grader = SparqlStructuralGrader(
            required_patterns=["up:reviewed true", "FILTER"]
        )

        transcript = [{
            'iteration': 1,
            'code_blocks': [{
                'code': '''
                SELECT ?protein WHERE {
                    ?protein a up:Protein ;
                             up:reviewed true .
                    FILTER (?score > 0.9)
                }
                ''',
                'result': {'stdout': 'Query executed', 'stderr': ''}
            }]
        }]

        result = grader.grade(transcript, "answer", {})
        assert result.passed, f"Expected pass but got: {result.reason}"

    def test_no_query_found(self):
        """Test handling when no SPARQL query is found."""
        grader = SparqlStructuralGrader(requires_graph=True)

        transcript = [{
            'iteration': 1,
            'code_blocks': [{
                'code': 'print("Hello world")',
                'result': {'stdout': 'Hello world', 'stderr': ''}
            }]
        }]

        result = grader.grade(transcript, "answer", {})
        assert not result.passed
        assert "No SPARQL query found" in result.reason


class TestAffordanceUtilizationGrader:
    """Tests for affordance utilization grader (Rung 7)."""

    def test_high_utilization_passes(self):
        """Test that high utilization rate passes."""
        grader = AffordanceUtilizationGrader(
            min_utilization_rate=0.3,
            max_hallucination_rate=0.1,
            require_evidence_grounding=False  # Disable for this test
        )

        # Mock task with simple ontology URIs
        task = {
            'context': {
                'ontologies': []  # Empty for now, will be mocked
            }
        }

        transcript = [{
            'iteration': 1,
            'code_blocks': [{
                'code': '''
                SELECT ?label WHERE {
                    <http://www.w3.org/2000/01/rdf-schema#Class>
                        <http://www.w3.org/2000/01/rdf-schema#label> ?label
                }
                ''',
                'result': {'stdout': 'Query executed', 'stderr': ''}
            }]
        }]

        # Mock the provided URIs by patching the grader
        grader._get_provided_uris = lambda task: {
            'http://www.w3.org/2000/01/rdf-schema#Class',
            'http://www.w3.org/2000/01/rdf-schema#label',
            'http://www.w3.org/2000/01/rdf-schema#comment'
        }

        result = grader.grade(transcript, "answer", task)
        # Should pass because 2/3 URIs used (66% > 30%)
        assert result.passed, f"Expected pass but got: {result.reason}"
        assert result.details['utilization_rate'] > 0.3

    def test_from_config(self):
        """Test grader creation from config."""
        config = {
            'min_utilization_rate': 0.5,
            'max_hallucination_rate': 0.2
        }
        grader = SparqlStructuralGrader.from_config(config)
        assert grader is not None


class TestAblationConfig:
    """Tests for ablation configuration system (Rung 4)."""

    def test_baseline_preset(self):
        """Test baseline preset has minimal features."""
        config = AblationConfig.from_preset('baseline')
        assert config.name == 'baseline'
        assert config.basic_stats is True
        assert config.labeling_predicates is False
        assert config.enable_memory is False

    def test_full_preset(self):
        """Test full preset has all features."""
        config = AblationConfig.from_preset('full')
        assert config.name == 'full'
        assert config.basic_stats is True
        assert config.labeling_predicates is True
        assert config.hierarchy is True
        assert config.sparql_templates is True
        assert config.enable_memory is False  # Not memory yet

    def test_full_with_memory_preset(self):
        """Test full_with_memory preset enables memory."""
        config = AblationConfig.from_preset('full_with_memory')
        assert config.enable_memory is True
        assert config.memory_retrieval_k == 3

    def test_structural_preset(self):
        """Test structural preset has hierarchy and domain/range."""
        config = AblationConfig.from_preset('structural')
        assert config.hierarchy is True
        assert config.domain_range is True
        assert config.property_characteristics is False  # Not semantic yet

    def test_invalid_preset_raises(self):
        """Test that invalid preset raises ValueError."""
        with pytest.raises(ValueError, match="Unknown preset"):
            AblationConfig.from_preset('nonexistent')

    def test_get_enabled_features(self):
        """Test getting list of enabled features."""
        config = AblationConfig.from_preset('minimal')
        features = config.get_enabled_features()
        assert 'basic_stats' in features
        assert 'labeling_predicates' in features
        assert len(features) == 2

    def test_to_dict(self):
        """Test serialization to dict."""
        config = AblationConfig.from_preset('baseline')
        d = config.to_dict()
        assert d['name'] == 'baseline'
        assert 'features' in d
        assert 'memory' in d


class TestAnalysisTools:
    """Tests for analysis tools (Rung 8)."""

    def test_generate_summary_with_sample_data(self, tmp_path):
        """Test summary generation with sample result files."""
        # Create sample result files
        results_dir = tmp_path / "results"
        results_dir.mkdir()

        # Sample result 1: passing task
        result1 = {
            'task_id': 'entity_discovery_test_001',
            'task_query': 'Find entities of type X',
            'total_trials': 3,
            'passed_trials': 3,
            'pass_at_k': 1.0,
            'avg_iterations': 5.0,
            'avg_groundedness': 0.9
        }
        with open(results_dir / 'result1.json', 'w') as f:
            json.dump(result1, f)

        # Sample result 2: failing task
        result2 = {
            'task_id': 'hierarchy_test_001',
            'task_query': 'Find hierarchy',
            'total_trials': 3,
            'passed_trials': 1,
            'pass_at_k': 0.33,
            'avg_iterations': 12.0,
            'avg_groundedness': 0.5
        }
        with open(results_dir / 'result2.json', 'w') as f:
            json.dump(result2, f)

        # Generate summary
        summary = generate_summary(str(results_dir))

        assert 'error' not in summary
        assert summary['total_tasks'] == 2
        assert summary['total_trials'] == 6
        assert summary['total_passed'] == 4
        assert summary['overall_pass_rate'] == pytest.approx(4/6, rel=1e-2)

        # Check category aggregation
        assert 'entity' in summary['by_category'] or 'entity_discovery' in str(summary['by_category'])

        # Check recommendations exist
        assert 'recommendations' in summary
        assert len(summary['recommendations']) > 0

    def test_generate_summary_empty_dir(self, tmp_path):
        """Test summary generation with empty directory."""
        results_dir = tmp_path / "empty"
        results_dir.mkdir()

        summary = generate_summary(str(results_dir))
        assert 'error' in summary
        assert 'No result files found' in summary['error']

    def test_generate_summary_nonexistent_dir(self):
        """Test summary generation with nonexistent directory."""
        summary = generate_summary('/nonexistent/path')
        assert 'error' in summary
        assert 'not found' in summary['error']


# Mark tests that require rdflib (optional dependency)
class TestIntegration:
    """Integration tests for complete flows."""

    def test_cli_help_commands(self):
        """Test that CLI commands are registered."""
        from evals.cli import main
        import sys

        # Test that commands exist by checking the parser
        # This doesn't execute commands, just validates structure
        original_argv = sys.argv
        try:
            sys.argv = ['evals.cli', '--help']
            try:
                main()
            except SystemExit:
                pass  # --help exits, that's expected
        finally:
            sys.argv = original_argv


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
