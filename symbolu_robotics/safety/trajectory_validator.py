"""
Trajectory Pre-Validation and Predictive Safety
================================================

Validates trajectories BEFORE execution to ensure safety.

Key Features:
- Pre-execution trajectory validation
- Predictive collision detection (look-ahead)
- Joint limit, velocity, acceleration, jerk checking
- Workspace boundary enforcement
- SCC coherence-based safety confidence
- BCVF scoring for trajectory quality

O12_ABSOLVING: Safety constraints enforcement through prediction.
"""

from dataclasses import dataclass, field
from typing import Optional, List, Dict, Tuple, Any, Callable
from enum import Enum
import numpy as np

from symbolu_robotics.core.types import (
    Layer12D,
    ActuatorCommand,
    RobotPose,
    JointState,
    SafetyLevel,
)


class ValidationResult(Enum):
    """Result of trajectory validation."""
    VALID = "valid"                     # Trajectory is safe
    VALID_WITH_WARNINGS = "warnings"    # Safe but with concerns
    INVALID_COLLISION = "collision"     # Predicted collision
    INVALID_LIMITS = "limits"           # Exceeds limits
    INVALID_WORKSPACE = "workspace"     # Outside workspace
    INVALID_COHERENCE = "coherence"     # Low coherence
    INVALID_JERK = "jerk"               # Excessive jerk


class CollisionType(Enum):
    """Type of predicted collision."""
    SELF_COLLISION = "self"
    OBSTACLE_COLLISION = "obstacle"
    WORKSPACE_BOUNDARY = "workspace"
    HUMAN_PROXIMITY = "human"


@dataclass
class JointLimits:
    """Joint limit configuration."""
    position_min: np.ndarray = field(default_factory=lambda: np.full(6, -np.pi))
    position_max: np.ndarray = field(default_factory=lambda: np.full(6, np.pi))
    velocity_max: np.ndarray = field(default_factory=lambda: np.full(6, 2.0))
    acceleration_max: np.ndarray = field(default_factory=lambda: np.full(6, 5.0))
    jerk_max: np.ndarray = field(default_factory=lambda: np.full(6, 20.0))
    effort_max: np.ndarray = field(default_factory=lambda: np.full(6, 100.0))


@dataclass
class WorkspaceBounds:
    """Workspace boundary configuration."""
    x_min: float = -2.0
    x_max: float = 2.0
    y_min: float = -2.0
    y_max: float = 2.0
    z_min: float = 0.0
    z_max: float = 2.0

    # Restricted zones (list of (center, radius) tuples)
    restricted_zones: List[Tuple[np.ndarray, float]] = field(default_factory=list)


@dataclass
class TrajectoryValidatorConfig:
    """Configuration for trajectory validator."""
    # Joint limits
    joint_limits: JointLimits = field(default_factory=JointLimits)

    # Workspace bounds
    workspace_bounds: WorkspaceBounds = field(default_factory=WorkspaceBounds)

    # Timing
    dt: float = 0.01  # Time step for trajectory discretization
    prediction_horizon: float = 2.0  # Look-ahead time (seconds)

    # Safety margins
    position_margin: float = 0.05  # Radians from limit
    velocity_margin: float = 0.1   # Fraction of max
    collision_margin: float = 0.1  # Meters
    human_safety_distance: float = 0.5  # Meters from human

    # Coherence integration (SCC)
    use_coherence_validation: bool = True
    min_coherence_threshold: float = 0.4
    coherence_weight: float = 0.3

    # Validation strictness
    allow_warnings: bool = True
    max_warnings: int = 3

    # Self-collision checking
    check_self_collision: bool = True
    self_collision_pairs: List[Tuple[int, int]] = field(
        default_factory=lambda: [(0, 3), (1, 4), (2, 5)]  # Joint pairs to check
    )


@dataclass
class TrajectoryPoint:
    """Single point in a trajectory."""
    timestamp: float
    positions: np.ndarray
    velocities: Optional[np.ndarray] = None
    accelerations: Optional[np.ndarray] = None
    end_effector_pose: Optional[RobotPose] = None
    coherence: float = 1.0


