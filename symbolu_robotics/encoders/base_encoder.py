"""
Base Encoder for Robotics
=========================

Abstract base class for all sensor-to-12D encoders.
Uses patent formulas S5 (entropy) and U1 (coherence).
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Dict, Optional, Tuple
import numpy as np

from symbolu_robotics.core.types import SensorFrame, Layer12D
from symbolu_robotics.core.ontology_12d import LAYER_NAMES


@dataclass
class EncoderConfig:
    """Configuration for sensor encoders."""
    normalize_output: bool = True
    temporal_smoothing: float = 0.0
    entropy_threshold: float = 0.8


@dataclass
class EncoderMetrics:
    """Metrics computed during encoding."""
    semantic_entropy: float = 0.0
    layer_coherence: float = 0.0
    encoding_confidence: float = 1.0
    active_layers: int = 0


class BaseEncoder(ABC):
    """Abstract base class for sensor-to-12D encoders."""

    def __init__(self, config: Optional[EncoderConfig] = None):
        self.config = config or EncoderConfig()
        self._prev_output: Optional[Layer12D] = None
        self._metrics = EncoderMetrics()

    @property
    @abstractmethod
    def encoder_name(self) -> str:
        pass

    @property
    @abstractmethod
    def required_sensors(self) -> Tuple[str, ...]:
        pass

    @abstractmethod
    def _encode_internal(self, sensor_frame: SensorFrame) -> Layer12D:
        pass

    def encode(self, sensor_frame: SensorFrame) -> Layer12D:
        """Encode sensor data to 12D layer activations."""
        raw_output = self._encode_internal(sensor_frame)

        if self.config.temporal_smoothing > 0 and self._prev_output is not None:
            alpha = self.config.temporal_smoothing
            raw_output = (1 - alpha) * self._prev_output + alpha * raw_output

        if self.config.normalize_output:
            max_val = np.max(np.abs(raw_output))
            if max_val > 0:
                raw_output = raw_output / max_val

        self._compute_metrics(raw_output)
        self._prev_output = raw_output.copy()
        return raw_output

    def _compute_metrics(self, layer_values: Layer12D) -> None:
        """Compute S5 entropy and coherence metrics."""
        abs_vals = np.abs(layer_values)
        total = np.sum(abs_vals)

        if total > 0:
            p = abs_vals / total
            p_safe = np.where(p > 0, p, 1)
            entropy = -np.sum(p * np.log(p_safe))
            self._metrics.semantic_entropy = float(entropy / np.log(12))
        else:
            self._metrics.semantic_entropy = 0.0

        coherence = 0.0
        for i in range(11):
            coherence += 1.0 - abs(layer_values[i] - layer_values[i+1])
        self._metrics.layer_coherence = coherence / 11.0
        self._metrics.active_layers = int(np.sum(layer_values > 0.1))
        self._metrics.encoding_confidence = (1.0 - self._metrics.semantic_entropy) * 0.5 + self._metrics.layer_coherence * 0.5

    @property
    def metrics(self) -> EncoderMetrics:
        return self._metrics

    def reset(self) -> None:
        self._prev_output = None
        self._metrics = EncoderMetrics()


class LightweightEncoder(BaseEncoder):
    """Minimal encoder for Tier R1 (Reflexive) - sub-millisecond response."""

    @property
    def encoder_name(self) -> str:
        return "lightweight"

    @property
    def required_sensors(self) -> Tuple[str, ...]:
        return ("proximity",)

    def _encode_internal(self, sensor_frame: SensorFrame) -> Layer12D:
        layer_values = np.zeros(12, dtype=np.float32)

        # O1_POTENTIAL: Sensor readiness
        layer_values[0] = 1.0 if sensor_frame.has_proprioception() else 0.0

        # O3_EXECUTION: Motion detection
        if sensor_frame.joints is not None:
            vel_norm = np.linalg.norm(sensor_frame.joints.velocities)
            layer_values[2] = min(1.0, vel_norm / 2.0)

        # O12_ABSOLVING: Obstacle proximity (safety)
        if sensor_frame.proximity_distances is not None:
            min_dist = np.min(sensor_frame.proximity_distances)
            layer_values[11] = max(0.0, 1.0 - min_dist / 1.0)

        if sensor_frame.human_detected:
            layer_values[11] = max(layer_values[11], 0.8)

        return layer_values
