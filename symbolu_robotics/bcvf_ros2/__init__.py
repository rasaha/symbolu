"""§6.4 ROS 2 companion package for the BCVF Autonomy Runtime.

Framework-agnostic core (``core``, ``messages``, ``node``, ``qos``)
is pure Python and can be tested / used without ROS 2 installed.
The ``ros2_shim`` module lazily imports ``rclpy`` and produces a
real ROS 2 node when an rclpy environment is present.

Public surface (post-v0.7.x, provisional):

* :class:`BCVFTrustBridge` — pure-Python trust-shaping bridge.
* :class:`BCVFTrustBridgeConfig` — bridge config dataclass.
* :class:`PredictedTrajectories` / :class:`TrustDistribution` —
  framework-agnostic message dataclasses.
* :class:`PredictorTrajectoryMessage` /
  :class:`ConsensusOutputMessage` — typed equivalents of the
  per-predictor + consensus-output ROS 2 ``.msg`` schemas.
* :class:`BCVFNodeBehaviour` (alias :data:`BCVFNode`) —
  framework-agnostic node behaviour with rate-limiting +
  deadline-awareness + safety-state-machine composition.
* :class:`BCVFNodeConfig` — node-level configuration.
* :class:`DDSQoSProfile` + :data:`DDS_QOS_PROFILE` — the
  documented DDS QoS profile (RELIABLE / VOLATILE / 10 ms / 100 ms).
* :func:`build_rclpy_qos_profile` — lazy-rclpy adapter.

Design: see ``bcvf_autonomous/ROS2_DDS_SBOM_DESIGN.md`` for the
full design + ship-when-ready criteria.
"""

from .core import BCVFTrustBridge, BCVFTrustBridgeConfig
from .messages import PredictedTrajectories, TrustDistribution
from .node import (
    BCVFNode,
    BCVFNodeBehaviour,
    BCVFNodeConfig,
    ConsensusOutputMessage,
    PredictorTrajectoryMessage,
)
from .qos import DDS_QOS_PROFILE, DDSQoSProfile, build_rclpy_qos_profile


__all__ = [
    # Bridge layer
    "BCVFTrustBridge",
    "BCVFTrustBridgeConfig",
    "PredictedTrajectories",
    "TrustDistribution",
    # Node behaviour layer
    "BCVFNode",
    "BCVFNodeBehaviour",
    "BCVFNodeConfig",
    "PredictorTrajectoryMessage",
    "ConsensusOutputMessage",
    # DDS QoS profile
    "DDS_QOS_PROFILE",
    "DDSQoSProfile",
    "build_rclpy_qos_profile",
]