@dataclass
class CollisionPrediction:
    """Predicted collision along trajectory."""
    collision_type: CollisionType
    time_to_collision: float  # Seconds until collision
    collision_point: np.ndarray  # 3D point
    severity: float  # 0-1, higher = more severe
    joint_index: Optional[int] = None  # If joint-specific
    obstacle_id: Optional[str] = None  # If obstacle collision


@dataclass
class ValidationReport:
    """Complete validation report for a trajectory."""
    result: ValidationResult
    is_safe: bool
    safety_score: float  # 0-1, higher = safer

    # Detailed results
    limit_violations: List[str] = field(default_factory=list)
    collision_predictions: List[CollisionPrediction] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)

    # Per-point validation
    point_validations: List[bool] = field(default_factory=list)

    # Coherence analysis
    mean_coherence: float = 1.0
    min_coherence: float = 1.0
    coherence_valid: bool = True

    # Timing
    validation_time_ms: float = 0.0

    # Safe trajectory (if modifications needed)
    safe_trajectory: Optional[List[TrajectoryPoint]] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "result": self.result.value,
            "is_safe": self.is_safe,
            "safety_score": self.safety_score,
            "limit_violations": self.limit_violations,
            "num_collisions": len(self.collision_predictions),
            "warnings": self.warnings,
            "mean_coherence": self.mean_coherence,
            "validation_time_ms": self.validation_time_ms,
        }


