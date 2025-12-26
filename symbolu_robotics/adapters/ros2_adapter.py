"""
ROS2 Adapter for Robotics
==========================

Integration with ROS2 ecosystem.
"""

from typing import Optional
import numpy as np

from symbolu_robotics.adapters.base_adapter import BaseAdapter, AdapterConfig
from symbolu_robotics.core.types import SensorFrame, ActuatorCommand, JointState, RobotPose
from symbolu_robotics.comms.ros_bridge import ROSBridge


class ROS2Adapter(BaseAdapter):
    """
    Adapter for ROS2-based robots.

    Subscribes to standard ROS2 topics and publishes commands.
    """

    def __init__(
        self,
        config: Optional[AdapterConfig] = None,
        node_name: str = "symbolu_robotics",
        simulation: bool = True
    ):
        super().__init__(config)
        self.node_name = node_name
        self.simulation = simulation

        self._bridge: Optional[ROSBridge] = None
        self._last_sensor_frame = SensorFrame()

    @property
    def adapter_name(self) -> str:
        return "ros2"

    def connect(self) -> bool:
        """Initialize ROS2 node and subscriptions."""
        try:
            self._bridge = ROSBridge(
                node_name=self.node_name,
                simulation_mode=self.simulation
            )

            # Subscribe to sensor topics
            self._bridge.subscribe(
                "/joint_states",
                "sensor_msgs/JointState",
                self._on_joint_state
            )

            self._bridge.subscribe(
                "/odom",
                "nav_msgs/Odometry",
                self._on_odometry
            )

            self._connected = True
            return True

        except Exception as e:
            print(f"ROS2 connection failed: {e}")
            return False

    def disconnect(self) -> None:
        """Shutdown ROS2 node."""
        if self._bridge:
            self._bridge.shutdown()
        self._connected = False

    def _on_joint_state(self, msg) -> None:
        """Handle joint state message."""
        self._last_sensor_frame.joints = JointState(
            positions=np.array(msg.data.get("position", [])),
            velocities=np.array(msg.data.get("velocity", [])),
            efforts=np.array(msg.data.get("effort", []))
        )

    def _on_odometry(self, msg) -> None:
        """Handle odometry message."""
        pose = msg.data.get("pose", {}).get("pose", {})
        pos = pose.get("position", {})
        ori = pose.get("orientation", {})

        self._last_sensor_frame.base_pose = RobotPose(
            x=pos.get("x", 0),
            y=pos.get("y", 0),
            z=pos.get("z", 0),
            # Quaternion to Euler would go here
        )

    def read_sensors(self) -> SensorFrame:
        """Read latest sensor data."""
        if self._bridge:
            self._bridge.spin_once()
        return self._last_sensor_frame

    def send_command(self, command: ActuatorCommand) -> bool:
        """Send command to robot."""
        if not self._bridge or not self._connected:
            return False

        if command.emergency_stop:
            self._bridge.publish_cmd_vel((0, 0, 0), (0, 0, 0))
            return True

        if command.target_velocities is not None:
            self._bridge.publish_joint_trajectory(
                positions=command.target_positions.tolist() if command.target_positions is not None else [],
                velocities=command.target_velocities.tolist()
            )

        if command.base_linear_velocity is not None:
            self._bridge.publish_cmd_vel(
                linear=tuple(command.base_linear_velocity),
                angular=tuple(command.base_angular_velocity or [0, 0, 0])
            )

        return True
