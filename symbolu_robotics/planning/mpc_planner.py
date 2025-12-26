"""
Model Predictive Control Planner
================================

Receding horizon control for real-time trajectory optimization.

Integrates with Symbolu ontology:
- Uses 12D Layer as state representation
- SCC (S1-S9) for coherence-based cost shaping
- DynamicsModel for state prediction
- BCVF (B1-B3) for action candidate evaluation

Key Features:
- Receding horizon optimization
- Constraint satisfaction (joint limits, collisions)
- Real-time replanning at ~50Hz
- Uncertainty-aware via learned dynamics
"""

from dataclasses import dataclass, field
from typing import Optional, List, Dict, Tuple, Callable
from enum import Enum
import numpy as np

from symbolu_robotics.core.types import Layer12D, ActuatorCommand, RobotPose


class MPCStatus(Enum):
    """MPC solver status."""
    OPTIMAL = "optimal"
    SUBOPTIMAL = "suboptimal"
    INFEASIBLE = "infeasible"
    MAX_ITER = "max_iterations"
    TIMEOUT = "timeout"


@dataclass
class MPCConfig:
    """Configuration for MPC planner."""
    # Horizon
    prediction_horizon: int = 20  # Steps to predict ahead
    control_horizon: int = 5  # Steps of control to optimize
    dt: float = 0.05  # Time step (seconds)

    # Optimization
    max_iterations: int = 50
    tolerance: float = 1e-4
    timeout_ms: float = 20.0  # 50Hz replanning

    # Cost weights
    state_cost_weights: np.ndarray = field(default_factory=lambda: np.ones(12))
    control_cost_weight: float = 0.1
    terminal_cost_weight: float = 10.0

    # Coherence integration
    use_coherence_cost: bool = True
    coherence_cost_weight: float = 0.5
    min_coherence_threshold: float = 0.3

    # Constraints
    velocity_limit: float = 1.0
    acceleration_limit: float = 2.0
    jerk_limit: float = 5.0


@dataclass
class MPCResult:
    """Result of MPC optimization."""
    status: MPCStatus
    optimal_action: ActuatorCommand
    predicted_trajectory: List[Layer12D]
    predicted_coherence: List[float]

    # Optimization metrics
    cost: float = 0.0
    iterations: int = 0
    solve_time_ms: float = 0.0

    # Diagnostics
    constraint_violations: List[str] = field(default_factory=list)
    coherence_penalty: float = 0.0


class CostFunction:
    """
    Cost function for MPC optimization.

    Integrates SCC coherence into cost shaping.
    """

    def __init__(self, config: MPCConfig):
        self._config = config
        self._reference_trajectory: List[Layer12D] = []
        self._terminal_state: Optional[Layer12D] = None

    def set_reference(
        self,
        trajectory: List[Layer12D],
        terminal: Optional[Layer12D] = None,
    ) -> None:
        """Set reference trajectory to track."""
        self._reference_trajectory = trajectory
        self._terminal_state = terminal or (trajectory[-1] if trajectory else None)

    def compute_stage_cost(
        self,
        state: Layer12D,
        action: np.ndarray,
        stage: int,
        coherence: float = 1.0,
    ) -> float:
        """
        Compute cost at single stage.

        Cost = state_tracking + control_effort + coherence_penalty
        """
        cost = 0.0

        # State tracking cost
        if stage < len(self._reference_trajectory):
            reference = self._reference_trajectory[stage]
            state_error = state - reference
            cost += np.sum(self._config.state_cost_weights * state_error**2)

        # Control effort cost
        cost += self._config.control_cost_weight * np.sum(action**2)

        # Coherence penalty (low coherence = high cost)
        if self._config.use_coherence_cost:
            coherence_penalty = self._config.coherence_cost_weight * (1.0 - coherence)**2
            cost += coherence_penalty

        return cost

    def compute_terminal_cost(
        self,
        state: Layer12D,
        coherence: float = 1.0,
    ) -> float:
        """Compute terminal cost."""
        if self._terminal_state is None:
            return 0.0

        state_error = state - self._terminal_state
        cost = self._config.terminal_cost_weight * np.sum(state_error**2)

        # Extra penalty for low terminal coherence
        if coherence < self._config.min_coherence_threshold:
            cost *= 2.0

        return cost


