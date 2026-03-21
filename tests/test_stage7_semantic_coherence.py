"""
Tests for Appendix F Stage 7A — SemanticCoherenceController Integration
========================================================================

Verifies that SemanticCoherenceIntegration correctly aggregates per-layer
S1 scores into S1/S2/S3 signals and feeds them into UnifiedCoherenceController.

Reference: docs/design/CONSCIOUS_GENERATION_DESIGN.md, §F.10.6.1
"""

import pytest
from symbolu.inference.semantic_coherence_integration import (
    SemanticCoherenceIntegration,
    SemanticCoherenceConfig,
)
from symbolu.inference.unified_coherence_controller import (
    UnifiedCoherenceController,
    UnifiedCoherenceConfig,
)


# =========================================================================
# SemanticCoherenceIntegration
# =========================================================================

class TestSemanticCoherenceIntegration:
    """Tests for per-layer S1 collection and S1/S2/S3 computation."""

    def test_no_layers_returns_neutral(self):
        """With no layer data, all signals should be 0.5 (neutral)."""
        sci = SemanticCoherenceIntegration()
        signals = sci.compute_signals()
        assert signals["s1"] == pytest.approx(0.5)
        assert signals["s2"] == pytest.approx(0.5)
        assert signals["s3"] == pytest.approx(0.5)

    def test_single_layer(self):
        """Single layer: S1 = that layer's score, S3 = 0.5 (no coupling)."""
        sci = SemanticCoherenceIntegration(SemanticCoherenceConfig(num_layers=4))
        sci.record_layer(0, 0.8)
        signals = sci.compute_signals()
        assert signals["s1"] == pytest.approx(0.8)
        assert signals["s3"] == pytest.approx(0.5)  # No pairs

    def test_uniform_layers(self):
        """All layers same score: S1 = that score, S3 ≈ 1.0."""
        sci = SemanticCoherenceIntegration(SemanticCoherenceConfig(num_layers=4))
        for i in range(4):
            sci.record_layer(i, 0.7)
        signals = sci.compute_signals()
        assert signals["s1"] == pytest.approx(0.7)
        assert signals["s3"] == pytest.approx(1.0)  # Zero diffs

    def test_varying_layers(self):
        """Different per-layer scores produce meaningful S1/S2/S3."""
        sci = SemanticCoherenceIntegration(SemanticCoherenceConfig(num_layers=4))
        scores = [0.9, 0.7, 0.5, 0.8]
        for i, s in enumerate(scores):
            sci.record_layer(i, s)
        signals = sci.compute_signals()
        assert signals["s1"] == pytest.approx(sum(scores) / 4)
        # S3: adjacent diffs = [0.2, 0.2, 0.3], mean = 0.233, S3 = 1 - 0.233
        assert signals["s3"] == pytest.approx(1.0 - (0.2 + 0.2 + 0.3) / 3, abs=1e-6)

    def test_weighted_aggregation(self):
        """Weighted S1 aggregation weighs later layers more."""
        cfg = SemanticCoherenceConfig(num_layers=3, s1_aggregation="weighted")
        sci = SemanticCoherenceIntegration(cfg)
        sci.record_layer(0, 0.4)  # weight 1
        sci.record_layer(1, 0.6)  # weight 2
        sci.record_layer(2, 0.8)  # weight 3
        signals = sci.compute_signals()
        expected_s1 = (1 * 0.4 + 2 * 0.6 + 3 * 0.8) / (1 + 2 + 3)
        assert signals["s1"] == pytest.approx(expected_s1, abs=1e-6)

    def test_disabled_returns_neutral(self):
        """When disabled, returns neutral signals regardless of data."""
        cfg = SemanticCoherenceConfig(enable=False)
        sci = SemanticCoherenceIntegration(cfg)
        sci.record_layer(0, 0.9)
        signals = sci.compute_signals()
        assert signals["s1"] == pytest.approx(0.5)
        assert signals["s2"] == pytest.approx(0.5)
        assert signals["s3"] == pytest.approx(0.5)

    def test_reset_clears_layer_scores(self):
        """Reset should clear per-token data."""
        sci = SemanticCoherenceIntegration(SemanticCoherenceConfig(num_layers=4))
        sci.record_layer(0, 0.9)
        sci.reset()
        signals = sci.compute_signals()
        assert signals["s1"] == pytest.approx(0.5)

    def test_full_reset_clears_history(self):
        """Full reset clears both layer scores and history."""
        sci = SemanticCoherenceIntegration()
        sci.record_layer(0, 0.8)
        sci.compute_signals()  # Adds to history
        sci.full_reset()
        assert len(sci._history) == 0
        assert all(s is None for s in sci.layer_scores)

    def test_out_of_bounds_layer_ignored(self):
        """Recording to invalid layer index should not crash."""
        sci = SemanticCoherenceIntegration(SemanticCoherenceConfig(num_layers=4))
        sci.record_layer(99, 0.5)  # Out of bounds
        sci.record_layer(-1, 0.5)  # Negative
        signals = sci.compute_signals()
        assert signals["s1"] == pytest.approx(0.5)  # No valid data


# =========================================================================
# Integration with UnifiedCoherenceController (Stage 7A + 7G)
# =========================================================================

