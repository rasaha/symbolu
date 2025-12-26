"""
Collision Guard for Robotics
=============================

Layer 1 safety: Sub-millisecond collision detection and response.

Cannot be overridden by software - operates at the reflexive tier.
"""

from dataclasses import dataclass
from typing import Optional, List, Tuple
import numpy as np

from symbolu_robotics.core.types import SensorFrame, ActuatorCommand, SafetyLevel


@dataclass
class CollisionZone:
    """Definition of a collision monitoring zone."""
    name: str
    center: np.ndarray      # (x, y, z)
    radius: float           # meters
    priority: int = 1       # Higher = more critical


class CollisionGuard:
    """
    Layer 1: Reflexive collision avoidance.

    Operates at <1ms latency for immediate safety response.
    """

    def __init__(
        self,
        min_distance: float = 0.05,
        emergency_stop_distance: float = 0.02,
        zones: Optional[List[CollisionZone]] = None
    ):
        self.min_distance = min_distance
        self.emergency_stop_distance = emergency_stop_distance
        self.zones = zones or []
        self._collision_detected = False
        self._closest_distance = float('inf')

    def clear(self, sensor_frame: SensorFrame) -> bool:
        """
        Check if path is clear for motion.

        Fast check for reflexive tier.

        Returns:
            True if safe to proceed, False if collision imminent
        """
        self._collision_detected = False
        self._closest_distance = float('inf')

        # Check proximity sensors
        if sensor_frame.proximity_distances is not None:
            min_prox = np.min(sensor_frame.proximity_distances)
            self._closest_distance = min(self._closest_distance, min_prox)

            if min_prox < self.emergency_stop_distance:
                self._collision_detected = True
                return False

        # Check LIDAR
        if sensor_frame.lidar_ranges is not None:
            min_lidar = np.min(sensor_frame.lidar_ranges)
            self._closest_distance = min(self._closest_distance, min_lidar)

            if min_lidar < self.emergency_stop_distance:
                self._collision_detected = True
                return False

        # Check depth
        if sensor_frame.depth_image is not None:
            valid_depths = sensor_frame.depth_image[sensor_frame.depth_image > 0]
            if len(valid_depths) > 0:
                min_depth = np.min(valid_depths)
                self._closest_distance = min(self._closest_distance, min_depth)

                if min_depth < self.emergency_stop_distance:
                    self._collision_detected = True
                    return False

        return True

    def get_safety_level(self) -> SafetyLevel:
        """Get current safety level based on closest obstacle."""
        if self._collision_detected:
            return SafetyLevel.EMERGENCY_STOP

        if self._closest_distance < self.min_distance:
            return SafetyLevel.RESTRICTED
        elif self._closest_distance < self.min_distance * 3:
            return SafetyLevel.CAUTION
        else:
            return SafetyLevel.NOMINAL

    def get_constraint_level(self) -> float:
        """Get O12_ABSOLVING constraint level (0-1)."""
        if self._collision_detected:
            return 1.0

        if self._closest_distance >= self.min_distance * 5:
            return 0.0

        # Linear interpolation
        return max(0.0, 1.0 - (self._closest_distance - self.emergency_stop_distance) /
                   (self.min_distance * 5 - self.emergency_stop_distance))

    def emergency_stop(self) -> ActuatorCommand:
        """Generate emergency stop command."""
        return ActuatorCommand(
            emergency_stop=True,
            target_velocities=np.zeros(6),
            control_mode="velocity"
        )

    def constrain_command(
        self,
        command: ActuatorCommand,
        sensor_frame: SensorFrame
    ) -> ActuatorCommand:
        """
        Apply collision-aware constraints to command.

        Args:
            command: Input command
            sensor_frame: Current sensor data

        Returns:
            Constrained command (or E-STOP if collision)
        """
        if not self.clear(sensor_frame):
            return self.emergency_stop()

        safety_level = self.get_safety_level()

        if safety_level == SafetyLevel.EMERGENCY_STOP:
            return self.emergency_stop()

        elif safety_level == SafetyLevel.RESTRICTED:
            # Reduce to 10% speed
            return self._scale_command(command, 0.1)

        elif safety_level == SafetyLevel.CAUTION:
            # Reduce to 50% speed
            return self._scale_command(command, 0.5)

        return command

    def _scale_command(self, command: ActuatorCommand, scale: float) -> ActuatorCommand:
        """Scale command velocities."""
        if command.target_velocities is not None:
            command.target_velocities = command.target_velocities * scale
        if command.base_linear_velocity is not None:
            command.base_linear_velocity = command.base_linear_velocity * scale
        if command.base_angular_velocity is not None:
            command.base_angular_velocity = command.base_angular_velocity * scale
        command.safety_limited = True
        return command

    def check_zone_intrusion(
        self,
        point: np.ndarray
    ) -> Tuple[bool, Optional[CollisionZone]]:
        """Check if a point intrudes any collision zone."""
        for zone in self.zones:
            distance = np.linalg.norm(point - zone.center)
            if distance < zone.radius:
                return True, zone
        return False, None

    @property
    def closest_distance(self) -> float:
        return self._closest_distance

    @property
    def is_collision_detected(self) -> bool:
        return self._collision_detected
