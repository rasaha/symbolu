"""
Phase 38 - Temporal Coherence Forecasting Tests

Test suite for P38 with focused tests organized into groups:

Group A - Determinism (3 tests)
    - Same inputs produce same outputs

Group B - Boundary Clamp (3 tests)
    - Values clamped to [0.0, 1.0]

Group C - Trend Classification (4 tests)
    - Improving/stable/declining classification

Group D - Confidence Scaling (3 tests)
    - Confidence based on history count

Group E - Import Safety (3 tests)
    - No forbidden dependencies

Group F - Regression/Non-Interference (3 tests)
    - P38 values do not affect downstream behavior

INVARIANTS TESTED:
    - INV-P38-1: Forecast never influences current decisions
    - INV-P38-2: Forecast never escalates authority
    - INV-P38-3: Observer-only behavior enforced
    - INV-P38-4: Deterministic math only
    - INV-P38-5: No acoustic dependency
    - INV-P38-6: Monotonic safety
"""

import inspect
import pytest
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

from symbolu.mechanical.pipeline.p38_temporal_forecast import (
    P38_VERSION,
    Phase38TemporalForecast,
    W_CURRENT_QUALITY,
    W_HISTORY_MEAN,
    W_DRIFT_FUSION,
    W_TEMPORAL_ENTROPY,
    TREND_IMPROVING_THRESHOLD,
    TREND_DECLINING_THRESHOLD,
    CONFIDENCE_HISTORY_DIVISOR,
    clamp,
    compute_history_mean,
    compute_forecast_score,
    classify_trend,
    compute_confidence,
    resolve_forecast,
    maybe_run_p38,
    run_p38_directly,
    is_p38_disabled,
    has_p38_forecast,
    get_p38_forecast,
    get_forecast_score,
    get_forecast_trend,
    get_forecast_confidence,
    is_forecast_improving,
    is_forecast_stable,
    is_forecast_declining,
    get_p38_version,
    create_forecast,
    create_empty_forecast,
)


# ============================================================================
# TEST FIXTURES
# ============================================================================


@dataclass
class MockCoherenceState:
    """Mock coherence state for testing."""
    coherence_v3_quality: Optional[float] = None
    drift_fusion_index: Optional[float] = None
    coherence_v3_quality_history: Optional[List[float]] = None


@dataclass
class MockP18:
    """Mock P18 report for testing."""
    delta_entropy: float = 0.0


@dataclass
class MockP19:
    """Mock P19 report for testing."""
    drift_fusion_index: float = 0.5


@dataclass
class MockPipelineContext:
    """Mock pipeline context for testing."""
    coherence_state: Optional[MockCoherenceState] = None
    coherence_history: Optional[List[Any]] = None
    p18: Optional[MockP18] = None
    p19: Optional[MockP19] = None
    p38: Optional[Phase38TemporalForecast] = None
    phase12_quality: Optional[float] = None
    phase18_temporal_entropy_diff: Optional[float] = None
    phase19_drift_fusion_index: Optional[float] = None
    _p38_disabled: bool = False

    # Upstream phases that P38 should NOT modify
    p6_regime: Optional[Any] = None
    p7_discourse_envelope: Optional[Any] = None
    semantic_frame: Optional[Any] = None
    lexical_frame: Optional[Any] = None


# ============================================================================
# GROUP A - DETERMINISM TESTS
# ============================================================================


class TestGroupA_Determinism:
    """Group A: Tests for deterministic behavior (INV-P38-4)."""

    def test_same_inputs_same_output_forecast_score(self):
        """Test identical inputs produce identical forecast scores."""
        inputs = {
            "current_quality": 0.7,
            "history_mean": 0.65,
            "drift_fusion_index": 0.3,
            "temporal_entropy_diff": 0.4,
        }

        score1 = compute_forecast_score(**inputs)
        score2 = compute_forecast_score(**inputs)

        assert score1 == score2

    def test_same_inputs_same_output_full_forecast(self):
        """Test identical inputs produce identical forecasts."""
        result1 = run_p38_directly(
            current_quality=0.7,
            coherence_history=[0.6, 0.65, 0.68],
            drift_fusion_index=0.3,
            temporal_entropy_diff=0.4,
        )
        result2 = run_p38_directly(
            current_quality=0.7,
            coherence_history=[0.6, 0.65, 0.68],
            drift_fusion_index=0.3,
            temporal_entropy_diff=0.4,
        )

        assert result1.forecast_score == result2.forecast_score
        assert result1.forecast_trend == result2.forecast_trend
        assert result1.confidence == result2.confidence

    def test_multiple_runs_identical_results(self):
        """Test multiple runs produce identical results."""
        results = []
        for _ in range(10):
            result = run_p38_directly(
                current_quality=0.75,
                coherence_history=[0.7, 0.72, 0.74],
                drift_fusion_index=0.25,
                temporal_entropy_diff=0.35,
            )
            results.append(result.forecast_score)

        # All results should be identical
        assert len(set(results)) == 1


