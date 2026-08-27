"""Correction D: every typed AbstentionReason is reachable through a supported service path."""

from __future__ import annotations

from datetime import timedelta

import pytest

import fc_helpers as fx
from ugence_cloud_scaling_controller.canonical import (
    CanonicalCapacityState, CapacityState, InfrastructureState, Measurement, Unit,
)
from ugence_cloud_scaling_controller.forecasting import (
    AbstentionReason,
    AdmissionPolicy,
    FeatureConfig,
    HarmonicPhaseForecaster,
    CanonicalCapacitySeries,
    ForecastHorizon,
    ForecastTarget,
    ForecastValueSpace,
    LinearTrendForecaster,
    PersistenceForecaster,
    UncertaintyConfig,
    UncertaintyMethod,
    forecast_from_observations,
    forecast_with_evidence,
)

H1 = ForecastHorizon(60.0)
NPOL = fx.cpu_norm_policy()
NONE_UC = UncertaintyConfig(method=UncertaintyMethod.NONE)


class LimitedForecaster(PersistenceForecaster):
    def supported_targets(self):
        return frozenset({ForecastTarget.CPU_UTILIZATION})

    def supports_horizon(self, horizon):
        return horizon.seconds <= 600.0


class NonFiniteForecaster(PersistenceForecaster):
    """A (supported) custom forecaster whose point is non-finite — exercises the guard."""
    model_id = "nonfinite-test"

    def _predict(self, event_times, values, forecast_for):
        return float("nan")


def _series(values, **kw):
    return CanonicalCapacitySeries.build(fx.cpu_series_states(values, **kw))


def _fw(series, target=ForecastTarget.CPU_UTILIZATION, *, horizon=H1, forecaster=None,
        npol=NPOL, admission=None, uncertainty=None, expected_subject=None, cutoff=None,
        forecast_space=ForecastValueSpace.PROJECTED_WITHOUT_CONVERSION):
    return forecast_with_evidence(
        series, target, cutoff if cutoff is not None else series.end_event_time, horizon,
        forecaster or PersistenceForecaster(), normalization_policy=npol,
        admission_policy=admission, uncertainty_config=uncertainty or NONE_UC,
        expected_subject=expected_subject, forecast_space=forecast_space,
    )


def _reason(ev):
    assert ev.forecast.is_abstained, "expected an abstention"
    return ev.forecast.abstention_reason


# One supported-path constructor per reason.

def test_insufficient_history():
    assert _reason(_fw(_series([10.0, 20.0]), forecaster=LinearTrendForecaster())) is AbstentionReason.INSUFFICIENT_HISTORY


def test_stale_history():
    s = _series([10.0, 20.0, 30.0])
    ev = _fw(s, cutoff=s.end_event_time + timedelta(seconds=400))
    assert _reason(ev) is AbstentionReason.STALE_HISTORY


def test_excessive_missingness():
    states = [fx.cpu_state(fx.at(0), 10.0), fx.cpu_state(fx.at(60), None),
              fx.cpu_state(fx.at(120), None), fx.cpu_state(fx.at(180), None)]
    ev = forecast_with_evidence(CanonicalCapacitySeries.build(states),
                                ForecastTarget.CPU_UTILIZATION, fx.at(180), H1,
                                PersistenceForecaster(), normalization_policy=NPOL, uncertainty_config=NONE_UC)
    assert _reason(ev) is AbstentionReason.EXCESSIVE_MISSINGNESS


def test_subject_mismatch():
    ev = _fw(_series([10.0, 20.0, 30.0]), expected_subject=fx.subject("wl-OTHER"))
    assert _reason(ev) is AbstentionReason.SUBJECT_MISMATCH


def test_tenant_scope_mismatch():
    # Same workload_id as the default series subject, only the tenant differs.
    ev = _fw(_series([10.0, 20.0, 30.0]), expected_subject=fx.subject("wl-1", tenant_id="other-tenant"))
    assert _reason(ev) is AbstentionReason.TENANT_SCOPE_MISMATCH


