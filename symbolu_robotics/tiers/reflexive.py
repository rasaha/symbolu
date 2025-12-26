"""
Reflexive Tier (R1) for Robotics
=================================

Sub-millisecond reflexive control.

Characteristics:
- Runs on microcontroller (ARM Cortex-M, ESP32)
- No learning, pure deterministic
- Always active as safety layer
- Latency target: <1ms (200μs typical)
"""

from typing import Optional, Dict
import numpy as np

from symbolu_robotics.tiers.base import BaseTier, TierConfig
from symbolu_robotics.core.types import SensorFrame, ActuatorCommand, Layer12D
from symbolu_robotics.encoders.base_encoder import LightweightEncoder
from symbolu_robotics.safety.collision_guard import CollisionGuard


class ReflexLibrary:
    """
    Library of reflexive behaviors.

    Maps dominant layer index to reflexive response.
    """

    def __init__(self):
        # Behavior lookup: layer_index -> velocity_scale
        self._behaviors: Dict[int, float] = {
            0: 0.0,   # O1_POTENTIAL: idle
            1: 0.3,   # O2_IDENTITY: slow orientation
            2: 1.0,   # O3_EXECUTION: full motion
            3: 0.5,   # O4_STRUCTURE: moderate motion
            4: 0.2,   # O5_COGNITION: exploratory
            5: 0.8,   # O6_AGENCY: active
            11: 0.0,  # O12_ABSOLVING: stop (safety)
        }

    def lookup(self, dominant_layer: int) -> float:
        """Get velocity scale for dominant layer."""
        return self._behaviors.get(dominant_layer, 0.5)


class ReflexiveTier(BaseTier):
    """
    Tier R1: Sub-millisecond reflexive control.

    Timing budget:
    - 100μs encoding
    - 50μs lookup
    - 50μs safety
    = 200μs total
    """

    def __init__(self, config: Optional[TierConfig] = None):
        super().__init__(config)
        self.encoder = LightweightEncoder()
        self.safety = CollisionGuard()
        self.reflexes = ReflexLibrary()

    @property
    def tier_name(self) -> str:
        return "reflexive"

    @property
    def target_latency_ms(self) -> float:
        return 1.0  # Hard deadline

    def step(self, sensor_frame: SensorFrame) -> ActuatorCommand:
        """
        Execute reflexive control step.

        O1: Readiness check
        O5 → O3: Direct perception-to-action
        O12: Safety constraint application
        """
        # O1: Readiness check - immediate safety check
        if not self.safety.clear(sensor_frame):
            self._metrics.safety_applied = True
            return self.safety.emergency_stop()

        # O5 → O3: Direct perception-to-action encoding
        layer_12d = self.encoder.encode(sensor_frame)
        self._metrics.layer_12d = layer_12d

        # Find dominant layer (lower layers only for speed)
        dominant = int(np.argmax(layer_12d[0:6]))

        # Get reflex response
        velocity_scale = self.reflexes.lookup(dominant)

        # Generate command
        if sensor_frame.joints is not None:
            num_joints = sensor_frame.joints.num_joints
        else:
            num_joints = 6

        # O12: Safety constraint application
        constraint = layer_12d[11]
        effective_scale = velocity_scale * (1.0 - constraint * 0.9)

        # Simple velocity command
        target_velocities = np.zeros(num_joints)
        if effective_scale > 0.01:
            # Continue current motion at scaled speed
            if sensor_frame.joints is not None and sensor_frame.joints.velocities is not None:
                target_velocities = sensor_frame.joints.velocities * effective_scale

        command = ActuatorCommand(
            target_velocities=target_velocities,
            control_mode="velocity"
        )

        # Final safety check
        return self.safety.constrain_command(command, sensor_frame)

    def reset(self) -> None:
        super().reset()
        self.encoder.reset()