class TrajectoryValidator:
    """
    Pre-execution trajectory validation with predictive safety.

    Validates trajectories BEFORE they are sent to actuators,
    predicting potential collisions and limit violations.

    Integration:
    - O12_ABSOLVING: Safety constraint enforcement
    - SCC (S1-S9): Coherence-based safety confidence
    - Predictive collision detection along trajectory

    Usage:
        validator = TrajectoryValidator()

        # Validate before execution
        report = validator.validate(trajectory)
        if report.is_safe:
            execute(trajectory)
        else:
            handle_unsafe(report)
    """

    def __init__(
        self,
        config: Optional[TrajectoryValidatorConfig] = None,
        forward_kinematics: Optional[Callable[[np.ndarray], RobotPose]] = None,
    ):
        self.config = config or TrajectoryValidatorConfig()
        self._forward_kinematics = forward_kinematics or self._default_fk

        # Obstacle map for collision checking
        self._obstacles: List[Tuple[np.ndarray, float]] = []

        # Human position tracking
        self._human_position: Optional[np.ndarray] = None
        self._human_velocity: Optional[np.ndarray] = None

        # Cached last validation
        self._last_report: Optional[ValidationReport] = None

    def validate(
        self,
        trajectory: List[TrajectoryPoint],
        current_state: Optional[JointState] = None,
        coherence_values: Optional[List[float]] = None,
    ) -> ValidationReport:
        """
        Validate trajectory before execution.

        Args:
            trajectory: List of trajectory points
            current_state: Current robot state (for continuity check)
            coherence_values: SCC coherence values per point

        Returns:
            ValidationReport with detailed safety analysis
        """
        import time
        start_time = time.time()

        if not trajectory:
            return ValidationReport(
                result=ValidationResult.VALID,
                is_safe=True,
                safety_score=1.0,
            )

        # Initialize report
        limit_violations = []
        collision_predictions = []
        warnings = []
        point_validations = []

        # Validate each point
        prev_point = None
        prev_prev_point = None

        for i, point in enumerate(trajectory):
            point_valid = True

            # 1. Joint position limits
            pos_valid, pos_violations = self._check_position_limits(point.positions)
            if not pos_valid:
                point_valid = False
                limit_violations.extend(pos_violations)

            # 2. Velocity limits
            if point.velocities is not None:
                vel_valid, vel_violations = self._check_velocity_limits(point.velocities)
                if not vel_valid:
                    point_valid = False
                    limit_violations.extend(vel_violations)
            elif prev_point is not None:
                # Compute velocity from positions
                dt = point.timestamp - prev_point.timestamp
                if dt > 0:
                    computed_vel = (point.positions - prev_point.positions) / dt
                    vel_valid, vel_violations = self._check_velocity_limits(computed_vel)
                    if not vel_valid:
                        point_valid = False
                        limit_violations.extend(vel_violations)

            # 3. Acceleration limits
            if point.accelerations is not None:
                acc_valid, acc_violations = self._check_acceleration_limits(
                    point.accelerations
                )
                if not acc_valid:
                    point_valid = False
                    limit_violations.extend(acc_violations)

            # 4. Jerk limits (needs 3 consecutive points)
            if prev_point is not None and prev_prev_point is not None:
                jerk_valid, jerk_violations = self._check_jerk_limits(
                    prev_prev_point, prev_point, point
                )
                if not jerk_valid:
                    point_valid = False
                    limit_violations.extend(jerk_violations)

            # 5. Workspace bounds
            ee_pose = point.end_effector_pose or self._forward_kinematics(point.positions)
            ws_valid, ws_violations = self._check_workspace_bounds(ee_pose)
            if not ws_valid:
                point_valid = False
                limit_violations.extend(ws_violations)

            # 6. Collision prediction
            collisions = self._predict_collisions(point, ee_pose)
            if collisions:
                collision_predictions.extend(collisions)
                # Immediate collisions invalidate point
                for col in collisions:
                    if col.time_to_collision < 0.1:
                        point_valid = False

            # 7. Self-collision check
            if self.config.check_self_collision:
                self_col = self._check_self_collision(point.positions)
                if self_col:
                    point_valid = False
                    collision_predictions.append(self_col)

            # 8. Human proximity check
            human_col = self._check_human_proximity(ee_pose, point.timestamp)
            if human_col:
                if human_col.severity > 0.8:
                    point_valid = False
                else:
                    warnings.append(
                        f"Human proximity warning at t={point.timestamp:.2f}s"
                    )
                collision_predictions.append(human_col)

            point_validations.append(point_valid)

            # Update history
            prev_prev_point = prev_point
            prev_point = point

        # Coherence analysis
        coherence_valid = True
        mean_coherence = 1.0
        min_coherence = 1.0

        if self.config.use_coherence_validation:
            if coherence_values:
                mean_coherence = float(np.mean(coherence_values))
                min_coherence = float(np.min(coherence_values))
            else:
                # Use point coherence values
                coherences = [p.coherence for p in trajectory]
                mean_coherence = float(np.mean(coherences))
                min_coherence = float(np.min(coherences))

            if min_coherence < self.config.min_coherence_threshold:
                coherence_valid = False
                warnings.append(
                    f"Low coherence detected: min={min_coherence:.2f} "
                    f"(threshold={self.config.min_coherence_threshold})"
                )

        # Determine overall result
        num_invalid = sum(1 for v in point_validations if not v)
        has_collisions = any(
            c.time_to_collision < 0.5 for c in collision_predictions
        )

        if has_collisions:
            result = ValidationResult.INVALID_COLLISION
            is_safe = False
        elif num_invalid > 0:
            if limit_violations:
                if any("jerk" in v.lower() for v in limit_violations):
                    result = ValidationResult.INVALID_JERK
                elif any("workspace" in v.lower() for v in limit_violations):
                    result = ValidationResult.INVALID_WORKSPACE
                else:
                    result = ValidationResult.INVALID_LIMITS
            else:
                result = ValidationResult.INVALID_LIMITS
            is_safe = False
        elif not coherence_valid:
            result = ValidationResult.INVALID_COHERENCE
            is_safe = False
        elif warnings and len(warnings) > self.config.max_warnings:
            result = ValidationResult.VALID_WITH_WARNINGS
            is_safe = self.config.allow_warnings
        elif warnings:
            result = ValidationResult.VALID_WITH_WARNINGS
            is_safe = True
        else:
            result = ValidationResult.VALID
            is_safe = True

        # Compute safety score
        safety_score = self._compute_safety_score(
            point_validations,
            collision_predictions,
            mean_coherence,
            limit_violations,
        )

        elapsed_ms = (time.time() - start_time) * 1000

        report = ValidationReport(
            result=result,
            is_safe=is_safe,
            safety_score=safety_score,
            limit_violations=list(set(limit_violations)),  # Deduplicate
            collision_predictions=collision_predictions,
            warnings=warnings,
            point_validations=point_validations,
            mean_coherence=mean_coherence,
            min_coherence=min_coherence,
            coherence_valid=coherence_valid,
            validation_time_ms=elapsed_ms,
        )

        self._last_report = report
        return report

    def validate_command(
        self,
        command: ActuatorCommand,
        current_state: JointState,
        coherence: float = 1.0,
    ) -> ValidationReport:
        """
        Validate a single actuator command.

        Creates a mini-trajectory and validates it.
        """
        # Create trajectory from current to commanded
        trajectory = []

        if command.target_positions is not None:
            # Position command
            trajectory = [
                TrajectoryPoint(
                    timestamp=0.0,
                    positions=current_state.positions,
                    velocities=current_state.velocities,
                    coherence=coherence,
                ),
                TrajectoryPoint(
                    timestamp=self.config.dt,
                    positions=command.target_positions,
                    coherence=coherence,
                ),
            ]
        elif command.target_velocities is not None:
            # Velocity command - project forward
            num_steps = int(self.config.prediction_horizon / self.config.dt)
            positions = current_state.positions.copy()

            for i in range(num_steps):
                t = i * self.config.dt
                trajectory.append(TrajectoryPoint(
                    timestamp=t,
                    positions=positions.copy(),
                    velocities=command.target_velocities,
                    coherence=coherence,
                ))
                positions += command.target_velocities * self.config.dt
        else:
            # No movement command
            return ValidationReport(
                result=ValidationResult.VALID,
                is_safe=True,
                safety_score=1.0,
            )

        return self.validate(trajectory)

    def predict_trajectory_safety(
        self,
        trajectory: List[TrajectoryPoint],
        look_ahead_time: Optional[float] = None,
    ) -> List[CollisionPrediction]:
        """
        Predict potential collisions along trajectory.

        Returns list of collision predictions ordered by time.
        """
        look_ahead = look_ahead_time or self.config.prediction_horizon
        predictions = []

        for point in trajectory:
            if point.timestamp > look_ahead:
                break

            ee_pose = point.end_effector_pose or self._forward_kinematics(
                point.positions
            )

            # Check all collision types
            collisions = self._predict_collisions(point, ee_pose)
            predictions.extend(collisions)

            # Self-collision
            self_col = self._check_self_collision(point.positions)
            if self_col:
                predictions.append(self_col)

            # Human proximity
            human_col = self._check_human_proximity(ee_pose, point.timestamp)
            if human_col:
                predictions.append(human_col)

        # Sort by time to collision
        predictions.sort(key=lambda c: c.time_to_collision)

        return predictions

    def set_obstacles(
        self,
        obstacles: List[Tuple[np.ndarray, float]],
    ) -> None:
        """
        Update obstacle map for collision checking.

        Args:
            obstacles: List of (center, radius) tuples
        """
        self._obstacles = obstacles

    def set_human_state(
        self,
        position: Optional[np.ndarray],
        velocity: Optional[np.ndarray] = None,
    ) -> None:
        """Update tracked human position and velocity."""
        self._human_position = position
        self._human_velocity = velocity

    def get_safe_velocity_scale(
        self,
        current_state: JointState,
        desired_velocity: np.ndarray,
        coherence: float = 1.0,
    ) -> float:
        """
        Compute safe velocity scaling factor.

        Returns a factor [0, 1] to scale velocity for safety.
        """
        # Base scale from velocity limits
        limits = self.config.joint_limits.velocity_max
        velocity_ratio = np.abs(desired_velocity) / limits
        max_ratio = np.max(velocity_ratio)

        if max_ratio > 1.0:
            base_scale = 1.0 / max_ratio
        else:
            base_scale = 1.0

        # Reduce based on coherence
        coherence_scale = 0.5 + 0.5 * coherence

        # Reduce based on human proximity
        human_scale = 1.0
        if self._human_position is not None:
            ee_pose = self._forward_kinematics(current_state.positions)
            ee_pos = np.array([ee_pose.x, ee_pose.y, ee_pose.z])
            dist = np.linalg.norm(ee_pos - self._human_position)

            if dist < self.config.human_safety_distance:
                human_scale = dist / self.config.human_safety_distance

        return float(base_scale * coherence_scale * human_scale)

    def compute_o12_absolving(self) -> float:
        """
        Compute O12_ABSOLVING layer activation.

        Based on current safety state from last validation.
        """
        if self._last_report is None:
            return 0.1  # Low default

        report = self._last_report

        # Higher O12 when more safety concerns exist
        collision_factor = min(1.0, len(report.collision_predictions) / 5.0)
        violation_factor = min(1.0, len(report.limit_violations) / 10.0)
        coherence_factor = 1.0 - report.mean_coherence

        # O12 increases with safety concerns
        o12 = (
            0.4 * collision_factor +
            0.3 * violation_factor +
            0.3 * coherence_factor
        )

        return float(np.clip(o12, 0.0, 1.0))

    # -------------------------------------------------------------------------
    # Private Methods
    # -------------------------------------------------------------------------

    def _check_position_limits(
        self,
        positions: np.ndarray,
    ) -> Tuple[bool, List[str]]:
        """Check joint position limits with margin."""
        violations = []
        limits = self.config.joint_limits
        margin = self.config.position_margin

        for i, pos in enumerate(positions):
            if pos < limits.position_min[i] + margin:
                violations.append(
                    f"Joint {i} position {pos:.3f} below min "
                    f"{limits.position_min[i]:.3f}"
                )
            elif pos > limits.position_max[i] - margin:
                violations.append(
                    f"Joint {i} position {pos:.3f} above max "
                    f"{limits.position_max[i]:.3f}"
                )

        return len(violations) == 0, violations

    def _check_velocity_limits(
        self,
        velocities: np.ndarray,
    ) -> Tuple[bool, List[str]]:
        """Check joint velocity limits with margin."""
        violations = []
        limits = self.config.joint_limits
        margin_factor = 1.0 - self.config.velocity_margin

        for i, vel in enumerate(velocities):
            max_vel = limits.velocity_max[i] * margin_factor
            if abs(vel) > max_vel:
                violations.append(
                    f"Joint {i} velocity {vel:.3f} exceeds limit {max_vel:.3f}"
                )

        return len(violations) == 0, violations

    def _check_acceleration_limits(
        self,
        accelerations: np.ndarray,
    ) -> Tuple[bool, List[str]]:
        """Check joint acceleration limits."""
        violations = []
        limits = self.config.joint_limits

        for i, acc in enumerate(accelerations):
            if abs(acc) > limits.acceleration_max[i]:
                violations.append(
                    f"Joint {i} acceleration {acc:.3f} exceeds limit "
                    f"{limits.acceleration_max[i]:.3f}"
                )

        return len(violations) == 0, violations

    def _check_jerk_limits(
        self,
        p0: TrajectoryPoint,
        p1: TrajectoryPoint,
        p2: TrajectoryPoint,
    ) -> Tuple[bool, List[str]]:
        """Check jerk (derivative of acceleration) limits."""
        violations = []
        limits = self.config.joint_limits

        dt1 = p1.timestamp - p0.timestamp
        dt2 = p2.timestamp - p1.timestamp

        if dt1 <= 0 or dt2 <= 0:
            return True, []

        # Compute accelerations
        v0 = (p1.positions - p0.positions) / dt1
        v1 = (p2.positions - p1.positions) / dt2

        a0 = (v1 - v0) / ((dt1 + dt2) / 2)

        # For jerk, we'd need more points, so estimate from acceleration change
        # This is a simplified check
        jerk_estimate = np.abs(a0) / dt2

        for i, jerk in enumerate(jerk_estimate):
            if jerk > limits.jerk_max[i]:
                violations.append(
                    f"Joint {i} jerk {jerk:.3f} exceeds limit "
                    f"{limits.jerk_max[i]:.3f}"
                )

        return len(violations) == 0, violations

    def _check_workspace_bounds(
        self,
        pose: RobotPose,
    ) -> Tuple[bool, List[str]]:
        """Check if end-effector is within workspace bounds."""
        violations = []
        bounds = self.config.workspace_bounds

        if pose.x < bounds.x_min or pose.x > bounds.x_max:
            violations.append(f"X position {pose.x:.3f} outside workspace")
        if pose.y < bounds.y_min or pose.y > bounds.y_max:
            violations.append(f"Y position {pose.y:.3f} outside workspace")
        if pose.z < bounds.z_min or pose.z > bounds.z_max:
            violations.append(f"Z position {pose.z:.3f} outside workspace")

        # Check restricted zones
        ee_pos = np.array([pose.x, pose.y, pose.z])
        for center, radius in bounds.restricted_zones:
            dist = np.linalg.norm(ee_pos - center)
            if dist < radius:
                violations.append(
                    f"End-effector in restricted zone at {center}"
                )

        return len(violations) == 0, violations

    def _predict_collisions(
        self,
        point: TrajectoryPoint,
        ee_pose: RobotPose,
    ) -> List[CollisionPrediction]:
        """Predict collisions with obstacles."""
        predictions = []
        margin = self.config.collision_margin

        ee_pos = np.array([ee_pose.x, ee_pose.y, ee_pose.z])

        for i, (center, radius) in enumerate(self._obstacles):
            dist = np.linalg.norm(ee_pos - center) - radius

            if dist < margin:
                # Collision or near-collision
                severity = max(0.0, 1.0 - dist / margin)
                predictions.append(CollisionPrediction(
                    collision_type=CollisionType.OBSTACLE_COLLISION,
                    time_to_collision=point.timestamp,
                    collision_point=center,
                    severity=severity,
                    obstacle_id=f"obstacle_{i}",
                ))

        return predictions

    def _check_self_collision(
        self,
        positions: np.ndarray,
    ) -> Optional[CollisionPrediction]:
        """Check for self-collision between joint pairs."""
        # Simplified self-collision check based on joint configuration
        # In practice, this would use the full kinematic chain

        for j1, j2 in self.config.self_collision_pairs:
            if j1 < len(positions) and j2 < len(positions):
                # Check if joints are in collision-prone configuration
                angle_diff = abs(positions[j1] - positions[j2])

                # Heuristic: certain angle combinations are problematic
                if angle_diff < 0.1 and abs(positions[j1]) > 2.5:
                    return CollisionPrediction(
                        collision_type=CollisionType.SELF_COLLISION,
                        time_to_collision=0.0,
                        collision_point=np.zeros(3),
                        severity=0.8,
                        joint_index=j1,
                    )

        return None

    def _check_human_proximity(
        self,
        ee_pose: RobotPose,
        timestamp: float,
    ) -> Optional[CollisionPrediction]:
        """Check proximity to tracked human."""
        if self._human_position is None:
            return None

        ee_pos = np.array([ee_pose.x, ee_pose.y, ee_pose.z])

        # Predict human position if velocity available
        human_pos = self._human_position.copy()
        if self._human_velocity is not None:
            human_pos += self._human_velocity * timestamp

        dist = np.linalg.norm(ee_pos - human_pos)
        safety_dist = self.config.human_safety_distance

        if dist < safety_dist:
            severity = 1.0 - (dist / safety_dist)
            return CollisionPrediction(
                collision_type=CollisionType.HUMAN_PROXIMITY,
                time_to_collision=timestamp,
                collision_point=human_pos,
                severity=severity,
            )

        return None

    def _compute_safety_score(
        self,
        point_validations: List[bool],
        collisions: List[CollisionPrediction],
        mean_coherence: float,
        violations: List[str],
    ) -> float:
        """Compute overall safety score [0, 1]."""
        if not point_validations:
            return 1.0

        # Base score from valid points
        valid_ratio = sum(point_validations) / len(point_validations)

        # Penalize collisions
        collision_penalty = min(1.0, len(collisions) * 0.1)

        # Penalize violations
        violation_penalty = min(1.0, len(violations) * 0.05)

        # Weight by coherence
        coherence_factor = 0.5 + 0.5 * mean_coherence

        score = (
            0.5 * valid_ratio +
            0.2 * (1.0 - collision_penalty) +
            0.1 * (1.0 - violation_penalty) +
            0.2 * coherence_factor
        )

        return float(np.clip(score, 0.0, 1.0))

    def _default_fk(self, positions: np.ndarray) -> RobotPose:
        """Default forward kinematics (placeholder)."""
        # Simplified FK - in practice, this would be robot-specific
        # Assumes a simple arm configuration
        if len(positions) >= 3:
            x = 0.5 * np.cos(positions[0]) * np.cos(positions[1])
            y = 0.5 * np.sin(positions[0]) * np.cos(positions[1])
            z = 0.3 + 0.5 * np.sin(positions[1])
        else:
            x, y, z = 0.0, 0.0, 0.3

        return RobotPose(x=x, y=y, z=z)


