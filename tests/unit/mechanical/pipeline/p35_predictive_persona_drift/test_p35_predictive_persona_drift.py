"""
Phase 35 - Predictive Persona Drift Model Tests

Comprehensive test suite for P35 with 45+ tests organized into groups:

Group A — Formula Correctness (12 tests)
    - Weight validation
    - Clamp enforcement

Group B — Trend Detection (10 tests)
    - Stable / improving / worsening classification

Group C — Read-Only Proof (8 tests)
    - P35 output changes do not affect any upstream or downstream authority

Group D — Determinism (5 tests)
    - Identical inputs → identical outputs

Group E — Import Safety (5 tests)
    - No observer imports
    - No governance imports

Group F — Regression Lock (5 tests)
    - Historical snapshots missing → graceful fallback

INVARIANTS TESTED:
    - INV-P35-1: Forecast never influences current decisions
    - INV-P35-2: Prediction never escalates authority
    - INV-P35-3: Observer-only behavior enforced
    - INV-P35-4: Deterministic math only
    - INV-P35-5: No acoustic dependency
"""

import ast
import inspect
import pytest
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

# Core module imports
from symbolu.core.predictive.persona_drift import (
    P35_VERSION,
    PredictivePersonaDriftReport,
    DriftRiskBand,
    TrendDirection,
    ForecastHorizon,
    ALLOWED_CONTRIBUTING_FACTORS,
    W_DRIFT_FUSION_INDEX,
    W_SCHEMA_DRIFT,
    W_TEMPORAL_ENTROPY_DIFF,
    W_COHERENCE_QUALITY,
    W_UCF_SCORE,
    RISK_BAND_LOW_THRESHOLD,
    RISK_BAND_HIGH_THRESHOLD,
    TREND_CHANGE_THRESHOLD,
    TREND_MIN_SIGNALS,
    create_report,
    create_empty_report,
    risk_band_from_score,
    clamp,
    compute_base_drift_score,
    compute_variance,
    compute_confidence,
    compute_contributing_factors,
    compute_signal_variance,
    SignalSnapshot,
    compute_signal_deltas,
    classify_trend_direction,
    analyze_trend_from_histories,
)

# Pipeline integration imports
from symbolu.mechanical.pipeline.p35_predictive_persona_drift import (
    maybe_run_p35,
    run_p35_directly,
    get_p35_resolver,
    is_p35_disabled,
    has_p35_report,
    get_p35_report,
    get_predicted_drift_score,
    get_drift_risk_band,
    get_trend_direction,
    get_contributing_factors,
    get_confidence,
    is_low_risk,
    is_moderate_risk,
    is_high_risk,
    is_stable,
    is_worsening,
    is_improving,
    get_p35_version,
)


# ============================================================================
# TEST FIXTURES
# ============================================================================


@dataclass
class MockCoherenceState:
    """Mock coherence state for testing."""
    drift_fusion_index: Optional[float] = None
    persona_schema_drift: Optional[float] = None
    temporal_entropy_diff: Optional[float] = None
    coherence_v3_quality: Optional[float] = None
    current_coi: Optional[float] = None
    current_identity_harmonics_index: Optional[float] = None

    # Histories
    drift_fusion_index_history: List[Optional[float]] = None
    persona_schema_drift_history: List[Optional[float]] = None
    temporal_entropy_diff_history: List[Optional[float]] = None
    identity_stability_history: List[Optional[float]] = None
    drift_magnitude_history: List[Optional[float]] = None

    # P35 output fields
    predictive_drift_snapshot: Any = None
    predictive_drift_history: List[Any] = None
    current_drift_magnitude_prediction: Optional[float] = None
    current_drift_stability_score: Optional[float] = None
    current_drift_likelihood_band: Optional[str] = None
    current_drift_direction_scores: Optional[Dict[str, float]] = None
    drift_stability_history: List[Optional[float]] = None
    drift_likelihood_band_history: List[Optional[str]] = None

    def __post_init__(self):
        if self.drift_fusion_index_history is None:
            self.drift_fusion_index_history = []
        if self.persona_schema_drift_history is None:
            self.persona_schema_drift_history = []
        if self.temporal_entropy_diff_history is None:
            self.temporal_entropy_diff_history = []
        if self.identity_stability_history is None:
            self.identity_stability_history = []
        if self.drift_magnitude_history is None:
            self.drift_magnitude_history = []
        if self.predictive_drift_history is None:
            self.predictive_drift_history = []
        if self.drift_stability_history is None:
            self.drift_stability_history = []
        if self.drift_likelihood_band_history is None:
            self.drift_likelihood_band_history = []


