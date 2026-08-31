"""
Tests for Appendix F Stage 7G — Convergence Metric Formula Alignment
=====================================================================

Verifies that the UnifiedCoherenceController correctly computes
C_agreement = 1 - |C_token - C_latent| and integrates it into
the four-term aggregation formula.

Reference: Project_documentation/repository/docs/design/CONSCIOUS_GENERATION_DESIGN.md, §F.10.6.7
"""

import pytest
from symbolu.inference.unified_coherence_controller import (
    UnifiedCoherenceController,
    UnifiedCoherenceConfig,
)


# =========================================================================
# C_agreement computation
# =========================================================================

class TestCAgreement:
    """Tests for the C_agreement = 1 - |C_token - C_latent| formula."""

    def test_perfect_agreement(self):
        """When C_token == C_latent, C_agreement should be 1.0."""
        ctrl = UnifiedCoherenceController(UnifiedCoherenceConfig(
            w_agreement=0.2, enable_agreement=True,
        ))
        result = ctrl.update(c_token=0.8, c_latent=0.8, c_conv=0.7)
        assert result["C_agreement"] == pytest.approx(1.0)

    def test_complete_disagreement(self):
        """When C_token=0 and C_latent=1, C_agreement should be 0.0."""
        ctrl = UnifiedCoherenceController(UnifiedCoherenceConfig(
            w_agreement=0.2, enable_agreement=True,
        ))
        result = ctrl.update(c_token=0.0, c_latent=1.0, c_conv=0.7)
        assert result["C_agreement"] == pytest.approx(0.0)

    def test_partial_agreement(self):
        """C_agreement with partial token-latent gap."""
        ctrl = UnifiedCoherenceController(UnifiedCoherenceConfig(
            w_agreement=0.2, enable_agreement=True,
        ))
        result = ctrl.update(c_token=0.9, c_latent=0.6, c_conv=0.7)
        assert result["C_agreement"] == pytest.approx(0.7)

    def test_symmetric(self):
        """C_agreement should be symmetric: f(a,b) == f(b,a)."""
        ctrl = UnifiedCoherenceController(UnifiedCoherenceConfig(
            w_agreement=0.2, enable_agreement=True,
        ))
        r1 = ctrl.update(c_token=0.3, c_latent=0.8)
        ctrl.reset()
        r2 = ctrl.update(c_token=0.8, c_latent=0.3)
        assert r1["C_agreement"] == pytest.approx(r2["C_agreement"])

    def test_agreement_in_output(self):
        """C_agreement should always be present in output dict."""
        ctrl = UnifiedCoherenceController()
        result = ctrl.update(c_token=0.5, c_latent=0.5)
        assert "C_agreement" in result


# =========================================================================
# Four-term formula with C_agreement
# =========================================================================

class TestFourTermFormula:
    """Tests for the extended C_total formula with C_agreement."""

    def test_rebalanced_weights(self):
        """With spec-recommended weights (0.30, 0.25, 0.20, 0.25)."""
        cfg = UnifiedCoherenceConfig(
            w_token=0.30, w_latent=0.25, w_agreement=0.20, w_conv=0.25,
            ema_alpha=1.0,  # No smoothing for precise testing
            enable_agreement=True,
        )
        ctrl = UnifiedCoherenceController(cfg)
        result = ctrl.update(c_token=0.8, c_latent=0.6, c_conv=0.7)

        c_agreement = 1.0 - abs(0.8 - 0.6)  # = 0.8
        expected = 0.30 * 0.8 + 0.25 * 0.6 + 0.20 * 0.8 + 0.25 * 0.7
        assert result["C_total"] == pytest.approx(expected, abs=1e-6)

    def test_agreement_weight_zero_matches_stage4(self):
        """When w_agreement=0, should match Stage 4 three-term formula."""
        cfg_stage4 = UnifiedCoherenceConfig(
            w_token=0.4, w_latent=0.3, w_conv=0.3, w_agreement=0.0,
            ema_alpha=1.0,
        )
        ctrl = UnifiedCoherenceController(cfg_stage4)
        result = ctrl.update(c_token=0.8, c_latent=0.6, c_conv=0.7)
        expected = 0.4 * 0.8 + 0.3 * 0.6 + 0.3 * 0.7
        assert result["C_total"] == pytest.approx(expected, abs=1e-6)

    def test_enable_agreement_false(self):
        """When enable_agreement=False, w_agreement is not used."""
        cfg = UnifiedCoherenceConfig(
            w_token=0.4, w_latent=0.3, w_conv=0.3,
            w_agreement=0.2,  # Non-zero but disabled
            ema_alpha=1.0,
            enable_agreement=False,
        )
        ctrl = UnifiedCoherenceController(cfg)
        result = ctrl.update(c_token=0.8, c_latent=0.6, c_conv=0.7)
        expected = 0.4 * 0.8 + 0.3 * 0.6 + 0.3 * 0.7
        assert result["C_total"] == pytest.approx(expected, abs=1e-6)

    def test_agreement_drops_during_incoherence(self):
        """C_agreement should drop when token and latent diverge."""
        ctrl = UnifiedCoherenceController(UnifiedCoherenceConfig(
            w_agreement=0.2, ema_alpha=1.0, enable_agreement=True,
        ))
        # Coherent
        r1 = ctrl.update(c_token=0.8, c_latent=0.8)
        ctrl.reset()
        # Incoherent
        r2 = ctrl.update(c_token=0.9, c_latent=0.2)
        assert r2["C_agreement"] < r1["C_agreement"]
        assert r2["C_agreement"] == pytest.approx(0.3)


# =========================================================================
# Backward compatibility (null integration test)
# =========================================================================

class TestBackwardCompatibility7G:
    """Verify Stage 4 behavior is preserved when 7G is disabled."""

    def test_default_config_backward_compatible(self):
        """Default config has w_agreement=0, so behaves like Stage 4."""
        cfg = UnifiedCoherenceConfig()
        assert cfg.w_agreement == 0.0

    def test_output_fields_superset(self):
        """Stage 7G adds C_agreement but preserves all Stage 4 fields."""
        ctrl = UnifiedCoherenceController()
        result = ctrl.update(c_token=0.5, c_latent=0.5, c_conv=0.5)
        # Stage 4 fields
        for key in ["C_total", "C_token", "C_latent", "C_conversation", "C_raw"]:
            assert key in result
        # Stage 7G field
        assert "C_agreement" in result

    def test_ema_still_works(self):
        """EMA smoothing should work correctly with C_agreement."""
        ctrl = UnifiedCoherenceController(UnifiedCoherenceConfig(
            w_agreement=0.2, ema_alpha=0.5, enable_agreement=True,
        ))
        r1 = ctrl.update(c_token=1.0, c_latent=1.0, c_conv=1.0)
        r2 = ctrl.update(c_token=0.0, c_latent=0.0, c_conv=0.0)
        # Second update should be smoothed, not jump to 0
        assert r2["C_total"] > 0.0
