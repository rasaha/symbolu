"""
Tests for Appendix F Stage 4 — Unified Coherence Controller.

Validates:
- UnifiedCoherenceConfig defaults and custom values (F.6.5)
- UnifiedCoherenceController aggregation formula (F.6.4)
  - Weighted sum: C_total = w_token * C_token + w_latent * C_latent + w_conv * C_conv
  - EMA smoothing prevents jitter
  - Missing signals default to neutral values
- Bliss history window for C_token (F.6.5)
- Integration with Stage 1 CoherenceAwareDecoder (F.6.6)
- Measurement fields: C_total, C_token, C_latent, C_conversation (F.6.8)
- Reset behavior for new generation sessions
- EMA convergence properties
"""

import math

import pytest

from symbolu.inference.unified_coherence_controller import (
    UnifiedCoherenceController,
    UnifiedCoherenceConfig,
)
from symbolu.inference.coherence_aware_decoder import (
    CoherenceAwareDecoder,
    CoherenceDecoderConfig,
)


# =============================================================================
# UnifiedCoherenceConfig
# =============================================================================


class TestUnifiedCoherenceConfig:

    def test_defaults(self):
        cfg = UnifiedCoherenceConfig()
        assert cfg.w_token == 0.4
        assert cfg.w_latent == 0.3
        assert cfg.w_conv == 0.3
        assert cfg.ema_alpha == 0.1
        assert cfg.history_window == 20

    def test_weights_sum_to_one(self):
        cfg = UnifiedCoherenceConfig()
        assert abs(cfg.w_token + cfg.w_latent + cfg.w_conv - 1.0) < 1e-6

    def test_custom(self):
        cfg = UnifiedCoherenceConfig(w_token=0.5, w_latent=0.25, w_conv=0.25, ema_alpha=0.2)
        assert cfg.w_token == 0.5
        assert cfg.ema_alpha == 0.2


# =============================================================================
# Aggregation Formula (F.6.4)
# =============================================================================


class TestAggregationFormula:
    """Test the weighted sum C_total = w_t*C_t + w_l*C_l + w_c*C_c."""

    def test_all_signals_provided(self):
        ctrl = UnifiedCoherenceController()
        result = ctrl.update(c_token=0.8, c_latent=0.6, c_conv=0.7)
        expected_raw = 0.4 * 0.8 + 0.3 * 0.6 + 0.3 * 0.7  # 0.71
        # EMA: 0.1 * 0.71 + 0.9 * 0.7 = 0.701
        assert abs(result["C_raw"] - expected_raw) < 1e-6
        assert abs(result["C_total"] - (0.1 * expected_raw + 0.9 * 0.7)) < 1e-6

    def test_missing_c_token_uses_default(self):
        ctrl = UnifiedCoherenceController()
        result = ctrl.update(c_token=None, c_latent=0.6, c_conv=0.7)
        # c_token defaults to 0.5 (from c_token property, empty history)
        expected_raw = 0.4 * 0.5 + 0.3 * 0.6 + 0.3 * 0.7
        assert abs(result["C_raw"] - expected_raw) < 1e-6
        assert result["C_token"] == 0.5

    def test_missing_c_latent_uses_default(self):
        ctrl = UnifiedCoherenceController()
        result = ctrl.update(c_token=0.8, c_latent=None, c_conv=0.7)
        expected_raw = 0.4 * 0.8 + 0.3 * 0.5 + 0.3 * 0.7
        assert abs(result["C_raw"] - expected_raw) < 1e-6
        assert result["C_latent"] == 0.5

    def test_missing_c_conv_uses_default(self):
        ctrl = UnifiedCoherenceController()
        result = ctrl.update(c_token=0.8, c_latent=0.6, c_conv=None)
        expected_raw = 0.4 * 0.8 + 0.3 * 0.6 + 0.3 * 0.7
        assert abs(result["C_raw"] - expected_raw) < 1e-6
        assert result["C_conversation"] == 0.7

    def test_all_missing_defaults(self):
        ctrl = UnifiedCoherenceController()
        result = ctrl.update()
        expected_raw = 0.4 * 0.5 + 0.3 * 0.5 + 0.3 * 0.7  # 0.56
        assert abs(result["C_raw"] - expected_raw) < 1e-6

    def test_perfect_coherence(self):
        ctrl = UnifiedCoherenceController()
        result = ctrl.update(c_token=1.0, c_latent=1.0, c_conv=1.0)
        assert abs(result["C_raw"] - 1.0) < 1e-6

    def test_zero_coherence(self):
        ctrl = UnifiedCoherenceController()
        result = ctrl.update(c_token=0.0, c_latent=0.0, c_conv=0.0)
        assert abs(result["C_raw"] - 0.0) < 1e-6

    def test_custom_weights(self):
        cfg = UnifiedCoherenceConfig(w_token=0.6, w_latent=0.2, w_conv=0.2)
        ctrl = UnifiedCoherenceController(cfg)
        result = ctrl.update(c_token=1.0, c_latent=0.0, c_conv=0.0)
        assert abs(result["C_raw"] - 0.6) < 1e-6


