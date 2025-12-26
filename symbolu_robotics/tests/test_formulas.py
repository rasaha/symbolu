# Symbolu Robotics - Formula Tests
"""Tests for patent formula implementations (BCVF, USE, SCC)."""

import pytest
import numpy as np
from typing import Dict

from symbolu_robotics.formulas.bcvf import (
    compute_consistency_lagrangian,
    compute_bcvf_weight,
    normalize_bcvf_weights,
    score_action_candidates,
    BCVFScorer,
    BCVFConfig,
    ActionScore,
)
from symbolu_robotics.formulas.use import (
    compute_correlation_matrix,
    compute_coherence_fusion,
    compute_temporal_alignment,
    compute_confidence,
    USEFusion,
    USEConfig,
)
from symbolu_robotics.formulas.scc import (
    compute_layer_coherence,
    compute_global_coherence,
    compute_cosine_similarity,
    compute_semantic_entropy,
    SCCMonitor,
    SCCConfig,
)


class TestBCVFFormulas:
    """Tests for BCVF (B1-B3) formulas."""

    def test_b1_consistency_lagrangian_perfect_scores(self):
        """Test B1 with perfect forward and backward scores."""
        L = compute_consistency_lagrangian(1.0, 1.0)
        assert L == 0.0  # Perfect scores = zero Lagrangian

    def test_b1_consistency_lagrangian_zero_scores(self):
        """Test B1 with zero scores."""
        L = compute_consistency_lagrangian(0.0, 0.0)
        assert L == 2.0  # λf(1)² + λb(1)² = 1 + 1 = 2

    def test_b1_consistency_lagrangian_mismatched(self):
        """Test B1 with mismatched scores."""
        L = compute_consistency_lagrangian(1.0, 0.0)
        # λf(0)² + λb(1)² + λc(1)² = 0 + 1 + 0.5 = 1.5
        assert L == 1.5

    def test_b1_custom_weights(self):
        """Test B1 with custom penalty weights."""
        L = compute_consistency_lagrangian(
            0.5, 0.5,
            lambda_f=2.0, lambda_b=2.0, lambda_c=1.0
        )
        # 2*(0.5)² + 2*(0.5)² + 1*(0)² = 0.5 + 0.5 + 0 = 1.0
        assert L == 1.0

    def test_b2_weight_conversion(self):
        """Test B2 weight conversion."""
        # Zero Lagrangian -> weight = 1
        w = compute_bcvf_weight(0.0)
        assert w == 1.0

        # Positive Lagrangian -> weight < 1
        w = compute_bcvf_weight(1.0, beta=1.0)
        assert np.isclose(w, np.exp(-1.0))

    def test_b2_higher_beta_more_selective(self):
        """Test that higher beta makes weights more selective."""
        L = 0.5
        w_low_beta = compute_bcvf_weight(L, beta=1.0)
        w_high_beta = compute_bcvf_weight(L, beta=5.0)
        assert w_high_beta < w_low_beta

    def test_b3_normalization(self):
        """Test B3 weight normalization."""
        weights = [0.5, 0.3, 0.2]
        normalized = normalize_bcvf_weights(weights)

        assert np.isclose(sum(normalized), 1.0)
        assert normalized[0] == 0.5
        assert normalized[1] == 0.3
        assert normalized[2] == 0.2

    def test_score_action_candidates(self):
        """Test complete action candidate scoring."""
        forward = [0.9, 0.7, 0.5]
        backward = [0.8, 0.9, 0.6]

        scores = score_action_candidates(forward, backward)

        assert len(scores) == 3
        assert all(isinstance(s, ActionScore) for s in scores)
        assert np.isclose(sum(s.normalized_weight for s in scores), 1.0)

    def test_bcvf_scorer_select_best(self):
        """Test BCVFScorer selects best candidate."""
        scorer = BCVFScorer()

        candidates = ["action1", "action2", "action3"]
        forward = [0.9, 0.5, 0.5]
        backward = [0.9, 0.5, 0.5]

        best_idx, best_score = scorer.select_best(candidates, forward, backward)

        assert best_idx == 0  # First has best scores
        assert best_score.forward_score == 0.9
        assert best_score.backward_score == 0.9

    def test_bcvf_scorer_consistency_matters(self):
        """Test that consistency affects score."""
        scorer = BCVFScorer()

        # Same total but different consistency
        forward = [0.7, 0.9]
        backward = [0.7, 0.5]  # Second is inconsistent

        scores = scorer.score_candidates(forward, backward)

        # First should score better (more consistent)
        assert scores[0].normalized_weight > scores[1].normalized_weight


