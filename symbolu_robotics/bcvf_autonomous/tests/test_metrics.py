"""Tests for bcvf_autonomous.metrics — DESIGN.md §4B.7."""

from __future__ import annotations

import math

import numpy as np
import pytest

from symbolu_robotics.bcvf_autonomous.metrics import (
    AggregateMetrics,
    EpisodeMetrics,
    build_summary_table,
    compare_collision_rates,
    compare_continuous_metric,
    compute_aggregate_metrics,
    compute_early_warning_time,
    compute_episode_metrics,
    fisher_exact_2x2,
    welch_t_test,
    wilson_ci,
)
from symbolu_robotics.bcvf_autonomous.runner import EpisodeDiagnostics


def _make_diagnostics(
    T: int = 20,
    collision_step: int | None = None,
    bcvf_costs: np.ndarray | None = None,
    path_length: float = 100.0,
    path_efficiency: float = 1.0,
    rms_jerk: float = 0.5,
) -> EpisodeDiagnostics:
    gt = np.stack(
        [np.linspace(0.0, path_length, T), np.zeros(T), np.zeros(T)], axis=-1
    )
    controls = np.zeros((T, 2))
    bcvf = (
        bcvf_costs
        if bcvf_costs is not None
        else np.zeros(T, dtype=np.float64)
    )
    return EpisodeDiagnostics(
        config={},
        collision=collision_step is not None,
        collision_step=collision_step,
        total_steps=T,
        ground_truth_trajectory=gt,
        predictor_trajectories={},
        applied_controls=controls,
        bcvf_costs=bcvf,
        perf_costs=np.zeros(T),
        total_costs=np.zeros(T),
        solve_times_ms=np.full(T, 5.0),
        effective_samples=np.full(T, 50.0),
        mean_solve_time_ms=5.0,
        p99_solve_time_ms=7.0,
        path_length=path_length,
        path_efficiency=path_efficiency,
        mean_lateral_deviation=0.0,
        rms_lateral_jerk=rms_jerk,
    )


# --- Per-episode ---


def test_path_length_straight_line() -> None:
    diag = _make_diagnostics(T=101, path_length=100.0, path_efficiency=1.0)
    m = compute_episode_metrics(diag)
    assert m.path_length == pytest.approx(100.0)


def test_path_efficiency_perfect() -> None:
    diag = _make_diagnostics(path_efficiency=1.0)
    m = compute_episode_metrics(diag)
    assert m.path_efficiency == pytest.approx(1.0)


def test_path_efficiency_detour() -> None:
    diag = _make_diagnostics(path_efficiency=1.10)
    m = compute_episode_metrics(diag)
    assert m.path_efficiency == pytest.approx(1.10)


def test_lateral_jerk_constant_velocity() -> None:
    diag = _make_diagnostics(rms_jerk=0.0)
    m = compute_episode_metrics(diag)
    assert m.rms_lateral_jerk == pytest.approx(0.0)


def test_steering_rate_constant() -> None:
    diag = _make_diagnostics()
    diag.applied_controls[:, 1] = 0.1  # constant steering
    m = compute_episode_metrics(diag)
    assert m.rms_steering_rate == pytest.approx(0.0)


def test_bcvf_activation_rate_zero_nominal() -> None:
    diag = _make_diagnostics(bcvf_costs=np.zeros(20))
    m = compute_episode_metrics(diag)
    assert m.bcvf_activation_rate == 0.0


def test_bcvf_activation_rate_half() -> None:
    costs = np.zeros(20)
    costs[:10] = 1.0  # half the steps above threshold
    diag = _make_diagnostics(bcvf_costs=costs)
    m = compute_episode_metrics(diag, bcvf_activation_threshold=0.5)
    assert m.bcvf_activation_rate == pytest.approx(0.5)


# --- Early warning ---


def test_early_warning_time_basic() -> None:
    # Baseline collides at step 100 (dt=0.1 -> 10s).
    baseline = _make_diagnostics(T=100, collision_step=100)
    bcvf_costs = np.zeros(100)
    bcvf_costs[50:] = 1.0  # first activation at step 50 (t=5s).
    bcvf = _make_diagnostics(bcvf_costs=bcvf_costs)
    ewt = compute_early_warning_time(bcvf, baseline, bcvf_activation_threshold=0.5)
    assert ewt == pytest.approx(100 * 0.1 - 50 * 0.1)


