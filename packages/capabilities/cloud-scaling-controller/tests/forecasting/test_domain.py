"""Correction C: input+output SignalDomain enforcement reusing the Phase-1 authority."""

from __future__ import annotations

import pytest

import fc_helpers as fx
from ugence_cloud_scaling_controller.canonical import (
    CanonicalCapacityState, CapacityState, InfrastructureState, Measurement, Unit,
    MeasurementError, unit_domain,
)
from ugence_cloud_scaling_controller.canonical.state import StateError
from ugence_cloud_scaling_controller.forecasting import (
    AbstentionReason,
    AdmissionPolicy,
    CanonicalCapacitySeries,
    ForecastHorizon,
    ForecastTarget,
    LinearTrendForecaster,
    PersistenceForecaster,
    REPLICAS_UNIT,
    SignalDomain,
    UncertaintyConfig,
    UncertaintyMethod,
    domain_for,
    forecast_with_evidence,
)

NONE_UC = UncertaintyConfig(method=UncertaintyMethod.NONE)


# ---- authority reuse / no divergent duplicate bounds -----------------------------

def test_signal_domain_sourced_from_unit_domain_authority():
    for u in (Unit.PERCENT, Unit.RATIO, Unit.RATE, Unit.COUNT, Unit.MILLISECONDS):
        d = domain_for(u.value)
        a = unit_domain(u)
        assert (d.lower, d.upper, d.integer) == (a.lower, a.upper, a.integer)
    rep = domain_for(REPLICAS_UNIT)
    assert (rep.lower, rep.upper, rep.integer) == (0.0, None, True)


def test_measurement_bounds_agree_with_unit_domain():
    # A representative grid: Measurement accepts iff the authoritative domain contains it.
    cases = [
        (Unit.PERCENT, [-1.0, 0.0, 50.0, 100.0, 101.0]),
        (Unit.RATIO, [-0.1, 0.0, 0.5, 1.0, 1.1]),
        (Unit.RATE, [-0.1, 0.0, 1.0, 1.1]),
        (Unit.COUNT, [-1.0, 0.0, 3.0, 3.5]),
        (Unit.MILLISECONDS, [-1.0, 0.0, 12.5]),
    ]
    for unit, values in cases:
        dom = unit_domain(unit)
        for v in values:
            ok = dom.contains(v)
            try:
                Measurement(v, unit)
                built = True
            except MeasurementError:
                built = False
            assert built == ok, (unit, v, built, ok)


# ---- integer semantics -----------------------------------------------------------

def test_integer_domain_rejects_fractional():
    rep = domain_for(REPLICAS_UNIT)
    assert rep.contains(3.0) is True
    assert rep.contains(3.5) is False   # fractional in an integer domain is OUT of domain
    assert rep.contains(-1.0) is False


def test_fractional_running_replica_observation_fails_closed():
    with pytest.raises(StateError):
        CapacityState(running_replicas=3.5)   # Phase-1 authority: replicas are integer counts


def test_fractional_running_replica_forecast_abstains_by_default():
    subj = fx.subject()
    states = [fx.replicas_state(fx.at(60 * i), 3 + i, subj=subj) for i in range(5)]  # 3..7
    s = CanonicalCapacitySeries.build(states)
    # 90s horizon over a slope of 1 replica / 60s => +1.5 => 8.5 (fractional, out of integer domain).
    ev = forecast_with_evidence(
        s, ForecastTarget.RUNNING_REPLICAS, s.end_event_time, ForecastHorizon(90.0),
        LinearTrendForecaster(), normalization_policy=fx.cpu_norm_policy(), uncertainty_config=NONE_UC,
    )
    assert ev.forecast.is_abstained
    assert ev.forecast.abstention_reason is AbstentionReason.FORECAST_OUTSIDE_DOMAIN


def test_integer_domain_forecast_retained_when_integer_valued():
    subj = fx.subject()
    states = [fx.replicas_state(fx.at(60 * i), 3 + i, subj=subj) for i in range(5)]
    s = CanonicalCapacitySeries.build(states)
    # 60s horizon => +1 => integer 8, in-domain.
    ev = forecast_with_evidence(
        s, ForecastTarget.RUNNING_REPLICAS, s.end_event_time, ForecastHorizon(60.0),
        LinearTrendForecaster(), normalization_policy=fx.cpu_norm_policy(), uncertainty_config=NONE_UC,
    )
    assert ev.forecast.is_forecast
    assert abs(ev.forecast.point_estimate - 8.0) < 1e-6


# ---- output-domain bounds (per target) + evidence binding ------------------------

def test_percent_forecast_below_zero_abstains_and_is_evidence_bound():
    s = CanonicalCapacitySeries.build(fx.cpu_series_states([50.0, 40.0, 30.0, 20.0, 10.0]))
    ev = forecast_with_evidence(
        s, ForecastTarget.CPU_UTILIZATION, s.end_event_time, ForecastHorizon.minutes(60),
        LinearTrendForecaster(), normalization_policy=fx.cpu_norm_policy(), uncertainty_config=NONE_UC,
    )
    assert ev.forecast.abstention_reason is AbstentionReason.FORECAST_OUTSIDE_DOMAIN
    assert ev.digest().startswith("sha256:")   # abstention is evidence-producing + digest-bound


def test_out_of_domain_retained_only_with_explicit_policy():
    s = CanonicalCapacitySeries.build(fx.cpu_series_states([50.0, 40.0, 30.0, 20.0, 10.0]))
    ev = forecast_with_evidence(
        s, ForecastTarget.CPU_UTILIZATION, s.end_event_time, ForecastHorizon.minutes(60),
        LinearTrendForecaster(), normalization_policy=fx.cpu_norm_policy(), uncertainty_config=NONE_UC,
        admission_policy=AdmissionPolicy(allow_out_of_domain=True),
    )
    assert ev.forecast.is_forecast
    assert any("outside the admissible" in w for w in ev.forecast.warnings)


def test_domain_never_clamps_or_rounds():
    # An out-of-domain forecast is reported/abstained, never coerced into [0, 100].
    s = CanonicalCapacitySeries.build(fx.cpu_series_states([50.0, 40.0, 30.0, 20.0, 10.0]))
    ev = forecast_with_evidence(
        s, ForecastTarget.CPU_UTILIZATION, s.end_event_time, ForecastHorizon.minutes(60),
        LinearTrendForecaster(), normalization_policy=fx.cpu_norm_policy(), uncertainty_config=NONE_UC,
        admission_policy=AdmissionPolicy(allow_out_of_domain=True),
    )
    assert ev.forecast.point_estimate < 0.0   # preserved exactly, not clamped to 0
