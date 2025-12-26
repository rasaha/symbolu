"""
Base Decoder for Robotics
=========================

Abstract base class for all 12D-to-actuator decoders.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Optional
import numpy as np

from symbolu_robotics.core.types import ActuatorCommand, Layer12D


@dataclass
class DecoderConfig:
    """Configuration for actuator decoders."""
    safety_scaling: bool = True       # Scale output by O12_ABSOLVING
    smoothing_alpha: float = 0.0      # Temporal smoothing (0 = none)
    max_velocity: float = 2.0         # rad/s
    max_acceleration: float = 5.0     # rad/s^2


class BaseDecoder(ABC):
    """Abstract base class for 12D-to-actuator decoders."""

    def __init__(self, config: Optional[DecoderConfig] = None):
        self.config = config or DecoderConfig()
        self._prev_command: Optional[ActuatorCommand] = None

    @property
    @abstractmethod
    def decoder_name(self) -> str:
        pass

    @abstractmethod
    def _decode_internal(self, layer_12d: Layer12D) -> ActuatorCommand:
        """Internal decoding implementation."""
        pass

    def decode(self, layer_12d: Layer12D) -> ActuatorCommand:
        """
        Decode 12D layers to actuator command.

        Applies:
        1. Internal decoding
        2. Safety scaling (O12_ABSOLVING)
        3. Temporal smoothing
        """
        command = self._decode_internal(layer_12d)

        # Safety scaling: reduce command magnitude based on O12_ABSOLVING
        if self.config.safety_scaling:
            safety_level = layer_12d[11]  # O12_ABSOLVING
            scale = 1.0 - safety_level * 0.9  # Max 90% reduction
            command = self._scale_command(command, scale)

        # Temporal smoothing
        if self.config.smoothing_alpha > 0 and self._prev_command is not None:
            command = self._smooth_command(command, self._prev_command)

        self._prev_command = command
        return command

    def _scale_command(self, cmd: ActuatorCommand, scale: float) -> ActuatorCommand:
        """Scale command velocities/efforts by a factor."""
        if cmd.target_velocities is not None:
            cmd.target_velocities = cmd.target_velocities * scale
        if cmd.target_efforts is not None:
            cmd.target_efforts = cmd.target_efforts * scale
        if cmd.base_linear_velocity is not None:
            cmd.base_linear_velocity = cmd.base_linear_velocity * scale
        if cmd.base_angular_velocity is not None:
            cmd.base_angular_velocity = cmd.base_angular_velocity * scale
        cmd.safety_limited = scale < 1.0
        return cmd

    def _smooth_command(self, cmd: ActuatorCommand, prev: ActuatorCommand) -> ActuatorCommand:
        """Apply temporal smoothing between commands."""
        alpha = self.config.smoothing_alpha

        if cmd.target_velocities is not None and prev.target_velocities is not None:
            cmd.target_velocities = (1 - alpha) * prev.target_velocities + alpha * cmd.target_velocities
        if cmd.target_positions is not None and prev.target_positions is not None:
            cmd.target_positions = (1 - alpha) * prev.target_positions + alpha * cmd.target_positions

        return cmd

    def reset(self) -> None:
        """Reset decoder state."""
        self._prev_command = None
