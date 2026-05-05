"""Behavioural tests for the real-time-budget framework.

The framework is the §9-row-#4 industry-features-roadmap pick.
These tests pin the load-bearing contracts:

* :class:`RealTimeBudget` validates every knob at construction.
* :class:`LatencyMonitor` correctly classifies observations
  against budget tiers (p99 / p999 / p9999 / max), with
  mutually-exclusive tier counters (a tick exceeding p9999
  but not max increments only n_p9999_violations).
* :func:`summary` honours the percentile-availability
  discipline: p999 / p9999 are ``None`` below documented
  sample-count thresholds.
* The over-budget audit log is bounded by the ring-buffer
  capacity.
* The monitor's ``observe_series`` bulk-ingests a
  per-tick latency array.
* :meth:`reset` clears observations + counters + ring buffer
  without changing the budget.
* Edge cases: empty observations, exactly-at-threshold,
  negative input rejection.
"""

from __future__ import annotations

import numpy as np
import pytest

from symbolu_robotics.bcvf_autonomous.realtime import (
    AllocationTrace,
    BudgetSummary,
    BudgetViolationError,
    LatencyMonitor,
    OverBudgetTick,
    RealTimeBudget,
    RealTimeBudgetError,
)


# --------------------------------------------------------------------------- #
# Helpers
# --------------------------------------------------------------------------- #


def _default_budget(**overrides) -> RealTimeBudget:
    base = dict(
        target_hz=100.0,
        p99_budget_ms=8.0,
        p999_budget_ms=9.5,
        p9999_budget_ms=10.0,
        max_budget_ms=15.0,
        min_samples_for_p999=1000,
        min_samples_for_p9999=10000,
        over_budget_log_capacity=100,
    )
    base.update(overrides)
    return RealTimeBudget(**base)


# --------------------------------------------------------------------------- #
# RealTimeBudget construction + validation
# --------------------------------------------------------------------------- #


def test_budget_construction_with_defaults_succeeds():
    budget = RealTimeBudget()
    assert budget.target_hz == 100.0
    assert budget.deadline_ms == 10.0


def test_budget_deadline_ms_derives_from_target_hz():
    assert RealTimeBudget(target_hz=10.0).deadline_ms == 100.0  # automotive
    assert RealTimeBudget(target_hz=50.0).deadline_ms == 20.0   # industrial
    assert RealTimeBudget(
        target_hz=100.0,
        p99_budget_ms=8.0,
        p999_budget_ms=9.5,
        p9999_budget_ms=10.0,
        max_budget_ms=15.0,
    ).deadline_ms == 10.0  # drone


def test_budget_rejects_non_positive_target_hz():
    with pytest.raises(RealTimeBudgetError, match="target_hz"):
        RealTimeBudget(target_hz=0)
    with pytest.raises(RealTimeBudgetError, match="target_hz"):
        RealTimeBudget(target_hz=-100)


def test_budget_rejects_non_positive_ms_thresholds():
    with pytest.raises(RealTimeBudgetError, match="p99_budget_ms"):
        _default_budget(p99_budget_ms=0)
    with pytest.raises(RealTimeBudgetError, match="p999_budget_ms"):
        _default_budget(p999_budget_ms=-1)
    with pytest.raises(RealTimeBudgetError, match="max_budget_ms"):
        _default_budget(max_budget_ms=0)


def test_budget_rejects_non_monotone_tiers():
    """Rarer percentiles are at least as loose as more common
    ones — a tighter p999 than p99 is a configuration error."""
    with pytest.raises(RealTimeBudgetError, match="p999_budget_ms"):
        _default_budget(p99_budget_ms=10.0, p999_budget_ms=8.0)
    with pytest.raises(RealTimeBudgetError, match="p9999_budget_ms"):
        _default_budget(p999_budget_ms=10.0, p9999_budget_ms=9.0)
    with pytest.raises(RealTimeBudgetError, match="max_budget_ms"):
        _default_budget(p9999_budget_ms=15.0, max_budget_ms=10.0)


