"""
Locomotion Decoder for Robotics
================================

12D -> Gait parameters for mobile robots.

Layer Interpretation:
- O2_IDENTITY: Current position awareness
- O3_EXECUTION: Movement speed
- O7_REASONING: Path following
- O8_PURPOSE: Goal direction
- O12_ABSOLVING: Movement constraints
"""

from typing import Optional, Tuple
import numpy as np

from symbolu_robotics.decoders.base_decoder import BaseDecoder, DecoderConfig
from symbolu_robotics.core.types import ActuatorCommand, Layer12D


class LocomotionDecoder(BaseDecoder):
    """12D to base velocity decoding for mobile robots."""

    def __init__(
        self,
        config: Optional[DecoderConfig] = None,
        max_linear_speed: float = 1.0,      # m/s
        max_angular_speed: float = 1.5,     # rad/s
        goal_direction: Optional[float] = None  # radians
    ):
        super().__init__(config)
        self.max_linear_speed = max_linear_speed
        self.max_angular_speed = max_angular_speed
        self.goal_direction = goal_direction  # Can be updated dynamically

    @property
    def decoder_name(self) -> str:
        return "locomotion"

    def _decode_internal(self, layer_12d: Layer12D) -> ActuatorCommand:
        identity = layer_12d[1]       # O2_IDENTITY
        execution = layer_12d[2]      # O3_EXECUTION
        reasoning = layer_12d[6]      # O7_REASONING
        purpose = layer_12d[7]        # O8_PURPOSE
        safety = layer_12d[11]        # O12_ABSOLVING

        # Linear speed based on execution and purpose
        linear_speed = execution * purpose * self.max_linear_speed

        # Angular speed based on reasoning (path planning)
        # and purpose (goal seeking)
        if self.goal_direction is not None:
            # Turn toward goal
            angular_speed = reasoning * np.sign(self.goal_direction) * self.max_angular_speed
            angular_speed *= min(1.0, abs(self.goal_direction) / np.pi)
        else:
            # Exploratory turning based on reasoning
            angular_speed = (reasoning - 0.5) * 2 * self.max_angular_speed * 0.5

        # Safety reduction
        safety_scale = 1.0 - safety * 0.9

        return ActuatorCommand(
            base_linear_velocity=np.array([linear_speed * safety_scale, 0.0, 0.0]),
            base_angular_velocity=np.array([0.0, 0.0, angular_speed * safety_scale]),
            control_mode="velocity"
        )

    def set_goal_direction(self, direction: float) -> None:
        """Set goal direction in radians (-pi to pi)."""
        self.goal_direction = np.clip(direction, -np.pi, np.pi)

    def compute_velocity_from_goal(
        self,
        current_pose: Tuple[float, float, float],  # x, y, yaw
        goal_pose: Tuple[float, float]              # x, y
    ) -> Tuple[float, float]:
        """Compute velocities to reach goal."""
        dx = goal_pose[0] - current_pose[0]
        dy = goal_pose[1] - current_pose[1]

        # Distance to goal
        distance = np.sqrt(dx**2 + dy**2)

        # Angle to goal
        goal_angle = np.arctan2(dy, dx)
        angle_error = goal_angle - current_pose[2]

        # Normalize angle
        while angle_error > np.pi:
            angle_error -= 2 * np.pi
        while angle_error < -np.pi:
            angle_error += 2 * np.pi

        self.goal_direction = angle_error

        return distance, angle_error
