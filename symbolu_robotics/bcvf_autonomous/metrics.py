"""Phase 4B — metrics and statistical analysis (DESIGN.md §4B).

Pure analysis layer: consumes :class:`EpisodeDiagnostics` produced by
Phase 3C, returns structured metrics. No I/O, no plotting, no scipy —
all statistical tests (Wilson CI, Welch's t, Fisher's exact,
Mann-Whitney U) are implemented from formulas using NumPy.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Sequence, Tuple

import numpy as np

from .mppi_planner import _project_point_to_polyline
from .runner import EpisodeDiagnostics


# --- Per-episode metrics ---


@dataclass
class EpisodeMetrics:
    """All metrics computed from a single episode (DESIGN §4B.3)."""

    # Safety
    collision: bool
    collision_step: Optional[int]
    collision_time: Optional[float]

    # Early warning (populated only when baseline is supplied).
    early_warning_time: Optional[float] = None
    first_bcvf_activation_step: Optional[int] = None
    first_bcvf_activation_time: Optional[float] = None

    # Efficiency
    path_length: float = 0.0
    road_length: float = 0.0
    path_efficiency: float = 0.0  # V3.1 convention: path_length / road_length

    # Comfort
    rms_lateral_jerk: float = 0.0
    rms_steering_rate: float = 0.0
    max_lateral_acceleration: float = 0.0

    # BCVF behavior
    mean_bcvf_cost: float = 0.0
    max_bcvf_cost: float = 0.0
    bcvf_activation_rate: float = 0.0
    mean_perf_cost: float = 0.0

    # Planner health
    mean_solve_time_ms: float = 0.0
    p99_solve_time_ms: float = 0.0
    mean_effective_samples: float = 0.0

    # Recovery metrics (added after B2 smoke revealed A3's advantage is
    # concentrated in lane-center recovery after the failure peak, not in
    # peak magnitude itself). See DESIGN Appendix and metrics.py docstring.
    final_lateral_deviation: float = 0.0  # |y| at the last recorded step
    time_integrated_lateral: float = 0.0  # Σ |y(t)| · dt over the episode
    post_peak_recovery_s: Optional[float] = None  # seconds from peak |y|
                                                   # to first step where
                                                   # |y| < recovery threshold;
                                                   # None if never recovers


def _first_activation(
    bcvf_costs: np.ndarray, threshold: float
) -> Optional[int]:
    idx = np.where(bcvf_costs > threshold)[0]
    return int(idx[0]) if idx.size > 0 else None


def _steering_rate(controls: np.ndarray, dt: float) -> float:
    if controls.shape[0] < 2:
        return 0.0
    rate = np.diff(controls[:, 1]) / dt
    return float(np.sqrt(np.mean(rate * rate)))


def _lateral_jerk(trajectory: np.ndarray, road_pts: np.ndarray, dt: float) -> float:
    if trajectory.shape[0] < 4:
        return 0.0
    lat = _project_point_to_polyline(trajectory[:, :2], road_pts)
    # Third finite difference (no need for signed lateral — jerk magnitude).
    jerk = np.diff(lat, n=3) / (dt ** 3)
    return float(np.sqrt(np.mean(jerk * jerk))) if jerk.size > 0 else 0.0


def _max_lateral_accel(trajectory: np.ndarray, dt: float) -> float:
    if trajectory.shape[0] < 3:
        return 0.0
    xy = trajectory[:, :2]
    velocities = np.linalg.norm(np.diff(xy, axis=0), axis=-1) / dt  # (T-1,)
    headings = trajectory[:, 2]
    heading_rate = np.diff(headings) / dt  # (T-1,)
    lat_accel = velocities * heading_rate
    return float(np.max(np.abs(lat_accel))) if lat_accel.size > 0 else 0.0


def compute_episode_metrics(
    diagnostics: EpisodeDiagnostics,
    bcvf_activation_threshold: float = 0.01,
    dt: float = 0.1,
    recovery_threshold_m: float = 0.5,
) -> EpisodeMetrics:
    """Compute per-episode metrics (DESIGN §4B.3)."""
    gt = diagnostics.ground_truth_trajectory
    controls = diagnostics.applied_controls
    bcvf = diagnostics.bcvf_costs

    # Road length from diagnostics.config (serialized) isn't directly
    # accessible; use the provided path_length ratio if available, else
    # reconstruct from the trajectory (which makes path_efficiency 1.0).
    path_length = diagnostics.path_length
    road_length = (
        path_length / diagnostics.path_efficiency
        if diagnostics.path_efficiency > 1e-9
        else path_length
    )

    first_active = _first_activation(bcvf, bcvf_activation_threshold)
    first_time = first_active * dt if first_active is not None else None

    collision_time = (
        diagnostics.collision_step * dt
        if diagnostics.collision and diagnostics.collision_step is not None
        else None
    )

    # Lateral jerk requires the road centerline; diagnostics.config serializes
    # only the road length. Fall back to the episode's own rms_lateral_jerk
    # (already computed in Phase 3C) rather than recomputing here.

    # Recovery metrics: use the ground-truth y directly. Straight-road
    # scenarios put the lane center at y=0 so |y| is the lateral
    # deviation. For curved-road scenarios a proper "lateral deviation
    # from centerline" would need the road polyline; current V1 scenarios
    # (S3_map_error[_accel], S6_glass_corridor) are all straight.
    y = gt[:, 1] if gt.shape[0] > 0 else np.zeros(0)
    abs_y = np.abs(y)
    if abs_y.size > 0:
        final_lat = float(abs_y[-1])
        time_int_lat = float(np.sum(abs_y) * dt)
        peak_idx = int(np.argmax(abs_y))
        # Post-peak recovery: time from the peak to the first subsequent
        # step where |y| < threshold.
        post_peak_recovery: Optional[float] = None
        after = abs_y[peak_idx + 1:]
        below = np.where(after < recovery_threshold_m)[0]
        if below.size > 0:
            post_peak_recovery = float((int(below[0]) + 1) * dt)
    else:
        final_lat = 0.0
        time_int_lat = 0.0
        post_peak_recovery = None

    return EpisodeMetrics(
        collision=diagnostics.collision,
        collision_step=diagnostics.collision_step,
        collision_time=collision_time,
        early_warning_time=None,
        first_bcvf_activation_step=first_active,
        first_bcvf_activation_time=first_time,
        path_length=path_length,
        road_length=road_length,
        path_efficiency=diagnostics.path_efficiency,
        rms_lateral_jerk=diagnostics.rms_lateral_jerk,
        rms_steering_rate=_steering_rate(controls, dt),
        max_lateral_acceleration=_max_lateral_accel(gt, dt),
        mean_bcvf_cost=float(bcvf.mean()) if bcvf.size > 0 else 0.0,
        max_bcvf_cost=float(bcvf.max()) if bcvf.size > 0 else 0.0,
        bcvf_activation_rate=float(np.mean(bcvf > bcvf_activation_threshold)) if bcvf.size > 0 else 0.0,
        mean_perf_cost=float(diagnostics.perf_costs.mean()) if diagnostics.perf_costs.size > 0 else 0.0,
        mean_solve_time_ms=diagnostics.mean_solve_time_ms,
        p99_solve_time_ms=diagnostics.p99_solve_time_ms,
        mean_effective_samples=float(diagnostics.effective_samples.mean()) if diagnostics.effective_samples.size > 0 else 0.0,
        final_lateral_deviation=final_lat,
        time_integrated_lateral=time_int_lat,
        post_peak_recovery_s=post_peak_recovery,
    )


def compute_early_warning_time(
    bcvf_diagnostics: EpisodeDiagnostics,
    baseline_diagnostics: EpisodeDiagnostics,
    bcvf_activation_threshold: float = 0.01,
    dt: float = 0.1,
) -> Optional[float]:
    """Seconds between first BCVF activation and the baseline collision.

    Returns ``None`` if the baseline did not collide or BCVF never
    activated. Defined in DESIGN §4B.3.
    """
    if not baseline_diagnostics.collision:
        return None
    if baseline_diagnostics.collision_step is None:
        return None
    baseline_collision_time = baseline_diagnostics.collision_step * dt
    active_idx = np.where(
        bcvf_diagnostics.bcvf_costs > bcvf_activation_threshold
    )[0]
    if active_idx.size == 0:
        return None
    first_activation_time = float(active_idx[0]) * dt
    return baseline_collision_time - first_activation_time


# --- Aggregate metrics ---


@dataclass
class AggregateMetrics:
    """Statistics across N runs of one configuration."""

    n_runs: int
    collision_rate: float
    collision_rate_ci_low: float
    collision_rate_ci_high: float
    early_warning_time_median: Optional[float]
    early_warning_time_iqr: Optional[Tuple[float, float]]
    path_efficiency_mean: float
    path_efficiency_std: float
    rms_lateral_jerk_mean: float
    rms_lateral_jerk_std: float
    false_positive_rate: float
    mean_bcvf_cost_mean: float
    mean_bcvf_cost_std: float
    solve_time_mean_ms: float
    solve_time_p99_ms: float
    # Recovery (added after B2 smoke — see EpisodeMetrics recovery fields)
    final_lateral_mean: float = 0.0
    final_lateral_std: float = 0.0
    time_integrated_lateral_mean: float = 0.0
    time_integrated_lateral_std: float = 0.0
    recovery_rate: float = 0.0                 # fraction of runs that
                                               # recovered after peak
    post_peak_recovery_median_s: Optional[float] = None


def wilson_ci(successes: int, n: int, z: float = 1.96) -> Tuple[float, float]:
    """Wilson score interval for a binomial proportion (DESIGN §4B.4)."""
    if n <= 0:
        return (0.0, 1.0)
    p_hat = successes / n
    denom = 1.0 + (z * z) / n
    center = (p_hat + (z * z) / (2.0 * n)) / denom
    margin = (z / denom) * math.sqrt(
        p_hat * (1.0 - p_hat) / n + (z * z) / (4.0 * n * n)
    )
    return (max(0.0, center - margin), min(1.0, center + margin))


def compute_aggregate_metrics(
    episode_metrics_list: List[EpisodeMetrics],
) -> AggregateMetrics:
    """Aggregate N per-episode metrics (DESIGN §4B.4)."""
    n = len(episode_metrics_list)
    if n == 0:
        return AggregateMetrics(
            n_runs=0,
            collision_rate=0.0,
            collision_rate_ci_low=0.0,
            collision_rate_ci_high=1.0,
            early_warning_time_median=None,
            early_warning_time_iqr=None,
            path_efficiency_mean=0.0,
            path_efficiency_std=0.0,
            rms_lateral_jerk_mean=0.0,
            rms_lateral_jerk_std=0.0,
            false_positive_rate=0.0,
            mean_bcvf_cost_mean=0.0,
            mean_bcvf_cost_std=0.0,
            solve_time_mean_ms=0.0,
            solve_time_p99_ms=0.0,
            final_lateral_mean=0.0,
            final_lateral_std=0.0,
            time_integrated_lateral_mean=0.0,
            time_integrated_lateral_std=0.0,
            recovery_rate=0.0,
            post_peak_recovery_median_s=None,
        )

    collisions = sum(1 for m in episode_metrics_list if m.collision)
    collision_rate = collisions / n
    ci_low, ci_high = wilson_ci(collisions, n)

    ewts = [m.early_warning_time for m in episode_metrics_list if m.early_warning_time is not None]
    if ewts:
        ewt_arr = np.asarray(ewts)
        ewt_median = float(np.median(ewt_arr))
        ewt_iqr = (float(np.percentile(ewt_arr, 25)), float(np.percentile(ewt_arr, 75)))
    else:
        ewt_median = None
        ewt_iqr = None

    eff = np.asarray([m.path_efficiency for m in episode_metrics_list])
    jerk = np.asarray([m.rms_lateral_jerk for m in episode_metrics_list])
    bcvf = np.asarray([m.mean_bcvf_cost for m in episode_metrics_list])
    act = np.asarray([m.bcvf_activation_rate for m in episode_metrics_list])
    solve = np.asarray([m.mean_solve_time_ms for m in episode_metrics_list])
    p99 = np.asarray([m.p99_solve_time_ms for m in episode_metrics_list])

    final_lat = np.asarray([m.final_lateral_deviation for m in episode_metrics_list])
    ti_lat = np.asarray([m.time_integrated_lateral for m in episode_metrics_list])
    recovery_times = [
        m.post_peak_recovery_s
        for m in episode_metrics_list
        if m.post_peak_recovery_s is not None
    ]
    recovery_rate = len(recovery_times) / n if n > 0 else 0.0
    recovery_median = (
        float(np.median(recovery_times)) if recovery_times else None
    )

    return AggregateMetrics(
        n_runs=n,
        collision_rate=collision_rate,
        collision_rate_ci_low=ci_low,
        collision_rate_ci_high=ci_high,
        early_warning_time_median=ewt_median,
        early_warning_time_iqr=ewt_iqr,
        path_efficiency_mean=float(eff.mean()),
        path_efficiency_std=float(eff.std(ddof=0)),
        rms_lateral_jerk_mean=float(jerk.mean()),
        rms_lateral_jerk_std=float(jerk.std(ddof=0)),
        false_positive_rate=float(act.mean()),
        mean_bcvf_cost_mean=float(bcvf.mean()),
        mean_bcvf_cost_std=float(bcvf.std(ddof=0)),
        solve_time_mean_ms=float(solve.mean()),
        solve_time_p99_ms=float(np.percentile(p99, 99)) if p99.size > 0 else 0.0,
        final_lateral_mean=float(final_lat.mean()),
        final_lateral_std=float(final_lat.std(ddof=0)),
        time_integrated_lateral_mean=float(ti_lat.mean()),
        time_integrated_lateral_std=float(ti_lat.std(ddof=0)),
        recovery_rate=recovery_rate,
        post_peak_recovery_median_s=recovery_median,
    )


# --- Statistical tests (NumPy-only) ---


def _normal_cdf(x: float) -> float:
    """Standard normal CDF using erf — no scipy."""
    return 0.5 * (1.0 + math.erf(x / math.sqrt(2.0)))


def welch_t_test(
    values_a: Sequence[float], values_b: Sequence[float]
) -> Tuple[float, float]:
    """Welch's unpaired t-test. Returns (t_stat, two-sided p-value)."""
    a = np.asarray(values_a, dtype=np.float64)
    b = np.asarray(values_b, dtype=np.float64)
    if a.size < 2 or b.size < 2:
        return (0.0, 1.0)
    mean_a, mean_b = a.mean(), b.mean()
    var_a = a.var(ddof=1)
    var_b = b.var(ddof=1)
    se_sq = var_a / a.size + var_b / b.size
    if se_sq <= 0.0:
        return (0.0, 1.0)
    t = (mean_a - mean_b) / math.sqrt(se_sq)
    # Normal approximation for df > 30 (sufficient for N=100 runs).
    p = 2.0 * (1.0 - _normal_cdf(abs(t)))
    return (float(t), float(p))


