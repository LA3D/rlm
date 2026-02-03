"""Unit tests for trajectory diversity metrics.

Tests the diversity.py module with known inputs to verify:
- Vendi Score computation (identical vs different inputs)
- Jaccard similarity edge cases
- Forking point detection
- Effective sample size computation
"""

import pytest
import sys
sys.path.insert(0, '/Users/cvardema/dev/git/LA3D/rlm')

from experiments.reasoningbank.metrics.diversity import (
    # Level 1 metrics
    extract_query_pattern,
    count_unique_patterns,
    answer_jaccard,

    # Level 2 metrics
    trajectory_jaccard,
    trajectory_edit_distance,
    find_divergence_point,
    mean_pairwise_jaccard,
    mean_edit_distance,
    serialize_trajectory,

    # Level 3 metrics
    iteration_diversity,
    identify_forking_points,
    divergence_statistics,

    # Level 4 metrics
    effective_trajectory_count,

    # Report
    compute_diversity_report,
    DiversityReport,

    # Utilities
    load_trajectory,
    _levenshtein_distance,
)


# =============================================================================
# Test Data Fixtures
# =============================================================================

@pytest.fixture
def identical_trajectories():
    """Five identical trajectories."""
    step = {
        'event_type': 'iteration',
        'data': {
            'code': 'x = sparql_query("SELECT ?s WHERE { ?s a ?o }")',
            'reasoning': 'Exploring the ontology',
            'output': 'Found 10 results'
        }
    }
    return [[step, step] for _ in range(5)]


@pytest.fixture
def diverse_trajectories():
    """Five completely different trajectories."""
    return [
        [{'event_type': 'iteration', 'data': {'code': 'query_classes()', 'reasoning': 'A'}}],
        [{'event_type': 'iteration', 'data': {'code': 'query_properties()', 'reasoning': 'B'}}],
        [{'event_type': 'iteration', 'data': {'code': 'get_schema()', 'reasoning': 'C'}}],
        [{'event_type': 'iteration', 'data': {'code': 'find_entities()', 'reasoning': 'D'}}],
        [{'event_type': 'iteration', 'data': {'code': 'explore_graph()', 'reasoning': 'E'}}],
    ]


@pytest.fixture
def partial_overlap_trajectories():
    """Trajectories that start the same but diverge."""
    common_start = {
        'event_type': 'iteration',
        'data': {'code': 'get_ontology_info()', 'reasoning': 'Starting exploration'}
    }
    return [
        [common_start, {'event_type': 'iteration', 'data': {'code': 'path_A()', 'reasoning': 'X'}}],
        [common_start, {'event_type': 'iteration', 'data': {'code': 'path_B()', 'reasoning': 'Y'}}],
        [common_start, {'event_type': 'iteration', 'data': {'code': 'path_C()', 'reasoning': 'Z'}}],
    ]


@pytest.fixture
def sample_queries():
    """Sample SPARQL queries with varying similarity."""
    return [
        "SELECT ?protein WHERE { ?protein a up:Protein }",
        "SELECT ?protein WHERE { ?protein a up:Protein } LIMIT 10",
        "SELECT DISTINCT ?enzyme WHERE { ?enzyme a up:Enzyme }",
        "ASK { ?x up:organism ?human }",
        "CONSTRUCT { ?s ?p ?o } WHERE { ?s a up:Protein ; ?p ?o }",
    ]


# =============================================================================
# Level 1: Outcome Diversity Tests
# =============================================================================