def test_invalid_time_order_via_admission_service():
    obs = fx.cpu_series_states([10.0, 20.0, 30.0])
    ev = forecast_from_observations([obs[2], obs[0], obs[1]], ForecastTarget.CPU_UTILIZATION,
                                    obs[2].observed_at, H1, PersistenceForecaster(),
                                    normalization_policy=NPOL, uncertainty_config=NONE_UC)
    assert _reason(ev) is AbstentionReason.INVALID_TIME_ORDER


def test_conflicting_duplicate_via_admission_service():
    obs = fx.cpu_series_states([10.0, 20.0, 30.0])
    conflict = fx.cpu_state(obs[1].observed_at, 99.0)  # same ts, different content
    ev = forecast_from_observations([obs[0], obs[1], conflict, obs[2]],
                                    ForecastTarget.CPU_UTILIZATION, obs[2].observed_at, H1,
                                    PersistenceForecaster(), normalization_policy=NPOL, uncertainty_config=NONE_UC)
    assert _reason(ev) is AbstentionReason.CONFLICTING_DUPLICATE


def test_unsupported_target():
    ev = _fw(_series([10.0, 20.0, 30.0]), target=ForecastTarget.MEMORY_UTILIZATION,
             forecaster=LimitedForecaster())
    assert _reason(ev) is AbstentionReason.UNSUPPORTED_TARGET


def test_unsupported_horizon():
    ev = _fw(_series([10.0, 20.0, 30.0]), horizon=ForecastHorizon.minutes(60), forecaster=LimitedForecaster())
    assert _reason(ev) is AbstentionReason.UNSUPPORTED_HORIZON


def test_irregular_cadence():
    states = [fx.cpu_state(fx.at(0), 10.0), fx.cpu_state(fx.at(60), 20.0), fx.cpu_state(fx.at(400), 30.0)]
    ev = forecast_with_evidence(CanonicalCapacitySeries.build(states), ForecastTarget.CPU_UTILIZATION,
                                fx.at(400), H1, PersistenceForecaster(), normalization_policy=NPOL,
                                uncertainty_config=NONE_UC)
    assert _reason(ev) is AbstentionReason.IRREGULAR_CADENCE


def test_missing_normalization_policy_none():
    ev = _fw(_series([10.0, 20.0, 30.0]), npol=None)
    assert _reason(ev) is AbstentionReason.MISSING_NORMALIZATION_POLICY


def test_missing_normalization_policy_no_method_for_signal():
    from ugence_cloud_scaling_controller.canonical import NormalizationMethod, NormalizationPolicy
    mem_only = NormalizationPolicy(policy_id="mem", method_by_signal={"memory": NormalizationMethod.PERCENT_TO_RATIO})
    ev = _fw(_series([10.0, 20.0, 30.0]), npol=mem_only)  # cpu target, policy has no "cpu" method
    assert _reason(ev) is AbstentionReason.MISSING_NORMALIZATION_POLICY


def test_inconsistent_unit_mixed_units():
    subj = fx.subject()
    states = [
        CanonicalCapacityState(subject=subj, observed_at=fx.at(0),
                               infrastructure=InfrastructureState(cpu_utilization=Measurement(50.0, Unit.PERCENT)),
                               capacity=CapacityState(running_replicas=3)),
        CanonicalCapacityState(subject=subj, observed_at=fx.at(60),
                               infrastructure=InfrastructureState(cpu_utilization=Measurement(0.6, Unit.RATIO)),
                               capacity=CapacityState(running_replicas=3)),
        CanonicalCapacityState(subject=subj, observed_at=fx.at(120),
                               infrastructure=InfrastructureState(cpu_utilization=Measurement(55.0, Unit.PERCENT)),
                               capacity=CapacityState(running_replicas=3)),
    ]
    ev = forecast_with_evidence(CanonicalCapacitySeries.build(states), ForecastTarget.CPU_UTILIZATION,
                                fx.at(120), H1, PersistenceForecaster(), normalization_policy=NPOL,
                                uncertainty_config=NONE_UC)
    assert _reason(ev) is AbstentionReason.INCONSISTENT_UNIT


def test_insufficient_calibration_history():
    ev = _fw(_series([10.0, 20.0, 30.0]), forecaster=LinearTrendForecaster(),
             uncertainty=UncertaintyConfig(min_calibration_samples=5, match_tolerance_seconds=5.0))
    assert _reason(ev) is AbstentionReason.INSUFFICIENT_CALIBRATION_HISTORY


