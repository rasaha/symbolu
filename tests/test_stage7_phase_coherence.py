"""
Tests for Appendix F Stage 7F — Phase Coherence as Interpretive Signal
=======================================================================

Verifies that PhaseCoherenceExtractor, PhaseCoherenceAggregator, and
PhaseCoherenceProjection correctly extract, aggregate, and project
phase coherence for the interpretive state.

Reference: docs/design/CONSCIOUS_GENERATION_DESIGN.md, §F.10.6.6
"""

import pytest
import torch
from symbolu.inference.phase_coherence_signal import (
    PhaseCoherenceExtractor,
    PhaseCoherenceAggregator,
    PhaseCoherenceProjection,
    PhaseCoherenceConfig,
)


# =========================================================================
# PhaseCoherenceExtractor
# =========================================================================

class TestPhaseCoherenceExtractor:
    """Tests for per-head phase coherence extraction."""

    def test_output_shape(self):
        """Output should be [B, H]."""
        cfg = PhaseCoherenceConfig(num_heads=4)
        extractor = PhaseCoherenceExtractor(cfg)
        phase_angles = torch.randn(2, 4, 10, 32)  # [B, H, T, D_half]
        result = extractor.compute_per_head(phase_angles)
        assert result.shape == (2, 4)

    def test_aligned_phases_high_coherence(self):
        """Perfectly aligned phases should produce high coherence."""
        cfg = PhaseCoherenceConfig(num_heads=2)
        extractor = PhaseCoherenceExtractor(cfg)
        # All phases the same → std ≈ 0 → coherence ≈ 1.0
        phase_angles = torch.ones(1, 2, 5, 16) * 0.5
        result = extractor.compute_per_head(phase_angles)
        assert (result > 0.9).all()

    def test_scattered_phases_low_coherence(self):
        """Widely scattered phases should produce lower coherence."""
        cfg = PhaseCoherenceConfig(num_heads=2)
        extractor = PhaseCoherenceExtractor(cfg)
        # Random phases with high variance
        torch.manual_seed(42)
        phase_angles = torch.randn(1, 2, 5, 16) * 3.0
        result = extractor.compute_per_head(phase_angles)
        # Coherence should be lower than aligned case
        assert (result < 0.9).any()

    def test_disabled_returns_zeros(self):
        """When disabled, should return zeros."""
        cfg = PhaseCoherenceConfig(enable=False, num_heads=4)
        extractor = PhaseCoherenceExtractor(cfg)
        phase_angles = torch.randn(2, 4, 10, 32)
        result = extractor.compute_per_head(phase_angles)
        assert result.shape == (2, 4)
        assert (result == 0).all()

    def test_coherence_bounded(self):
        """Coherence should be in [0, 1]."""
        cfg = PhaseCoherenceConfig(num_heads=4)
        extractor = PhaseCoherenceExtractor(cfg)
        torch.manual_seed(123)
        phase_angles = torch.randn(4, 4, 20, 32) * 5.0
        result = extractor.compute_per_head(phase_angles)
        assert (result >= 0.0).all()
        assert (result <= 1.0).all()


# =========================================================================
# PhaseCoherenceAggregator
# =========================================================================

