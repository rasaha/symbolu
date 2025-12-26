"""
ROS Bridge for Robotics
========================

Bridge between Symbolu Robotics and ROS2 ecosystem.

Note: Requires rclpy to be installed for actual ROS2 integration.
This module provides the interface and can run in simulation mode.
"""

from dataclasses import dataclass
from typing import Optional, Callable, Dict, Any, List
import time


@dataclass
class ROSMessage:
    """Generic ROS message container."""
    topic: str
    msg_type: str
    data: Dict[str, Any]
    timestamp: float = 0.0


class ROSBridge:
    """
    Bridge to ROS2 for hardware integration.

    Can run in simulation mode without ROS2.
    """

    def __init__(
        self,
        node_name: str = "symbolu_robotics",
        simulation_mode: bool = True
    ):
        self.node_name = node_name
        self.simulation_mode = simulation_mode

        self._subscribers: Dict[str, Callable] = {}
        self._publishers: Dict[str, Any] = {}
        self._message_queue: List[ROSMessage] = []

        # ROS2 node (if available)
        self._node = None

        if not simulation_mode:
            self._init_ros2()

    def _init_ros2(self) -> None:
        """Initialize ROS2 node."""
        try:
            import rclpy
            from rclpy.node import Node

            if not rclpy.ok():
                rclpy.init()

            class SymboluNode(Node):
                def __init__(self, name):
                    super().__init__(name)

            self._node = SymboluNode(self.node_name)

        except ImportError:
            print("ROS2 not available, running in simulation mode")
            self.simulation_mode = True

    def subscribe(
        self,
        topic: str,
        msg_type: str,
        callback: Callable[[ROSMessage], None]
    ) -> None:
        """
        Subscribe to a ROS topic.

        Args:
            topic: Topic name (e.g., "/joint_states")
            msg_type: Message type (e.g., "sensor_msgs/JointState")
            callback: Callback function for received messages
        """
        self._subscribers[topic] = callback

        if not self.simulation_mode and self._node:
            # Create actual ROS2 subscription
            try:
                from sensor_msgs.msg import JointState, Image
                from geometry_msgs.msg import Twist, Pose

                # Map common message types
                type_map = {
                    "sensor_msgs/JointState": JointState,
                    "geometry_msgs/Twist": Twist,
                    "geometry_msgs/Pose": Pose,
                }

                if msg_type in type_map:
                    ros_type = type_map[msg_type]
                    self._node.create_subscription(
                        ros_type,
                        topic,
                        lambda msg: self._ros_callback(topic, msg),
                        10
                    )
            except ImportError:
                pass

    def _ros_callback(self, topic: str, msg: Any) -> None:
        """Internal ROS callback."""
        # Convert ROS message to ROSMessage
        data = {}
        for field in msg.get_fields_and_field_types().keys():
            data[field] = getattr(msg, field)

        ros_msg = ROSMessage(
            topic=topic,
            msg_type=type(msg).__name__,
            data=data,
            timestamp=time.time()
        )

        # Call user callback
        if topic in self._subscribers:
            self._subscribers[topic](ros_msg)

    def publish(
        self,
        topic: str,
        msg_type: str,
        data: Dict[str, Any]
    ) -> None:
        """
        Publish to a ROS topic.

        Args:
            topic: Topic name
            msg_type: Message type
            data: Message data
        """
        msg = ROSMessage(
            topic=topic,
            msg_type=msg_type,
            data=data,
            timestamp=time.time()
        )

        if self.simulation_mode:
            # Store in queue for simulation
            self._message_queue.append(msg)
        else:
            self._publish_ros2(topic, msg_type, data)

    def _publish_ros2(self, topic: str, msg_type: str, data: Dict) -> None:
        """Publish to actual ROS2 topic."""
        if not self._node:
            return

        try:
            from trajectory_msgs.msg import JointTrajectory, JointTrajectoryPoint
            from geometry_msgs.msg import Twist

            if topic not in self._publishers:
                # Create publisher
                type_map = {
                    "trajectory_msgs/JointTrajectory": JointTrajectory,
                    "geometry_msgs/Twist": Twist,
                }
                if msg_type in type_map:
                    self._publishers[topic] = self._node.create_publisher(
                        type_map[msg_type], topic, 10
                    )

            if topic in self._publishers:
                # Create and publish message
                pub = self._publishers[topic]
                if msg_type == "geometry_msgs/Twist":
                    msg = Twist()
                    if "linear" in data:
                        msg.linear.x = data["linear"][0]
                        msg.linear.y = data["linear"][1]
                        msg.linear.z = data["linear"][2]
                    if "angular" in data:
                        msg.angular.x = data["angular"][0]
                        msg.angular.y = data["angular"][1]
                        msg.angular.z = data["angular"][2]
                    pub.publish(msg)

        except ImportError:
            pass

    def spin_once(self, timeout_sec: float = 0.01) -> None:
        """Process ROS callbacks once."""
        if not self.simulation_mode and self._node:
            try:
                import rclpy
                rclpy.spin_once(self._node, timeout_sec=timeout_sec)
            except:
                pass

    # Convenience methods for common topics

    def publish_cmd_vel(
        self,
        linear: tuple = (0, 0, 0),
        angular: tuple = (0, 0, 0)
    ) -> None:
        """Publish velocity command."""
        self.publish(
            "/cmd_vel",
            "geometry_msgs/Twist",
            {"linear": list(linear), "angular": list(angular)}
        )

    def publish_joint_trajectory(
        self,
        positions: list,
        velocities: list = None,
        duration: float = 1.0
    ) -> None:
        """Publish joint trajectory."""
        self.publish(
            "/joint_trajectory_controller/command",
            "trajectory_msgs/JointTrajectory",
            {
                "positions": positions,
                "velocities": velocities or [0] * len(positions),
                "duration": duration
            }
        )

    # Simulation helpers

    def simulate_sensor_data(
        self,
        topic: str,
        data: Dict[str, Any]
    ) -> None:
        """Simulate incoming sensor data (for testing)."""
        if topic in self._subscribers:
            msg = ROSMessage(
                topic=topic,
                msg_type="simulated",
                data=data,
                timestamp=time.time()
            )
            self._subscribers[topic](msg)

    def get_published_messages(self) -> List[ROSMessage]:
        """Get messages published in simulation mode."""
        msgs = self._message_queue.copy()
        self._message_queue.clear()
        return msgs

    def shutdown(self) -> None:
        """Shutdown ROS node."""
        if self._node:
            try:
                self._node.destroy_node()
            except:
                pass
