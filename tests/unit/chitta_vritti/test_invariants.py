"""Tests for Chitta-Vṛtti invariants.

Tests the core invariants specified in the design document:
- INV-CV-1: Order independence
- INV-CV-2: Scale invariance
- INV-CV-3: Identity
- INV-CV-4: Null handling
- INV-CV-5: Bounded output
- INV-CV-6: Determinism
- INV-CV-7: Sum constraint
"""

import pytest
import numpy as np

from symbolu.chitta_vritti.types import ChittaVrittiInputs, OptimizedConfig
from symbolu.chitta_vritti.coherence import (
    compute_pairwise_similarities,
    compute_fractures,
    compute_aggregate_coherence,
)
from symbolu.chitta_vritti.vritti import compute_nidra, normalize_vritti
from symbolu.chitta_vritti.engine import ChittaVrittiEngine


class TestOrderIndependence:
    """INV-CV-1: Reordering representations must not change results."""

    def test_pairwise_similarity_order_independence(self):
        """Similarity keys should be sorted consistently."""
        projections_abc = {
            "a": np.array([1.0, 0.0, 0.0]),
            "b": np.array([0.0, 1.0, 0.0]),
            "c": np.array([0.0, 0.0, 1.0]),
        }

        projections_cba = {
            "c": np.array([0.0, 0.0, 1.0]),
            "b": np.array([0.0, 1.0, 0.0]),
            "a": np.array([1.0, 0.0, 0.0]),
        }

        sim_abc = compute_pairwise_similarities(projections_abc)
        sim_cba = compute_pairwise_similarities(projections_cba)

        # Keys should be the same (sorted)
        assert set(sim_abc.keys()) == set(sim_cba.keys())

        # Values should be the same
        for key in sim_abc:
            assert sim_abc[key] == pytest.approx(sim_cba[key])

    def test_coherence_order_independence(self):
        """Coherence should be same regardless of input order."""
        dim = 32
        rng = np.random.default_rng(42)

        # Create random representations
        phonemic = rng.random(dim)
        semantic = rng.random(dim)
        structural = rng.random(dim)

        # Order 1
        inputs1 = ChittaVrittiInputs(
            phonemic_rep=phonemic,
            semantic_rep=semantic,
            structural_rep=structural,
        )

        # Order 2 (different assignment order)
        inputs2 = ChittaVrittiInputs(
            structural_rep=structural,
            phonemic_rep=phonemic,
            semantic_rep=semantic,
        )

        engine = ChittaVrittiEngine()
        result1 = engine.compute(inputs1)
        engine.reset_session()
        result2 = engine.compute(inputs2)

        assert result1.coherence == pytest.approx(result2.coherence)


class TestScaleInvariance:
    """INV-CV-2: Uniform scaling before projection must not change similarity."""

    def test_l2_normalization_removes_scale(self):
        """Scaled vectors should have same similarity after L2 norm."""
        from symbolu.chitta_vritti.projector import l2_normalize
        from symbolu.chitta_vritti.coherence import cosine_similarity

        vec_a = np.array([1.0, 2.0, 3.0])
        vec_b = np.array([2.0, 4.0, 6.0])  # 2x scale

        norm_a = l2_normalize(vec_a)
        norm_b = l2_normalize(vec_b)

        # Should be identical after normalization
        assert np.allclose(norm_a, norm_b)

        # Similarity should be 1.0
        sim = cosine_similarity(norm_a, norm_b)
        assert sim == pytest.approx(1.0)


class TestIdentity:
    """INV-CV-3: Identical projections → coherence=1."""

    def test_identical_projections_full_coherence(self):
        """Identical representations should yield coherence=1."""
        dim = 32
        identical = np.random.default_rng(42).random(dim)

        inputs = ChittaVrittiInputs(
            phonemic_rep=identical.copy(),
            semantic_rep=identical.copy(),
            structural_rep=identical.copy(),
            temporal_rep=identical.copy(),
            entropy=0.0,
            motion=0.0,
        )

        # Use config that disables fast path to test actual computation
        config = OptimizedConfig(fast_path_entropy_threshold=-1.0)
        engine = ChittaVrittiEngine(config=config)
        result = engine.compute(inputs)

        assert result.coherence == pytest.approx(1.0, abs=0.01)

    def test_identical_projections_zero_fractures(self):
        """Identical representations should yield zero fractures."""
        dim = 32
        identical = np.random.default_rng(42).random(dim)

        projections = {
            "a": identical.copy(),
            "b": identical.copy(),
            "c": identical.copy(),
        }

        # Normalize first
        from symbolu.chitta_vritti.projector import l2_normalize
        projections = {k: l2_normalize(v) for k, v in projections.items()}

        similarities = compute_pairwise_similarities(projections)
        fractures = compute_fractures(similarities)

        for frac in fractures.values():
            assert frac == pytest.approx(0.0, abs=0.01)


