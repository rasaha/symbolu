"""
Proprioception Encoder for Robotics
=====================================

Joint states -> 12D encoding.

Layer Mapping:
- Joint positions -> O4_STRUCTURE (body schema)
- Joint velocities -> O3_EXECUTION (motion state)
- Joint torques -> O6_AGENCY (effort level)
- End-effector pose -> O2_IDENTITY (self-localization)
"""

from typing import Tuple, Optional
import numpy as np

from symbolu_robotics.encoders.base_encoder import BaseEncoder, EncoderConfig
from symbolu_robotics.core.types import SensorFrame, Layer12D, JointState


class ProprioceptionEncoder(BaseEncoder):
    """Joint state to 12D layer encoding."""

    def __init__(
        self,
        config: Optional[EncoderConfig] = None,
        home_position: Optional[np.ndarray] = None,
        joint_limits: Optional[Tuple[np.ndarray, np.ndarray]] = None,
        velocity_limit: float = 3.0,
        effort_limit: float = 100.0
    ):
        super().__init__(config)
        self.home_position = home_position
        self.joint_limits = joint_limits
        self.velocity_limit = velocity_limit
        self.effort_limit = effort_limit

    @property
    def encoder_name(self) -> str:
        return "proprioception"

    @property
    def required_sensors(self) -> Tuple[str, ...]:
        return ("joints",)

    def _encode_internal(self, sensor_frame: SensorFrame) -> Layer12D:
        layer_values = np.zeros(12, dtype=np.float32)

        if sensor_frame.joints is None:
            return layer_values

        joints = sensor_frame.joints

        # O1_POTENTIAL: Sensor readiness
        layer_values[0] = 1.0

        # O2_IDENTITY: Self-localization via end-effector
        if sensor_frame.base_pose is not None:
            pose = sensor_frame.base_pose
            # Normalize position magnitude
            pos_mag = np.sqrt(pose.x**2 + pose.y**2 + pose.z**2)
            layer_values[1] = min(1.0, pos_mag / 10.0)

        # O3_EXECUTION: Motion state (velocity norm)
        if joints.velocities is not None:
            vel_norm = np.linalg.norm(joints.velocities)
            layer_values[2] = min(1.0, vel_norm / self.velocity_limit)

        # O4_STRUCTURE: Pose deviation from home
        if self.home_position is not None and joints.positions is not None:
            deviation = np.linalg.norm(joints.positions - self.home_position)
            layer_values[3] = min(1.0, deviation / np.pi)  # Normalize by pi
        else:
            # Default: use position magnitude
            if joints.positions is not None:
                layer_values[3] = min(1.0, np.linalg.norm(joints.positions) / (np.pi * 2))

        # O6_AGENCY: Effort level
        if joints.efforts is not None:
            effort_norm = np.linalg.norm(joints.efforts)
            layer_values[5] = min(1.0, effort_norm / self.effort_limit)

        # O12_ABSOLVING: Joint limit proximity
        if self.joint_limits is not None and joints.positions is not None:
            lower, upper = self.joint_limits
            margin_lower = joints.positions - lower
            margin_upper = upper - joints.positions
            min_margin = min(np.min(margin_lower), np.min(margin_upper))
            # Closer to limit = higher constraint
            layer_values[11] = max(0.0, 1.0 - min_margin / 0.5)

        return layer_values

    def compute_manipulability(self, jacobian: np.ndarray) -> float:
        """Compute Yoshikawa manipulability measure."""
        if jacobian is None:
            return 0.0
        try:
            det = np.linalg.det(jacobian @ jacobian.T)
            return np.sqrt(max(0, det))
        except:
            return 0.0