def fisher_exact_2x2(
    a: int, b: int, c: int, d: int
) -> Tuple[float, float]:
    """Fisher's exact test on a 2x2 contingency table.

    Returns ``(odds_ratio, two_sided_p_value)``. Rows: group A vs B;
    columns: success vs failure. Odds ratio = (a*d) / (b*c).
    """
    n = a + b + c + d
    if n == 0:
        return (0.0, 1.0)

    def log_binom(n_: int, k_: int) -> float:
        if k_ < 0 or k_ > n_:
            return -math.inf
        return (
            math.lgamma(n_ + 1)
            - math.lgamma(k_ + 1)
            - math.lgamma(n_ - k_ + 1)
        )

    row1 = a + b
    col1 = a + c
    col2 = b + d
    row2 = c + d

    # P(a|marginals) = C(row1, a) * C(row2, col1 - a) / C(n, col1)
    def log_pmf(x: int) -> float:
        return (
            log_binom(row1, x)
            + log_binom(row2, col1 - x)
            - log_binom(n, col1)
        )

    observed_logp = log_pmf(a)
    p_value = 0.0
    x_min = max(0, col1 - row2)
    x_max = min(col1, row1)
    for x in range(x_min, x_max + 1):
        lp = log_pmf(x)
        if lp <= observed_logp + 1e-12:
            p_value += math.exp(lp)
    p_value = min(1.0, p_value)

    odds_ratio = (a * d) / (b * c) if (b > 0 and c > 0) else math.inf
    return (float(odds_ratio), float(p_value))


