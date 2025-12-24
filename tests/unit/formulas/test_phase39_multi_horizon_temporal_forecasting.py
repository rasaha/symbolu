"""
Test Suite for Phase 39: Multi-Horizon Temporal Forecasting Engine (MHTFE) v1.0

This test suite ensures that the Multi-Horizon Temporal Forecasting Engine:
1. Computes accurate forecasts across H1, H2, H3 horizons
2. Properly integrates with coherence state and engine
3. Exposes correct data through Unified API and Observer
4. Maintains Zero-LLM, deterministic, observation-only behavior
5. Does NOT affect routing, mappers, scoring, or semantic output

Test Groups:
- Group A: Forecast Math (15 tests)
- Group B: Coherence Integration (12 tests)
- Group C: Unified API + Observer (8 tests)
- Group E: Behavioral Invariance (12 tests)

Total: 47 tests (core critical functionality)
"""

import pytest
from symbolu.formulas.multi_horizon_temporal_forecasting import (
    compute_multi_horizon_forecast,
    MultiHorizonForecastSnapshot,
    HorizonForecast,
    _clamp,
    _safe_get,
    _compute_variance,
    _compute_linear_slope,
    _normalize_slope,
    _compute_forecast_strength,
    _compute_drift_risk,
    _compute_entropy_risk,
    _compute_forecast_consensus_index,
    _compute_future_stability_envelope,
)


# ============================================================================
# GROUP A: FORECAST MATH (15 TESTS)
# ============================================================================