def test_budget_rejects_too_small_min_samples():
    """A min_samples_for_p999 below 100 produces statistically
    meaningless reports — reject loud."""
    with pytest.raises(RealTimeBudgetError, match="min_samples_for_p999"):
        _default_budget(min_samples_for_p999=10)
    with pytest.raises(RealTimeBudgetError, match="min_samples_for_p9999"):
        _default_budget(min_samples_for_p9999=100)


def test_budget_rejects_zero_log_capacity():
    with pytest.raises(RealTimeBudgetError, match="over_budget_log_capacity"):
        _default_budget(over_budget_log_capacity=0)


def test_budget_to_dict_round_trips_keys():
    d = _default_budget().to_dict()
    assert set(d.keys()) == {
        "target_hz", "p99_budget_ms", "p999_budget_ms",
        "p9999_budget_ms", "max_budget_ms", "min_samples_for_p999",
        "min_samples_for_p9999", "over_budget_log_capacity",
    }


# --------------------------------------------------------------------------- #
# LatencyMonitor — construction
# --------------------------------------------------------------------------- #


def test_monitor_rejects_non_budget_input():
    with pytest.raises(RealTimeBudgetError, match="RealTimeBudget"):
        LatencyMonitor(budget="not a budget")  # type: ignore[arg-type]


def test_monitor_initial_state_is_empty():
    mon = LatencyMonitor(_default_budget())
    assert mon.n_observations == 0
    assert mon.budget.target_hz == 100.0
    assert mon.track_allocations is False


# --------------------------------------------------------------------------- #
# LatencyMonitor.observe — classification
# --------------------------------------------------------------------------- #


def test_observe_under_p99_increments_no_violation_counter():
    mon = LatencyMonitor(_default_budget())
    mon.observe(5.0, tick_index=0)
    mon.observe(7.0, tick_index=1)
    s = mon.summary()
    assert s.n_p99_violations == 0
    assert s.n_p999_violations == 0
    assert s.n_p9999_violations == 0
    assert s.n_max_violations == 0
    assert s.meets_budget is True


def test_observe_between_p99_and_p999_increments_p99_only():
    """Mutually-exclusive tier counters: a tick exceeding p99
    but not p999 increments only n_p99_violations."""
    mon = LatencyMonitor(_default_budget())
    mon.observe(8.5, tick_index=0)  # > 8.0 (p99), < 9.5 (p999)
    s = mon.summary()
    assert s.n_p99_violations == 1
    assert s.n_p999_violations == 0
    assert s.n_p9999_violations == 0
    assert s.n_max_violations == 0


def test_observe_between_p999_and_p9999_increments_p999_only():
    mon = LatencyMonitor(_default_budget())
    mon.observe(9.7, tick_index=0)  # > 9.5 (p999), < 10.0 (p9999)
    s = mon.summary()
    assert s.n_p99_violations == 0
    assert s.n_p999_violations == 1
    assert s.n_p9999_violations == 0


def test_observe_between_p9999_and_max_increments_p9999_only():
    mon = LatencyMonitor(_default_budget())
    mon.observe(12.0, tick_index=0)  # > 10.0 (p9999), < 15.0 (max)
    s = mon.summary()
    assert s.n_p9999_violations == 1
    assert s.n_max_violations == 0


def test_observe_above_max_increments_max_only():
    mon = LatencyMonitor(_default_budget())
    mon.observe(20.0, tick_index=0)
    s = mon.summary()
    assert s.n_max_violations == 1
    # Mutually-exclusive: max-tier violation does NOT also
    # increment p9999 / p999 / p99 counters.
    assert s.n_p9999_violations == 0
    assert s.n_p999_violations == 0
    assert s.n_p99_violations == 0


def test_observe_at_threshold_does_not_violate():
    """The tier check is strictly >, not ≥. A tick exactly at
    a threshold is in budget — design discipline."""
    mon = LatencyMonitor(_default_budget())
    mon.observe(8.0, tick_index=0)  # == p99 threshold
    mon.observe(15.0, tick_index=1)  # == max threshold
    s = mon.summary()
    assert s.n_p99_violations == 0
    assert s.n_max_violations == 0


