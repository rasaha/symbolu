"""
Tests for Appendix F Stage 7B — Adaptive Diagnostic Controller
================================================================

Verifies that AdaptiveDiagnosticController correctly monitors diagnostic
signals and triggers appropriate adaptive responses.

Reference: docs/design/CONSCIOUS_GENERATION_DESIGN.md, §F.10.6.2
"""

import pytest
from symbolu.training.conscious_generation.diagnostics.adaptive_diagnostic_controller import (
    AdaptiveDiagnosticController,
    AdaptiveDiagnosticConfig,
    DiagnosticSignals,
    AdaptiveResponse,
)


# =========================================================================
# DiagnosticSignals dataclass
# =========================================================================

class TestDiagnosticSignals:
    """Tests for the structured diagnostic signals."""

    def test_default_values(self):
        """Default signals should indicate healthy state."""
        signals = DiagnosticSignals()
        assert signals.projector_drift == 0.0
        assert signals.adapter_gate_magnitude == 0.0
        assert signals.primitive_cache_shift == 0.0
        assert signals.component_norm_ratio == 1.0
        assert signals.step == 0

    def test_custom_values(self):
        """Custom signal values should be stored correctly."""
        signals = DiagnosticSignals(
            projector_drift=0.08,
            adapter_gate_magnitude=2.5,
            primitive_cache_shift=0.12,
            component_norm_ratio=4.0,
            step=1000,
        )
        assert signals.projector_drift == 0.08
        assert signals.step == 1000


# =========================================================================
# Threshold checking
# =========================================================================

class TestThresholdChecking:
    """Tests for threshold-based adaptive responses."""

    def test_healthy_signals_no_responses(self):
        """Healthy signals should trigger no adaptive responses."""
        ctrl = AdaptiveDiagnosticController()
        signals = DiagnosticSignals(
            projector_drift=0.03,
            adapter_gate_magnitude=1.5,
            primitive_cache_shift=0.05,
            component_norm_ratio=2.0,
        )
        responses = ctrl.check(signals)
        assert len(responses) == 0

    def test_projector_drift_triggers_lr_reduction(self):
        """High projector drift should trigger LR reduction."""
        ctrl = AdaptiveDiagnosticController()
        signals = DiagnosticSignals(projector_drift=0.08)
        responses = ctrl.check(signals)
        assert any(r.action == "reduce_projector_lr" for r in responses)
        assert any(r.signal_name == "projector_drift" for r in responses)

    def test_adapter_gate_triggers_clipping(self):
        """High adapter gate magnitude should trigger clipping."""
        ctrl = AdaptiveDiagnosticController()
        signals = DiagnosticSignals(adapter_gate_magnitude=2.5)
        responses = ctrl.check(signals)
        assert any(r.action == "clip_adapter_gate" for r in responses)

    def test_cache_shift_triggers_recomputation(self):
        """High primitive cache shift should trigger recomputation."""
        ctrl = AdaptiveDiagnosticController()
        signals = DiagnosticSignals(primitive_cache_shift=0.15)
        responses = ctrl.check(signals)
        assert any(r.action == "recompute_cache" for r in responses)

    def test_norm_ratio_triggers_normalization(self):
        """High component norm ratio should trigger normalization."""
        ctrl = AdaptiveDiagnosticController()
        signals = DiagnosticSignals(component_norm_ratio=4.0)
        responses = ctrl.check(signals)
        assert any(r.action == "normalize_components" for r in responses)

    def test_extreme_norm_ratio_is_critical(self):
        """Very high norm ratio should have 'critical' severity."""
        ctrl = AdaptiveDiagnosticController()
        signals = DiagnosticSignals(component_norm_ratio=15.0)
        responses = ctrl.check(signals)
        norm_responses = [r for r in responses if r.action == "normalize_components"]
        assert len(norm_responses) == 1
        assert norm_responses[0].severity == "critical"

    def test_multiple_thresholds_crossed(self):
        """Multiple threshold violations should produce multiple responses."""
        ctrl = AdaptiveDiagnosticController()
        signals = DiagnosticSignals(
            projector_drift=0.08,
            adapter_gate_magnitude=3.0,
            primitive_cache_shift=0.2,
            component_norm_ratio=5.0,
        )
        responses = ctrl.check(signals)
        assert len(responses) == 4

    def test_at_exact_threshold_no_response(self):
        """Values exactly at threshold should NOT trigger response."""
        ctrl = AdaptiveDiagnosticController()
        signals = DiagnosticSignals(
            projector_drift=0.05,  # Exactly at threshold
            adapter_gate_magnitude=2.0,  # Exactly at threshold
        )
        responses = ctrl.check(signals)
        assert len(responses) == 0


