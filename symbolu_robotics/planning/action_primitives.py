"""
Action Primitives for Robotics
===============================

O3_EXECUTION library - atomic actions that can be composed.
"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Callable, Any
from enum import Enum
import numpy as np

from symbolu_robotics.core.types import ActuatorCommand


class ActionType(Enum):
    """Types of action primitives."""
    MOVE = "move"
    GRASP = "grasp"
    RELEASE = "release"
    ROTATE = "rotate"
    WAIT = "wait"
    SPEAK = "speak"
    LOOK = "look"


@dataclass
class ActionPrimitive:
    """
    Atomic action primitive.

    Actions are parameterized operations that produce ActuatorCommands.
    """
    name: str
    action_type: ActionType
    parameters: Dict[str, Any] = field(default_factory=dict)
    duration: float = 1.0  # seconds
    preconditions: List[str] = field(default_factory=list)
    effects: List[str] = field(default_factory=list)

    def is_applicable(self, state: Dict[str, Any]) -> bool:
        """Check if preconditions are met."""
        for precond in self.preconditions:
            if precond not in state or not state[precond]:
                return False
        return True

    def to_command(self, num_joints: int = 6) -> ActuatorCommand:
        """Convert to ActuatorCommand."""
        if self.action_type == ActionType.MOVE:
            velocities = self.parameters.get("velocities", np.zeros(num_joints))
            return ActuatorCommand(
                target_velocities=np.array(velocities),
                control_mode="velocity"
            )

        elif self.action_type == ActionType.GRASP:
            return ActuatorCommand(
                gripper_position=0.0,
                gripper_force=self.parameters.get("force", 30.0)
            )

        elif self.action_type == ActionType.RELEASE:
            return ActuatorCommand(
                gripper_position=1.0,
                gripper_force=5.0
            )

        elif self.action_type == ActionType.ROTATE:
            velocities = np.zeros(num_joints)
            velocities[0] = self.parameters.get("angular_velocity", 0.5)
            return ActuatorCommand(
                target_velocities=velocities,
                control_mode="velocity"
            )

        elif self.action_type == ActionType.WAIT:
            return ActuatorCommand(
                target_velocities=np.zeros(num_joints),
                control_mode="velocity"
            )

        else:
            return ActuatorCommand()


class ActionPrimitives:
    """
    Library of action primitives.

    Provides factory methods for common actions.
    """

    def __init__(self):
        self._primitives: Dict[str, ActionPrimitive] = {}
        self._register_defaults()

    def _register_defaults(self) -> None:
        """Register default action primitives."""
        # Movement primitives
        self.register(ActionPrimitive(
            name="move_forward",
            action_type=ActionType.MOVE,
            parameters={"velocities": [0.5, 0, 0, 0, 0, 0]},
            duration=1.0
        ))

        self.register(ActionPrimitive(
            name="move_backward",
            action_type=ActionType.MOVE,
            parameters={"velocities": [-0.3, 0, 0, 0, 0, 0]},
            duration=1.0
        ))

        self.register(ActionPrimitive(
            name="stop",
            action_type=ActionType.WAIT,
            duration=0.0
        ))

        # Gripper primitives
        self.register(ActionPrimitive(
            name="grasp_soft",
            action_type=ActionType.GRASP,
            parameters={"force": 20.0},
            duration=2.0,
            preconditions=["gripper_open"],
            effects=["object_grasped"]
        ))

        self.register(ActionPrimitive(
            name="grasp_firm",
            action_type=ActionType.GRASP,
            parameters={"force": 50.0},
            duration=2.0,
            preconditions=["gripper_open"],
            effects=["object_grasped"]
        ))

        self.register(ActionPrimitive(
            name="release",
            action_type=ActionType.RELEASE,
            duration=1.0,
            preconditions=["object_grasped"],
            effects=["gripper_open"]
        ))

        # Rotation primitives
        self.register(ActionPrimitive(
            name="rotate_left",
            action_type=ActionType.ROTATE,
            parameters={"angular_velocity": 0.5},
            duration=1.0
        ))

        self.register(ActionPrimitive(
            name="rotate_right",
            action_type=ActionType.ROTATE,
            parameters={"angular_velocity": -0.5},
            duration=1.0
        ))

    def register(self, primitive: ActionPrimitive) -> None:
        """Register an action primitive."""
        self._primitives[primitive.name] = primitive

    def get(self, name: str) -> Optional[ActionPrimitive]:
        """Get primitive by name."""
        return self._primitives.get(name)

    def get_applicable(self, state: Dict[str, Any]) -> List[ActionPrimitive]:
        """Get all applicable primitives given current state."""
        return [p for p in self._primitives.values() if p.is_applicable(state)]

    def list_all(self) -> List[str]:
        """List all registered primitives."""
        return list(self._primitives.keys())

    def create_move(
        self,
        velocities: np.ndarray,
        duration: float = 1.0
    ) -> ActionPrimitive:
        """Create a custom move primitive."""
        return ActionPrimitive(
            name=f"move_custom_{id(velocities)}",
            action_type=ActionType.MOVE,
            parameters={"velocities": velocities.tolist()},
            duration=duration
        )

    def create_sequence(
        self,
        primitives: List[str]
    ) -> List[ActuatorCommand]:
        """Create a sequence of commands from primitive names."""
        commands = []
        for name in primitives:
            prim = self.get(name)
            if prim:
                commands.append(prim.to_command())
        return commands