def test_observe_rejects_non_numeric():
    mon = LatencyMonitor(_default_budget())
    with pytest.raises(RealTimeBudgetError, match="elapsed_ms"):
        mon.observe("5.0", tick_index=0)  # type: ignore[arg-type]


def test_observe_rejects_negative():
    mon = LatencyMonitor(_default_budget())
    with pytest.raises(RealTimeBudgetError, match="elapsed_ms must be"):
        mon.observe(-1.0, tick_index=0)


def test_observe_accepts_zero():
    """Zero is a valid measurement (a tick that took
    immeasurably little time, e.g. a no-op planner stub)."""
    mon = LatencyMonitor(_default_budget())
    mon.observe(0.0, tick_index=0)
    assert mon.n_observations == 1


# --------------------------------------------------------------------------- #
# LatencyMonitor.observe_series — bulk ingest
# --------------------------------------------------------------------------- #


def test_observe_series_bulk_ingests_array():
    mon = LatencyMonitor(_default_budget())
    series = np.array([5.0, 6.0, 7.0, 9.7, 12.0])
    mon.observe_series(series)
    assert mon.n_observations == 5
    s = mon.summary()
    assert s.n_p999_violations == 1  # 9.7
    assert s.n_p9999_violations == 1  # 12.0


def test_observe_series_with_tick_offset_preserves_unique_indices():
    mon = LatencyMonitor(_default_budget())
    mon.observe_series(np.array([20.0]), tick_offset=0)
    mon.observe_series(np.array([20.0]), tick_offset=100)
    s = mon.summary()
    indices = [t.tick_index for t in s.over_budget_ticks]
    assert 0 in indices and 100 in indices


def test_observe_series_rejects_non_1d_input():
    mon = LatencyMonitor(_default_budget())
    with pytest.raises(RealTimeBudgetError, match="1-D"):
        mon.observe_series(np.zeros((2, 3)))


def test_observe_series_rejects_negative_values():
    mon = LatencyMonitor(_default_budget())
    with pytest.raises(RealTimeBudgetError, match="negative"):
        mon.observe_series(np.array([5.0, -1.0, 7.0]))


# --------------------------------------------------------------------------- #
# Percentile-availability discipline
# --------------------------------------------------------------------------- #


def test_p999_is_none_below_min_samples_threshold():
    """The percentile-availability gate: p999 reported on n=10
    is statistical noise. Returns None instead."""
    mon = LatencyMonitor(_default_budget())
    for i in range(100):
        mon.observe(5.0, tick_index=i)
    s = mon.summary()
    assert s.p999_ms is None
    assert s.p9999_ms is None


def test_p999_reported_when_sample_count_clears_threshold():
    """Lowering min_samples_for_p999 lets a small load test
    surface a real p999. p9999 stays None because the floor
    on min_samples_for_p9999 (1000) prevents loosening below
    statistical-meaningfulness."""
    cfg = _default_budget(min_samples_for_p999=100)
    mon = LatencyMonitor(cfg)
    for i in range(150):
        mon.observe(5.0 + 0.01 * i, tick_index=i)
    s = mon.summary()
    assert s.p999_ms is not None
    assert s.p9999_ms is None  # 150 < 10000 (default min_samples_for_p9999)


def test_summary_meets_budget_true_on_clean_run():
    cfg = _default_budget(min_samples_for_p999=100)
    mon = LatencyMonitor(cfg)
    for i in range(150):
        mon.observe(5.0, tick_index=i)
    s = mon.summary()
    assert s.meets_budget is True
    assert s.over_budget_ticks == ()


def test_summary_meets_budget_false_on_any_violation():
    mon = LatencyMonitor(_default_budget())
    mon.observe(5.0, tick_index=0)
    mon.observe(20.0, tick_index=1)  # max violation
    s = mon.summary()
    assert s.meets_budget is False


