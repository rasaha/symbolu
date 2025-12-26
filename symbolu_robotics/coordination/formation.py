"""
Formation Control with USE Fusion
==================================

Multi-robot formation control using USE for position fusion
and SCC for formation coherence monitoring.

Uses:
- USE (U1-U4): Fuse position estimates from multiple robots
- SCC (S1-S9): Monitor formation coherence and detect breakup

O10_UNIFYING: Geometric coordination for collective behavior.
"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple, Callable
from enum import Enum
import numpy as np
import time

from symbolu_robotics.formulas.use import (
    USEFusion,
    USEConfig,
    FusionResult,
    compute_correlation_matrix,
    compute_coherence_fusion,
)
from symbolu_robotics.formulas.scc import (
    SCCMonitor,
    SCCConfig,
    CoherenceResult,
    compute_cosine_similarity,
)


class FormationType(Enum):
    """Standard formation patterns."""
    LINE = "line"
    V_SHAPE = "v_shape"
    CIRCLE = "circle"
    GRID = "grid"
    WEDGE = "wedge"
    COLUMN = "column"
    DIAMOND = "diamond"
    CUSTOM = "custom"


@dataclass
class FormationConfig:
    """Configuration for formation control."""
    # Formation parameters
    default_spacing: float = 1.0  # Meters between robots
    formation_type: FormationType = FormationType.LINE

    # USE config for position fusion
    use_config: USEConfig = field(default_factory=lambda: USEConfig(
        temporal_alpha=0.4,  # More responsive for position
        coherence_threshold=0.3,
    ))

    # SCC config for coherence monitoring
    scc_config: SCCConfig = field(default_factory=lambda: SCCConfig(
        coherence_threshold=0.5,
        entropy_spike_threshold=0.3,
    ))

    # Control parameters
    position_gain: float = 0.5  # P gain for position control
    velocity_limit: float = 1.0  # Max velocity
    cohesion_weight: float = 0.4  # Weight for cohesion force
    separation_weight: float = 0.3  # Weight for separation force
    alignment_weight: float = 0.3  # Weight for velocity alignment

    # Thresholds
    formation_tolerance: float = 0.1  # Position tolerance for "in formation"
    coherence_threshold: float = 0.6  # Min coherence to maintain formation
    breakup_threshold: float = 0.3  # Coherence below this = formation lost


@dataclass
class RobotFormationState:
    """State of a robot in the formation."""
    robot_id: str
    position: Tuple[float, float, float] = (0.0, 0.0, 0.0)
    velocity: Tuple[float, float, float] = (0.0, 0.0, 0.0)
    target_offset: Tuple[float, float, float] = (0.0, 0.0, 0.0)
    in_position: bool = False
    coherence: float = 1.0
    last_update: float = field(default_factory=time.time)


@dataclass
class FormationState:
    """Overall formation state."""
    center: Tuple[float, float, float] = (0.0, 0.0, 0.0)
    heading: float = 0.0  # Radians
    robots: Dict[str, RobotFormationState] = field(default_factory=dict)

    # Metrics
    coherence: float = 1.0  # Overall formation coherence
    is_formed: bool = False  # All robots in position?
    is_stable: bool = False  # Coherence above threshold?
    velocity: Tuple[float, float, float] = (0.0, 0.0, 0.0)


@dataclass
class FormationCommand:
    """Command for a robot to maintain formation."""
    robot_id: str
    target_position: Tuple[float, float, float]
    target_velocity: Tuple[float, float, float]
    priority: float = 1.0  # Higher = more important to follow


class FormationController:
    """
    USE/SCC-based formation controller.

    Maintains geometric formations using:
    - USE for fusing position data from multiple robots
    - SCC for monitoring formation coherence

    Implements Reynolds flocking rules:
    - Cohesion: Move toward formation center
    - Separation: Avoid collisions with neighbors
    - Alignment: Match velocity with neighbors

    Usage:
        controller = FormationController(robot_id="robot_1")

        # Set formation type
        controller.set_formation(FormationType.V_SHAPE, spacing=2.0)

        # Update with other robots' positions
        controller.update_peer("robot_2", position, velocity)

        # Get command for this robot
        cmd = controller.compute_command(my_position, my_velocity)
        # Apply cmd.target_velocity to actuators
    """

    def __init__(
        self,
        robot_id: str,
        config: Optional[FormationConfig] = None,
    ):
        self.robot_id = robot_id
        self.config = config or FormationConfig()

        # USE for position fusion
        self._use_fusion = USEFusion(self.config.use_config)

        # SCC for coherence monitoring
        self._scc_monitor = SCCMonitor(self.config.scc_config)

        # Formation state
        self._state = FormationState()
        self._formation_offsets: Dict[str, Tuple[float, float, float]] = {}
        self._robot_order: List[str] = []

        # My position in formation
        self._my_offset: Tuple[float, float, float] = (0.0, 0.0, 0.0)
        self._my_index: int = 0

    def set_formation(
        self,
        formation_type: FormationType,
        spacing: float = 1.0,
        robot_ids: Optional[List[str]] = None,
    ) -> None:
        """
        Configure formation pattern.

        Args:
            formation_type: Type of formation
            spacing: Distance between robots
            robot_ids: Ordered list of robot IDs (None = use current)
        """
        self.config.formation_type = formation_type
        self.config.default_spacing = spacing

        if robot_ids:
            self._robot_order = robot_ids
        elif self.robot_id not in self._robot_order:
            self._robot_order.append(self.robot_id)

        # Compute offsets for each robot
        self._formation_offsets = self._compute_formation_offsets(
            formation_type, spacing, self._robot_order
        )

        # Set my offset
        if self.robot_id in self._formation_offsets:
            self._my_offset = self._formation_offsets[self.robot_id]
            self._my_index = self._robot_order.index(self.robot_id)

    def _compute_formation_offsets(
        self,
        formation_type: FormationType,
        spacing: float,
        robot_ids: List[str],
    ) -> Dict[str, Tuple[float, float, float]]:
        """Compute offsets for each robot in formation."""
        n = len(robot_ids)
        offsets = {}

        if formation_type == FormationType.LINE:
            # Line along X axis, centered
            for i, rid in enumerate(robot_ids):
                x = (i - (n - 1) / 2) * spacing
                offsets[rid] = (x, 0.0, 0.0)

        elif formation_type == FormationType.V_SHAPE:
            # V formation
            for i, rid in enumerate(robot_ids):
                if i == 0:
                    offsets[rid] = (0.0, 0.0, 0.0)  # Leader
                else:
                    side = 1 if i % 2 == 1 else -1
                    row = (i + 1) // 2
                    x = -row * spacing * 0.7  # Back
                    y = side * row * spacing  # Side
                    offsets[rid] = (x, y, 0.0)

        elif formation_type == FormationType.CIRCLE:
            # Circle formation
            for i, rid in enumerate(robot_ids):
                angle = 2 * np.pi * i / n
                radius = spacing * n / (2 * np.pi)
                x = radius * np.cos(angle)
                y = radius * np.sin(angle)
                offsets[rid] = (x, y, 0.0)

        elif formation_type == FormationType.GRID:
            # Grid formation
            cols = int(np.ceil(np.sqrt(n)))
            for i, rid in enumerate(robot_ids):
                row = i // cols
                col = i % cols
                x = (col - (cols - 1) / 2) * spacing
                y = (row - (n // cols - 1) / 2) * spacing
                offsets[rid] = (x, y, 0.0)

        elif formation_type == FormationType.WEDGE:
            # Wedge/arrow formation
            for i, rid in enumerate(robot_ids):
                if i == 0:
                    offsets[rid] = (0.0, 0.0, 0.0)
                else:
                    row = i
                    x = -row * spacing * 0.5
                    y = (row if i % 2 == 1 else -row) * spacing * 0.5
                    offsets[rid] = (x, y, 0.0)

        elif formation_type == FormationType.COLUMN:
            # Column along Y axis
            for i, rid in enumerate(robot_ids):
                y = (i - (n - 1) / 2) * spacing
                offsets[rid] = (0.0, y, 0.0)

        elif formation_type == FormationType.DIAMOND:
            # Diamond formation
            for i, rid in enumerate(robot_ids):
                if i == 0:
                    offsets[rid] = (spacing, 0.0, 0.0)  # Front
                elif i == n - 1:
                    offsets[rid] = (-spacing, 0.0, 0.0)  # Back
                else:
                    side = 1 if i % 2 == 1 else -1
                    offsets[rid] = (0.0, side * spacing, 0.0)

        else:  # CUSTOM - keep existing or zero
            for rid in robot_ids:
                if rid not in offsets:
                    offsets[rid] = (0.0, 0.0, 0.0)

        return offsets

    def update_peer(
        self,
        robot_id: str,
        position: Tuple[float, float, float],
        velocity: Tuple[float, float, float] = (0.0, 0.0, 0.0),
        coherence: float = 1.0,
    ) -> None:
        """
        Update peer robot state.

        Uses USE to fuse position data for center estimation.
        """
        # Add to robot order if new
        if robot_id not in self._robot_order:
            self._robot_order.append(robot_id)
            # Recompute offsets
            self.set_formation(
                self.config.formation_type,
                self.config.default_spacing,
                self._robot_order,
            )

        # Update robot state
        if robot_id not in self._state.robots:
            self._state.robots[robot_id] = RobotFormationState(robot_id=robot_id)

        robot_state = self._state.robots[robot_id]
        robot_state.position = position
        robot_state.velocity = velocity
        robot_state.coherence = coherence
        robot_state.last_update = time.time()

        if robot_id in self._formation_offsets:
            robot_state.target_offset = self._formation_offsets[robot_id]

        # Update USE fusion with position as 12D vector
        position_12d = self._position_to_12d(position)
        self._use_fusion.update(robot_id, position_12d)

    def _position_to_12d(
        self,
        position: Tuple[float, float, float],
    ) -> np.ndarray:
        """Convert 3D position to 12D representation for USE fusion."""
        # Encode position in relevant layers
        layer = np.zeros(12)

        # O2_IDENTITY: Position encoding
        layer[1] = (position[0] + 10) / 20  # Normalize x
        layer[2] = (position[1] + 10) / 20  # Normalize y

        # O4_STRUCTURE: Spatial relation
        layer[3] = (position[2] + 5) / 10  # Normalize z

        # O10_UNIFYING: Coordination strength
        layer[9] = 0.5  # Default coordination level

        return np.clip(layer, 0, 1)

    def compute_formation_center(self) -> Tuple[float, float, float]:
        """
        Compute formation center using USE fusion.

        Returns weighted average position.
        """
        if not self._state.robots:
            return (0.0, 0.0, 0.0)

        # Get USE fusion result
        fusion_result = self._use_fusion.fuse()

        # Weight positions by coherence
        total_weight = 0.0
        center = np.zeros(3)

        for robot_id, robot_state in self._state.robots.items():
            weight = fusion_result.modality_weights.get(robot_id, 0.5)
            weight *= robot_state.coherence
            center += np.array(robot_state.position) * weight
            total_weight += weight

        if total_weight > 0:
            center /= total_weight

        self._state.center = tuple(center)
        return tuple(center)

    def compute_formation_coherence(self) -> float:
        """
        Compute formation coherence using SCC.

        High coherence = robots in correct positions.
        """
        if not self._state.robots:
            return 0.0

        center = self.compute_formation_center()

        # Compute position errors for each robot
        errors = []
        for robot_id, robot_state in self._state.robots.items():
            if robot_id not in self._formation_offsets:
                continue

            offset = self._formation_offsets[robot_id]
            expected = (
                center[0] + offset[0],
                center[1] + offset[1],
                center[2] + offset[2],
            )

            error = np.linalg.norm(
                np.array(robot_state.position) - np.array(expected)
            )
            errors.append(error)

            # Check if in position
            robot_state.in_position = error < self.config.formation_tolerance

        if not errors:
            return 0.0

        # Coherence inversely proportional to error
        avg_error = np.mean(errors)
        coherence = np.exp(-avg_error / self.config.default_spacing)

        # Update SCC with coherence as activation
        coherence_12d = np.ones(12) * coherence
        coherence_12d[9] = coherence  # O10_UNIFYING
        scc_result = self._scc_monitor.update(coherence_12d)

        self._state.coherence = float(coherence)
        self._state.is_stable = coherence >= self.config.coherence_threshold
        self._state.is_formed = all(
            r.in_position for r in self._state.robots.values()
        )

        return float(coherence)

    def compute_command(
        self,
        my_position: Tuple[float, float, float],
        my_velocity: Tuple[float, float, float] = (0.0, 0.0, 0.0),
    ) -> FormationCommand:
        """
        Compute formation-keeping command for this robot.

        Uses Reynolds flocking rules weighted by USE coherence.
        """
        # Update my state
        self.update_peer(self.robot_id, my_position, my_velocity)

        # Compute formation center
        center = self.compute_formation_center()

        # Target position
        target = (
            center[0] + self._my_offset[0],
            center[1] + self._my_offset[1],
            center[2] + self._my_offset[2],
        )

        # Position error
        error = np.array(target) - np.array(my_position)

        # Cohesion: Move toward formation position
        cohesion = error * self.config.cohesion_weight

        # Separation: Avoid nearby robots
        separation = np.zeros(3)
        for robot_id, robot_state in self._state.robots.items():
            if robot_id == self.robot_id:
                continue

            diff = np.array(my_position) - np.array(robot_state.position)
            dist = np.linalg.norm(diff)

            if dist < self.config.default_spacing * 0.8 and dist > 0:
                # Too close, push away
                separation += (diff / dist) * (1.0 - dist / self.config.default_spacing)

        separation *= self.config.separation_weight

        # Alignment: Match velocity with neighbors
        alignment = np.zeros(3)
        if len(self._state.robots) > 1:
            avg_velocity = np.mean([
                np.array(r.velocity)
                for r in self._state.robots.values()
            ], axis=0)
            alignment = (avg_velocity - np.array(my_velocity)) * self.config.alignment_weight

        # Combine forces
        target_velocity = cohesion + separation + alignment

        # Apply velocity limit
        speed = np.linalg.norm(target_velocity)
        if speed > self.config.velocity_limit:
            target_velocity = target_velocity / speed * self.config.velocity_limit

        # Compute priority based on coherence
        coherence = self.compute_formation_coherence()
        priority = 0.5 + 0.5 * coherence  # Higher coherence = higher priority

        return FormationCommand(
            robot_id=self.robot_id,
            target_position=target,
            target_velocity=tuple(target_velocity),
            priority=priority,
        )

    def get_state(self) -> FormationState:
        """Get current formation state."""
        self.compute_formation_coherence()
        return self._state

    def detect_breakup(self) -> bool:
        """Detect if formation has broken up."""
        coherence = self.compute_formation_coherence()
        return coherence < self.config.breakup_threshold

    def compute_o10_unifying(self) -> float:
        """
        Compute O10_UNIFYING layer activation.

        Based on formation coherence and stability.
        """
        if not self._state.robots:
            return 0.1

        # Formation coherence
        coherence = self._state.coherence

        # Stability (from SCC)
        if self._scc_monitor.history:
            stability = 1.0 - abs(self._scc_monitor.history[-1].momentum)
        else:
            stability = 0.5

        # Coverage (robots in position)
        in_position = sum(1 for r in self._state.robots.values() if r.in_position)
        coverage = in_position / max(len(self._state.robots), 1)

        # Combine
        o10 = 0.4 * coherence + 0.3 * stability + 0.3 * coverage
        return float(np.clip(o10, 0.0, 1.0))
