"""Correction E: normalization/projection semantics — explicit space, applied policy, replica semantics."""

from __future__ import annotations

import pytest

import fc_helpers as fx
from ugence_cloud_scaling_controller.canonical import (
    CanonicalCapacityState, CapacityState, NormalizationMethod, NormalizationPolicy,
)
from ugence_cloud_scaling_controller.forecasting import (
    AbstentionReason,
    CanonicalCapacitySeries,
    ForecastHorizon,
    ForecastTarget,
    ForecastValueSpace,
    PersistenceForecaster,
    UncertaintyConfig,
    UncertaintyMethod,
    forecast_with_evidence,
)

H1 = ForecastHorizon(60.0)
NONE_UC = UncertaintyConfig(method=UncertaintyMethod.NONE)


def _series(values):
    return CanonicalCapacitySeries.build(fx.cpu_series_states(values, cadence_seconds=60.0))


def _fw(series, *, npol, space=ForecastValueSpace.PROJECTED_WITHOUT_CONVERSION,
        target=ForecastTarget.CPU_UTILIZATION, horizon=H1):
    return forecast_with_evidence(series, target, series.end_event_time, horizon,
                                  PersistenceForecaster(), normalization_policy=npol,
                                  uncertainty_config=NONE_UC, forecast_space=space)


def test_raw_is_projected_without_conversion():
    ev = _fw(_series([50.0, 60.0, 70.0]), npol=fx.cpu_norm_policy())
    fc = ev.forecast
    assert fc.value_space == "projected_without_conversion"
    assert fc.normalization_applied is False
    assert fc.unit == "percent"
    assert fc.point_estimate == 70.0   # raw percent, unconverted


def test_normalized_applies_phase1_authority():
    ev = _fw(_series([50.0, 60.0, 70.0]), npol=fx.cpu_norm_policy(),
             space=ForecastValueSpace.NORMALIZED)
    fc = ev.forecast
    assert fc.value_space == "normalized"
    assert fc.normalization_applied is True
    assert fc.unit == "ratio"
    assert abs(fc.point_estimate - 0.70) < 1e-9   # 70 percent -> 0.70 ratio via PERCENT_TO_RATIO


def test_raw_and_normalized_have_different_evidence_identity():
    s = _series([50.0, 60.0, 70.0])
    a = _fw(s, npol=fx.cpu_norm_policy())
    b = _fw(s, npol=fx.cpu_norm_policy(), space=ForecastValueSpace.NORMALIZED)
    assert a.digest() != b.digest()
    assert a.forecast.input_window_digest != b.forecast.input_window_digest


def test_missing_policy_abstains():
    ev = _fw(_series([50.0, 60.0, 70.0]), npol=None)
    assert ev.forecast.abstention_reason is AbstentionReason.MISSING_NORMALIZATION_POLICY
    assert ev.normalization_policy_digest is None


def test_policy_without_method_for_signal_abstains():
    mem = NormalizationPolicy(policy_id="mem", method_by_signal={"memory": NormalizationMethod.PERCENT_TO_RATIO})
    ev = _fw(_series([50.0, 60.0, 70.0]), npol=mem)
    assert ev.forecast.abstention_reason is AbstentionReason.MISSING_NORMALIZATION_POLICY


def test_incompatible_unit_abstains():
    # cpu observed in PERCENT but policy's cpu method expects MILLISECONDS -> not applicable.
    bad = NormalizationPolicy(policy_id="bad",
                              method_by_signal={"cpu": NormalizationMethod.LATENCY_MS_TO_THRESHOLD},
                              thresholds={"cpu": 100.0})
    ev = _fw(_series([50.0, 60.0, 70.0]), npol=bad)
    assert ev.forecast.abstention_reason is AbstentionReason.INCONSISTENT_UNIT


def test_policy_digest_change_changes_evidence_digest():
    s = _series([50.0, 60.0, 70.0])
    a = _fw(s, npol=fx.cpu_norm_policy("pol-A"))
    b = _fw(s, npol=fx.cpu_norm_policy("pol-B"))
    assert a.digest() != b.digest()
    assert a.normalization_policy_digest != b.normalization_policy_digest


def test_running_replicas_uses_running_not_other_semantics_via_service():
    subj = fx.subject()
    states = [
        CanonicalCapacityState(subject=subj, observed_at=fx.at(60 * i),
                               capacity=CapacityState(running_replicas=3 + i, ready_replicas=1,
                                                      desired_replicas=99, healthy_replicas=2))
        for i in range(5)
    ]
    s = CanonicalCapacitySeries.build(states)
    ev = forecast_with_evidence(s, ForecastTarget.RUNNING_REPLICAS, s.end_event_time, H1,
                                PersistenceForecaster(), normalization_policy=fx.cpu_norm_policy(),
                                uncertainty_config=NONE_UC)
    assert ev.forecast.is_forecast
    assert ev.forecast.point_estimate == 7.0   # last running_replicas (3+4), never desired=99
    assert ev.forecast.unit == "replicas"
    assert ev.forecast.value_space == "projected_without_conversion"
    assert ev.forecast.normalization_applied is False


def test_normalized_on_replicas_abstains():
    subj = fx.subject()
    states = [fx.replicas_state(fx.at(60 * i), 3 + i, subj=subj) for i in range(5)]
    s = CanonicalCapacitySeries.build(states)
    ev = forecast_with_evidence(s, ForecastTarget.RUNNING_REPLICAS, s.end_event_time, H1,
                                PersistenceForecaster(), normalization_policy=fx.cpu_norm_policy(),
                                uncertainty_config=NONE_UC, forecast_space=ForecastValueSpace.NORMALIZED)
    assert ev.forecast.abstention_reason is AbstentionReason.UNSUPPORTED_TARGET
