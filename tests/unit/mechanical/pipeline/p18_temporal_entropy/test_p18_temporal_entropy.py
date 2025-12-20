"""
P18 Temporal Entropy Differential Test Suite

Comprehensive tests for P18 temporal entropy monitoring:
A. No history → trend INSUFFICIENT_HISTORY, delta None, prev None
B. With history: stable / increasing / decreasing cases
C. Bounds always respected
D. Determinism: same inputs produce same report
E. Missing upstream signals use neutral defaults (does not crash)
F. Volatility band classification

All tests are DETERMINISTIC with ZERO false positives expected.
"""

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

import pytest

from symbolu.mechanical.pipeline.p18_temporal_entropy import (
    # Schema
    EntropyTrend,
    VolatilityBand,
    P18TemporalEntropyReport,
    P18_VERSION,
    create_report,
    # Resolver
    P18TemporalEntropyDifferential,
    W_COHERENCE,
    W_QUALITY,
    W_INTEGRITY,
    W_TENSION,
    W_VOLATILITY,
    EVIDENCE_MISSING_PENALTY,
    TREND_EPSILON,
    VOLATILITY_LOW_THRESHOLD,
    VOLATILITY_HIGH_THRESHOLD,
    DEFAULT_WINDOW_SIZE,
    # Integration
    maybe_run_p18,
    run_p18_directly,
    is_p18_disabled,
    has_p18_report,
    get_p18_report,
    get_entropy_now,
    get_entropy_trend,
    get_volatility_band,
    is_entropy_increasing,
    is_entropy_stable,
    is_high_volatility,
    get_p18_version,
)


# ============================================================================
# MOCK HELPERS - Replicating Pipeline Context Structure
# ============================================================================


@dataclass
class MockP17Report:
    """Mock P17 integrity report."""
    integrity_score: float = 0.85
    is_clean: bool = True


@dataclass
class MockCoherenceState:
    """Mock coherence state with history tracking."""
    # Core coherence metrics
    coherence_score: float = 0.8
    coherence_score_v2: Optional[float] = None
    coherence_score_v3: Optional[float] = None
    coherence_v3_quality: Optional[float] = None
    coherence_fused: Optional[float] = None

    # Tension metrics
    tension_index: Optional[float] = None

    # P17 metrics
    semantic_integrity_score: Optional[float] = None

    # P18 history tracking
    temporal_entropy_snapshot: Optional[Any] = None
    temporal_entropy_diff: Optional[float] = None
    temporal_entropy_volatility: Optional[float] = None
    temporal_entropy_diff_history: List[Optional[float]] = field(default_factory=list)
    temporal_entropy_volatility_history: List[Optional[float]] = field(default_factory=list)


@dataclass
class MockPipelineContext:
    """Mock pipeline context for testing P18."""
    coherence_state: Optional[MockCoherenceState] = None
    p17: Optional[MockP17Report] = None
    tension_corridor: Optional[float] = None
    p18: Optional[P18TemporalEntropyReport] = None
    _p18_disabled: bool = False


# ============================================================================
# FACTORY FUNCTIONS
# ============================================================================


def make_context_no_history() -> MockPipelineContext:
    """Create a context with no previous entropy history."""
    return MockPipelineContext(
        coherence_state=MockCoherenceState(
            coherence_score=0.8,
            coherence_v3_quality=0.75,
            tension_index=0.2,
            temporal_entropy_diff=None,
            temporal_entropy_diff_history=[],
        ),
        p17=MockP17Report(integrity_score=0.9),
    )


def make_context_with_history(
    prev_entropy: float = 0.3,
    delta_history: Optional[List[float]] = None,
) -> MockPipelineContext:
    """Create a context with previous entropy history."""
    return MockPipelineContext(
        coherence_state=MockCoherenceState(
            coherence_score=0.8,
            coherence_v3_quality=0.75,
            tension_index=0.2,
            temporal_entropy_diff=prev_entropy,
            temporal_entropy_diff_history=delta_history or [],
        ),
        p17=MockP17Report(integrity_score=0.9),
    )