@dataclass
class MockP19:
    """Mock P19 report for testing."""
    drift_fusion_index: float = 0.5


@dataclass
class MockP18:
    """Mock P18 report for testing."""
    delta_entropy: float = 0.0


@dataclass
class MockP33:
    """Mock P33 snapshot for testing."""
    schema_drift_scores: Dict[str, float] = None

    def __post_init__(self):
        if self.schema_drift_scores is None:
            self.schema_drift_scores = {"default": 0.3}


@dataclass
class MockP26:
    """Mock P26 state for testing."""
    ucf_score: float = 0.8


@dataclass
class MockPipelineContext:
    """Mock pipeline context for testing."""
    coherence_state: Optional[MockCoherenceState] = None
    p18: Optional[MockP18] = None
    p19: Optional[MockP19] = None
    p33: Optional[MockP33] = None
    p26: Optional[MockP26] = None
    p35: Optional[PredictivePersonaDriftReport] = None
    _p35_disabled: bool = False


# ============================================================================
# GROUP A — FORMULA CORRECTNESS (12 tests)
# ============================================================================


class TestGroupA_FormulaCorrectness:
    """Group A: Tests for formula correctness and weight validation."""

    def test_weights_sum_to_one(self):
        """Test that formula weights sum to 1.0."""
        total = (
            W_DRIFT_FUSION_INDEX
            + W_SCHEMA_DRIFT
            + W_TEMPORAL_ENTROPY_DIFF
            + W_COHERENCE_QUALITY
            + W_UCF_SCORE
        )
        assert abs(total - 1.0) < 1e-10, f"Weights sum to {total}, expected 1.0"

    def test_weight_drift_fusion_index(self):
        """Test drift fusion index weight is 0.35."""
        assert W_DRIFT_FUSION_INDEX == 0.35

    def test_weight_schema_drift(self):
        """Test schema drift weight is 0.25."""
        assert W_SCHEMA_DRIFT == 0.25

    def test_weight_temporal_entropy_diff(self):
        """Test temporal entropy diff weight is 0.20."""
        assert W_TEMPORAL_ENTROPY_DIFF == 0.20

    def test_weight_coherence_quality(self):
        """Test coherence quality weight is 0.10."""
        assert W_COHERENCE_QUALITY == 0.10

    def test_weight_ucf_score(self):
        """Test UCF score weight is 0.10."""
        assert W_UCF_SCORE == 0.10

    def test_clamp_function_within_range(self):
        """Test clamp keeps values within range."""
        assert clamp(0.5) == 0.5
        assert clamp(0.0) == 0.0
        assert clamp(1.0) == 1.0

    def test_clamp_function_below_min(self):
        """Test clamp handles values below minimum."""
        assert clamp(-0.5) == 0.0
        assert clamp(-1.0) == 0.0
        assert clamp(-100.0) == 0.0

    def test_clamp_function_above_max(self):
        """Test clamp handles values above maximum."""
        assert clamp(1.5) == 1.0
        assert clamp(2.0) == 1.0
        assert clamp(100.0) == 1.0

    def test_compute_base_drift_score_all_zero(self):
        """Test base drift score with all zero inputs."""
        score = compute_base_drift_score(
            drift_fusion_index=0.0,
            schema_drift=0.0,
            temporal_entropy_diff=0.0,
            coherence_v3_quality=1.0,  # High quality = low drift
            ucf_score=1.0,  # High UCF = low drift
        )
        assert score == 0.0

    def test_compute_base_drift_score_all_one(self):
        """Test base drift score with all maximum drift inputs."""
        score = compute_base_drift_score(
            drift_fusion_index=1.0,
            schema_drift=1.0,
            temporal_entropy_diff=1.0,
            coherence_v3_quality=0.0,  # Low quality = high drift
            ucf_score=0.0,  # Low UCF = high drift
        )
        assert score == 1.0

    def test_compute_base_drift_score_middle_values(self):
        """Test base drift score with middle values."""
        score = compute_base_drift_score(
            drift_fusion_index=0.5,
            schema_drift=0.5,
            temporal_entropy_diff=0.5,
            coherence_v3_quality=0.5,
            ucf_score=0.5,
        )
        # Expected: 0.35*0.5 + 0.25*0.5 + 0.20*0.5 + 0.10*0.5 + 0.10*0.5
        # = 0.175 + 0.125 + 0.10 + 0.05 + 0.05 = 0.50
        assert abs(score - 0.5) < 1e-10


