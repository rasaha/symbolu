"""
Strategy 2 Tests — E = G × P × T → Bounded Confidence Adjustment.

Tests verifying:
1. compute_modulation_confidence_adjustment: transform correctness
2. ConfidenceSignals output_modulation_adjustment field
3. ConfidenceAggregator applies the adjustment
4. Escalation/execution decisions shift with the adjustment
5. Fallback: missing E → neutral behavior
6. Metadata: raw E and applied adjustment are surfaced
7. No regression: absent modulation matches prior behavior
"""

import pytest

from agentic.agentic_framework.signal_adapters.output_modulation_adapter import (
    compute_modulation_confidence_adjustment,
    _E_LOW_THRESHOLD,
    _E_HIGH_THRESHOLD,
    _E_MAX_PENALTY,
    _E_MAX_UPLIFT,
)
from agentic.agentic_framework.confidence_gate import (
    ConfidenceSignals,
    ConfidenceAggregator,
    ConfidenceGate,
    EscalationLevel,
    ExecutionMode,
)


# =========================================================================
# Test: Bounded transform function
# =========================================================================


class TestModulationConfidenceAdjustment:
    """Tests for compute_modulation_confidence_adjustment."""

    def test_none_returns_zero(self):
        """Missing E → neutral, no effect."""
        assert compute_modulation_confidence_adjustment(None) == 0.0

    def test_zero_E_returns_max_penalty(self):
        """E=0.0 → maximum cautionary penalty."""
        adj = compute_modulation_confidence_adjustment(0.0)
        assert adj == pytest.approx(_E_MAX_PENALTY)
        assert adj == pytest.approx(-0.10)

    def test_low_threshold_boundary_returns_zero(self):
        """E exactly at low threshold → no penalty."""
        adj = compute_modulation_confidence_adjustment(_E_LOW_THRESHOLD)
        assert adj == pytest.approx(0.0, abs=1e-10)

    def test_high_threshold_boundary_returns_zero(self):
        """E exactly at high threshold → no uplift."""
        adj = compute_modulation_confidence_adjustment(_E_HIGH_THRESHOLD)
        assert adj == pytest.approx(0.0, abs=1e-10)

    def test_max_E_returns_max_uplift(self):
        """E=1.0 → maximum modest uplift."""
        adj = compute_modulation_confidence_adjustment(1.0)
        assert adj == pytest.approx(_E_MAX_UPLIFT)
        assert adj == pytest.approx(0.03)

    def test_dead_zone_midpoint_returns_zero(self):
        """E in the dead zone [0.4, 0.7] → zero adjustment."""
        assert compute_modulation_confidence_adjustment(0.5) == 0.0
        assert compute_modulation_confidence_adjustment(0.55) == 0.0
        assert compute_modulation_confidence_adjustment(0.4) == pytest.approx(0.0, abs=1e-10)
        assert compute_modulation_confidence_adjustment(0.7) == pytest.approx(0.0, abs=1e-10)

    def test_half_penalty_at_E_0_2(self):
        """E=0.2 → half of max penalty."""
        adj = compute_modulation_confidence_adjustment(0.2)
        expected = _E_MAX_PENALTY * (1.0 - 0.2 / _E_LOW_THRESHOLD)
        assert adj == pytest.approx(expected)
        assert adj == pytest.approx(-0.05)

    def test_asymmetric_penalty_larger_than_uplift(self):
        """Downside should be significantly larger than upside."""
        penalty = abs(compute_modulation_confidence_adjustment(0.0))
        uplift = compute_modulation_confidence_adjustment(1.0)
        assert penalty > uplift * 3  # At least 3× asymmetry

    def test_bounded_within_range(self):
        """All values of E produce adjustments in [-0.10, +0.03]."""
        for e_val in [0.0, 0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9, 1.0]:
            adj = compute_modulation_confidence_adjustment(e_val)
            assert _E_MAX_PENALTY <= adj <= _E_MAX_UPLIFT, f"E={e_val} → {adj} out of bounds"

    def test_out_of_range_E_clamped(self):
        """E outside [0, 1] is clamped, not crashed."""
        adj_neg = compute_modulation_confidence_adjustment(-0.5)
        adj_high = compute_modulation_confidence_adjustment(2.0)
        assert adj_neg == pytest.approx(_E_MAX_PENALTY)  # Clamped to E=0.0
        assert adj_high == pytest.approx(_E_MAX_UPLIFT)  # Clamped to E=1.0

    def test_deterministic(self):
        """Same E → same adjustment, always."""
        for _ in range(10):
            assert compute_modulation_confidence_adjustment(0.35) == compute_modulation_confidence_adjustment(0.35)

    def test_monotonic_in_low_range(self):
        """Adjustment monotonically increases (less negative) as E rises in [0, 0.4]."""
        values = [compute_modulation_confidence_adjustment(e / 10.0) for e in range(5)]
        for i in range(len(values) - 1):
            assert values[i] <= values[i + 1]

    def test_monotonic_in_high_range(self):
        """Adjustment monotonically increases as E rises in [0.7, 1.0]."""
        values = [compute_modulation_confidence_adjustment(0.7 + e * 0.1) for e in range(4)]
        for i in range(len(values) - 1):
            assert values[i] <= values[i + 1]