def test_forecast_outside_domain():
    ev = _fw(_series([50.0, 40.0, 30.0, 20.0, 10.0]), horizon=ForecastHorizon.minutes(60),
             forecaster=LinearTrendForecaster())
    assert _reason(ev) is AbstentionReason.FORECAST_OUTSIDE_DOMAIN


def test_invalid_measurement_via_nonfinite_forecaster():
    ev = _fw(_series([10.0, 20.0, 30.0]), forecaster=NonFiniteForecaster())
    assert _reason(ev) is AbstentionReason.INVALID_MEASUREMENT


def _periodic_states(periods=7, cadence=60.0, period=3600.0, drop=()):
    """Deterministic multi-period CPU series for the periodic-model reachability cases."""
    import math

    states = []
    n = int(periods * period / cadence) + 1
    for i in range(n):
        if i in drop:
            continue
        t = fx.T0 + timedelta(seconds=cadence * i)
        phi = 2.0 * math.pi * ((t.timestamp() % period) / period)
        states.append(fx.cpu_state(t, 50.0 + 10.0 * math.cos(phi) + 4.0 * math.sin(phi)))
    return states


def _periodic_evidence(states, forecaster):
    series = CanonicalCapacitySeries.build(states)
    return forecast_with_evidence(
        series, ForecastTarget.CPU_UTILIZATION, states[-1].observed_at, H1, forecaster,
        normalization_policy=NPOL,
        feature_config=FeatureConfig(lookback_seconds=7 * 3600.0 + 600.0,
                                     expected_cadence_seconds=60.0),
        admission_policy=AdmissionPolicy(require_regular_cadence=False,
                                         max_staleness_seconds=None),
        uncertainty_config=NONE_UC,
    )


_SCALED_H = {
    "period_seconds": 3600.0,
    "min_cycle_span_seconds": 7 * 3600.0 - 60.0,
    "phase_bins": 12,
    "min_occupied_bins": 11,
    "min_days_with_coverage": 6,
    "lookback_days": 7,
}


def test_insufficient_cycle_coverage_is_reachable():
    """A periodic model whose window does not span enough of its period."""
    ev = _periodic_evidence(_periodic_states(periods=1), HarmonicPhaseForecaster(_SCALED_H))
    assert ev.forecast.status == "abstained"
    assert ev.forecast.abstention_reason is AbstentionReason.INSUFFICIENT_CYCLE_COVERAGE


def test_period_not_resolvable_is_reachable():
    """Span and phase coverage are fine; a scrape outage breaks the maximum-gap rule."""
    states = _periodic_states(drop=tuple(range(200, 216)))
    ev = _periodic_evidence(states, HarmonicPhaseForecaster(_SCALED_H))
    assert ev.forecast.status == "abstained"
    assert ev.forecast.abstention_reason is AbstentionReason.PERIOD_NOT_RESOLVABLE


def test_every_abstention_reason_is_covered_by_this_module():
    # Guard: if a new AbstentionReason is added, force a reachability test for it.
    covered = {
        AbstentionReason.INSUFFICIENT_HISTORY, AbstentionReason.STALE_HISTORY,
        AbstentionReason.EXCESSIVE_MISSINGNESS, AbstentionReason.SUBJECT_MISMATCH,
        AbstentionReason.TENANT_SCOPE_MISMATCH, AbstentionReason.INVALID_TIME_ORDER,
        AbstentionReason.CONFLICTING_DUPLICATE, AbstentionReason.UNSUPPORTED_TARGET,
        AbstentionReason.UNSUPPORTED_HORIZON, AbstentionReason.IRREGULAR_CADENCE,
        AbstentionReason.MISSING_NORMALIZATION_POLICY, AbstentionReason.INVALID_MEASUREMENT,
        AbstentionReason.INCONSISTENT_UNIT, AbstentionReason.INSUFFICIENT_CALIBRATION_HISTORY,
        AbstentionReason.FORECAST_OUTSIDE_DOMAIN,
        AbstentionReason.INSUFFICIENT_CYCLE_COVERAGE,
        AbstentionReason.PERIOD_NOT_RESOLVABLE,
    }
    assert covered == set(AbstentionReason), set(AbstentionReason) - covered