def test_early_warning_time_no_baseline_collision() -> None:
    baseline = _make_diagnostics(collision_step=None)
    bcvf = _make_diagnostics()
    assert compute_early_warning_time(bcvf, baseline) is None


# --- Wilson CI ---


def test_wilson_ci_zero_rate() -> None:
    lo, hi = wilson_ci(0, 100)
    assert lo == 0.0
    assert hi < 0.05


def test_wilson_ci_full_rate() -> None:
    lo, hi = wilson_ci(100, 100)
    assert hi > 0.99
    assert lo > 0.95


def test_wilson_ci_half_rate() -> None:
    lo, hi = wilson_ci(50, 100)
    assert 0.39 < lo < 0.41
    assert 0.59 < hi < 0.61


# --- Aggregate ---


def test_aggregate_metrics_shapes() -> None:
    ms = [
        EpisodeMetrics(
            collision=(i % 4 == 0),
            collision_step=i if i % 4 == 0 else None,
            collision_time=None,
            path_efficiency=1.0 + 0.01 * i,
            rms_lateral_jerk=0.5,
            mean_bcvf_cost=0.1,
            bcvf_activation_rate=0.05,
            mean_solve_time_ms=5.0,
            p99_solve_time_ms=7.0,
        )
        for i in range(20)
    ]
    agg = compute_aggregate_metrics(ms)
    assert agg.n_runs == 20
    assert 0.0 < agg.collision_rate < 1.0
    assert agg.collision_rate_ci_low <= agg.collision_rate <= agg.collision_rate_ci_high


# --- Comparisons ---


def test_compare_collision_rates_significant() -> None:
    a = AggregateMetrics(
        n_runs=100,
        collision_rate=0.85,
        collision_rate_ci_low=0.77,
        collision_rate_ci_high=0.91,
        early_warning_time_median=None,
        early_warning_time_iqr=None,
        path_efficiency_mean=1.0,
        path_efficiency_std=0.0,
        rms_lateral_jerk_mean=0.0,
        rms_lateral_jerk_std=0.0,
        false_positive_rate=0.0,
        mean_bcvf_cost_mean=0.0,
        mean_bcvf_cost_std=0.0,
        solve_time_mean_ms=0.0,
        solve_time_p99_ms=0.0,
    )
    b = AggregateMetrics(**{**a.__dict__, "collision_rate": 0.05})
    result = compare_collision_rates(a, b)
    assert result.significant
    assert result.p_value < 0.001


def test_compare_continuous_metric() -> None:
    rng = np.random.default_rng(0)
    a = rng.normal(loc=1.0, scale=0.1, size=50)
    b = rng.normal(loc=1.5, scale=0.1, size=50)
    res = compare_continuous_metric(a, b, "x")
    assert res.significant
    assert res.p_value < 0.01


# --- Summary table ---


# --- Recovery metrics (B2-smoke follow-up) ---


def _diag_with_y(y_series: np.ndarray) -> EpisodeDiagnostics:
    """Make an EpisodeDiagnostics whose ground_truth y-column is y_series."""
    T = y_series.size
    gt = np.stack([np.linspace(0.0, T, T), y_series, np.zeros(T)], axis=-1)
    return EpisodeDiagnostics(
        config={},
        collision=False,
        collision_step=None,
        total_steps=T,
        ground_truth_trajectory=gt,
        predictor_trajectories={},
        applied_controls=np.zeros((T, 2)),
        bcvf_costs=np.zeros(T),
        perf_costs=np.zeros(T),
        total_costs=np.zeros(T),
        solve_times_ms=np.full(T, 5.0),
        effective_samples=np.full(T, 50.0),
        mean_solve_time_ms=5.0,
        p99_solve_time_ms=7.0,
        path_length=float(T),
        path_efficiency=1.0,
        mean_lateral_deviation=float(np.mean(np.abs(y_series))),
        rms_lateral_jerk=0.0,
    )


def test_final_lateral_deviation_uses_last_step() -> None:
    diag = _diag_with_y(np.array([0.0, 3.0, 5.0, 2.0]))
    m = compute_episode_metrics(diag, dt=0.1)
    assert m.final_lateral_deviation == pytest.approx(2.0)