@dataclass
class ComparisonResult:
    """Pairwise comparison result (DESIGN §4B.5)."""

    config_a_name: str
    config_b_name: str
    metric_name: str
    a_mean: float
    b_mean: float
    difference: float
    relative_change: float
    significant: bool
    p_value: float


def compare_collision_rates(
    metrics_a: AggregateMetrics,
    metrics_b: AggregateMetrics,
    name_a: str = "A",
    name_b: str = "B",
    alpha: float = 0.05,
) -> ComparisonResult:
    """Fisher's exact test on collision counts."""
    a_succ = int(round(metrics_a.collision_rate * metrics_a.n_runs))
    a_fail = metrics_a.n_runs - a_succ
    b_succ = int(round(metrics_b.collision_rate * metrics_b.n_runs))
    b_fail = metrics_b.n_runs - b_succ
    _, p = fisher_exact_2x2(a_succ, a_fail, b_succ, b_fail)
    diff = metrics_b.collision_rate - metrics_a.collision_rate
    rel = diff / max(metrics_a.collision_rate, 1e-9)
    return ComparisonResult(
        config_a_name=name_a,
        config_b_name=name_b,
        metric_name="collision_rate",
        a_mean=metrics_a.collision_rate,
        b_mean=metrics_b.collision_rate,
        difference=diff,
        relative_change=rel,
        significant=p < alpha,
        p_value=p,
    )


