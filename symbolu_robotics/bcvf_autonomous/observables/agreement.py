"""Predictor-agreement observable.

Cheapest disagreement proxy. Along the planning horizon, count the
fraction of timesteps where every predictor agrees with the
ensemble mean within a position tolerance and a heading tolerance.

  agreement_fraction = (# steps where all predictors are within
                        tolerance of the ensemble mean) / H
  scalar             = 1 - agreement_fraction

Polarity matches BCVF: higher = more suspicious. Cheap — no kernel
call, only a mean / norm sweep over the trajectory tensor.
"""

from __future__ import annotations

from typing import Optional

import numpy as np

from ..manifold import wrap_angle
from .base import ObservableValue, validate_trajectory_tensor


class PredictorAgreementObservable:
    name: str = "predictor_disagreement_fraction"
    higher_means_more_suspicious: bool = True

    def __init__(
        self,
        position_tolerance: float = 0.5,
        heading_tolerance: float = 0.1,
    ) -> None:
        if position_tolerance < 0:
            raise ValueError("position_tolerance must be >= 0")
        if heading_tolerance < 0:
            raise ValueError("heading_tolerance must be >= 0")
        self._pos_tol = float(position_tolerance)
        self._heading_tol = float(heading_tolerance)

    def observe(
        self,
        trajectories: np.ndarray,
        ground_truth: Optional[np.ndarray] = None,
    ) -> ObservableValue:
        arr = validate_trajectory_tensor(trajectories)
        M, H, _ = arr.shape

        mean_xy = arr[..., :2].mean(axis=0)  # (H, 2)
        mean_sin = np.sin(arr[..., 2]).mean(axis=0)
        mean_cos = np.cos(arr[..., 2]).mean(axis=0)
        mean_th = np.arctan2(mean_sin, mean_cos)  # (H,)

        pos_dev = np.linalg.norm(
            arr[..., :2] - mean_xy[None, :, :], axis=-1
        )  # (M, H)
        heading_diff = arr[..., 2] - mean_th[None, :]
        heading_dev = np.abs(
            np.arctan2(np.sin(heading_diff), np.cos(heading_diff))
        )  # (M, H)

        all_within_pos = np.all(pos_dev < self._pos_tol, axis=0)        # (H,)
        all_within_heading = np.all(heading_dev < self._heading_tol, axis=0)
        unanimous = all_within_pos & all_within_heading
        agreement_fraction = float(unanimous.mean()) if H > 0 else 1.0

        per_predictor_max_dev = pos_dev.max(axis=1)  # (M,)

        return ObservableValue(
            scalar=1.0 - agreement_fraction,
            per_predictor=per_predictor_max_dev,
            metadata={
                "agreement_fraction": agreement_fraction,
                "H": int(H),
                "M": int(M),
                "position_tolerance": self._pos_tol,
                "heading_tolerance": self._heading_tol,
                "max_position_deviation": float(pos_dev.max()),
                "max_heading_deviation": float(heading_dev.max()),
            },
        )
