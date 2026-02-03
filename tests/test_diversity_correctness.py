"""Mathematical correctness tests for diversity metrics.

These tests verify the metrics produce mathematically correct results
using hand-calculated ground truth values.

References:
- Vendi Score: https://arxiv.org/abs/2210.02410
- Jaccard Index: https://en.wikipedia.org/wiki/Jaccard_index
- Levenshtein Distance: https://en.wikipedia.org/wiki/Levenshtein_distance
"""

import pytest
import numpy as np
import sys
sys.path.insert(0, '/Users/cvardema/dev/git/LA3D/rlm')

from experiments.reasoningbank.metrics.diversity import (
    _levenshtein_distance,
    _cosine_similarity,
    answer_jaccard,
    trajectory_jaccard,
)


# =============================================================================
# Levenshtein Distance - Known Examples from Literature
# =============================================================================

class TestLevenshteinCorrectness:
    """Verify Levenshtein distance against known examples."""

    def test_wikipedia_example_kitten_sitting(self):
        """Classic example: kitten → sitting = 3 operations.

        kitten → sitten (substitute k→s)
        sitten → sittin (substitute e→i)
        sittin → sitting (insert g)
        """
        # Our implementation works on lists, so convert to char lists
        seq1 = list('kitten')
        seq2 = list('sitting')
        assert _levenshtein_distance(seq1, seq2) == 3

    def test_saturday_sunday(self):
        """saturday → sunday = 3 operations.

        saturday → sturday (delete a)
        sturday → surday (delete t)
        surday → sunday (substitute r→n)
        """
        seq1 = list('saturday')
        seq2 = list('sunday')
        assert _levenshtein_distance(seq1, seq2) == 3

    def test_empty_to_string(self):
        """Empty to 'abc' = 3 insertions."""
        assert _levenshtein_distance([], list('abc')) == 3

    def test_string_to_empty(self):
        """'abc' to empty = 3 deletions."""
        assert _levenshtein_distance(list('abc'), []) == 3

    def test_identical_strings(self):
        """Identical strings = 0 distance."""
        seq = list('hello')
        assert _levenshtein_distance(seq, seq) == 0

    def test_completely_different(self):
        """'abc' to 'xyz' = 3 substitutions."""
        assert _levenshtein_distance(list('abc'), list('xyz')) == 3

    def test_single_insertion(self):
        """'ac' to 'abc' = 1 insertion."""
        assert _levenshtein_distance(list('ac'), list('abc')) == 1

    def test_single_deletion(self):
        """'abc' to 'ac' = 1 deletion."""
        assert _levenshtein_distance(list('abc'), list('ac')) == 1

    def test_single_substitution(self):
        """'abc' to 'adc' = 1 substitution."""
        assert _levenshtein_distance(list('abc'), list('adc')) == 1

    def test_tool_sequences(self):
        """Test with realistic tool call sequences."""
        # Sequence 1: query → filter → submit
        # Sequence 2: query → explore → filter → submit
        # Distance = 1 (insert 'explore')
        seq1 = ['query', 'filter', 'submit']
        seq2 = ['query', 'explore', 'filter', 'submit']
        assert _levenshtein_distance(seq1, seq2) == 1


# =============================================================================
# Jaccard Index - Mathematical Properties
# =============================================================================

class TestJaccardCorrectness:
    """Verify Jaccard index calculations."""

    def test_identical_sets(self):
        """J(A, A) = 1.0 for any non-empty A."""
        answers = [{1, 2, 3}, {1, 2, 3}]
        assert answer_jaccard(answers) == 1.0

    def test_disjoint_sets(self):
        """J(A, B) = 0.0 when A ∩ B = ∅."""
        answers = [{1, 2}, {3, 4}]
        assert answer_jaccard(answers) == 0.0

    def test_subset_relationship(self):
        """J({1,2}, {1,2,3,4}) = 2/4 = 0.5."""
        answers = [{1, 2}, {1, 2, 3, 4}]
        # |A ∩ B| = 2, |A ∪ B| = 4
        assert answer_jaccard(answers) == 0.5

    def test_partial_overlap(self):
        """J({1,2,3}, {2,3,4}) = 2/4 = 0.5."""
        answers = [{1, 2, 3}, {2, 3, 4}]
        # |A ∩ B| = {2,3} = 2
        # |A ∪ B| = {1,2,3,4} = 4
        assert answer_jaccard(answers) == 0.5

    def test_one_element_overlap(self):
        """J({1,2,3}, {3,4,5}) = 1/5 = 0.2."""
        answers = [{1, 2, 3}, {3, 4, 5}]
        # |A ∩ B| = {3} = 1
        # |A ∪ B| = {1,2,3,4,5} = 5
        assert answer_jaccard(answers) == 0.2

    def test_three_way_average(self):
        """Mean pairwise Jaccard for 3 sets.

        A = {1,2}, B = {2,3}, C = {3,4}
        J(A,B) = 1/3 (intersection {2}, union {1,2,3})
        J(A,C) = 0/4 = 0 (no overlap)
        J(B,C) = 1/3 (intersection {3}, union {2,3,4})
        Mean = (1/3 + 0 + 1/3) / 3 = 2/9 ≈ 0.222
        """
        answers = [{1, 2}, {2, 3}, {3, 4}]
        expected = (1/3 + 0 + 1/3) / 3
        assert answer_jaccard(answers) == pytest.approx(expected, rel=0.01)

    def test_trajectory_jaccard_tool_sets(self):
        """Trajectory Jaccard based on tool sets."""
        # T1 uses tools: {A, B, C}
        # T2 uses tools: {A, B, D}
        # J = |{A,B}| / |{A,B,C,D}| = 2/4 = 0.5
        t1 = [{'tool': 'A'}, {'tool': 'B'}, {'tool': 'C'}]
        t2 = [{'tool': 'A'}, {'tool': 'B'}, {'tool': 'D'}]
        assert trajectory_jaccard(t1, t2) == 0.5


