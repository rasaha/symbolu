"""Coherence-anchored BCVF observable.

BCVF LLM §11.11 result: aggregate BCVF is direction-free — it
detects disagreement but cannot tell truth from consensus
hallucination. Multiplying by a truth-direction anchor surfaced
signal that neither factor alone carried. The autonomous analog:

  scalar = stability * alignment

where

  stability = 1 / (1 + max-step BCVF cost)
              — high when no horizon step lights up the kernel
  alignment = exp(-mean_step ||xy_consensus - xy_ground_truth|| / scale)
              — high when the trust-weighted ensemble mean tracks the
              ground-truth trajectory

Polarity: trust (higher = better). The alignment factor uses the
ensemble mean as a stand-in for the consensus the planner would
produce; passing predictor-specific weights via ``ensemble_weights``
lets a caller substitute the actual MPPI consensus when it has been
computed.

When ``ground_truth`` is ``None``, alignment defaults to 1.0 and the
scalar reduces to pure stability — useful at planning time when
truth is unknown but the observable is still wanted as a stability
proxy.
"""

from __future__ import annotations

from typing import Optional

import numpy as np

from ..core import BCVFConfig
from .base import ObservableValue, validate_trajectory_tensor
from .kernel_per_step import compute_bcvf_per_step


class CoherenceAnchoredBCVFObservable:
    name: str = "coherence_anchored_bcvf"
    higher_means_more_suspicious: bool = False

    def __init__(
        self,
        bcvf_config: Optional[BCVFConfig] = None,
        alignment_scale: float = 1.0,
        ensemble_weights: Optional[np.ndarray] = None,
    ) -> None:
        if alignment_scale <= 0:
            raise ValueError("alignment_scale must be > 0")
        self._cfg = bcvf_config or BCVFConfig()
        self._scale = float(alignment_scale)
        self._weights = (
            None if ensemble_weights is None
            else np.asarray(ensemble_weights, dtype=np.float64)
        )

    def observe(
        self,
        trajectories: np.ndarray,
        ground_truth: Optional[np.ndarray] = None,
    ) -> ObservableValue:
        arr = validate_trajectory_tensor(trajectories)
        M, H, _ = arr.shape

        breakdown = compute_bcvf_per_step(arr, self._cfg)
        per_step = breakdown.per_step_total
        max_bcvf = float(per_step.max()) if per_step.size > 0 else 0.0
        stability = 1.0 / (1.0 + max_bcvf)

        if ground_truth is None:
            alignment = 1.0
            mean_err = float("nan")
        else:
            gt = np.asarray(ground_truth, dtype=np.float64)
            if gt.shape != (H, 3):
                raise ValueError(
                    f"ground_truth must have shape (H, 3) = ({H}, 3); "
                    f"got {gt.shape}"
                )
            if self._weights is None:
                consensus_xy = arr[..., :2].mean(axis=0)  # (H, 2)
            else:
                if self._weights.shape != (M,):
                    raise ValueError(
                        f"ensemble_weights must have shape ({M},); "
                        f"got {self._weights.shape}"
                    )
                w = self._weights / max(self._weights.sum(), 1e-12)
                consensus_xy = np.einsum("m,mhd->hd", w, arr[..., :2])
            err = np.linalg.norm(consensus_xy - gt[..., :2], axis=-1)
            mean_err = float(err.mean())
            alignment = float(np.exp(-mean_err / self._scale))

        scalar = stability * alignment

        return ObservableValue(
            scalar=scalar,
            metadata={
                "stability": stability,
                "alignment": alignment,
                "max_step_bcvf": max_bcvf,
                "mean_alignment_error": mean_err,
                "n_steps": int(per_step.shape[0]),
                "per_step_costs": per_step.tolist(),
                "alignment_scale": self._scale,
            },
        )