def test_time_integrated_lateral_sums_over_dt() -> None:
    # Constant |y| = 0.5, 20 steps, dt = 0.1 → ∫|y|dt = 0.5 * 20 * 0.1 = 1.0.
    diag = _diag_with_y(np.full(20, 0.5))
    m = compute_episode_metrics(diag, dt=0.1)
    assert m.time_integrated_lateral == pytest.approx(1.0)


def test_post_peak_recovery_returns_seconds_from_peak() -> None:
    # Peak at index 2 (y=5). Recover to |y|<0.5 at index 5. Gap = 3 steps → 0.3s.
    y = np.array([0.0, 3.0, 5.0, 3.0, 1.0, 0.3, 0.1, 0.1])
    diag = _diag_with_y(y)
    m = compute_episode_metrics(diag, dt=0.1, recovery_threshold_m=0.5)
    # (index_of_first_below + 1) * dt — 'first below' in after-peak slice is
    # index 2 of that slice (step 5 of full series), so (2+1)*0.1 = 0.3s.
    assert m.post_peak_recovery_s == pytest.approx(0.3)


def test_post_peak_recovery_none_when_never_recovers() -> None:
    # Monotonic excursion, never re-enters threshold after peak.
    y = np.array([0.0, 1.0, 2.0, 3.0, 4.0, 5.0])
    diag = _diag_with_y(y)
    m = compute_episode_metrics(diag, dt=0.1, recovery_threshold_m=0.5)
    assert m.post_peak_recovery_s is None


def test_aggregate_recovery_rate_counts_only_recoverers() -> None:
    """3 of 5 episodes recover → recovery_rate = 0.6."""
    recovered = EpisodeMetrics(
        collision=False, collision_step=None, collision_time=None,
        final_lateral_deviation=0.1,
        time_integrated_lateral=5.0,
        post_peak_recovery_s=0.5,
    )
    not_recovered = EpisodeMetrics(
        collision=False, collision_step=None, collision_time=None,
        final_lateral_deviation=10.0,
        time_integrated_lateral=200.0,
        post_peak_recovery_s=None,
    )
    agg = compute_aggregate_metrics([recovered, recovered, recovered, not_recovered, not_recovered])
    assert agg.recovery_rate == pytest.approx(0.6)
    # Median recovery time taken only over recoverers.
    assert agg.post_peak_recovery_median_s == pytest.approx(0.5)
    # Final lateral mean across all 5 runs.
    assert agg.final_lateral_mean == pytest.approx((3 * 0.1 + 2 * 10.0) / 5.0)


def test_summary_table_structure() -> None:
    agg = AggregateMetrics(
        n_runs=10,
        collision_rate=0.1,
        collision_rate_ci_low=0.01,
        collision_rate_ci_high=0.3,
        early_warning_time_median=3.0,
        early_warning_time_iqr=(2.5, 3.5),
        path_efficiency_mean=1.02,
        path_efficiency_std=0.01,
        rms_lateral_jerk_mean=0.5,
        rms_lateral_jerk_std=0.05,
        false_positive_rate=0.01,
        mean_bcvf_cost_mean=0.1,
        mean_bcvf_cost_std=0.05,
        solve_time_mean_ms=5.0,
        solve_time_p99_ms=7.0,
    )
    results = {
        ("S1_normal_driving", "A0_baseline"): agg,
        ("S6_glass_corridor", "A3_second_bcvf"): agg,
    }
    table = build_summary_table(results)
    assert "S1_normal_driving" in table
    assert "A0_baseline" in table["S1_normal_driving"]
    assert "collision_rate" in table["S1_normal_driving"]["A0_baseline"]


# --- Stats internals ---


def test_fisher_exact_symmetry() -> None:
    _, p_ab = fisher_exact_2x2(10, 0, 0, 10)
    assert p_ab < 0.001


def test_welch_t_extreme() -> None:
    rng = np.random.default_rng(0)
    a = rng.normal(loc=1.0, scale=0.1, size=60)
    b = rng.normal(loc=5.0, scale=0.1, size=60)
    _, p = welch_t_test(a, b)
    assert p < 1e-9