def test_summary_on_empty_monitor_returns_none_percentiles():
    """Audit-fix Finding 6: empty-monitor percentiles must be
    None (not 0.0). Returning 0.0 would silently pass a CI gate
    of the form ``if summary.p99_ms > budget.p99_budget_ms``
    when the planner crashed before the first observe() — the
    "we shipped 0 ms p99" report is indistinguishable from
    "we passed"."""
    mon = LatencyMonitor(_default_budget())
    s = mon.summary()
    assert s.n_observations == 0
    assert s.mean_ms is None
    assert s.p50_ms is None
    assert s.p95_ms is None
    assert s.p99_ms is None
    assert s.p999_ms is None
    assert s.p9999_ms is None
    assert s.max_ms is None
    assert s.meets_budget is True  # vacuously


# --------------------------------------------------------------------------- #
# Over-budget audit log
# --------------------------------------------------------------------------- #


def test_over_budget_ticks_record_tier_and_threshold():
    mon = LatencyMonitor(_default_budget())
    mon.observe(8.5, tick_index=10)
    mon.observe(9.7, tick_index=20)
    mon.observe(20.0, tick_index=30)
    s = mon.summary()
    assert len(s.over_budget_ticks) == 3
    by_idx = {t.tick_index: t for t in s.over_budget_ticks}
    assert by_idx[10].budget_tier == "p99"
    assert by_idx[10].threshold_ms == 8.0
    assert by_idx[20].budget_tier == "p999"
    assert by_idx[20].threshold_ms == 9.5
    assert by_idx[30].budget_tier == "max"
    assert by_idx[30].threshold_ms == 15.0


def test_over_budget_log_is_bounded_by_capacity():
    cfg = _default_budget(over_budget_log_capacity=5)
    mon = LatencyMonitor(cfg)
    for i in range(20):
        mon.observe(20.0, tick_index=i)  # max violation each tick
    s = mon.summary()
    assert len(s.over_budget_ticks) == 5
    # The ring buffer keeps the LATEST 5 violations.
    indices = [t.tick_index for t in s.over_budget_ticks]
    assert indices == [15, 16, 17, 18, 19]
    # But the violation counter is unbounded.
    assert s.n_max_violations == 20


# --------------------------------------------------------------------------- #
# reset()
# --------------------------------------------------------------------------- #


def test_reset_clears_observations_and_counters():
    mon = LatencyMonitor(_default_budget())
    for i in range(10):
        mon.observe(20.0, tick_index=i)
    assert mon.summary().n_max_violations == 10
    mon.reset()
    assert mon.n_observations == 0
    s = mon.summary()
    assert s.n_max_violations == 0
    assert s.over_budget_ticks == ()
    assert s.meets_budget is True


def test_reset_does_not_change_budget():
    mon = LatencyMonitor(_default_budget(target_hz=50.0))
    mon.reset()
    assert mon.budget.target_hz == 50.0


# --------------------------------------------------------------------------- #
# Allocation tracking (advisory)
# --------------------------------------------------------------------------- #


def test_allocation_trace_disabled_by_default():
    mon = LatencyMonitor(_default_budget())
    mon.observe(5.0, tick_index=0)
    s = mon.summary()
    assert s.allocation_trace is None


def test_allocation_trace_enabled_emits_advisory_summary():
    """When track_allocations=True, the summary carries an
    AllocationTrace. Advisory only — see §6 of the design doc."""
    mon = LatencyMonitor(_default_budget(), track_allocations=True)
    # Allocate some memory between observations to make the
    # trace non-trivial.
    junk = []
    for i in range(5):
        junk.append([0.0] * 1000)
        mon.observe(5.0, tick_index=i)
    s = mon.summary()
    assert s.allocation_trace is not None
    assert isinstance(s.allocation_trace, AllocationTrace)
    assert s.allocation_trace.n_observations == 5


# --------------------------------------------------------------------------- #
# BudgetSummary serialisation
# --------------------------------------------------------------------------- #