class TestGroupA_RiskBands:
    """Group A continued: Tests for risk band classification."""

    def test_risk_band_low_threshold(self):
        """Test risk band threshold for low."""
        assert RISK_BAND_LOW_THRESHOLD == 0.35

    def test_risk_band_high_threshold(self):
        """Test risk band threshold for high."""
        assert RISK_BAND_HIGH_THRESHOLD == 0.65

    def test_risk_band_from_score_low(self):
        """Test risk band classification for low scores."""
        assert risk_band_from_score(0.0) == "low"
        assert risk_band_from_score(0.2) == "low"
        assert risk_band_from_score(0.34) == "low"

    def test_risk_band_from_score_moderate(self):
        """Test risk band classification for moderate scores."""
        assert risk_band_from_score(0.35) == "moderate"
        assert risk_band_from_score(0.5) == "moderate"
        assert risk_band_from_score(0.64) == "moderate"

    def test_risk_band_from_score_high(self):
        """Test risk band classification for high scores."""
        assert risk_band_from_score(0.65) == "high"
        assert risk_band_from_score(0.8) == "high"
        assert risk_band_from_score(1.0) == "high"


# ============================================================================
# GROUP B — TREND DETECTION (10 tests)
# ============================================================================


class TestGroupB_TrendDetection:
    """Group B: Tests for trend detection and classification."""

    def test_trend_change_threshold(self):
        """Test trend change threshold is 0.05."""
        assert TREND_CHANGE_THRESHOLD == 0.05

    def test_trend_min_signals(self):
        """Test minimum signals for trend detection is 2."""
        assert TREND_MIN_SIGNALS == 2

    def test_classify_trend_stable_no_history(self):
        """Test trend is stable with no history."""
        snapshots = []
        assert classify_trend_direction(snapshots) == "stable"

    def test_classify_trend_stable_single_snapshot(self):
        """Test trend is stable with single snapshot."""
        snapshots = [SignalSnapshot(drift_fusion_index=0.5)]
        assert classify_trend_direction(snapshots) == "stable"

    def test_classify_trend_stable_small_changes(self):
        """Test trend is stable with small changes."""
        snapshots = [
            SignalSnapshot(drift_fusion_index=0.50, schema_drift=0.30),
            SignalSnapshot(drift_fusion_index=0.52, schema_drift=0.32),
            SignalSnapshot(drift_fusion_index=0.51, schema_drift=0.31),
        ]
        assert classify_trend_direction(snapshots) == "stable"

    def test_classify_trend_worsening(self):
        """Test trend is worsening when 2+ signals increase > 0.05."""
        snapshots = [
            SignalSnapshot(drift_fusion_index=0.30, schema_drift=0.30, temporal_entropy_diff=0.30),
            SignalSnapshot(drift_fusion_index=0.40, schema_drift=0.40, temporal_entropy_diff=0.31),
            SignalSnapshot(drift_fusion_index=0.50, schema_drift=0.50, temporal_entropy_diff=0.32),
        ]
        assert classify_trend_direction(snapshots) == "worsening"

    def test_classify_trend_improving(self):
        """Test trend is improving when 2+ signals decrease > 0.05."""
        snapshots = [
            SignalSnapshot(drift_fusion_index=0.70, schema_drift=0.70, temporal_entropy_diff=0.70),
            SignalSnapshot(drift_fusion_index=0.60, schema_drift=0.60, temporal_entropy_diff=0.69),
            SignalSnapshot(drift_fusion_index=0.50, schema_drift=0.50, temporal_entropy_diff=0.68),
        ]
        assert classify_trend_direction(snapshots) == "improving"

    def test_classify_trend_worsening_quality_decrease(self):
        """Test trend detects worsening from quality metric decreases."""
        # Quality metrics decrease = drift increases (inverted)
        snapshots = [
            SignalSnapshot(coherence_v3_quality=0.80, ucf_score=0.80),
            SignalSnapshot(coherence_v3_quality=0.70, ucf_score=0.70),
            SignalSnapshot(coherence_v3_quality=0.60, ucf_score=0.60),
        ]
        assert classify_trend_direction(snapshots) == "worsening"

    def test_analyze_trend_from_histories_stable(self):
        """Test analyze_trend_from_histories returns stable for flat data."""
        trend = analyze_trend_from_histories(
            drift_fusion_index_history=[0.5, 0.5, 0.5],
            schema_drift_history=[0.3, 0.3, 0.3],
        )
        assert trend == "stable"

    def test_analyze_trend_from_histories_worsening(self):
        """Test analyze_trend_from_histories detects worsening."""
        trend = analyze_trend_from_histories(
            drift_fusion_index_history=[0.3, 0.4, 0.5],
            schema_drift_history=[0.2, 0.3, 0.4],
            temporal_entropy_diff_history=[0.3, 0.35, 0.40],
        )
        assert trend == "worsening"