class TestSemanticCoherenceUnifiedIntegration:
    """Tests for S1/S2/S3 feeding into UnifiedCoherenceController."""

    def test_s_scores_in_output(self):
        """S1, S2, S3 should appear in controller output."""
        ctrl = UnifiedCoherenceController(UnifiedCoherenceConfig(
            w_s1=0.05, w_s2=0.05, w_s3=0.05, enable_semantic=True,
        ))
        result = ctrl.update(s1=0.8, s2=0.7, s3=0.6)
        assert result["S1"] == pytest.approx(0.8)
        assert result["S2"] == pytest.approx(0.7)
        assert result["S3"] == pytest.approx(0.6)

    def test_s_weights_affect_c_total(self):
        """Non-zero S-weights should change C_total."""
        cfg_without = UnifiedCoherenceConfig(ema_alpha=1.0)
        cfg_with = UnifiedCoherenceConfig(
            w_s1=0.1, w_s2=0.05, w_s3=0.05,
            ema_alpha=1.0, enable_semantic=True,
        )
        ctrl1 = UnifiedCoherenceController(cfg_without)
        ctrl2 = UnifiedCoherenceController(cfg_with)

        r1 = ctrl1.update(c_token=0.5, c_latent=0.5, c_conv=0.5)
        r2 = ctrl2.update(c_token=0.5, c_latent=0.5, c_conv=0.5,
                          s1=0.9, s2=0.9, s3=0.9)
        assert r2["C_total"] > r1["C_total"]

    def test_s_weights_clamped_to_max(self):
        """S-weights should be clamped to s_weight_max."""
        cfg = UnifiedCoherenceConfig(
            w_token=0.3, w_latent=0.2, w_conv=0.2,
            w_s1=0.5,  # Exceeds max
            s_weight_max=0.15,
            ema_alpha=1.0,
            enable_semantic=True,
        )
        ctrl = UnifiedCoherenceController(cfg)
        result = ctrl.update(c_token=0.5, c_latent=0.5, c_conv=0.5, s1=1.0)
        # With clamped w_s1=0.15 and s1=1.0:
        expected_s1_contribution = 0.15 * 1.0
        # Without S contribution
        base = 0.3 * 0.5 + 0.2 * 0.5 + 0.2 * 0.5
        assert result["C_total"] == pytest.approx(base + expected_s1_contribution, abs=1e-6)

    def test_enable_semantic_false(self):
        """When enable_semantic=False, S-weights have no effect."""
        cfg = UnifiedCoherenceConfig(
            w_s1=0.1, w_s2=0.1, w_s3=0.1,
            ema_alpha=1.0,
            enable_semantic=False,
        )
        ctrl = UnifiedCoherenceController(cfg)
        r = ctrl.update(c_token=0.5, c_latent=0.5, c_conv=0.5,
                        s1=1.0, s2=1.0, s3=1.0)
        expected = 0.4 * 0.5 + 0.3 * 0.5 + 0.3 * 0.5
        assert r["C_total"] == pytest.approx(expected, abs=1e-6)

    def test_bounded_introduction(self):
        """Default S-weights are 0.0, so no effect at initialization."""
        ctrl = UnifiedCoherenceController()
        cfg = ctrl.config
        assert cfg.w_s1 == 0.0
        assert cfg.w_s2 == 0.0
        assert cfg.w_s3 == 0.0

    def test_missing_s_scores_default_neutral(self):
        """When S-scores not provided, they default to 0.5."""
        ctrl = UnifiedCoherenceController(UnifiedCoherenceConfig(
            w_s1=0.1, ema_alpha=1.0, enable_semantic=True,
        ))
        result = ctrl.update(c_token=0.5, c_latent=0.5, c_conv=0.5)
        assert result["S1"] == pytest.approx(0.5)
        assert result["S2"] == pytest.approx(0.5)
        assert result["S3"] == pytest.approx(0.5)


# =========================================================================
# End-to-end: SemanticCoherenceIntegration → UnifiedCoherenceController
# =========================================================================

class TestEndToEnd7A:
    """End-to-end integration test for Stage 7A."""

    def test_full_pipeline(self):
        """Layer scores → SemanticCoherenceIntegration → UnifiedCoherenceController."""
        sci = SemanticCoherenceIntegration(SemanticCoherenceConfig(num_layers=4))
        ctrl = UnifiedCoherenceController(UnifiedCoherenceConfig(
            w_s1=0.05, w_s2=0.05, w_s3=0.05,
            ema_alpha=1.0,
            enable_semantic=True,
        ))

        # Simulate per-layer coherence
        for i, score in enumerate([0.8, 0.75, 0.85, 0.7]):
            sci.record_layer(i, score)

        signals = sci.compute_signals()
        result = ctrl.update(
            c_token=0.8, c_latent=0.7, c_conv=0.65,
            s1=signals["s1"], s2=signals["s2"], s3=signals["s3"],
        )

        assert "C_total" in result
        assert result["S1"] == pytest.approx(signals["s1"])
        assert result["S2"] == pytest.approx(signals["s2"])
        assert result["S3"] == pytest.approx(signals["s3"])
        assert result["C_total"] > 0