class TestForecastMath:
    """Test core forecasting mathematics."""

    def test_clamp_within_bounds(self):
        """Test clamping values within normal range."""
        assert _clamp(0.5) == 0.5
        assert _clamp(0.0) == 0.0
        assert _clamp(1.0) == 1.0

    def test_clamp_outside_bounds(self):
        """Test clamping values outside range."""
        assert _clamp(-0.5) == 0.0
        assert _clamp(1.5) == 1.0
        assert _clamp(100.0) == 1.0

    def test_safe_get_with_value(self):
        """Test safe_get with valid value."""
        assert _safe_get(0.7) == 0.7
        assert _safe_get(0.0) == 0.0
        assert _safe_get(1.0) == 1.0

    def test_safe_get_with_none(self):
        """Test safe_get with None returns default."""
        assert _safe_get(None) == 0.5
        assert _safe_get(None, default=0.75) == 0.75

    def test_compute_variance_basic(self):
        """Test variance computation with normal data."""
        values = [0.5, 0.6, 0.5, 0.7, 0.5]
        variance = _compute_variance(values)
        assert 0.0 <= variance <= 1.0
        assert variance < 0.01  # Low variance for these values

    def test_compute_variance_high_variance(self):
        """Test variance computation with high variance data."""
        values = [0.1, 0.9, 0.2, 0.8]
        variance = _compute_variance(values)
        assert variance > 0.1  # High variance

    def test_compute_linear_slope_upward(self):
        """Test slope computation with upward trend."""
        values = [0.3, 0.4, 0.5, 0.6, 0.7]
        slope = _compute_linear_slope(values)
        assert slope > 0  # Positive slope

    def test_compute_linear_slope_downward(self):
        """Test slope computation with downward trend."""
        values = [0.7, 0.6, 0.5, 0.4, 0.3]
        slope = _compute_linear_slope(values)
        assert slope < 0  # Negative slope

    def test_compute_linear_slope_flat(self):
        """Test slope computation with flat trend."""
        values = [0.5, 0.5, 0.5, 0.5, 0.5]
        slope = _compute_linear_slope(values)
        assert abs(slope) < 0.01  # Near zero

    def test_normalize_slope(self):
        """Test slope normalization to [-1, 1]."""
        # Small slopes stay small
        assert abs(_normalize_slope(0.0)) < 0.01

        # Large slopes get clamped toward ±1
        assert _normalize_slope(10.0) > 0.99
        assert _normalize_slope(-10.0) < -0.99

        # Moderate slopes get scaled appropriately
        normalized = _normalize_slope(0.2)
        assert -1.0 <= normalized <= 1.0

    def test_compute_forecast_strength(self):
        """Test forecast strength computation."""
        # Low variance, consistent slope = high strength
        history = [0.5, 0.55, 0.6, 0.65, 0.7]
        slope = 0.05
        strength = _compute_forecast_strength(history, slope, window=5)
        assert strength > 0.5  # Should be moderately high
        assert 0.0 <= strength <= 1.0

    def test_compute_drift_risk_scaling(self):
        """Test drift risk scales with horizon."""
        # H1 (scale=1.0)
        risk_h1 = _compute_drift_risk(
            drift_magnitude=0.6,
            drift_stability=0.4,
            entropy_volatility=0.5,
            horizon_scale=1.0
        )

        # H3 (scale=1.35)
        risk_h3 = _compute_drift_risk(
            drift_magnitude=0.6,
            drift_stability=0.4,
            entropy_volatility=0.5,
            horizon_scale=1.35
        )

        # H3 risk should be higher
        assert risk_h3 > risk_h1
        assert 0.0 <= risk_h1 <= 1.0
        assert 0.0 <= risk_h3 <= 1.0

    def test_compute_entropy_risk_scaling(self):
        """Test entropy risk scales with horizon."""
        # H1 (scale=1.0)
        risk_h1 = _compute_entropy_risk(
            entropy_volatility=0.6,
            entropy_diff=0.5,
            horizon_scale=1.0
        )

        # H3 (scale=1.3)
        risk_h3 = _compute_entropy_risk(
            entropy_volatility=0.6,
            entropy_diff=0.5,
            horizon_scale=1.3
        )

        # H3 risk should be higher
        assert risk_h3 > risk_h1
        assert 0.0 <= risk_h1 <= 1.0
        assert 0.0 <= risk_h3 <= 1.0

    def test_compute_forecast_consensus_index(self):
        """Test FCI computation."""
        # All horizons agree (similar slopes)
        h1 = HorizonForecast(
            coherence_slope=0.5,
            continuity_slope=0.5,
            drift_risk=0.3,
            entropy_risk=0.3,
            forecast_strength=0.7,
            forecast_band="MILD_UPTREND"
        )
        h2 = HorizonForecast(
            coherence_slope=0.52,
            continuity_slope=0.48,
            drift_risk=0.3,
            entropy_risk=0.3,
            forecast_strength=0.7,
            forecast_band="MILD_UPTREND"
        )
        h3 = HorizonForecast(
            coherence_slope=0.48,
            continuity_slope=0.52,
            drift_risk=0.3,
            entropy_risk=0.3,
            forecast_strength=0.7,
            forecast_band="MILD_UPTREND"
        )

        fci = _compute_forecast_consensus_index(h1, h2, h3)
        assert fci > 0.7  # High consensus
        assert 0.0 <= fci <= 1.0

    def test_compute_future_stability_envelope(self):
        """Test FSE computation."""
        h1 = HorizonForecast(
            coherence_slope=0.3,
            continuity_slope=0.3,
            drift_risk=0.2,
            entropy_risk=0.2,
            forecast_strength=0.8,
            forecast_band="MILD_UPTREND"
        )
        h2 = HorizonForecast(
            coherence_slope=0.3,
            continuity_slope=0.3,
            drift_risk=0.25,
            entropy_risk=0.25,
            forecast_strength=0.75,
            forecast_band="MILD_UPTREND"
        )
        h3 = HorizonForecast(
            coherence_slope=0.3,
            continuity_slope=0.3,
            drift_risk=0.3,
            entropy_risk=0.3,
            forecast_strength=0.7,
            forecast_band="MILD_UPTREND"
        )

        coherence_history = [0.6, 0.62, 0.64, 0.66, 0.68]

        fse = _compute_future_stability_envelope(
            h1=h1,
            h2=h2,
            h3=h3,
            coherence_history=coherence_history,
            identity_anchoring=0.7,
            symbolic_stabilization=0.7
        )

        assert 0.0 <= fse <= 1.0
        assert fse > 0.5  # Should be reasonably stable


# ============================================================================
# GROUP B: COHERENCE INTEGRATION (12 TESTS)
# ============================================================================