# ============================================================================
# GROUP C — READ-ONLY PROOF (8 tests)
# ============================================================================


class TestGroupC_ReadOnlyProof:
    """Group C: Tests proving P35 is read-only and observer-only."""

    def test_report_is_frozen(self):
        """Test PredictivePersonaDriftReport is immutable."""
        report = create_report(
            predicted_drift_score=0.5,
            drift_risk_band="moderate",
            trend_direction="stable",
            contributing_factors=[],
            confidence=0.8,
        )
        with pytest.raises(Exception):  # FrozenInstanceError
            report.predicted_drift_score = 0.9

    def test_report_observer_only_always_true(self):
        """Test report observer_only is always True."""
        report = create_report(
            predicted_drift_score=0.5,
            drift_risk_band="moderate",
            trend_direction="stable",
            contributing_factors=[],
            confidence=0.8,
        )
        assert report.observer_only is True

    def test_report_rejects_observer_only_false(self):
        """Test report creation rejects observer_only=False."""
        with pytest.raises(ValueError, match="observer_only must be True"):
            PredictivePersonaDriftReport(
                predicted_drift_score=0.5,
                drift_risk_band="moderate",
                trend_direction="stable",
                forecast_horizon="short",
                contributing_factors=(),
                confidence=0.8,
                observer_only=False,
            )

    def test_p35_does_not_modify_p19(self):
        """Test P35 does not modify P19 report."""
        ctx = MockPipelineContext(
            p19=MockP19(drift_fusion_index=0.5),
            coherence_state=MockCoherenceState(drift_fusion_index=0.5),
        )
        original_p19_value = ctx.p19.drift_fusion_index

        maybe_run_p35(ctx)

        assert ctx.p19.drift_fusion_index == original_p19_value

    def test_p35_does_not_modify_p33(self):
        """Test P35 does not modify P33 snapshot."""
        ctx = MockPipelineContext(
            p33=MockP33(schema_drift_scores={"test": 0.4}),
            coherence_state=MockCoherenceState(persona_schema_drift=0.4),
        )
        original_p33_scores = dict(ctx.p33.schema_drift_scores)

        maybe_run_p35(ctx)

        assert ctx.p33.schema_drift_scores == original_p33_scores

    def test_p35_does_not_modify_coherence_score(self):
        """Test P35 does not modify coherence scores."""
        ctx = MockPipelineContext(
            coherence_state=MockCoherenceState(
                drift_fusion_index=0.5,
                coherence_v3_quality=0.7,
            ),
        )
        original_quality = ctx.coherence_state.coherence_v3_quality

        maybe_run_p35(ctx)

        assert ctx.coherence_state.coherence_v3_quality == original_quality

    def test_report_architectural_phase_is_p35(self):
        """Test report architectural_phase is P35."""
        report = create_report(
            predicted_drift_score=0.5,
            drift_risk_band="moderate",
            trend_direction="stable",
            contributing_factors=[],
            confidence=0.8,
        )
        assert report.architectural_phase == "P35"

    def test_report_forecast_horizon_is_short(self):
        """Test report forecast_horizon is always 'short'."""
        report = create_report(
            predicted_drift_score=0.5,
            drift_risk_band="moderate",
            trend_direction="stable",
            contributing_factors=[],
            confidence=0.8,
        )
        assert report.forecast_horizon == "short"