class TestQueryPatterns:
    """Tests for SPARQL query pattern extraction."""

    def test_extract_select_pattern(self):
        query = "SELECT ?x WHERE { ?x a up:Protein }"
        pattern = extract_query_pattern(query)
        assert 'SELECT' in pattern

    def test_extract_ask_pattern(self):
        query = "ASK { ?x a up:Protein }"
        pattern = extract_query_pattern(query)
        assert 'ASK' in pattern

    def test_extract_filter_pattern(self):
        query = "SELECT ?x WHERE { ?x a up:Protein FILTER(?x != <foo>) }"
        pattern = extract_query_pattern(query)
        assert 'FILTER' in pattern

    def test_extract_optional_pattern(self):
        query = "SELECT ?x ?y WHERE { ?x a up:Protein OPTIONAL { ?x rdfs:label ?y } }"
        pattern = extract_query_pattern(query)
        assert 'OPTIONAL' in pattern

    def test_empty_query_pattern(self):
        pattern = extract_query_pattern("")
        assert pattern == "empty"

    def test_count_unique_patterns(self, sample_queries):
        patterns = count_unique_patterns(sample_queries)
        # Should have different patterns for SELECT, ASK, CONSTRUCT
        assert len(patterns) >= 3


class TestAnswerJaccard:
    """Tests for answer set Jaccard similarity."""

    def test_identical_answers(self):
        answers = [{1, 2, 3}, {1, 2, 3}, {1, 2, 3}]
        assert answer_jaccard(answers) == 1.0

    def test_disjoint_answers(self):
        answers = [{1, 2}, {3, 4}, {5, 6}]
        assert answer_jaccard(answers) == 0.0

    def test_partial_overlap(self):
        answers = [{1, 2, 3}, {2, 3, 4}]
        # Intersection = {2, 3} = 2, Union = {1, 2, 3, 4} = 4
        assert answer_jaccard(answers) == 0.5

    def test_single_answer(self):
        answers = [{1, 2, 3}]
        assert answer_jaccard(answers) == 1.0

    def test_empty_answers(self):
        answers = [set(), set()]
        assert answer_jaccard(answers) == 1.0  # Both empty = identical


# =============================================================================
# Level 2: Trajectory Diversity Tests
# =============================================================================

class TestTrajectoryJaccard:
    """Tests for trajectory Jaccard similarity."""

    def test_identical_trajectories(self, identical_trajectories):
        t1, t2 = identical_trajectories[0], identical_trajectories[1]
        assert trajectory_jaccard(t1, t2) == 1.0

    def test_different_tools(self):
        t1 = [{'tool': 'query_classes'}, {'tool': 'get_schema'}]
        t2 = [{'tool': 'explore_graph'}, {'tool': 'find_entities'}]
        assert trajectory_jaccard(t1, t2) == 0.0

    def test_partial_tool_overlap(self):
        t1 = [{'tool': 'query_classes'}, {'tool': 'get_schema'}]
        t2 = [{'tool': 'query_classes'}, {'tool': 'explore_graph'}]
        # Intersection = {query_classes} = 1, Union = 3
        assert trajectory_jaccard(t1, t2) == pytest.approx(1/3, rel=0.01)

    def test_empty_trajectories(self):
        t1, t2 = [], []
        assert trajectory_jaccard(t1, t2) == 1.0


class TestTrajectoryEditDistance:
    """Tests for trajectory edit distance."""

    def test_identical_sequences(self):
        t1 = [{'tool': 'A'}, {'tool': 'B'}, {'tool': 'C'}]
        t2 = [{'tool': 'A'}, {'tool': 'B'}, {'tool': 'C'}]
        assert trajectory_edit_distance(t1, t2) == 0

    def test_one_substitution(self):
        t1 = [{'tool': 'A'}, {'tool': 'B'}, {'tool': 'C'}]
        t2 = [{'tool': 'A'}, {'tool': 'X'}, {'tool': 'C'}]
        assert trajectory_edit_distance(t1, t2) == 1

    def test_one_deletion(self):
        t1 = [{'tool': 'A'}, {'tool': 'B'}, {'tool': 'C'}]
        t2 = [{'tool': 'A'}, {'tool': 'C'}]
        assert trajectory_edit_distance(t1, t2) == 1

    def test_completely_different(self):
        t1 = [{'tool': 'A'}, {'tool': 'B'}]
        t2 = [{'tool': 'X'}, {'tool': 'Y'}]
        assert trajectory_edit_distance(t1, t2) == 2


