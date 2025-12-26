"""
Motor Decoder for Robotics
===========================

12D -> Joint torques/velocities.

Layer Interpretation:
- O3_EXECUTION: Motion intensity
- O4_STRUCTURE: Target configuration
- O6_AGENCY: Control mode selection
- O12_ABSOLVING: Safety constraints
"""

from typing import Optional
import numpy as np

from symbolu_robotics.decoders.base_decoder import BaseDecoder, DecoderConfig
from symbolu_robotics.core.types import ActuatorCommand, Layer12D


class MotorDecoder(BaseDecoder):
    """12D to joint command decoding."""

    def __init__(
        self,
        config: Optional[DecoderConfig] = None,
        num_joints: int = 6,
        home_position: Optional[np.ndarray] = None,
        joint_mapping: Optional[np.ndarray] = None
    ):
        super().__init__(config)
        self.num_joints = num_joints
        self.home_position = home_position if home_position is not None else np.zeros(num_joints)

        # Optional: learned mapping from 12D to joints
        # Shape: (num_joints, 12) - projects 12D to joint space
        if joint_mapping is not None:
            self.joint_mapping = joint_mapping
        else:
            # Default: use O3_EXECUTION and O4_STRUCTURE primarily
            self.joint_mapping = np.zeros((num_joints, 12))
            # O3 drives velocity, O4 drives position
            for i in range(num_joints):
                self.joint_mapping[i, 2] = 1.0 / num_joints  # O3_EXECUTION
                self.joint_mapping[i, 3] = 0.5 / num_joints  # O4_STRUCTURE

    @property
    def decoder_name(self) -> str:
        return "motor"

    def _decode_internal(self, layer_12d: Layer12D) -> ActuatorCommand:
        # Extract key layers
        execution = layer_12d[2]      # O3_EXECUTION: motion intensity
        structure = layer_12d[3]      # O4_STRUCTURE: configuration
        agency = layer_12d[5]         # O6_AGENCY: control mode

        # Determine control mode based on agency
        if agency < 0.3:
            # Low agency: position control toward home
            target_positions = self.home_position.copy()
            return ActuatorCommand(
                target_positions=target_positions,
                control_mode="position"
            )

        elif agency < 0.7:
            # Medium agency: velocity control
            # Project 12D to joint velocities
            base_velocities = self.joint_mapping @ layer_12d
            # Scale by execution intensity
            velocities = base_velocities * execution * self.config.max_velocity

            return ActuatorCommand(
                target_velocities=velocities,
                control_mode="velocity"
            )

        else:
            # High agency: effort/torque control
            # More direct mapping for compliant behavior
            base_efforts = self.joint_mapping @ layer_12d
            efforts = base_efforts * execution * 10.0  # Scale to Nm

            return ActuatorCommand(
                target_efforts=efforts,
                control_mode="effort"
            )

    def set_joint_mapping(self, mapping: np.ndarray) -> None:
        """Set learned joint mapping matrix."""
        if mapping.shape != (self.num_joints, 12):
            raise ValueError(f"Expected shape ({self.num_joints}, 12), got {mapping.shape}")
        self.joint_mapping = mapping