class PredictiveSafetyMonitor:
    """
    Continuous predictive safety monitoring.

    Runs alongside execution to predict safety issues
    and trigger preemptive actions.
    """

    def __init__(
        self,
        validator: TrajectoryValidator,
        prediction_interval_ms: float = 50.0,
    ):
        self._validator = validator
        self._prediction_interval_ms = prediction_interval_ms

        # Current trajectory being monitored
        self._current_trajectory: Optional[List[TrajectoryPoint]] = None
        self._trajectory_start_time: float = 0.0

        # Prediction state
        self._last_predictions: List[CollisionPrediction] = []
        self._safety_level: SafetyLevel = SafetyLevel.NOMINAL

        # Callbacks
        self._on_collision_predicted: Optional[
            Callable[[CollisionPrediction], None]
        ] = None
        self._on_safety_level_change: Optional[
            Callable[[SafetyLevel], None]
        ] = None

    def start_monitoring(
        self,
        trajectory: List[TrajectoryPoint],
    ) -> None:
        """Start monitoring a trajectory during execution."""
        import time
        self._current_trajectory = trajectory
        self._trajectory_start_time = time.time()
        self._safety_level = SafetyLevel.NOMINAL

    def update(
        self,
        current_time: float,
        current_state: JointState,
    ) -> Tuple[SafetyLevel, List[CollisionPrediction]]:
        """
        Update predictions based on current state.

        Call this at regular intervals during execution.

        Returns:
            (safety_level, predicted_collisions)
        """
        if self._current_trajectory is None:
            return SafetyLevel.NOMINAL, []

        # Get remaining trajectory from current time
        elapsed = current_time - self._trajectory_start_time
        remaining = [
            p for p in self._current_trajectory
            if p.timestamp > elapsed
        ]

        if not remaining:
            self._current_trajectory = None
            return SafetyLevel.NOMINAL, []

        # Predict collisions
        predictions = self._validator.predict_trajectory_safety(remaining)
        self._last_predictions = predictions

        # Determine safety level
        new_level = self._compute_safety_level(predictions)

        # Trigger callback if level changed
        if new_level != self._safety_level:
            self._safety_level = new_level
            if self._on_safety_level_change:
                self._on_safety_level_change(new_level)

        # Trigger collision callbacks
        for pred in predictions:
            if pred.time_to_collision < 0.5 and self._on_collision_predicted:
                self._on_collision_predicted(pred)

        return self._safety_level, predictions

    def set_collision_callback(
        self,
        callback: Callable[[CollisionPrediction], None],
    ) -> None:
        """Set callback for predicted collisions."""
        self._on_collision_predicted = callback

    def set_safety_level_callback(
        self,
        callback: Callable[[SafetyLevel], None],
    ) -> None:
        """Set callback for safety level changes."""
        self._on_safety_level_change = callback

    def _compute_safety_level(
        self,
        predictions: List[CollisionPrediction],
    ) -> SafetyLevel:
        """Compute safety level from predictions."""
        if not predictions:
            return SafetyLevel.NOMINAL

        # Find most urgent prediction
        most_urgent = min(predictions, key=lambda p: p.time_to_collision)

        if most_urgent.time_to_collision < 0.1:
            return SafetyLevel.EMERGENCY_STOP
        elif most_urgent.time_to_collision < 0.3:
            return SafetyLevel.RESTRICTED
        elif most_urgent.time_to_collision < 1.0:
            return SafetyLevel.CAUTION
        else:
            return SafetyLevel.NOMINAL