def test_budget_summary_to_dict_round_trips_keys():
    mon = LatencyMonitor(_default_budget())
    mon.observe(5.0, tick_index=0)
    mon.observe(20.0, tick_index=1)
    d = mon.summary().to_dict()
    # Audit-fix Finding 1: allocation_trace is now in the dict
    # (previously silently dropped).
    expected_keys = {
        "n_observations", "mean_ms", "p50_ms", "p95_ms", "p99_ms",
        "p999_ms", "p9999_ms", "max_ms",
        "n_p99_violations", "n_p999_violations",
        "n_p9999_violations", "n_max_violations",
        "over_budget_ticks", "budget", "meets_budget",
        "allocation_trace",
    }
    assert set(d.keys()) == expected_keys


def test_budget_summary_to_dict_preserves_none_for_missing_percentiles():
    """JSON round-trip: a None p999_ms must serialise as None,
    not as 0 or NaN. Downstream consumers must distinguish
    'not enough samples' from 'percentile is zero'."""
    mon = LatencyMonitor(_default_budget())
    mon.observe(5.0, tick_index=0)
    d = mon.summary().to_dict()
    assert d["p999_ms"] is None
    assert d["p9999_ms"] is None


def test_over_budget_tick_serialises_as_dict_with_named_fields():
    mon = LatencyMonitor(_default_budget())
    mon.observe(20.0, tick_index=42)
    d = mon.summary().to_dict()
    assert len(d["over_budget_ticks"]) == 1
    entry = d["over_budget_ticks"][0]
    assert entry["tick_index"] == 42
    assert entry["budget_tier"] == "max"
    assert entry["threshold_ms"] == 15.0
    assert entry["observed_ms"] == 20.0


# --------------------------------------------------------------------------- #
# Composition with EpisodeDiagnostics-style series
# --------------------------------------------------------------------------- #


def test_observe_series_replays_episode_diagnostics_style_input():
    """The monitor accepts the same per-tick latency series
    EpisodeDiagnostics.solve_times_ms carries — composition
    with the existing runner output is straight."""
    # Synthesise an EpisodeDiagnostics-style series.
    rng = np.random.default_rng(42)
    series = rng.uniform(2.0, 7.0, size=200).astype(np.float64)
    series[150] = 12.0  # one p9999 violation
    series[180] = 20.0  # one max violation
    mon = LatencyMonitor(_default_budget())
    mon.observe_series(series)
    s = mon.summary()
    assert s.n_observations == 200
    assert s.n_p9999_violations == 1
    assert s.n_max_violations == 1
    assert s.meets_budget is False


# --------------------------------------------------------------------------- #
# Errors
# --------------------------------------------------------------------------- #


def test_budget_violation_error_is_real_time_budget_error_subclass():
    """Catching the base class catches the violation subclass."""
    assert issubclass(BudgetViolationError, RealTimeBudgetError)
    err = BudgetViolationError("test")
    assert isinstance(err, RealTimeBudgetError)


# --------------------------------------------------------------------------- #
# Audit-fix regression pins (post-v0.7.x critical-audit pass on §9-row-#4)
# --------------------------------------------------------------------------- #


def test_audit_fix_observe_rejects_nan():
    """Audit Finding 2 (CRITICAL): a NaN tick used to slip
    past every guard. ``isinstance(nan, float)`` is True;
    ``nan < 0`` is False. The NaN polluted every percentile
    + the CI gate ``if not summary.meets_budget`` silently
    passed because no tier counter incremented (NaN
    comparisons are all False). The framework's whole point
    is to surface budget violations — it must not silently
    swallow NaN."""
    mon = LatencyMonitor(_default_budget())
    with pytest.raises(RealTimeBudgetError, match="finite"):
        mon.observe(float("nan"), tick_index=0)


def test_audit_fix_observe_rejects_positive_infinity():
    """Audit Finding 2 (companion): +Inf must also be rejected
    — ``inf > max_budget_ms`` is True so it would route to the
    max counter, but the percentile fields would still be Inf.
    Reject loud rather than poison the stats."""
    mon = LatencyMonitor(_default_budget())
    with pytest.raises(RealTimeBudgetError, match="finite"):
        mon.observe(float("inf"), tick_index=0)


