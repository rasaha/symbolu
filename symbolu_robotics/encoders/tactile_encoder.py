"""
Tactile Encoder for Robotics
=============================

Touch sensors -> 12D encoding.

Layer Mapping:
- Contact forces -> O3_EXECUTION (interaction)
- Contact locations -> O4_STRUCTURE (geometry)
- Force distribution -> O5_COGNITION (sensing)
- Slip detection -> O12_ABSOLVING (safety)
"""

from typing import Tuple, Optional
import numpy as np

from symbolu_robotics.encoders.base_encoder import BaseEncoder, EncoderConfig
from symbolu_robotics.core.types import SensorFrame, Layer12D


class TactileEncoder(BaseEncoder):
    """Touch sensor to 12D layer encoding."""

    def __init__(
        self,
        config: Optional[EncoderConfig] = None,
        force_threshold: float = 1.0,
        max_force: float = 50.0,
        slip_threshold: float = 0.5
    ):
        super().__init__(config)
        self.force_threshold = force_threshold
        self.max_force = max_force
        self.slip_threshold = slip_threshold
        self._prev_forces: Optional[np.ndarray] = None

    @property
    def encoder_name(self) -> str:
        return "tactile"

    @property
    def required_sensors(self) -> Tuple[str, ...]:
        return ("contact_forces",)

    def _encode_internal(self, sensor_frame: SensorFrame) -> Layer12D:
        layer_values = np.zeros(12, dtype=np.float32)

        if sensor_frame.contact_forces is None:
            return layer_values

        forces = sensor_frame.contact_forces  # Shape: (N, 3)
        if len(forces) == 0:
            return layer_values

        # O1_POTENTIAL: Contact detected
        total_force = np.sum(np.linalg.norm(forces, axis=1))
        if total_force > self.force_threshold:
            layer_values[0] = 1.0

        # O3_EXECUTION: Interaction intensity
        layer_values[2] = min(1.0, total_force / self.max_force)

        # O4_STRUCTURE: Contact geometry (if locations available)
        if sensor_frame.contact_points is not None:
            points = sensor_frame.contact_points
            if len(points) > 1:
                spread = np.std(points, axis=0)
                layer_values[3] = min(1.0, np.mean(spread))

        # O5_COGNITION: Force distribution entropy
        force_mags = np.linalg.norm(forces, axis=1)
        if np.sum(force_mags) > 0:
            p = force_mags / np.sum(force_mags)
            p_safe = np.where(p > 0, p, 1)
            entropy = -np.sum(p * np.log(p_safe))
            max_entropy = np.log(len(forces)) if len(forces) > 1 else 1.0
            layer_values[4] = entropy / max_entropy

        # O12_ABSOLVING: Slip detection (force change rate)
        if self._prev_forces is not None and len(self._prev_forces) == len(forces):
            force_change = np.mean(np.abs(forces - self._prev_forces))
            if force_change > self.slip_threshold:
                layer_values[11] = min(1.0, force_change / (self.slip_threshold * 2))

        self._prev_forces = forces.copy()
        return layer_values

    def reset(self) -> None:
        super().reset()
        self._prev_forces = None