# =============================================================================
# EMA Smoothing
# =============================================================================


class TestEMASmoothing:
    """Test exponential moving average behavior."""

    def test_ema_initial_value(self):
        ctrl = UnifiedCoherenceController()
        assert ctrl.c_total_ema == 0.7

    def test_ema_smooths_jitter(self):
        """Rapidly alternating signals produce a smooth EMA."""
        ctrl = UnifiedCoherenceController()
        results = []
        for i in range(20):
            c = 0.9 if i % 2 == 0 else 0.3
            result = ctrl.update(c_token=c, c_latent=c, c_conv=c)
            results.append(result["C_total"])

        # EMA should be smoother than the raw alternation
        raw_range = 0.9 - 0.3
        ema_range = max(results[-10:]) - min(results[-10:])
        assert ema_range < raw_range

    def test_ema_converges_to_stable_signal(self):
        """Constant input signal → EMA converges to that value."""
        ctrl = UnifiedCoherenceController()
        for _ in range(100):
            result = ctrl.update(c_token=0.5, c_latent=0.5, c_conv=0.5)
        # Should converge to 0.5
        assert abs(result["C_total"] - 0.5) < 0.01

    def test_ema_responds_to_change(self):
        """EMA responds gradually to sustained change."""
        ctrl = UnifiedCoherenceController()
        # Start with high coherence
        for _ in range(50):
            ctrl.update(c_token=0.9, c_latent=0.9, c_conv=0.9)
        high = ctrl.c_total_ema

        # Switch to low coherence
        for _ in range(10):
            ctrl.update(c_token=0.1, c_latent=0.1, c_conv=0.1)
        after_drop = ctrl.c_total_ema

        assert after_drop < high
        assert after_drop > 0.1  # EMA hasn't fully converged yet

    def test_custom_ema_alpha(self):
        """Higher ema_alpha → faster response."""
        cfg_fast = UnifiedCoherenceConfig(ema_alpha=0.5)
        cfg_slow = UnifiedCoherenceConfig(ema_alpha=0.05)

        ctrl_fast = UnifiedCoherenceController(cfg_fast)
        ctrl_slow = UnifiedCoherenceController(cfg_slow)

        # Both start at 0.7, apply one update with low signal
        r_fast = ctrl_fast.update(c_token=0.1, c_latent=0.1, c_conv=0.1)
        r_slow = ctrl_slow.update(c_token=0.1, c_latent=0.1, c_conv=0.1)

        # Fast should have moved more toward 0.1
        assert r_fast["C_total"] < r_slow["C_total"]


# =============================================================================
# Bliss History Window
# =============================================================================


class TestBlissHistory:
    """Test rolling Bliss history for C_token computation."""

    def test_empty_history_default(self):
        ctrl = UnifiedCoherenceController()
        assert ctrl.c_token == 0.5

    def test_record_bliss(self):
        ctrl = UnifiedCoherenceController()
        ctrl.record_bliss(0.8)
        ctrl.record_bliss(0.6)
        assert abs(ctrl.c_token - 0.7) < 1e-6

    def test_history_window_cap(self):
        """History is capped at history_window size."""
        cfg = UnifiedCoherenceConfig(history_window=5)
        ctrl = UnifiedCoherenceController(cfg)
        for i in range(10):
            ctrl.record_bliss(float(i) / 10)
        assert len(ctrl.bliss_history) == 5
        # Should contain last 5 values: 0.5, 0.6, 0.7, 0.8, 0.9
        expected_mean = (0.5 + 0.6 + 0.7 + 0.8 + 0.9) / 5
        assert abs(ctrl.c_token - expected_mean) < 1e-6

    def test_c_token_used_when_not_provided(self):
        """When c_token=None, update uses bliss_history mean."""
        ctrl = UnifiedCoherenceController()
        ctrl.record_bliss(0.9)
        ctrl.record_bliss(0.9)
        result = ctrl.update(c_token=None, c_latent=0.5, c_conv=0.5)
        assert result["C_token"] == 0.9

    def test_explicit_c_token_overrides_history(self):
        """Explicit c_token overrides bliss_history mean."""
        ctrl = UnifiedCoherenceController()
        ctrl.record_bliss(0.9)
        result = ctrl.update(c_token=0.1, c_latent=0.5, c_conv=0.5)
        assert result["C_token"] == 0.1


# =============================================================================
# Reset
# =============================================================================


class TestReset:

    def test_reset_clears_state(self):
        ctrl = UnifiedCoherenceController()
        ctrl.record_bliss(0.5)
        ctrl.update(c_token=0.3, c_latent=0.3, c_conv=0.3)
        ctrl.reset()
        assert ctrl.c_total_ema == 0.7
        assert len(ctrl.bliss_history) == 0

    def test_reset_restores_initial_behavior(self):
        ctrl = UnifiedCoherenceController()
        # Drive EMA down
        for _ in range(100):
            ctrl.update(c_token=0.1, c_latent=0.1, c_conv=0.1)
        ctrl.reset()
        # Should behave like fresh controller
        result = ctrl.update(c_token=0.8, c_latent=0.8, c_conv=0.8)
        ctrl2 = UnifiedCoherenceController()
        result2 = ctrl2.update(c_token=0.8, c_latent=0.8, c_conv=0.8)
        assert abs(result["C_total"] - result2["C_total"]) < 1e-6