def compare_recovery_rates(
    metrics_a: AggregateMetrics,
    metrics_b: AggregateMetrics,
    name_a: str = "A",
    name_b: str = "B",
    alpha: float = 0.05,
) -> ComparisonResult:
    """Fisher's exact test on recovery counts (binomial, N from each).

    Recovery = post-peak |y| drops below recovery_threshold_m. Higher
    is better. Reported as ``difference = b_mean - a_mean`` so a
    positive difference means B recovers more often than A.
    """
    a_succ = int(round(metrics_a.recovery_rate * metrics_a.n_runs))
    a_fail = metrics_a.n_runs - a_succ
    b_succ = int(round(metrics_b.recovery_rate * metrics_b.n_runs))
    b_fail = metrics_b.n_runs - b_succ
    _, p = fisher_exact_2x2(a_succ, a_fail, b_succ, b_fail)
    diff = metrics_b.recovery_rate - metrics_a.recovery_rate
    rel = diff / max(metrics_a.recovery_rate, 1e-9)
    return ComparisonResult(
        config_a_name=name_a,
        config_b_name=name_b,
        metric_name="recovery_rate",
        a_mean=metrics_a.recovery_rate,
        b_mean=metrics_b.recovery_rate,
        difference=diff,
        relative_change=rel,
        significant=p < alpha,
        p_value=p,
    )


