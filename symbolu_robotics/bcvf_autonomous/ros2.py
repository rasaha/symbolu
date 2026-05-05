"""Re-export shim for the ``bcvf_ros2`` package.

The ``bcvf_ros2`` companion package lives at
``symbolu_robotics.bcvf_ros2`` (a sibling of this package, not a
submodule). The :data:`PROVISIONAL_API` registry's
:func:`resolve_qualified` helper hardcodes the
``symbolu_robotics.bcvf_autonomous.`` prefix, so the registry
needs the ROS 2 / DDS surface to be reachable under a path that
includes that prefix.

This module is the re-export shim. Importing from here returns
the same object the canonical ``bcvf_ros2`` package exposes —
``object identity is preserved`` so downstream ``isinstance``
checks work transparently across both paths.

Symbols re-exported:

* :class:`BCVFNode` (alias of :class:`BCVFNodeBehaviour`)
* :class:`BCVFNodeBehaviour`
* :class:`BCVFNodeConfig`
* :class:`PredictorTrajectoryMessage`
* :class:`ConsensusOutputMessage`
* :class:`DDSQoSProfile`
* :data:`DDS_QOS_PROFILE`
* :func:`build_rclpy_qos_profile`

See ``ROS2_DDS_SBOM_DESIGN.md`` for the integration contract.
"""

from symbolu_robotics.bcvf_ros2 import (
    BCVFNode,
    BCVFNodeBehaviour,
    BCVFNodeConfig,
    BCVFTrustBridge,
    BCVFTrustBridgeConfig,
    ConsensusOutputMessage,
    DDS_QOS_PROFILE,
    DDSQoSProfile,
    PredictedTrajectories,
    PredictorTrajectoryMessage,
    TrustDistribution,
    build_rclpy_qos_profile,
)


__all__ = [
    "BCVFNode",
    "BCVFNodeBehaviour",
    "BCVFNodeConfig",
    "BCVFTrustBridge",
    "BCVFTrustBridgeConfig",
    "ConsensusOutputMessage",
    "DDS_QOS_PROFILE",
    "DDSQoSProfile",
    "PredictedTrajectories",
    "PredictorTrajectoryMessage",
    "TrustDistribution",
    "build_rclpy_qos_profile",
]