# =============================================================================
# Integration with Stage 1 (F.6.6)
# =============================================================================


class TestStage1Integration:
    """Verify unified signal feeds into CoherenceAwareDecoder correctly."""

    def test_unified_signal_triggers_dampening(self):
        """Low unified coherence triggers Stage 1 temperature dampening."""
        ctrl = UnifiedCoherenceController()
        decoder = CoherenceAwareDecoder()

        # Drive EMA low
        for _ in range(50):
            ctrl.update(c_token=0.1, c_latent=0.1, c_conv=0.1)

        result = ctrl.update(c_token=0.1, c_latent=0.1, c_conv=0.1)
        c_total = result["C_total"]
        assert c_total < 0.4  # Should be below threshold

        policy = decoder.adjust_policy(coherence=c_total, base_temperature=1.0, base_top_p=0.9)
        assert policy["temperature"] < 1.0  # Dampened

    def test_unified_signal_no_dampening_when_high(self):
        """High unified coherence means no dampening."""
        ctrl = UnifiedCoherenceController()
        decoder = CoherenceAwareDecoder()

        # Drive EMA high
        for _ in range(50):
            ctrl.update(c_token=0.9, c_latent=0.9, c_conv=0.9)

        result = ctrl.update(c_token=0.9, c_latent=0.9, c_conv=0.9)
        c_total = result["C_total"]
        assert c_total > 0.4

        policy = decoder.adjust_policy(coherence=c_total, base_temperature=1.0, base_top_p=0.9)
        assert policy["temperature"] == 1.0  # No dampening

    def test_unified_replaces_simple_scalar(self):
        """Unified signal should produce different policy than raw scalar."""
        decoder = CoherenceAwareDecoder()

        # Simple scalar: 0.3 → dampening
        p1 = decoder.adjust_policy(coherence=0.3, base_temperature=1.0, base_top_p=0.9)

        # Unified with EMA (starts at 0.7, one update with 0.3 raw)
        ctrl = UnifiedCoherenceController()
        result = ctrl.update(c_token=0.3, c_latent=0.3, c_conv=0.3)
        c_total = result["C_total"]

        p2 = decoder.adjust_policy(coherence=c_total, base_temperature=1.0, base_top_p=0.9)

        # EMA makes unified signal higher than raw 0.3
        assert c_total > 0.3
        # So unified may not trigger dampening (EMA smoothed)
        assert p2["temperature"] >= p1["temperature"]


# =============================================================================
# Output Fields (F.6.8)
# =============================================================================


class TestOutputFields:

    def test_all_fields_present(self):
        ctrl = UnifiedCoherenceController()
        result = ctrl.update(c_token=0.8, c_latent=0.6, c_conv=0.7)
        assert "C_total" in result
        assert "C_token" in result
        assert "C_latent" in result
        assert "C_conversation" in result
        assert "C_raw" in result

    def test_field_types(self):
        ctrl = UnifiedCoherenceController()
        result = ctrl.update(c_token=0.8, c_latent=0.6, c_conv=0.7)
        for key in ["C_total", "C_token", "C_latent", "C_conversation", "C_raw"]:
            assert isinstance(result[key], float), f"{key} is not float"


# =============================================================================
# Edge Cases
# =============================================================================


class TestEdgeCases:

    def test_extreme_low_signals(self):
        ctrl = UnifiedCoherenceController()
        result = ctrl.update(c_token=0.0, c_latent=0.0, c_conv=0.0)
        assert result["C_raw"] == 0.0
        assert result["C_total"] >= 0.0  # EMA keeps it non-negative

    def test_extreme_high_signals(self):
        ctrl = UnifiedCoherenceController()
        result = ctrl.update(c_token=1.0, c_latent=1.0, c_conv=1.0)
        assert abs(result["C_raw"] - 1.0) < 1e-6

    def test_many_updates_stable(self):
        """Controller remains stable after many updates."""
        ctrl = UnifiedCoherenceController()
        for _ in range(10000):
            ctrl.update(c_token=0.6, c_latent=0.6, c_conv=0.6)
        assert abs(ctrl.c_total_ema - 0.6) < 0.01
        assert not math.isnan(ctrl.c_total_ema)
        assert not math.isinf(ctrl.c_total_ema)

    def test_negative_inputs_handled(self):
        """Negative coherence values don't crash."""
        ctrl = UnifiedCoherenceController()
        result = ctrl.update(c_token=-0.5, c_latent=-0.3, c_conv=-0.1)
        assert not math.isnan(result["C_total"])

    def test_values_above_one_handled(self):
        """Values > 1.0 don't crash."""
        ctrl = UnifiedCoherenceController()
        result = ctrl.update(c_token=1.5, c_latent=1.2, c_conv=1.0)
        assert not math.isnan(result["C_total"])
