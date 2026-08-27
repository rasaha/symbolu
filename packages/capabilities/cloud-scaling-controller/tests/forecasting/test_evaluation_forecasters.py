"""Arms N and H: behaviour, ratified resolvability, and abstention precedence.

Unit tests use a **scaled period** (one hour standing in for one day, with the bin counts
scaled to match) so a full multi-period window is a few hundred samples rather than ten
thousand. The mathematics is period-agnostic; one test at the real 86,400-second period
confirms that, and the bounded integration fixture exercises the chronology.
"""

from __future__ import annotations

import math
from datetime import datetime, timedelta, timezone

import pytest

import fc_helpers as fx
from ugence_cloud_scaling_controller.forecasting import (
    AbstentionReason,
    AdmissionPolicy,
    CanonicalCapacitySeries,
    DAILY_PERIOD_SECONDS,
    FeatureConfig,
    ForecastHorizon,
    ForecastTarget,
    HarmonicPhaseForecaster,
    LinearTrendForecaster,
    PersistenceForecaster,
    SeasonalNaiveForecaster,
    UncertaintyConfig,
    UncertaintyMethod,
    build_input_window,
    forecast_with_evidence,
)
from ugence_cloud_scaling_controller.forecasting.evaluation_forecasters import (
    MAX_GAP_SECONDS,
    MAX_P95_GAP_SECONDS,
    MIN_CYCLE_SPAN_SECONDS,
    MIN_DAYS_WITH_COVERAGE,
    MIN_OCCUPIED_BINS,
    PHASE_BINS,
)
from ugence_cloud_scaling_controller.forecasting.forecasters import ForecasterError

T0 = fx.T0
CAD = 60.0

# Scaled analogue of the ratified configuration: period 3600 s, 12 phase bins (300 s each,
# so a 60 s cadence fills every bin), 11 of 12 bins on 6 of 7 periods.
SCALED = dict(
    period_seconds=3600.0,
    min_cycle_span_seconds=7 * 3600.0 - CAD,
    phase_bins=12,
    min_occupied_bins=11,
    min_days_with_coverage=6,
    lookback_days=7,
)


def _h(**over):
    cfg = dict(SCALED)
    cfg.update(over)
    return HarmonicPhaseForecaster(cfg)


def _n(**over):
    cfg = {"period_seconds": 3600.0, "match_tolerance_seconds": 5.0}
    cfg.update(over)
    return SeasonalNaiveForecaster(cfg)


def _harmonic_series(periods=7, cadence=CAD, period=3600.0, level=50.0, slope=0.0,
                     amp_cos=10.0, amp_sin=4.0, drop=()):
    """Deterministic daily-shaped series; ``drop`` removes sample indices to open gaps."""
    times, values = [], []
    n = int(periods * period / cadence) + 1
    for i in range(n):
        if i in drop:
            continue
        t = T0 + timedelta(seconds=cadence * i)
        e = t.timestamp()
        phi = 2.0 * math.pi * ((e % period) / period)
        values.append(level + slope * (e - T0.timestamp())
                      + amp_cos * math.cos(phi) + amp_sin * math.sin(phi))
        times.append(t)
    return times, values


def _truth(t, period=3600.0, level=50.0, slope=0.0, amp_cos=10.0, amp_sin=4.0):
    e = t.timestamp()
    phi = 2.0 * math.pi * ((e % period) / period)
    return level + slope * (e - T0.timestamp()) + amp_cos * math.cos(phi) + amp_sin * math.sin(phi)


# ------------------------------------------------------------------------------ identities
def test_model_identities_are_exactly_the_ratified_ids():
    assert PersistenceForecaster().model_id == "persistence"
    assert LinearTrendForecaster().model_id == "linear_trend"
    assert SeasonalNaiveForecaster().model_id == "seasonal_naive"
    assert HarmonicPhaseForecaster().model_id == "harmonic_phase"


def test_thresholds_are_part_of_the_model_config_digest():
    """A run cannot quietly relax a ratified threshold without changing model identity."""
    a = HarmonicPhaseForecaster()
    b = HarmonicPhaseForecaster({"max_gap_seconds": MAX_GAP_SECONDS * 2})
    assert a.config_digest() != b.config_digest()


def test_default_thresholds_are_the_ratified_values():
    assert (MIN_CYCLE_SPAN_SECONDS, MAX_P95_GAP_SECONDS, MAX_GAP_SECONDS) == (604740.0, 120.0, 900.0)
    assert (PHASE_BINS, MIN_OCCUPIED_BINS, MIN_DAYS_WITH_COVERAGE) == (96, 90, 6)
    assert DAILY_PERIOD_SECONDS == 86400.0


# ------------------------------------------------------------------------------------- H
def test_harmonic_recovers_a_pure_harmonic_exactly():
    times, values = _harmonic_series()
    target = times[-1] + timedelta(seconds=900)
    got = _h().predict_from(times, values, target)
    assert got == pytest.approx(_truth(target), abs=1e-9)


