"""
Deliberative Tier (R3) for Robotics
====================================

Deliberative planning and reasoning.

Characteristics:
- Runs on edge GPU or cloud
- Full Chitta-Vritti analysis (v2.8)
- Task planning with goal hierarchy
- Natural language interface
- Latency target: <100ms (can be async)
"""

from typing import Optional, List
import numpy as np

from symbolu_robotics.tiers.base import BaseTier, TierConfig
from symbolu_robotics.core.types import SensorFrame, ActuatorCommand, Layer12D, Plan, Goal
from symbolu_robotics.core.chitta_vritti import compute_vritti, VrittiResult
from symbolu_robotics.core.mirror_pairs_12d import propagate_to_mirror_12d
from symbolu_robotics.encoders.fusion_encoder import FusionEncoder


class WorldModel:
    """
    O9_WITNESSES: World model representation.

    Tracks environment state for planning.
    """

    def __init__(self):
        self._objects: List[dict] = []
        self._obstacles: List[dict] = []
        self._last_update = 0.0

    def update(self, layer_12d: Layer12D, sensor_frame: SensorFrame) -> None:
        """Update world model from sensors."""
        self._last_update = sensor_frame.timestamp

        # Simple obstacle detection from proximity
        if sensor_frame.proximity_distances is not None:
            self._obstacles = [
                {"distance": float(d), "direction": i}
                for i, d in enumerate(sensor_frame.proximity_distances)
                if d < 2.0
            ]

    def get_obstacles(self) -> List[dict]:
        return self._obstacles


class TaskPlanner:
    """
    O7_REASONING + O8_PURPOSE: Task planning.

    Uses BCVF (B1-B3) for action selection.
    """

    def __init__(self):
        self._goal_stack: List[Goal] = []
        self._action_library = {
            "move_to": self._plan_move,
            "grasp": self._plan_grasp,
            "release": self._plan_release,
            "wait": self._plan_wait,
        }

    def push_goal(self, goal: Goal) -> None:
        """Add goal to stack."""
        self._goal_stack.append(goal)

    def pop_goal(self) -> Optional[Goal]:
        """Remove and return top goal."""
        if self._goal_stack:
            return self._goal_stack.pop()
        return None

    def plan(
        self,
        current_state: Layer12D,
        world: WorldModel,
        cognitive_mode: VrittiResult
    ) -> Plan:
        """
        Generate plan using BCVF action selection.

        Uses B1-B3 formulas for scoring action candidates.
        """
        if not self._goal_stack:
            return Plan()

        current_goal = self._goal_stack[-1]

        # B1: Generate action candidates based on goal
        candidates = self._generate_candidates(current_goal, current_state, world)

        if not candidates:
            return Plan()

        # B2: Score candidates using 12D coherence
        scored = []
        for action, params in candidates:
            # Simple scoring based on layer alignment
            score = self._score_action(action, params, current_state, cognitive_mode)
            scored.append((score, action, params))

        # B3: Select best action
        scored.sort(reverse=True)
        best_score, best_action, best_params = scored[0]

        # Generate plan
        plan_fn = self._action_library.get(best_action, self._plan_wait)
        return plan_fn(best_params, current_state)

    def _generate_candidates(
        self,
        goal: Goal,
        state: Layer12D,
        world: WorldModel
    ) -> List[tuple]:
        """Generate action candidates for goal."""
        candidates = []

        if goal.target_pose is not None:
            candidates.append(("move_to", {"pose": goal.target_pose}))

        if "grasp" in goal.description.lower():
            candidates.append(("grasp", {}))

        if "release" in goal.description.lower():
            candidates.append(("release", {}))

        # Always include wait as fallback
        candidates.append(("wait", {}))

        return candidates

    def _score_action(
        self,
        action: str,
        params: dict,
        state: Layer12D,
        cognitive_mode: VrittiResult
    ) -> float:
        """Score action using BCVF-inspired formula."""
        base_score = 0.5

        # Pramana (valid cognition) boosts confidence in action
        if cognitive_mode.dominant == "pramana":
            base_score += 0.3

        # Action-specific scoring
        if action == "move_to":
            base_score += state[2] * 0.2  # O3_EXECUTION
            base_score += state[7] * 0.3  # O8_PURPOSE
        elif action == "grasp":
            base_score += state[4] * 0.3  # O5_COGNITION (object perception)
        elif action == "release":
            base_score += state[7] * 0.2  # O8_PURPOSE

        # Safety penalty
        base_score -= state[11] * 0.4  # O12_ABSOLVING

        return max(0.0, min(1.0, base_score))

    def _plan_move(self, params: dict, state: Layer12D) -> Plan:
        """Generate move plan."""
        actions = []
        # Simplified: single velocity command toward goal
        cmd = ActuatorCommand(
            target_velocities=np.array([0.5, 0, 0, 0, 0, 0]),
            control_mode="velocity"
        )
        actions.append(cmd)
        return Plan(actions=actions, estimated_duration=5.0)

    def _plan_grasp(self, params: dict, state: Layer12D) -> Plan:
        """Generate grasp plan."""
        cmd = ActuatorCommand(gripper_position=0.0, gripper_force=30.0)
        return Plan(actions=[cmd], estimated_duration=2.0)

    def _plan_release(self, params: dict, state: Layer12D) -> Plan:
        """Generate release plan."""
        cmd = ActuatorCommand(gripper_position=1.0, gripper_force=5.0)
        return Plan(actions=[cmd], estimated_duration=1.0)

    def _plan_wait(self, params: dict, state: Layer12D) -> Plan:
        """Generate wait plan."""
        cmd = ActuatorCommand(target_velocities=np.zeros(6), control_mode="velocity")
        return Plan(actions=[cmd], estimated_duration=0.5)


