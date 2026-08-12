"""ForecastInputWindow: leakage invariant, lookback, missingness, cadence, horizons."""

from __future__ import annotations

from datetime import timedelta

import pytest

import fc_helpers as fx
from ugence_cloud_scaling_controller.forecasting import (
    CanonicalCapacitySeries,
    FeatureConfig,
    ForecastHorizon,
    ForecastTarget,
    ForecastInputWindow,
    WindowError,
    build_input_window,
)


def _series(values, **kw):
    return CanonicalCapacitySeries.build(fx.cpu_series_states(values, **kw))


def test_horizon_validation():
    with pytest.raises(WindowError):
        ForecastHorizon(0)
    with pytest.raises(WindowError):
        ForecastHorizon(-5)
    h = ForecastHorizon.minutes(15)
    assert h.seconds == 900.0
    assert h.delta == timedelta(minutes=15)


def test_window_only_contains_observations_at_or_before_cutoff():
    s = _series([10.0, 20.0, 30.0, 40.0, 50.0])
    cutoff = fx.at(120)  # third observation
    w = build_input_window(s, ForecastTarget.CPU_UTILIZATION, cutoff, ForecastHorizon.minutes(5))
    assert w.sample_count == 3
    assert all(smp.event_time <= cutoff for smp in w.samples)
    assert w.forecast_for == cutoff + timedelta(minutes=5)


def test_leakage_invariant_asserted_on_construction():
    # Directly constructing a window with a future sample must fail closed.
    s = _series([10.0, 20.0])
    good = build_input_window(s, ForecastTarget.CPU_UTILIZATION, fx.at(60), ForecastHorizon.minutes(5))
    future_sample = s.states[-1]  # event time 60 == cutoff is fine; fabricate a later one
    from ugence_cloud_scaling_controller.forecasting.targets import TargetSample
    bad_sample = TargetSample(event_time=fx.at(120), value=1.0, unit="percent")
    with pytest.raises(WindowError, match="leakage invariant"):
        ForecastInputWindow(
            schema_version=good.schema_version,
            subject_digest_dict=good.subject_digest_dict,
            target=good.target,
            cutoff=fx.at(60),
            horizon=good.horizon,
            forecast_for=good.forecast_for,
            lookback_seconds=good.lookback_seconds,
            samples=(bad_sample,),
            units_present=("percent",),
            missingness=good.missingness,
            cadence=good.cadence,
            feature_config=good.feature_config,
            source_series_digest=good.source_series_digest,
        )


def test_lookback_excludes_older_observations():
    s = _series([float(i) for i in range(20)])  # 0..19 at 60s cadence
    cutoff = fx.at(60 * 19)
    fc = FeatureConfig(lookback_seconds=300.0)  # only last 5 minutes
    w = build_input_window(s, ForecastTarget.CPU_UTILIZATION, cutoff, ForecastHorizon.minutes(5), fc)
    # cutoff - 300s .. cutoff  -> 6 observations (i=14..19)
    assert w.sample_count == 6


def test_missingness_counts_but_never_imputes():
    states = [
        fx.cpu_state(fx.at(0), 10.0),
        fx.cpu_state(fx.at(60), None),   # missing CPU
        fx.cpu_state(fx.at(120), 30.0),
        fx.cpu_state(fx.at(180), None),  # missing CPU
    ]
    s = CanonicalCapacitySeries.build(states)
    w = build_input_window(s, ForecastTarget.CPU_UTILIZATION, fx.at(180), ForecastHorizon.minutes(5))
    assert w.missingness.considered_count == 4
    assert w.missingness.present_count == 2
    assert w.missingness.missing_count == 2
    assert w.missingness.missing_fraction == 0.5
    assert w.sample_count == 2  # only present values are samples; nothing filled


def test_cadence_detects_irregular_gaps():
    states = [
        fx.cpu_state(fx.at(0), 10.0),
        fx.cpu_state(fx.at(60), 20.0),
        fx.cpu_state(fx.at(300), 30.0),  # 240s gap (irregular vs 60s expected)
    ]
    s = CanonicalCapacitySeries.build(states)
    fc = FeatureConfig(expected_cadence_seconds=60.0, cadence_tolerance_seconds=5.0)
    w = build_input_window(s, ForecastTarget.CPU_UTILIZATION, fx.at(300), ForecastHorizon.minutes(5), fc)
    assert w.cadence.irregular_gap_count == 1
    assert w.cadence.max_gap_seconds == 240.0


def test_feature_config_digest_changes_with_config():
    a = FeatureConfig(lookback_seconds=3600.0).digest()
    b = FeatureConfig(lookback_seconds=1800.0).digest()
    assert a != b


def test_window_digest_stable_and_content_sensitive():
    s = _series([10.0, 20.0, 30.0])
    w1 = build_input_window(s, ForecastTarget.CPU_UTILIZATION, fx.at(120), ForecastHorizon.minutes(5))
    w2 = build_input_window(s, ForecastTarget.CPU_UTILIZATION, fx.at(120), ForecastHorizon.minutes(5))
    assert w1.digest() == w2.digest()
    w3 = build_input_window(s, ForecastTarget.CPU_UTILIZATION, fx.at(120), ForecastHorizon.minutes(15))
    assert w1.digest() != w3.digest()  # horizon is authoritative


def test_running_replicas_target_uses_running_not_other_semantics():
    from ugence_cloud_scaling_controller.canonical import CanonicalCapacityState, CapacityState
    subj = fx.subject()
    states = [
        CanonicalCapacityState(subject=subj, observed_at=fx.at(0),
                               capacity=CapacityState(running_replicas=3, ready_replicas=1,
                                                      desired_replicas=9, healthy_replicas=2)),
        CanonicalCapacityState(subject=subj, observed_at=fx.at(60),
                               capacity=CapacityState(running_replicas=4, ready_replicas=1,
                                                      desired_replicas=9, healthy_replicas=2)),
    ]
    s = CanonicalCapacitySeries.build(states)
    w = build_input_window(s, ForecastTarget.RUNNING_REPLICAS, fx.at(60), ForecastHorizon.minutes(5))
    assert w.values == (3.0, 4.0)  # running_replicas, never ready/desired/healthy
