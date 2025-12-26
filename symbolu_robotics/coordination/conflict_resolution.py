"""
Conflict Resolution with BCVF/SCC
==================================

Distributed conflict resolution for multi-robot systems.

Uses:
- BCVF (B1-B3): Score resolution strategies
- SCC (S1-S9): Monitor conflict state and resolution progress

O12_ABSOLVING: Safety-critical conflict avoidance.
"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple, Callable, Any
from enum import Enum
import time
import numpy as np

from symbolu_robotics.formulas.bcvf import (
    BCVFScorer,
    BCVFConfig,
    ActionScore,
    score_action_candidates,
)
from symbolu_robotics.formulas.scc import (
    SCCMonitor,
    SCCConfig,
    CoherenceResult,
    compute_cosine_similarity,
)


class ConflictType(Enum):
    """Types of multi-robot conflicts."""
    PATH_CROSSING = "path_crossing"  # Robots' paths intersect
    RESOURCE_CONTENTION = "resource_contention"  # Both need same resource
    GOAL_OVERLAP = "goal_overlap"  # Same goal target
    WORKSPACE_OVERLAP = "workspace_overlap"  # Overlapping work areas
    COMMUNICATION_INTERFERENCE = "communication_interference"
    PRIORITY_DEADLOCK = "priority_deadlock"  # Circular priority


class ResolutionStrategy(Enum):
    """Resolution strategies."""
    PRIORITY_YIELD = "priority_yield"  # Lower priority yields
    TEMPORAL_OFFSET = "temporal_offset"  # Delay one robot
    SPATIAL_AVOIDANCE = "spatial_avoidance"  # Reroute one robot
    RESOURCE_SHARING = "resource_sharing"  # Take turns
    TASK_REALLOCATION = "task_reallocation"  # Reassign task
    MUTUAL_STOP = "mutual_stop"  # Both stop
    NEGOTIATED = "negotiated"  # Custom negotiated solution


class ConflictSeverity(Enum):
    """Conflict severity levels."""
    LOW = 1  # Minor inconvenience
    MEDIUM = 2  # Requires action
    HIGH = 3  # Imminent collision risk
    CRITICAL = 4  # Emergency stop required


@dataclass
class ConflictConfig:
    """Configuration for conflict resolution."""
    # BCVF for strategy scoring
    bcvf_config: BCVFConfig = field(default_factory=BCVFConfig)

    # SCC for conflict monitoring
    scc_config: SCCConfig = field(default_factory=lambda: SCCConfig(
        coherence_threshold=0.4,
        entropy_spike_threshold=0.4,
    ))

    # Resolution parameters
    max_resolution_time_ms: float = 100.0
    retry_limit: int = 3
    priority_weight: float = 0.3
    safety_weight: float = 0.4
    efficiency_weight: float = 0.3

    # Thresholds
    collision_distance: float = 0.5  # Min safe distance
    path_conflict_lookahead: float = 2.0  # Seconds
    resolution_coherence_threshold: float = 0.5


@dataclass
class Conflict:
    """Detected conflict between robots."""
    conflict_id: str
    conflict_type: ConflictType
    severity: ConflictSeverity

    # Involved parties
    robot_a: str
    robot_b: str

    # Conflict details
    position: Tuple[float, float, float] = (0.0, 0.0, 0.0)
    time_to_conflict: float = 0.0  # Seconds until conflict occurs
    resource_id: Optional[str] = None

    # Resolution
    resolved: bool = False
    resolution: Optional[ResolutionStrategy] = None
    resolution_details: Dict[str, Any] = field(default_factory=dict)

    # Timing
    detected_at: float = field(default_factory=time.time)
    resolved_at: Optional[float] = None

    # Metrics
    coherence_at_detection: float = 0.0
    coherence_at_resolution: float = 0.0


@dataclass
class ResolutionResult:
    """Result of conflict resolution attempt."""
    conflict_id: str
    success: bool
    strategy: Optional[ResolutionStrategy] = None

    # Actions for each robot
    robot_a_action: Dict[str, Any] = field(default_factory=dict)
    robot_b_action: Dict[str, Any] = field(default_factory=dict)

    # BCVF scores
    strategy_score: Optional[ActionScore] = None

    # Diagnostics
    resolution_time_ms: float = 0.0
    attempts: int = 1
    failure_reason: Optional[str] = None


@dataclass
class StrategyCandidate:
    """Candidate resolution strategy with scores."""
    strategy: ResolutionStrategy
    forward_score: float  # sf: Will it work?
    backward_score: float  # sb: Is it efficient?
    priority_score: float
    safety_score: float
    details: Dict[str, Any] = field(default_factory=dict)


class ConflictResolver:
    """
    BCVF/SCC-based conflict resolver.

    Detects conflicts between robots and selects optimal resolution
    strategies using BCVF scoring.

    BCVF Integration:
    - Forward score (sf): Will the strategy resolve the conflict?
      - Collision avoidance probability
      - Resource release timing
      - Path clearance
    - Backward score (sb): How efficient is the resolution?
      - Time delay introduced
      - Energy cost
      - Task completion impact

    SCC Integration:
    - Monitors conflict state coherence
    - Detects resolution progress
    - Triggers escalation on coherence drop

    Usage:
        resolver = ConflictResolver(robot_id="robot_1")

        # Detect conflicts
        conflicts = resolver.detect_conflicts(my_state, peer_states)

        for conflict in conflicts:
            # Resolve each conflict
            result = resolver.resolve(conflict)
            if result.success:
                apply_action(result.robot_a_action)
    """

    def __init__(
        self,
        robot_id: str,
        config: Optional[ConflictConfig] = None,
    ):
        self.robot_id = robot_id
        self.config = config or ConflictConfig()
        self._bcvf_scorer = BCVFScorer(self.config.bcvf_config)
        self._scc_monitor = SCCMonitor(self.config.scc_config)

        # Active conflicts
        self._conflicts: Dict[str, Conflict] = {}

        # Robot priorities (higher = more priority)
        self._priorities: Dict[str, float] = {}

        # Resolution history
        self._history: List[ResolutionResult] = []

    def set_priority(self, robot_id: str, priority: float) -> None:
        """Set robot priority for conflict resolution."""
        self._priorities[robot_id] = np.clip(priority, 0.0, 1.0)

    def detect_conflicts(
        self,
        my_position: Tuple[float, float, float],
        my_velocity: Tuple[float, float, float],
        my_path: Optional[List[Tuple[float, float, float]]] = None,
        peer_states: Optional[Dict[str, Dict[str, Any]]] = None,
    ) -> List[Conflict]:
        """
        Detect conflicts with other robots.

        Returns list of detected conflicts.
        """
        conflicts = []
        peer_states = peer_states or {}

        for peer_id, peer_state in peer_states.items():
            if peer_id == self.robot_id:
                continue

            peer_pos = peer_state.get("position", (0, 0, 0))
            peer_vel = peer_state.get("velocity", (0, 0, 0))
            peer_path = peer_state.get("path")

            # Check proximity conflict
            distance = np.linalg.norm(
                np.array(my_position) - np.array(peer_pos)
            )

            if distance < self.config.collision_distance:
                conflict = self._create_conflict(
                    ConflictType.WORKSPACE_OVERLAP,
                    peer_id,
                    position=tuple((np.array(my_position) + np.array(peer_pos)) / 2),
                    time_to_conflict=0.0,
                    severity=ConflictSeverity.HIGH,
                )
                conflicts.append(conflict)
                continue

            # Check path crossing
            if my_path and peer_path:
                crossing = self._check_path_crossing(my_path, peer_path)
                if crossing:
                    conflict = self._create_conflict(
                        ConflictType.PATH_CROSSING,
                        peer_id,
                        position=crossing[0],
                        time_to_conflict=crossing[1],
                        severity=ConflictSeverity.MEDIUM,
                    )
                    conflicts.append(conflict)

            # Check velocity-based future collision
            time_to_collision = self._predict_collision(
                my_position, my_velocity, peer_pos, peer_vel
            )
            if time_to_collision is not None and time_to_collision < self.config.path_conflict_lookahead:
                conflict = self._create_conflict(
                    ConflictType.PATH_CROSSING,
                    peer_id,
                    position=my_position,  # Approximate
                    time_to_conflict=time_to_collision,
                    severity=ConflictSeverity.MEDIUM if time_to_collision > 0.5 else ConflictSeverity.HIGH,
                )
                conflicts.append(conflict)

        # Update SCC with conflict state
        self._update_conflict_coherence(conflicts)

        return conflicts

    def _create_conflict(
        self,
        conflict_type: ConflictType,
        other_robot: str,
        position: Tuple[float, float, float],
        time_to_conflict: float,
        severity: ConflictSeverity,
        resource_id: Optional[str] = None,
    ) -> Conflict:
        """Create a new conflict record."""
        conflict_id = f"{self.robot_id}_{other_robot}_{int(time.time() * 1000)}"

        # Get current coherence
        if self._scc_monitor.history:
            coherence = self._scc_monitor.history[-1].global_coherence
        else:
            coherence = 1.0

        conflict = Conflict(
            conflict_id=conflict_id,
            conflict_type=conflict_type,
            severity=severity,
            robot_a=self.robot_id,
            robot_b=other_robot,
            position=position,
            time_to_conflict=time_to_conflict,
            resource_id=resource_id,
            coherence_at_detection=coherence,
        )

        self._conflicts[conflict_id] = conflict
        return conflict

    def _check_path_crossing(
        self,
        path_a: List[Tuple[float, float, float]],
        path_b: List[Tuple[float, float, float]],
    ) -> Optional[Tuple[Tuple[float, float, float], float]]:
        """Check if two paths cross. Returns (crossing_point, time_to_cross) or None."""
        if not path_a or not path_b:
            return None

        # Simple pairwise distance check
        for i, point_a in enumerate(path_a):
            for j, point_b in enumerate(path_b):
                dist = np.linalg.norm(np.array(point_a) - np.array(point_b))
                if dist < self.config.collision_distance:
                    # Estimate time (assuming uniform time between waypoints)
                    time_to_cross = i * 0.1  # Approximate
                    crossing = tuple((np.array(point_a) + np.array(point_b)) / 2)
                    return (crossing, time_to_cross)

        return None

    def _predict_collision(
        self,
        pos_a: Tuple[float, float, float],
        vel_a: Tuple[float, float, float],
        pos_b: Tuple[float, float, float],
        vel_b: Tuple[float, float, float],
    ) -> Optional[float]:
        """Predict time to collision based on current velocities."""
        # Relative position and velocity
        rel_pos = np.array(pos_b) - np.array(pos_a)
        rel_vel = np.array(vel_b) - np.array(vel_a)

        # Quadratic solution for collision time
        # |rel_pos + t * rel_vel| = collision_distance
        a = np.dot(rel_vel, rel_vel)
        b = 2 * np.dot(rel_pos, rel_vel)
        c = np.dot(rel_pos, rel_pos) - self.config.collision_distance**2

        if a < 1e-10:  # No relative motion
            if c < 0:  # Already colliding
                return 0.0
            return None

        discriminant = b**2 - 4*a*c
        if discriminant < 0:
            return None  # No collision

        t1 = (-b - np.sqrt(discriminant)) / (2*a)
        t2 = (-b + np.sqrt(discriminant)) / (2*a)

        # Return first positive time
        if t1 > 0:
            return float(t1)
        if t2 > 0:
            return float(t2)

        return None

    def resolve(self, conflict: Conflict) -> ResolutionResult:
        """
        Resolve a conflict using BCVF-scored strategies.

        Generates candidate strategies and selects best using BCVF.
        """
        start_time = time.time()

        # Generate candidate strategies
        candidates = self._generate_candidates(conflict)

        if not candidates:
            return ResolutionResult(
                conflict_id=conflict.conflict_id,
                success=False,
                failure_reason="No viable strategies",
            )

        # Score candidates using BCVF
        forward_scores = [c.forward_score for c in candidates]
        backward_scores = [c.backward_score for c in candidates]

        bcvf_scores = score_action_candidates(
            forward_scores,
            backward_scores,
            self.config.bcvf_config,
        )

        # Apply priority and safety weights
        for i, candidate in enumerate(candidates):
            weight = bcvf_scores[i].normalized_weight
            weight *= (1.0 + self.config.priority_weight * candidate.priority_score)
            weight *= (1.0 + self.config.safety_weight * candidate.safety_score)
            bcvf_scores[i].normalized_weight = weight

        # Renormalize
        total = sum(s.normalized_weight for s in bcvf_scores)
        for s in bcvf_scores:
            s.normalized_weight /= max(total, 1e-10)

        # Select best strategy
        best_idx = max(range(len(bcvf_scores)), key=lambda i: bcvf_scores[i].normalized_weight)
        best = candidates[best_idx]

        # Generate actions for each robot
        robot_a_action, robot_b_action = self._generate_actions(
            conflict, best
        )

        # Update conflict state
        conflict.resolved = True
        conflict.resolution = best.strategy
        conflict.resolution_details = best.details
        conflict.resolved_at = time.time()

        # Get resolution coherence
        if self._scc_monitor.history:
            conflict.coherence_at_resolution = self._scc_monitor.history[-1].global_coherence

        elapsed_ms = (time.time() - start_time) * 1000

        result = ResolutionResult(
            conflict_id=conflict.conflict_id,
            success=True,
            strategy=best.strategy,
            robot_a_action=robot_a_action,
            robot_b_action=robot_b_action,
            strategy_score=bcvf_scores[best_idx],
            resolution_time_ms=elapsed_ms,
        )

        self._history.append(result)
        return result

    def _generate_candidates(self, conflict: Conflict) -> List[StrategyCandidate]:
        """Generate candidate resolution strategies."""
        candidates = []

        # Get priorities
        priority_a = self._priorities.get(conflict.robot_a, 0.5)
        priority_b = self._priorities.get(conflict.robot_b, 0.5)

        # 1. Priority yield
        if priority_a != priority_b:
            higher = conflict.robot_a if priority_a > priority_b else conflict.robot_b
            candidates.append(StrategyCandidate(
                strategy=ResolutionStrategy.PRIORITY_YIELD,
                forward_score=0.9,  # Usually works
                backward_score=0.7,  # Moderate efficiency
                priority_score=abs(priority_a - priority_b),
                safety_score=0.8,
                details={"yielding_robot": conflict.robot_b if higher == conflict.robot_a else conflict.robot_a},
            ))

        # 2. Temporal offset
        if conflict.time_to_conflict > 0.5:  # Enough time to delay
            candidates.append(StrategyCandidate(
                strategy=ResolutionStrategy.TEMPORAL_OFFSET,
                forward_score=0.85,
                backward_score=0.6,  # Introduces delay
                priority_score=0.5,
                safety_score=0.9,
                details={"delay_seconds": min(conflict.time_to_conflict / 2, 2.0)},
            ))

        # 3. Spatial avoidance
        candidates.append(StrategyCandidate(
            strategy=ResolutionStrategy.SPATIAL_AVOIDANCE,
            forward_score=0.8,
            backward_score=0.65,  # Path deviation
            priority_score=0.5,
            safety_score=0.95,
            details={"avoidance_distance": self.config.collision_distance * 2},
        ))

        # 4. Mutual stop (emergency)
        if conflict.severity in (ConflictSeverity.HIGH, ConflictSeverity.CRITICAL):
            candidates.append(StrategyCandidate(
                strategy=ResolutionStrategy.MUTUAL_STOP,
                forward_score=1.0,  # Always works
                backward_score=0.3,  # Very inefficient
                priority_score=0.0,
                safety_score=1.0,  # Maximum safety
                details={"stop_duration": 1.0},
            ))

        # 5. Resource sharing (for resource conflicts)
        if conflict.conflict_type == ConflictType.RESOURCE_CONTENTION:
            candidates.append(StrategyCandidate(
                strategy=ResolutionStrategy.RESOURCE_SHARING,
                forward_score=0.75,
                backward_score=0.8,  # Fair and efficient
                priority_score=0.5,
                safety_score=0.85,
                details={"time_slice_seconds": 2.0},
            ))

        return candidates

    def _generate_actions(
        self,
        conflict: Conflict,
        strategy: StrategyCandidate,
    ) -> Tuple[Dict[str, Any], Dict[str, Any]]:
        """Generate actions for each robot based on strategy."""
        action_a: Dict[str, Any] = {"robot_id": conflict.robot_a}
        action_b: Dict[str, Any] = {"robot_id": conflict.robot_b}

        if strategy.strategy == ResolutionStrategy.PRIORITY_YIELD:
            yielding = strategy.details.get("yielding_robot")
            if yielding == conflict.robot_a:
                action_a["action"] = "yield"
                action_a["wait_seconds"] = 1.0
                action_b["action"] = "proceed"
            else:
                action_a["action"] = "proceed"
                action_b["action"] = "yield"
                action_b["wait_seconds"] = 1.0

        elif strategy.strategy == ResolutionStrategy.TEMPORAL_OFFSET:
            delay = strategy.details.get("delay_seconds", 1.0)
            # Lower priority robot delays
            priority_a = self._priorities.get(conflict.robot_a, 0.5)
            priority_b = self._priorities.get(conflict.robot_b, 0.5)

            if priority_a <= priority_b:
                action_a["action"] = "delay"
                action_a["delay_seconds"] = delay
                action_b["action"] = "proceed"
            else:
                action_a["action"] = "proceed"
                action_b["action"] = "delay"
                action_b["delay_seconds"] = delay

        elif strategy.strategy == ResolutionStrategy.SPATIAL_AVOIDANCE:
            avoidance = strategy.details.get("avoidance_distance", 1.0)
            # Both robots adjust path
            action_a["action"] = "avoid"
            action_a["offset"] = (avoidance / 2, 0, 0)
            action_b["action"] = "avoid"
            action_b["offset"] = (-avoidance / 2, 0, 0)

        elif strategy.strategy == ResolutionStrategy.MUTUAL_STOP:
            duration = strategy.details.get("stop_duration", 1.0)
            action_a["action"] = "stop"
            action_a["duration"] = duration
            action_b["action"] = "stop"
            action_b["duration"] = duration

        elif strategy.strategy == ResolutionStrategy.RESOURCE_SHARING:
            time_slice = strategy.details.get("time_slice_seconds", 2.0)
            # Alternate access
            action_a["action"] = "share"
            action_a["access_start"] = 0.0
            action_a["access_duration"] = time_slice
            action_b["action"] = "share"
            action_b["access_start"] = time_slice
            action_b["access_duration"] = time_slice

        return action_a, action_b

    def _update_conflict_coherence(self, conflicts: List[Conflict]) -> None:
        """Update SCC with conflict state."""
        # Create activation vector based on conflict severity
        activations = np.ones(12) * 0.5

        if conflicts:
            max_severity = max(c.severity.value for c in conflicts)
            # Higher severity = lower coherence
            activations *= (1.0 - max_severity * 0.2)

            # Boost O12_ABSOLVING (safety) when conflicts exist
            activations[11] = 0.8 + max_severity * 0.05

        self._scc_monitor.update(activations)

    def get_active_conflicts(self) -> List[Conflict]:
        """Get unresolved conflicts."""
        return [c for c in self._conflicts.values() if not c.resolved]

    def cleanup_resolved(self, max_age_seconds: float = 60.0) -> int:
        """Remove old resolved conflicts."""
        now = time.time()
        to_remove = [
            cid for cid, c in self._conflicts.items()
            if c.resolved and c.resolved_at and (now - c.resolved_at) > max_age_seconds
        ]
        for cid in to_remove:
            del self._conflicts[cid]
        return len(to_remove)

    def compute_o12_absolving(self) -> float:
        """
        Compute O12_ABSOLVING layer activation.

        Based on conflict state and resolution success.
        """
        active = self.get_active_conflicts()

        if not active:
            return 0.9  # No conflicts = high safety

        # Severity factor
        max_severity = max(c.severity.value for c in active)
        severity_factor = 1.0 - max_severity * 0.2

        # Resolution rate
        if self._history:
            success_count = sum(1 for r in self._history[-10:] if r.success)
            resolution_rate = success_count / min(len(self._history), 10)
        else:
            resolution_rate = 0.5

        # Coherence from SCC
        if self._scc_monitor.history:
            coherence = self._scc_monitor.history[-1].safety_coherence
        else:
            coherence = 0.5

        o12 = 0.3 * severity_factor + 0.3 * resolution_rate + 0.4 * coherence
        return float(np.clip(o12, 0.0, 1.0))
