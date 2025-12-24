"""Tests for coherence computation."""

import pytest
import numpy as np

from symbolu.chitta_vritti.coherence import (
    cosine_similarity,
    compute_pairwise_similarities,
    compute_fractures,
    compute_aggregate_coherence,
    find_primary_fracture,
    CoherenceComputer,
    quick_opposition_check,
)
from symbolu.chitta_vritti.types import ChittaVrittiInputs
from symbolu.chitta_vritti.projector import l2_normalize


class TestCosineSimilarity:
    """Test cosine similarity computation."""

    def test_identical_vectors_similarity_one(self):
        """Identical vectors → similarity = 1."""
        vec = l2_normalize(np.array([1.0, 2.0, 3.0]))
        assert cosine_similarity(vec, vec) == pytest.approx(1.0)

    def test_opposite_vectors_similarity_negative_one(self):
        """Opposite vectors → similarity = -1."""
        vec_a = l2_normalize(np.array([1.0, 0.0, 0.0]))
        vec_b = l2_normalize(np.array([-1.0, 0.0, 0.0]))
        assert cosine_similarity(vec_a, vec_b) == pytest.approx(-1.0)

    def test_orthogonal_vectors_similarity_zero(self):
        """Orthogonal vectors → similarity = 0."""
        vec_a = l2_normalize(np.array([1.0, 0.0, 0.0]))
        vec_b = l2_normalize(np.array([0.0, 1.0, 0.0]))
        assert cosine_similarity(vec_a, vec_b) == pytest.approx(0.0)


class TestPairwiseSimilarities:
    """Test pairwise similarity computation."""

    def test_two_projections(self):
        """Two projections → one pair."""
        projections = {
            "a": l2_normalize(np.array([1.0, 0.0])),
            "b": l2_normalize(np.array([0.0, 1.0])),
        }

        similarities = compute_pairwise_similarities(projections)

        assert len(similarities) == 1
        assert ("a", "b") in similarities or ("b", "a") in similarities

    def test_three_projections(self):
        """Three projections → three pairs."""
        projections = {
            "a": l2_normalize(np.array([1.0, 0.0, 0.0])),
            "b": l2_normalize(np.array([0.0, 1.0, 0.0])),
            "c": l2_normalize(np.array([0.0, 0.0, 1.0])),
        }

        similarities = compute_pairwise_similarities(projections)
        assert len(similarities) == 3

    def test_keys_are_sorted(self):
        """Keys should be sorted tuples for consistency."""
        projections = {
            "z": l2_normalize(np.array([1.0, 0.0])),
            "a": l2_normalize(np.array([0.0, 1.0])),
        }

        similarities = compute_pairwise_similarities(projections)

        for key in similarities:
            assert key[0] < key[1], f"Key {key} not sorted"


class TestFractures:
    """Test fracture computation."""

    def test_similarity_one_fracture_zero(self):
        """Similarity 1 → fracture 0."""
        similarities = {("a", "b"): 1.0}
        fractures = compute_fractures(similarities)
        assert fractures[("a", "b")] == pytest.approx(0.0)

    def test_similarity_negative_one_fracture_one(self):
        """Similarity -1 → fracture 1."""
        similarities = {("a", "b"): -1.0}
        fractures = compute_fractures(similarities)
        assert fractures[("a", "b")] == pytest.approx(1.0)

    def test_similarity_zero_fracture_half(self):
        """Similarity 0 → fracture 0.5."""
        similarities = {("a", "b"): 0.0}
        fractures = compute_fractures(similarities)
        assert fractures[("a", "b")] == pytest.approx(0.5)


class TestAggregateCoherence:
    """Test aggregate coherence computation."""

    def test_empty_fractures_full_coherence(self):
        """No fractures → coherence = 1."""
        coherence = compute_aggregate_coherence({})
        assert coherence == 1.0

    def test_zero_fractures_full_coherence(self):
        """All zero fractures → coherence = 1."""
        fractures = {("a", "b"): 0.0, ("a", "c"): 0.0}
        coherence = compute_aggregate_coherence(fractures)
        assert coherence == pytest.approx(1.0)

    def test_max_fractures_zero_coherence(self):
        """All max fractures → coherence = 0."""
        fractures = {("a", "b"): 1.0, ("a", "c"): 1.0}
        coherence = compute_aggregate_coherence(fractures)
        assert coherence == pytest.approx(0.0)


class TestPrimaryFracture:
    """Test primary fracture identification."""

    def test_empty_fractures_returns_none(self):
        """Empty fractures → None."""
        assert find_primary_fracture({}) is None

    def test_finds_highest_fracture(self):
        """Should return pair with highest fracture."""
        fractures = {
            ("a", "b"): 0.3,
            ("a", "c"): 0.7,  # Highest
            ("b", "c"): 0.5,
        }

        primary = find_primary_fracture(fractures)
        assert primary == ("a", "c")


class TestCoherenceComputer:
    """Test CoherenceComputer class."""

    def test_compute_returns_all_components(self):
        """Compute should return coherence, fractures, primary_fracture."""
        dim = 32
        rng = np.random.default_rng(42)

        inputs = ChittaVrittiInputs(
            phonemic_rep=rng.random(dim),
            semantic_rep=rng.random(dim),
            structural_rep=rng.random(dim),
        )

        computer = CoherenceComputer(projection_dim=dim)
        coherence, fractures, primary = computer.compute(inputs)

        assert 0.0 <= coherence <= 1.0
        assert len(fractures) == 3  # 3 pairs
        assert primary is not None

    def test_single_layer_returns_full_coherence(self):
        """Single layer → coherence = 1, no fractures."""
        inputs = ChittaVrittiInputs(
            semantic_rep=np.random.default_rng(42).random(32),
        )

        computer = CoherenceComputer()
        coherence, fractures, primary = computer.compute(inputs)

        assert coherence == 1.0
        assert fractures == {}
        assert primary is None


class TestQuickOppositionCheck:
    """Test quick opposition check for fast-path safety."""

    def test_missing_layers_returns_zero(self):
        """Missing semantic or structural → returns 0."""
        inputs = ChittaVrittiInputs(
            phonemic_rep=np.ones(32),
            # semantic and structural missing
        )

        assert quick_opposition_check(inputs) == 0.0

    def test_aligned_layers_returns_zero(self):
        """Aligned layers → returns 0."""
        vec = np.ones(32) / np.sqrt(32)
        inputs = ChittaVrittiInputs(
            semantic_rep=vec.copy(),
            structural_rep=vec.copy(),
        )

        assert quick_opposition_check(inputs) == 0.0

    def test_opposing_layers_returns_positive(self):
        """Opposing layers → returns positive value."""
        vec_a = np.zeros(32)
        vec_a[0] = 1.0

        vec_b = np.zeros(32)
        vec_b[0] = -1.0

        inputs = ChittaVrittiInputs(
            semantic_rep=vec_a,
            structural_rep=vec_b,
        )

        result = quick_opposition_check(inputs)
        assert result > 0.0