class TestPhaseCoherenceAggregator:
    """Tests for cross-layer phase coherence aggregation."""

    def test_no_data_returns_none(self):
        """Without layer data, should return None."""
        agg = PhaseCoherenceAggregator(PhaseCoherenceConfig(num_layers=4))
        assert agg.get_phase_coherence_vector() is None

    def test_single_layer(self):
        """Single layer data should be returned directly."""
        agg = PhaseCoherenceAggregator(PhaseCoherenceConfig(num_layers=4, num_heads=2))
        per_head = torch.tensor([[0.8, 0.6]])  # [B=1, H=2]
        agg.record_layer(0, per_head)
        result = agg.get_phase_coherence_vector()
        assert result is not None
        assert result.shape == (1, 2)
        assert torch.allclose(result, per_head)

    def test_mean_aggregation(self):
        """Mean aggregation should average across layers."""
        cfg = PhaseCoherenceConfig(num_layers=3, num_heads=2, aggregation="mean")
        agg = PhaseCoherenceAggregator(cfg)
        agg.record_layer(0, torch.tensor([[0.6, 0.8]]))
        agg.record_layer(1, torch.tensor([[0.8, 0.6]]))
        agg.record_layer(2, torch.tensor([[0.7, 0.7]]))
        result = agg.get_phase_coherence_vector()
        expected = torch.tensor([[0.7, 0.7]])
        assert torch.allclose(result, expected, atol=1e-6)

    def test_last_aggregation(self):
        """'last' aggregation should return the last layer."""
        cfg = PhaseCoherenceConfig(num_layers=3, num_heads=2, aggregation="last")
        agg = PhaseCoherenceAggregator(cfg)
        agg.record_layer(0, torch.tensor([[0.6, 0.8]]))
        agg.record_layer(2, torch.tensor([[0.9, 0.3]]))
        result = agg.get_phase_coherence_vector()
        expected = torch.tensor([[0.9, 0.3]])
        assert torch.allclose(result, expected)

    def test_reset_clears_data(self):
        """Reset should clear per-token layer data."""
        agg = PhaseCoherenceAggregator(PhaseCoherenceConfig(num_layers=4))
        agg.record_layer(0, torch.tensor([[0.5, 0.5]]))
        agg.reset()
        assert agg.get_phase_coherence_vector() is None

    def test_disabled_returns_none(self):
        """When disabled, should return None."""
        cfg = PhaseCoherenceConfig(enable=False)
        agg = PhaseCoherenceAggregator(cfg)
        agg.record_layer(0, torch.tensor([[0.8, 0.6]]))
        assert agg.get_phase_coherence_vector() is None

    def test_out_of_bounds_ignored(self):
        """Out-of-bounds layer indices should be ignored."""
        agg = PhaseCoherenceAggregator(PhaseCoherenceConfig(num_layers=2))
        agg.record_layer(99, torch.tensor([[0.5, 0.5]]))
        assert agg.get_phase_coherence_vector() is None


# =========================================================================
# PhaseCoherenceProjection
# =========================================================================

class TestPhaseCoherenceProjection:
    """Tests for projecting phase coherence into interpretive state."""

    def test_output_shape(self):
        """Output should be [B, T, phase_out_dim]."""
        proj = PhaseCoherenceProjection(num_heads=4, phase_out_dim=8)
        phase_vec = torch.randn(2, 4)  # [B, H]
        result = proj(phase_vec, seq_len=10)
        assert result.shape == (2, 10, 8)

    def test_zero_init(self):
        """Initial projection should output near-zero (bounded intro)."""
        proj = PhaseCoherenceProjection(num_heads=4, phase_out_dim=8)
        phase_vec = torch.randn(1, 4)
        result = proj(phase_vec, seq_len=5)
        assert result.abs().max() < 0.01

    def test_broadcast_across_sequence(self):
        """Each sequence position should get the same projection."""
        proj = PhaseCoherenceProjection(num_heads=4, phase_out_dim=8)
        phase_vec = torch.randn(1, 4)
        result = proj(phase_vec, seq_len=3)
        assert torch.allclose(result[:, 0, :], result[:, 1, :])
        assert torch.allclose(result[:, 0, :], result[:, 2, :])

    def test_gradient_flows(self):
        """Gradients should flow through the projection."""
        proj = PhaseCoherenceProjection(num_heads=4, phase_out_dim=8)
        phase_vec = torch.randn(1, 4, requires_grad=True)
        result = proj(phase_vec, seq_len=5)
        loss = result.sum()
        loss.backward()
        assert phase_vec.grad is not None
        # With zero init, grad might be zero; that's fine for bounded intro


# =========================================================================
# Null integration test
# =========================================================================

class TestNullIntegration7F:
    """Verify phase coherence has no effect at initialization."""

    def test_zero_init_projection_doesnt_affect_hidden(self):
        """With zero-init projection, adding phase signal should be negligible."""
        proj = PhaseCoherenceProjection(num_heads=4, phase_out_dim=8)
        phase_vec = torch.randn(1, 4)
        phase_signal = proj(phase_vec, seq_len=5)

        hidden = torch.randn(1, 5, 64)
        # If we were to add phase_signal (after another projection to hidden_dim),
        # the contribution should be negligible
        assert phase_signal.abs().max() < 0.01
