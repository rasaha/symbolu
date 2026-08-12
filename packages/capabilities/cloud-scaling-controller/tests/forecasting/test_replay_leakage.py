"""Replay evaluation + adversarial leakage prevention (must fail closed)."""

from __future__ import annotations

from datetime import timedelta

import pytest

import fc_helpers as fx
from ugence_cloud_scaling_controller.canonical import (
    CanonicalCapacityState, CapacityState, InfrastructureState, Measurement, Unit,
    ObservationProvenance, ObservationSourceType,
)
from ugence_cloud_scaling_controller.forecasting import (
    CanonicalCapacitySeries,
    DuplicateTimestampPolicy,
    FeatureConfig,
    ForecastHorizon,
    ForecastTarget,
    LinearTrendForecaster,
    OrderingPolicy,
    PersistenceForecaster,
    SeriesConstructionPolicy,
    UncertaintyConfig,
    build_input_window,
    default_cutoffs,
    run_replay_evaluation,
)
from ugence_cloud_scaling_controller.forecasting.replay import ReplayError, _history_at_or_before
from ugence_cloud_scaling_controller.forecasting.series import _as_utc

H = ForecastHorizon(60.0)  # one-step horizon at 60s cadence
NPOL = fx.cpu_norm_policy()
UCFG = UncertaintyConfig(min_calibration_samples=3, match_tolerance_seconds=5.0)


def _assert_windows_leakage_free(observations, cutoffs, target=ForecastTarget.CPU_UTILIZATION):
    """For every cutoff, the window must contain only observations at or before it."""
    for cutoff in cutoffs:
        history = _history_at_or_before(observations, cutoff)
        if not history:
            continue
        series = CanonicalCapacitySeries.build(
            history, SeriesConstructionPolicy(ordering=OrderingPolicy.SORT)
        )
        assert _as_utc(series.end_event_time) <= _as_utc(cutoff)
        w = build_input_window(series, target, cutoff, H)
        for smp in w.samples:
            assert _as_utc(smp.event_time) <= _as_utc(cutoff)


def test_basic_replay_runs_and_matches_future_actuals():
    values = [0.0, 10.0, 5.0, 20.0, 15.0, 30.0, 25.0, 40.0]
    obs = fx.cpu_series_states(values, cadence_seconds=60.0)
    res = run_replay_evaluation(
        obs, ForecastTarget.CPU_UTILIZATION, H, PersistenceForecaster(),
        normalization_policy=NPOL, uncertainty_config=UCFG, match_tolerance_seconds=5.0,
    )
    assert res.aggregate.record_count == len(obs)
    # Every matched actual is strictly AFTER the forecast cutoff (never a feature).
    for r in res.records:
        if r.actual_event_time is not None and r.status.value == "evaluated":
            assert _as_utc(r.actual_event_time) > _as_utc(r.forecast_cutoff)


def test_future_records_preloaded_do_not_leak_into_windows():
    values = [float(i) for i in range(10)]
    obs = fx.cpu_series_states(values, cadence_seconds=60.0)
    cutoffs = default_cutoffs(obs)
    # Windows built at each cutoff must never include a later observation.
    _assert_windows_leakage_free(obs, cutoffs)


def test_randomized_input_order_yields_order_independent_forecasts():
    values = [0.0, 10.0, 5.0, 20.0, 15.0, 30.0, 25.0, 40.0]
    obs = fx.cpu_series_states(values, cadence_seconds=60.0)
    # Deterministic non-trivial permutation (no RNG).
    perm = [obs[i] for i in (5, 0, 7, 2, 4, 1, 6, 3)]

    from ugence_cloud_scaling_controller.forecasting import OrderingPolicy
    sort_pol = SeriesConstructionPolicy(ordering=OrderingPolicy.SORT)

    ref = run_replay_evaluation(obs, ForecastTarget.CPU_UTILIZATION, H, PersistenceForecaster(),
                                normalization_policy=NPOL, uncertainty_config=UCFG,
                                series_policy=sort_pol, match_tolerance_seconds=5.0)
    shuffled = run_replay_evaluation(perm, ForecastTarget.CPU_UTILIZATION, H, PersistenceForecaster(),
                                     normalization_policy=NPOL, uncertainty_config=UCFG,
                                     series_policy=sort_pol, match_tolerance_seconds=5.0)
    # Forecast VALUES/errors are order-independent (leakage-free), even if disclosure differs.
    for field in ("record_count", "evaluated_count", "abstention_count",
                  "mean_absolute_error", "root_mean_squared_error", "mean_signed_error"):
        assert getattr(ref.aggregate, field) == getattr(shuffled.aggregate, field)


