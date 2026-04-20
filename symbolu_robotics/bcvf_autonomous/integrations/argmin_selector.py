"""Minimal non-MPPI planner adapter for ``TrustWeightComputer`` (§6.3).

Reference implementation that demonstrates the trust computer is
genuinely planner-agnostic. Unlike MPPI — which applies a softmax
over candidate rollout costs — this adapter picks the single
argmin-cost rollout (greedy selection) and returns its first control.

The point of this file is **not** to be a production planner. It is
to prove that:

1. The trust computer has no MPPI-specific dependencies.
2. A different action-selection rule (argmin vs softmax weighted mean)
   can be built on top of the same trust pipeline without touching
   ``trust.py`` or ``mppi_planner.py``.
3. The Lemma 1 invariance and V1 consumer pattern transfer cleanly
   to a non-MPPI consumer.

For a production non-MPPI adapter (MPC, RRT*, hybrid A*), follow the
same skeleton but replace ``_sample_controls`` with the planner's own
candidate-generation logic.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Optional

import numpy as np

from ..core import BCVFConfig
from ..mppi_planner import MPPIConfig, PerfCostConfig, _compute_perf_cost_batch
from ..predictors.base import BasePredictor
from ..simulator import Obstacle, Road
from ..trust import TrustWeightComputer


@dataclass
class ArgminSelectorResult:
    """Output of a single argmin-selector planning step."""

    first_control: np.ndarray      # (2,) applied control
    selected_rollout_idx: int      # which K-index won
    perf_cost: float               # perf cost of the winning rollout
    bcvf_cost: float               # diagnostic — bcvf_total of winner


class ArgminSelectorPlanner:
    """Greedy rollout-selection planner built on TrustWeightComputer.

    Produces K candidate control sequences (same sampling as MPPI),
    rolls each out under all M predictors, asks the TrustWeightComputer
    for trust weights, forms a trust-weighted consensus trajectory per
    rollout, scores each consensus against the performance cost, and
    returns the first control of the minimum-cost rollout.

    Differs from MPPI only in the action-selection rule:
    - MPPI: softmax-weighted mean of all K controls by exp(-cost/τ).
    - Argmin: single argmin-cost control.

    Uses the exact same TrustWeightComputer that MPPI uses.
    """

    def __init__(
        self,
        config: MPPIConfig,
        perf_config: PerfCostConfig,
        predictors: Dict[str, BasePredictor],
        road: Road,
        obstacles: List[Obstacle],
    ) -> None:
        self.config = config
        self.perf_config = perf_config
        self.predictors = predictors
        self.road = road
        self.obstacles = list(obstacles)
        self._rng = np.random.default_rng(0)
        self._trust_computer = TrustWeightComputer(config.bcvf_config)

    # --- trust-computer passthrough setters ---

    def set_seed(self, seed: int) -> None:
        self._rng = np.random.default_rng(seed)

    def set_ema_alpha(self, alpha: float) -> None:
        self._trust_computer.set_ema_alpha(alpha)

    def set_deadband_k_sigma(self, k_sigma: float) -> None:
        self._trust_computer.set_deadband_k_sigma(k_sigma)

    def set_exclusion(
        self,
        enabled: bool,
        r: float = 1.5,
        T_exclude: int = 20,
        T_reinstate: int = 20,
    ) -> None:
        self._trust_computer.set_exclusion(
            enabled=enabled,
            r=r,
            T_exclude=T_exclude,
            T_reinstate=T_reinstate,
        )

    def reset(self) -> None:
        self._trust_computer.reset()

    # --- planning loop ---

    def plan(self) -> ArgminSelectorResult:
        c = self.config
        model_ids = list(self.predictors.keys())
        num_models = len(model_ids)
        anchor_idx = model_ids.index(c.anchor)

        # Candidate controls — use the same Gaussian sampling MPPI uses
        # around a zero-mean prior. Simpler than MPPI's warm-start path;
        # production adapters would substitute their own sampler.
        controls_batch = self._rng.normal(
            loc=0.0,
            scale=c.noise_std,
            size=(c.num_rollouts, c.horizon, 2),
        )
        # Clip to planner bounds (MPPI uses the same clamp logic).
        v_lo, v_hi = c.velocity_bounds
        steer_hi = c.steering_bounds[1]
        steer_lo = c.steering_bounds[0]
        controls_batch[..., 0] = np.clip(controls_batch[..., 0], v_lo, v_hi)
        controls_batch[..., 1] = np.clip(controls_batch[..., 1], steer_lo, steer_hi)

        k_batch = controls_batch.shape[0]

        # Roll out every predictor.
        all_trajs = np.zeros(
            (k_batch, num_models, c.horizon, 3), dtype=np.float64
        )
        for k in range(k_batch):
            for m_idx, name in enumerate(model_ids):
                all_trajs[k, m_idx] = self.predictors[name].predict(
                    controls_batch[k]
                )

        # Trust weights via the shared computer. Re-configure its
        # BCVFConfig each step with the current anchor_idx and the
        # effective lambda_c (MPPIConfig's value, not BCVFConfig's —
        # see mppi_planner.py for the rationale).
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
        result = self._trust_computer.compute(all_trajs)
        weights = result.weights
        bcvf_total = result.bcvf_total

        # Weighted consensus (same formula as MPPI reference adapter,
        # atan2-safe heading).
        w = weights[..., None, None]
        xy_w = np.sum(all_trajs[..., :2] * w, axis=1)
        sin_w = np.sum(np.sin(all_trajs[..., 2]) * weights[..., None], axis=1)
        cos_w = np.sum(np.cos(all_trajs[..., 2]) * weights[..., None], axis=1)
        theta_w = np.arctan2(sin_w, cos_w)
        consensus_trajs = np.concatenate(
            [xy_w, theta_w[..., None]], axis=-1
        )

        perf_costs = _compute_perf_cost_batch(
            consensus_trajs,
            controls_batch,
            self.road,
            self.obstacles,
            self.perf_config,
        )

        # Argmin selection — this is what makes this adapter non-MPPI.
        # MPPI would do softmax(-perf_costs / temperature) and mix
        # controls; we pick the single best rollout.
        best_idx = int(np.argmin(perf_costs))
        return ArgminSelectorResult(
            first_control=controls_batch[best_idx, 0].copy(),
            selected_rollout_idx=best_idx,
            perf_cost=float(perf_costs[best_idx]),
            bcvf_cost=float(bcvf_total[best_idx]),
        )
