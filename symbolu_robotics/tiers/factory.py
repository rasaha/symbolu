"""
Tier Factory for Robotics
==========================

Creates and manages tier instances.
"""

from enum import Enum
from typing import Optional, Union

from symbolu_robotics.tiers.base import BaseTier, TierConfig
from symbolu_robotics.tiers.reflexive import ReflexiveTier
from symbolu_robotics.tiers.reactive import ReactiveTier
from symbolu_robotics.tiers.deliberative import DeliberativeTier


class TierLevel(Enum):
    """Tier level enumeration."""
    R1_REFLEXIVE = "reflexive"
    R2_REACTIVE = "reactive"
    R3_DELIBERATIVE = "deliberative"


def create_tier(
    level: Union[TierLevel, str],
    config: Optional[TierConfig] = None,
    **kwargs
) -> BaseTier:
    """
    Create a tier instance.

    Args:
        level: Tier level (R1, R2, or R3)
        config: Optional tier configuration
        **kwargs: Additional arguments passed to tier constructor

    Returns:
        Tier instance

    Example:
        tier = create_tier(TierLevel.R2_REACTIVE, num_joints=7)
    """
    if isinstance(level, str):
        level = TierLevel(level)

    if level == TierLevel.R1_REFLEXIVE:
        return ReflexiveTier(config)

    elif level == TierLevel.R2_REACTIVE:
        return ReactiveTier(config, **kwargs)

    elif level == TierLevel.R3_DELIBERATIVE:
        return DeliberativeTier(config)

    else:
        raise ValueError(f"Unknown tier level: {level}")


class TierCascade:
    """
    Cascaded tier execution.

    Runs all tiers with fallback logic:
    - R1 always runs (safety)
    - R2 runs if time permits
    - R3 runs asynchronously
    """

    def __init__(self, config: Optional[TierConfig] = None, num_joints: int = 6):
        self.r1 = ReflexiveTier(config)
        self.r2 = ReactiveTier(config, num_joints=num_joints)
        self.r3 = DeliberativeTier(config)

        self._use_r2 = True
        self._use_r3 = True

    def step(self, sensor_frame, command: Optional[str] = None):
        """
        Execute cascaded tier step.

        Priority: Safety (R1) > Behavior (R2) > Planning (R3)
        """
        from symbolu_robotics.core.types import SensorFrame, ActuatorCommand

        # R1: Always run for safety
        r1_cmd, r1_metrics = self.r1.step_timed(sensor_frame)

        # If R1 triggered emergency stop, return immediately
        if r1_cmd.emergency_stop:
            return r1_cmd

        # R2: Run if enabled and time budget allows
        if self._use_r2:
            r2_cmd, r2_metrics = self.r2.step_timed(sensor_frame)

            # Use R2 command if it's safe
            if not r2_cmd.emergency_stop:
                final_cmd = r2_cmd
            else:
                final_cmd = r1_cmd
        else:
            final_cmd = r1_cmd

        # R3: Run asynchronously for planning (if command provided)
        if self._use_r3 and command:
            # In real implementation, this would be async
            plan = self.r3.step(sensor_frame, command)
            # Plan would be fed back to R2 for execution

        return final_cmd

    def enable_tier(self, level: TierLevel, enabled: bool = True) -> None:
        """Enable or disable a tier."""
        if level == TierLevel.R2_REACTIVE:
            self._use_r2 = enabled
        elif level == TierLevel.R3_DELIBERATIVE:
            self._use_r3 = enabled

    def reset(self) -> None:
        """Reset all tiers."""
        self.r1.reset()
        self.r2.reset()
        self.r3.reset()