# ============================================================================
# GROUP D — DETERMINISM (5 tests)
# ============================================================================


class TestGroupD_Determinism:
    """Group D: Tests for deterministic behavior."""

    def test_same_inputs_same_output_base_score(self):
        """Test identical inputs produce identical base drift scores."""
        inputs = {
            "drift_fusion_index": 0.5,
            "schema_drift": 0.3,
            "temporal_entropy_diff": 0.4,
            "coherence_v3_quality": 0.7,
            "ucf_score": 0.8,
        }

        score1 = compute_base_drift_score(**inputs)
        score2 = compute_base_drift_score(**inputs)

        assert score1 == score2

    def test_same_inputs_same_output_full_report(self):
        """Test identical inputs produce identical reports."""
        result1 = run_p35_directly(
            drift_fusion_index=0.5,
            schema_drift=0.3,
            temporal_entropy_diff=0.4,
            coherence_v3_quality=0.7,
            ucf_score=0.8,
        )
        result2 = run_p35_directly(
            drift_fusion_index=0.5,
            schema_drift=0.3,
            temporal_entropy_diff=0.4,
            coherence_v3_quality=0.7,
            ucf_score=0.8,
        )

        assert result1.predicted_drift_score == result2.predicted_drift_score
        assert result1.drift_risk_band == result2.drift_risk_band
        assert result1.trend_direction == result2.trend_direction
        assert result1.contributing_factors == result2.contributing_factors

    def test_same_inputs_same_output_trend_analysis(self):
        """Test identical history produces identical trend."""
        history = [0.3, 0.4, 0.5]

        trend1 = analyze_trend_from_histories(
            drift_fusion_index_history=history,
            schema_drift_history=history,
        )
        trend2 = analyze_trend_from_histories(
            drift_fusion_index_history=history,
            schema_drift_history=history,
        )

        assert trend1 == trend2

    def test_same_inputs_same_output_contributing_factors(self):
        """Test identical inputs produce identical contributing factors."""
        inputs = {
            "drift_fusion_index": 0.6,
            "schema_drift": 0.55,
            "temporal_entropy_diff": 0.6,
            "coherence_v3_quality": 0.4,
            "ucf_score": 0.4,
            "identity_harmonics_score": 0.4,
            "signal_variance": 0.15,
        }

        factors1 = compute_contributing_factors(**inputs)
        factors2 = compute_contributing_factors(**inputs)

        assert factors1 == factors2

    def test_same_inputs_same_output_multiple_runs(self):
        """Test multiple runs produce identical results."""
        results = []
        for _ in range(10):
            result = run_p35_directly(
                drift_fusion_index=0.6,
                schema_drift=0.5,
                temporal_entropy_diff=0.55,
                coherence_v3_quality=0.6,
                ucf_score=0.7,
            )
            results.append(result.predicted_drift_score)

        # All results should be identical
        assert len(set(results)) == 1