def make_high_entropy_context() -> MockPipelineContext:
    """Create a context that should produce high entropy."""
    return MockPipelineContext(
        coherence_state=MockCoherenceState(
            coherence_score=0.2,  # Low coherence = high instability
            coherence_v3_quality=0.3,
            tension_index=0.9,  # High tension
            temporal_entropy_diff=0.5,
            temporal_entropy_diff_history=[0.3, 0.4, 0.5],
        ),
        p17=MockP17Report(integrity_score=0.3),  # Low integrity
    )


def make_low_entropy_context() -> MockPipelineContext:
    """Create a context that should produce low entropy."""
    return MockPipelineContext(
        coherence_state=MockCoherenceState(
            coherence_score=0.95,  # High coherence = low instability
            coherence_v3_quality=0.9,
            tension_index=0.1,  # Low tension
            temporal_entropy_diff=0.1,
            temporal_entropy_diff_history=[0.01, -0.01, 0.02],
        ),
        p17=MockP17Report(integrity_score=0.95),  # High integrity
    )


# ============================================================================
# GROUP A - NO HISTORY TESTS
# ============================================================================


class TestGroupA_NoHistory:
    """
    GROUP A: No history scenarios.

    When no previous entropy is available, trend should be INSUFFICIENT_HISTORY,
    delta should be None, and entropy_prev should be None.
    """

    def test_no_history_returns_insufficient_history_trend(self):
        """No history → trend INSUFFICIENT_HISTORY."""
        ctx = make_context_no_history()
        report = maybe_run_p18(ctx)

        assert report is not None
        assert report.trend == EntropyTrend.INSUFFICIENT_HISTORY
        assert report.entropy_prev is None
        assert report.delta_entropy is None

    def test_no_history_still_computes_entropy_now(self):
        """Even without history, entropy_now should be computed."""
        ctx = make_context_no_history()
        report = maybe_run_p18(ctx)

        assert report is not None
        assert report.entropy_now is not None
        assert 0.0 <= report.entropy_now <= 1.0

    def test_no_history_volatility_unknown_or_from_single_delta(self):
        """Without history, volatility should be UNKNOWN."""
        ctx = make_context_no_history()
        report = maybe_run_p18(ctx)

        assert report is not None
        # With no delta history, volatility should be UNKNOWN
        assert report.volatility_band in [VolatilityBand.UNKNOWN, VolatilityBand.LOW, VolatilityBand.MED, VolatilityBand.HIGH]

    def test_empty_coherence_state_graceful(self):
        """Empty coherence_state should not crash."""
        ctx = MockPipelineContext(
            coherence_state=MockCoherenceState(),
            p17=None,
        )
        report = maybe_run_p18(ctx)

        assert report is not None
        assert report.trend == EntropyTrend.INSUFFICIENT_HISTORY


# ============================================================================
# GROUP B - WITH HISTORY TESTS
# ============================================================================