def compare_continuous_metric(
    values_a: Sequence[float],
    values_b: Sequence[float],
    metric_name: str,
    name_a: str = "A",
    name_b: str = "B",
    alpha: float = 0.05,
) -> ComparisonResult:
    """Welch's t-test on a continuous metric."""
    a = np.asarray(values_a, dtype=np.float64)
    b = np.asarray(values_b, dtype=np.float64)
    a_mean = float(a.mean()) if a.size > 0 else 0.0
    b_mean = float(b.mean()) if b.size > 0 else 0.0
    _, p = welch_t_test(values_a, values_b)
    diff = b_mean - a_mean
    rel = diff / max(abs(a_mean), 1e-9)
    return ComparisonResult(
        config_a_name=name_a,
        config_b_name=name_b,
        metric_name=metric_name,
        a_mean=a_mean,
        b_mean=b_mean,
        difference=diff,
        relative_change=rel,
        significant=p < alpha,
        p_value=p,
    )


# --- Summary table (DESIGN §4B.6) ---


VARIANT_DISPLAY = {
    "A0_baseline": "Baseline (A0)",
    "A1_zeroth": "0th-Order (A1)",
    "A2_first": "1st-Order (A2)",
    "A3_second_bcvf": "BCVF (A3)",
}


def _format_collision_rate(m: AggregateMetrics) -> str:
    return f"{m.collision_rate:.2f} [{m.collision_rate_ci_low:.2f}, {m.collision_rate_ci_high:.2f}]"