# =============================================================================
# Cosine Similarity - Mathematical Properties
# =============================================================================

class TestCosineSimilarityCorrectness:
    """Verify cosine similarity matrix computation."""

    def test_identical_vectors(self):
        """cos(v, v) = 1.0."""
        embeddings = np.array([
            [1.0, 0.0, 0.0],
            [1.0, 0.0, 0.0],
        ])
        sim = _cosine_similarity(embeddings)
        assert sim[0, 1] == pytest.approx(1.0, rel=0.001)

    def test_orthogonal_vectors(self):
        """cos(v1, v2) = 0.0 for orthogonal vectors."""
        embeddings = np.array([
            [1.0, 0.0, 0.0],
            [0.0, 1.0, 0.0],
        ])
        sim = _cosine_similarity(embeddings)
        assert sim[0, 1] == pytest.approx(0.0, abs=0.001)

    def test_opposite_vectors(self):
        """cos(v, -v) = -1.0."""
        embeddings = np.array([
            [1.0, 0.0, 0.0],
            [-1.0, 0.0, 0.0],
        ])
        sim = _cosine_similarity(embeddings)
        assert sim[0, 1] == pytest.approx(-1.0, rel=0.001)

    def test_45_degree_angle(self):
        """cos(45°) = 1/√2 ≈ 0.707."""
        embeddings = np.array([
            [1.0, 0.0],
            [1.0, 1.0],  # 45° from x-axis
        ])
        sim = _cosine_similarity(embeddings)
        # cos(45°) = 1/√2 ≈ 0.7071
        assert sim[0, 1] == pytest.approx(1/np.sqrt(2), rel=0.001)

    def test_symmetry(self):
        """Similarity matrix should be symmetric."""
        embeddings = np.array([
            [1.0, 2.0, 3.0],
            [4.0, 5.0, 6.0],
            [7.0, 8.0, 9.0],
        ])
        sim = _cosine_similarity(embeddings)
        assert np.allclose(sim, sim.T)

    def test_diagonal_ones(self):
        """Diagonal should be 1.0 (self-similarity)."""
        embeddings = np.array([
            [1.0, 2.0, 3.0],
            [4.0, 5.0, 6.0],
        ])
        sim = _cosine_similarity(embeddings)
        assert sim[0, 0] == pytest.approx(1.0, rel=0.001)
        assert sim[1, 1] == pytest.approx(1.0, rel=0.001)


# =============================================================================
# Vendi Score - Mathematical Properties (requires vendi-score package)
# =============================================================================