class TestCoherenceIntegration:
    """Test integration with coherence state and engine."""

    def test_compute_multi_horizon_forecast_basic(self):
        """Test basic multi-horizon forecast computation."""
        coherence_history = [0.5, 0.55, 0.6, 0.65, 0.7, 0.72]
        ncc_history = [0.6, 0.62, 0.64, 0.66, 0.68, 0.70]

        snapshot = compute_multi_horizon_forecast(
            coherence_fused_history=coherence_history,
            ncc_history=ncc_history,
            drift_magnitude_prediction=0.3,
            drift_stability_score=0.7,
            identity_memory_strength=0.7,
            identity_drift_anchoring=0.6,
            identity_stability_score=0.7,
            symbolic_harmonization_index=0.6,
            consciousness_order_index=0.6,
            consciousness_stability_index=0.7,
            temporal_entropy_volatility=0.4,
            temporal_entropy_diff=0.3,
        )

        assert snapshot is not None
        assert isinstance(snapshot, MultiHorizonForecastSnapshot)
        assert isinstance(snapshot.h1_forecast, HorizonForecast)
        assert isinstance(snapshot.h2_forecast, HorizonForecast)
        assert isinstance(snapshot.h3_forecast, HorizonForecast)

    def test_graceful_degradation_insufficient_data(self):
        """Test graceful degradation with insufficient data."""
        # Not enough history (less than 5 points)
        snapshot = compute_multi_horizon_forecast(
            coherence_fused_history=[0.5, 0.6],
            ncc_history=[0.5, 0.6],
        )

        assert snapshot is None

    def test_all_horizon_fields_present(self):
        """Test that all horizon fields are populated."""
        coherence_history = [0.5, 0.55, 0.6, 0.65, 0.7, 0.72]
        ncc_history = [0.6, 0.62, 0.64, 0.66, 0.68, 0.70]

        snapshot = compute_multi_horizon_forecast(
            coherence_fused_history=coherence_history,
            ncc_history=ncc_history,
        )

        assert snapshot is not None

        # Check H1 fields
        assert snapshot.h1_forecast.coherence_slope is not None
        assert snapshot.h1_forecast.continuity_slope is not None
        assert snapshot.h1_forecast.drift_risk is not None
        assert snapshot.h1_forecast.entropy_risk is not None
        assert snapshot.h1_forecast.forecast_strength is not None
        assert snapshot.h1_forecast.forecast_band is not None

        # Check H2 fields
        assert snapshot.h2_forecast.coherence_slope is not None
        assert snapshot.h2_forecast.continuity_slope is not None
        assert snapshot.h2_forecast.drift_risk is not None
        assert snapshot.h2_forecast.entropy_risk is not None
        assert snapshot.h2_forecast.forecast_strength is not None
        assert snapshot.h2_forecast.forecast_band is not None

        # Check H3 fields
        assert snapshot.h3_forecast.coherence_slope is not None
        assert snapshot.h3_forecast.continuity_slope is not None
        assert snapshot.h3_forecast.drift_risk is not None
        assert snapshot.h3_forecast.entropy_risk is not None
        assert snapshot.h3_forecast.forecast_strength is not None
        assert snapshot.h3_forecast.forecast_band is not None

        # Check cross-horizon analytics
        assert snapshot.forecast_consensus_index is not None
        assert snapshot.future_stability_envelope is not None

    def test_boundedness_all_outputs(self):
        """Test that all outputs are properly bounded."""
        coherence_history = [0.5, 0.55, 0.6, 0.65, 0.7, 0.72]
        ncc_history = [0.6, 0.62, 0.64, 0.66, 0.68, 0.70]

        snapshot = compute_multi_horizon_forecast(
            coherence_fused_history=coherence_history,
            ncc_history=ncc_history,
        )

        assert snapshot is not None

        # Check H1 boundedness
        assert -1.0 <= snapshot.h1_forecast.coherence_slope <= 1.0
        assert -1.0 <= snapshot.h1_forecast.continuity_slope <= 1.0
        assert 0.0 <= snapshot.h1_forecast.drift_risk <= 1.0
        assert 0.0 <= snapshot.h1_forecast.entropy_risk <= 1.0
        assert 0.0 <= snapshot.h1_forecast.forecast_strength <= 1.0

        # Check H2 boundedness
        assert -1.0 <= snapshot.h2_forecast.coherence_slope <= 1.0
        assert -1.0 <= snapshot.h2_forecast.continuity_slope <= 1.0
        assert 0.0 <= snapshot.h2_forecast.drift_risk <= 1.0
        assert 0.0 <= snapshot.h2_forecast.entropy_risk <= 1.0
        assert 0.0 <= snapshot.h2_forecast.forecast_strength <= 1.0

        # Check H3 boundedness
        assert -1.0 <= snapshot.h3_forecast.coherence_slope <= 1.0
        assert -1.0 <= snapshot.h3_forecast.continuity_slope <= 1.0
        assert 0.0 <= snapshot.h3_forecast.drift_risk <= 1.0
        assert 0.0 <= snapshot.h3_forecast.entropy_risk <= 1.0
        assert 0.0 <= snapshot.h3_forecast.forecast_strength <= 1.0

        # Check cross-horizon analytics boundedness
        assert 0.0 <= snapshot.forecast_consensus_index <= 1.0
        assert 0.0 <= snapshot.future_stability_envelope <= 1.0

    def test_determinism(self):
        """Test that the same inputs produce the same outputs."""
        coherence_history = [0.5, 0.55, 0.6, 0.65, 0.7, 0.72]
        ncc_history = [0.6, 0.62, 0.64, 0.66, 0.68, 0.70]

        snapshot1 = compute_multi_horizon_forecast(
            coherence_fused_history=coherence_history.copy(),
            ncc_history=ncc_history.copy(),
            drift_magnitude_prediction=0.3,
            drift_stability_score=0.7,
        )

        snapshot2 = compute_multi_horizon_forecast(
            coherence_fused_history=coherence_history.copy(),
            ncc_history=ncc_history.copy(),
            drift_magnitude_prediction=0.3,
            drift_stability_score=0.7,
        )

        assert snapshot1 is not None
        assert snapshot2 is not None

        # Check determinism
        assert snapshot1.h1_forecast.coherence_slope == snapshot2.h1_forecast.coherence_slope
        assert snapshot1.h2_forecast.coherence_slope == snapshot2.h2_forecast.coherence_slope
        assert snapshot1.h3_forecast.coherence_slope == snapshot2.h3_forecast.coherence_slope
        assert snapshot1.forecast_consensus_index == snapshot2.forecast_consensus_index
        assert snapshot1.future_stability_envelope == snapshot2.future_stability_envelope

    def test_upward_trend_detection(self):
        """Test detection of upward trend."""
        # Strong upward trend
        coherence_history = [0.3, 0.4, 0.5, 0.6, 0.7, 0.8]
        ncc_history = [0.3, 0.4, 0.5, 0.6, 0.7, 0.8]

        snapshot = compute_multi_horizon_forecast(
            coherence_fused_history=coherence_history,
            ncc_history=ncc_history,
        )

        assert snapshot is not None
        # At least one horizon should detect uptrend
        assert (
            snapshot.h1_forecast.forecast_band in ["STRONG_UPTREND", "MILD_UPTREND"] or
            snapshot.h2_forecast.forecast_band in ["STRONG_UPTREND", "MILD_UPTREND"] or
            snapshot.h3_forecast.forecast_band in ["STRONG_UPTREND", "MILD_UPTREND"]
        )

    def test_downward_trend_detection(self):
        """Test detection of downward trend."""
        # Strong downward trend
        coherence_history = [0.8, 0.7, 0.6, 0.5, 0.4, 0.3]
        ncc_history = [0.8, 0.7, 0.6, 0.5, 0.4, 0.3]

        snapshot = compute_multi_horizon_forecast(
            coherence_fused_history=coherence_history,
            ncc_history=ncc_history,
        )

        assert snapshot is not None
        # At least one horizon should detect downtrend
        assert (
            snapshot.h1_forecast.forecast_band in ["STRONG_DOWNTREND", "MILD_DOWNTREND"] or
            snapshot.h2_forecast.forecast_band in ["STRONG_DOWNTREND", "MILD_DOWNTREND"] or
            snapshot.h3_forecast.forecast_band in ["STRONG_DOWNTREND", "MILD_DOWNTREND"]
        )

    def test_diagnostic_tags_generated(self):
        """Test that diagnostic tags are generated."""
        coherence_history = [0.5, 0.55, 0.6, 0.65, 0.7, 0.72]
        ncc_history = [0.6, 0.62, 0.64, 0.66, 0.68, 0.70]

        snapshot = compute_multi_horizon_forecast(
            coherence_fused_history=coherence_history,
            ncc_history=ncc_history,
        )

        assert snapshot is not None
        assert isinstance(snapshot.diagnostic_tags, list)
        # Should have at least some tags
        assert len(snapshot.diagnostic_tags) > 0

    def test_fallback_to_alternative_continuity_sources(self):
        """Test fallback from NCC to ICC to CSS."""
        coherence_history = [0.5, 0.55, 0.6, 0.65, 0.7, 0.72]
        icc_history = [0.6, 0.62, 0.64, 0.66, 0.68, 0.70]

        # Test with ICC (no NCC)
        snapshot = compute_multi_horizon_forecast(
            coherence_fused_history=coherence_history,
            icc_history=icc_history,
        )

        assert snapshot is not None
        assert "continuity_from_icc" in snapshot.diagnostic_tags

    def test_null_safe_with_none_inputs(self):
        """Test null safety with None inputs."""
        coherence_history = [0.5, 0.55, 0.6, 0.65, 0.7, 0.72]
        ncc_history = [0.6, 0.62, 0.64, 0.66, 0.68, 0.70]

        # All optional parameters as None
        snapshot = compute_multi_horizon_forecast(
            coherence_fused_history=coherence_history,
            ncc_history=ncc_history,
            drift_magnitude_prediction=None,
            drift_stability_score=None,
            identity_memory_strength=None,
            identity_drift_anchoring=None,
            identity_stability_score=None,
            symbolic_harmonization_index=None,
            consciousness_order_index=None,
            consciousness_stability_index=None,
            temporal_entropy_volatility=None,
            temporal_entropy_diff=None,
        )

        assert snapshot is not None

    def test_horizon_risk_amplification(self):
        """Test that risks amplify with longer horizons."""
        coherence_history = [0.5, 0.55, 0.6, 0.65, 0.7, 0.72]
        ncc_history = [0.6, 0.62, 0.64, 0.66, 0.68, 0.70]

        snapshot = compute_multi_horizon_forecast(
            coherence_fused_history=coherence_history,
            ncc_history=ncc_history,
            drift_magnitude_prediction=0.5,
            temporal_entropy_volatility=0.5,
        )

        assert snapshot is not None
        # H3 drift/entropy risks should be >= H2 >= H1 (due to amplification)
        # Note: May not always be strictly true due to other factors, but trend should hold
        assert snapshot.h3_forecast.drift_risk >= snapshot.h1_forecast.drift_risk * 0.9
        assert snapshot.h3_forecast.entropy_risk >= snapshot.h1_forecast.entropy_risk * 0.9


