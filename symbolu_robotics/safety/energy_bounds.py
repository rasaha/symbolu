"""
Energy Bounds Monitor for Robotics
===================================

Monitors and enforces actuator energy limits.

Prevents:
- Motor overheating
- Battery depletion
- Excessive current draw
"""

from dataclasses import dataclass
from typing import Optional, List
import numpy as np

from symbolu_robotics.core.types import JointState, ActuatorCommand


@dataclass
class EnergyLimits:
    """Energy limit configuration."""
    max_power_per_joint: float = 50.0      # Watts
    max_total_power: float = 200.0         # Watts
    max_continuous_effort: float = 80.0    # Nm (average)
    max_peak_effort: float = 150.0         # Nm (instantaneous)
    thermal_time_constant: float = 30.0    # seconds


class EnergyBoundsMonitor:
    """Monitors and enforces actuator energy limits."""

    def __init__(
        self,
        limits: Optional[EnergyLimits] = None,
        num_joints: int = 6
    ):
        self.limits = limits or EnergyLimits()
        self.num_joints = num_joints

        # Thermal model: EMA of effort for each joint
        self._thermal_state = np.zeros(num_joints)
        self._alpha = 2.0 / (self.limits.thermal_time_constant + 1)

    def update(self, joints: JointState) -> None:
        """Update thermal model with current joint state."""
        if joints.efforts is not None:
            effort_magnitude = np.abs(joints.efforts)
            self._thermal_state = (1 - self._alpha) * self._thermal_state + \
                                  self._alpha * effort_magnitude

    def compute_power(self, joints: JointState) -> np.ndarray:
        """Compute power consumption per joint (P = τ * ω)."""
        if joints.efforts is None or joints.velocities is None:
            return np.zeros(self.num_joints)

        return np.abs(joints.efforts * joints.velocities)

    def check_limits(self, joints: JointState) -> List[str]:
        """
        Check if current state violates energy limits.

        Returns:
            List of violation messages
        """
        violations = []

        # Check power per joint
        power = self.compute_power(joints)
        for i, p in enumerate(power):
            if p > self.limits.max_power_per_joint:
                violations.append(f"joint_{i}_power_exceeded")

        # Check total power
        total_power = np.sum(power)
        if total_power > self.limits.max_total_power:
            violations.append("total_power_exceeded")

        # Check peak effort
        if joints.efforts is not None:
            max_effort = np.max(np.abs(joints.efforts))
            if max_effort > self.limits.max_peak_effort:
                violations.append("peak_effort_exceeded")

        # Check thermal (continuous effort) via EMA
        if np.any(self._thermal_state > self.limits.max_continuous_effort):
            violations.append("thermal_limit_exceeded")

        return violations

    def constrain_command(
        self,
        command: ActuatorCommand,
        current_joints: JointState
    ) -> ActuatorCommand:
        """
        Constrain command to stay within energy limits.

        Args:
            command: Input actuator command
            current_joints: Current joint state

        Returns:
            Energy-constrained command
        """
        if command.target_efforts is not None:
            # Limit peak effort
            command.target_efforts = np.clip(
                command.target_efforts,
                -self.limits.max_peak_effort,
                self.limits.max_peak_effort
            )

            # Reduce effort if thermal limit is approaching
            thermal_margin = self.limits.max_continuous_effort - self._thermal_state
            thermal_scale = np.clip(thermal_margin / 20.0, 0.2, 1.0)  # 20 Nm buffer
            command.target_efforts = command.target_efforts * thermal_scale

        if command.target_velocities is not None:
            # Estimate power and limit velocity if needed
            if current_joints.efforts is not None:
                estimated_power = np.abs(current_joints.efforts * command.target_velocities)
                if np.any(estimated_power > self.limits.max_power_per_joint):
                    # Scale velocities to meet power limit
                    scale = self.limits.max_power_per_joint / (np.max(estimated_power) + 1e-6)
                    command.target_velocities = command.target_velocities * min(scale, 1.0)
                    command.safety_limited = True

        return command

    def get_thermal_percentage(self) -> np.ndarray:
        """Get thermal utilization as percentage of limit."""
        return self._thermal_state / self.limits.max_continuous_effort * 100

    def reset(self) -> None:
        """Reset thermal model."""
        self._thermal_state = np.zeros(self.num_joints)
