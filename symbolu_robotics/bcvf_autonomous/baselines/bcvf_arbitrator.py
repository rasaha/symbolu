"""BCVF arbitrator — wraps the existing kernel + V1 trust shaper
at the same interface the baselines use.

At each horizon step:
  1. Run :func:`compute_bcvf_per_step` on the (M, H, 3) trajectory
     tensor to get per-predictor cost time series.
  2. Sum across the horizon to get per-predictor total attribution.
  3. Apply the V1 trust shaping (per-source EMA centering optional;
     softmin) to convert per-predictor cost into trust weights.
  4. Consensus = trust-weighted mean of the M trajectories.

The BCVF kernel produces a *per-step per-predictor* breakdown,
which makes attribution much more granular than the EKF or
majority-vote baselines (which only have per-step or per-tick
attribution). For the shootout's headline metrics we collapse to
per-predictor scalars; the granularity remains available via the
existing per-step diagnostic record.
"""

from __future__ import annotations

import time

import numpy as np

from ..core import BCVFConfig, CostOrder
from ..observables.kernel_per_step import compute_bcvf_per_step
from .base import ArbitrationResult, Arbitrator, validate_trajectories


class BCVFArbitrator:
    name: str = "BCVF"

    def __init__(self, config: BCVFConfig | None = None,
                 trust_temperature: float = 1.0) -> None:
        self._cfg = config or BCVFConfig(
            gate_threshold=0.05, gate_beta=400.0, huber_delta=0.5,
            lever_arm=2.5, weight_matrix=np.ones(3, dtype=np.float64),
            use_anchor_pairing=False, anchor_index=0,
            dt=0.1, cost_order=CostOrder.SECOND, lambda_c=1.0,
        )
        if trust_temperature <= 0:
            raise ValueError("trust_temperature must be > 0")
        self._tau = float(trust_temperature)

    def arbitrate(self, trajectories: np.ndarray) -> ArbitrationResult:
        arr = validate_trajectories(trajectories)
        M, H, _ = arr.shape
        t0 = time.perf_counter()
        breakdown = compute_bcvf_per_step(arr, self._cfg)
        per_predictor_cost = breakdown.per_step_per_predictor.sum(axis=1)

        # Softmin trust weights.
        shifted = per_predictor_cost - per_predictor_cost.min()
        arg = np.clip(-shifted / self._tau, -50.0, 50.0)
        raw = np.exp(arg)
        weights = raw / raw.sum()

        # Weighted consensus, atan2-safe on heading.
        w = weights.reshape(-1, 1, 1)
        consensus_xy = (w * arr[..., :2]).sum(axis=0)
        sin_w = (weights[:, None] * np.sin(arr[..., 2])).sum(axis=0)
        cos_w = (weights[:, None] * np.cos(arr[..., 2])).sum(axis=0)
        consensus_th = np.arctan2(sin_w, cos_w)
        consensus = np.concatenate(
            [consensus_xy, consensus_th[:, None]], axis=-1
        )

        elapsed_us = (time.perf_counter() - t0) * 1e6
        per_tick_us = elapsed_us / H

        return ArbitrationResult(
            consensus=consensus,
            attribution=per_predictor_cost,
            per_tick_us=per_tick_us,
            metadata={
                "trust_weights": weights.tolist(),
                "trust_temperature": self._tau,
            },
        )
