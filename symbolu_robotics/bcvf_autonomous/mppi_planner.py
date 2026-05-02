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
from .trust import (
    ConsumerV2Config,
    TrustWeightComputer,
    TrustWeightResult,
)
from .trust_diagnostics import (
    RolloutAggregation,
    TrustDiagnosticsRecorder,
    TrustShapedEpisodeRecord,
)
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
        # §6.3: consumer-layer trust-weight computation is now a
        # separate module (trust.TrustWeightComputer) so non-MPPI
        # planners can reuse the validated V1 pattern. This planner
        # delegates all EMA / deadband / exclusion state to it and
        # keeps only the MPPI-specific bits (rollout generation,
        # weighted consensus, MPPI softmax action selection).
        self._trust_computer = TrustWeightComputer(mppi_config.bcvf_config)
        # Optional per-step trust-state log (deep-dive diagnostic). When
        # enabled via set_trust_log_enabled(True), each plan() call
        # appends a compact summary dict to self._trust_log. Disabled
        # by default to avoid memory bloat in production runs.
        self._trust_log_enabled: bool = False
        self._trust_log: List[Dict[str, Any]] = []
        self._trust_log_step: int = 0
        # Typed per-step trust diagnostics — autonomous analog of BCVF
        # LLM's TrustShapedDecodeResult. Built on top of
        # TrustDiagnosticsRecorder; off by default. Coexists with the
        # legacy dict-form trust log; the two record different shapes
        # (compact summary dict vs typed (T, M) arrays).
        self._diagnostics_enabled: bool = False
        self._diagnostics_recorder: Optional[TrustDiagnosticsRecorder] = None

    # --- public API ---

    def reset(self) -> None:
        self._prev_solution = None
        self._trust_computer.reset()
        self._trust_log_step = 0
        if self._trust_log_enabled:
            self._trust_log = []
        if self._diagnostics_recorder is not None:
            self._diagnostics_recorder.reset()

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

        # §6.3: delegate consumer-layer trust-weight computation to
        # the shared TrustWeightComputer. The computer handles EMA
        # centering, deadband gate, exclusion, softmin. It falls back
        # to uniform weights automatically when lambda_c == 0 (A0).
        # The effective lambda_c is MPPIConfig.lambda_c (the outer
        # gate — "is the planner using BCVF at all?"), not the
        # kernel's lambda_c; the MPPI planner sets the computer's
        # BCVFConfig.lambda_c = MPPIConfig.lambda_c so the trust
        # computer's internal short-circuit matches the original
        # planner-level gate. The anchor_index override for BCVF
        # anchor-pairing mode is handled here.
        self._trust_computer._bcvf_config = BCVFConfig(
            lambda_c=c.lambda_c,
            gate_threshold=c.bcvf_config.gate_threshold,
            gate_beta=c.bcvf_config.gate_beta,
            huber_delta=c.bcvf_config.huber_delta,
            lever_arm=c.bcvf_config.lever_arm,
            weight_matrix=np.asarray(
                c.bcvf_config.weight_matrix, dtype=np.float64
            ),
            use_anchor_pairing=c.bcvf_config.use_anchor_pairing,
            anchor_index=anchor_idx,
            dt=c.bcvf_config.dt,
            cost_order=c.bcvf_config.cost_order,
        )
        trust_result = self._trust_computer.compute(all_trajs)
        weights = trust_result.weights
        bcvf_total = trust_result.bcvf_total

        # Optional deep-dive trust-state log. Records per-step
        # summaries (per-predictor stats, not full K×M matrices) so
        # post-hoc analysis can attribute trajectory failures to
        # specific BCVF/EMA/deadband behavior.
        if self._trust_log_enabled and c.lambda_c > 0.0:
            per_pred_cost = trust_result.per_pred_cost
            ema_mean_view = (
                trust_result.ema_mean.tolist()
                if trust_result.ema_mean is not None else None
            )
            ema_std_view = (
                trust_result.ema_std.tolist()
                if trust_result.ema_std is not None else None
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
                    "active_count": trust_result.deadband_active_count,
                    "k_sigma": self._trust_computer._deadband_k_sigma,
                },
                "bcvf_total_summary": {
                    "mean": float(bcvf_total.mean()),
                    "max": float(bcvf_total.max()),
                },
            })
            self._trust_log_step += 1

        # Typed per-step trust diagnostics (TrustShapedEpisodeRecord).
        # Records every tick, not just BCVF-active ones — a tick where
        # ``lambda_c == 0`` still produces a uniform-weight record so
        # the (T, M) arrays line up with the simulator's tick index.
        if self._diagnostics_recorder is not None:
            self._diagnostics_recorder.record(trust_result)

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
        Delegates to the trust computer.
        """
        self._trust_computer.set_ema_alpha(alpha)

    def set_deadband_k_sigma(self, k_sigma: float) -> None:
        """Set deadband threshold. Delegates to the trust computer."""
        self._trust_computer.set_deadband_k_sigma(k_sigma)

    def set_exclusion(
        self,
        enabled: bool,
        r: float = 1.5,
        T_exclude: int = 20,
        T_reinstate: int = 20,
    ) -> None:
        """Configure §6.6a dynamic predictor exclusion. Delegates."""
        self._trust_computer.set_exclusion(
            enabled=enabled, r=r, T_exclude=T_exclude, T_reinstate=T_reinstate,
        )

    # --- Backward-compat property accessors for tests that inspect
    # --- internal trust state. Newer tests should use the
    # --- TrustWeightComputer directly via self._trust_computer.

    @property
    def _ema_alpha(self) -> float:
        return self._trust_computer._ema_alpha

    @property
    def _ema_mean(self):
        return self._trust_computer._ema_mean

    @_ema_mean.setter
    def _ema_mean(self, value):
        self._trust_computer._ema_mean = value

    @property
    def _ema_var(self):
        return self._trust_computer._ema_var

    @_ema_var.setter
    def _ema_var(self, value):
        self._trust_computer._ema_var = value

    @property
    def _deadband_k_sigma(self) -> float:
        return self._trust_computer._deadband_k_sigma

    @property
    def _exclusion_enabled(self) -> bool:
        return self._trust_computer._exclusion_enabled

    @property
    def _exclusion_r(self) -> float:
        return self._trust_computer._exclusion_r

    @property
    def _exclusion_T(self) -> int:
        return self._trust_computer._exclusion_T

    @property
    def _exclusion_T_reinstate(self) -> int:
        return self._trust_computer._exclusion_T_reinstate

    @property
    def _consec_suspect(self):
        return self._trust_computer._consec_suspect

    @_consec_suspect.setter
    def _consec_suspect(self, value):
        self._trust_computer._consec_suspect = value

    @property
    def _consec_ok(self):
        return self._trust_computer._consec_ok

    @_consec_ok.setter
    def _consec_ok(self, value):
        self._trust_computer._consec_ok = value

    @property
    def _is_excluded(self):
        return self._trust_computer._is_excluded

    @_is_excluded.setter
    def _is_excluded(self, value):
        self._trust_computer._is_excluded = value

    @property
    def _trust_temperature(self) -> float:
        return self._trust_computer._trust_temperature

    @_trust_temperature.setter
    def _trust_temperature(self, value: float):
        self._trust_computer.set_trust_temperature(value)

    def set_trust_log_enabled(self, enabled: bool) -> None:
        """Enable/disable per-step trust-state logging (deep-dive)."""
        self._trust_log_enabled = bool(enabled)
        if enabled:
            self._trust_log = []
            self._trust_log_step = 0

    def get_trust_log(self) -> List[Dict[str, Any]]:
        """Return the accumulated trust-state log (one dict per step)."""
        return list(self._trust_log)

    def set_trust_diagnostics_enabled(
        self,
        enabled: bool,
        aggregation: RolloutAggregation = RolloutAggregation.MEAN,
    ) -> None:
        """Enable typed per-step trust diagnostics.

        When enabled, every ``plan()`` call appends a ``TrustStepRecord``
        to an internal ``TrustDiagnosticsRecorder`` keyed by simulator
        tick. Call :meth:`get_trust_diagnostics` after the episode to
        retrieve the stacked ``TrustShapedEpisodeRecord``.

        Coexists with :meth:`set_trust_log_enabled`: the legacy log
        records compact summaries; the diagnostics recorder records
        typed ``(T, M)`` arrays.
        """
        self._diagnostics_enabled = bool(enabled)
        if enabled:
            num_models = len(self.predictors)
            self._diagnostics_recorder = TrustDiagnosticsRecorder(
                M=num_models, aggregation=aggregation
            )
        else:
            self._diagnostics_recorder = None

    def get_trust_diagnostics(self) -> Optional[TrustShapedEpisodeRecord]:
        """Finalize and return the typed per-step trust-diagnostics record."""
        if self._diagnostics_recorder is None:
            return None
        return self._diagnostics_recorder.finalize()

    def set_v2_consumer(self, config: ConsumerV2Config) -> None:
        """Install the §14a V2 Schmitt-triggered consumer.

        Forwards to :meth:`TrustWeightComputer.set_v2_consumer`. With
        ``config.enabled = False`` the planner's behavior is exactly
        V1 (default). With ``enabled = True`` the trust computer
        gates the entire shaping pipeline through the engage /
        disengage state machine.
        """
        self._trust_computer.set_v2_consumer(config)
