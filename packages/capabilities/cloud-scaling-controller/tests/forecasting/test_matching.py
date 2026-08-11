"""Correction B: deterministic, order-independent, fail-closed actual matching."""

from __future__ import annotations

from datetime import timedelta

import pytest

import fc_helpers as fx
from ugence_cloud_scaling_controller.forecasting import (
    CanonicalCapacitySeries,
    ForecastHorizon,
    ForecastTarget,
    PersistenceForecaster,
    UncertaintyConfig,
)
from ugence_cloud_scaling_controller.forecasting.replay import (
    MATCH_AMBIGUOUS,
    MATCH_NONE,
    MATCH_UNIQUE,
    _match_actual,
)

H = ForecastHorizon(60.0)


def _forecast_for(cutoff):
    return cutoff + H.delta


def test_unique_closest_selected_and_order_independent():
    subj = fx.subject()
    cutoff = fx.at(0)
    ff = _forecast_for(cutoff)  # t=60
    a = fx.cpu_state(fx.at(58), 1.0, subj=subj)   # gap 2
    b = fx.cpu_state(fx.at(61), 2.0, subj=subj)   # gap 1 (closest)
    c = fx.cpu_state(fx.at(64), 3.0, subj=subj)   # gap 4
    for order in ([a, b, c], [c, b, a], [b, c, a], [c, a, b]):
        kind, chosen = _match_actual(order, cutoff, ff, 5.0, subj, ForecastTarget.CPU_UTILIZATION)
        assert kind == MATCH_UNIQUE
        assert chosen is b  # always the closest regardless of input order


def test_two_equidistant_candidates_are_ambiguous():
    subj = fx.subject()
    cutoff = fx.at(0)
    ff = _forecast_for(cutoff)  # t=60
    left = fx.cpu_state(fx.at(57), 1.0, subj=subj)   # gap 3
    right = fx.cpu_state(fx.at(63), 2.0, subj=subj)  # gap 3
    kind, chosen = _match_actual([left, right], cutoff, ff, 5.0, subj, ForecastTarget.CPU_UTILIZATION)
    assert kind == MATCH_AMBIGUOUS
    assert chosen is None
    # And order does not change the ambiguity verdict.
    kind2, _ = _match_actual([right, left], cutoff, ff, 5.0, subj, ForecastTarget.CPU_UTILIZATION)
    assert kind2 == MATCH_AMBIGUOUS


def test_multiple_non_equidistant_picks_unique_closest():
    subj = fx.subject()
    cutoff = fx.at(0)
    ff = _forecast_for(cutoff)  # t=60
    cands = [fx.cpu_state(fx.at(t), float(t), subj=subj) for t in (56, 59, 63, 64)]
    kind, chosen = _match_actual(cands, cutoff, ff, 5.0, subj, ForecastTarget.CPU_UTILIZATION)
    assert kind == MATCH_UNIQUE
    assert chosen.observed_at == fx.at(59)  # gap 1, unique minimum


def test_exact_horizon_match():
    subj = fx.subject()
    cutoff = fx.at(0)
    ff = _forecast_for(cutoff)
    exact = fx.cpu_state(ff, 5.0, subj=subj)  # gap 0
    kind, chosen = _match_actual([exact], cutoff, ff, 0.0, subj, ForecastTarget.CPU_UTILIZATION)
    assert kind == MATCH_UNIQUE and chosen is exact


def test_candidates_outside_tolerance_are_unmatched():
    subj = fx.subject()
    cutoff = fx.at(0)
    ff = _forecast_for(cutoff)  # t=60
    far = fx.cpu_state(fx.at(80), 1.0, subj=subj)  # gap 20 > tol
    kind, chosen = _match_actual([far], cutoff, ff, 5.0, subj, ForecastTarget.CPU_UTILIZATION)
    assert kind == MATCH_NONE and chosen is None


def test_at_or_before_cutoff_never_matched():
    subj = fx.subject()
    cutoff = fx.at(60)
    ff = _forecast_for(cutoff)  # t=120
    # A candidate exactly at forecast_for but with event time <= cutoff cannot exist here;
    # a past observation near forecast_for must still be excluded if <= cutoff.
    past = fx.cpu_state(fx.at(60), 1.0, subj=subj)  # == cutoff -> excluded (leakage)
    kind, _ = _match_actual([past], cutoff, ff, 100.0, subj, ForecastTarget.CPU_UTILIZATION)
    assert kind == MATCH_NONE


def test_cross_subject_and_cross_tenant_candidates_excluded():
    subj = fx.subject("wl", tenant_id="t1")
    other_subj = fx.subject("wl-OTHER", tenant_id="t1")
    other_tenant = fx.subject("wl", tenant_id="t2")
    cutoff = fx.at(0)
    ff = _forecast_for(cutoff)
    c1 = fx.cpu_state(fx.at(60), 1.0, subj=other_subj)
    c2 = fx.cpu_state(fx.at(60), 1.0, subj=other_tenant)
    kind, _ = _match_actual([c1, c2], cutoff, ff, 5.0, subj, ForecastTarget.CPU_UTILIZATION)
    assert kind == MATCH_NONE  # neither belongs to the forecast's subject/tenant


def test_replay_emits_ambiguous_record():
    # Construct observations so a forecast-for lands equidistant between two later actuals.
    subj = fx.subject()
    obs = [
        fx.cpu_state(fx.at(0), 10.0, subj=subj),
        fx.cpu_state(fx.at(60), 20.0, subj=subj),   # cutoff candidate; forecast_for = 120
        fx.cpu_state(fx.at(117), 30.0, subj=subj),  # gap 3 from 120
        fx.cpu_state(fx.at(123), 40.0, subj=subj),  # gap 3 from 120 -> equidistant
    ]
    from ugence_cloud_scaling_controller.forecasting import run_replay_evaluation, EvaluationStatus
    res = run_replay_evaluation(
        obs, ForecastTarget.CPU_UTILIZATION, H, PersistenceForecaster(),
        normalization_policy=fx.cpu_norm_policy(),
        uncertainty_config=UncertaintyConfig(min_calibration_samples=1, match_tolerance_seconds=10.0),
        cutoffs=[fx.at(60)], match_tolerance_seconds=10.0,
    )
    assert any(r.status is EvaluationStatus.AMBIGUOUS for r in res.records)
    assert res.aggregate.ambiguous_count >= 1