def test_harmonic_recovers_harmonic_plus_trend():
    times, values = _harmonic_series(slope=0.001)
    target = times[-1] + timedelta(seconds=900)
    got = _h().predict_from(times, values, target)
    assert got == pytest.approx(_truth(target, slope=0.001), abs=1e-9)


def test_harmonic_works_at_the_real_daily_period():
    """The scaled unit fixtures are a speed device, not a different model."""
    times, values = _harmonic_series(periods=7, cadence=CAD, period=DAILY_PERIOD_SECONDS,
                                     slope=2e-5)
    target = times[-1] + timedelta(seconds=3600)
    got = HarmonicPhaseForecaster().predict_from(times, values, target)
    assert got == pytest.approx(_truth(target, period=DAILY_PERIOD_SECONDS, slope=2e-5), abs=1e-6)


def test_harmonic_is_deterministic():
    times, values = _harmonic_series()
    target = times[-1] + timedelta(seconds=900)
    f = _h()
    assert f.predict_from(times, values, target) == f.predict_from(times, values, target)
    assert _h().predict_from(times, values, target) == f.predict_from(times, values, target)


def test_harmonic_centring_origin_makes_u_zero_at_the_target():
    """u is centred on forecast_for, so the constant term carries the level there."""
    times, values = _harmonic_series(slope=0.002)
    target = times[-1] + timedelta(seconds=1800)
    row = _h()._design_row(target, target.timestamp())
    assert row[0] == 1.0 and row[1] == 0.0


# --------------------------------------------------------------- resolvability precedence
def test_short_span_is_insufficient_cycle_coverage():
    times, values = _harmonic_series(periods=1)
    assert _h().resolvability_failure(times) is AbstentionReason.INSUFFICIENT_CYCLE_COVERAGE
    assert _h().predict_from(times, values, times[-1] + timedelta(seconds=60)) is None


def test_too_few_samples_is_insufficient_cycle_coverage():
    times, values = _harmonic_series(periods=7)
    assert _h().resolvability_failure(times[:3]) is AbstentionReason.INSUFFICIENT_CYCLE_COVERAGE


def test_deficient_phase_bin_coverage_is_insufficient_cycle_coverage():
    """Dense on average, blind over part of the cycle — span alone must not admit it."""
    times, values = [], []
    period, n = 3600.0, int(7 * 3600 / CAD) + 1
    for i in range(n):
        t = T0 + timedelta(seconds=CAD * i)
        # keep only the first third of each period: bins 0-3 of 12 are occupied
        if (t.timestamp() % period) >= period / 3:
            continue
        times.append(t)
        values.append(_truth(t))
    assert (times[-1] - times[0]).total_seconds() >= SCALED["min_cycle_span_seconds"]
    assert _h().resolvability_failure(times) is AbstentionReason.INSUFFICIENT_CYCLE_COVERAGE


def test_excessive_maximum_gap_is_period_not_resolvable():
    # Drop 16 consecutive samples (a 17-minute outage) from one period: one bin is lost, so
    # bin coverage still passes (11 of 12), and the max-gap rule is what fires.
    times, values = _harmonic_series(drop=tuple(range(200, 216)))
    gaps = [(b - a).total_seconds() for a, b in zip(times, times[1:])]
    assert max(gaps) > MAX_GAP_SECONDS
    assert _h().resolvability_failure(times) is AbstentionReason.PERIOD_NOT_RESOLVABLE


def test_excessive_p95_gap_is_period_not_resolvable():
    times, values = _harmonic_series(cadence=300.0, period=3600.0)
    f = _h(min_cycle_span_seconds=7 * 3600.0 - 300.0)
    assert f.resolvability_failure(times) is AbstentionReason.PERIOD_NOT_RESOLVABLE


def test_precedence_reports_span_before_gaps():
    """Several conditions failing at once must not let the reported reason be chosen."""
    times, values = _harmonic_series(periods=1, drop=tuple(range(20, 40)))
    assert _h().resolvability_failure(times) is AbstentionReason.INSUFFICIENT_CYCLE_COVERAGE


def test_rank_failure_is_period_not_resolvable():
    """A degenerate design (all samples at one phase) cannot identify the harmonic."""
    times, values = [], []
    for i in range(400):
        t = T0 + timedelta(seconds=3600.0 * i)  # every sample at phase 0
        times.append(t)
        values.append(10.0)
    f = _h(max_p95_gap_seconds=1e9, max_gap_seconds=1e9, min_occupied_bins=1,
           min_days_with_coverage=1)
    assert f.resolvability_failure(times) is None       # sampling rules deliberately relaxed
    assert f.predict_from(times, values, times[-1] + timedelta(seconds=60)) is None


def test_conditioning_ceiling_rejects_an_ill_posed_fit():
    times, values = _harmonic_series()
    strict = _h(max_condition_number=1.0)  # nothing real can satisfy this
    assert strict.predict_from(times, values, times[-1] + timedelta(seconds=60)) is None