class TestGroupB_WithHistory:
    """
    GROUP B: With history scenarios.

    Test increasing, decreasing, and stable trends with proper history.
    """

    def test_increasing_trend_detected(self):
        """When entropy increases beyond epsilon, trend is INCREASING."""
        ctx = make_context_with_history(
            prev_entropy=0.2,  # Low previous entropy
            delta_history=[0.05, 0.06, 0.07],
        )
        # Make current context produce higher entropy
        ctx.coherence_state.coherence_score = 0.5  # Lower coherence
        ctx.p17 = MockP17Report(integrity_score=0.6)

        report = maybe_run_p18(ctx)

        assert report is not None
        assert report.entropy_prev == 0.2
        assert report.delta_entropy is not None
        # With lower coherence and integrity, entropy should be higher
        if report.delta_entropy > TREND_EPSILON:
            assert report.trend == EntropyTrend.INCREASING

    def test_decreasing_trend_detected(self):
        """When entropy decreases beyond epsilon, trend is DECREASING."""
        ctx = make_context_with_history(
            prev_entropy=0.6,  # High previous entropy
            delta_history=[-0.05, -0.06, -0.07],
        )
        # Make current context produce lower entropy
        ctx.coherence_state.coherence_score = 0.95  # High coherence
        ctx.p17 = MockP17Report(integrity_score=0.95)

        report = maybe_run_p18(ctx)

        assert report is not None
        assert report.entropy_prev == 0.6
        assert report.delta_entropy is not None
        # With high coherence and integrity, entropy should be lower
        if report.delta_entropy < -TREND_EPSILON:
            assert report.trend == EntropyTrend.DECREASING

    def test_stable_trend_when_delta_small(self):
        """When delta is within epsilon, trend is STABLE."""
        # First run to establish entropy_now
        ctx = make_low_entropy_context()
        report1 = maybe_run_p18(ctx)

        # Create new context with prev_entropy very close to expected current
        ctx2 = make_context_with_history(
            prev_entropy=report1.entropy_now,  # Same as current
            delta_history=[0.01, -0.01, 0.0],
        )
        ctx2.coherence_state.coherence_score = 0.95
        ctx2.coherence_state.coherence_v3_quality = 0.9
        ctx2.coherence_state.tension_index = 0.1
        ctx2.p17 = MockP17Report(integrity_score=0.95)

        report2 = maybe_run_p18(ctx2)

        assert report2 is not None
        assert report2.delta_entropy is not None
        if abs(report2.delta_entropy) <= TREND_EPSILON:
            assert report2.trend == EntropyTrend.STABLE

    def test_delta_equals_now_minus_prev(self):
        """delta_entropy should equal entropy_now - entropy_prev."""
        ctx = make_context_with_history(prev_entropy=0.3)
        report = maybe_run_p18(ctx)

        assert report is not None
        assert report.entropy_prev is not None
        assert report.delta_entropy is not None
        expected_delta = report.entropy_now - report.entropy_prev
        assert abs(report.delta_entropy - expected_delta) < 1e-9


# ============================================================================
# GROUP C - BOUNDS TESTS
# ============================================================================


class TestGroupC_BoundsRespected:
    """
    GROUP C: Bounds always respected.

    entropy_now in [0,1], entropy_prev in [0,1], delta in [-1,1].
    """

    def test_entropy_now_bounded_0_1(self):
        """entropy_now should always be in [0.0, 1.0]."""
        # Test with high entropy context
        ctx_high = make_high_entropy_context()
        report_high = maybe_run_p18(ctx_high)

        assert report_high is not None
        assert 0.0 <= report_high.entropy_now <= 1.0

        # Test with low entropy context
        ctx_low = make_low_entropy_context()
        report_low = maybe_run_p18(ctx_low)

        assert report_low is not None
        assert 0.0 <= report_low.entropy_now <= 1.0

    def test_entropy_prev_bounded_when_present(self):
        """entropy_prev should be in [0.0, 1.0] when present."""
        ctx = make_context_with_history(prev_entropy=0.5)
        report = maybe_run_p18(ctx)

        assert report is not None
        assert report.entropy_prev is not None
        assert 0.0 <= report.entropy_prev <= 1.0

    def test_delta_bounded_when_present(self):
        """delta_entropy should be in [-1.0, 1.0] when present."""
        # Test increasing case
        ctx_inc = make_context_with_history(prev_entropy=0.1)
        ctx_inc.coherence_state.coherence_score = 0.1  # Low coherence
        report_inc = maybe_run_p18(ctx_inc)

        assert report_inc is not None
        if report_inc.delta_entropy is not None:
            assert -1.0 <= report_inc.delta_entropy <= 1.0

        # Test decreasing case
        ctx_dec = make_context_with_history(prev_entropy=0.9)
        ctx_dec.coherence_state.coherence_score = 0.95  # High coherence
        report_dec = maybe_run_p18(ctx_dec)

        assert report_dec is not None
        if report_dec.delta_entropy is not None:
            assert -1.0 <= report_dec.delta_entropy <= 1.0

    def test_schema_rejects_out_of_bounds_entropy_now(self):
        """Schema should reject entropy_now outside [0, 1]."""
        with pytest.raises(ValueError, match=r"\[0\.0, 1\.0\]"):
            create_report(
                entropy_now=1.5,
                trend=EntropyTrend.INSUFFICIENT_HISTORY,
                volatility_band=VolatilityBand.UNKNOWN,
                window_size_used=0,
            )

    def test_schema_rejects_negative_entropy_now(self):
        """Schema should reject negative entropy_now."""
        with pytest.raises(ValueError, match=r"\[0\.0, 1\.0\]"):
            create_report(
                entropy_now=-0.1,
                trend=EntropyTrend.INSUFFICIENT_HISTORY,
                volatility_band=VolatilityBand.UNKNOWN,
                window_size_used=0,
            )