def test_audit_fix_observe_rejects_negative_infinity():
    mon = LatencyMonitor(_default_budget())
    with pytest.raises(RealTimeBudgetError, match="finite"):
        mon.observe(float("-inf"), tick_index=0)


def test_audit_fix_observe_series_rejects_nan_in_array():
    """Audit Finding 2 (companion): bulk-ingest must also
    reject non-finite values. A single NaN in a 10⁶-tick series
    used to silently corrupt every downstream percentile."""
    mon = LatencyMonitor(_default_budget())
    series = np.array([5.0, 6.0, float("nan"), 7.0])
    with pytest.raises(RealTimeBudgetError, match="non-finite"):
        mon.observe_series(series)


def test_audit_fix_observe_rejects_bool():
    """Audit Finding 4: ``True isinstance int`` is True in
    Python. ``mon.observe(True, tick_index=i)`` used to slip
    past the type guard and contribute 1.0 to the latency
    series. A bug-prone caller writing
    ``mon.observe(planner_did_succeed, tick_index=i)`` should
    get a loud type error, not silent acceptance."""
    mon = LatencyMonitor(_default_budget())
    with pytest.raises(RealTimeBudgetError, match="number"):
        mon.observe(True, tick_index=0)
    with pytest.raises(RealTimeBudgetError, match="number"):
        mon.observe(False, tick_index=0)


def test_audit_fix_observe_accepts_numpy_scalars():
    """Audit Finding 4 (companion): ``np.float64(5.0)`` and
    ``np.int64(5)`` are what comes out of ``arr[i]`` when
    iterating a numpy array. Both must be accepted (a
    deployment partner feeding ``solve_times_ms[i]`` directly
    shouldn't get a type error)."""
    mon = LatencyMonitor(_default_budget())
    mon.observe(np.float64(5.0), tick_index=0)
    mon.observe(np.int64(7), tick_index=1)
    mon.observe(np.float32(3.0), tick_index=2)
    assert mon.n_observations == 3


def test_audit_fix_validator_rejects_equal_p99_p999():
    """Audit Finding 5: equal-tier budgets used to route a
    violation to whichever tier was checked first in the
    if/elif chain — silently dropping the tighter-tier
    counter. Strict-monotone validator now forbids equal
    tiers."""
    with pytest.raises(RealTimeBudgetError, match="strictly looser"):
        _default_budget(p99_budget_ms=8.0, p999_budget_ms=8.0)


def test_audit_fix_validator_rejects_equal_max_p9999():
    with pytest.raises(RealTimeBudgetError, match="bleeding-edge"):
        _default_budget(p9999_budget_ms=10.0, max_budget_ms=10.0)


def test_audit_fix_close_stops_tracemalloc_only_if_we_started_it():
    """Audit Finding 3: tracemalloc.start() is global.
    LatencyMonitor used to enable it without ever stopping —
    a leak that left the whole interpreter paying tracemalloc
    overhead for the rest of its lifetime. close() now
    stops tracemalloc only if THIS monitor enabled it."""
    import tracemalloc
    # Ensure tracemalloc is not already running.
    if tracemalloc.is_tracing():
        tracemalloc.stop()
    assert not tracemalloc.is_tracing()
    mon = LatencyMonitor(_default_budget(), track_allocations=True)
    assert tracemalloc.is_tracing()
    mon.close()
    assert not tracemalloc.is_tracing()


def test_audit_fix_close_does_not_stop_externally_started_tracemalloc():
    """Audit Finding 3 (companion): if tracemalloc was already
    running when LatencyMonitor was constructed, close() must
    NOT stop it — the external owner keeps theirs."""
    import tracemalloc
    if not tracemalloc.is_tracing():
        tracemalloc.start()
    try:
        mon = LatencyMonitor(_default_budget(), track_allocations=True)
        mon.close()
        # Externally-started tracemalloc is still running.
        assert tracemalloc.is_tracing()
    finally:
        tracemalloc.stop()


def test_audit_fix_close_is_idempotent():
    mon = LatencyMonitor(_default_budget())
    mon.close()
    mon.close()  # second call must not raise