# ============================================================================
# GROUP B - BOUNDARY CLAMP TESTS
# ============================================================================


class TestGroupB_BoundaryClamp:
    """Group B: Tests for boundary clamping."""

    def test_clamp_within_range(self):
        """Test clamp keeps values within range."""
        assert clamp(0.5) == 0.5
        assert clamp(0.0) == 0.0
        assert clamp(1.0) == 1.0

    def test_clamp_below_min(self):
        """Test clamp handles values below minimum."""
        assert clamp(-0.5) == 0.0
        assert clamp(-1.0) == 0.0
        assert clamp(-100.0) == 0.0

    def test_clamp_above_max(self):
        """Test clamp handles values above maximum."""
        assert clamp(1.5) == 1.0
        assert clamp(2.0) == 1.0
        assert clamp(100.0) == 1.0

    def test_forecast_score_always_clamped(self):
        """Test forecast score is always in [0.0, 1.0]."""
        # High stability inputs (score should be close to 1.0)
        result_high = run_p38_directly(
            current_quality=1.0,
            coherence_history=[1.0, 1.0, 1.0],
            drift_fusion_index=0.0,
            temporal_entropy_diff=0.0,
        )
        assert 0.0 <= result_high.forecast_score <= 1.0

        # Low stability inputs (score should be close to 0.0)
        result_low = run_p38_directly(
            current_quality=0.0,
            coherence_history=[0.0, 0.0, 0.0],
            drift_fusion_index=1.0,
            temporal_entropy_diff=1.0,
        )
        assert 0.0 <= result_low.forecast_score <= 1.0


# ============================================================================
# GROUP C - TREND CLASSIFICATION TESTS
# ============================================================================


class TestGroupC_TrendClassification:
    """Group C: Tests for trend classification."""

    def test_trend_stable_when_close(self):
        """Test stable trend when forecast close to current."""
        # forecast_score close to current_quality (within 0.05)
        trend = classify_trend(forecast_score=0.72, current_quality=0.70)
        assert trend == "stable"

    def test_trend_improving_when_higher(self):
        """Test improving trend when forecast significantly higher."""
        # forecast_score > current_quality + 0.05
        trend = classify_trend(forecast_score=0.80, current_quality=0.70)
        assert trend == "improving"

    def test_trend_declining_when_lower(self):
        """Test declining trend when forecast significantly lower."""
        # forecast_score < current_quality - 0.05
        trend = classify_trend(forecast_score=0.60, current_quality=0.70)
        assert trend == "declining"

    def test_trend_thresholds_are_correct(self):
        """Test trend thresholds are exactly 0.05."""
        assert TREND_IMPROVING_THRESHOLD == 0.05
        assert TREND_DECLINING_THRESHOLD == 0.05


# ============================================================================
# GROUP D - CONFIDENCE SCALING TESTS
# ============================================================================


class TestGroupD_ConfidenceScaling:
    """Group D: Tests for confidence scaling based on history."""

    def test_confidence_zero_with_no_history(self):
        """Test confidence is 0 when no history."""
        confidence = compute_confidence(history_count=0)
        assert confidence == 0.0

    def test_confidence_scales_with_history(self):
        """Test confidence scales linearly with history count."""
        assert compute_confidence(1) == 0.2  # 1/5
        assert compute_confidence(2) == 0.4  # 2/5
        assert compute_confidence(3) == 0.6  # 3/5
        assert compute_confidence(4) == 0.8  # 4/5
        assert compute_confidence(5) == 1.0  # 5/5

    def test_confidence_caps_at_one(self):
        """Test confidence caps at 1.0 for history >= 5."""
        assert compute_confidence(5) == 1.0
        assert compute_confidence(10) == 1.0
        assert compute_confidence(100) == 1.0


# ============================================================================
# GROUP E - IMPORT SAFETY TESTS
# ============================================================================


