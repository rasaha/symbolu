"""Tests for the StreamingFleetMonitor (online aggregation + alerts).

Three contract surfaces:

1. **Ingestion** — both the convenience path (``observe_episode``
   on a raw record) and the production fast path (``observe_summary``
   on a pre-summarised episode + exclusion vector).
2. **Windowed summary** — ``summary(window=...)`` filters by
   ``observed_at`` and produces a :class:`FleetSummary` that matches
   the batch :func:`aggregate_fleet` output on the same episodes
   (the streaming monitor's "batch parity within the window"
   invariant).
3. **Alerts** — :class:`AlertRule` threshold rules fire / don't
   fire correctly across direction, min_episodes, dotted-path
   metrics, and missing-metric conditions.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import List

import numpy as np
import pytest

from symbolu_robotics.bcvf_autonomous.analysis import (
    Alert,
    AlertRule,
    EpisodeSummary,
    FleetSummary,
    StreamingFleetMonitor,
    WindowedFleetSummary,
    aggregate_fleet,
    summarize_episode,
)
from symbolu_robotics.bcvf_autonomous.trust_diagnostics import (
    RolloutAggregation,
    TrustShapedEpisodeRecord,
)


# --------------------------------------------------------------------------- #
# Helpers
# --------------------------------------------------------------------------- #


def _make_record(
    n_steps: int = 10,
    M: int = 3,
    flips: bool = False,
    excluded_predictor: int = -1,
) -> TrustShapedEpisodeRecord:
    """Construct a TrustShapedEpisodeRecord with the right shapes filled in.

    ``flips=True`` alternates argmax weights between predictor 0 and 1
    so the resulting episode summary has ``n_argmax_flips > 0``.
    ``excluded_predictor`` (>=0) marks one predictor as excluded for
    every step — exercises the per-predictor-exclusion aggregation path.
    """
    weights = np.full((n_steps, M), 1.0 / M, dtype=np.float64)
    if flips:
        weights[:] = 0.0
        for t in range(n_steps):
            weights[t, t % 2] = 1.0
    else:
        weights[:] = 0.0
        weights[:, 0] = 1.0
    excl = np.zeros((n_steps, M), dtype=bool)
    if 0 <= excluded_predictor < M:
        excl[:, excluded_predictor] = True
    return TrustShapedEpisodeRecord(
        n_steps=n_steps,
        M=M,
        aggregation=RolloutAggregation.MEAN,
        per_step_weights=weights,
        per_step_costs=np.zeros((n_steps, M), dtype=np.float64),
        per_step_residuals=np.zeros((n_steps, M), dtype=np.float64),
        per_step_ema_mean=np.zeros((n_steps, M), dtype=np.float64),
        per_step_ema_std=np.zeros((n_steps, M), dtype=np.float64),
        per_step_bcvf_total=np.zeros(n_steps, dtype=np.float64),
        per_step_deadband_active_count=np.zeros(n_steps, dtype=np.int64),
        per_step_deadband_fired=np.zeros(n_steps, dtype=bool),
        per_step_is_excluded=excl,
        per_step_gate_activations=np.zeros(n_steps, dtype=np.int64),
        per_step_v2_state=[""] * n_steps,
        per_step_v2_signal=np.full(n_steps, np.nan),
        per_step_consec_suspect=np.full((n_steps, M), -1, dtype=np.int64),
        per_step_consec_ok=np.full((n_steps, M), -1, dtype=np.int64),
        exclusion_T=None,
    )


@pytest.fixture
def base_time() -> datetime:
    return datetime(2026, 5, 1, 12, 0, 0, tzinfo=timezone.utc)


# --------------------------------------------------------------------------- #
# Constructor + introspection
# --------------------------------------------------------------------------- #


def test_constructor_defaults():
    mon = StreamingFleetMonitor()
    assert mon.n_observed == 0
    assert mon.latest_observed_at is None
    assert mon.earliest_observed_at is None


def test_constructor_rejects_non_positive_retention():
    with pytest.raises(ValueError):
        StreamingFleetMonitor(retention=timedelta(seconds=0))
    with pytest.raises(ValueError):
        StreamingFleetMonitor(retention=timedelta(seconds=-1))


def test_constructor_rejects_non_positive_max_retained():
    with pytest.raises(ValueError):
        StreamingFleetMonitor(max_retained=0)
    with pytest.raises(ValueError):
        StreamingFleetMonitor(max_retained=-1)


# --------------------------------------------------------------------------- #
# Ingestion
# --------------------------------------------------------------------------- #


def test_observe_episode_summarises_and_stores(base_time):
    mon = StreamingFleetMonitor(clock=lambda: base_time)
    summary = mon.observe_episode(
        _make_record(n_steps=20, M=4),
        episode_id="trip_1",
        classification="no_collision",
        metadata={"vehicle_id": "vh_42"},
    )
    assert isinstance(summary, EpisodeSummary)
    assert summary.episode_id == "trip_1"
    assert summary.M == 4
    assert mon.n_observed == 1
    assert mon.latest_observed_at == base_time


def test_observe_summary_fast_path(base_time):
    """Distributed deployments summarise on the vehicle and ship the
    pre-summarised payload to the central monitor."""
    mon = StreamingFleetMonitor(clock=lambda: base_time)
    rec = _make_record(n_steps=10, M=3)
    pre = summarize_episode(rec, episode_id="trip_x", classification="no_collision")
    mon.observe_summary(
        pre, per_predictor_excluded_ever=[0, 0, 0], observed_at=base_time,
    )
    assert mon.n_observed == 1
    ws = mon.summary(window=None, now=base_time)
    assert ws.n_observed_in_window == 1


def test_observe_summary_rejects_mismatched_M(base_time):
    mon = StreamingFleetMonitor(clock=lambda: base_time)
    rec = _make_record(n_steps=10, M=3)
    pre = summarize_episode(rec)
    with pytest.raises(ValueError):
        mon.observe_summary(pre, per_predictor_excluded_ever=[0, 0])  # len != 3


def test_observe_summary_rejects_non_1d_exclusion(base_time):
    mon = StreamingFleetMonitor(clock=lambda: base_time)
    rec = _make_record(n_steps=10, M=3)
    pre = summarize_episode(rec)
    with pytest.raises(ValueError):
        mon.observe_summary(
            pre,
            per_predictor_excluded_ever=np.zeros((3, 3), dtype=np.int64),
        )


def test_observe_episode_uses_clock_when_observed_at_omitted(base_time):
    times = [base_time, base_time + timedelta(minutes=5)]
    idx = [0]

    def clock() -> datetime:
        return times[idx[0]]

    mon = StreamingFleetMonitor(clock=clock)
    mon.observe_episode(_make_record(), episode_id="t1")
    idx[0] = 1
    mon.observe_episode(_make_record(), episode_id="t2")
    assert mon.earliest_observed_at == times[0]
    assert mon.latest_observed_at == times[1]


# --------------------------------------------------------------------------- #
# Eviction
# --------------------------------------------------------------------------- #


def test_retention_evicts_on_observe(base_time):
    mon = StreamingFleetMonitor(retention=timedelta(hours=24))
    mon.observe_episode(_make_record(), episode_id="old", observed_at=base_time)
    assert mon.n_observed == 1
    mon.observe_episode(
        _make_record(),
        episode_id="new",
        observed_at=base_time + timedelta(hours=25),
    )
    # The 25-hour-newer write evicts the 0-hour one.
    assert mon.n_observed == 1
    assert mon.latest_observed_at == base_time + timedelta(hours=25)


def test_max_retained_evicts_oldest(base_time):
    mon = StreamingFleetMonitor(max_retained=2)
    for i in range(5):
        mon.observe_episode(
            _make_record(),
            episode_id=f"trip_{i}",
            observed_at=base_time + timedelta(minutes=i),
        )
    assert mon.n_observed == 2
    # Only the two most recent survive.
    assert mon.earliest_observed_at == base_time + timedelta(minutes=3)
    assert mon.latest_observed_at == base_time + timedelta(minutes=4)


def test_prune_returns_eviction_count(base_time):
    mon = StreamingFleetMonitor()
    for i in range(5):
        mon.observe_episode(
            _make_record(),
            episode_id=f"trip_{i}",
            observed_at=base_time + timedelta(minutes=i),
        )
    evicted = mon.prune(older_than=base_time + timedelta(minutes=3))
    assert evicted == 3
    assert mon.n_observed == 2


# --------------------------------------------------------------------------- #
# Windowed summary
# --------------------------------------------------------------------------- #


def test_summary_empty_monitor_returns_zero_episode_summary():
    mon = StreamingFleetMonitor()
    ws = mon.summary(window=timedelta(hours=24))
    assert ws.n_observed_in_window == 0
    assert ws.fleet.n_episodes == 0
    assert ws.fleet.argmax_flips_per_step == {
        "mean": 0.0, "p50": 0.0, "p95": 0.0, "p99": 0.0,
    }


def test_summary_window_filters_by_observed_at(base_time):
    mon = StreamingFleetMonitor()
    mon.observe_episode(
        _make_record(), episode_id="old", observed_at=base_time,
    )
    mon.observe_episode(
        _make_record(),
        episode_id="recent",
        observed_at=base_time + timedelta(hours=23, minutes=50),
    )
    ws = mon.summary(
        window=timedelta(hours=1),
        now=base_time + timedelta(hours=24),
    )
    # Only "recent" sits in the [now-1h, now] window.
    assert ws.n_observed_in_window == 1
    assert ws.fleet.episodes[0].episode_id == "recent"


def test_summary_window_none_returns_all(base_time):
    mon = StreamingFleetMonitor()
    for i in range(3):
        mon.observe_episode(
            _make_record(),
            episode_id=f"trip_{i}",
            observed_at=base_time + timedelta(hours=i),
        )
    ws = mon.summary(window=None)
    assert ws.n_observed_in_window == 3
    assert ws.window_start == base_time
    assert ws.window_end == base_time + timedelta(hours=2)


def test_summary_default_now_is_latest_observation(base_time):
    mon = StreamingFleetMonitor()
    ts = base_time + timedelta(hours=5)
    mon.observe_episode(_make_record(), episode_id="t", observed_at=ts)
    ws = mon.summary(window=timedelta(hours=1))
    # ``now`` defaults to the latest observation, so the window is
    # [ts - 1h, ts] and the single observation falls inside.
    assert ws.window_end == ts
    assert ws.n_observed_in_window == 1


def test_summary_rejects_non_positive_window():
    mon = StreamingFleetMonitor()
    with pytest.raises(ValueError):
        mon.summary(window=timedelta(seconds=0))
    with pytest.raises(ValueError):
        mon.summary(window=timedelta(seconds=-10))


# --------------------------------------------------------------------------- #
# Batch-parity invariant — the streaming monitor's core contract
# --------------------------------------------------------------------------- #


def test_streaming_summary_matches_batch_aggregate_fleet(base_time):
    """The streaming monitor's aggregate over a window is identical to
    what :func:`aggregate_fleet` would produce on the same episodes
    fed in batch. This is the streaming module's load-bearing contract:
    a buyer comparing rolling-window numbers to historical batch
    numbers must see byte-identical aggregation logic.
    """
    records = [
        _make_record(n_steps=20, M=3, flips=False, excluded_predictor=-1),
        _make_record(n_steps=15, M=3, flips=True, excluded_predictor=2),
        _make_record(n_steps=30, M=3, flips=False, excluded_predictor=0),
    ]
    ids = ["trip_1", "trip_2", "trip_3"]
    classifications = ["no_collision", "collision", "no_collision"]

    batch = aggregate_fleet(records, ids, classifications)

    mon = StreamingFleetMonitor()
    for i, (rec, eid, cls) in enumerate(zip(records, ids, classifications)):
        mon.observe_episode(
            rec,
            episode_id=eid,
            classification=cls,
            observed_at=base_time + timedelta(minutes=i),
        )
    ws = mon.summary(window=None)
    streamed = ws.fleet

    assert streamed.n_episodes == batch.n_episodes
    assert streamed.n_total_steps == batch.n_total_steps
    assert streamed.classification_counts == batch.classification_counts
    assert streamed.argmax_flips_per_step == batch.argmax_flips_per_step
    assert streamed.deadband_fired_rate == batch.deadband_fired_rate
    assert streamed.per_predictor_excluded_rate == batch.per_predictor_excluded_rate


def test_streaming_per_predictor_exclusion_pads_when_M_grows(base_time):
    """If a later episode reports more predictors than earlier ones,
    per-predictor exclusion aggregation must use the fleet-wide M
    width (matching the batch path's behaviour)."""
    mon = StreamingFleetMonitor()
    mon.observe_episode(
        _make_record(M=2),
        episode_id="t1",
        observed_at=base_time,
    )
    mon.observe_episode(
        _make_record(M=4, excluded_predictor=3),
        episode_id="t2",
        observed_at=base_time + timedelta(minutes=1),
    )
    ws = mon.summary(window=None)
    assert len(ws.fleet.per_predictor_excluded_rate) == 4
    # Predictor 3 was excluded in 1 of 2 episodes.
    assert ws.fleet.per_predictor_excluded_rate[3] == pytest.approx(0.5)


# --------------------------------------------------------------------------- #
# Alerts
# --------------------------------------------------------------------------- #


def test_alert_fires_when_threshold_crossed_above(base_time):
    mon = StreamingFleetMonitor()
    # Two flips-heavy episodes — argmax_flips_per_step.mean will be ~1.0.
    for i in range(2):
        mon.observe_episode(
            _make_record(n_steps=10, flips=True),
            episode_id=f"chatter_{i}",
            observed_at=base_time + timedelta(minutes=i),
        )
    rule = AlertRule(
        name="chatter_high",
        metric="argmax_flips_per_step.mean",
        threshold=0.5,
        direction="above",
    )
    alerts = mon.evaluate_alerts([rule], window=timedelta(hours=1))
    assert len(alerts) == 1
    assert alerts[0].rule.name == "chatter_high"
    assert alerts[0].observed_value > 0.5
    assert alerts[0].n_episodes == 2


def test_alert_does_not_fire_below_threshold(base_time):
    mon = StreamingFleetMonitor()
    mon.observe_episode(_make_record(flips=False), observed_at=base_time)
    rule = AlertRule(
        name="chatter_high",
        metric="argmax_flips_per_step.mean",
        threshold=0.1,
        direction="above",
    )
    alerts = mon.evaluate_alerts([rule], window=timedelta(hours=1))
    assert alerts == []


def test_alert_direction_below(base_time):
    """A 'below' rule fires when the metric drops under threshold —
    e.g. 'min_ci_lower_bound dropped below 0.90 across the fleet'."""
    mon = StreamingFleetMonitor()
    mon.observe_episode(_make_record(flips=False), observed_at=base_time)
    rule = AlertRule(
        name="argmax_too_quiet",
        metric="argmax_flips_per_step.mean",
        threshold=0.5,
        direction="below",
    )
    alerts = mon.evaluate_alerts([rule], window=timedelta(hours=1))
    assert len(alerts) == 1


def test_alert_min_episodes_suppresses_undersampled_window(base_time):
    """A rule with min_episodes=5 must not fire on a 1-episode window
    even if the metric crosses the threshold — protects against
    alerting on a single noisy point."""
    mon = StreamingFleetMonitor()
    mon.observe_episode(_make_record(flips=True), observed_at=base_time)
    rule = AlertRule(
        name="chatter_high",
        metric="argmax_flips_per_step.mean",
        threshold=0.0,
        direction="above",
        min_episodes=5,
    )
    alerts = mon.evaluate_alerts([rule], window=timedelta(hours=1))
    assert alerts == []


def test_alert_rule_rejects_invalid_direction():
    with pytest.raises(ValueError):
        AlertRule(name="x", metric="y", threshold=1.0, direction="sideways")


def test_alert_rule_rejects_negative_min_episodes():
    with pytest.raises(ValueError):
        AlertRule(
            name="x", metric="y", threshold=1.0,
            direction="above", min_episodes=-1,
        )


def test_alert_metric_path_resolves_nested_key(base_time):
    mon = StreamingFleetMonitor()
    mon.observe_episode(_make_record(flips=True), observed_at=base_time)
    rule = AlertRule(
        name="chatter_p99",
        metric="argmax_flips_per_step.p99",
        threshold=0.0,
        direction="above",
    )
    alerts = mon.evaluate_alerts([rule], window=timedelta(hours=1))
    assert len(alerts) == 1


def test_alert_unknown_metric_path_raises(base_time):
    mon = StreamingFleetMonitor()
    mon.observe_episode(_make_record(), observed_at=base_time)
    rule = AlertRule(
        name="bad",
        metric="this.path.does.not.exist",
        threshold=0.0,
    )
    with pytest.raises(KeyError):
        mon.evaluate_alerts([rule], window=timedelta(hours=1))


def test_alert_skips_metric_that_resolves_to_none(base_time):
    """v2_engaged_fraction is None when V2 was never enabled in the
    window. A rule referencing it must NOT fire (it's a data-availability
    issue, not an alert condition) — and must not raise either."""
    mon = StreamingFleetMonitor()
    mon.observe_episode(_make_record(), observed_at=base_time)
    rule = AlertRule(
        name="v2_quiet",
        metric="v2_engaged_fraction.mean",
        threshold=0.0,
        direction="above",
    )
    alerts = mon.evaluate_alerts([rule], window=timedelta(hours=1))
    assert alerts == []


def test_alert_to_dict_round_trip(base_time):
    mon = StreamingFleetMonitor()
    for i in range(2):
        mon.observe_episode(
            _make_record(flips=True),
            observed_at=base_time + timedelta(minutes=i),
        )
    rule = AlertRule(
        name="chatter",
        metric="argmax_flips_per_step.mean",
        threshold=0.0,
        direction="above",
    )
    alerts = mon.evaluate_alerts([rule], window=timedelta(hours=1))
    assert len(alerts) == 1
    payload = alerts[0].to_dict()
    assert payload["rule_name"] == "chatter"
    assert payload["direction"] == "above"
    assert payload["n_episodes"] == 2
    assert "window_start" in payload and "window_end" in payload


# --------------------------------------------------------------------------- #
# WindowedFleetSummary serialisation
# --------------------------------------------------------------------------- #


def test_windowed_fleet_summary_to_dict_round_trips(base_time):
    mon = StreamingFleetMonitor()
    mon.observe_episode(
        _make_record(),
        episode_id="t1",
        classification="no_collision",
        observed_at=base_time,
    )
    ws = mon.summary(window=None)
    payload = ws.to_dict()
    assert payload["n_observed_in_window"] == 1
    assert payload["fleet"]["n_episodes"] == 1
    assert "window_start" in payload and "window_end" in payload


# --------------------------------------------------------------------------- #
# Audit fixes — out-of-order ingest + bool-metric rejection
# --------------------------------------------------------------------------- #


def test_latest_observed_at_returns_max_by_timestamp_not_insertion_order(base_time):
    """Pinned regression: pre-fix ``latest_observed_at`` returned the
    *last inserted* observation's timestamp, so an out-of-order
    arrival (typical under network jitter on a production fleet)
    silently anchored ``summary(window=...)`` on a stale wall-clock
    time and dropped the genuinely-newest data from the window.
    """
    mon = StreamingFleetMonitor()
    mon.observe_episode(_make_record(), "first", observed_at=base_time)
    mon.observe_episode(
        _make_record(),
        "newest",
        observed_at=base_time + timedelta(hours=1),
    )
    # Late-arriving observation, *older* by wall time than "newest".
    mon.observe_episode(
        _make_record(),
        "late_old",
        observed_at=base_time - timedelta(minutes=10),
    )
    # Pre-fix this returned base_time - 10min (last inserted); post-fix
    # it returns base_time + 1h (max by timestamp).
    assert mon.latest_observed_at == base_time + timedelta(hours=1)
    assert mon.earliest_observed_at == base_time - timedelta(minutes=10)


def test_summary_default_now_uses_max_observed_at_under_out_of_order_ingest(base_time):
    """The window end-time defaults to the latest *by timestamp*. With
    out-of-order ingest, the genuinely-newest observation must remain
    inside the window."""
    mon = StreamingFleetMonitor()
    newest = base_time + timedelta(hours=1)
    mon.observe_episode(_make_record(), "newest", observed_at=newest)
    mon.observe_episode(
        _make_record(),
        "late_old",
        observed_at=base_time - timedelta(minutes=30),
    )
    ws = mon.summary(window=timedelta(hours=2))
    # Window covers [newest - 2h, newest]; both observations land inside.
    assert ws.window_end == newest
    assert ws.n_observed_in_window == 2


def test_eviction_refreshes_max_observed_at_when_max_was_evicted(base_time):
    """Out-of-order ingest can park the timestamp-max in the
    insertion-oldest slot, which FIFO eviction pops first. The
    monitor must rebuild ``_max_observed_at`` from the survivors so
    a subsequent ``latest_observed_at`` doesn't return a ghost time."""
    mon = StreamingFleetMonitor(max_retained=2)
    # Insert order: [t+10min (oldest), t+5min, t+1min] with max_retained=2.
    # After third insert, eviction pops t+10min (the timestamp-max).
    mon.observe_episode(
        _make_record(), "max", observed_at=base_time + timedelta(minutes=10),
    )
    mon.observe_episode(
        _make_record(), "mid", observed_at=base_time + timedelta(minutes=5),
    )
    mon.observe_episode(
        _make_record(), "young", observed_at=base_time + timedelta(minutes=1),
    )
    # Surviving max observed_at is t+5min.
    assert mon.latest_observed_at == base_time + timedelta(minutes=5)


def test_alert_rule_rejects_metric_resolving_to_bool(base_time):
    """Pinned regression: pre-fix ``_resolve_metric_path`` accepted
    bool as numeric (``isinstance(True, int)`` is True), so a future
    bool field in ``FleetSummary.to_dict()`` would silently become a
    numeric metric. Now bool is explicitly rejected.
    """
    from symbolu_robotics.bcvf_autonomous.analysis.streaming import (
        _resolve_metric_path,
    )
    view = {"meets_certification_floor": True}
    with pytest.raises(TypeError) as exc_info:
        _resolve_metric_path(view, "meets_certification_floor")
    assert "bool" in str(exc_info.value)


def test_resolve_metric_path_accepts_int_and_float(base_time):
    """Sanity: numeric metrics still resolve cleanly post-fix."""
    from symbolu_robotics.bcvf_autonomous.analysis.streaming import (
        _resolve_metric_path,
    )
    assert _resolve_metric_path({"x": 7}, "x") == 7.0
    assert _resolve_metric_path({"x": 7.5}, "x") == 7.5
    assert _resolve_metric_path({"x": {"y": 0.25}}, "x.y") == 0.25
