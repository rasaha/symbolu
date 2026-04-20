"""Python dataclasses mirroring the eventual ROS 2 ``.msg`` types.

These are the framework-agnostic message payloads the
``BCVFTrustBridge`` consumes and produces. The ``ros2_shim`` converts
between these dataclasses and real ``rclpy``-generated message types
at the ROS boundary.

See ``docs/experiments/phase_6_4_ros2_plan.md`` §Message schema for
the intended ``.msg`` files.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import List, Optional

import numpy as np


@dataclass
class PredictedTrajectories:
    """Payload of ``/predicted_trajectories`` — aggregated predictor
    output from all M predictor nodes for a single planning step.

    Fields map 1:1 to the sketched ``PredictedTrajectories.msg``
    except ``trajectories`` stays an ``ndarray`` rather than a
    flattened ``Pose2D[]`` to avoid repeated flatten/unflatten in
    the pure-Python core. The ``ros2_shim`` handles the flatten at
    the ROS boundary.
    """

    stamp: float                        # nanoseconds since epoch
    frame_id: str                       # e.g., "map" or "base_link"
    predictor_names: List[str]          # length M
    trajectories: np.ndarray            # (K, M, H, 3) SE(2) x/y/θ

    def __post_init__(self) -> None:
        if self.trajectories.ndim != 4 or self.trajectories.shape[-1] != 3:
            raise ValueError(
                "PredictedTrajectories.trajectories must be (K, M, H, 3); "
                f"got {self.trajectories.shape}"
            )
        if len(self.predictor_names) != self.trajectories.shape[1]:
            raise ValueError(
                f"predictor_names has {len(self.predictor_names)} entries "
                f"but trajectories has M = {self.trajectories.shape[1]}"
            )

    @property
    def num_predictors(self) -> int:
        return int(self.trajectories.shape[1])

    @property
    def num_rollouts(self) -> int:
        return int(self.trajectories.shape[0])

    @property
    def horizon(self) -> int:
        return int(self.trajectories.shape[2])


@dataclass
class TrustDistribution:
    """Payload of ``/trust_distribution`` — the BCVF bridge output.

    One per planning step, published in response to each incoming
    ``PredictedTrajectories``.
    """

    stamp: float
    frame_id: str
    predictor_names: List[str]
    weights: np.ndarray                  # (K, M), rows sum to 1
    bcvf_total: np.ndarray               # (K,), diagnostic
    ema_mean: Optional[np.ndarray] = None        # (M,) or None
    ema_std: Optional[np.ndarray] = None         # (M,) or None
    deadband_active_count: int = 0
    is_excluded: Optional[np.ndarray] = None     # (M,) bool or None

    def __post_init__(self) -> None:
        if self.weights.ndim != 2 or self.weights.shape[-1] != len(self.predictor_names):
            raise ValueError(
                "TrustDistribution.weights must be (K, M) with M matching "
                "predictor_names; got "
                f"weights.shape={self.weights.shape}, "
                f"len(predictor_names)={len(self.predictor_names)}"
            )
        if self.bcvf_total.ndim != 1 or self.bcvf_total.shape[0] != self.weights.shape[0]:
            raise ValueError(
                "TrustDistribution.bcvf_total must be (K,) matching "
                "weights.shape[0]"
            )

    @property
    def num_predictors(self) -> int:
        return int(self.weights.shape[1])

    @property
    def num_rollouts(self) -> int:
        return int(self.weights.shape[0])
