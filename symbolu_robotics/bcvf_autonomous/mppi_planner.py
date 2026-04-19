"""Phase 3B — MPPI planner with J_perf + lambda_c * J_BCVF (DESIGN.md §3B).

Implements V3.1 Definition 7: sample K control sequences, forward-simulate
all predictors for each, score with performance + BCVF coherence, then
importance-weighted average.

Keeps no Python loop over K at the numerics layer: control sampling,
performance cost, BCVF cost, weights, and the weighted-mean control are
all vectorized. The one `for k in range(K)` loop sits at the predictor
rollout (Option A from DESIGN §3B.7); Option B (batch bicycle) stays on
the escalation path if the timing budget isn't met.
"""

from __future__ import annotations

import math
import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

import numpy as np

from .core import BCVFConfig, CostOrder, compute_bcvf_cost_batch
from .predictors.base import BasePredictor
from .simulator import Obstacle, Road


@dataclass
class MPPIConfig:
    """MPPI planner configuration (DESIGN.md §3B.4)."""

    num_rollouts: int = 1000
    horizon: int = 50
    dt: float = 0.1
    temperature: float = 5.0
    control_dim: int = 2
    noise_std: np.ndarray = field(
        default_factory=lambda: np.array([1.0, 0.15], dtype=np.float64)
    )
    velocity_bounds: Tuple[float, float] = (-2.0, 15.0)
    steering_bounds: Tuple[float, float] = (-0.6, 0.6)
    warm_start: bool = True
    lambda_c: float = 1.0
    bcvf_config: BCVFConfig = field(default_factory=BCVFConfig)
    anchor: str = "M1"


@dataclass
class PerfCostConfig:
    """Performance cost J_perf configuration (DESIGN.md §3B.5)."""

    lane_deviation_weight: float = 1.0
    progress_weight: float = 0.5
    control_smoothness_weight: float = 0.1
    collision_weight: float = 1000.0
    collision_margin: float = 3.0
    # Gate-2 cost-balance experiment: when set, the per-step squared lane
    # deviation is clamped to this value before being summed. Prevents
    # J_perf from saturating at 1e4+ under a failing-anchor rollout,
    # which collapses MPPI's softmax onto a single winner and strips
    # J_BCVF of leverage. ``None`` = no cap (legacy behavior).
    lane_deviation_cap: Optional[float] = None


@dataclass
class MPPIResult:
    """Diagnostics from one MPPI planning cycle."""

    optimal_control: np.ndarray
    first_control: np.ndarray
    total_cost: float
    perf_cost: float
    bcvf_cost: float
    solve_time_ms: float
    effective_samples: float


# --- J_perf ---


def _project_point_to_polyline(points: np.ndarray, pts: np.ndarray) -> np.ndarray:
    """For each row of ``points`` (N, 2), return the min Euclidean distance
    to any segment of the ``pts`` (M, 2) polyline. Vectorized over N.
    """
    # Segment endpoints.
    a = pts[:-1]  # (M-1, 2)
    b = pts[1:]
    seg = b - a                                   # (M-1, 2)
    seg_len2 = np.sum(seg * seg, axis=-1)         # (M-1,)
    seg_len2 = np.where(seg_len2 > 1e-12, seg_len2, 1.0)

    # (N, M-1, 2)
    diff = points[:, None, :] - a[None, :, :]
    t = np.einsum("nmd,md->nm", diff, seg) / seg_len2[None, :]
    t = np.clip(t, 0.0, 1.0)
    proj = a[None, :, :] + t[..., None] * seg[None, :, :]
    d = np.linalg.norm(points[:, None, :] - proj, axis=-1)  # (N, M-1)
    return d.min(axis=-1)