# ============================================================================
# GROUP E — IMPORT SAFETY (5 tests)
# ============================================================================


class TestGroupE_ImportSafety:
    """Group E: Tests for import safety - no forbidden dependencies."""

    def test_no_p22_acoustic_witness_import(self):
        """Test drift_formula.py does not import P22 acoustic witness."""
        import symbolu.core.predictive.persona_drift.drift_formula as module
        source = inspect.getsource(module)
        assert "p22_acoustic" not in source.lower()
        assert "acoustic_witness" not in source.lower()

    def test_no_p23_alignment_import(self):
        """Test drift_formula.py does not import P23 alignment."""
        import symbolu.core.predictive.persona_drift.drift_formula as module
        source = inspect.getsource(module)
        assert "p23_alignment" not in source.lower()
        assert "inner_outer_alignment" not in source.lower()

    def test_no_p24_projection_import(self):
        """Test drift_formula.py does not import P24 projection."""
        import symbolu.core.predictive.persona_drift.drift_formula as module
        source = inspect.getsource(module)
        assert "p24_projection" not in source.lower()
        assert "acoustic_ontology" not in source.lower()

    def test_no_governance_import_in_formula(self):
        """Test drift_formula.py does not import governance modules."""
        import symbolu.core.predictive.persona_drift.drift_formula as module
        source = inspect.getsource(module)
        # Check for common governance patterns
        assert "regime" not in source.lower() or "discourse" not in source.lower()
        assert "policy" not in source.lower() or "# policy" in source.lower()

    def test_no_renderer_import(self):
        """Test drift_formula.py does not import renderer modules."""
        import symbolu.core.predictive.persona_drift.drift_formula as module
        source = inspect.getsource(module)
        assert "renderer" not in source.lower()
        assert "dha_engine" not in source.lower()


# ============================================================================
# GROUP F — REGRESSION LOCK (5 tests)
# ============================================================================


class TestGroupF_RegressionLock:
    """Group F: Tests for graceful fallback with missing data."""

    def test_graceful_fallback_no_history(self):
        """Test graceful fallback when no history available."""
        result = run_p35_directly(
            drift_fusion_index=0.5,
            schema_drift=0.3,
        )

        assert result is not None
        assert result.trend_direction == "stable"  # Default when no history
        assert result.confidence == 0.5  # Moderate confidence without history

    def test_graceful_fallback_partial_inputs(self):
        """Test graceful fallback with partial inputs."""
        result = run_p35_directly(
            drift_fusion_index=0.5,
            # Other inputs missing
        )

        assert result is not None
        assert 0.0 <= result.predicted_drift_score <= 1.0

    def test_graceful_fallback_all_none_returns_none(self):
        """Test returns None when all inputs are None."""
        result = run_p35_directly(
            drift_fusion_index=None,
            schema_drift=None,
            temporal_entropy_diff=None,
            coherence_v3_quality=None,
            ucf_score=None,
        )

        assert result is None

    def test_graceful_fallback_empty_context(self):
        """Test graceful fallback with empty context."""
        ctx = MockPipelineContext()
        result = maybe_run_p35(ctx)

        # Should return None or handle gracefully
        # Empty context has no coherence_state, p18, p19, p33
        assert result is None

    def test_graceful_fallback_partial_history(self):
        """Test graceful fallback with partial history."""
        result = run_p35_directly(
            drift_fusion_index=0.5,
            schema_drift=0.3,
            drift_fusion_index_history=[0.4, 0.5],  # Only 2 values
            schema_drift_history=[0.2],  # Only 1 value
        )

        assert result is not None
        assert result.trend_direction in ("stable", "worsening", "improving")


