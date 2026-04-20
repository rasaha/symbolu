"""Framework-agnostic ROS 2 bridge core.

Pure-Python bridge between the ROS 2 message layer and the autonomy
``TrustWeightComputer``. Consumes ``PredictedTrajectories`` dataclasses
(equivalent to the incoming ROS msg payload) and produces
``TrustDistribution`` dataclasses (equivalent to the outgoing msg
payload). No ``rclpy`` imports — testable in any Python environment.

The ``ros2_shim`` module wraps this with rclpy pub/sub + timers once
a real ROS 2 install is available.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

import numpy as np

from ..bcvf_autonomous.core import BCVFConfig
from ..bcvf_autonomous.trust import TrustWeightComputer
from .messages import PredictedTrajectories, TrustDistribution


@dataclass
class BCVFTrustBridgeConfig:
    """Configuration for the ROS 2 bridge (parameters that would come
    from ROS 2 node parameters at runtime)."""

    bcvf_config: BCVFConfig
    ema_alpha: float = 0.05
    deadband_k_sigma: float = 2.0
    trust_temperature: float = 1.0
    exclusion_enabled: bool = False
    exclusion_r: float = 1.5
    exclusion_T: int = 20
    exclusion_T_reinstate: int = 20


class BCVFTrustBridge:
    """Pure-Python bridge between ``PredictedTrajectories`` messages
    and ``TrustDistribution`` messages.

    Wraps a ``TrustWeightComputer`` and handles the message <-> tensor
    conversion. Stateful (EMA, exclusion); ``reset()`` between
    episodes.

    Usage:
        bridge = BCVFTrustBridge(cfg)
        for pred_msg in incoming_predictions:
            trust_msg = bridge.step(pred_msg)
            # publish trust_msg to /trust_distribution
    """

    def __init__(self, cfg: BCVFTrustBridgeConfig) -> None:
        self._cfg = cfg
        self._computer = TrustWeightComputer(cfg.bcvf_config)
        self._computer.set_ema_alpha(cfg.ema_alpha)
        self._computer.set_deadband_k_sigma(cfg.deadband_k_sigma)
        self._computer.set_trust_temperature(cfg.trust_temperature)
        if cfg.exclusion_enabled:
            self._computer.set_exclusion(
                enabled=True,
                r=cfg.exclusion_r,
                T_exclude=cfg.exclusion_T,
                T_reinstate=cfg.exclusion_T_reinstate,
            )
        self._latest_predictor_names: Optional[list] = None

    def reset(self) -> None:
        """Clear per-episode state. Call on new episode or mode change."""
        self._computer.reset()

    def step(self, msg: PredictedTrajectories) -> TrustDistribution:
        """Consume one ``PredictedTrajectories`` msg, produce one
        ``TrustDistribution`` msg.

        The frame_id and stamp are propagated; the predictor_names
        list is carried forward unchanged.
        """
        self._latest_predictor_names = list(msg.predictor_names)
        result = self._computer.compute(msg.trajectories)
        return TrustDistribution(
            stamp=msg.stamp,
            frame_id=msg.frame_id,
            predictor_names=list(msg.predictor_names),
            weights=result.weights,
            bcvf_total=result.bcvf_total,
            ema_mean=(
                result.ema_mean.copy()
                if result.ema_mean is not None else None
            ),
            ema_std=(
                result.ema_std.copy()
                if result.ema_std is not None else None
            ),
            deadband_active_count=int(result.deadband_active_count),
            is_excluded=(
                result.is_excluded.copy()
                if result.is_excluded is not None else None
            ),
        )

    @property
    def config(self) -> BCVFTrustBridgeConfig:
        return self._cfg

    @property
    def trust_computer(self) -> TrustWeightComputer:
        """Exposed for diagnostic / test introspection."""
        return self._computer