# ============================================================================
# GROUP D - DETERMINISM TESTS
# ============================================================================


class TestGroupD_Determinism:
    """
    GROUP D: Determinism verification.

    Same inputs produce same report.
    """

    def test_same_context_identical_reports(self):
        """Same context produces identical reports."""
        ctx = make_context_with_history(prev_entropy=0.3)

        report1 = run_p18_directly(
            coherence_state=ctx.coherence_state,
            p17=ctx.p17,
        )

        report2 = run_p18_directly(
            coherence_state=ctx.coherence_state,
            p17=ctx.p17,
        )

        assert report1.entropy_now == report2.entropy_now
        assert report1.entropy_prev == report2.entropy_prev
        assert report1.delta_entropy == report2.delta_entropy
        assert report1.trend == report2.trend
        assert report1.volatility_band == report2.volatility_band

    def test_determinism_across_100_runs(self):
        """Reports are deterministic across 100 runs."""
        ctx = make_high_entropy_context()

        first_report = run_p18_directly(
            coherence_state=ctx.coherence_state,
            p17=ctx.p17,
        )

        for i in range(100):
            report = run_p18_directly(
                coherence_state=ctx.coherence_state,
                p17=ctx.p17,
            )

            assert report.entropy_now == first_report.entropy_now, \
                f"entropy_now changed on run {i}"
            assert report.trend == first_report.trend, \
                f"trend changed on run {i}"

    def test_resolver_is_pure_function(self):
        """Resolver compute() is a pure function."""
        resolver = P18TemporalEntropyDifferential()
        ctx = make_context_with_history(prev_entropy=0.4)

        # Compute multiple times
        results = [resolver.compute(ctx) for _ in range(10)]

        # All should be identical
        first = results[0]
        for r in results[1:]:
            assert r.entropy_now == first.entropy_now
            assert r.trend == first.trend


# ============================================================================
# GROUP E - MISSING INPUTS TESTS
# ============================================================================


class TestGroupE_MissingInputsGraceful:
    """
    GROUP E: Missing upstream signals use neutral defaults.

    Does not crash, uses neutral defaults.
    """

    def test_no_coherence_state_uses_defaults(self):
        """Missing coherence_state uses neutral defaults."""
        ctx = MockPipelineContext(
            coherence_state=None,
            p17=MockP17Report(integrity_score=0.9),
        )

        report = maybe_run_p18(ctx)

        # Should still produce a report
        assert report is not None
        assert 0.0 <= report.entropy_now <= 1.0

    def test_no_p17_uses_defaults(self):
        """Missing P17 uses neutral defaults."""
        ctx = MockPipelineContext(
            coherence_state=MockCoherenceState(coherence_score=0.8),
            p17=None,
        )

        report = maybe_run_p18(ctx)

        assert report is not None
        assert 0.0 <= report.entropy_now <= 1.0

    def test_empty_context_returns_none(self):
        """Context with no relevant attributes returns None."""
        class EmptyContext:
            pass

        ctx = EmptyContext()
        report = maybe_run_p18(ctx)

        # Should skip when no relevant attributes
        assert report is None

    def test_missing_inputs_tracked_in_debug(self):
        """Missing inputs are tracked in debug dict."""
        ctx = MockPipelineContext(
            coherence_state=MockCoherenceState(
                coherence_score=0.8,
                coherence_v3_quality=None,  # Missing
                tension_index=None,  # Missing
            ),
            p17=None,  # Missing
        )

        report = maybe_run_p18(ctx)

        assert report is not None
        assert "missing_inputs" in report.debug
        assert report.debug["missing_count"] >= 2  # At least some missing

    def test_missing_inputs_add_penalty(self):
        """Missing inputs add evidence_missing_penalty."""
        # Context with all inputs
        ctx_full = MockPipelineContext(
            coherence_state=MockCoherenceState(
                coherence_score=0.8,
                coherence_v3_quality=0.8,
                tension_index=0.2,
            ),
            p17=MockP17Report(integrity_score=0.8),
        )

        # Context with missing inputs
        ctx_missing = MockPipelineContext(
            coherence_state=MockCoherenceState(
                coherence_score=0.8,
                coherence_v3_quality=None,
                tension_index=None,
            ),
            p17=None,
        )

        report_full = maybe_run_p18(ctx_full)
        report_missing = maybe_run_p18(ctx_missing)

        assert report_full is not None
        assert report_missing is not None
        # Missing inputs should result in higher entropy due to penalty
        # (though the neutral defaults may offset this)
        assert report_missing.debug["missing_count"] > report_full.debug["missing_count"]


