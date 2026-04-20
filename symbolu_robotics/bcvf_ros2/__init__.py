"""§6.4 ROS 2 companion package for the BCVF Autonomy Runtime.

Framework-agnostic core (``core``, ``messages``) is pure Python and
can be tested / used without ROS 2 installed. The ``ros2_shim``
module lazily imports ``rclpy`` and produces a real ROS 2 node
(``BCVFTrustNode``) when an rclpy environment is present.

Design: see ``docs/experiments/phase_6_4_ros2_plan.md``.
"""

from .core import BCVFTrustBridge
from .messages import PredictedTrajectories, TrustDistribution

__all__ = [
    "BCVFTrustBridge",
    "PredictedTrajectories",
    "TrustDistribution",
]