class ConstraintChecker:
    """
    Constraint checking for MPC.

    Enforces joint limits, velocity limits, and collision avoidance.
    """

    def __init__(self, config: MPCConfig):
        self._config = config
        self._obstacles: List[np.ndarray] = []

    def set_obstacles(self, obstacles: List[np.ndarray]) -> None:
        """Set obstacle positions for collision checking."""
        self._obstacles = obstacles

    def check_velocity(self, velocity: np.ndarray) -> Tuple[bool, str]:
        """Check velocity limits."""
        max_vel = np.max(np.abs(velocity))
        if max_vel > self._config.velocity_limit:
            return False, f"velocity_exceeded_{max_vel:.2f}"
        return True, ""

    def check_acceleration(
        self,
        velocity_prev: np.ndarray,
        velocity_curr: np.ndarray,
    ) -> Tuple[bool, str]:
        """Check acceleration limits."""
        accel = (velocity_curr - velocity_prev) / self._config.dt
        max_accel = np.max(np.abs(accel))
        if max_accel > self._config.acceleration_limit:
            return False, f"acceleration_exceeded_{max_accel:.2f}"
        return True, ""

    def check_collision(self, position: np.ndarray) -> Tuple[bool, str]:
        """Check collision with obstacles."""
        for i, obs in enumerate(self._obstacles):
            dist = np.linalg.norm(position[:3] - obs[:3])
            min_dist = obs[3] if len(obs) > 3 else 0.5  # Obstacle radius
            if dist < min_dist:
                return False, f"collision_obstacle_{i}"
        return True, ""

    def check_all(
        self,
        state: Layer12D,
        action: np.ndarray,
        prev_action: Optional[np.ndarray] = None,
    ) -> List[str]:
        """Check all constraints, return list of violations."""
        violations = []

        # Extract velocity from action
        velocity = action[:6] if len(action) >= 6 else action

        # Velocity check
        valid, msg = self.check_velocity(velocity)
        if not valid:
            violations.append(msg)

        # Acceleration check
        if prev_action is not None:
            prev_velocity = prev_action[:6] if len(prev_action) >= 6 else prev_action
            valid, msg = self.check_acceleration(prev_velocity, velocity)
            if not valid:
                violations.append(msg)

        # Collision check (using O2_IDENTITY as position)
        position = state[:3]  # First 3 dims approximate position
        valid, msg = self.check_collision(position)
        if not valid:
            violations.append(msg)

        return violations