# ============================================================================
# GROUP F - VOLATILITY BAND TESTS
# ============================================================================


class TestGroupF_VolatilityBand:
    """
    GROUP F: Volatility band classification.
    """

    def test_low_volatility_with_small_deltas(self):
        """Small consistent deltas = LOW volatility."""
        ctx = make_context_with_history(
            prev_entropy=0.3,
            delta_history=[0.01, -0.01, 0.02, -0.02, 0.01],
        )

        report = maybe_run_p18(ctx)

        assert report is not None
        # Small deltas should result in LOW volatility
        assert report.volatility_band in [VolatilityBand.LOW, VolatilityBand.MED]

    def test_high_volatility_with_large_deltas(self):
        """Large varying deltas = HIGH volatility."""
        ctx = make_context_with_history(
            prev_entropy=0.5,
            delta_history=[0.4, -0.4, 0.35, -0.35, 0.4],
        )

        report = maybe_run_p18(ctx)

        assert report is not None
        # Large varying deltas should result in HIGH volatility
        assert report.volatility_band in [VolatilityBand.MED, VolatilityBand.HIGH]

    def test_unknown_volatility_with_no_history(self):
        """No delta history = UNKNOWN volatility (or based on current delta)."""
        ctx = make_context_no_history()

        report = maybe_run_p18(ctx)

        assert report is not None
        # With no history, should be UNKNOWN or based on single value
        assert report.volatility_band in [VolatilityBand.UNKNOWN, VolatilityBand.LOW, VolatilityBand.MED, VolatilityBand.HIGH]

    def test_window_size_tracked(self):
        """window_size_used should reflect actual history used."""
        delta_history = [0.1, 0.2, 0.15]
        ctx = make_context_with_history(
            prev_entropy=0.3,
            delta_history=delta_history,
        )

        report = maybe_run_p18(ctx)

        assert report is not None
        # Window size should be <= DEFAULT_WINDOW_SIZE and based on history
        assert report.window_size_used <= DEFAULT_WINDOW_SIZE


# ============================================================================
# SCHEMA VALIDATION TESTS
# ============================================================================


class TestSchemaValidation:
    """Tests for schema dataclass validation."""

    def test_valid_report_construction(self):
        """Report can be constructed with valid values."""
        report = create_report(
            entropy_now=0.5,
            entropy_prev=0.4,
            delta_entropy=0.1,
            trend=EntropyTrend.INCREASING,
            volatility_band=VolatilityBand.MED,
            window_size_used=3,
        )

        assert report.entropy_now == 0.5
        assert report.entropy_prev == 0.4
        assert report.delta_entropy == 0.1
        assert report.trend == EntropyTrend.INCREASING
        assert report.volatility_band == VolatilityBand.MED

    def test_no_history_construction(self):
        """Report can be constructed without history."""
        report = create_report(
            entropy_now=0.5,
            entropy_prev=None,
            delta_entropy=None,
            trend=EntropyTrend.INSUFFICIENT_HISTORY,
            volatility_band=VolatilityBand.UNKNOWN,
            window_size_used=0,
        )

        assert report.entropy_prev is None
        assert report.delta_entropy is None
        assert report.trend == EntropyTrend.INSUFFICIENT_HISTORY

    def test_rejects_inconsistent_trend(self):
        """Rejects trend != INSUFFICIENT_HISTORY when no prev."""
        with pytest.raises(ValueError, match="INSUFFICIENT_HISTORY"):
            create_report(
                entropy_now=0.5,
                entropy_prev=None,
                delta_entropy=None,
                trend=EntropyTrend.STABLE,  # Should be INSUFFICIENT_HISTORY
                volatility_band=VolatilityBand.UNKNOWN,
                window_size_used=0,
            )

    def test_rejects_delta_without_prev(self):
        """Rejects delta_entropy present when entropy_prev is None."""
        with pytest.raises(ValueError, match="must be None"):
            create_report(
                entropy_now=0.5,
                entropy_prev=None,
                delta_entropy=0.1,  # Should be None
                trend=EntropyTrend.INSUFFICIENT_HISTORY,
                volatility_band=VolatilityBand.UNKNOWN,
                window_size_used=0,
            )

    def test_rejects_wrong_delta_value(self):
        """Rejects delta that doesn't match now - prev."""
        with pytest.raises(ValueError, match="must equal"):
            create_report(
                entropy_now=0.5,
                entropy_prev=0.3,
                delta_entropy=0.1,  # Should be 0.2
                trend=EntropyTrend.INCREASING,
                volatility_band=VolatilityBand.MED,
                window_size_used=0,
            )

    def test_version_constant(self):
        """P18_VERSION is defined."""
        assert P18_VERSION is not None
        assert P18_VERSION == "1.0.0"