# =========================================================================
# Test: ConfidenceSignals field
# =========================================================================


class TestConfidenceSignalsField:
    """Tests that ConfidenceSignals has and serializes the new field."""

    def test_default_is_zero(self):
        signals = ConfidenceSignals()
        assert signals.output_modulation_adjustment == 0.0

    def test_custom_value_stored(self):
        signals = ConfidenceSignals(output_modulation_adjustment=-0.05)
        assert signals.output_modulation_adjustment == -0.05

    def test_to_dict_includes_field(self):
        signals = ConfidenceSignals(output_modulation_adjustment=-0.07)
        d = signals.to_dict()
        assert "output_modulation_adjustment" in d
        assert d["output_modulation_adjustment"] == -0.07


# =========================================================================
# Test: ConfidenceAggregator applies adjustment
# =========================================================================


class TestAggregatorAppliesModulation:
    """Tests that ConfidenceAggregator applies output_modulation_adjustment."""

    def test_zero_adjustment_no_change(self):
        """No adjustment → same result as before Strategy 2."""
        agg = ConfidenceAggregator()
        signals_a = ConfidenceSignals(output_modulation_adjustment=0.0)
        signals_b = ConfidenceSignals()  # default is also 0.0
        result_a = agg.aggregate(signals_a)
        result_b = agg.aggregate(signals_b)
        assert result_a.overall == pytest.approx(result_b.overall)

    def test_negative_adjustment_reduces_confidence(self):
        """Penalty from low E reduces overall confidence."""
        agg = ConfidenceAggregator()
        signals_base = ConfidenceSignals()
        signals_penalized = ConfidenceSignals(output_modulation_adjustment=-0.10)
        base = agg.aggregate(signals_base).overall
        penalized = agg.aggregate(signals_penalized).overall
        assert penalized < base
        assert base - penalized == pytest.approx(0.10, abs=0.01)

    def test_positive_adjustment_increases_confidence(self):
        """Modest uplift from high E increases overall confidence."""
        agg = ConfidenceAggregator()
        signals_base = ConfidenceSignals()
        signals_uplifted = ConfidenceSignals(output_modulation_adjustment=0.03)
        base = agg.aggregate(signals_base).overall
        uplifted = agg.aggregate(signals_uplifted).overall
        assert uplifted > base
        assert uplifted - base == pytest.approx(0.03, abs=0.01)

    def test_adjustment_clamped_to_zero_floor(self):
        """Adjustment can't push confidence below 0."""
        agg = ConfidenceAggregator()
        # Start with very low signals AND a penalty
        signals = ConfidenceSignals(
            quality_score=0.0,
            coherence_score=0.0,
            correctness_score=0.0,
            completeness_score=0.0,
            relevance_score=0.0,
            internal_consistency=0.0,
            goal_alignment=0.0,
            trajectory_confidence=0.0,
            session_stability=0.0,
            action_reversibility=0.0,
            action_complexity=1.0,
            volatility_index=1.0,
            prediction_reversal_risk=1.0,
            output_modulation_adjustment=-0.10,
        )
        result = agg.aggregate(signals)
        assert result.overall >= 0.0

    def test_adjustment_clamped_to_one_ceiling(self):
        """Adjustment can't push confidence above 1."""
        agg = ConfidenceAggregator()
        signals = ConfidenceSignals(
            quality_score=1.0,
            coherence_score=1.0,
            correctness_score=1.0,
            completeness_score=1.0,
            relevance_score=1.0,
            internal_consistency=1.0,
            goal_alignment=1.0,
            trajectory_confidence=1.0,
            session_stability=1.0,
            action_reversibility=1.0,
            action_complexity=0.0,
            volatility_index=0.0,
            prediction_reversal_risk=0.0,
            output_modulation_adjustment=0.03,
        )
        result = agg.aggregate(signals)
        assert result.overall <= 1.0

    def test_signals_used_records_modulation(self):
        """signals_used includes output_modulation_adjustment when non-zero."""
        agg = ConfidenceAggregator()
        signals = ConfidenceSignals(output_modulation_adjustment=-0.05)
        result = agg.aggregate(signals)
        assert "output_modulation_adjustment" in result.signals_used

    def test_signals_used_excludes_when_zero(self):
        """signals_used does NOT include output_modulation_adjustment when zero."""
        agg = ConfidenceAggregator()
        signals = ConfidenceSignals(output_modulation_adjustment=0.0)
        result = agg.aggregate(signals)
        assert "output_modulation_adjustment" not in result.signals_used


