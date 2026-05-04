"""Ensemble-spread observable (the autonomous analog of LLM entropy).

For BCVF LLM the natural confidence proxy is the entropy of the
base model's next-token distribution. The autonomous analog is the
*spatial* spread of the predictor ensemble: at each horizon step,
how far apart are the predictors in body-frame? Higher spread =
the ensemble is hedging across multiple plausible futures = more
suspicion, in the same polarity sense.

Two scalars are tracked:

  EnsembleSpreadObservable
    scalar = mean over horizon of the per-step radial spread
             (mean over predictors of ``||xy_i - mean_xy||``)

  EnsembleHeadingEntropyObservable
    scalar = mean over horizon of the angular dispersion
             ``1 - |mean(unit_vectors_of_heading)|`` — the circular-
             stats analog of Shannon entropy on the heading
             distribution. Higher = headings disagree more.

Both are independent of any ground truth and require no kernel
call; they are pure ensemble-statistics probes.
"""

from __future__ import annotations

from typing import Optional

import numpy as np

from .base import ObservableValue, validate_trajectory_tensor


class EnsembleSpreadObservable:
    name: str = "ensemble_spatial_spread"
    higher_means_more_suspicious: bool = True

    def observe(
        self,
        trajectories: np.ndarray,
        ground_truth: Optional[np.ndarray] = None,
    ) -> ObservableValue:
        arr = validate_trajectory_tensor(trajectories)
        M, H, _ = arr.shape

        mean_xy = arr[..., :2].mean(axis=0, keepdims=True)  # (1, H, 2)
        deviations = np.linalg.norm(
            arr[..., :2] - mean_xy, axis=-1
        )  # (M, H)
        per_step_spread = deviations.mean(axis=0)  # (H,)
        scalar = float(per_step_spread.mean()) if H > 0 else 0.0

        per_predictor_mean = deviations.mean(axis=1)  # (M,)

        return ObservableValue(
            scalar=scalar,
            per_predictor=per_predictor_mean,
            metadata={
                "per_step_spread": per_step_spread.tolist(),
                "max_step_spread": float(per_step_spread.max()) if H > 0 else 0.0,
                "argmax_step": (
                    int(per_step_spread.argmax()) if H > 0 else -1
                ),
                "H": int(H),
                "M": int(M),
            },
        )


class EnsembleHeadingEntropyObservable:
    """Circular-statistics dispersion of predictor headings.

    For each horizon step, compute the resultant length
    ``R = |mean(e^{i theta_m})|``. ``R`` lies in ``[0, 1]``: 1 means
    all predictors agree on heading, 0 means they are uniformly
    distributed on the circle. The dispersion ``1 - R`` is the
    natural "circular entropy" — bounded in ``[0, 1]``, matches
    Shannon entropy's polarity (more dispersed = higher).
    """

    name: str = "ensemble_heading_entropy"
    higher_means_more_suspicious: bool = True

    def observe(
        self,
        trajectories: np.ndarray,
        ground_truth: Optional[np.ndarray] = None,
    ) -> ObservableValue:
        arr = validate_trajectory_tensor(trajectories)
        M, H, _ = arr.shape

        sin_t = np.sin(arr[..., 2])  # (M, H)
        cos_t = np.cos(arr[..., 2])
        mean_sin = sin_t.mean(axis=0)  # (H,)
        mean_cos = cos_t.mean(axis=0)
        resultant_len = np.sqrt(mean_sin * mean_sin + mean_cos * mean_cos)
        per_step_dispersion = np.clip(1.0 - resultant_len, 0.0, 1.0)
        scalar = float(per_step_dispersion.mean()) if H > 0 else 0.0

        return ObservableValue(
            scalar=scalar,
            metadata={
                "per_step_dispersion": per_step_dispersion.tolist(),
                "max_step_dispersion": (
                    float(per_step_dispersion.max()) if H > 0 else 0.0
                ),
                "argmax_step": (
                    int(per_step_dispersion.argmax()) if H > 0 else -1
                ),
                "H": int(H),
                "M": int(M),
            },
        )