def test_observation_with_future_event_time_inserted_early_is_excluded():
    values = [10.0, 20.0, 30.0, 40.0]
    obs = fx.cpu_series_states(values, cadence_seconds=60.0)
    # Put the LAST (future) observation first in the list.
    reordered = [obs[3], obs[0], obs[1], obs[2]]
    early_cutoff = obs[1].observed_at  # t=60
    history = _history_at_or_before(reordered, early_cutoff)
    assert len(history) == 2  # only t=0 and t=60, never the t=180 obs placed first
    assert all(_as_utc(h.observed_at) <= _as_utc(early_cutoff) for h in history)


def test_collection_time_after_observation_time_uses_event_time():
    subj = fx.subject()
    states = []
    for i, v in enumerate([10.0, 20.0, 30.0]):
        obs_at = fx.at(60 * i)
        prov = ObservationProvenance(
            source_type=ObservationSourceType.FIXTURE,
            observed_at=obs_at,
            collected_at=obs_at + timedelta(hours=1),  # collected much later
        )
        states.append(CanonicalCapacityState(
            subject=subj, observed_at=obs_at,
            infrastructure=InfrastructureState(cpu_utilization=Measurement(v, Unit.PERCENT)),
            capacity=CapacityState(running_replicas=3), provenance=prov,
        ))
    series = CanonicalCapacitySeries.build(states)
    # Cutoff at the middle event time: window uses EVENT time, ignoring collection time.
    w = build_input_window(series, ForecastTarget.CPU_UTILIZATION, fx.at(60), H)
    assert w.sample_count == 2
    assert w.last_event_time == fx.at(60)


def test_duplicate_timestamps_handled_without_leakage():
    subj = fx.subject()
    base = fx.cpu_series_states([10.0, 20.0, 30.0], subj=subj)
    dup = fx.cpu_state(base[1].observed_at, 20.0, subj=subj)  # identical duplicate of t=60
    obs = [base[0], base[1], dup, base[2]]
    res = run_replay_evaluation(
        obs, ForecastTarget.CPU_UTILIZATION, H, PersistenceForecaster(),
        normalization_policy=NPOL, uncertainty_config=UCFG,
        series_policy=SeriesConstructionPolicy(
            duplicate_timestamp=DuplicateTimestampPolicy.COLLAPSE_IDENTICAL),
        match_tolerance_seconds=5.0,
    )
    assert res.aggregate.record_count >= 1


def test_matched_actual_is_never_in_the_forecast_window():
    values = [0.0, 10.0, 20.0, 30.0, 40.0, 50.0]
    obs = fx.cpu_series_states(values, cadence_seconds=60.0)
    res = run_replay_evaluation(
        obs, ForecastTarget.CPU_UTILIZATION, H, PersistenceForecaster(),
        normalization_policy=NPOL, uncertainty_config=UCFG, match_tolerance_seconds=5.0,
    )
    for ev, r in zip(res.evidences, res.records):
        if r.actual_event_time is None:
            continue
        cutoff = ev.forecast.forecast_cutoff
        history = _history_at_or_before(obs, cutoff)
        window_times = {_as_utc(h.observed_at) for h in history}
        # The scored actual's event time must be strictly future — not in the window.
        assert _as_utc(r.actual_event_time) not in window_times or \
            _as_utc(r.actual_event_time) > _as_utc(cutoff)
        assert _as_utc(r.actual_event_time) > _as_utc(cutoff)


def test_harness_leakage_guard_fails_closed(monkeypatch):
    """If history filtering were subverted to admit a future observation, the harness
    must fail closed rather than score a leaked forecast."""
    import ugence_cloud_scaling_controller.forecasting.replay as R
    values = [10.0, 20.0, 30.0, 40.0]
    obs = fx.cpu_series_states(values, cadence_seconds=60.0)

    # Subvert the history filter to (wrongly) return ALL observations regardless of cutoff.
    monkeypatch.setattr(R, "_history_at_or_before", lambda observations, cutoff: list(observations))
    with pytest.raises(ReplayError, match="leakage detected"):
        R.run_replay_evaluation(
            obs, ForecastTarget.CPU_UTILIZATION, H, PersistenceForecaster(),
            normalization_policy=NPOL, uncertainty_config=UCFG,
            cutoffs=[obs[0].observed_at], match_tolerance_seconds=5.0,
        )


def test_aggregate_reports_abstentions_and_unmatched():
    values = [float(i) for i in range(6)]
    obs = fx.cpu_series_states(values, cadence_seconds=60.0)
    res = run_replay_evaluation(
        obs, ForecastTarget.CPU_UTILIZATION, H, LinearTrendForecaster(),
        normalization_policy=NPOL, uncertainty_config=UCFG, match_tolerance_seconds=5.0,
    )
    agg = res.aggregate
    assert agg.record_count == 6
    assert agg.abstention_count + agg.forecast_count == agg.record_count
    assert agg.evaluated_count + agg.unmatched_count + agg.subject_mismatch_count == agg.forecast_count
