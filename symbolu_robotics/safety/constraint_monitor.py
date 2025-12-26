"""
Constraint Monitor for Robotics
================================

O12_ABSOLVING enforcement - safety constraint application.

Maps to the ontological layer that "absolves" actions by ensuring safety.
"""

from dataclasses import dataclass, field
from typing import Optional, Tuple, List
import numpy as np

from symbolu_robotics.core.types import ActuatorCommand, Layer12D, SafetyLevel


@dataclass
class SafetyConfig:
    """Safety configuration parameters."""
    # Joint limits (radians)
    joint_lower_limits: np.ndarray = field(default_factory=lambda: np.full(6, -np.pi))
    joint_upper_limits: np.ndarray = field(default_factory=lambda: np.full(6, np.pi))

    # Velocity limits (rad/s)
    max_joint_velocity: float = 2.0

    # Acceleration limits (rad/s^2)
    max_joint_acceleration: float = 5.0

    # Force/torque limits (Nm)
    max_joint_effort: float = 100.0

    # Human proximity threshold (meters)
    human_distance_threshold: float = 1.0

    # Collision distance threshold (meters)
    collision_threshold: float = 0.05


# Preset configurations
INDUSTRIAL_SAFETY = SafetyConfig(
    max_joint_velocity=3.0,
    max_joint_effort=200.0,
    human_distance_threshold=0.5,
)

COLLABORATIVE_SAFETY = SafetyConfig(
    max_joint_velocity=1.0,
    max_joint_effort=50.0,
    human_distance_threshold=1.5,
)


class ConstraintMonitor:
    """
    O12_ABSOLVING: Safety constraint enforcement.

    Applies position, velocity, and effort limits to actuator commands.
    """

    def __init__(self, config: Optional[SafetyConfig] = None):
        self.config = config or SafetyConfig()
        self._violation_log: List[str] = []
        self._current_safety_level = SafetyLevel.NOMINAL

    @property
    def safety_level(self) -> SafetyLevel:
        return self._current_safety_level

    def constrain(
        self,
        command: ActuatorCommand,
        layer_12d: Layer12D
    ) -> ActuatorCommand:
        """
        Apply safety constraints to command based on O12 level.

        Args:
            command: Raw actuator command
            layer_12d: Current 12D state (O12 indicates constraint tightness)

        Returns:
            Constrained actuator command
        """
        if command.emergency_stop:
            return command  # E-stop always passes through

        constraint_level = layer_12d[11]  # O12_ABSOLVING
        self._update_safety_level(constraint_level)

        # Scale limits by constraint level
        effective_vel_limit = self.config.max_joint_velocity * (1.0 - constraint_level * 0.8)
        effective_effort_limit = self.config.max_joint_effort * (1.0 - constraint_level * 0.7)

        # Apply velocity constraints
        if command.target_velocities is not None:
            command.target_velocities = self._clip_velocity(
                command.target_velocities, effective_vel_limit
            )

        # Apply position constraints
        if command.target_positions is not None:
            command.target_positions = self._clip_position(command.target_positions)

        # Apply effort constraints
        if command.target_efforts is not None:
            command.target_efforts = self._clip_effort(
                command.target_efforts, effective_effort_limit
            )

        # Slow motion mode for high constraint
        if constraint_level > 0.8:
            command = self._slow_motion_mode(command)

        return command

    def _update_safety_level(self, constraint: float) -> None:
        """Update safety level based on constraint."""
        if constraint > 0.9:
            self._current_safety_level = SafetyLevel.EMERGENCY_STOP
        elif constraint > 0.7:
            self._current_safety_level = SafetyLevel.RESTRICTED
        elif constraint > 0.4:
            self._current_safety_level = SafetyLevel.CAUTION
        else:
            self._current_safety_level = SafetyLevel.NOMINAL

    def _clip_velocity(self, velocities: np.ndarray, limit: float) -> np.ndarray:
        """Clip velocities to limit."""
        clipped = np.clip(velocities, -limit, limit)
        if not np.array_equal(clipped, velocities):
            self._violation_log.append("velocity_limit")
        return clipped

    def _clip_position(self, positions: np.ndarray) -> np.ndarray:
        """Clip positions to joint limits."""
        clipped = np.clip(
            positions,
            self.config.joint_lower_limits[:len(positions)],
            self.config.joint_upper_limits[:len(positions)]
        )
        if not np.array_equal(clipped, positions):
            self._violation_log.append("position_limit")
        return clipped

    def _clip_effort(self, efforts: np.ndarray, limit: float) -> np.ndarray:
        """Clip efforts to limit."""
        clipped = np.clip(efforts, -limit, limit)
        if not np.array_equal(clipped, efforts):
            self._violation_log.append("effort_limit")
        return clipped

    def _slow_motion_mode(self, command: ActuatorCommand) -> ActuatorCommand:
        """Apply slow motion mode for safety."""
        scale = 0.2  # 20% of normal speed

        if command.target_velocities is not None:
            command.target_velocities *= scale
        if command.base_linear_velocity is not None:
            command.base_linear_velocity *= scale
        if command.base_angular_velocity is not None:
            command.base_angular_velocity *= scale

        command.safety_limited = True
        return command

    def check_command_safety(self, command: ActuatorCommand) -> Tuple[bool, List[str]]:
        """
        Check if a command is within safety bounds.

        Returns:
            Tuple of (is_safe, list_of_violations)
        """
        violations = []

        if command.target_velocities is not None:
            if np.any(np.abs(command.target_velocities) > self.config.max_joint_velocity):
                violations.append("velocity_exceeded")

        if command.target_positions is not None:
            if np.any(command.target_positions < self.config.joint_lower_limits[:len(command.target_positions)]):
                violations.append("position_below_lower_limit")
            if np.any(command.target_positions > self.config.joint_upper_limits[:len(command.target_positions)]):
                violations.append("position_above_upper_limit")

        if command.target_efforts is not None:
            if np.any(np.abs(command.target_efforts) > self.config.max_joint_effort):
                violations.append("effort_exceeded")

        return len(violations) == 0, violations

    def get_violation_log(self) -> List[str]:
        """Get and clear violation log."""
        log = self._violation_log.copy()
        self._violation_log = []
        return log