class TestDivergencePoint:
    """Tests for trajectory divergence detection."""

    def test_immediate_divergence(self):
        t1 = [{'data': {'code': 'A'}}]
        t2 = [{'data': {'code': 'B'}}]
        assert find_divergence_point(t1, t2) == 0

    def test_late_divergence(self, partial_overlap_trajectories):
        t1, t2 = partial_overlap_trajectories[0], partial_overlap_trajectories[1]
        # They share the first step
        assert find_divergence_point(t1, t2) == 1

    def test_no_divergence(self, identical_trajectories):
        t1, t2 = identical_trajectories[0], identical_trajectories[1]
        # All steps identical, returns min length
        assert find_divergence_point(t1, t2) == len(t1)


class TestMeanMetrics:
    """Tests for aggregate pairwise metrics."""

    def test_mean_jaccard_identical(self, identical_trajectories):
        jaccard = mean_pairwise_jaccard(identical_trajectories)
        assert jaccard == 1.0

    def test_mean_edit_identical(self, identical_trajectories):
        edit = mean_edit_distance(identical_trajectories)
        assert edit == 0.0

    def test_mean_jaccard_single(self):
        jaccard = mean_pairwise_jaccard([[{'tool': 'A'}]])
        assert jaccard == 1.0


class TestSerializeTrajectory:
    """Tests for trajectory serialization."""

    def test_serialize_with_code(self):
        traj = [
            {'data': {'code': 'x = 1', 'reasoning': 'thinking'}},
            {'tool': 'query', 'data': {'code': 'y = 2'}},
        ]
        text = serialize_trajectory(traj)
        assert 'x = 1' in text
        assert 'y = 2' in text
        assert '[query]' in text

    def test_serialize_empty(self):
        text = serialize_trajectory([])
        assert text == ''


# =============================================================================
# Level 3: Decision Point Analysis Tests
# =============================================================================

class TestIterationDiversity:
    """Tests for per-iteration diversity measurement."""

    def test_all_same_at_iteration(self, identical_trajectories):
        diversity = iteration_diversity(identical_trajectories, 0)
        # All have same code at iteration 0
        assert diversity == pytest.approx(1/5, rel=0.01)  # 1 unique / 5 total

    def test_all_different_at_iteration(self, diverse_trajectories):
        diversity = iteration_diversity(diverse_trajectories, 0)
        # All have different code at iteration 0
        assert diversity == 1.0


class TestForkingPoints:
    """Tests for forking point identification."""

    def test_no_forking_identical(self, identical_trajectories):
        forking = identify_forking_points(identical_trajectories, threshold=0.5)
        assert forking == []

    def test_forking_point_at_divergence(self, partial_overlap_trajectories):
        # First iteration same, second different
        forking = identify_forking_points(partial_overlap_trajectories, threshold=0.5)
        assert 1 in forking


class TestDivergenceStatistics:
    """Tests for divergence statistics."""

    def test_stats_identical(self, identical_trajectories):
        stats = divergence_statistics(identical_trajectories)
        # With 5 identical trajectories, mean divergence should be at the end (2 steps)
        assert stats['mean_divergence_point'] == 2.0
        assert stats['never_diverge'] == 10  # C(5,2) = 10 pairs, all identical

    def test_stats_immediate_diverge(self, diverse_trajectories):
        stats = divergence_statistics(diverse_trajectories)
        # All diverge at iteration 0
        assert stats['mean_divergence_point'] == 0.0


# =============================================================================
# Level 4: Convergence Diagnostics Tests
# =============================================================================

class TestEffectiveTrajectoryCount:
    """Tests for effective sample size computation."""

    def test_single_trajectory(self):
        result = effective_trajectory_count([[{'tool': 'A'}]])
        assert result['actual_count'] == 1
        assert result['efficiency'] == 1.0

    def test_empty_list(self):
        result = effective_trajectory_count([])
        assert result['actual_count'] == 0