class TestGroupE_ImportSafety:
    """Group E: Tests for import safety - no forbidden dependencies (INV-P38-5)."""

    def test_no_acoustic_imports_in_schema(self):
        """Test p38_schema.py does not import acoustic modules."""
        import symbolu.mechanical.pipeline.p38_temporal_forecast.p38_schema as module
        source = inspect.getsource(module)
        # Check for actual import statements (look for "from ... import" or "import ..." patterns)
        import_lines = [line for line in source.split("\n") if line.strip().startswith(("from ", "import "))]
        import_text = "\n".join(import_lines).lower()
        assert "p22_acoustic" not in import_text
        assert "p10_acoustic" not in import_text
        assert "p13_acoustic" not in import_text

    def test_no_governance_imports_in_resolver(self):
        """Test p38_resolver.py does not import governance/renderer modules."""
        import symbolu.mechanical.pipeline.p38_temporal_forecast.p38_resolver as module
        source = inspect.getsource(module)
        # Check for actual import statements
        import_lines = [line for line in source.split("\n") if line.strip().startswith(("from ", "import "))]
        import_text = "\n".join(import_lines).lower()
        assert "renderer" not in import_text
        assert "dha_engine" not in import_text
        assert "persona_engine" not in import_text

    def test_no_observer_imports(self):
        """Test P38 does not import observer modules like P22, P23, P24."""
        import symbolu.mechanical.pipeline.p38_temporal_forecast.p38_integration as module
        source = inspect.getsource(module)
        # Check for actual import statements
        import_lines = [line for line in source.split("\n") if line.strip().startswith(("from ", "import "))]
        import_text = "\n".join(import_lines).lower()
        assert "p22_acoustic_witness" not in import_text
        assert "p23_alignment" not in import_text
        assert "p24_projection" not in import_text


# ============================================================================
# GROUP F - REGRESSION / NON-INTERFERENCE TESTS
# ============================================================================


class TestGroupF_RegressionNonInterference:
    """Group F: Tests proving P38 does not affect downstream behavior (INV-P38-1)."""

    def test_p38_does_not_modify_upstream_phases(self):
        """Test P38 does not modify upstream phase envelopes."""
        ctx = MockPipelineContext(
            coherence_state=MockCoherenceState(coherence_v3_quality=0.7),
            p6_regime="test_regime",
            p7_discourse_envelope="test_discourse",
            semantic_frame="test_semantic",
            lexical_frame="test_lexical",
        )

        # Store original values
        original_p6 = ctx.p6_regime
        original_p7 = ctx.p7_discourse_envelope
        original_semantic = ctx.semantic_frame
        original_lexical = ctx.lexical_frame

        # Run P38
        maybe_run_p38(ctx)

        # Verify nothing was modified
        assert ctx.p6_regime == original_p6
        assert ctx.p7_discourse_envelope == original_p7
        assert ctx.semantic_frame == original_semantic
        assert ctx.lexical_frame == original_lexical

    def test_different_p38_same_downstream(self):
        """Test two contexts with identical authoritative phases but different P38 values."""
        # Create two contexts with same authoritative data
        ctx1 = MockPipelineContext(
            coherence_state=MockCoherenceState(coherence_v3_quality=0.7),
            p6_regime="same_regime",
            p7_discourse_envelope="same_discourse",
        )
        ctx2 = MockPipelineContext(
            coherence_state=MockCoherenceState(coherence_v3_quality=0.5),
            p6_regime="same_regime",
            p7_discourse_envelope="same_discourse",
        )

        # Run P38 on both (will produce different P38 values)
        maybe_run_p38(ctx1)
        maybe_run_p38(ctx2)

        # P38 values should be different
        assert ctx1.p38.forecast_score != ctx2.p38.forecast_score

        # But authoritative phases should be identical
        assert ctx1.p6_regime == ctx2.p6_regime
        assert ctx1.p7_discourse_envelope == ctx2.p7_discourse_envelope

    def test_observer_only_always_true(self):
        """Test observer_only is always True and cannot be False."""
        # Valid creation
        forecast = create_forecast(
            forecast_score=0.7,
            forecast_trend="stable",
            confidence=0.8,
        )
        assert forecast.observer_only is True

        # Invalid creation should raise
        with pytest.raises(ValueError, match="observer_only must be True"):
            Phase38TemporalForecast(
                forecast_score=0.7,
                forecast_trend="stable",
                confidence=0.8,
                observer_only=False,
            )


# ============================================================================
# ADDITIONAL TESTS - Formula Weights
# ============================================================================


class TestFormulaWeights:
    """Tests for formula weight validation."""

    def test_weights_sum_to_one(self):
        """Test that formula weights sum to 1.0."""
        total = W_CURRENT_QUALITY + W_HISTORY_MEAN + W_DRIFT_FUSION + W_TEMPORAL_ENTROPY
        assert abs(total - 1.0) < 1e-10, f"Weights sum to {total}, expected 1.0"

    def test_weight_values_correct(self):
        """Test individual weight values are correct."""
        assert W_CURRENT_QUALITY == 0.40
        assert W_HISTORY_MEAN == 0.30
        assert W_DRIFT_FUSION == 0.20
        assert W_TEMPORAL_ENTROPY == 0.10


# ============================================================================
# ADDITIONAL TESTS - History Mean
# ============================================================================