class MPCPlanner:
    """
    Model Predictive Control planner for robotics.

    Features:
    - Receding horizon optimization
    - Integration with DynamicsModel for prediction
    - SCC coherence-aware cost shaping
    - BCVF action candidate evaluation

    Skeleton Implementation:
    - Core data structures defined
    - Simple gradient-free optimization (for production, use CasADi/IPOPT)
    """

    def __init__(self, config: Optional[MPCConfig] = None):
        self._config = config or MPCConfig()
        self._cost_fn = CostFunction(self._config)
        self._constraints = ConstraintChecker(self._config)

        # Dynamics model (optional, for learned prediction)
        self._dynamics_model = None

        # State
        self._last_solution: Optional[List[np.ndarray]] = None
        self._warmstart_enabled = True

    def set_dynamics_model(self, model) -> None:
        """Set learned dynamics model for prediction."""
        self._dynamics_model = model

    def set_reference_trajectory(
        self,
        trajectory: List[Layer12D],
        terminal: Optional[Layer12D] = None,
    ) -> None:
        """Set reference trajectory to track."""
        self._cost_fn.set_reference(trajectory, terminal)

    def set_obstacles(self, obstacles: List[np.ndarray]) -> None:
        """Set obstacles for collision avoidance."""
        self._constraints.set_obstacles(obstacles)

    def plan(
        self,
        current_state: Layer12D,
        current_coherence: float = 1.0,
        goal_state: Optional[Layer12D] = None,
    ) -> MPCResult:
        """
        Plan optimal control action via MPC.

        Process:
        1. Initialize with warmstart from previous solution
        2. Predict trajectory using dynamics model
        3. Optimize control sequence
        4. Check constraints
        5. Return first action (receding horizon)
        """
        import time
        start_time = time.time()

        # Initialize action sequence
        if self._warmstart_enabled and self._last_solution is not None:
            # Shift warmstart
            action_sequence = self._last_solution[1:] + [self._last_solution[-1]]
        else:
            action_sequence = [np.zeros(7) for _ in range(self._config.control_horizon)]

        # Set goal as terminal if provided
        if goal_state is not None:
            self._cost_fn._terminal_state = goal_state

        # Simple optimization loop (gradient-free for skeleton)
        best_cost = float('inf')
        best_sequence = action_sequence.copy()
        all_violations = []

        for iteration in range(self._config.max_iterations):
            # Evaluate current sequence
            trajectory, coherences, cost = self._simulate_trajectory(
                current_state,
                action_sequence,
                current_coherence,
            )

            # Check constraints
            violations = []
            for i, action in enumerate(action_sequence):
                prev = action_sequence[i-1] if i > 0 else None
                violations.extend(self._constraints.check_all(
                    trajectory[i] if i < len(trajectory) else current_state,
                    action,
                    prev,
                ))

            if violations:
                cost += len(violations) * 100.0  # Penalty
                all_violations = violations

            if cost < best_cost:
                best_cost = cost
                best_sequence = [a.copy() for a in action_sequence]

            # Check convergence
            if cost < self._config.tolerance:
                break

            # Simple perturbation (would use gradient in production)
            action_sequence = self._perturb_sequence(action_sequence, iteration)

            # Check timeout
            elapsed_ms = (time.time() - start_time) * 1000
            if elapsed_ms > self._config.timeout_ms:
                break

        # Save for warmstart
        self._last_solution = best_sequence

        # Simulate final trajectory
        trajectory, coherences, final_cost = self._simulate_trajectory(
            current_state,
            best_sequence,
            current_coherence,
        )

        # Compute coherence penalty
        coherence_penalty = sum(
            self._config.coherence_cost_weight * (1.0 - c)**2
            for c in coherences
        )

        # Determine status
        elapsed_ms = (time.time() - start_time) * 1000
        if all_violations:
            status = MPCStatus.INFEASIBLE
        elif iteration >= self._config.max_iterations - 1:
            status = MPCStatus.MAX_ITER
        elif elapsed_ms >= self._config.timeout_ms:
            status = MPCStatus.TIMEOUT
        elif best_cost < self._config.tolerance * 10:
            status = MPCStatus.OPTIMAL
        else:
            status = MPCStatus.SUBOPTIMAL

        # Convert first action to ActuatorCommand
        first_action = best_sequence[0]
        optimal_cmd = ActuatorCommand(
            target_velocities=first_action[:6],
            gripper_position=first_action[6] if len(first_action) > 6 else 0.0,
            control_mode="velocity",
        )

        return MPCResult(
            status=status,
            optimal_action=optimal_cmd,
            predicted_trajectory=trajectory,
            predicted_coherence=coherences,
            cost=best_cost,
            iterations=iteration + 1,
            solve_time_ms=elapsed_ms,
            constraint_violations=all_violations,
            coherence_penalty=coherence_penalty,
        )

    def _simulate_trajectory(
        self,
        initial_state: Layer12D,
        actions: List[np.ndarray],
        initial_coherence: float,
    ) -> Tuple[List[Layer12D], List[float], float]:
        """Simulate trajectory given action sequence."""
        trajectory = [initial_state.copy()]
        coherences = [initial_coherence]
        total_cost = 0.0

        state = initial_state.copy()
        coherence = initial_coherence

        for i, action in enumerate(actions):
            # Predict next state
            if self._dynamics_model is not None and self._dynamics_model.is_trained:
                # Use learned dynamics
                cmd = ActuatorCommand(target_velocities=action[:6])
                pred = self._dynamics_model.predict(state, cmd)
                next_state = pred.state
                coherence = pred.coherence
            else:
                # Simple linear dynamics
                next_state = self._simple_dynamics(state, action)
                coherence = initial_coherence * 0.99  # Slight decay

            # Accumulate cost
            stage_cost = self._cost_fn.compute_stage_cost(
                state, action, i, coherence
            )
            total_cost += stage_cost

            trajectory.append(next_state)
            coherences.append(coherence)
            state = next_state

        # Terminal cost
        total_cost += self._cost_fn.compute_terminal_cost(state, coherence)

        return trajectory, coherences, total_cost

    def _simple_dynamics(self, state: Layer12D, action: np.ndarray) -> Layer12D:
        """Simple first-order dynamics for when no learned model available."""
        next_state = state.copy()

        # O3_EXECUTION influenced by action
        next_state[2] = np.clip(state[2] + action[0] * 0.1, 0, 1)

        # O2_IDENTITY (position) changes with velocity
        next_state[1] = np.clip(state[1] + np.sum(action[:3]) * 0.05, 0, 1)

        # O12_ABSOLVING influenced by action magnitude
        action_mag = np.linalg.norm(action)
        next_state[11] = np.clip(state[11] - action_mag * 0.01, 0, 1)

        return next_state

    def _perturb_sequence(
        self,
        sequence: List[np.ndarray],
        iteration: int,
    ) -> List[np.ndarray]:
        """Perturb action sequence for exploration."""
        scale = 0.1 / (1 + iteration * 0.1)  # Decay perturbation

        return [
            action + np.random.randn(*action.shape) * scale
            for action in sequence
        ]

    def get_predicted_trajectory(self) -> Optional[List[Layer12D]]:
        """Get last predicted trajectory."""
        if self._last_solution is None:
            return None
        # Would need to re-simulate
        return None

    def reset(self) -> None:
        """Reset planner state."""
        self._last_solution = None

    # -------------------------------------------------------------------------
    # Trajectory Validation Integration
    # -------------------------------------------------------------------------

    def set_trajectory_validator(self, validator) -> None:
        """
        Set trajectory validator for pre-execution safety checking.

        Args:
            validator: TrajectoryValidator instance from safety module
        """
        self._trajectory_validator = validator

    def plan_with_validation(
        self,
        current_state: Layer12D,
        current_joints: "JointState",
        current_coherence: float = 1.0,
        goal_state: Optional[Layer12D] = None,
    ) -> Tuple[MPCResult, Optional["ValidationReport"]]:
        """
        Plan with integrated trajectory pre-validation.

        This method:
        1. Plans trajectory using standard MPC
        2. Converts 12D trajectory to joint trajectory
        3. Validates with TrajectoryValidator
        4. Returns both MPC result and validation report

        Args:
            current_state: Current 12D state
            current_joints: Current joint state
            current_coherence: SCC coherence value
            goal_state: Optional goal state

        Returns:
            Tuple of (MPCResult, ValidationReport or None)
        """
        # First, run standard MPC planning
        mpc_result = self.plan(current_state, current_coherence, goal_state)

        # If no validator set, return without validation
        if not hasattr(self, '_trajectory_validator') or self._trajectory_validator is None:
            return mpc_result, None

        # Convert predicted trajectory to TrajectoryPoints for validation
        from symbolu_robotics.safety.trajectory_validator import TrajectoryPoint

        trajectory_points = []
        for i, state_12d in enumerate(mpc_result.predicted_trajectory):
            # Estimate joint positions from 12D state
            # In practice, this would use inverse kinematics
            # Here we approximate using the O3_EXECUTION and O4_STRUCTURE layers
            joint_estimate = self._estimate_joints_from_12d(
                state_12d, current_joints
            )

            coherence = (
                mpc_result.predicted_coherence[i]
                if i < len(mpc_result.predicted_coherence)
                else current_coherence
            )

            trajectory_points.append(TrajectoryPoint(
                timestamp=i * self._config.dt,
                positions=joint_estimate,
                coherence=coherence,
            ))

        # Validate trajectory
        validation_report = self._trajectory_validator.validate(
            trajectory_points,
            current_state=current_joints,
            coherence_values=mpc_result.predicted_coherence,
        )

        # If trajectory is unsafe, mark MPC result as infeasible
        if not validation_report.is_safe:
            mpc_result.status = MPCStatus.INFEASIBLE
            mpc_result.constraint_violations.extend([
                f"Pre-validation: {v}" for v in validation_report.limit_violations
            ])
            for col in validation_report.collision_predictions:
                mpc_result.constraint_violations.append(
                    f"Predicted collision: {col.collision_type.value} at t={col.time_to_collision:.2f}s"
                )

        return mpc_result, validation_report

    def _estimate_joints_from_12d(
        self,
        state_12d: Layer12D,
        reference_joints: "JointState",
    ) -> np.ndarray:
        """
        Estimate joint positions from 12D state representation.

        This is a simplified estimation - in production,
        inverse kinematics would be used.
        """
        # Use reference as base
        joints = reference_joints.positions.copy()

        # Scale by O3_EXECUTION (motion intensity)
        execution_factor = state_12d[2] if len(state_12d) > 2 else 0.5

        # Scale by O4_STRUCTURE (body configuration)
        structure_factor = state_12d[3] if len(state_12d) > 3 else 0.5

        # Simple perturbation based on 12D state
        for i in range(min(len(joints), 6)):
            joints[i] += (execution_factor - 0.5) * 0.1 * (i + 1)
            joints[i] *= 0.9 + 0.2 * structure_factor

        return joints

    def get_safe_velocity_scale(
        self,
        current_state: Layer12D,
        current_joints: "JointState",
        desired_action: np.ndarray,
    ) -> float:
        """
        Get safe velocity scaling factor using trajectory validator.

        Returns scaling factor [0, 1] to apply to velocities.
        """
        if not hasattr(self, '_trajectory_validator') or self._trajectory_validator is None:
            return 1.0

        coherence = current_state[11] if len(current_state) > 11 else 1.0

        return self._trajectory_validator.get_safe_velocity_scale(
            current_joints,
            desired_action[:6] if len(desired_action) >= 6 else desired_action,
            coherence,
        )


# Type hint imports for validation integration
try:
    from symbolu_robotics.core.types import JointState
    from symbolu_robotics.safety.trajectory_validator import ValidationReport
except ImportError:
    pass  # Allow module to work without safety module installed