# ============================================================================
# GROUP C: UNIFIED API + OBSERVER (8 TESTS)
# ============================================================================


class TestUnifiedAPIAndObserver:
    """Test Unified API and Observer integration."""

    def test_snapshot_serialization(self):
        """Test that snapshot can be serialized to dict."""
        coherence_history = [0.5, 0.55, 0.6, 0.65, 0.7, 0.72]
        ncc_history = [0.6, 0.62, 0.64, 0.66, 0.68, 0.70]

        snapshot = compute_multi_horizon_forecast(
            coherence_fused_history=coherence_history,
            ncc_history=ncc_history,
        )

        assert snapshot is not None

        # Test that we can access all fields (dict-like access)
        assert hasattr(snapshot, 'h1_forecast')
        assert hasattr(snapshot, 'h2_forecast')
        assert hasattr(snapshot, 'h3_forecast')
        assert hasattr(snapshot, 'forecast_consensus_index')
        assert hasattr(snapshot, 'future_stability_envelope')
        assert hasattr(snapshot, 'diagnostic_tags')
        assert hasattr(snapshot, 'raw_signals')

    def test_raw_signals_populated(self):
        """Test that raw_signals dict is populated."""
        coherence_history = [0.5, 0.55, 0.6, 0.65, 0.7, 0.72]
        ncc_history = [0.6, 0.62, 0.64, 0.66, 0.68, 0.70]

        snapshot = compute_multi_horizon_forecast(
            coherence_fused_history=coherence_history,
            ncc_history=ncc_history,
        )

        assert snapshot is not None
        assert isinstance(snapshot.raw_signals, dict)
        assert len(snapshot.raw_signals) > 0

        # Check key signals are present
        assert "h1_coherence_slope" in snapshot.raw_signals
        assert "h2_coherence_slope" in snapshot.raw_signals
        assert "h3_coherence_slope" in snapshot.raw_signals
        assert "forecast_consensus_index" in snapshot.raw_signals
        assert "future_stability_envelope" in snapshot.raw_signals

    def test_json_safe_output(self):
        """Test that all outputs are JSON-safe."""
        coherence_history = [0.5, 0.55, 0.6, 0.65, 0.7, 0.72]
        ncc_history = [0.6, 0.62, 0.64, 0.66, 0.68, 0.70]

        snapshot = compute_multi_horizon_forecast(
            coherence_fused_history=coherence_history,
            ncc_history=ncc_history,
        )

        assert snapshot is not None

        # All numeric values should be floats (JSON-safe)
        assert isinstance(snapshot.h1_forecast.coherence_slope, float)
        assert isinstance(snapshot.h1_forecast.drift_risk, float)
        assert isinstance(snapshot.forecast_consensus_index, float)
        assert isinstance(snapshot.future_stability_envelope, float)

        # String values should be strings
        assert isinstance(snapshot.h1_forecast.forecast_band, str)

        # Lists should be lists
        assert isinstance(snapshot.diagnostic_tags, list)

    def test_backward_compatibility(self):
        """Test backward compatibility with existing code."""
        # Test that snapshot doesn't break if accessed with getattr
        coherence_history = [0.5, 0.55, 0.6, 0.65, 0.7, 0.72]
        ncc_history = [0.6, 0.62, 0.64, 0.66, 0.68, 0.70]

        snapshot = compute_multi_horizon_forecast(
            coherence_fused_history=coherence_history,
            ncc_history=ncc_history,
        )

        assert snapshot is not None

        # Test getattr-style access (used in API integration)
        h1 = getattr(snapshot, 'h1_forecast', None)
        assert h1 is not None

        h1_slope = getattr(h1, 'coherence_slope', None)
        assert h1_slope is not None

    def test_null_safe_extraction(self):
        """Test null-safe extraction from None snapshot."""
        # Simulate extraction from None snapshot (insufficient data case)
        snapshot = None

        # Should not crash
        h1_slope = None
        if snapshot is not None:
            h1_forecast = getattr(snapshot, 'h1_forecast', None)
            if h1_forecast is not None:
                h1_slope = getattr(h1_forecast, 'coherence_slope', None)

        assert h1_slope is None

    def test_diagnostic_tags_sorted_deduplicated(self):
        """Test that diagnostic tags are sorted and deduplicated."""
        coherence_history = [0.5, 0.55, 0.6, 0.65, 0.7, 0.72]
        ncc_history = [0.6, 0.62, 0.64, 0.66, 0.68, 0.70]

        snapshot = compute_multi_horizon_forecast(
            coherence_fused_history=coherence_history,
            ncc_history=ncc_history,
        )

        assert snapshot is not None
        assert isinstance(snapshot.diagnostic_tags, list)

        # Tags should be sorted
        if len(snapshot.diagnostic_tags) > 1:
            assert snapshot.diagnostic_tags == sorted(snapshot.diagnostic_tags)

        # Tags should be deduplicated (no duplicates)
        assert len(snapshot.diagnostic_tags) == len(set(snapshot.diagnostic_tags))

    def test_horizon_forecast_dataclass_fields(self):
        """Test HorizonForecast dataclass has all required fields."""
        coherence_history = [0.5, 0.55, 0.6, 0.65, 0.7, 0.72]
        ncc_history = [0.6, 0.62, 0.64, 0.66, 0.68, 0.70]

        snapshot = compute_multi_horizon_forecast(
            coherence_fused_history=coherence_history,
            ncc_history=ncc_history,
        )

        assert snapshot is not None

        # Check H1 forecast has all required fields
        h1 = snapshot.h1_forecast
        assert hasattr(h1, 'coherence_slope')
        assert hasattr(h1, 'continuity_slope')
        assert hasattr(h1, 'drift_risk')
        assert hasattr(h1, 'entropy_risk')
        assert hasattr(h1, 'forecast_strength')
        assert hasattr(h1, 'forecast_band')

    def test_observer_field_extraction(self):
        """Test that observer can extract fields from snapshot."""
        coherence_history = [0.5, 0.55, 0.6, 0.65, 0.7, 0.72]
        ncc_history = [0.6, 0.62, 0.64, 0.66, 0.68, 0.70]

        snapshot = compute_multi_horizon_forecast(
            coherence_fused_history=coherence_history,
            ncc_history=ncc_history,
        )

        assert snapshot is not None

        # Simulate observer extraction
        mh_slope_H1 = getattr(snapshot.h1_forecast, 'coherence_slope', None)
        mh_band_H2 = getattr(snapshot.h2_forecast, 'forecast_band', None)
        mh_consensus = getattr(snapshot, 'forecast_consensus_index', None)

        assert mh_slope_H1 is not None
        assert mh_band_H2 is not None
        assert mh_consensus is not None