class TestHistoryMean:
    """Tests for history mean computation."""

    def test_history_mean_empty_list(self):
        """Test history mean returns 0.5 for empty list."""
        assert compute_history_mean([]) == 0.5

    def test_history_mean_single_value(self):
        """Test history mean with single value."""
        assert compute_history_mean([0.8]) == 0.8

    def test_history_mean_uses_last_three(self):
        """Test history mean uses last 3 values."""
        history = [0.5, 0.6, 0.7, 0.8, 0.9]
        # Should use [0.7, 0.8, 0.9]
        expected = (0.7 + 0.8 + 0.9) / 3
        assert abs(compute_history_mean(history) - expected) < 1e-10


# ============================================================================
# ADDITIONAL TESTS - Integration Functions
# ============================================================================


class TestIntegrationFunctions:
    """Tests for pipeline integration functions."""

    def test_maybe_run_p38_attaches_forecast(self):
        """Test maybe_run_p38 attaches forecast to context."""
        ctx = MockPipelineContext(
            coherence_state=MockCoherenceState(coherence_v3_quality=0.7),
        )

        result = maybe_run_p38(ctx)

        assert result is not None
        assert ctx.p38 is not None
        assert ctx.p38 == result

    def test_p38_disabled_skips_computation(self):
        """Test P38 skips when disabled."""
        ctx = MockPipelineContext(
            coherence_state=MockCoherenceState(coherence_v3_quality=0.7),
            _p38_disabled=True,
        )

        result = maybe_run_p38(ctx)

        assert result is None

    def test_returns_none_without_current_quality(self):
        """Test returns None when current_quality is missing."""
        ctx = MockPipelineContext()
        result = maybe_run_p38(ctx)
        assert result is None

    def test_helper_functions_defaults(self):
        """Test helper functions return sensible defaults when no forecast."""
        ctx = MockPipelineContext()

        assert get_forecast_score(ctx) == 0.5
        assert get_forecast_trend(ctx) == "stable"
        assert get_forecast_confidence(ctx) == 0.0
        assert is_forecast_improving(ctx) is False
        assert is_forecast_stable(ctx) is True
        assert is_forecast_declining(ctx) is False


# ============================================================================
# ADDITIONAL TESTS - Schema Validation
# ============================================================================


class TestSchemaValidation:
    """Tests for schema validation."""

    def test_forecast_score_must_be_valid(self):
        """Test forecast_score must be in [0.0, 1.0]."""
        with pytest.raises(ValueError):
            Phase38TemporalForecast(
                forecast_score=1.5,
                forecast_trend="stable",
                confidence=0.5,
            )

    def test_confidence_must_be_valid(self):
        """Test confidence must be in [0.0, 1.0]."""
        with pytest.raises(ValueError):
            Phase38TemporalForecast(
                forecast_score=0.5,
                forecast_trend="stable",
                confidence=1.5,
            )

    def test_trend_must_be_valid(self):
        """Test trend must be a valid value."""
        with pytest.raises(ValueError):
            Phase38TemporalForecast(
                forecast_score=0.5,
                forecast_trend="invalid_trend",
                confidence=0.5,
            )

    def test_horizon_must_be_near(self):
        """Test horizon must be 'near'."""
        with pytest.raises(ValueError):
            Phase38TemporalForecast(
                forecast_score=0.5,
                forecast_trend="stable",
                confidence=0.5,
                horizon="far",
            )

    def test_to_dict_serialization(self):
        """Test to_dict produces valid serialization."""
        forecast = create_forecast(
            forecast_score=0.75,
            forecast_trend="stable",
            confidence=0.8,
            current_quality=0.7,
            history_mean=0.72,
        )

        d = forecast.to_dict()

        assert d["forecast_score"] == 0.75
        assert d["forecast_trend"] == "stable"
        assert d["confidence"] == 0.8
        assert d["horizon"] == "near"
        assert d["observer_only"] is True
        assert d["inputs"]["current_quality"] == 0.7
        assert d["inputs"]["history_mean"] == 0.72

    def test_version_is_correct(self):
        """Test version is 1.0.0."""
        assert P38_VERSION == "1.0.0"
        assert get_p38_version() == "1.0.0"


# ============================================================================
# ADDITIONAL TESTS - Empty Forecast
# ============================================================================


class TestEmptyForecast:
    """Tests for empty forecast creation."""

    def test_create_empty_forecast(self):
        """Test create_empty_forecast returns valid default forecast."""
        forecast = create_empty_forecast()

        assert forecast.forecast_score == 0.5
        assert forecast.forecast_trend == "stable"
        assert forecast.confidence == 0.0
        assert forecast.horizon == "near"
        assert forecast.observer_only is True


# Run tests if executed directly
if __name__ == "__main__":
    pytest.main([__file__, "-v"])
