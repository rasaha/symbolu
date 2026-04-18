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
from typing import Dict, List, Optional, Tuple

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

    # --- public API ---

    def reset(self) -> None:
        self._prev_solution = None

    def plan(self) -> MPPIResult:
        start = time.perf_counter()
        controls_batch = self._sample_controls()   # (K, H, 2)
        perf_costs, bcvf_costs = self._rollout_all(controls_batch)
        total_costs = perf_costs + self.config.lambda_c * bcvf_costs
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
            total_cost=perf_w + self.config.lambda_c * bcvf_w,
            perf_cost=perf_w,
            bcvf_cost=bcvf_w,
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
        c = self.config
        k_batch = controls_batch.shape[0]
        anchor = self.predictors[c.anchor]
        model_ids = list(self.predictors.keys())
        num_models = len(model_ids)
        anchor_idx = model_ids.index(c.anchor)

        if c.lambda_c == 0.0:
            # Lambda_c = 0: only anchor rollouts needed for J_perf. Skip BCVF.
            anchor_trajs = np.zeros((k_batch, c.horizon, 3), dtype=np.float64)
            for k in range(k_batch):
                anchor_trajs[k] = anchor.predict(controls_batch[k])
            perf_costs = _compute_perf_cost_batch(
                anchor_trajs, controls_batch, self.road, self.obstacles, self.perf_config
            )
            bcvf_costs = np.zeros(k_batch, dtype=np.float64)
            return perf_costs, bcvf_costs

        # Full rollouts for every predictor.
        all_trajs = np.zeros((k_batch, num_models, c.horizon, 3), dtype=np.float64)
        for k in range(k_batch):
            for m_idx, name in enumerate(model_ids):
                all_trajs[k, m_idx] = self.predictors[name].predict(controls_batch[k])

        anchor_trajs = all_trajs[:, anchor_idx, :, :]
        perf_costs = _compute_perf_cost_batch(
            anchor_trajs, controls_batch, self.road, self.obstacles, self.perf_config
        )

        # Sync anchor_index for the BCVF config (relevant only when
        # anchor pairing is enabled). Respect the caller's
        # use_anchor_pairing flag so the planner can run all-pairs BCVF
        # when requested — that detaches BCVF from a single poisoned
        # reference frame on scenarios where the anchor itself is the
        # failing predictor.
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
        bcvf_costs = compute_bcvf_cost_batch(trajectories_list, bcvf_cfg)
        return perf_costs, bcvf_costs

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