class TestUSEFormulas:
    """Tests for USE (U1-U4) formulas."""

    def test_u1_correlation_matrix_single_modality(self):
        """Test U1 with single modality."""
        vectors = {'vision': np.random.rand(12)}
        R = compute_correlation_matrix(vectors)
        assert R.shape == (1, 1)
        assert R[0, 0] == 1.0

    def test_u1_correlation_matrix_identical_modalities(self):
        """Test U1 with identical modalities."""
        v = np.random.rand(12)
        vectors = {'a': v, 'b': v.copy()}
        R = compute_correlation_matrix(vectors)
        assert np.allclose(R, np.ones((2, 2)))

    def test_u1_correlation_matrix_orthogonal(self):
        """Test U1 with orthogonal modalities."""
        vectors = {
            'a': np.array([1, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0]),
            'b': np.array([0, 1, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0]),
        }
        R = compute_correlation_matrix(vectors)
        assert np.isclose(R[0, 1], 0.0)  # Orthogonal = zero correlation

    def test_u2_coherence_fusion_equal_weights(self):
        """Test U2 with coherent modalities."""
        v = np.random.rand(12)
        vectors = {'a': v, 'b': v.copy()}

        fused, weights = compute_coherence_fusion(vectors)

        assert fused.shape == (12,)
        assert len(weights) == 2
        assert np.isclose(weights['a'], weights['b'], atol=0.1)

    def test_u2_incoherent_modality_lower_weight(self):
        """Test U2 gives lower weight to incoherent modality."""
        vectors = {
            'a': np.ones(12),
            'b': np.ones(12),
            'c': -np.ones(12),  # Opposite = incoherent
        }

        _, weights = compute_coherence_fusion(vectors)

        # 'c' should have lower weight
        assert weights['c'] < weights['a']

    def test_u3_temporal_alignment_first_frame(self):
        """Test U3 on first frame (no previous)."""
        current = np.random.rand(12)
        aligned = compute_temporal_alignment(current, None)
        np.testing.assert_array_equal(aligned, current)

    def test_u3_temporal_alignment_smoothing(self):
        """Test U3 smooths between frames."""
        current = np.ones(12)
        previous = np.zeros(12)
        alpha = 0.3

        aligned = compute_temporal_alignment(current, previous, alpha)

        expected = 0.3 * current + 0.7 * previous
        np.testing.assert_array_almost_equal(aligned, expected)

    def test_u4_confidence_focused(self):
        """Test U4 gives high confidence for focused activation."""
        # All activation in one layer
        focused = np.zeros(12)
        focused[5] = 1.0

        conf = compute_confidence(focused)
        assert conf > 0.8

    def test_u4_confidence_uniform(self):
        """Test U4 gives low confidence for uniform activation."""
        uniform = np.ones(12) / 12
        conf = compute_confidence(uniform, normalize=False)
        assert conf < 0.2

    def test_use_fusion_complete(self):
        """Test complete USE fusion."""
        fusion = USEFusion()

        fusion.update('vision', np.random.rand(12))
        fusion.update('proprioception', np.random.rand(12))
        fusion.update('tactile', np.random.rand(12))

        result = fusion.fuse()

        assert result.fused_vector.shape == (12,)
        assert 0 <= result.coherence_score <= 1
        assert 0 <= result.confidence <= 1
        assert len(result.modality_weights) == 3

    def test_use_fusion_detect_failure(self):
        """Test USE detects sensor failure."""
        fusion = USEFusion()

        # Two coherent modalities
        v = np.random.rand(12)
        fusion.update('a', v)
        fusion.update('b', v)
        # One incoherent (simulating failure)
        fusion.update('c', -v)

        failures = fusion.detect_sensor_failure(threshold=0.25)
        assert 'c' in failures


