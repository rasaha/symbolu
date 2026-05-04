"""Per-horizon-step BCVF observables.

The aggregate ``compute_bcvf_cost`` sums the
``gate * pseudo_huber(signal)`` array across the horizon. Two
observables that read the array *before* the horizon-sum:

  BCVFPerStepMaxObservable
    scalar = max over horizon steps of the summed-across-pairs
             per-step BCVF cost. Mirrors the BCVF LLM
             ``bcvf_per_step_max`` reduction that surfaced
             discriminative signal where the aggregate did not.

  BCVFPredictorPerStepMaxObservable
    scalar = max over horizon steps of the cost attributed to
             a single predictor (sum of pair costs containing it).
             Targets the "the failing predictor's step-spike is
             being smoothed out by the per-tick aggregate" failure
             mode — a per-predictor analog of LLM's
             ``bcvf_source_0_per_step_max``.
"""

from __future__ import annotations

from typing import Optional

import numpy as np

from ..core import BCVFConfig
from .base import ObservableValue, validate_trajectory_tensor
from .kernel_per_step import compute_bcvf_per_step


class BCVFPerStepMaxObservable:
    name: str = "bcvf_per_step_max"
    higher_means_more_suspicious: bool = True

    def __init__(self, bcvf_config: Optional[BCVFConfig] = None) -> None:
        self._cfg = bcvf_config or BCVFConfig()

    def observe(
        self,
        trajectories: np.ndarray,
        ground_truth: Optional[np.ndarray] = None,
    ) -> ObservableValue:
        arr = validate_trajectory_tensor(trajectories, min_horizon=3)
        breakdown = compute_bcvf_per_step(arr, self._cfg)
        per_step = breakdown.per_step_total
        n_steps = int(per_step.shape[0])
        scalar = float(per_step.max()) if n_steps > 0 else 0.0
        per_predictor = breakdown.per_step_per_predictor.max(axis=1)

        return ObservableValue(
            scalar=scalar,
            per_predictor=per_predictor,
            metadata={
                "per_step_costs": per_step.tolist(),
                "n_steps": n_steps,
                "mean_cost": float(per_step.mean()) if n_steps > 0 else 0.0,
                "argmax_step": (
                    int(per_step.argmax()) if n_steps > 0 else -1
                ),
                "total_cost": float(per_step.sum()),
                "gate_activations_per_step": (
                    breakdown.gate_activations_per_step.tolist()
                ),
            },
        )


class BCVFPredictorPerStepMaxObservable:
    """Max per-step cost attributed to one predictor across the horizon.

    Aggregation matches ``compute_bcvf_cost_batch(..., return_per_predictor=True)``:
    a predictor's per-step cost is the sum of pair costs the predictor
    participates in. The lone-failing-predictor signature is a per-
    predictor step-spike that the across-pair sum amplifies; the
    healthy population's step-spike, if any, is one pair only.
    """

    higher_means_more_suspicious: bool = True

    def __init__(
        self,
        predictor_index: int,
        bcvf_config: Optional[BCVFConfig] = None,
    ) -> None:
        if predictor_index < 0:
            raise ValueError("predictor_index must be >= 0")
        self._idx = int(predictor_index)
        self._cfg = bcvf_config or BCVFConfig()
        self.name = f"bcvf_predictor_{predictor_index}_per_step_max"

    def observe(
        self,
        trajectories: np.ndarray,
        ground_truth: Optional[np.ndarray] = None,
    ) -> ObservableValue:
        arr = validate_trajectory_tensor(trajectories, min_horizon=3)
        if self._idx >= arr.shape[0]:
            raise IndexError(
                f"predictor_index {self._idx} out of range for M={arr.shape[0]}"
            )
        breakdown = compute_bcvf_per_step(arr, self._cfg)
        predictor_series = breakdown.per_step_per_predictor[self._idx]
        n_steps = int(predictor_series.shape[0])
        scalar = float(predictor_series.max()) if n_steps > 0 else 0.0

        return ObservableValue(
            scalar=scalar,
            per_predictor=breakdown.per_step_per_predictor.max(axis=1),
            metadata={
                "predictor_index": self._idx,
                "per_step_predictor_costs": predictor_series.tolist(),
                "per_step_total_costs": breakdown.per_step_total.tolist(),
                "argmax_step": (
                    int(predictor_series.argmax()) if n_steps > 0 else -1
                ),
                "n_steps": n_steps,
            },
        )
