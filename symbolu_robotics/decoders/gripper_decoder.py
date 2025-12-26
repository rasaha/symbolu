"""
Gripper Decoder for Robotics
=============================

12D -> Grasp commands.

Layer Interpretation:
- O3_EXECUTION: Grip action intensity
- O5_COGNITION: Object detection confidence
- O6_AGENCY: Grasp/release selection
- O12_ABSOLVING: Force limits
"""

from typing import Optional
import numpy as np

from symbolu_robotics.decoders.base_decoder import BaseDecoder, DecoderConfig
from symbolu_robotics.core.types import ActuatorCommand, Layer12D


class GripperDecoder(BaseDecoder):
    """12D to gripper command decoding."""

    def __init__(
        self,
        config: Optional[DecoderConfig] = None,
        max_force: float = 40.0,
        min_position: float = 0.0,
        max_position: float = 1.0
    ):
        super().__init__(config)
        self.max_force = max_force
        self.min_position = min_position
        self.max_position = max_position
        self._current_position: float = max_position  # Start open

    @property
    def decoder_name(self) -> str:
        return "gripper"

    def _decode_internal(self, layer_12d: Layer12D) -> ActuatorCommand:
        execution = layer_12d[2]      # O3_EXECUTION
        cognition = layer_12d[4]      # O5_COGNITION
        agency = layer_12d[5]         # O6_AGENCY
        safety = layer_12d[11]        # O12_ABSOLVING

        # Determine grasp/release action
        # High agency + high execution = grasp
        # Low agency + high execution = release
        grasp_intent = agency * execution

        if grasp_intent > 0.5:
            # Grasp: close gripper
            target_position = self.min_position + (1 - grasp_intent) * 0.3
            # Force based on cognition (object confidence) and safety
            target_force = self.max_force * cognition * (1 - safety * 0.8)
        else:
            # Release: open gripper
            release_speed = execution * (1 - agency)
            target_position = self.max_position
            target_force = self.max_force * 0.1  # Minimal force

        # Smooth position transition
        alpha = 0.3
        self._current_position = (1 - alpha) * self._current_position + alpha * target_position

        return ActuatorCommand(
            gripper_position=float(np.clip(self._current_position, self.min_position, self.max_position)),
            gripper_force=float(np.clip(target_force, 0, self.max_force))
        )

    def reset(self) -> None:
        super().reset()
        self._current_position = self.max_position