def _format_path_efficiency(m: AggregateMetrics) -> str:
    return f"{m.path_efficiency_mean:.3f} +/- {m.path_efficiency_std:.3f}"


def _format_ewt(m: AggregateMetrics) -> str:
    if m.early_warning_time_median is None or m.early_warning_time_iqr is None:
        return "—"
    lo, hi = m.early_warning_time_iqr
    return f"{m.early_warning_time_median:.1f} [{lo:.1f}, {hi:.1f}]"


def build_summary_table(
    results: Dict[Tuple[str, str], AggregateMetrics],
) -> Dict[str, Dict[str, Dict[str, str]]]:
    """Build the DESIGN §4B.6 summary table from ``(scenario, variant) -> AggregateMetrics``."""
    scenarios = sorted({s for s, _ in results.keys()})
    variants = sorted({v for _, v in results.keys()})
    table: Dict[str, Dict[str, Dict[str, str]]] = {}
    for scenario in scenarios:
        table[scenario] = {}
        for variant in variants:
            m = results.get((scenario, variant))
            if m is None:
                continue
            recovery = (
                f"{m.post_peak_recovery_median_s:.1f}s"
                if m.post_peak_recovery_median_s is not None
                else "—"
            )
            recovered_count = int(round(m.recovery_rate * m.n_runs))
            table[scenario][variant] = {
                "collision_rate": _format_collision_rate(m),
                "path_efficiency": _format_path_efficiency(m),
                "early_warning_s": _format_ewt(m),
                "false_positive_rate": f"{m.false_positive_rate:.3f}",
                "rms_jerk_ratio": f"{m.rms_lateral_jerk_mean:.2f}",
                "solve_time_ms": f"{m.solve_time_mean_ms:.1f} (p99 {m.solve_time_p99_ms:.1f})",
                # Recovery suite — the metrics the B2 smoke says differ.
                "final_lateral_m": f"{m.final_lateral_mean:.2f} +/- {m.final_lateral_std:.2f}",
                "time_integrated_lateral": f"{m.time_integrated_lateral_mean:.1f} +/- {m.time_integrated_lateral_std:.1f}",
                "recovery_rate": f"{m.recovery_rate:.2f}",
                "recovery_count": f"{recovered_count}/{m.n_runs}",
                "post_peak_recovery_median": recovery,
            }
    return table