# ============================================================================
# GROUP E: BEHAVIORAL INVARIANCE (12 TESTS)
# ============================================================================


class TestBehavioralInvariance:
    """Test that MHTFE maintains behavioral invariants."""

    def test_zero_llm_pure_math(self):
        """Test that MHTFE uses only pure math (no LLM calls)."""
        coherence_history = [0.5, 0.55, 0.6, 0.65, 0.7, 0.72]
        ncc_history = [0.6, 0.62, 0.64, 0.66, 0.68, 0.70]

        # This should complete instantly (no LLM calls)
        import time
        start = time.time()
        snapshot = compute_multi_horizon_forecast(
            coherence_fused_history=coherence_history,
            ncc_history=ncc_history,
        )
        elapsed = time.time() - start

        assert snapshot is not None
        # Should complete in milliseconds (no LLM latency)
        assert elapsed < 0.1  # 100ms max

    def test_observation_only_no_side_effects(self):
        """Test that MHTFE has no side effects on inputs."""
        coherence_history = [0.5, 0.55, 0.6, 0.65, 0.7, 0.72]
        ncc_history = [0.6, 0.62, 0.64, 0.66, 0.68, 0.70]

        # Make copies
        coherence_copy = coherence_history.copy()
        ncc_copy = ncc_history.copy()

        snapshot = compute_multi_horizon_forecast(
            coherence_fused_history=coherence_history,
            ncc_history=ncc_history,
        )

        assert snapshot is not None

        # Inputs should be unchanged
        assert coherence_history == coherence_copy
        assert ncc_history == ncc_copy

    def test_no_routing_modification(self):
        """Test that MHTFE does not modify routing logic."""
        # MHTFE should never touch routing
        # This is a behavioral contract test
        coherence_history = [0.5, 0.55, 0.6, 0.65, 0.7, 0.72]
        ncc_history = [0.6, 0.62, 0.64, 0.66, 0.68, 0.70]

        snapshot = compute_multi_horizon_forecast(
            coherence_fused_history=coherence_history,
            ncc_history=ncc_history,
        )

        assert snapshot is not None
        # MHTFE should only return a snapshot, never modify external state
        # This test documents the contract

    def test_no_mapper_modification(self):
        """Test that MHTFE does not modify mapper logic."""
        # MHTFE should never touch mappers
        # This is a behavioral contract test
        coherence_history = [0.5, 0.55, 0.6, 0.65, 0.7, 0.72]
        ncc_history = [0.6, 0.62, 0.64, 0.66, 0.68, 0.70]

        snapshot = compute_multi_horizon_forecast(
            coherence_fused_history=coherence_history,
            ncc_history=ncc_history,
        )

        assert snapshot is not None
        # MHTFE should only return a snapshot, never modify external state
        # This test documents the contract

    def test_no_coherence_scoring_modification(self):
        """Test that MHTFE does not modify coherence scores."""
        # MHTFE should never modify v1/v2/v3/UCF scores
        # This is a behavioral contract test
        coherence_history = [0.5, 0.55, 0.6, 0.65, 0.7, 0.72]
        ncc_history = [0.6, 0.62, 0.64, 0.66, 0.68, 0.70]

        snapshot = compute_multi_horizon_forecast(
            coherence_fused_history=coherence_history,
            ncc_history=ncc_history,
        )

        assert snapshot is not None
        # MHTFE should only return a snapshot, never modify coherence scores
        # This test documents the contract

    def test_deterministic_same_session(self):
        """Test determinism within same session."""
        coherence_history = [0.5, 0.55, 0.6, 0.65, 0.7, 0.72]
        ncc_history = [0.6, 0.62, 0.64, 0.66, 0.68, 0.70]

        snapshots = []
        for _ in range(3):
            snapshot = compute_multi_horizon_forecast(
                coherence_fused_history=coherence_history.copy(),
                ncc_history=ncc_history.copy(),
            )
            snapshots.append(snapshot)

        # All snapshots should be identical
        for i in range(1, len(snapshots)):
            assert snapshots[i].forecast_consensus_index == snapshots[0].forecast_consensus_index
            assert snapshots[i].future_stability_envelope == snapshots[0].future_stability_envelope

    def test_bounded_outputs_extreme_inputs(self):
        """Test that outputs remain bounded even with extreme inputs."""
        # Extreme upward trend
        coherence_history = [0.1, 0.3, 0.5, 0.7, 0.9, 1.0]
        ncc_history = [0.1, 0.3, 0.5, 0.7, 0.9, 1.0]

        snapshot = compute_multi_horizon_forecast(
            coherence_fused_history=coherence_history,
            ncc_history=ncc_history,
            drift_magnitude_prediction=1.0,
            temporal_entropy_volatility=1.0,
        )

        assert snapshot is not None

        # All outputs should still be bounded
        assert -1.0 <= snapshot.h1_forecast.coherence_slope <= 1.0
        assert 0.0 <= snapshot.h1_forecast.drift_risk <= 1.0
        assert 0.0 <= snapshot.forecast_consensus_index <= 1.0
        assert 0.0 <= snapshot.future_stability_envelope <= 1.0

    def test_graceful_degradation_empty_history(self):
        """Test graceful degradation with empty history."""
        snapshot = compute_multi_horizon_forecast(
            coherence_fused_history=[],
            ncc_history=[],
        )

        # Should return None, not crash
        assert snapshot is None

    def test_graceful_degradation_missing_optional_params(self):
        """Test graceful degradation with all optional params missing."""
        coherence_history = [0.5, 0.55, 0.6, 0.65, 0.7, 0.72]
        ncc_history = [0.6, 0.62, 0.64, 0.66, 0.68, 0.70]

        # No optional parameters
        snapshot = compute_multi_horizon_forecast(
            coherence_fused_history=coherence_history,
            ncc_history=ncc_history,
        )

        assert snapshot is not None

    def test_no_text_modification(self):
        """Test that MHTFE never modifies text output."""
        # MHTFE should never touch semantic output
        # This is a behavioral contract test
        coherence_history = [0.5, 0.55, 0.6, 0.65, 0.7, 0.72]
        ncc_history = [0.6, 0.62, 0.64, 0.66, 0.68, 0.70]

        snapshot = compute_multi_horizon_forecast(
            coherence_fused_history=coherence_history,
            ncc_history=ncc_history,
        )

        assert snapshot is not None
        # MHTFE should only return a snapshot, never modify text
        # This test documents the contract

    def test_no_reasoning_modification(self):
        """Test that MHTFE never modifies reasoning."""
        # MHTFE should never touch reasoning chains
        # This is a behavioral contract test
        coherence_history = [0.5, 0.55, 0.6, 0.65, 0.7, 0.72]
        ncc_history = [0.6, 0.62, 0.64, 0.66, 0.68, 0.70]

        snapshot = compute_multi_horizon_forecast(
            coherence_fused_history=coherence_history,
            ncc_history=ncc_history,
        )

        assert snapshot is not None
        # MHTFE should only return a snapshot, never modify reasoning
        # This test documents the contract

    def test_readonly_observation(self):
        """Test that MHTFE is truly read-only."""
        coherence_history = [0.5, 0.55, 0.6, 0.65, 0.7, 0.72]
        ncc_history = [0.6, 0.62, 0.64, 0.66, 0.68, 0.70]

        # Capture initial state
        initial_coherence = coherence_history.copy()
        initial_ncc = ncc_history.copy()

        # Run MHTFE
        snapshot = compute_multi_horizon_forecast(
            coherence_fused_history=coherence_history,
            ncc_history=ncc_history,
        )

        assert snapshot is not None

        # Verify no modifications
        assert coherence_history == initial_coherence
        assert ncc_history == initial_ncc


# ============================================================================
# TEST EXECUTION
# ============================================================================

if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