# ============================================================================
# ADDITIONAL TESTS — Contributing Factors (5 tests)
# ============================================================================


class TestContributingFactors:
    """Tests for contributing factor detection."""

    def test_schema_instability_detected(self):
        """Test SCHEMA_INSTABILITY is detected when threshold exceeded."""
        factors = compute_contributing_factors(
            drift_fusion_index=0.5,
            schema_drift=0.55,  # >= 0.50
            temporal_entropy_diff=0.3,
            coherence_v3_quality=0.7,
            ucf_score=0.8,
            identity_harmonics_score=0.7,
        )
        assert "SCHEMA_INSTABILITY" in factors

    def test_temporal_entropy_rising_detected(self):
        """Test TEMPORAL_ENTROPY_RISING is detected when threshold exceeded."""
        factors = compute_contributing_factors(
            drift_fusion_index=0.5,
            schema_drift=0.3,
            temporal_entropy_diff=0.60,  # >= 0.55
            coherence_v3_quality=0.7,
            ucf_score=0.8,
            identity_harmonics_score=0.7,
        )
        assert "TEMPORAL_ENTROPY_RISING" in factors

    def test_coherence_decay_detected(self):
        """Test COHERENCE_DECAY is detected when quality below threshold."""
        factors = compute_contributing_factors(
            drift_fusion_index=0.5,
            schema_drift=0.3,
            temporal_entropy_diff=0.3,
            coherence_v3_quality=0.40,  # < 0.45
            ucf_score=0.8,
            identity_harmonics_score=0.7,
        )
        assert "COHERENCE_DECAY" in factors

    def test_identity_harmonics_weakening_detected(self):
        """Test IDENTITY_HARMONICS_WEAKENING is detected when below threshold."""
        factors = compute_contributing_factors(
            drift_fusion_index=0.5,
            schema_drift=0.3,
            temporal_entropy_diff=0.3,
            coherence_v3_quality=0.7,
            ucf_score=0.8,
            identity_harmonics_score=0.40,  # < 0.45
        )
        assert "IDENTITY_HARMONICS_WEAKENING" in factors

    def test_cross_signal_volatility_detected(self):
        """Test CROSS_SIGNAL_VOLATILITY is detected when variance high."""
        factors = compute_contributing_factors(
            drift_fusion_index=0.5,
            schema_drift=0.3,
            temporal_entropy_diff=0.3,
            coherence_v3_quality=0.7,
            ucf_score=0.8,
            identity_harmonics_score=0.7,
            signal_variance=0.15,  # > 0.10
        )
        assert "CROSS_SIGNAL_VOLATILITY" in factors


# ============================================================================
# ADDITIONAL TESTS — Integration Functions (5 tests)
# ============================================================================