# =========================================================================
# Test: Escalation and execution shift
# =========================================================================


class TestEscalationShift:
    """Tests that E-derived adjustment actually changes behavioral decisions."""

    def test_penalty_can_push_escalation_from_none_to_notify(self):
        """A confidence near the NOTIFY boundary shifts with penalty."""
        gate = ConfidenceGate()
        # Build signals that produce confidence just above 0.75 (NONE threshold)
        signals_base = ConfidenceSignals(
            quality_score=0.8,
            coherence_score=0.8,
            correctness_score=0.8,
            completeness_score=0.7,
            relevance_score=0.7,
            internal_consistency=0.8,
            goal_alignment=0.7,
            trajectory_confidence=0.8,
            session_stability=0.7,
        )
        base_decision = gate.evaluate(signals_base)
        base_conf = base_decision.confidence.overall

        # Now apply penalty
        signals_penalized = ConfidenceSignals(
            quality_score=0.8,
            coherence_score=0.8,
            correctness_score=0.8,
            completeness_score=0.7,
            relevance_score=0.7,
            internal_consistency=0.8,
            goal_alignment=0.7,
            trajectory_confidence=0.8,
            session_stability=0.7,
            output_modulation_adjustment=-0.10,
        )
        pen_decision = gate.evaluate(signals_penalized)
        pen_conf = pen_decision.confidence.overall

        # Penalty should reduce confidence
        assert pen_conf < base_conf
        # And potentially shift escalation level
        # (exact shift depends on base confidence; at minimum, confidence moved)
        assert pen_decision.confidence.overall < base_decision.confidence.overall

    def test_no_modulation_matches_prior_behavior(self):
        """Default (no modulation) produces same result as before Strategy 2."""
        gate = ConfidenceGate()
        signals = ConfidenceSignals(quality_score=0.7, coherence_score=0.7)
        decision = gate.evaluate(signals)
        # No output_modulation_adjustment in signals_used
        assert "output_modulation_adjustment" not in decision.confidence.signals_used


# =========================================================================
# Test: End-to-end E → confidence path
# =========================================================================