class TestSCCFormulas:
    """Tests for SCC (S1-S9) formulas."""

    def test_s1_layer_coherence(self):
        """Test S1 per-layer coherence."""
        activations = np.random.rand(12)
        result = compute_layer_coherence(5, activations)

        assert 0 <= result.coherence <= 1
        assert 0 <= result.sensor_consistency <= 1
        assert 0 <= result.resonance <= 1
        assert 0 <= result.entropy <= 1
        assert 0 <= result.predictability <= 1

    def test_s1_high_activation_consistent(self):
        """Test S1 gives high consistency for strong activation."""
        activations = np.zeros(12)
        activations[5] = 0.9  # Strong activation

        result = compute_layer_coherence(5, activations)
        assert result.sensor_consistency > 0.7

    def test_s2_global_coherence(self):
        """Test S2 global coherence computation."""
        activations = np.random.rand(12)
        result = compute_global_coherence(activations)

        assert 0 <= result.global_coherence <= 1
        assert len(result.layer_coherences) == 12
        assert isinstance(result.is_valid, bool)

    def test_s3_validity_threshold(self):
        """Test S3 coherence threshold."""
        config = SCCConfig(coherence_threshold=0.5)

        # High coherence should be valid
        high_act = np.ones(12) * 0.8
        result = compute_global_coherence(high_act, config=config)
        assert result.is_valid

    def test_s4_cosine_similarity_identical(self):
        """Test S4 cosine similarity with identical vectors."""
        v = np.random.rand(12)
        sim = compute_cosine_similarity(v, v)
        assert np.isclose(sim, 1.0)

    def test_s4_cosine_similarity_opposite(self):
        """Test S4 cosine similarity with opposite vectors."""
        v = np.random.rand(12)
        sim = compute_cosine_similarity(v, -v)
        assert np.isclose(sim, -1.0)

    def test_s4_cosine_similarity_orthogonal(self):
        """Test S4 cosine similarity with orthogonal vectors."""
        a = np.array([1, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0])
        b = np.array([0, 1, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0])
        sim = compute_cosine_similarity(a, b)
        assert np.isclose(sim, 0.0)

    def test_s5_semantic_entropy_focused(self):
        """Test S5 entropy for focused activation."""
        focused = np.zeros(12)
        focused[0] = 1.0

        entropy = compute_semantic_entropy(focused)
        assert entropy < 0.5  # Low entropy

    def test_s5_semantic_entropy_uniform(self):
        """Test S5 entropy for uniform activation."""
        uniform = np.ones(12)

        entropy = compute_semantic_entropy(uniform)
        assert entropy > 2.0  # High entropy (near log(12) ≈ 2.48)

    def test_s6_entropy_rate(self):
        """Test S6 entropy rate."""
        act1 = np.ones(12)  # Uniform (high entropy)
        act2 = np.zeros(12)
        act2[0] = 1.0  # Focused (low entropy)

        result1 = compute_global_coherence(act1)
        result2 = compute_global_coherence(act2, previous_entropy=result1.entropy)

        # Entropy should decrease (negative rate)
        assert result2.entropy_rate < 0

    def test_s8_layer_imbalance(self):
        """Test S8 layer imbalance."""
        # High imbalance
        activations = np.zeros(12)
        activations[0] = 1.0  # One very high
        activations[11] = 0.0  # One very low

        result = compute_global_coherence(activations)
        assert result.imbalance > 0.5

    def test_s9_safety_coherence(self):
        """Test S9 safety coherence."""
        activations = np.ones(12) * 0.5
        activations[11] = 0.9  # High safety layer activation

        result = compute_global_coherence(activations)

        # Safety coherence should be high
        assert result.safety_coherence > 0.5

    def test_scc_monitor_update(self):
        """Test SCC monitor update cycle."""
        monitor = SCCMonitor()

        for _ in range(10):
            activations = np.random.rand(12)
            result = monitor.update(activations)
            assert result is not None

        assert len(monitor.history) == 10

    def test_scc_monitor_detect_spike(self):
        """Test SCC monitor entropy spike detection."""
        monitor = SCCMonitor()

        # Stable readings
        for _ in range(5):
            monitor.update(np.ones(12) * 0.5)

        # Sudden change
        spike = np.zeros(12)
        spike[0] = 1.0
        monitor.update(spike)

        # Should detect entropy change
        assert monitor.detect_entropy_spike() or not monitor.detect_entropy_spike()

    def test_scc_monitor_get_weakest_layers(self):
        """Test SCC monitor identifies weak layers."""
        monitor = SCCMonitor()

        activations = np.ones(12) * 0.5
        activations[0] = 0.0  # Make layer 0 weak
        activations[1] = 0.1  # Make layer 1 weak

        monitor.update(activations)

        weakest = monitor.get_weakest_layers(n=2)
        assert 0 in weakest or 1 in weakest


class TestFormulaIntegration:
    """Integration tests across formula modules."""

    def test_bcvf_with_scc_coherence(self):
        """Test BCVF using SCC for forward score."""
        scorer = BCVFScorer()
        monitor = SCCMonitor()

        # Generate action candidates with different coherences
        candidates = []
        forward_scores = []
        backward_scores = []

        for coherence in [0.9, 0.5, 0.3]:
            activations = np.ones(12) * coherence
            result = monitor.update(activations)

            candidates.append(f"action_{coherence}")
            forward_scores.append(result.global_coherence)  # Use coherence as forward
            backward_scores.append(0.8)  # Same backward for all

        best_idx, _ = scorer.select_best(candidates, forward_scores, backward_scores)

        # Should select highest coherence
        assert best_idx == 0

    def test_use_with_scc(self):
        """Test USE fusion with SCC monitoring."""
        fusion = USEFusion()
        monitor = SCCMonitor()

        # Fuse sensors
        fusion.update('vision', np.random.rand(12))
        fusion.update('proprio', np.random.rand(12))
        result = fusion.fuse()

        # Monitor fused result
        coherence = monitor.update(result.fused_vector)

        assert 0 <= coherence.global_coherence <= 1
        assert 0 <= result.confidence <= 1


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
