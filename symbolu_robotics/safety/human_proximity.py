"""
Human Proximity Monitor for Robotics
=====================================

ISO/TS 15066 compliant human-robot safety.

Implements speed and separation monitoring (SSM).
"""

from dataclasses import dataclass
from typing import Optional, Tuple, List
import numpy as np

from symbolu_robotics.core.types import SensorFrame, ActuatorCommand, SafetyLevel


@dataclass
class HumanSafetyConfig:
    """Configuration for human-robot safety."""
    # Distance thresholds (meters)
    stop_distance: float = 0.3           # Full stop
    reduced_speed_distance: float = 1.0   # Reduced speed zone
    monitoring_distance: float = 2.0      # Active monitoring zone

    # Speed limits (m/s)
    max_speed_near_human: float = 0.25   # ISO/TS 15066 limit
    reduced_speed: float = 0.5

    # Force limits (N)
    max_contact_force: float = 140.0     # ISO/TS 15066 transient
    max_static_force: float = 65.0       # ISO/TS 15066 quasi-static


class HumanProximityMonitor:
    """
    Human-robot safety monitoring per ISO/TS 15066.

    Implements speed and separation monitoring (SSM).
    """

    def __init__(self, config: Optional[HumanSafetyConfig] = None):
        self.config = config or HumanSafetyConfig()
        self._humans_detected: List[Tuple[np.ndarray, float]] = []  # (position, distance)
        self._closest_human_distance = float('inf')
        self._safety_level = SafetyLevel.NOMINAL

    def update(self, sensor_frame: SensorFrame) -> None:
        """Update human detection from sensors."""
        self._humans_detected = []
        self._closest_human_distance = float('inf')

        # Primary: dedicated human detection flag
        if sensor_frame.human_detected:
            if sensor_frame.human_distance is not None:
                self._closest_human_distance = sensor_frame.human_distance
                self._humans_detected.append((np.array([0, 0, 0]), sensor_frame.human_distance))

        # Secondary: estimate from proximity sensors (conservative)
        if sensor_frame.proximity_distances is not None:
            min_prox = np.min(sensor_frame.proximity_distances)
            if min_prox < self.config.monitoring_distance:
                # Assume it could be human (conservative)
                if min_prox < self._closest_human_distance:
                    self._closest_human_distance = min_prox

        # Update safety level
        self._update_safety_level()

    def _update_safety_level(self) -> None:
        """Update safety level based on proximity."""
        d = self._closest_human_distance

        if d <= self.config.stop_distance:
            self._safety_level = SafetyLevel.EMERGENCY_STOP
        elif d <= self.config.reduced_speed_distance:
            self._safety_level = SafetyLevel.RESTRICTED
        elif d <= self.config.monitoring_distance:
            self._safety_level = SafetyLevel.CAUTION
        else:
            self._safety_level = SafetyLevel.NOMINAL

    @property
    def safety_level(self) -> SafetyLevel:
        return self._safety_level

    @property
    def human_detected(self) -> bool:
        return len(self._humans_detected) > 0

    @property
    def closest_distance(self) -> float:
        return self._closest_human_distance

    def get_constraint_level(self) -> float:
        """Get O12_ABSOLVING constraint level for human proximity."""
        if self._closest_human_distance >= self.config.monitoring_distance:
            return 0.0

        if self._closest_human_distance <= self.config.stop_distance:
            return 1.0

        # Linear interpolation
        range_size = self.config.monitoring_distance - self.config.stop_distance
        return 1.0 - (self._closest_human_distance - self.config.stop_distance) / range_size

    def get_max_allowed_speed(self) -> float:
        """Get maximum allowed robot speed based on human proximity."""
        if self._safety_level == SafetyLevel.EMERGENCY_STOP:
            return 0.0
        elif self._safety_level == SafetyLevel.RESTRICTED:
            return self.config.max_speed_near_human
        elif self._safety_level == SafetyLevel.CAUTION:
            return self.config.reduced_speed
        else:
            return float('inf')  # No limit

    def constrain_command(self, command: ActuatorCommand) -> ActuatorCommand:
        """
        Apply human-aware constraints to command.

        Args:
            command: Input actuator command

        Returns:
            Constrained command
        """
        max_speed = self.get_max_allowed_speed()

        if max_speed == 0.0:
            return ActuatorCommand(emergency_stop=True)

        # Scale velocities to not exceed max speed
        if command.target_velocities is not None:
            speed = np.max(np.abs(command.target_velocities))
            if speed > max_speed:
                scale = max_speed / speed
                command.target_velocities = command.target_velocities * scale
                command.safety_limited = True

        if command.base_linear_velocity is not None:
            speed = np.linalg.norm(command.base_linear_velocity)
            if speed > max_speed:
                scale = max_speed / speed
                command.base_linear_velocity = command.base_linear_velocity * scale
                command.safety_limited = True

        return command

    def estimate_separation_distance(
        self,
        robot_velocity: np.ndarray,
        human_velocity: np.ndarray = None
    ) -> float:
        """
        Estimate safe separation distance per ISO/TS 15066.

        Args:
            robot_velocity: Robot velocity (m/s)
            human_velocity: Human velocity (m/s, optional)

        Returns:
            Required separation distance (meters)
        """
        if human_velocity is None:
            human_velocity = np.array([1.6, 0, 0])  # Max walking speed

        robot_speed = np.linalg.norm(robot_velocity)
        human_speed = np.linalg.norm(human_velocity)

        # Simplified SSM formula
        t_react = 0.5  # Reaction time
        t_stop = robot_speed / 5.0  # Assume 5 m/s^2 deceleration

        S_r = robot_speed * (t_react + t_stop / 2)  # Robot stopping distance
        S_h = human_speed * (t_react + t_stop)       # Human travel distance
        C = 0.2  # Safety margin

        return S_r + S_h + C