class TestVendiScoreCorrectness:
    """Verify Vendi Score mathematical properties.

    Vendi Score = exp(Shannon entropy of similarity eigenvalues)

    Key properties:
    - For n identical items: VS ≈ 1.0
    - For n orthogonal items: VS = n
    - For n items with similarity matrix S: VS = exp(-Σ λ_i log λ_i) where λ_i are eigenvalues of S/n
    """

    @pytest.fixture(autouse=True)
    def check_vendi(self):
        """Skip if vendi-score not installed."""
        try:
            from vendi_score import vendi
            self.vendi = vendi
        except ImportError:
            pytest.skip("vendi-score not installed")

    def test_identical_items_score_one(self):
        """n identical items should give VS ≈ 1.0.

        When all items are identical, similarity matrix is all 1s,
        which has one eigenvalue of 1 and rest are 0.
        Entropy = -1*log(1) = 0, so VS = exp(0) = 1.
        """
        # All-ones similarity matrix (all identical)
        n = 5
        sim = np.ones((n, n))
        score = self.vendi.score_K(sim)
        assert score == pytest.approx(1.0, rel=0.1)

    def test_orthogonal_items_score_n(self):
        """n orthogonal items should give VS = n.

        Identity matrix = all items perfectly distinct.
        All eigenvalues = 1/n, entropy = log(n), VS = n.
        """
        n = 5
        sim = np.eye(n)
        score = self.vendi.score_K(sim)
        assert score == pytest.approx(n, rel=0.1)

    def test_two_clusters(self):
        """Two clusters of identical items.

        If we have 2 clusters of size 2 each, VS should be ~2.
        """
        # 4x4 matrix: items 0,1 identical; items 2,3 identical; clusters orthogonal
        sim = np.array([
            [1.0, 1.0, 0.0, 0.0],
            [1.0, 1.0, 0.0, 0.0],
            [0.0, 0.0, 1.0, 1.0],
            [0.0, 0.0, 1.0, 1.0],
        ])
        score = self.vendi.score_K(sim)
        # Should be approximately 2 (two distinct clusters)
        assert score == pytest.approx(2.0, rel=0.2)

    def test_monotonicity_with_diversity(self):
        """More diverse items → higher Vendi Score."""
        # Low diversity: all similar
        sim_low = np.array([
            [1.0, 0.9, 0.9],
            [0.9, 1.0, 0.9],
            [0.9, 0.9, 1.0],
        ])

        # High diversity: all different
        sim_high = np.array([
            [1.0, 0.1, 0.1],
            [0.1, 1.0, 0.1],
            [0.1, 0.1, 1.0],
        ])

        score_low = self.vendi.score_K(sim_low)
        score_high = self.vendi.score_K(sim_high)

        assert score_high > score_low

    def test_bounds(self):
        """Vendi Score should be in [1, n]."""
        n = 5
        # Random similarity matrix
        np.random.seed(42)
        random_sim = np.random.rand(n, n)
        random_sim = (random_sim + random_sim.T) / 2  # Make symmetric
        np.fill_diagonal(random_sim, 1.0)  # Diagonal = 1

        score = self.vendi.score_K(random_sim)
        assert 1.0 <= score <= n


# =============================================================================
# Integration Test: End-to-End Correctness
# =============================================================================

class TestEndToEndCorrectness:
    """Test full pipeline with known data."""

    def test_diversity_report_with_known_data(self):
        """Verify DiversityReport produces expected values."""
        from experiments.reasoningbank.metrics.diversity import (
            compute_diversity_report,
            DiversityReport,
        )

        # Create 3 trajectories:
        # T1, T2 identical; T3 different
        t1 = [{'tool': 'A', 'data': {'code': 'x=1'}}, {'tool': 'B', 'data': {'code': 'y=2'}}]
        t2 = [{'tool': 'A', 'data': {'code': 'x=1'}}, {'tool': 'B', 'data': {'code': 'y=2'}}]
        t3 = [{'tool': 'C', 'data': {'code': 'z=3'}}, {'tool': 'D', 'data': {'code': 'w=4'}}]

        trajectories = [t1, t2, t3]
        report = compute_diversity_report(trajectories)

        # Check basic counts
        assert report.n_trajectories == 3

        # Jaccard calculations:
        # J(T1, T2) = |{A,B} ∩ {A,B}| / |{A,B} ∪ {A,B}| = 2/2 = 1.0
        # J(T1, T3) = |{A,B} ∩ {C,D}| / |{A,B} ∪ {C,D}| = 0/4 = 0.0
        # J(T2, T3) = 0/4 = 0.0
        # Mean = (1.0 + 0.0 + 0.0) / 3 = 0.333
        assert report.mean_pairwise_jaccard == pytest.approx(1/3, rel=0.01)

        # Edit distance calculations:
        # ED(T1, T2) = 0 (identical sequences)
        # ED(T1, T3) = 2 (both tools different)
        # ED(T2, T3) = 2
        # Mean = (0 + 2 + 2) / 3 = 1.333
        assert report.mean_edit_distance == pytest.approx(4/3, rel=0.01)

    def test_forking_point_with_known_divergence(self):
        """Test forking point detection with controlled divergence."""
        from experiments.reasoningbank.metrics.diversity import (
            identify_forking_points,
            iteration_diversity,
        )

        # 3 trajectories that share first 2 steps, diverge at step 3
        common1 = {'data': {'code': 'step1'}}
        common2 = {'data': {'code': 'step2'}}

        t1 = [common1, common2, {'data': {'code': 'path_A'}}]
        t2 = [common1, common2, {'data': {'code': 'path_B'}}]
        t3 = [common1, common2, {'data': {'code': 'path_C'}}]

        trajectories = [t1, t2, t3]

        # Check diversity at each iteration
        div0 = iteration_diversity(trajectories, 0)
        div1 = iteration_diversity(trajectories, 1)
        div2 = iteration_diversity(trajectories, 2)

        # Iterations 0 and 1: all same → diversity = 1/3
        assert div0 == pytest.approx(1/3, rel=0.01)
        assert div1 == pytest.approx(1/3, rel=0.01)

        # Iteration 2: all different → diversity = 1.0
        assert div2 == 1.0

        # Forking point should be at iteration 2
        forking = identify_forking_points(trajectories, threshold=0.5)
        assert 2 in forking
        assert 0 not in forking
        assert 1 not in forking


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