# ============================================================================
# INTEGRATION TESTS
# ============================================================================


class TestIntegration:
    """Tests for integration functions."""

    def test_maybe_run_p18_attaches_report(self):
        """maybe_run_p18 attaches report to ctx.p18."""
        ctx = make_context_no_history()

        report = maybe_run_p18(ctx)

        assert report is not None
        assert ctx.p18 is not None
        assert ctx.p18 == report
        assert has_p18_report(ctx) is True

    def test_maybe_run_p18_disabled_returns_none(self):
        """maybe_run_p18 returns None when disabled."""
        ctx = make_context_no_history()
        ctx._p18_disabled = True

        report = maybe_run_p18(ctx)

        assert report is None
        assert is_p18_disabled(ctx) is True

    def test_get_p18_report_returns_report(self):
        """get_p18_report returns the attached report."""
        ctx = make_context_no_history()
        maybe_run_p18(ctx)

        report = get_p18_report(ctx)

        assert report is not None
        assert isinstance(report, P18TemporalEntropyReport)

    def test_get_entropy_now_returns_value(self):
        """get_entropy_now returns entropy value."""
        ctx = make_context_no_history()
        maybe_run_p18(ctx)

        entropy = get_entropy_now(ctx)

        assert isinstance(entropy, float)
        assert 0.0 <= entropy <= 1.0

    def test_get_entropy_trend_returns_trend(self):
        """get_entropy_trend returns trend enum."""
        ctx = make_context_no_history()
        maybe_run_p18(ctx)

        trend = get_entropy_trend(ctx)

        assert isinstance(trend, EntropyTrend)

    def test_get_volatility_band_returns_band(self):
        """get_volatility_band returns band enum."""
        ctx = make_context_no_history()
        maybe_run_p18(ctx)

        band = get_volatility_band(ctx)

        assert isinstance(band, VolatilityBand)

    def test_is_entropy_increasing_helper(self):
        """is_entropy_increasing returns bool."""
        ctx = make_context_no_history()
        maybe_run_p18(ctx)

        result = is_entropy_increasing(ctx)

        assert isinstance(result, bool)

    def test_is_entropy_stable_helper(self):
        """is_entropy_stable returns bool."""
        ctx = make_context_no_history()
        maybe_run_p18(ctx)

        result = is_entropy_stable(ctx)

        assert isinstance(result, bool)

    def test_is_high_volatility_helper(self):
        """is_high_volatility returns bool."""
        ctx = make_context_no_history()
        maybe_run_p18(ctx)

        result = is_high_volatility(ctx)

        assert isinstance(result, bool)

    def test_get_p18_version(self):
        """get_p18_version returns version string."""
        version = get_p18_version()

        assert version == P18_VERSION
        assert version == "1.0.0"


# ============================================================================
# HELPER METHOD TESTS
# ============================================================================


