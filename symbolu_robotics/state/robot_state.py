"""
Robot State for Robotics
=========================

Full robot state vector with estimation.
"""

from dataclasses import dataclass, field
from typing import Optional, Dict, Any
import numpy as np
import time

from symbolu_robotics.core.types import RobotPose, JointState, Layer12D


@dataclass
class RobotState:
    """
    Complete robot state at a moment in time.

    Combines:
    - Kinematic state (pose, joints)
    - Dynamic state (velocities, forces)
    - Ontological state (12D layers)
    """
    # Timestamp
    timestamp: float = 0.0

    # Base pose
    base_pose: RobotPose = field(default_factory=RobotPose)

    # Joint state
    joints: JointState = field(default_factory=JointState)

    # Base velocities
    linear_velocity: np.ndarray = field(default_factory=lambda: np.zeros(3))
    angular_velocity: np.ndarray = field(default_factory=lambda: np.zeros(3))

    # 12D ontological state
    layer_12d: Layer12D = field(default_factory=lambda: np.zeros(12, dtype=np.float32))

    # Confidence/uncertainty
    position_covariance: Optional[np.ndarray] = None
    joint_covariance: Optional[np.ndarray] = None

    # Flags
    is_valid: bool = True
    is_moving: bool = False

    def to_dict(self) -> Dict[str, Any]:
        return {
            "timestamp": self.timestamp,
            "base_pose": {
                "x": self.base_pose.x,
                "y": self.base_pose.y,
                "z": self.base_pose.z,
                "roll": self.base_pose.roll,
                "pitch": self.base_pose.pitch,
                "yaw": self.base_pose.yaw,
            },
            "joints": self.joints.to_dict(),
            "linear_velocity": self.linear_velocity.tolist(),
            "angular_velocity": self.angular_velocity.tolist(),
            "layer_12d": self.layer_12d.tolist(),
            "is_valid": self.is_valid,
            "is_moving": self.is_moving,
        }


class RobotStateEstimator:
    """
    State estimator using sensor fusion.

    Combines proprioception, vision, and IMU.
    """

    def __init__(
        self,
        num_joints: int = 6,
        alpha_position: float = 0.3,
        alpha_velocity: float = 0.1
    ):
        self.num_joints = num_joints
        self.alpha_position = alpha_position
        self.alpha_velocity = alpha_velocity

        self._current_state = RobotState(
            joints=JointState(
                positions=np.zeros(num_joints),
                velocities=np.zeros(num_joints),
                efforts=np.zeros(num_joints)
            )
        )
        self._prev_timestamp = 0.0

    @property
    def current_state(self) -> RobotState:
        return self._current_state

    def update(
        self,
        joint_positions: Optional[np.ndarray] = None,
        joint_velocities: Optional[np.ndarray] = None,
        joint_efforts: Optional[np.ndarray] = None,
        base_pose: Optional[RobotPose] = None,
        imu_linear_accel: Optional[np.ndarray] = None,
        imu_angular_vel: Optional[np.ndarray] = None,
        layer_12d: Optional[Layer12D] = None,
        timestamp: Optional[float] = None
    ) -> RobotState:
        """
        Update state estimate with new sensor data.

        Uses EMA for smooth updates.
        """
        if timestamp is None:
            timestamp = time.time()

        dt = timestamp - self._prev_timestamp if self._prev_timestamp > 0 else 0.01
        self._prev_timestamp = timestamp

        new_state = RobotState(timestamp=timestamp)

        # Update joints with EMA
        if joint_positions is not None:
            new_state.joints.positions = (
                (1 - self.alpha_position) * self._current_state.joints.positions +
                self.alpha_position * joint_positions
            )
        else:
            new_state.joints.positions = self._current_state.joints.positions

        if joint_velocities is not None:
            new_state.joints.velocities = (
                (1 - self.alpha_velocity) * self._current_state.joints.velocities +
                self.alpha_velocity * joint_velocities
            )
        else:
            new_state.joints.velocities = self._current_state.joints.velocities

        if joint_efforts is not None:
            new_state.joints.efforts = joint_efforts

        # Update base pose
        if base_pose is not None:
            new_state.base_pose = base_pose
        else:
            new_state.base_pose = self._current_state.base_pose

        # Update velocities from IMU
        if imu_angular_vel is not None:
            new_state.angular_velocity = (
                (1 - self.alpha_velocity) * self._current_state.angular_velocity +
                self.alpha_velocity * imu_angular_vel
            )

        if imu_linear_accel is not None:
            # Simple integration (in practice, use proper sensor fusion)
            new_state.linear_velocity = (
                self._current_state.linear_velocity +
                imu_linear_accel * dt
            )

        # Update 12D state
        if layer_12d is not None:
            new_state.layer_12d = layer_12d

        # Check if moving
        vel_norm = np.linalg.norm(new_state.joints.velocities)
        new_state.is_moving = vel_norm > 0.01

        self._current_state = new_state
        return new_state

    def predict(self, dt: float) -> RobotState:
        """
        Predict state at future time.

        Simple constant-velocity model.
        """
        predicted = RobotState(
            timestamp=self._current_state.timestamp + dt
        )

        # Predict joint positions
        predicted.joints.positions = (
            self._current_state.joints.positions +
            self._current_state.joints.velocities * dt
        )
        predicted.joints.velocities = self._current_state.joints.velocities

        # Predict base pose
        predicted.base_pose = RobotPose(
            x=self._current_state.base_pose.x + self._current_state.linear_velocity[0] * dt,
            y=self._current_state.base_pose.y + self._current_state.linear_velocity[1] * dt,
            z=self._current_state.base_pose.z + self._current_state.linear_velocity[2] * dt,
            roll=self._current_state.base_pose.roll,
            pitch=self._current_state.base_pose.pitch,
            yaw=self._current_state.base_pose.yaw + self._current_state.angular_velocity[2] * dt,
        )

        return predicted

    def reset(self) -> None:
        """Reset estimator state."""
        self._current_state = RobotState(
            joints=JointState(
                positions=np.zeros(self.num_joints),
                velocities=np.zeros(self.num_joints),
                efforts=np.zeros(self.num_joints)
            )
        )
        self._prev_timestamp = 0.0
