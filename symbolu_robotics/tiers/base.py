"""
Base Tier for Robotics
======================

Abstract base class for all robotics tiers.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Optional, Tuple
import time

from symbolu_robotics.core.types import SensorFrame, ActuatorCommand, Layer12D, Plan


@dataclass
class TierConfig:
    """Configuration for robotics tiers."""
    max_latency_ms: float = 100.0
    enable_safety: bool = True
    enable_logging: bool = False


@dataclass
class TierMetrics:
    """Metrics from tier execution."""
    latency_ms: float = 0.0
    safety_applied: bool = False
    layer_12d: Optional[Layer12D] = None


class BaseTier(ABC):
    """
    Abstract base class for robotics control tiers.

    All tiers implement the step() method for control loop execution.
    """

    def __init__(self, config: Optional[TierConfig] = None):
        self.config = config or TierConfig()
        self._metrics = TierMetrics()

    @property
    @abstractmethod
    def tier_name(self) -> str:
        """Return the tier name."""
        pass

    @property
    @abstractmethod
    def target_latency_ms(self) -> float:
        """Return target latency in milliseconds."""
        pass

    @abstractmethod
    def step(self, sensor_frame: SensorFrame) -> ActuatorCommand:
        """
        Execute one control loop step.

        Args:
            sensor_frame: Current sensor data

        Returns:
            Actuator command to execute
        """
        pass

    def step_timed(self, sensor_frame: SensorFrame) -> Tuple[ActuatorCommand, TierMetrics]:
        """
        Execute step with timing measurement.

        Returns:
            Tuple of (command, metrics)
        """
        start = time.perf_counter()
        command = self.step(sensor_frame)
        elapsed_ms = (time.perf_counter() - start) * 1000

        self._metrics.latency_ms = elapsed_ms
        return command, self._metrics

    def check_latency(self) -> bool:
        """Check if last step met latency target."""
        return self._metrics.latency_ms <= self.target_latency_ms

    @property
    def metrics(self) -> TierMetrics:
        return self._metrics

    def reset(self) -> None:
        """Reset tier state."""
        self._metrics = TierMetrics()