class NaturalLanguageInterface:
    """
    Parse natural language commands to goals.

    Simple keyword-based for now; can integrate LLM.
    """

    def parse(self, command: str) -> Goal:
        """Parse command string to Goal."""
        cmd_lower = command.lower()

        if "pick" in cmd_lower or "grasp" in cmd_lower:
            return Goal(description="grasp object", priority=0.8)
        elif "place" in cmd_lower or "put" in cmd_lower or "release" in cmd_lower:
            return Goal(description="release object", priority=0.8)
        elif "move" in cmd_lower or "go" in cmd_lower:
            return Goal(description="move to location", priority=0.7)
        elif "stop" in cmd_lower:
            return Goal(description="stop", priority=1.0)
        else:
            return Goal(description=command, priority=0.5)


class DeliberativeTier(BaseTier):
    """
    Tier R3: Deliberative planning and reasoning.

    Full Chitta-Vritti analysis for cognitive mode.
    Task planning with BCVF action selection.
    """

    def __init__(self, config: Optional[TierConfig] = None):
        super().__init__(config)
        self.encoder = FusionEncoder()
        self.world_model = WorldModel()
        self.planner = TaskPlanner()
        self.nl_interface = NaturalLanguageInterface()

        # Vritti state
        self._accumulated_smrti = 0.0
        self._last_vritti: Optional[VrittiResult] = None

    @property
    def tier_name(self) -> str:
        return "deliberative"

    @property
    def target_latency_ms(self) -> float:
        return 100.0

    def step(
        self,
        sensor_frame: SensorFrame,
        command: Optional[str] = None
    ) -> Plan:
        """
        Execute deliberative planning step.

        Args:
            sensor_frame: Current sensor data
            command: Optional natural language command

        Returns:
            Plan to be executed by R2/R1 tiers
        """
        # O5 + O11: Full perception
        layer_12d = self.encoder.encode(sensor_frame)
        self._metrics.layer_12d = layer_12d

        # Mirror balance propagation
        layer_12d = propagate_to_mirror_12d(layer_12d)

        # v2.8: Cognitive mode analysis
        vritti_result, self._accumulated_smrti = compute_vritti(
            layer_12d=layer_12d,
            sensor_coherence=self.encoder.metrics.layer_coherence,
            accumulated_smrti=self._accumulated_smrti
        )
        self._last_vritti = vritti_result

        # O9: Update world model
        self.world_model.update(layer_12d, sensor_frame)

        # O8: Goal processing
        if command:
            goal = self.nl_interface.parse(command)
            self.planner.push_goal(goal)

        # O7: Planning
        plan = self.planner.plan(
            current_state=layer_12d,
            world=self.world_model,
            cognitive_mode=vritti_result
        )

        return plan

    def add_goal(self, goal: Goal) -> None:
        """Add goal to planner."""
        self.planner.push_goal(goal)

    def process_command(self, command: str) -> Goal:
        """Process natural language command."""
        goal = self.nl_interface.parse(command)
        self.planner.push_goal(goal)
        return goal

    @property
    def current_vritti(self) -> Optional[VrittiResult]:
        return self._last_vritti

    def reset(self) -> None:
        super().reset()
        self.encoder.reset()
        self._accumulated_smrti = 0.0
        self._last_vritti = None