class TestIntegrationFunctions:
    """Tests for pipeline integration functions."""

    def test_maybe_run_p35_attaches_report(self):
        """Test maybe_run_p35 attaches report to context."""
        ctx = MockPipelineContext(
            p19=MockP19(drift_fusion_index=0.5),
            coherence_state=MockCoherenceState(drift_fusion_index=0.5),
        )

        result = maybe_run_p35(ctx)

        assert result is not None
        assert ctx.p35 is not None
        assert ctx.p35 == result

    def test_p35_disabled_skips_computation(self):
        """Test P35 skips when disabled."""
        ctx = MockPipelineContext(
            p19=MockP19(drift_fusion_index=0.5),
            coherence_state=MockCoherenceState(drift_fusion_index=0.5),
            _p35_disabled=True,
        )

        result = maybe_run_p35(ctx)

        assert result is None

    def test_get_p35_report_returns_none_when_absent(self):
        """Test get_p35_report returns None when no report."""
        ctx = MockPipelineContext()
        assert get_p35_report(ctx) is None

    def test_helper_functions_default_values(self):
        """Test helper functions return defaults when no report."""
        ctx = MockPipelineContext()

        assert get_predicted_drift_score(ctx) == 0.0
        assert get_drift_risk_band(ctx) == "low"
        assert get_trend_direction(ctx) == "stable"
        assert get_contributing_factors(ctx) == []
        assert get_confidence(ctx) == 0.5
        assert is_low_risk(ctx) is True
        assert is_moderate_risk(ctx) is False
        assert is_high_risk(ctx) is False

    def test_get_p35_version(self):
        """Test get_p35_version returns correct version."""
        assert get_p35_version() == P35_VERSION
        assert get_p35_version() == "1.0.0"


# ============================================================================
# ADDITIONAL TESTS — Report Serialization (3 tests)
# ============================================================================


class TestReportSerialization:
    """Tests for report serialization."""

    def test_to_dict_contains_all_fields(self):
        """Test to_dict contains all expected fields."""
        report = create_report(
            predicted_drift_score=0.5,
            drift_risk_band="moderate",
            trend_direction="stable",
            contributing_factors=["SCHEMA_INSTABILITY"],
            confidence=0.8,
            drift_fusion_index=0.5,
            schema_drift=0.3,
        )

        d = report.to_dict()

        assert "predicted_drift_score" in d
        assert "drift_risk_band" in d
        assert "trend_direction" in d
        assert "forecast_horizon" in d
        assert "contributing_factors" in d
        assert "confidence" in d
        assert "inputs" in d
        assert "observer_only" in d

    def test_to_dict_inputs_section(self):
        """Test to_dict has correct inputs section."""
        report = create_report(
            predicted_drift_score=0.5,
            drift_risk_band="moderate",
            trend_direction="stable",
            contributing_factors=[],
            confidence=0.8,
            drift_fusion_index=0.5,
            schema_drift=0.3,
            temporal_entropy_diff=0.4,
        )

        d = report.to_dict()
        inputs = d["inputs"]

        assert inputs["drift_fusion_index"] == 0.5
        assert inputs["schema_drift"] == 0.3
        assert inputs["temporal_entropy_diff"] == 0.4

    def test_create_empty_report(self):
        """Test create_empty_report returns valid empty report."""
        report = create_empty_report()

        assert report.predicted_drift_score == 0.0
        assert report.drift_risk_band == "low"
        assert report.trend_direction == "stable"
        assert len(report.contributing_factors) == 0
        assert report.confidence == 0.0
        assert report.observer_only is True


# ============================================================================
# ADDITIONAL TESTS — Variance Computation (2 tests)
# ============================================================================


class TestVarianceComputation:
    """Tests for variance computation."""

    def test_compute_variance_empty_list(self):
        """Test variance of empty list is 0."""
        assert compute_variance([]) == 0.0

    def test_compute_variance_single_value(self):
        """Test variance of single value is 0."""
        assert compute_variance([0.5]) == 0.0

    def test_compute_variance_multiple_values(self):
        """Test variance computation with multiple values."""
        variance = compute_variance([0.4, 0.5, 0.6])
        # Mean = 0.5
        # Variance = ((0.4-0.5)^2 + (0.5-0.5)^2 + (0.6-0.5)^2) / 3
        # = (0.01 + 0 + 0.01) / 3 = 0.02/3 ≈ 0.00667
        expected = (0.01 + 0.0 + 0.01) / 3
        assert abs(variance - expected) < 1e-10


# Run tests if executed directly
if __name__ == "__main__":
    pytest.main([__file__, "-v"])
