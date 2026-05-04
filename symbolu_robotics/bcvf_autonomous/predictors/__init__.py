"""Predictor framework for BCVF Autonomous.

V3.1 reference: Appendix E.2.

Public API:

    from symbolu_robotics.bcvf_autonomous.predictors import (
        BasePredictor,
        BicycleConfig, PredictorState, FailureConfig, ControlInput,
        IMUOdometry, LidarSLAM, VisualOdometry, GNSSMap,
        create_predictor_set,
    )
"""

from __future__ import annotations

from typing import Dict, Optional

from .base import (
    BasePredictor,
    BicycleConfig,
    ControlInput,
    FailureConfig,
    PredictorState,
)
from .gnss_map import GNSSMap
from .imu_odometry import IMUOdometry
from .lidar_slam import LidarSLAM
from .multi_modal import (
    MultiModalPredictor,
    lane_frame_to_se2,
    se2_to_lane_frame,
    unify_to_se2_bundle,
)
from .state_space import LaneAnchor, PredictorStateSpace
from .visual_odometry import VisualOdometry


def create_predictor_set(
    bicycle_config: Optional[BicycleConfig] = None,
    seed: int = 42,
    gnss_failure_type: str = "multipath",
) -> Dict[str, BasePredictor]:
    """Instantiate the standard 4-predictor set (V3.1 Appendix E.2).

    Each predictor is given a deterministic seed offset so experiment runs
    are reproducible. The anchor is always ``M1`` — IMU+odometry — per
    DESIGN.md §2.3.2.
    """
    return {
        "M1": IMUOdometry(bicycle_config, seed=seed),
        "M2": LidarSLAM(bicycle_config, seed=seed + 1),
        "M3": VisualOdometry(bicycle_config, seed=seed + 2),
        "M4": GNSSMap(bicycle_config, seed=seed + 3, failure_type=gnss_failure_type),
    }


__all__ = [
    "BasePredictor",
    "BicycleConfig",
    "ControlInput",
    "FailureConfig",
    "GNSSMap",
    "IMUOdometry",
    "LaneAnchor",
    "LidarSLAM",
    "MultiModalPredictor",
    "PredictorState",
    "PredictorStateSpace",
    "VisualOdometry",
    "create_predictor_set",
    "lane_frame_to_se2",
    "se2_to_lane_frame",
    "unify_to_se2_bundle",
]
