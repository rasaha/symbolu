"""
Deliberative Tier (R3) for Robotics
====================================

Deliberative planning and reasoning.

Implements patent formulas:
- BCVF (B1-B3): Bidirectional Consistency Verification for action selection
- SCC (S1-S9): Semantic Coherence Controller for state monitoring

Characteristics:
- Runs on edge GPU or cloud
- Full Chitta-Vritti analysis (v2.8)
- Task planning with goal hierarchy
- Natural language interface
- Latency target: <100ms (can be async)
"""

from typing import Optional, List, Tuple, Dict, Any
import numpy as np

from symbolu_robotics.tiers.base import BaseTier, TierConfig
from symbolu_robotics.core.types import SensorFrame, ActuatorCommand, Layer12D, Plan, Goal
from symbolu_robotics.core.chitta_vritti import compute_vritti, VrittiResult
from symbolu_robotics.core.mirror_pairs_12d import propagate_to_mirror_12d
from symbolu_robotics.encoders.fusion_encoder import FusionEncoder
from symbolu_robotics.formulas.bcvf import (
    BCVFScorer,
    BCVFConfig,
    compute_consistency_lagrangian,
    ActionScore,
)
from symbolu_robotics.formulas.scc import (
    SCCMonitor,
    SCCConfig,
    compute_global_coherence,
    CoherenceResult,
)


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

    Uses BCVF (B1-B3) for action selection:
    - B1: Consistency Lagrangian for scoring
    - B2: Weight conversion from Lagrangian
    - B3: Normalization across candidates
    """

    def __init__(self, bcvf_config: Optional[BCVFConfig] = None):
        self._goal_stack: List[Goal] = []
        self._action_library = {
            "move_to": self._plan_move,
            "grasp": self._plan_grasp,
            "release": self._plan_release,
            "wait": self._plan_wait,
        }

        # BCVF scorer for action selection (B1-B3)
        self._bcvf_scorer = BCVFScorer(bcvf_config or BCVFConfig(
            lambda_forward=1.0,
            lambda_backward=1.0,
            lambda_consistency=0.5,
            beta=2.0,
        ))

        # Last scoring result for diagnostics
        self._last_action_scores: List[ActionScore] = []

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
        Generate plan using BCVF action selection (B1-B3).

        Process:
        1. Generate action candidates
        2. Compute forward scores (sf): action feasibility
        3. Compute backward scores (sb): goal achievement
        4. B1: Compute Consistency Lagrangian for each
        5. B2: Convert to weights
        6. B3: Normalize and select best
        """
        if not self._goal_stack:
            return Plan()

        current_goal = self._goal_stack[-1]

        # Generate action candidates
        candidates = self._generate_candidates(current_goal, current_state, world)

        if not candidates:
            return Plan()

        # Compute forward scores (sf): Is action physically feasible?
        forward_scores = [
            self._compute_forward_score(action, params, current_state, world)
            for action, params in candidates
        ]

        # Compute backward scores (sb): Does action achieve goal?
        backward_scores = [
            self._compute_backward_score(action, params, current_goal, cognitive_mode)
            for action, params in candidates
        ]

        # BCVF: Score candidates using B1-B3
        self._last_action_scores = self._bcvf_scorer.score_candidates(
            forward_scores, backward_scores
        )

        # Select best action (highest normalized weight from B3)
        best_idx = max(
            range(len(self._last_action_scores)),
            key=lambda i: self._last_action_scores[i].normalized_weight
        )
        best_action, best_params = candidates[best_idx]

        # Generate plan
        plan_fn = self._action_library.get(best_action, self._plan_wait)
        return plan_fn(best_params, current_state)

    def _generate_candidates(
        self,
        goal: Goal,
        state: Layer12D,
        world: WorldModel
    ) -> List[Tuple[str, dict]]:
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

    def _compute_forward_score(
        self,
        action: str,
        params: dict,
        state: Layer12D,
        world: WorldModel
    ) -> float:
        """
        Compute forward feasibility score sf ∈ [0,1].

        sf measures: Is this action physically executable?
        - Joint limits, collision risk, energy requirements
        """
        sf = 0.7  # Base feasibility

        # O3_EXECUTION: Motor readiness
        sf += state[2] * 0.15

        # O12_ABSOLVING: Safety constraints reduce feasibility
        sf -= state[11] * 0.3

        # Check obstacles for move actions
        if action == "move_to":
            obstacles = world.get_obstacles()
            if any(o["distance"] < 0.5 for o in obstacles):
                sf *= 0.5  # Reduce if obstacles nearby

        # Grasp needs object perception
        if action == "grasp":
            sf *= 0.5 + state[4] * 0.5  # O5_COGNITION

        return float(np.clip(sf, 0.0, 1.0))

    def _compute_backward_score(
        self,
        action: str,
        params: dict,
        goal: Goal,
        cognitive_mode: VrittiResult
    ) -> float:
        """
        Compute backward goal-achievement score sb ∈ [0,1].

        sb measures: Does this action achieve the goal?
        - Goal alignment, task completion, constraint satisfaction
        """
        sb = 0.5  # Base goal alignment

        # Pramana (valid cognition) boosts confidence
        if cognitive_mode.dominant == "pramana":
            sb += 0.2

        # Action-goal matching
        goal_lower = goal.description.lower()

        if action == "move_to":
            if "move" in goal_lower or "go" in goal_lower:
                sb += 0.3
            if goal.target_pose is not None:
                sb += 0.2  # Has specific target

        elif action == "grasp":
            if "grasp" in goal_lower or "pick" in goal_lower:
                sb += 0.4

        elif action == "release":
            if "release" in goal_lower or "place" in goal_lower or "put" in goal_lower:
                sb += 0.4

        elif action == "wait":
            if "stop" in goal_lower or "wait" in goal_lower:
                sb += 0.3
            else:
                sb -= 0.2  # Waiting usually doesn't achieve goal

        return float(np.clip(sb, 0.0, 1.0))

    def get_last_action_scores(self) -> List[ActionScore]:
        """Get BCVF scores from last planning cycle."""
        return self._last_action_scores

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

    Implements:
    - BCVF (B1-B3): Action selection via Consistency Lagrangian
    - SCC (S1-S9): Real-time semantic coherence monitoring
    - Full Chitta-Vritti analysis for cognitive mode

    The SCC monitor tracks:
    - S1: Per-layer coherence
    - S2: Global coherence
    - S5: Semantic entropy
    - S6: Entropy rate (spike detection)
    - S9: Safety coherence
    """

    def __init__(self, config: Optional[TierConfig] = None):
        super().__init__(config)
        self.encoder = FusionEncoder()
        self.world_model = WorldModel()
        self.planner = TaskPlanner()
        self.nl_interface = NaturalLanguageInterface()

        # SCC monitor for coherence tracking (S1-S9)
        self._scc_monitor = SCCMonitor(SCCConfig(
            coherence_threshold=0.5,
            entropy_spike_threshold=0.3,
            imbalance_threshold=0.5,
        ))

        # Vritti state
        self._accumulated_smrti = 0.0
        self._last_vritti: Optional[VrittiResult] = None
        self._last_coherence: Optional[CoherenceResult] = None

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

        Process:
        1. Encode sensors to 12D (uses USE formulas)
        2. SCC: Monitor coherence (S1-S9)
        3. Chitta-Vritti: Analyze cognitive mode
        4. BCVF: Plan actions (B1-B3)

        Args:
            sensor_frame: Current sensor data
            command: Optional natural language command

        Returns:
            Plan to be executed by R2/R1 tiers
        """
        # O5 + O11: Full perception (uses USE U1-U4)
        layer_12d = self.encoder.encode(sensor_frame)
        self._metrics.layer_12d = layer_12d

        # Mirror balance propagation
        layer_12d = propagate_to_mirror_12d(layer_12d)

        # SCC: Monitor coherence (S1-S9)
        self._last_coherence = self._scc_monitor.update(layer_12d)

        # S6: Check for entropy spike (potential anomaly)
        if self._scc_monitor.detect_entropy_spike():
            # Reduce action confidence when entropy spikes
            layer_12d[11] = max(layer_12d[11], 0.5)  # Boost O12_ABSOLVING

        # S3: Check coherence threshold
        if not self._last_coherence.is_valid:
            # Low coherence: be more cautious
            layer_12d[11] = max(layer_12d[11], 0.7)  # Strong safety activation

        # v2.8: Cognitive mode analysis
        vritti_result, self._accumulated_smrti = compute_vritti(
            layer_12d=layer_12d,
            sensor_coherence=self.encoder.get_coherence_score(),
            accumulated_smrti=self._accumulated_smrti
        )
        self._last_vritti = vritti_result

        # O9: Update world model
        self.world_model.update(layer_12d, sensor_frame)

        # O8: Goal processing
        if command:
            goal = self.nl_interface.parse(command)
            self.planner.push_goal(goal)

        # O7: Planning with BCVF (B1-B3)
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

    @property
    def current_coherence(self) -> Optional[CoherenceResult]:
        """Get last SCC coherence result (S1-S9)."""
        return self._last_coherence

    def is_coherent(self) -> bool:
        """Check if current state passes coherence threshold (S3)."""
        return self._scc_monitor.is_coherent()

    def get_safety_level(self) -> float:
        """Get S9 safety coherence level."""
        return self._scc_monitor.get_safety_level()

    def get_weakest_layers(self, n: int = 3) -> List[int]:
        """Get indices of n weakest layers from SCC analysis."""
        return self._scc_monitor.get_weakest_layers(n)

    def get_coherence_trend(self) -> float:
        """Get coherence trend (positive = improving)."""
        return self._scc_monitor.get_trend()

    def get_action_scores(self) -> List[ActionScore]:
        """Get BCVF scores from last planning cycle."""
        return self.planner.get_last_action_scores()

    def reset(self) -> None:
        super().reset()
        self.encoder.reset()
        self._scc_monitor.reset()
        self._accumulated_smrti = 0.0
        self._last_vritti = None
        self._last_coherence = None