# =========================================================================
# Kill switch (enable=False)
# =========================================================================

class TestKillSwitch7B:
    """Tests for the enable/disable kill switch."""

    def test_disabled_no_responses(self):
        """When disabled, no responses should be generated."""
        cfg = AdaptiveDiagnosticConfig(enable=False)
        ctrl = AdaptiveDiagnosticController(cfg)
        signals = DiagnosticSignals(
            projector_drift=1.0,
            adapter_gate_magnitude=10.0,
        )
        responses = ctrl.check(signals)
        assert len(responses) == 0

    def test_disabled_still_records_history(self):
        """History should still be recorded when disabled."""
        cfg = AdaptiveDiagnosticConfig(enable=False)
        ctrl = AdaptiveDiagnosticController(cfg)
        ctrl.check(DiagnosticSignals(step=1))
        ctrl.check(DiagnosticSignals(step=2))
        assert len(ctrl.history) == 2


# =========================================================================
# Trend analysis
# =========================================================================

class TestTrendAnalysis:
    """Tests for trend monitoring over diagnostic history."""

    def test_empty_history_healthy(self):
        """Empty history should report healthy."""
        ctrl = AdaptiveDiagnosticController()
        trend = ctrl.get_trend()
        assert trend["healthy"] is True
        assert trend["projector_drift_trend"] == "stable"

    def test_increasing_drift(self):
        """Increasing drift should be detected."""
        ctrl = AdaptiveDiagnosticController()
        for i in range(10):
            ctrl.check(DiagnosticSignals(projector_drift=0.01 * (i + 1)))
        trend = ctrl.get_trend()
        assert trend["projector_drift_trend"] == "increasing"

    def test_decreasing_drift(self):
        """Decreasing drift should be detected."""
        ctrl = AdaptiveDiagnosticController()
        for i in range(10):
            ctrl.check(DiagnosticSignals(projector_drift=0.1 - 0.008 * i))
        trend = ctrl.get_trend()
        assert trend["projector_drift_trend"] == "decreasing"

    def test_stable_drift(self):
        """Stable drift should be detected."""
        ctrl = AdaptiveDiagnosticController()
        for _ in range(10):
            ctrl.check(DiagnosticSignals(projector_drift=0.03))
        trend = ctrl.get_trend()
        assert trend["projector_drift_trend"] == "stable"

    def test_response_counts_tracked(self):
        """Response counts should accumulate over time."""
        ctrl = AdaptiveDiagnosticController()
        ctrl.check(DiagnosticSignals(projector_drift=0.08))
        ctrl.check(DiagnosticSignals(projector_drift=0.08))
        trend = ctrl.get_trend()
        assert trend["response_counts"]["reduce_projector_lr"] == 2

    def test_mean_gate_magnitude(self):
        """Mean gate magnitude should be computed correctly."""
        ctrl = AdaptiveDiagnosticController()
        ctrl.check(DiagnosticSignals(adapter_gate_magnitude=1.0))
        ctrl.check(DiagnosticSignals(adapter_gate_magnitude=3.0))
        trend = ctrl.get_trend()
        assert trend["mean_gate_magnitude"] == pytest.approx(2.0)


# =========================================================================
# Custom configuration
# =========================================================================

class TestCustomConfig7B:
    """Tests for custom threshold configuration."""

    def test_custom_thresholds(self):
        """Custom thresholds should be respected."""
        cfg = AdaptiveDiagnosticConfig(
            projector_drift_threshold=0.01,
            adapter_gate_max=1.0,
        )
        ctrl = AdaptiveDiagnosticController(cfg)
        # These would be healthy with defaults but trigger with custom
        signals = DiagnosticSignals(
            projector_drift=0.02,
            adapter_gate_magnitude=1.5,
        )
        responses = ctrl.check(signals)
        assert len(responses) == 2

    def test_history_window_respected(self):
        """History should be capped at history_window."""
        cfg = AdaptiveDiagnosticConfig(history_window=5)
        ctrl = AdaptiveDiagnosticController(cfg)
        for i in range(10):
            ctrl.check(DiagnosticSignals(step=i))
        assert len(ctrl.history) == 5
        assert ctrl.history[0].step == 5  # Oldest retained

    def test_reset(self):
        """Reset should clear all state."""
        ctrl = AdaptiveDiagnosticController()
        ctrl.check(DiagnosticSignals(projector_drift=0.08))
        ctrl.reset()
        assert len(ctrl.history) == 0
        assert ctrl._response_counts["reduce_projector_lr"] == 0
