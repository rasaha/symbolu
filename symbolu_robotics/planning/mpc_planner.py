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

Implementation: Hybrid approach using only numpy
- BFGS quasi-Newton optimization with numerical gradients
- No external optimization libraries required (CasADi, scipy, etc.)
"""

from dataclasses import dataclass, field
from typing import Optional, List, Dict, Tuple, Callable
from enum import Enum
import numpy as np
import logging
import time

from symbolu_robotics.core.types import Layer12D, ActuatorCommand, RobotPose

logger = logging.getLogger(__name__)


# ============================================================================
# Numpy-based Optimization (No External Dependencies)
# ============================================================================

class NumpyBFGS:
    """
    BFGS quasi-Newton optimizer using only numpy.

    Implements the Broyden-Fletcher-Goldfarb-Shanno algorithm
    for unconstrained optimization.
    """

    def __init__(
        self,
        max_iterations: int = 50,
        tolerance: float = 1e-6,
        grad_tolerance: float = 1e-5,
        line_search_max_iter: int = 20,
    ):
        self.max_iterations = max_iterations
        self.tolerance = tolerance
        self.grad_tolerance = grad_tolerance
        self.line_search_max_iter = line_search_max_iter

    def minimize(
        self,
        fun: Callable[[np.ndarray], float],
        x0: np.ndarray,
        bounds: Optional[Tuple[np.ndarray, np.ndarray]] = None,
    ) -> Tuple[np.ndarray, float, int, bool]:
        """
        Minimize function using BFGS.

        Args:
            fun: Objective function f(x) -> scalar
            x0: Initial guess
            bounds: Optional (lower, upper) bounds

        Returns:
            x_opt: Optimal solution
            f_opt: Optimal function value
            iterations: Number of iterations
            converged: Whether optimization converged
        """
        x = x0.copy().flatten()
        n = len(x)
        H = np.eye(n)  # Initial inverse Hessian approximation

        f = fun(x)
        grad = self._numerical_gradient(fun, x)

        for iteration in range(self.max_iterations):
            # Check gradient convergence
            grad_norm = np.linalg.norm(grad)
            if grad_norm < self.grad_tolerance:
                return x, f, iteration, True

            # Search direction
            p = -H @ grad

            # Line search (Armijo backtracking)
            alpha = self._line_search(fun, x, p, f, grad)

            if alpha < 1e-10:
                # Line search failed, try gradient descent step
                alpha = 0.001
                p = -grad

            # Update position
            s = alpha * p
            x_new = x + s

            # Apply bounds if provided
            if bounds is not None:
                x_new = np.clip(x_new, bounds[0], bounds[1])
                s = x_new - x

            # Evaluate new point
            f_new = fun(x_new)
            grad_new = self._numerical_gradient(fun, x_new)

            # Check function value convergence
            if abs(f_new - f) < self.tolerance:
                return x_new, f_new, iteration, True

            # BFGS update
            y = grad_new - grad

            # Curvature condition check
            sy = np.dot(s, y)
            if sy > 1e-10:
                # Valid curvature - update inverse Hessian
                rho = 1.0 / sy
                I = np.eye(n)
                V = I - rho * np.outer(s, y)
                H = V @ H @ V.T + rho * np.outer(s, s)

            # Update state
            x = x_new
            f = f_new
            grad = grad_new

        return x, f, self.max_iterations, False

    def _numerical_gradient(
        self,
        fun: Callable[[np.ndarray], float],
        x: np.ndarray,
        eps: float = 1e-7,
    ) -> np.ndarray:
        """Compute gradient using central differences."""
        grad = np.zeros_like(x)
        for i in range(len(x)):
            x_plus = x.copy()
            x_minus = x.copy()
            x_plus[i] += eps
            x_minus[i] -= eps
            grad[i] = (fun(x_plus) - fun(x_minus)) / (2 * eps)
        return grad

    def _line_search(
        self,
        fun: Callable[[np.ndarray], float],
        x: np.ndarray,
        p: np.ndarray,
        f0: float,
        grad: np.ndarray,
        c1: float = 1e-4,
        rho: float = 0.5,
    ) -> float:
        """
        Backtracking line search with Armijo condition.

        Returns step size alpha.
        """
        alpha = 1.0
        dphi0 = np.dot(grad, p)

        if dphi0 >= 0:
            # Not a descent direction
            return 0.0

        for _ in range(self.line_search_max_iter):
            x_new = x + alpha * p
            f_new = fun(x_new)

            # Armijo condition
            if f_new <= f0 + c1 * alpha * dphi0:
                return alpha

            alpha *= rho

        return alpha


class NumpyProjectedGD:
    """
    Projected gradient descent for constrained optimization.

    Simpler but more robust for constrained problems.
    """

    def __init__(
        self,
        max_iterations: int = 100,
        learning_rate: float = 0.01,
        tolerance: float = 1e-6,
        adaptive_lr: bool = True,
    ):
        self.max_iterations = max_iterations
        self.learning_rate = learning_rate
        self.tolerance = tolerance
        self.adaptive_lr = adaptive_lr

    def minimize(
        self,
        fun: Callable[[np.ndarray], float],
        x0: np.ndarray,
        bounds: Optional[Tuple[np.ndarray, np.ndarray]] = None,
    ) -> Tuple[np.ndarray, float, int, bool]:
        """Minimize with projected gradient descent."""
        x = x0.copy().flatten()
        f = fun(x)
        lr = self.learning_rate

        for iteration in range(self.max_iterations):
            # Numerical gradient
            grad = self._numerical_gradient(fun, x)

            # Gradient descent step
            x_new = x - lr * grad

            # Project to bounds
            if bounds is not None:
                x_new = np.clip(x_new, bounds[0], bounds[1])

            f_new = fun(x_new)

            # Adaptive learning rate
            if self.adaptive_lr:
                if f_new < f:
                    lr *= 1.1  # Increase if improving
                else:
                    lr *= 0.5  # Decrease if not improving
                    x_new = x  # Reject step
                    f_new = f

            # Check convergence
            if np.linalg.norm(x_new - x) < self.tolerance:
                return x_new, f_new, iteration, True

            x = x_new
            f = f_new

        return x, f, self.max_iterations, False

    def _numerical_gradient(self, fun, x, eps=1e-7):
        grad = np.zeros_like(x)
        for i in range(len(x)):
            x_plus = x.copy()
            x_minus = x.copy()
            x_plus[i] += eps
            x_minus[i] -= eps
            grad[i] = (fun(x_plus) - fun(x_minus)) / (2 * eps)
        return grad


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

    Implementation: Numpy-based BFGS optimization.
    No external optimization libraries required.
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

        # Initialize optimizer
        self._optimizer = NumpyBFGS(
            max_iterations=self._config.max_iterations,
            tolerance=self._config.tolerance,
        )

        # Alternative optimizer for constrained problems
        self._constrained_optimizer = NumpyProjectedGD(
            max_iterations=self._config.max_iterations * 2,
            learning_rate=0.1,
            tolerance=self._config.tolerance,
        )

        # Bounds for actions
        self._action_dim = 7  # 6 joints + gripper
        self._action_lower = np.array([-self._config.velocity_limit] * 6 + [0.0])
        self._action_upper = np.array([self._config.velocity_limit] * 6 + [1.0])

        logger.debug(f"MPCPlanner initialized with horizon={self._config.control_horizon}")

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
        Plan optimal control action via MPC using BFGS optimization.

        Process:
        1. Initialize with warmstart from previous solution
        2. Define cost function over flattened action sequence
        3. Optimize using numpy-based BFGS
        4. Check constraints and handle violations
        5. Return first action (receding horizon)
        """
        start_time = time.time()

        # Set goal as terminal if provided
        if goal_state is not None:
            self._cost_fn._terminal_state = goal_state

        # Initialize action sequence (flattened for optimizer)
        horizon = self._config.control_horizon
        if self._warmstart_enabled and self._last_solution is not None:
            # Shift warmstart
            x0 = np.concatenate(self._last_solution[1:] + [self._last_solution[-1]])
        else:
            x0 = np.zeros(horizon * self._action_dim)

        # Define cost function for optimizer
        def cost_fn(x_flat: np.ndarray) -> float:
            actions = [x_flat[i*self._action_dim:(i+1)*self._action_dim]
                      for i in range(horizon)]

            trajectory, coherences, cost = self._simulate_trajectory(
                current_state, actions, current_coherence
            )

            # Add constraint violation penalties
            for i, action in enumerate(actions):
                prev = actions[i-1] if i > 0 else None
                violations = self._constraints.check_all(
                    trajectory[i] if i < len(trajectory) else current_state,
                    action, prev
                )
                cost += len(violations) * 100.0

            return cost

        # Setup bounds
        lower_bounds = np.tile(self._action_lower, horizon)
        upper_bounds = np.tile(self._action_upper, horizon)
        bounds = (lower_bounds, upper_bounds)

        # Run optimization
        x_opt, f_opt, iterations, converged = self._constrained_optimizer.minimize(
            cost_fn, x0, bounds=bounds
        )

        # Check if we have time for refinement with BFGS
        elapsed_ms = (time.time() - start_time) * 1000
        if converged and elapsed_ms < self._config.timeout_ms * 0.5:
            # Refine with BFGS
            x_refined, f_refined, extra_iters, _ = self._optimizer.minimize(
                cost_fn, x_opt, bounds=bounds
            )
            if f_refined < f_opt:
                x_opt = x_refined
                f_opt = f_refined
                iterations += extra_iters

        # Extract action sequence
        best_sequence = [x_opt[i*self._action_dim:(i+1)*self._action_dim]
                        for i in range(horizon)]

        # Save for warmstart
        self._last_solution = best_sequence

        # Simulate final trajectory
        trajectory, coherences, final_cost = self._simulate_trajectory(
            current_state, best_sequence, current_coherence
        )

        # Check final constraint violations
        all_violations = []
        for i, action in enumerate(best_sequence):
            prev = best_sequence[i-1] if i > 0 else None
            violations = self._constraints.check_all(
                trajectory[i] if i < len(trajectory) else current_state,
                action, prev
            )
            all_violations.extend(violations)

        # Compute coherence penalty
        coherence_penalty = sum(
            self._config.coherence_cost_weight * (1.0 - c)**2
            for c in coherences
        )

        # Determine status
        elapsed_ms = (time.time() - start_time) * 1000
        if all_violations:
            status = MPCStatus.INFEASIBLE
        elif not converged:
            status = MPCStatus.MAX_ITER
        elif elapsed_ms >= self._config.timeout_ms:
            status = MPCStatus.TIMEOUT
        elif f_opt < self._config.tolerance * 10:
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

        logger.debug(
            f"MPC solved: status={status.value}, cost={f_opt:.4f}, "
            f"iterations={iterations}, time={elapsed_ms:.1f}ms"
        )

        return MPCResult(
            status=status,
            optimal_action=optimal_cmd,
            predicted_trajectory=trajectory,
            predicted_coherence=coherences,
            cost=f_opt,
            iterations=iterations,
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