# =============================================================================
# Comprehensive Report Tests
# =============================================================================

class TestDiversityReport:
    """Tests for the comprehensive diversity report."""

    def test_report_empty(self):
        report = compute_diversity_report([])
        assert report.n_trajectories == 0

    def test_report_single(self):
        report = compute_diversity_report([[{'tool': 'A'}]])
        assert report.n_trajectories == 1

    def test_report_identical(self, identical_trajectories):
        report = compute_diversity_report(identical_trajectories)
        assert report.n_trajectories == 5
        # Identical trajectories should have high Jaccard
        assert report.mean_pairwise_jaccard == 1.0
        # Low edit distance
        assert report.mean_edit_distance == 0.0

    def test_report_with_queries(self, partial_overlap_trajectories, sample_queries):
        report = compute_diversity_report(
            partial_overlap_trajectories,
            queries=sample_queries[:3]
        )
        assert report.unique_query_patterns > 0

    def test_report_to_dict(self, partial_overlap_trajectories):
        report = compute_diversity_report(partial_overlap_trajectories)
        d = report.to_dict()
        assert isinstance(d, dict)
        assert 'n_trajectories' in d
        assert 'mean_pairwise_jaccard' in d

    def test_report_summary(self, partial_overlap_trajectories):
        report = compute_diversity_report(partial_overlap_trajectories)
        summary = report.summary()
        assert 'Diversity Report' in summary
        assert 'trajectories' in summary


# =============================================================================
# Utility Function Tests
# =============================================================================

class TestLevenshteinDistance:
    """Tests for Levenshtein distance helper."""

    def test_identical(self):
        assert _levenshtein_distance(['a', 'b', 'c'], ['a', 'b', 'c']) == 0

    def test_one_different(self):
        assert _levenshtein_distance(['a', 'b', 'c'], ['a', 'x', 'c']) == 1

    def test_empty(self):
        assert _levenshtein_distance([], ['a', 'b']) == 2
        assert _levenshtein_distance(['a', 'b'], []) == 2


# =============================================================================
# Integration Tests (require optional dependencies)
# =============================================================================

class TestVendiScoreIntegration:
    """Tests for Vendi Score (requires vendi-score, sentence-transformers)."""

    @pytest.fixture(autouse=True)
    def check_dependencies(self):
        """Skip tests if optional dependencies not available."""
        try:
            import vendi_score
            from sentence_transformers import SentenceTransformer
        except ImportError:
            pytest.skip("vendi-score or sentence-transformers not installed")

    def test_sparql_vendi_identical(self):
        from experiments.reasoningbank.metrics.diversity import sparql_vendi_score

        queries = [
            "SELECT ?x WHERE { ?x a up:Protein }",
            "SELECT ?x WHERE { ?x a up:Protein }",
            "SELECT ?x WHERE { ?x a up:Protein }",
        ]
        score = sparql_vendi_score(queries)
        # Identical queries should give score close to 1.0
        assert score < 1.5

    def test_sparql_vendi_diverse(self):
        from experiments.reasoningbank.metrics.diversity import sparql_vendi_score

        queries = [
            "SELECT ?x WHERE { ?x a up:Protein }",
            "ASK { ?x up:organism ?human }",
            "CONSTRUCT { ?s ?p ?o } WHERE { ?s a up:Gene }",
        ]
        score = sparql_vendi_score(queries)
        # Diverse queries should give higher score
        assert score > 1.5

    def test_trajectory_vendi_identical(self, identical_trajectories):
        from experiments.reasoningbank.metrics.diversity import trajectory_vendi_score

        score = trajectory_vendi_score(identical_trajectories)
        # Identical should give low score (close to 1.0)
        assert score < 2.0

    def test_trajectory_vendi_diverse(self, diverse_trajectories):
        from experiments.reasoningbank.metrics.diversity import trajectory_vendi_score

        score = trajectory_vendi_score(diverse_trajectories)
        # Diverse should give higher score (closer to 5.0)
        assert score > 2.0


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
