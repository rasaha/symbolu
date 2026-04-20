"""Abstract dataset adapter interface for §6.2 pilot.

Every concrete adapter (``synthetic_realistic``, ``nuscenes``,
``kitti``) subclasses ``DatasetAdapter`` and produces ``SceneRecord``
objects that carry the per-timestep predictor trajectories + failure
metadata the V1 pipeline consumes.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Dict, List, Optional

import numpy as np


@dataclass
class SceneRecord:
    """One scene's worth of paired data ready for §6.2 evaluation.

    Fields:
        scene_id:
            Dataset-specific scene identifier (e.g., a nuScenes token
            or a KITTI sequence index).
        ego_trace:
            (T, 3) ground-truth ego pose over T simulator steps, in
            the SE(2) convention (x, y, theta) used by the V1 kernel.
        predictor_trajectories:
            Dict mapping predictor name ("M1".."M4") to a
            (T, H, 3) tensor. At each simulator step t, predictor
            "Mi" emits a length-H SE(2) trajectory forecast.
        failure_metadata:
            Describes the scene's failure injection:
            - ``type``: one of {"gps_multipath", "map_misalignment",
              "camera_degradation", "constant_bias_sanity"}.
            - ``onset_step``: simulator step where the failure starts
              to manifest. ``None`` for benign scenes (no failure).
            - ``duration_steps``: how many steps the failure persists.
            - ``ground_truth_failing_predictor``: which Mi is the
              injected outlier (used for attribution-accuracy
              diagnostics).
        dt:
            Simulator time step in seconds (typically 0.1 at 10 Hz).
    """

    scene_id: str
    ego_trace: np.ndarray                                 # (T, 3)
    predictor_trajectories: Dict[str, np.ndarray]         # Mi -> (T, H, 3)
    failure_metadata: Dict[str, object] = field(default_factory=dict)
    dt: float = 0.1

    def __post_init__(self) -> None:
        if self.ego_trace.ndim != 2 or self.ego_trace.shape[-1] != 3:
            raise ValueError(
                f"ego_trace must be (T, 3); got {self.ego_trace.shape}"
            )
        T = self.ego_trace.shape[0]
        for name, arr in self.predictor_trajectories.items():
            if arr.ndim != 3 or arr.shape[0] != T or arr.shape[-1] != 3:
                raise ValueError(
                    f"predictor {name} trajectory must be ({T}, H, 3); "
                    f"got {arr.shape}"
                )

    @property
    def num_predictors(self) -> int:
        return len(self.predictor_trajectories)

    @property
    def num_steps(self) -> int:
        return self.ego_trace.shape[0]

    @property
    def horizon(self) -> int:
        first = next(iter(self.predictor_trajectories.values()))
        return int(first.shape[1])


class DatasetAdapter(ABC):
    """Abstract interface for a §6.2 dataset adapter.

    Concrete subclasses implement ``scene_ids()`` and ``load_scene(id)``.
    The pilot runner iterates over paired (A0, A3) runs across all
    scenes returned by ``scene_ids()``.
    """

    @abstractmethod
    def scene_ids(self) -> List[str]:
        """Return all scene identifiers available from this adapter."""

    @abstractmethod
    def load_scene(self, scene_id: str) -> SceneRecord:
        """Load one scene's SceneRecord from the underlying dataset."""

    def __len__(self) -> int:
        return len(self.scene_ids())

    def __iter__(self):
        for sid in self.scene_ids():
            yield self.load_scene(sid)
