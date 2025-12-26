"""
Reactive Tier (R2) for Robotics
================================

Reactive behavioral control.

Characteristics:
- Runs on edge compute (Jetson, RPi5)
- EMA state tracking (v2.7)
- Mirror pair balancing
- Latency target: <10ms (5-7ms typical)
"""

from typing import Optional, List
import numpy as np

from symbolu_robotics.tiers.base import BaseTier, TierConfig
from symbolu_robotics.core.types import SensorFrame, ActuatorCommand, Layer12D
from symbolu_robotics.core.mirror_pairs_12d import compute_balance_12d, propagate_to_mirror_12d
from symbolu_robotics.core.v27_state import EMAState, update_ema_state, EMA_REACTIVE
from symbolu_robotics.encoders.fusion_encoder import FusionEncoder
from symbolu_robotics.decoders.motor_decoder import MotorDecoder
from symbolu_robotics.safety.constraint_monitor import ConstraintMonitor, SafetyConfig


class BehaviorLibrary:
    """
    Library of reactive behaviors.

    Behaviors are selected based on 12D balance state.
    """

    def select(self, layer_12d: Layer12D) -> str:
        """Select behavior based on layer state."""
        # Priority-based selection
        if layer_12d[11] > 0.7:  # O12_ABSOLVING high
            return "safety_retreat"
        if layer_12d[7] > 0.6:   # O8_PURPOSE high
            return "goal_seek"
        if layer_12d[2] > 0.5:   # O3_EXECUTION high
            return "execute_motion"
        if layer_12d[4] > 0.4:   # O5_COGNITION high
            return "explore"

        return "idle"

    def compute(self, behavior: str, layer_12d: Layer12D) -> np.ndarray:
        """
        Compute behavior output (velocity bias).

        Returns 6D joint velocity bias.
        """
        velocities = np.zeros(6)

        if behavior == "safety_retreat":
            # Reverse motion
            velocities[:] = -0.5
        elif behavior == "goal_seek":
            # Forward motion
            velocities[0] = layer_12d[7]  # Purpose drives speed
        elif behavior == "execute_motion":
            # Active motion based on execution layer
            velocities[:] = layer_12d[2] * 0.8
        elif behavior == "explore":
            # Slow exploratory motion
            velocities[:] = layer_12d[4] * 0.3

        return velocities


class ReactiveTier(BaseTier):
    """
    Tier R2: Reactive behavioral control.

    Timing budget:
    - 1ms encoding
    - 2ms mirror balance
    - 3ms behavior
    - 1ms safety
    = 7ms total
    """

    def __init__(self, config: Optional[TierConfig] = None, num_joints: int = 6):
        super().__init__(config)
        self.encoder = FusionEncoder()
        self.decoder = MotorDecoder(num_joints=num_joints)
        self.safety = ConstraintMonitor(SafetyConfig())
        self.behaviors = BehaviorLibrary()

        # v2.7 EMA state tracking
        self.state = EMAState()
        self.ema_config = EMA_REACTIVE

    @property
    def tier_name(self) -> str:
        return "reactive"

    @property
    def target_latency_ms(self) -> float:
        return 10.0

    def step(self, sensor_frame: SensorFrame) -> ActuatorCommand:
        """
        Execute reactive control step.

        O5 + O11: Perception and fusion
        v2.7 EMA: State update
        Mirror: Balance propagation
        O6: Agency check
        Behavior: Selection and computation
        O12: Safety constraints
        """
        # O5 + O11: Perception and fusion
        layer_12d = self.encoder.encode(sensor_frame)

        # v2.7 EMA state update
        self.state = update_ema_state(
            self.state, layer_12d, self.ema_config, sensor_frame.timestamp
        )
        layer_12d = self.state.layer_values
        self._metrics.layer_12d = layer_12d

        # Mirror pair balancing (O1↔O7, O3↔O9, etc.)
        balanced = propagate_to_mirror_12d(layer_12d)

        # O6: Agency check
        if balanced[5] < 0.3:  # Low agency
            return self._await_command()

        # Behavior selection based on balanced layers
        behavior = self.behaviors.select(balanced)
        velocity_bias = self.behaviors.compute(behavior, balanced)

        # Decode to motor command
        command = self.decoder.decode(balanced)

        # Apply behavior velocity bias
        if command.target_velocities is not None:
            command.target_velocities += velocity_bias

        # O12: Safety constraints
        command = self.safety.constrain(command, balanced)
        self._metrics.safety_applied = command.safety_limited

        return command

    def _await_command(self) -> ActuatorCommand:
        """Generate idle command while waiting for agency."""
        return ActuatorCommand(
            target_velocities=np.zeros(6),
            control_mode="velocity"
        )

    def reset(self) -> None:
        super().reset()
        self.encoder.reset()
        self.state = EMAState()