class TestNullHandling:
    """INV-CV-4: Missing representation increases nidrā, never others."""

    def test_missing_layers_increase_nidra(self):
        """Missing layers should only increase nidrā."""
        # All present
        inputs_full = ChittaVrittiInputs(
            phonemic_rep=np.zeros(32),
            semantic_rep=np.zeros(32),
            structural_rep=np.zeros(32),
            temporal_rep=np.zeros(32),
        )

        # One missing
        inputs_one = ChittaVrittiInputs(
            phonemic_rep=np.zeros(32),
            semantic_rep=np.zeros(32),
            structural_rep=np.zeros(32),
        )

        # Two missing
        inputs_two = ChittaVrittiInputs(
            phonemic_rep=np.zeros(32),
            semantic_rep=np.zeros(32),
        )

        nidra_full = compute_nidra(inputs_full)
        nidra_one = compute_nidra(inputs_one)
        nidra_two = compute_nidra(inputs_two)

        assert nidra_full == 0.0
        assert nidra_one == 0.25
        assert nidra_two == 0.5

    def test_nidra_only_increases_with_missing(self):
        """Other vṛttis should not increase due to missing layers alone."""
        from symbolu.chitta_vritti.vritti import (
            compute_pramana,
            compute_viparyaya,
            compute_vikalpa,
        )

        config = OptimizedConfig()

        # Pramāṇa should not increase due to missing layers
        pramana_value = compute_pramana(
            coherence=0.5, entropy=0.5, motion=0.5, config=config
        )

        # Viparyaya needs fractures, empty fractures = 0
        viparyaya_value = compute_viparyaya(
            fractures={}, confidence=1.0, config=config
        )

        # Vikalpa needs fractures and entropy
        vikalpa_value = compute_vikalpa(
            fractures={}, entropy=0.5, config=config
        )

        assert viparyaya_value == 0.0
        assert vikalpa_value == 0.0


class TestBoundedOutput:
    """INV-CV-5: All outputs ∈ [0,1]."""

    def test_coherence_bounded(self):
        """Coherence should be in [0, 1]."""
        # Test with various fracture values
        for mean_frac in [0.0, 0.25, 0.5, 0.75, 1.0]:
            fractures = {("a", "b"): mean_frac}
            coherence = compute_aggregate_coherence(fractures)
            assert 0.0 <= coherence <= 1.0

    def test_vritti_values_bounded(self):
        """All vṛtti values should be in [0, 1]."""
        dim = 32
        rng = np.random.default_rng(42)

        # Random inputs
        inputs = ChittaVrittiInputs(
            phonemic_rep=rng.random(dim),
            semantic_rep=rng.random(dim),
            structural_rep=rng.random(dim),
            temporal_rep=rng.random(dim),
            entropy=rng.random(),
            motion=rng.random(),
        )

        engine = ChittaVrittiEngine()
        result = engine.compute(inputs)

        for mode, value in result.vritti.items():
            assert 0.0 <= value <= 1.0, f"{mode} = {value} not in [0,1]"

    def test_score_bounded(self):
        """Score should be in [0, 1]."""
        dim = 32
        rng = np.random.default_rng(42)

        for _ in range(10):
            inputs = ChittaVrittiInputs(
                phonemic_rep=rng.random(dim),
                semantic_rep=rng.random(dim),
                entropy=rng.random(),
                motion=rng.random(),
            )

            engine = ChittaVrittiEngine()
            result = engine.compute(inputs)

            assert 0.0 <= result.score <= 1.0


class TestDeterminism:
    """INV-CV-6: Same inputs → identical outputs."""

    def test_same_inputs_same_outputs(self):
        """Same inputs should produce identical outputs every time."""
        dim = 32
        rng = np.random.default_rng(42)

        phonemic = rng.random(dim)
        semantic = rng.random(dim)
        structural = rng.random(dim)

        inputs = ChittaVrittiInputs(
            phonemic_rep=phonemic,
            semantic_rep=semantic,
            structural_rep=structural,
            entropy=0.3,
            motion=0.2,
        )

        engine = ChittaVrittiEngine()

        # Run multiple times
        results = []
        for _ in range(5):
            engine.reset_session()
            result = engine.compute(inputs)
            results.append(result)

        # All should be identical
        for r in results[1:]:
            assert r.coherence == results[0].coherence
            assert r.score == results[0].score
            assert r.dominant_vritti == results[0].dominant_vritti
            for mode in r.vritti:
                assert r.vritti[mode] == pytest.approx(results[0].vritti[mode])


class TestSumConstraint:
    """INV-CV-7: Σ p_v[v] = 1.0 (probability distribution)."""

    def test_vritti_sums_to_one(self):
        """Vṛtti distribution should sum to 1.0."""
        dim = 32
        rng = np.random.default_rng(42)

        for _ in range(10):
            inputs = ChittaVrittiInputs(
                phonemic_rep=rng.random(dim),
                semantic_rep=rng.random(dim),
                structural_rep=rng.random(dim),
                entropy=rng.random(),
                motion=rng.random(),
            )

            engine = ChittaVrittiEngine()
            result = engine.compute(inputs)

            vritti_sum = sum(result.vritti.values())
            assert vritti_sum == pytest.approx(1.0, abs=0.01)

    def test_normalize_vritti_sums_to_one(self):
        """normalize_vritti should produce sum=1."""
        raw = {"pramana": 0.5, "viparyaya": 0.2, "vikalpa": 0.1, "smrti": 0.1, "nidra": 0.1}
        normalized = normalize_vritti(raw)

        assert sum(normalized.values()) == pytest.approx(1.0)

    def test_normalize_handles_all_zeros(self):
        """normalize_vritti should handle all-zero input gracefully."""
        raw = {"pramana": 0.0, "viparyaya": 0.0, "vikalpa": 0.0, "smrti": 0.0, "nidra": 0.0}
        normalized = normalize_vritti(raw)

        # Should return uniform distribution when all zeros
        assert sum(normalized.values()) == pytest.approx(1.0)
        # Each value should be 1/5 = 0.2
        for value in normalized.values():
            assert value == pytest.approx(0.2)