def _project_arclength(points: np.ndarray, pts: np.ndarray) -> np.ndarray:
    """Return arc-length along the road for each input point (N,)."""
    # Cumulative arc-length at each waypoint.
    seg = pts[1:] - pts[:-1]
    seg_len = np.linalg.norm(seg, axis=-1)
    cum = np.concatenate([[0.0], np.cumsum(seg_len)])  # (M,)
    a = pts[:-1]
    diff = points[:, None, :] - a[None, :, :]
    seg_len2 = np.sum(seg * seg, axis=-1)
    seg_len2 = np.where(seg_len2 > 1e-12, seg_len2, 1.0)
    t = np.clip(np.einsum("nmd,md->nm", diff, seg) / seg_len2[None, :], 0.0, 1.0)
    proj = a[None, :, :] + t[..., None] * seg[None, :, :]
    d = np.linalg.norm(points[:, None, :] - proj, axis=-1)
    idx = d.argmin(axis=-1)  # (N,)
    rows = np.arange(points.shape[0])
    arc = cum[idx] + t[rows, idx] * seg_len[idx]
    return arc


def compute_perf_cost(
    trajectory: np.ndarray,
    control_sequence: np.ndarray,
    road: Road,
    obstacles: List[Obstacle],
    config: PerfCostConfig,
) -> float:
    """DESIGN.md §3B.5 performance cost for a single trajectory."""
    pts = road.centerline
    xy = trajectory[:, :2]

    # 1. Lane deviation.
    lane_d = _project_point_to_polyline(xy, pts)
    lane_d_sq = lane_d * lane_d
    if config.lane_deviation_cap is not None:
        lane_d_sq = np.minimum(lane_d_sq, config.lane_deviation_cap)
    lane_cost = float(np.sum(lane_d_sq)) * config.lane_deviation_weight

    # 2. Progress — reward the arc-length traveled from start of horizon to end.
    arc = _project_arclength(xy[[0, -1]], pts)
    progress = float(arc[1] - arc[0])
    progress_cost = -config.progress_weight * progress

    # 3. Control smoothness (first-difference ‖Δu‖² per step).
    ctrl = np.asarray(control_sequence, dtype=np.float64)
    du = np.diff(ctrl, axis=0)
    smooth_cost = config.control_smoothness_weight * float(np.sum(du * du))

    # 4. Collision proximity (smooth).
    collision_cost = 0.0
    if obstacles:
        margin = max(config.collision_margin, 1e-6)
        for obs in obstacles:
            d = np.linalg.norm(xy - np.array([obs.x, obs.y]), axis=-1) - obs.radius
            active = d < margin
            if np.any(active):
                scale = np.clip(1.0 - d[active] / margin, 0.0, 1.0)
                collision_cost += config.collision_weight * float(np.sum(scale * scale))

    return lane_cost + progress_cost + smooth_cost + collision_cost


def _compute_perf_cost_batch(
    trajectories_batch: np.ndarray,   # (K, H, 3)
    controls_batch: np.ndarray,       # (K, H, 2)
    road: Road,
    obstacles: List[Obstacle],
    config: PerfCostConfig,
) -> np.ndarray:
    """Vectorized J_perf over K candidates."""
    k_batch = trajectories_batch.shape[0]
    costs = np.zeros(k_batch, dtype=np.float64)
    for k in range(k_batch):
        costs[k] = compute_perf_cost(
            trajectories_batch[k], controls_batch[k], road, obstacles, config
        )
    return costs


# --- Planner ---


