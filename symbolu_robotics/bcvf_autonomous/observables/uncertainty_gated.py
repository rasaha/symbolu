"""Uncertainty-gated per-step BCVF observable.

BCVF LLM §11.14 diagnosis: per-step BCVF is only discriminative
when the base model is genuinely uncertain. On confident steps,
the prior is either right or confidently wrong; neither benefits
from trust shaping. The autonomous analog: per-step BCVF is only
discriminative when the predictor *ensemble* itself is genuinely
spread — when every predictor agrees, BCVF is firing on noise; when
predictors hedge across multiple plausible futures, the per-step
BCVF spike points at the disagreeing predictor.

  UncertaintyGatedBCVFPerStepMaxObservable
    scalar = max over steps where ensemble_spread(step) > tau of
             per_step_bcvf(step)

The gate is the per-step ensemble radial spread (mean over
predictors of the body-frame distance to the ensemble mean).
``tau = 0.5 m`` is a reasonable autonomous-driving default — the
spread at which predictors stop visibly agreeing on a single
future. Pre-committed; not tuned post-hoc.
"""

from __future__ import annotations

from typing import Optional

import numpy as np

from ..core import BCVFConfig
from .base import ObservableValue, validate_trajectory_tensor
from .kernel_per_step import compute_bcvf_per_step, stencil_align_to_signal


_DEFAULT_SPREAD_THRESHOLD = 0.5  # metres


class UncertaintyGatedBCVFPerStepMaxObservable:
    """Max per-step BCVF cost restricted to steps where ensemble spread > tau."""

    name: str = "uncertainty_gated_bcvf_per_step_max"
    higher_means_more_suspicious: bool = True

    def __init__(
        self,
        bcvf_config: Optional[BCVFConfig] = None,
        spread_threshold: float = _DEFAULT_SPREAD_THRESHOLD,
    ) -> None:
        if spread_threshold < 0:
            raise ValueError("spread_threshold must be >= 0")
        self._cfg = bcvf_config or BCVFConfig()
        self._tau = float(spread_threshold)

    def observe(
        self,
        trajectories: np.ndarray,
        ground_truth: Optional[np.ndarray] = None,
    ) -> ObservableValue:
        arr = validate_trajectory_tensor(trajectories, min_horizon=3)
        M, H, _ = arr.shape

        breakdown = compute_bcvf_per_step(arr, self._cfg)
        per_step_bcvf = breakdown.per_step_total
        n_steps = int(per_step_bcvf.shape[0])

        # Per-horizon-step ensemble spread on the full H-length axis,
        # then aligned to the BCVF stencil so the two series share an
        # index.
        mean_xy = arr[..., :2].mean(axis=0, keepdims=True)
        deviations = np.linalg.norm(
            arr[..., :2] - mean_xy, axis=-1
        )  # (M, H)
        spread_full = deviations.mean(axis=0)  # (H,)
        spread_aligned = stencil_align_to_signal(
            spread_full, self._cfg.cost_order
        )

        if spread_aligned.shape != per_step_bcvf.shape:
            raise RuntimeError(
                "spread / bcvf series shape mismatch — "
                f"{spread_aligned.shape} vs {per_step_bcvf.shape}"
            )

        gate_mask = spread_aligned > self._tau
        gated_costs = per_step_bcvf[gate_mask]
        scalar = float(gated_costs.max()) if gated_costs.size > 0 else 0.0

        return ObservableValue(
            scalar=scalar,
            metadata={
                "spread_threshold": self._tau,
                "n_steps": n_steps,
                "n_uncertain_steps": int(gate_mask.sum()),
                "per_step_costs": per_step_bcvf.tolist(),
                "per_step_spread": spread_aligned.tolist(),
                "max_step_cost_all": (
                    float(per_step_bcvf.max()) if n_steps > 0 else 0.0
                ),
                "max_step_cost_gated": scalar,
            },
        )
