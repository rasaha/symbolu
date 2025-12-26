"""
Shared World Model with USE Fusion
===================================

Collaborative world model building from multiple robot observations.

Uses:
- USE (U1-U4): Fuse observations from multiple robots
- SCC (S1-S9): Monitor world model coherence and consistency

O9_WITNESSES: Distributed scene understanding.
"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple, Any, Set
from enum import Enum
import time
import numpy as np

from symbolu_robotics.formulas.use import (
    USEFusion,
    USEConfig,
    FusionResult,
    compute_correlation_matrix,
    compute_confidence,
)
from symbolu_robotics.formulas.scc import (
    SCCMonitor,
    SCCConfig,
    CoherenceResult,
    compute_cosine_similarity,
)


class CellState(Enum):
    """State of a world cell."""
    UNKNOWN = "unknown"
    FREE = "free"
    OCCUPIED = "occupied"
    DYNAMIC = "dynamic"  # Moving obstacle
    UNCERTAIN = "uncertain"


class ObservationType(Enum):
    """Types of observations."""
    LIDAR = "lidar"
    CAMERA = "camera"
    ULTRASONIC = "ultrasonic"
    INFRARED = "infrared"
    FUSION = "fusion"  # Pre-fused observation


@dataclass
class SharedWorldConfig:
    """Configuration for shared world model."""
    # Grid parameters
    resolution: float = 0.1  # Meters per cell
    world_size: Tuple[float, float] = (20.0, 20.0)  # World dimensions
    origin: Tuple[float, float] = (-10.0, -10.0)  # World origin

    # USE config for observation fusion
    use_config: USEConfig = field(default_factory=lambda: USEConfig(
        temporal_alpha=0.3,
        coherence_threshold=0.25,
    ))

    # SCC config for coherence monitoring
    scc_config: SCCConfig = field(default_factory=lambda: SCCConfig(
        coherence_threshold=0.4,
    ))

    # Observation parameters
    observation_decay: float = 0.95  # Decay factor per second
    min_confidence: float = 0.1
    max_observations_per_cell: int = 10

    # Fusion thresholds
    agreement_threshold: float = 0.6  # Min agreement to confirm state
    conflict_threshold: float = 0.3  # Max disagreement before uncertain


@dataclass
class Observation:
    """Single observation from a robot."""
    robot_id: str
    observation_type: ObservationType
    timestamp: float = field(default_factory=time.time)

    # What was observed
    position: Tuple[float, float] = (0.0, 0.0)
    cell_state: CellState = CellState.UNKNOWN
    confidence: float = 1.0

    # Additional data
    velocity: Optional[Tuple[float, float]] = None  # For dynamic objects
    object_class: Optional[str] = None
    raw_data: Optional[np.ndarray] = None


@dataclass
class WorldCell:
    """Single cell in the world grid."""
    x: int
    y: int
    center: Tuple[float, float]

    # State
    state: CellState = CellState.UNKNOWN
    confidence: float = 0.0

    # Observations
    observations: List[Observation] = field(default_factory=list)
    last_observed: float = 0.0

    # Fusion result
    agreement_score: float = 0.0  # How much observers agree
    contributing_robots: Set[str] = field(default_factory=set)

    # Semantic info
    object_class: Optional[str] = None
    velocity: Optional[Tuple[float, float]] = None


@dataclass
class WorldModelState:
    """Overall world model state."""
    timestamp: float = field(default_factory=time.time)
    coherence: float = 0.0
    coverage: float = 0.0  # Fraction of cells observed
    num_robots: int = 0
    num_observations: int = 0
    agreement_score: float = 0.0  # Average agreement


class SharedWorldModel:
    """
    USE/SCC-based shared world model.

    Fuses observations from multiple robots to build a coherent
    world representation.

    USE Integration:
    - U1: Correlation between robot observations
    - U2: Coherence-weighted fusion of observations
    - U3: Temporal smoothing of cell states
    - U4: Confidence estimation for each cell

    SCC Integration:
    - Monitors world model coherence
    - Detects conflicting observations
    - Tracks model stability

    Usage:
        world = SharedWorldModel(robot_id="robot_1")

        # Add observations
        world.add_observation(Observation(
            robot_id="robot_1",
            position=(1.0, 2.0),
            cell_state=CellState.OCCUPIED,
        ))

        # Receive observations from peers
        world.add_observation(peer_observation)

        # Query the model
        state = world.get_cell_state(1.0, 2.0)
        print(f"Cell state: {state.state}, confidence: {state.confidence}")
    """

    def __init__(
        self,
        robot_id: str,
        config: Optional[SharedWorldConfig] = None,
    ):
        self.robot_id = robot_id
        self.config = config or SharedWorldConfig()

        # USE for observation fusion
        self._use_fusion = USEFusion(self.config.use_config)

        # SCC for coherence monitoring
        self._scc_monitor = SCCMonitor(self.config.scc_config)

        # Grid dimensions
        self._nx = int(self.config.world_size[0] / self.config.resolution)
        self._ny = int(self.config.world_size[1] / self.config.resolution)

        # Grid storage (sparse - only store observed cells)
        self._cells: Dict[Tuple[int, int], WorldCell] = {}

        # Robot positions for coverage computation
        self._robot_positions: Dict[str, Tuple[float, float]] = {}

        # Statistics
        self._total_observations = 0
        self._last_update = time.time()

    def world_to_grid(
        self,
        x: float,
        y: float,
    ) -> Tuple[int, int]:
        """Convert world coordinates to grid indices."""
        gx = int((x - self.config.origin[0]) / self.config.resolution)
        gy = int((y - self.config.origin[1]) / self.config.resolution)
        return (np.clip(gx, 0, self._nx - 1), np.clip(gy, 0, self._ny - 1))

    def grid_to_world(
        self,
        gx: int,
        gy: int,
    ) -> Tuple[float, float]:
        """Convert grid indices to world coordinates (cell center)."""
        x = self.config.origin[0] + (gx + 0.5) * self.config.resolution
        y = self.config.origin[1] + (gy + 0.5) * self.config.resolution
        return (x, y)

    def add_observation(self, observation: Observation) -> None:
        """
        Add an observation to the world model.

        Uses USE to fuse with existing observations.
        """
        # Get grid coordinates
        gx, gy = self.world_to_grid(observation.position[0], observation.position[1])
        key = (gx, gy)

        # Create cell if needed
        if key not in self._cells:
            center = self.grid_to_world(gx, gy)
            self._cells[key] = WorldCell(x=gx, y=gy, center=center)

        cell = self._cells[key]

        # Add observation
        cell.observations.append(observation)
        cell.last_observed = observation.timestamp
        cell.contributing_robots.add(observation.robot_id)

        # Limit observations per cell
        if len(cell.observations) > self.config.max_observations_per_cell:
            cell.observations = cell.observations[-self.config.max_observations_per_cell:]

        # Fuse observations for this cell
        self._fuse_cell(cell)

        # Update robot position
        if observation.robot_id not in self._robot_positions:
            self._robot_positions[observation.robot_id] = observation.position

        self._total_observations += 1
        self._last_update = time.time()

        # Update world coherence
        self._update_world_coherence()

    def _fuse_cell(self, cell: WorldCell) -> None:
        """
        Fuse observations for a single cell using USE.

        Applies U1-U4 to combine observations.
        """
        if not cell.observations:
            return

        # Group observations by robot
        robot_observations: Dict[str, List[Observation]] = {}
        for obs in cell.observations:
            if obs.robot_id not in robot_observations:
                robot_observations[obs.robot_id] = []
            robot_observations[obs.robot_id].append(obs)

        # Convert to 12D vectors for USE
        modality_vectors: Dict[str, np.ndarray] = {}
        for robot_id, obs_list in robot_observations.items():
            # Use most recent observation
            latest = max(obs_list, key=lambda o: o.timestamp)
            modality_vectors[robot_id] = self._observation_to_12d(latest)

        if len(modality_vectors) < 1:
            return

        # U1: Compute correlation matrix
        if len(modality_vectors) > 1:
            R = compute_correlation_matrix(modality_vectors)
            # Agreement score = mean off-diagonal correlation
            mask = ~np.eye(R.shape[0], dtype=bool)
            cell.agreement_score = float(np.mean(np.abs(R[mask])))
        else:
            cell.agreement_score = 1.0

        # Determine cell state from observations
        state_votes: Dict[CellState, float] = {}
        total_confidence = 0.0

        for robot_id, obs_list in robot_observations.items():
            latest = max(obs_list, key=lambda o: o.timestamp)
            # Weight by recency
            age = time.time() - latest.timestamp
            decay = self.config.observation_decay ** age
            weight = latest.confidence * decay

            if latest.cell_state not in state_votes:
                state_votes[latest.cell_state] = 0.0
            state_votes[latest.cell_state] += weight
            total_confidence += weight

        # Normalize votes
        if total_confidence > 0:
            for state in state_votes:
                state_votes[state] /= total_confidence

        # Determine final state
        if state_votes:
            best_state = max(state_votes.items(), key=lambda x: x[1])

            if best_state[1] >= self.config.agreement_threshold:
                cell.state = best_state[0]
                cell.confidence = best_state[1] * cell.agreement_score
            elif cell.agreement_score < self.config.conflict_threshold:
                cell.state = CellState.UNCERTAIN
                cell.confidence = cell.agreement_score
            else:
                cell.state = best_state[0]
                cell.confidence = best_state[1] * 0.5

        # Check for dynamic objects
        velocities = [
            obs.velocity for obs in cell.observations
            if obs.velocity is not None
        ]
        if velocities:
            avg_vel = np.mean(velocities, axis=0)
            if np.linalg.norm(avg_vel) > 0.1:
                cell.state = CellState.DYNAMIC
                cell.velocity = tuple(avg_vel)

        # Object class (most common)
        classes = [
            obs.object_class for obs in cell.observations
            if obs.object_class is not None
        ]
        if classes:
            from collections import Counter
            cell.object_class = Counter(classes).most_common(1)[0][0]

    def _observation_to_12d(self, observation: Observation) -> np.ndarray:
        """Convert observation to 12D vector for USE fusion."""
        layer = np.zeros(12)

        # O1_POTENTIAL: Observation quality
        layer[0] = observation.confidence

        # O4_STRUCTURE: Cell state encoding
        state_encoding = {
            CellState.UNKNOWN: 0.0,
            CellState.FREE: 0.2,
            CellState.OCCUPIED: 0.8,
            CellState.DYNAMIC: 0.9,
            CellState.UNCERTAIN: 0.5,
        }
        layer[3] = state_encoding.get(observation.cell_state, 0.5)

        # O5_AGENCY: Sensor type encoding
        sensor_encoding = {
            ObservationType.LIDAR: 0.9,
            ObservationType.CAMERA: 0.8,
            ObservationType.ULTRASONIC: 0.6,
            ObservationType.INFRARED: 0.7,
            ObservationType.FUSION: 0.95,
        }
        layer[4] = sensor_encoding.get(observation.observation_type, 0.5)

        # O9_WITNESSES: Observation recency
        age = time.time() - observation.timestamp
        layer[8] = max(0, 1.0 - age / 60.0)  # Decay over 60 seconds

        return layer

    def _update_world_coherence(self) -> None:
        """Update SCC with world model state."""
        if not self._cells:
            return

        # Compute world model activation vector
        activations = np.zeros(12)

        # O9_WITNESSES: Overall coverage and agreement
        coverage = len(self._cells) / (self._nx * self._ny)
        avg_agreement = np.mean([c.agreement_score for c in self._cells.values()])
        avg_confidence = np.mean([c.confidence for c in self._cells.values()])

        activations[8] = coverage * avg_agreement
        activations[0] = avg_confidence

        # O4_STRUCTURE: Map completeness
        known_cells = sum(1 for c in self._cells.values() if c.state != CellState.UNKNOWN)
        activations[3] = known_cells / max(len(self._cells), 1)

        # O10_UNIFYING: Multi-robot contribution
        num_robots = len(self._robot_positions)
        activations[9] = min(1.0, num_robots / 5.0)

        self._scc_monitor.update(activations)

    def get_cell(
        self,
        x: float,
        y: float,
    ) -> Optional[WorldCell]:
        """Get cell at world coordinates."""
        gx, gy = self.world_to_grid(x, y)
        return self._cells.get((gx, gy))

    def get_cell_state(
        self,
        x: float,
        y: float,
    ) -> Tuple[CellState, float]:
        """Get cell state and confidence at world coordinates."""
        cell = self.get_cell(x, y)
        if cell is None:
            return (CellState.UNKNOWN, 0.0)
        return (cell.state, cell.confidence)

    def get_region(
        self,
        x_min: float,
        y_min: float,
        x_max: float,
        y_max: float,
    ) -> List[WorldCell]:
        """Get all cells in a region."""
        gx_min, gy_min = self.world_to_grid(x_min, y_min)
        gx_max, gy_max = self.world_to_grid(x_max, y_max)

        cells = []
        for gx in range(gx_min, gx_max + 1):
            for gy in range(gy_min, gy_max + 1):
                cell = self._cells.get((gx, gy))
                if cell is not None:
                    cells.append(cell)

        return cells

    def get_obstacles(
        self,
        min_confidence: float = 0.5,
    ) -> List[Tuple[float, float]]:
        """Get list of obstacle positions."""
        obstacles = []
        for cell in self._cells.values():
            if cell.state == CellState.OCCUPIED and cell.confidence >= min_confidence:
                obstacles.append(cell.center)
        return obstacles

    def get_free_space(
        self,
        min_confidence: float = 0.5,
    ) -> List[Tuple[float, float]]:
        """Get list of free cell positions."""
        free = []
        for cell in self._cells.values():
            if cell.state == CellState.FREE and cell.confidence >= min_confidence:
                free.append(cell.center)
        return free

    def get_model_state(self) -> WorldModelState:
        """Get overall model state."""
        if not self._cells:
            return WorldModelState()

        # Coherence from SCC
        if self._scc_monitor.history:
            coherence = self._scc_monitor.history[-1].global_coherence
        else:
            coherence = 0.0

        # Coverage
        coverage = len(self._cells) / (self._nx * self._ny)

        # Agreement
        avg_agreement = np.mean([c.agreement_score for c in self._cells.values()])

        return WorldModelState(
            timestamp=self._last_update,
            coherence=coherence,
            coverage=coverage,
            num_robots=len(self._robot_positions),
            num_observations=self._total_observations,
            agreement_score=avg_agreement,
        )

    def decay_observations(self) -> int:
        """Decay old observations and remove stale cells."""
        now = time.time()
        removed = 0

        for key in list(self._cells.keys()):
            cell = self._cells[key]

            # Decay confidence based on age
            age = now - cell.last_observed
            decay = self.config.observation_decay ** age
            cell.confidence *= decay

            # Remove very old/low confidence cells
            if cell.confidence < self.config.min_confidence and age > 60:
                del self._cells[key]
                removed += 1

        return removed

    def merge_map(
        self,
        other_cells: Dict[Tuple[int, int], WorldCell],
        source_robot: str,
    ) -> int:
        """
        Merge map data from another robot.

        Returns number of cells merged.
        """
        merged = 0

        for key, other_cell in other_cells.items():
            # Convert observations
            for obs in other_cell.observations:
                obs_copy = Observation(
                    robot_id=source_robot,
                    observation_type=obs.observation_type,
                    timestamp=obs.timestamp,
                    position=other_cell.center,
                    cell_state=obs.cell_state,
                    confidence=obs.confidence * 0.9,  # Slight confidence reduction
                )
                self.add_observation(obs_copy)
                merged += 1

        return merged

    def compute_o9_witnesses(self) -> float:
        """
        Compute O9_WITNESSES layer activation.

        Based on world model quality.
        """
        if not self._cells:
            return 0.1

        state = self.get_model_state()

        # Coverage contribution
        coverage_score = min(1.0, state.coverage * 10)  # Scale up

        # Agreement contribution
        agreement_score = state.agreement_score

        # Coherence contribution
        coherence_score = state.coherence

        # Multi-robot contribution
        robot_score = min(1.0, state.num_robots / 3.0)

        o9 = (
            0.25 * coverage_score +
            0.25 * agreement_score +
            0.25 * coherence_score +
            0.25 * robot_score
        )

        return float(np.clip(o9, 0.0, 1.0))