class MPPIPlanner:
    """Model Predictive Path Integral planner with BCVF coherence cost."""

    def __init__(
        self,
        mppi_config: MPPIConfig,
        perf_config: PerfCostConfig,
        predictors: Dict[str, BasePredictor],
        road: Road,
        obstacles: List[Obstacle],
    ) -> None:
        self.config = mppi_config
        self.perf_config = perf_config
        self.predictors = predictors
        self.road = road
        self.obstacles = list(obstacles)
        if mppi_config.anchor not in predictors:
            raise ValueError(
                f"anchor {mppi_config.anchor!r} not found in predictors {list(predictors)}"
            )
        self._rng = np.random.default_rng(0)
        self._prev_solution: Optional[np.ndarray] = None
        # Softmin temperature for the Ketu→Rahu trust weighting. Per-
        # predictor BCVF costs in the prior smokes ranged ~0–10 per
        # rollout; τ_w=1 gives exp(10/1) ≈ 22000 weight ratio between
        # the healthiest and most-distrusted predictor — sharp enough
        # to push a clear outlier toward zero weight without completely
        # pinning when disagreement is mild. Exposed as a knob (set_*)
        # for tuning.
        self._trust_temperature: float = 1.0
        # Level-2 adaptive normalization (per-predictor EMA mean on
        # per_pred_cost, subtracted before softmin). α=0 disables —
        # softmin operates on raw per_pred_cost (prior behavior). α>0
        # maintains a running mean across outer steps and softmins on
        # the residual, removing the seed-dependent constant floor
        # identified in the N=26 diagnostic (option 3).
        self._ema_alpha: float = 0.0
        self._ema_mean: Optional[np.ndarray] = None  # (M,) once initialized
        # Solution-3 deadband gate: also track EMA residual variance per
        # predictor. If max_m(|residual[k,m]|/EMA_std[m]) <
        # _deadband_k_sigma for a rollout, fall back to uniform weights
        # for that rollout (noise regime). Addresses the N=26 Level-2
        # observation that seeds 76/81/96 were previously-healthy but
        # went catastrophic under EMA because small noise residuals
        # were shaping softmin weights. 0 disables.
        self._deadband_k_sigma: float = 0.0
        self._ema_var: Optional[np.ndarray] = None  # (M,) EMA of residual^2
        # Optional per-step trust-state log (deep-dive diagnostic). When
        # enabled via set_trust_log_enabled(True), each plan() call
        # appends a compact summary dict to self._trust_log. Disabled
        # by default to avoid memory bloat in production runs.
        self._trust_log_enabled: bool = False
        self._trust_log: List[Dict[str, Any]] = []
        self._trust_log_step: int = 0

    # --- public API ---

    def reset(self) -> None:
        self._prev_solution = None
        self._ema_mean = None
        self._ema_var = None
        self._trust_log_step = 0
        if self._trust_log_enabled:
            self._trust_log = []

    def plan(self) -> MPPIResult:
        start = time.perf_counter()
        controls_batch = self._sample_controls()   # (K, H, 2)
        perf_costs, bcvf_costs = self._rollout_all(controls_batch)
        # Ketu→Rahu composition: BCVF is an observer that shapes the
        # attractor (via trust weights in _rollout_all); it does NOT
        # contribute to J_total. The softmax ranks rollouts purely on
        # J_perf evaluated against the trust-weighted consensus.
        # bcvf_costs is carried forward as a diagnostic for downstream
        # reporting (SimState.bcvf_cost, tests that verify observer
        # activity, alignment analyses).
        total_costs = perf_costs
        weights = self._compute_weights(total_costs)
        optimal = self._weighted_mean(controls_batch, weights)
        solve_ms = (time.perf_counter() - start) * 1000.0
        effective = float(1.0 / max(float(np.sum(weights * weights)), 1e-12))

        if self.config.warm_start:
            self._prev_solution = optimal

        # Mean costs weighted across K — report the weighted expectation.
        perf_w = float(np.sum(weights * perf_costs))
        bcvf_w = float(np.sum(weights * bcvf_costs))
        return MPPIResult(
            optimal_control=optimal,
            first_control=optimal[0].copy(),
            total_cost=perf_w,  # J_total = J_perf only (no additive BCVF)
            perf_cost=perf_w,
            bcvf_cost=bcvf_w,   # diagnostic: observer activity, not in J_total
            solve_time_ms=solve_ms,
            effective_samples=effective,
        )

    # --- internals ---

    def _warm_start_mean(self) -> np.ndarray:
        c = self.config
        if not c.warm_start or self._prev_solution is None:
            return np.zeros((c.horizon, c.control_dim), dtype=np.float64)
        shifted = np.roll(self._prev_solution, -1, axis=0)
        shifted[-1] = shifted[-2]
        return shifted

    def _sample_controls(self) -> np.ndarray:
        c = self.config
        mean = self._warm_start_mean()  # (H, 2)
        noise = self._rng.normal(
            loc=0.0,
            scale=c.noise_std,
            size=(c.num_rollouts, c.horizon, c.control_dim),
        )
        controls = mean[None, :, :] + noise
        controls[..., 0] = np.clip(
            controls[..., 0], c.velocity_bounds[0], c.velocity_bounds[1]
        )
        controls[..., 1] = np.clip(
            controls[..., 1], c.steering_bounds[0], c.steering_bounds[1]
        )
        return controls

    def _rollout_all(
        self, controls_batch: np.ndarray
    ) -> Tuple[np.ndarray, np.ndarray]:
        """Ketu→Rahu composition: BCVF acts as a silent observer that
        shapes the attractor via per-predictor trust weights, rather
        than as an additive cost term in the softmax.

        1. Roll out every predictor for every candidate.
        2. If ``lambda_c > 0`` (BCVF active), extract per-predictor
           disagreement cost and convert to softmin trust weights;
           the consensus trajectory becomes a trust-weighted mean of
           the predictor rollouts. If ``lambda_c == 0`` (A0 baseline),
           use equal-weight consensus — BCVF is absent as an observer
           so every predictor is trusted equally.
        3. Evaluate J_perf on the (trust-weighted or equal-weight)
           consensus. No additive J_BCVF term in J_total.
        4. Report J_BCVF as a diagnostic only — it no longer appears
           in the softmax and does not affect control selection.

        This structurally prevents the two failure modes the N=34
        data exposed:
          - same-direction amplification (BCVF rewarding rollouts that
            align with the failing predictor's hallucinated future)
          - sign-flip collusion (BCVF picking the wrong side of
            centerline when J_perf is indecisive)
        Because BCVF no longer votes on which rollout wins, it cannot
        reward alignment with the failing predictor — it can only shift
        which predictor the attractor trusts.
        """
        c = self.config
        k_batch = controls_batch.shape[0]
        model_ids = list(self.predictors.keys())
        num_models = len(model_ids)
        anchor_idx = model_ids.index(c.anchor)

        # Always roll out every predictor.
        all_trajs = np.zeros((k_batch, num_models, c.horizon, 3), dtype=np.float64)
        for k in range(k_batch):
            for m_idx, name in enumerate(model_ids):
                all_trajs[k, m_idx] = self.predictors[name].predict(controls_batch[k])

        # Compute per-predictor trust weights.
        if c.lambda_c > 0.0:
            # BCVF observes; trust weights softmin over per-predictor
            # disagreement cost. Lemma 1 is preserved: under constant
            # or linear-in-time disagreement the SECOND-order BCVF cost
            # per predictor is ~0, so weights stay uniform and consensus
            # equals the equal-weight mean — same as A0 baseline.
            bcvf_cfg = BCVFConfig(
                lambda_c=c.bcvf_config.lambda_c,
                gate_threshold=c.bcvf_config.gate_threshold,
                gate_beta=c.bcvf_config.gate_beta,
                huber_delta=c.bcvf_config.huber_delta,
                lever_arm=c.bcvf_config.lever_arm,
                weight_matrix=np.asarray(c.bcvf_config.weight_matrix, dtype=np.float64),
                use_anchor_pairing=c.bcvf_config.use_anchor_pairing,
                anchor_index=anchor_idx,
                dt=c.bcvf_config.dt,
                cost_order=c.bcvf_config.cost_order,
            )
            trajectories_list = [
                [all_trajs[k, m] for m in range(num_models)] for k in range(k_batch)
            ]
            bcvf_total, per_pred_cost = compute_bcvf_cost_batch(
                trajectories_list, bcvf_cfg, return_per_predictor=True
            )
            # Level-2 adaptive normalization: subtract per-predictor EMA
            # mean (computed across outer steps) to remove the seed-
            # dependent constant floor. On the first step _ema_mean is
            # None → initialize from current step's mean across K, which
            # makes the residual identically zero at step 0 and yields
            # uniform weights (safe cold start). On subsequent steps,
            # residual = per_pred_cost - EMA_mean, and softmin operates
            # on residual instead of raw cost.
            if self._ema_alpha > 0.0:
                step_mean = per_pred_cost.mean(axis=0)  # (M,)
                if self._ema_mean is None:
                    self._ema_mean = step_mean.copy()
                    if self._deadband_k_sigma > 0.0:
                        # Initialize variance from within-K dispersion
                        # so the first meaningful residuals have a
                        # non-degenerate std reference. Residual^2 of
                        # the first step's (cost - step_mean) equals
                        # the rollout-wise variance at step 0.
                        self._ema_var = per_pred_cost.var(axis=0).copy()
                pred_signal = per_pred_cost - self._ema_mean[np.newaxis, :]
                # Update EMA *after* using current signal, so the first
                # step operates on its own mean (zero residual) and
                # subsequent steps use the stale-by-one estimate.
                a = self._ema_alpha
                if self._deadband_k_sigma > 0.0:
                    resid_sq = (pred_signal ** 2).mean(axis=0)   # (M,)
                    self._ema_var = a * resid_sq + (1.0 - a) * self._ema_var
                self._ema_mean = a * step_mean + (1.0 - a) * self._ema_mean
            else:
                pred_signal = per_pred_cost

            # Softmin weights: softmin(c) = softmax(-c). Scale by a
            # per-rollout min-shift so numerical exponents stay bounded
            # regardless of absolute cost magnitudes.
            tau_w = max(self._trust_temperature, 1e-9)
            shifted = pred_signal - pred_signal.min(axis=1, keepdims=True)
            arg = np.clip(-shifted / tau_w, -50.0, 50.0)
            raw = np.exp(arg)                                 # (K, M)
            weights = raw / raw.sum(axis=1, keepdims=True)    # (K, M)

            # Solution-3 deadband: for each rollout, check if the
            # largest |residual|/std exceeds k_sigma. If not, we're in
            # the noise regime — fall back to uniform weights for that
            # rollout. Residual = pred_signal when ema_alpha > 0 (zero-
            # centered); if ema disabled this block also disables.
            deadband_active_count = 0
            if (self._deadband_k_sigma > 0.0
                    and self._ema_alpha > 0.0
                    and self._ema_var is not None):
                eps = 1e-9
                ema_std = np.sqrt(self._ema_var) + eps        # (M,)
                z = np.abs(pred_signal) / ema_std[np.newaxis, :]  # (K, M)
                max_abs_z_per_rollout = z.max(axis=1)              # (K,)
                insignificant = max_abs_z_per_rollout < self._deadband_k_sigma
                deadband_active_count = int(np.sum(insignificant))
                if np.any(insignificant):
                    uniform = np.full(
                        (num_models,), 1.0 / num_models, dtype=np.float64
                    )
                    weights[insignificant] = uniform

            # Optional deep-dive trust-state log. Records per-step
            # summaries (per-predictor stats, not full K×M matrices) so
            # post-hoc analysis can attribute trajectory failures to
            # specific BCVF/EMA/deadband behavior.
            if self._trust_log_enabled:
                ema_mean_view = (
                    self._ema_mean.tolist() if self._ema_mean is not None else None
                )
                ema_std_view = (
                    np.sqrt(self._ema_var).tolist()
                    if self._ema_var is not None else None
                )
                argmax_pred = np.argmax(weights, axis=1)  # (K,)
                argmax_hist = np.bincount(
                    argmax_pred, minlength=num_models
                ).tolist()
                self._trust_log.append({
                    "step": self._trust_log_step,
                    "per_pred_cost": {
                        "mean": per_pred_cost.mean(axis=0).tolist(),
                        "std": per_pred_cost.std(axis=0).tolist(),
                        "min": per_pred_cost.min(axis=0).tolist(),
                        "max": per_pred_cost.max(axis=0).tolist(),
                        "median": np.median(per_pred_cost, axis=0).tolist(),
                    },
                    "weights": {
                        "mean": weights.mean(axis=0).tolist(),
                        "max": weights.max(axis=0).tolist(),
                        "argmax_hist": argmax_hist,
                    },
                    "ema_mean": ema_mean_view,
                    "ema_std": ema_std_view,
                    "deadband": {
                        "active_count": deadband_active_count,
                        "k_sigma": self._deadband_k_sigma,
                    },
                    "bcvf_total_summary": {
                        "mean": float(bcvf_total.mean()),
                        "max": float(bcvf_total.max()),
                    },
                })
                self._trust_log_step += 1
        else:
            # A0 baseline: equal weights (no observer).
            bcvf_total = np.zeros(k_batch, dtype=np.float64)
            weights = np.full(
                (k_batch, num_models), 1.0 / num_models, dtype=np.float64
            )

        # Weighted consensus — atan2-safe on heading.
        w_expand = weights[..., None, None]  # (K, M, 1, 1)
        xy_w = np.sum(all_trajs[..., :2] * w_expand, axis=1)                    # (K, H, 2)
        sin_w = np.sum(np.sin(all_trajs[..., 2]) * weights[..., None], axis=1)  # (K, H)
        cos_w = np.sum(np.cos(all_trajs[..., 2]) * weights[..., None], axis=1)
        theta_w = np.arctan2(sin_w, cos_w)
        consensus_trajs = np.concatenate(
            [xy_w, theta_w[..., None]], axis=-1
        )                                                                       # (K, H, 3)

        perf_costs = _compute_perf_cost_batch(
            consensus_trajs, controls_batch, self.road, self.obstacles, self.perf_config
        )

        # BCVF is reported as a diagnostic so downstream (SimState,
        # tests, reports) can still see observer activity, but its
        # contribution to J_total is zero — the Ketu role is to shape
        # the attractor (via weights above), not to score. The planner's
        # _compute_weights call multiplies this by λ_c=0 effectively
        # because we return it as a pure diagnostic channel.
        return perf_costs, bcvf_total

    def _compute_weights(self, total_costs: np.ndarray) -> np.ndarray:
        shifted = total_costs - float(total_costs.min())
        w = np.exp(-shifted / max(self.config.temperature, 1e-9))
        total = float(np.sum(w))
        if total <= 0.0 or not math.isfinite(total):
            # Fallback: uniform weights (shouldn't happen with finite costs).
            return np.full_like(total_costs, 1.0 / total_costs.size)
        return w / total

    def _weighted_mean(
        self, controls_batch: np.ndarray, weights: np.ndarray
    ) -> np.ndarray:
        return np.einsum("k,khd->hd", weights, controls_batch)

    # --- helpers for ablation-aware config ---

    def set_seed(self, seed: int) -> None:
        """Re-seed the internal sampling RNG (for deterministic tests)."""
        self._rng = np.random.default_rng(seed)

    def set_ema_alpha(self, alpha: float) -> None:
        """Set EMA rate for Level-2 adaptive trust-weight normalization.

        alpha=0 disables (softmin operates on raw per_pred_cost).
        alpha>0 subtracts a running per-predictor mean before softmin.
        Typical values: 0.02-0.1, giving effective τ ~ 10-50 outer steps
        (1-5 s at dt=0.1).
        """
        if alpha < 0.0 or alpha > 1.0:
            raise ValueError(f"ema_alpha must be in [0, 1]; got {alpha}")
        self._ema_alpha = alpha
        self._ema_mean = None
        self._ema_var = None

    def set_deadband_k_sigma(self, k_sigma: float) -> None:
        """Set deadband threshold in units of EMA residual std.

        k_sigma=0 disables (softmin applied to all rollouts). k_sigma>0
        requires ema_alpha>0 to have effect; for each rollout, the
        per-predictor residual z-score must exceed k_sigma before
        softmin-based weight shaping is applied — otherwise uniform
        weights. Typical values 1.5-3.0 (1σ to 3σ significance).
        """
        if k_sigma < 0.0:
            raise ValueError(f"deadband k_sigma must be >= 0; got {k_sigma}")
        self._deadband_k_sigma = k_sigma

    def set_trust_log_enabled(self, enabled: bool) -> None:
        """Enable/disable per-step trust-state logging (deep-dive)."""
        self._trust_log_enabled = bool(enabled)
        if enabled:
            self._trust_log = []
            self._trust_log_step = 0

    def get_trust_log(self) -> List[Dict[str, Any]]:
        """Return the accumulated trust-state log (one dict per step)."""
        return list(self._trust_log)
