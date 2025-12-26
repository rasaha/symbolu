"""
World State for Robotics
=========================

Combined robot + environment state.
"""

from dataclasses import dataclass, field
from typing import Dict, Any, Optional
import time

from symbolu_robotics.state.robot_state import RobotState
from symbolu_robotics.planning.world_model import WorldModel
from symbolu_robotics.core.types import Layer12D


@dataclass
class WorldState:
    """
    Complete world state including robot and environment.

    Combines:
    - Robot state
    - World model (objects, obstacles)
    - 12D ontological state
    """
    # Timestamp
    timestamp: float = 0.0

    # Robot state
    robot: RobotState = field(default_factory=RobotState)

    # World model
    world_model: WorldModel = field(default_factory=WorldModel)

    # Aggregated 12D state
    layer_12d: Layer12D = field(default_factory=lambda: __import__('numpy').zeros(12))

    # Mission state
    mission_active: bool = False
    mission_progress: float = 0.0

    # Safety state
    emergency_stop_active: bool = False
    safety_constraints_active: bool = False

    def compute_layer_12d(self) -> Layer12D:
        """
        Compute aggregated 12D layer state from components.

        Combines robot state, world model, and localization.
        """
        import numpy as np

        layer = np.zeros(12, dtype=np.float32)

        # O1_POTENTIAL: System readiness
        layer[0] = 1.0 if self.robot.is_valid else 0.0

        # O2_IDENTITY: Localization confidence
        layer[1] = 0.8  # From localization

        # O3_EXECUTION: Motion state
        if self.robot.is_moving:
            vel_norm = np.linalg.norm(self.robot.joints.velocities)
            layer[2] = min(1.0, vel_norm / 2.0)

        # O4_STRUCTURE: Body state
        pos_norm = np.linalg.norm(self.robot.joints.positions)
        layer[3] = min(1.0, pos_norm / np.pi)

        # O5_COGNITION: Perception (from robot layer if available)
        layer[4] = self.robot.layer_12d[4] if len(self.robot.layer_12d) > 4 else 0.5

        # O6_AGENCY: Autonomy level
        layer[5] = 0.5 if self.mission_active else 0.2

        # O7_REASONING: Planning active
        layer[6] = self.mission_progress

        # O8_PURPOSE: Goal state
        layer[7] = 1.0 if self.mission_active else 0.0

        # O9_WITNESSES: World model richness
        layer[8] = self.world_model.compute_witnesses_level()

        # O10_UNIFYING: Multi-agent (default single)
        layer[9] = 0.3

        # O11_INTEGRATION: Sensor fusion quality
        layer[10] = 0.7  # Default good fusion

        # O12_ABSOLVING: Safety constraints
        layer[11] = 1.0 if self.emergency_stop_active else (
            0.5 if self.safety_constraints_active else 0.1
        )

        self.layer_12d = layer
        return layer

    def to_dict(self) -> Dict[str, Any]:
        return {
            "timestamp": self.timestamp,
            "robot": self.robot.to_dict(),
            "layer_12d": self.layer_12d.tolist(),
            "mission_active": self.mission_active,
            "mission_progress": self.mission_progress,
            "emergency_stop_active": self.emergency_stop_active,
            "safety_constraints_active": self.safety_constraints_active,
        }


class WorldStateManager:
    """
    Manages world state updates and history.
    """

    def __init__(self, history_size: int = 100):
        self._current = WorldState()
        self._history = []
        self.history_size = history_size

    @property
    def current(self) -> WorldState:
        return self._current

    def update(
        self,
        robot_state: Optional[RobotState] = None,
        layer_12d: Optional[Layer12D] = None,
        mission_progress: Optional[float] = None
    ) -> WorldState:
        """Update world state."""
        self._current.timestamp = time.time()

        if robot_state is not None:
            self._current.robot = robot_state

        if layer_12d is not None:
            self._current.layer_12d = layer_12d
        else:
            self._current.compute_layer_12d()

        if mission_progress is not None:
            self._current.mission_progress = mission_progress

        # Store history
        self._history.append(self._current)
        if len(self._history) > self.history_size:
            self._history.pop(0)

        return self._current

    def set_emergency_stop(self, active: bool) -> None:
        """Set emergency stop state."""
        self._current.emergency_stop_active = active
        self._current.compute_layer_12d()

    def set_mission(self, active: bool) -> None:
        """Set mission state."""
        self._current.mission_active = active
        if not active:
            self._current.mission_progress = 0.0
        self._current.compute_layer_12d()

    def get_history(self) -> list:
        """Get state history."""
        return self._history.copy()