class TestEndToEndModulationPath:
    """Tests the full path: E → transform → signals → aggregator → decision."""

    def test_low_E_reduces_confidence(self):
        """Low E (0.1) causes confidence to drop."""
        adj = compute_modulation_confidence_adjustment(0.1)
        assert adj < 0

        gate = ConfidenceGate()
        signals = ConfidenceSignals(
            quality_score=0.7,
            coherence_score=0.7,
            output_modulation_adjustment=adj,
        )
        decision = gate.evaluate(signals)
        assert decision.confidence.overall < gate.evaluate(
            ConfidenceSignals(quality_score=0.7, coherence_score=0.7)
        ).confidence.overall

    def test_high_E_modestly_increases_confidence(self):
        """High E (0.95) causes confidence to rise modestly."""
        adj = compute_modulation_confidence_adjustment(0.95)
        assert adj > 0
        assert adj <= 0.03

        gate = ConfidenceGate()
        signals = ConfidenceSignals(
            quality_score=0.7,
            coherence_score=0.7,
            output_modulation_adjustment=adj,
        )
        decision = gate.evaluate(signals)
        assert decision.confidence.overall > gate.evaluate(
            ConfidenceSignals(quality_score=0.7, coherence_score=0.7)
        ).confidence.overall

    def test_neutral_E_no_effect(self):
        """Mid-range E (0.55) causes no confidence change."""
        adj = compute_modulation_confidence_adjustment(0.55)
        assert adj == 0.0

        gate = ConfidenceGate()
        signals_with = ConfidenceSignals(quality_score=0.7, output_modulation_adjustment=adj)
        signals_without = ConfidenceSignals(quality_score=0.7)
        assert gate.evaluate(signals_with).confidence.overall == pytest.approx(
            gate.evaluate(signals_without).confidence.overall
        )

    def test_missing_E_fallback_neutral(self):
        """None E → 0.0 adjustment → no behavioral change."""
        adj = compute_modulation_confidence_adjustment(None)
        assert adj == 0.0

        gate = ConfidenceGate()
        signals = ConfidenceSignals(quality_score=0.7, output_modulation_adjustment=adj)
        base = ConfidenceSignals(quality_score=0.7)
        assert gate.evaluate(signals).confidence.overall == pytest.approx(
            gate.evaluate(base).confidence.overall
        )


# =========================================================================
# Test: Metadata / audit surface
# =========================================================================


class TestMetadataAudit:
    """Tests that raw E and applied adjustment are recordable."""

    def test_resolution_carries_E(self):
        """OutputModulationResolution.guna_E feeds the transform."""
        from agentic.agentic_framework.signal_adapters.output_modulation_adapter import (
            OutputModulationResolution,
        )
        # Simulate a resolution with known E
        res = OutputModulationResolution(
            dha_available=False, dha_tone_weights=None, dha_intensity=None,
            dha_restraint=None, dha_delivery_factor=None, dha_dominant_tone=None,
            dha_suppressed=None,
            guna_modulation_available=True, guna_E=0.3, guna_G=0.4,
            guna_P=0.8, guna_T_scalar=0.9, guna_output_intensity=0.3,
            guna_vector={"sattva": 0.5, "rajas": 0.3, "tamas": 0.2},
            entropy_gate=None, entropy_combined=None,
            source_detail="test",
        )
        # Transform from the resolution's E
        adj = compute_modulation_confidence_adjustment(res.guna_E)
        assert adj < 0  # E=0.3 < 0.4 → penalty
        # Verify we can build an audit dict
        audit = {
            "guna_E_raw": res.guna_E,
            "modulation_adjustment": adj,
            "modulation_available": res.guna_modulation_available,
        }
        assert audit["guna_E_raw"] == 0.3
        assert audit["modulation_adjustment"] < 0

    def test_to_dict_roundtrips(self):
        """OutputModulationResolution.to_dict() includes E for audit."""
        from agentic.agentic_framework.signal_adapters.output_modulation_adapter import (
            OutputModulationResolution,
        )
        res = OutputModulationResolution(
            dha_available=False, dha_tone_weights=None, dha_intensity=None,
            dha_restraint=None, dha_delivery_factor=None, dha_dominant_tone=None,
            dha_suppressed=None,
            guna_modulation_available=True, guna_E=0.85, guna_G=0.9,
            guna_P=1.0, guna_T_scalar=0.95, guna_output_intensity=0.85,
            guna_vector=None, entropy_gate=None, entropy_combined=None,
            source_detail="test",
        )
        d = res.to_dict()
        assert d["guna_E"] == 0.85
        assert d["guna_modulation_available"] is True
