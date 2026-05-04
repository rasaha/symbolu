"""Scene-level evaluator for the §6.2 pilot (Mode A — open-loop).

Given a :class:`SceneRecord`, this module:

1. Runs **A0** — equal-weight consensus over the M predictors at
   every simulator step.
2. Runs **A3** — V1 trust-shaped consensus (EMA + deadband +
   softmin), optionally with V2 Schmitt trigger, over the same
   predictors.
3. Computes per-scene **forecast error** vs the ground-truth ego
   trace one horizon ahead.
4. Emits a :class:`TrustShapedEpisodeRecord` for A3 — directly
   consumable by the v0.4 fleet analysis harness.
5. Captures **attribution accuracy** for the failing predictor: did
   A3's per-predictor BCVF cost rank the injected outlier in the
   top half during the failure window?
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

import numpy as np

from ..core import BCVFConfig, CostOrder
from ..datasets.base import SceneRecord
from ..manifold import wrap_angle
from ..trust import ConsumerV2Config, TrustWeightComputer
from ..trust_diagnostics import (
    RolloutAggregation,
    TrustDiagnosticsRecorder,
    TrustShapedEpisodeRecord,
)


@dataclass
class SceneMetrics:
    """Per-configuration per-scene scalar metrics."""

    scene_id: str
    config_label: str        # "A0" or "A3"
    n_steps: int
    M: int

    # Forecast accuracy: mean Euclidean error between consensus and
    # the ground-truth ego pose one horizon ahead.
    mean_forecast_xy_error: float
    max_forecast_xy_error: float
    mean_forecast_heading_error: float

    # Trust-pipeline diagnostics — only populated for A3.
    mean_bcvf_total: float = 0.0
    max_bcvf_total: float = 0.0
    attribution_hit_rate: float = 0.0
    attribution_within_top_half: float = 0.0

    # The full per-step trust diagnostic record — only populated for
    # A3 (and only when ``record_diagnostics=True`` in the
    # evaluator config).
    episode_record: Optional[TrustShapedEpisodeRecord] = field(
        default=None, repr=False,
    )


@dataclass
class SceneEvaluatorConfig:
    """Knobs for the scene evaluator."""

    bcvf: BCVFConfig = field(default_factory=lambda: BCVFConfig(
        gate_threshold=0.05,
        gate_beta=400.0,
        huber_delta=0.5,
        lever_arm=2.5,
        weight_matrix=np.ones(3, dtype=np.float64),
        use_anchor_pairing=False,
        anchor_index=0,
        dt=0.1,
        cost_order=CostOrder.SECOND,
        lambda_c=1.0,
    ))
    ema_alpha: float = 0.05
    deadband_k_sigma: float = 2.0
    v2: Optional[ConsumerV2Config] = None
    record_diagnostics: bool = True
    forecast_horizon_lookahead: int = 1
    """How many simulator steps ahead the consensus is compared
    against ground truth. The default 1 evaluates the next-step
    prediction; set higher to evaluate longer-horizon forecasts."""


def _consensus_xy_theta(
    weights: np.ndarray,    # (M,)
    trajectories: np.ndarray,   # (M, H, 3)
) -> np.ndarray:
    """Trust-weighted consensus over M predictor trajectories.

    Returns ``(H, 3)``. Heading combination is atan2-safe.
    """
    w = weights.reshape(-1, 1, 1)
    xy = (w * trajectories[..., :2]).sum(axis=0)
    sin_w = (weights[:, None] * np.sin(trajectories[..., 2])).sum(axis=0)
    cos_w = (weights[:, None] * np.cos(trajectories[..., 2])).sum(axis=0)
    theta = np.arctan2(sin_w, cos_w)
    return np.concatenate([xy, theta[:, None]], axis=-1)


def _forecast_errors(
    consensus_per_step: np.ndarray,    # (T, H, 3)
    ego_trace: np.ndarray,             # (T, 3)
    lookahead: int,
) -> Dict[str, float]:
    """Per-step forecast error vs ground truth ``lookahead`` steps ahead.

    The consensus at time t says "I think the ego is at
    consensus[t, h, :] at simulator step t + h + 1". The error metric
    compares ``consensus[t, lookahead - 1, :]`` to ``ego[t + lookahead, :]``
    over all valid t.
    """
    T, H, _ = consensus_per_step.shape
    h_idx = max(0, min(lookahead - 1, H - 1))
    valid_t = T - lookahead
    if valid_t <= 0:
        return {"mean_xy": 0.0, "max_xy": 0.0, "mean_heading": 0.0}
    pred_xy = consensus_per_step[:valid_t, h_idx, :2]
    truth_xy = ego_trace[lookahead:lookahead + valid_t, :2]
    pred_th = consensus_per_step[:valid_t, h_idx, 2]
    truth_th = ego_trace[lookahead:lookahead + valid_t, 2]
    xy_err = np.linalg.norm(pred_xy - truth_xy, axis=-1)
    head_diff = pred_th - truth_th
    head_err = np.abs(np.arctan2(np.sin(head_diff), np.cos(head_diff)))
    return {
        "mean_xy": float(xy_err.mean()),
        "max_xy": float(xy_err.max()),
        "mean_heading": float(head_err.mean()),
    }


def _attribution_metrics(
    per_step_costs: np.ndarray,   # (T, M) per-step per-predictor BCVF
    failing_predictor_idx: Optional[int],
    onset_step: Optional[int],
    duration_steps: int,
    M: int,
) -> Dict[str, float]:
    """Attribution accuracy on the injected-failing predictor."""
    if failing_predictor_idx is None or onset_step is None:
        return {"hit_rate": 0.0, "within_top_half": 0.0}
    end_step = min(per_step_costs.shape[0], onset_step + duration_steps)
    if end_step <= onset_step:
        return {"hit_rate": 0.0, "within_top_half": 0.0}
    window = per_step_costs[onset_step:end_step]   # (W, M)
    if window.shape[0] == 0:
        return {"hit_rate": 0.0, "within_top_half": 0.0}
    # Rank descending (highest cost = rank 1).
    ranks_desc = np.argsort(-window, axis=1, kind="stable")
    # rank position of failing predictor
    pos = np.argmax(ranks_desc == failing_predictor_idx, axis=1) + 1   # 1..M
    hit = float(np.mean(pos == 1))
    # Top half uses the ceil convention ((M + 1) // 2) so it matches
    # the shootout's _attribution_top_half: M=3 → top 2, M=4 → top 2,
    # M=5 → top 3. The previous floor convention (M // 2) collapsed
    # to rank-1-only for odd M, making the field a duplicate of
    # ``hit_rate`` rather than the documented top-half measure.
    top_k = max(1, (M + 1) // 2)
    top_half = float(np.mean(pos <= top_k))
    return {"hit_rate": hit, "within_top_half": top_half}


def evaluate_scene_a0(
    scene: SceneRecord,
    config: Optional[SceneEvaluatorConfig] = None,
) -> SceneMetrics:
    """A0 — equal-weight (uniform) consensus over M predictors."""
    cfg = config or SceneEvaluatorConfig()
    pred_names = sorted(scene.predictor_trajectories.keys())
    M = len(pred_names)
    T = scene.num_steps
    H = scene.horizon
    uniform = np.full(M, 1.0 / M, dtype=np.float64)

    consensus = np.zeros((T, H, 3), dtype=np.float64)
    for t in range(T):
        trajs = np.stack(
            [scene.predictor_trajectories[name][t] for name in pred_names],
            axis=0,
        )
        consensus[t] = _consensus_xy_theta(uniform, trajs)

    err = _forecast_errors(consensus, scene.ego_trace, cfg.forecast_horizon_lookahead)
    return SceneMetrics(
        scene_id=scene.scene_id,
        config_label="A0",
        n_steps=T,
        M=M,
        mean_forecast_xy_error=err["mean_xy"],
        max_forecast_xy_error=err["max_xy"],
        mean_forecast_heading_error=err["mean_heading"],
    )


def evaluate_scene_a3(
    scene: SceneRecord,
    config: Optional[SceneEvaluatorConfig] = None,
) -> SceneMetrics:
    """A3 — V1 trust-shaped consensus (with optional V2)."""
    cfg = config or SceneEvaluatorConfig()
    pred_names = sorted(scene.predictor_trajectories.keys())
    M = len(pred_names)
    T = scene.num_steps
    H = scene.horizon

    bcvf_cfg = BCVFConfig(
        gate_threshold=cfg.bcvf.gate_threshold,
        gate_beta=cfg.bcvf.gate_beta,
        huber_delta=cfg.bcvf.huber_delta,
        lever_arm=cfg.bcvf.lever_arm,
        weight_matrix=np.asarray(cfg.bcvf.weight_matrix, dtype=np.float64),
        use_anchor_pairing=cfg.bcvf.use_anchor_pairing,
        anchor_index=cfg.bcvf.anchor_index,
        dt=scene.dt,
        cost_order=cfg.bcvf.cost_order,
        lambda_c=cfg.bcvf.lambda_c,
    )
    computer = TrustWeightComputer(bcvf_cfg)
    if cfg.ema_alpha > 0.0:
        computer.set_ema_alpha(cfg.ema_alpha)
    if cfg.deadband_k_sigma > 0.0:
        computer.set_deadband_k_sigma(cfg.deadband_k_sigma)
    if cfg.v2 is not None:
        computer.set_v2_consumer(cfg.v2)

    recorder: Optional[TrustDiagnosticsRecorder] = None
    if cfg.record_diagnostics:
        recorder = TrustDiagnosticsRecorder(
            M=M, aggregation=RolloutAggregation.MEAN,
        )

    consensus = np.zeros((T, H, 3), dtype=np.float64)
    per_step_costs = np.zeros((T, M), dtype=np.float64)
    bcvf_totals = np.zeros(T, dtype=np.float64)

    for t in range(T):
        trajs_M = np.stack(
            [scene.predictor_trajectories[name][t] for name in pred_names],
            axis=0,
        )                                       # (M, H, 3)
        trajs_KMH3 = trajs_M[np.newaxis, ...]   # (K=1, M, H, 3)
        result = computer.compute(trajs_KMH3)
        weights = result.weights[0]             # (M,)
        consensus[t] = _consensus_xy_theta(weights, trajs_M)
        per_step_costs[t] = result.per_pred_cost[0]
        bcvf_totals[t] = float(result.bcvf_total[0])
        if recorder is not None:
            recorder.record(result)

    err = _forecast_errors(consensus, scene.ego_trace, cfg.forecast_horizon_lookahead)
    failing_name = scene.failure_metadata.get("ground_truth_failing_predictor")
    failing_idx = (
        pred_names.index(failing_name) if failing_name in pred_names else None
    )
    onset = scene.failure_metadata.get("onset_step")
    duration = int(scene.failure_metadata.get("duration_steps") or 0)
    attr = _attribution_metrics(
        per_step_costs,
        failing_predictor_idx=failing_idx,
        onset_step=onset,
        duration_steps=duration,
        M=M,
    )

    episode_record = recorder.finalize() if recorder is not None else None

    return SceneMetrics(
        scene_id=scene.scene_id,
        config_label="A3",
        n_steps=T,
        M=M,
        mean_forecast_xy_error=err["mean_xy"],
        max_forecast_xy_error=err["max_xy"],
        mean_forecast_heading_error=err["mean_heading"],
        mean_bcvf_total=float(bcvf_totals.mean()),
        max_bcvf_total=float(bcvf_totals.max()),
        attribution_hit_rate=attr["hit_rate"],
        attribution_within_top_half=attr["within_top_half"],
        episode_record=episode_record,
    )