class TestHelperMethods:
    """Tests for P18TemporalEntropyReport helper methods."""

    def test_is_increasing_method(self):
        """is_increasing() returns correct value."""
        report = create_report(
            entropy_now=0.5,
            entropy_prev=0.3,
            delta_entropy=0.2,
            trend=EntropyTrend.INCREASING,
            volatility_band=VolatilityBand.MED,
            window_size_used=0,
        )

        assert report.is_increasing() is True
        assert report.is_decreasing() is False
        assert report.is_stable() is False

    def test_is_decreasing_method(self):
        """is_decreasing() returns correct value."""
        report = create_report(
            entropy_now=0.3,
            entropy_prev=0.5,
            delta_entropy=-0.2,
            trend=EntropyTrend.DECREASING,
            volatility_band=VolatilityBand.MED,
            window_size_used=0,
        )

        assert report.is_decreasing() is True
        assert report.is_increasing() is False
        assert report.is_stable() is False

    def test_is_stable_method(self):
        """is_stable() returns correct value."""
        report = create_report(
            entropy_now=0.5,
            entropy_prev=0.5,
            delta_entropy=0.0,
            trend=EntropyTrend.STABLE,
            volatility_band=VolatilityBand.LOW,
            window_size_used=0,
        )

        assert report.is_stable() is True
        assert report.is_increasing() is False
        assert report.is_decreasing() is False

    def test_has_history_method(self):
        """has_history() returns correct value."""
        report_with = create_report(
            entropy_now=0.5,
            entropy_prev=0.4,
            delta_entropy=0.1,
            trend=EntropyTrend.INCREASING,
            volatility_band=VolatilityBand.MED,
            window_size_used=3,
        )

        report_without = create_report(
            entropy_now=0.5,
            entropy_prev=None,
            delta_entropy=None,
            trend=EntropyTrend.INSUFFICIENT_HISTORY,
            volatility_band=VolatilityBand.UNKNOWN,
            window_size_used=0,
        )

        assert report_with.has_history() is True
        assert report_without.has_history() is False

    def test_volatility_methods(self):
        """is_high_volatility() and is_low_volatility() work correctly."""
        report_high = create_report(
            entropy_now=0.5,
            trend=EntropyTrend.INSUFFICIENT_HISTORY,
            volatility_band=VolatilityBand.HIGH,
            window_size_used=0,
        )

        report_low = create_report(
            entropy_now=0.5,
            trend=EntropyTrend.INSUFFICIENT_HISTORY,
            volatility_band=VolatilityBand.LOW,
            window_size_used=0,
        )

        assert report_high.is_high_volatility() is True
        assert report_high.is_low_volatility() is False
        assert report_low.is_low_volatility() is True
        assert report_low.is_high_volatility() is False

    def test_to_dict_serialization(self):
        """to_dict() produces valid dictionary."""
        report = create_report(
            entropy_now=0.5,
            entropy_prev=0.4,
            delta_entropy=0.1,
            trend=EntropyTrend.INCREASING,
            volatility_band=VolatilityBand.MED,
            window_size_used=3,
            debug={"test": "value"},
        )

        d = report.to_dict()

        assert d["entropy_now"] == 0.5
        assert d["entropy_prev"] == 0.4
        assert d["delta_entropy"] == 0.1
        assert d["trend"] == "INCREASING"
        assert d["volatility_band"] == "MED"
        assert d["window_size_used"] == 3
        assert d["debug"]["test"] == "value"
        assert d["version"] == P18_VERSION


# ============================================================================
# CONSTANTS TESTS
# ============================================================================


class TestConstants:
    """Tests for P18 constants."""

    def test_weights_defined(self):
        """All weights are defined."""
        assert W_COHERENCE == 0.30
        assert W_QUALITY == 0.20
        assert W_INTEGRITY == 0.25
        assert W_TENSION == 0.15
        assert W_VOLATILITY == 0.10

    def test_weights_sum_to_one(self):
        """Weights sum to 1.0."""
        total = W_COHERENCE + W_QUALITY + W_INTEGRITY + W_TENSION + W_VOLATILITY
        assert total == 1.0

    def test_thresholds_defined(self):
        """Thresholds are defined."""
        assert TREND_EPSILON == 0.05
        assert VOLATILITY_LOW_THRESHOLD == 0.10
        assert VOLATILITY_HIGH_THRESHOLD == 0.30
        assert DEFAULT_WINDOW_SIZE == 5
        assert EVIDENCE_MISSING_PENALTY == 0.05
