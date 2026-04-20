"""ROS 2 node shim — lazily imports ``rclpy``.

Only used when running inside a real ROS 2 environment. Kept in a
separate file so the rest of the package is importable without
``rclpy`` installed (tests, CI, the §6.4 pre-pilot scaffold).

The real implementation lands in the §6.4 execution phase (~1 week
of work against a Humble/Jazzy environment). This file documents the
intended shape and includes a runnable stub that imports rclpy at
call time, so running ``python -m symbolu_robotics.bcvf_ros2.ros2_shim``
fails cleanly with "rclpy not available" in a non-ROS environment
rather than raising an import-time error.
"""

from __future__ import annotations

import sys
from typing import TYPE_CHECKING


def _require_rclpy():
    """Import rclpy on demand; raise a clear error if unavailable."""
    try:
        import rclpy  # noqa: F401
        from rclpy.node import Node  # noqa: F401
    except ImportError as e:
        raise ImportError(
            "ROS 2 (rclpy) is not installed in this environment. "
            "The BCVFTrustNode requires a ROS 2 Humble or newer "
            "installation. See docs/experiments/phase_6_4_ros2_plan.md "
            "for installation guidance. The pure-Python "
            "BCVFTrustBridge in symbolu_robotics.bcvf_ros2.core is "
            "usable without rclpy and should be used for testing / "
            "development / CI."
        ) from e


if TYPE_CHECKING:  # pragma: no cover
    import rclpy
    from rclpy.node import Node


def build_bcvf_trust_node(bridge_config):
    """Factory for a BCVFTrustNode. Lazy-imports rclpy.

    Returns an instance of the internal _BCVFTrustNode class that
    subscribes to ``/predicted_trajectories``, runs BCVF trust
    shaping via the framework-agnostic bridge, and publishes
    ``/trust_distribution``.

    NOTE: This is a scaffold. The actual message-type bindings to
    real ROS 2 message classes land in the §6.4 execution phase
    (see docs/experiments/phase_6_4_ros2_plan.md).
    """
    _require_rclpy()
    import rclpy
    from rclpy.node import Node
    from .core import BCVFTrustBridge

    class _BCVFTrustNode(Node):
        """ROS 2 Node wrapping the BCVFTrustBridge.

        Subscribed: /predicted_trajectories (PredictedTrajectories.msg)
        Published:  /trust_distribution     (TrustDistribution.msg)

        Both message types are custom to this package and must be
        available in the ROS 2 interface registry (CMakeLists.txt
        + package.xml in the colcon build — landed in §6.4 exec).
        """

        def __init__(self):
            super().__init__("bcvf_trust")
            self._bridge = BCVFTrustBridge(bridge_config)
            # TODO (§6.4 exec): real subscription + publication once
            # the custom msg types are registered via colcon build.
            self.get_logger().info(
                "BCVFTrustNode scaffold — waiting on §6.4 execution "
                "work to wire real pub/sub."
            )

    rclpy.init()
    try:
        node = _BCVFTrustNode()
        return node
    except Exception:
        rclpy.shutdown()
        raise


def main(args=None):  # pragma: no cover
    """Minimal entry point for ``ros2 run symbolu_bcvf_ros2 bcvf_trust``.

    Real implementation lands in §6.4 execution. For now this
    fails-fast with an informative error if ROS 2 is not installed,
    or prints a "scaffold — not yet wired" message if it is.
    """
    try:
        _require_rclpy()
    except ImportError as e:
        print(f"[bcvf_ros2] {e}", file=sys.stderr)
        sys.exit(1)

    import rclpy
    from ..bcvf_autonomous.core import BCVFConfig, CostOrder
    from .core import BCVFTrustBridgeConfig

    # Default bridge config — production integrators override via
    # ROS 2 node parameters (not yet wired).
    bridge_cfg = BCVFTrustBridgeConfig(
        bcvf_config=BCVFConfig(
            gate_threshold=0.05,
            gate_beta=400.0,
            huber_delta=0.5,
            use_anchor_pairing=False,
            cost_order=CostOrder.SECOND,
        ),
    )
    node = build_bcvf_trust_node(bridge_cfg)
    print("[bcvf_ros2] BCVFTrustNode scaffold instantiated. "
          "Real pub/sub pending §6.4 execution.")
    rclpy.spin(node)
    rclpy.shutdown()


if __name__ == "__main__":  # pragma: no cover
    main()