def test_no_detrend_then_accumulate_variant_exists():
    """The joint fit is the only estimator here; no accumulator shortcut is offered."""
    names = dir(HarmonicPhaseForecaster)
    assert not any("accumul" in n.lower() or "detrend" in n.lower() for n in names)


# ------------------------------------------------------------------------------------- N
def test_seasonal_naive_returns_the_value_one_period_earlier():
    times, values = _harmonic_series()
    target = times[-1] + timedelta(seconds=60)
    expected_at = target - timedelta(seconds=3600)
    idx = times.index(expected_at)
    assert _n().predict_from(times, values, target) == values[idx]


def test_seasonal_naive_declines_when_no_sample_is_within_tolerance():
    times, values = _harmonic_series()
    # Ask for a target whose lagged instant falls in a hole we punch out.
    target = times[-1] + timedelta(seconds=60)
    lag = target - timedelta(seconds=3600)
    keep = [(t, v) for t, v in zip(times, values) if abs((t - lag).total_seconds()) > 30]
    ts = [t for t, _ in keep]
    vs = [v for _, v in keep]
    assert _n().predict_from(ts, vs, target) is None


def test_seasonal_naive_never_interpolates():
    """Declining is the point: a stand-in would make the control look better than the data."""
    times = [T0, T0 + timedelta(seconds=3600 - 100), T0 + timedelta(seconds=3600 + 100)]
    values = [1.0, 2.0, 3.0]
    assert _n().predict_from(times, values, T0 + timedelta(seconds=2 * 3600)) is None


def test_seasonal_naive_rejects_bad_configuration():
    with pytest.raises(ForecasterError):
        SeasonalNaiveForecaster({"period_seconds": 0})
    with pytest.raises(ForecasterError):
        SeasonalNaiveForecaster({"match_tolerance_seconds": -1})


# ------------------------------------------------------------ arms share the same skeleton
def test_all_four_arms_share_target_and_horizon_support():
    arms = [PersistenceForecaster(), LinearTrendForecaster(), _n(), _h()]
    targets = {frozenset(a.supported_targets()) for a in arms}
    assert len(targets) == 1
    for a in arms:
        assert a.supports_horizon(ForecastHorizon(300.0))


def test_arms_have_distinct_identities():
    ids = {a.model_id for a in [PersistenceForecaster(), LinearTrendForecaster(), _n(), _h()]}
    assert ids == {"persistence", "linear_trend", "seasonal_naive", "harmonic_phase"}


# ------------------------------------------------- typed abstentions through the service
def _states(times, values):
    return [fx.cpu_state(t, v) for t, v in zip(times, values)]


def _evidence(times, values, forecaster, horizon_seconds=60.0):
    states = _states(times, values)
    series = CanonicalCapacitySeries.build(states)
    return forecast_with_evidence(
        series, ForecastTarget.CPU_UTILIZATION, states[-1].observed_at,
        ForecastHorizon(horizon_seconds), forecaster,
        normalization_policy=fx.cpu_norm_policy(),
        feature_config=FeatureConfig(lookback_seconds=7 * 3600.0 + 600.0,
                                     expected_cadence_seconds=CAD),
        admission_policy=AdmissionPolicy(require_regular_cadence=False,
                                         max_staleness_seconds=None),
        uncertainty_config=UncertaintyConfig(method=UncertaintyMethod.NONE),
    )


def test_service_reports_insufficient_cycle_coverage():
    times, values = _harmonic_series(periods=1)
    ev = _evidence(times, values, _h())
    assert ev.forecast.status == "abstained"
    assert ev.forecast.abstention_reason is AbstentionReason.INSUFFICIENT_CYCLE_COVERAGE


def test_service_reports_period_not_resolvable():
    times, values = _harmonic_series(drop=tuple(range(200, 216)))
    ev = _evidence(times, values, _h())
    assert ev.forecast.status == "abstained"
    assert ev.forecast.abstention_reason is AbstentionReason.PERIOD_NOT_RESOLVABLE


def test_service_still_reports_insufficient_history_for_plain_forecasters():
    """The default decline reason is unchanged for every shipped forecaster."""
    times, values = _harmonic_series(periods=1)
    ev = _evidence(times[:1], values[:1], LinearTrendForecaster())
    assert ev.forecast.abstention_reason is AbstentionReason.INSUFFICIENT_HISTORY


def test_decline_reason_is_pure():
    times, values = _harmonic_series(periods=1)
    states = _states(times, values)
    series = CanonicalCapacitySeries.build(states)
    window = build_input_window(series, ForecastTarget.CPU_UTILIZATION,
                                states[-1].observed_at, ForecastHorizon(60.0),
                                FeatureConfig(lookback_seconds=7 * 3600.0 + 600.0,
                                              expected_cadence_seconds=CAD))
    f = _h()
    first = f.decline_reason(window)
    assert first is f.decline_reason(window)  # no memory of the previous call
    assert f.point_estimate(window) is None
    assert f.decline_reason(window) is first