def test_audit_fix_context_manager_calls_close():
    import tracemalloc
    if tracemalloc.is_tracing():
        tracemalloc.stop()
    with LatencyMonitor(_default_budget(), track_allocations=True) as mon:
        mon.observe(5.0, tick_index=0)
        assert tracemalloc.is_tracing()
    assert not tracemalloc.is_tracing()


def test_audit_fix_allocation_trace_round_trips_through_to_dict():
    """Audit Finding 1: BudgetSummary.to_dict used to silently
    drop allocation_trace. A recall investigator opening the
    JSON saw no allocation data even when track_allocations=True
    was set."""
    import tracemalloc
    if tracemalloc.is_tracing():
        tracemalloc.stop()
    with LatencyMonitor(_default_budget(), track_allocations=True) as mon:
        mon.observe(5.0, tick_index=0)
        mon.observe(6.0, tick_index=1)
        d = mon.summary().to_dict()
    assert "allocation_trace" in d
    if d["allocation_trace"] is not None:
        # When tracemalloc captures any allocations, the trace
        # serialises with the four documented fields.
        assert set(d["allocation_trace"].keys()) == {
            "n_observations",
            "mean_bytes_per_tick",
            "p99_bytes_per_tick",
            "max_bytes_per_tick",
        }


def test_audit_fix_allocation_trace_is_none_when_disabled():
    """When track_allocations=False, the trace is None and
    the to_dict entry is None — not missing."""
    mon = LatencyMonitor(_default_budget())
    mon.observe(5.0, tick_index=0)
    d = mon.summary().to_dict()
    assert "allocation_trace" in d
    assert d["allocation_trace"] is None


def test_audit_fix_observe_works_after_reset():
    """Coverage gap: reset() should leave the monitor usable.
    Pinned so a future deque/list re-init bug regresses loud."""
    mon = LatencyMonitor(_default_budget())
    mon.observe(5.0, tick_index=0)
    mon.observe(20.0, tick_index=1)
    mon.reset()
    # Use the monitor normally after reset.
    mon.observe(7.0, tick_index=2)
    mon.observe(8.5, tick_index=3)  # > p99
    s = mon.summary()
    assert s.n_observations == 2
    assert s.n_p99_violations == 1


def test_audit_fix_to_dict_preserves_none_for_empty_monitor():
    """Audit Finding 6 (companion): empty-monitor's None
    percentiles must round-trip through to_dict as None
    (not 0.0). Downstream JSON consumers must distinguish
    'no data' from 'p99 was zero'."""
    mon = LatencyMonitor(_default_budget())
    d = mon.summary().to_dict()
    for key in ("mean_ms", "p50_ms", "p95_ms", "p99_ms",
                "p999_ms", "p9999_ms", "max_ms"):
        assert d[key] is None, f"{key} should be None on empty monitor"


def test_audit_fix_canonical_to_dict_snapshot():
    """Audit Finding 9 (coverage gap): a JSON snapshot pin
    on BudgetSummary.to_dict surfaces shape regressions
    (dropped key, renamed field, changed nesting) that
    keys-only assertions miss."""
    cfg = _default_budget(min_samples_for_p999=100)
    mon = LatencyMonitor(cfg)
    for i in range(105):
        mon.observe(5.0, tick_index=i)
    mon.observe(20.0, tick_index=200)  # one max violation
    d = mon.summary().to_dict()

    assert d["n_observations"] == 106
    assert d["n_max_violations"] == 1
    assert d["meets_budget"] is False
    # Pin specific over_budget_tick shape.
    assert len(d["over_budget_ticks"]) == 1
    entry = d["over_budget_ticks"][0]
    assert entry == {
        "tick_index": 200,
        "observed_ms": 20.0,
        "budget_tier": "max",
        "threshold_ms": 15.0,
    }
    # Pin budget shape: every documented knob present.
    assert set(d["budget"].keys()) == {
        "target_hz", "p99_budget_ms", "p999_budget_ms",
        "p9999_budget_ms", "max_budget_ms",
        "min_samples_for_p999", "min_samples_for_p9999",
        "over_budget_log_capacity",
    }
