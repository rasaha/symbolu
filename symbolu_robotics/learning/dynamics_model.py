"""
Dynamics Model Module
=====================

Learned dynamics model for prediction and planning.

Uses 12D ontological state as representation:
- Learns state transitions: s_{t+1} = f(s_t, a_t)
- Provides uncertainty estimates via SCC coherence
- Enables model-predictive control

Integration:
- Deliberative tier (R3) uses predictions for planning
- SCC monitors prediction coherence
- Can detect distribution shift via coherence degradation
"""

from dataclasses import dataclass, field
from typing import Optional, List, Dict, Any, Tuple
from enum import Enum
import numpy as np

from symbolu_robotics.core.types import Layer12D, ActuatorCommand


class ModelType(Enum):
    """Type of dynamics model."""
    LINEAR = "linear"  # Simple linear model
    NEURAL = "neural"  # Neural network
    ENSEMBLE = "ensemble"  # Ensemble for uncertainty
    GAUSSIAN_PROCESS = "gp"  # GP for small data


@dataclass
class DynamicsConfig:
    """Configuration for dynamics model."""
    model_type: ModelType = ModelType.ENSEMBLE

    # Model architecture
    hidden_dims: List[int] = field(default_factory=lambda: [256, 256])
    ensemble_size: int = 5  # For ensemble models

    # Training
    learning_rate: float = 0.001
    batch_size: int = 64
    max_epochs: int = 100

    # Prediction
    horizon: int = 10  # Prediction horizon for planning
    uncertainty_threshold: float = 0.3  # Max acceptable uncertainty

    # Integration with Symbolu
    use_coherence_weighting: bool = True  # Weight training by SCC coherence
    predict_coherence: bool = True  # Also predict coherence evolution


@dataclass
class Prediction:
    """Single state prediction with uncertainty."""
    state: Layer12D  # Predicted 12D state
    uncertainty: np.ndarray  # Per-dimension uncertainty
    coherence: float  # Predicted SCC coherence

    # Confidence metrics
    model_confidence: float = 0.0  # Model's confidence in prediction
    ensemble_disagreement: float = 0.0  # For ensemble models

    def is_reliable(self, threshold: float = 0.3) -> bool:
        """Check if prediction is reliable."""
        return (
            self.uncertainty.mean() < threshold and
            self.coherence > 0.5 and
            self.ensemble_disagreement < threshold
        )


class TransitionBuffer:
    """Buffer for storing state transitions."""

    def __init__(self, capacity: int = 50000):
        self._capacity = capacity
        self._states: List[Layer12D] = []
        self._actions: List[np.ndarray] = []
        self._next_states: List[Layer12D] = []
        self._coherences: List[float] = []
        self._position = 0

    def add(
        self,
        state: Layer12D,
        action: np.ndarray,
        next_state: Layer12D,
        coherence: float = 1.0,
    ) -> None:
        """Add transition to buffer."""
        if len(self._states) < self._capacity:
            self._states.append(state.copy())
            self._actions.append(action.copy())
            self._next_states.append(next_state.copy())
            self._coherences.append(coherence)
        else:
            self._states[self._position] = state.copy()
            self._actions[self._position] = action.copy()
            self._next_states[self._position] = next_state.copy()
            self._coherences[self._position] = coherence

        self._position = (self._position + 1) % self._capacity

    def sample(
        self,
        batch_size: int,
        coherence_weighted: bool = True,
    ) -> Tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
        """Sample batch of transitions."""
        n = len(self._states)
        if n == 0:
            return (np.array([]), np.array([]), np.array([]), np.array([]))

        batch_size = min(batch_size, n)

        if coherence_weighted:
            # Weight by coherence (higher coherence = more likely to sample)
            weights = np.array(self._coherences[:n])
            weights = weights / weights.sum()
            indices = np.random.choice(n, batch_size, p=weights, replace=False)
        else:
            indices = np.random.choice(n, batch_size, replace=False)

        states = np.array([self._states[i] for i in indices])
        actions = np.array([self._actions[i] for i in indices])
        next_states = np.array([self._next_states[i] for i in indices])
        coherences = np.array([self._coherences[i] for i in indices])

        return states, actions, next_states, coherences

    def clear(self) -> None:
        """Clear buffer."""
        self._states.clear()
        self._actions.clear()
        self._next_states.clear()
        self._coherences.clear()
        self._position = 0

    def __len__(self) -> int:
        return len(self._states)


class DynamicsModel:
    """
    Learned dynamics model for state prediction.

    Skeleton Implementation:
    - Data structures and interfaces defined
    - Uses simple linear model as baseline
    - Neural network requires external framework

    Integration Points:
    - Deliberative tier uses for planning
    - SCC coherence informs prediction reliability
    - Detects distribution shift
    """

    def __init__(self, config: Optional[DynamicsConfig] = None):
        self._config = config or DynamicsConfig()

        # Transition storage
        self._buffer = TransitionBuffer()

        # Model parameters (placeholder)
        # For linear model: next_state = A @ state + B @ action
        self._A: Optional[np.ndarray] = None  # State transition matrix
        self._B: Optional[np.ndarray] = None  # Action effect matrix

        # For ensemble: list of (A, B) pairs
        self._ensemble: List[Tuple[np.ndarray, np.ndarray]] = []

        # Training state
        self._trained = False
        self._training_loss = float('inf')
        self._last_coherence = 0.0

    @property
    def is_trained(self) -> bool:
        """Check if model has been trained."""
        return self._trained

    def record_transition(
        self,
        state: Layer12D,
        action: ActuatorCommand,
        next_state: Layer12D,
        coherence: float = 1.0,
    ) -> None:
        """Record state transition for training."""
        action_array = self._action_to_array(action)
        self._buffer.add(state, action_array, next_state, coherence)

    def _action_to_array(self, action: ActuatorCommand) -> np.ndarray:
        """Convert action to array."""
        components = []

        if action.target_velocities is not None:
            components.extend(action.target_velocities.flatten())
        if action.target_positions is not None:
            components.extend(action.target_positions.flatten())
        if action.target_torques is not None:
            components.extend(action.target_torques.flatten())
        if action.gripper_position is not None:
            components.append(action.gripper_position)

        # Pad to fixed size if needed
        if len(components) < 7:
            components.extend([0.0] * (7 - len(components)))

        return np.array(components[:7], dtype=np.float32)

    def train(self, epochs: Optional[int] = None) -> Dict[str, float]:
        """
        Train dynamics model on collected data.

        Skeleton: Implements simple linear regression.
        """
        if len(self._buffer) < self._config.batch_size:
            return {"status": "insufficient_data", "samples": len(self._buffer)}

        epochs = epochs or self._config.max_epochs

        # Get all data
        states, actions, next_states, coherences = self._buffer.sample(
            len(self._buffer),
            coherence_weighted=self._config.use_coherence_weighting,
        )

        if len(states) == 0:
            return {"status": "no_data"}

        # Simple linear regression: next_state = A @ state + B @ action
        # Concatenate state and action as features
        X = np.hstack([states, actions])  # [N, 12 + action_dim]
        Y = next_states  # [N, 12]

        # Weighted least squares with coherence weights
        W = np.diag(coherences)

        try:
            # Solve: (X.T @ W @ X) @ params = X.T @ W @ Y
            XtWX = X.T @ W @ X
            XtWY = X.T @ W @ Y
            params = np.linalg.lstsq(XtWX, XtWY, rcond=None)[0]

            # Split into A (state) and B (action) matrices
            self._A = params[:12, :].T  # [12, 12]
            self._B = params[12:, :].T  # [12, action_dim]

            # Compute training loss
            Y_pred = X @ params
            self._training_loss = np.mean((Y - Y_pred) ** 2)
            self._trained = True

            # Build ensemble (with bootstrap sampling)
            if self._config.model_type == ModelType.ENSEMBLE:
                self._build_ensemble(states, actions, next_states, coherences)

            return {
                "status": "success",
                "loss": self._training_loss,
                "samples": len(states),
            }

        except np.linalg.LinAlgError:
            return {"status": "failed", "reason": "singular_matrix"}

    def _build_ensemble(
        self,
        states: np.ndarray,
        actions: np.ndarray,
        next_states: np.ndarray,
        coherences: np.ndarray,
    ) -> None:
        """Build ensemble of models with bootstrap sampling."""
        self._ensemble = []
        n = len(states)

        for _ in range(self._config.ensemble_size):
            # Bootstrap sample
            indices = np.random.choice(n, n, replace=True)
            X = np.hstack([states[indices], actions[indices]])
            Y = next_states[indices]
            W = np.diag(coherences[indices])

            try:
                XtWX = X.T @ W @ X
                XtWY = X.T @ W @ Y
                params = np.linalg.lstsq(XtWX, XtWY, rcond=None)[0]

                A = params[:12, :].T
                B = params[12:, :].T
                self._ensemble.append((A, B))
            except np.linalg.LinAlgError:
                continue

    def predict(
        self,
        state: Layer12D,
        action: ActuatorCommand,
    ) -> Prediction:
        """
        Predict next state given current state and action.

        Returns prediction with uncertainty estimate.
        """
        if not self._trained:
            return Prediction(
                state=state.copy(),
                uncertainty=np.ones(12),
                coherence=0.0,
                model_confidence=0.0,
            )

        action_array = self._action_to_array(action)

        if self._config.model_type == ModelType.ENSEMBLE and self._ensemble:
            return self._predict_ensemble(state, action_array)
        else:
            return self._predict_single(state, action_array)

    def _predict_single(
        self,
        state: Layer12D,
        action: np.ndarray,
    ) -> Prediction:
        """Single model prediction."""
        next_state = self._A @ state + self._B @ action
        next_state = np.clip(next_state, 0, 1).astype(np.float32)

        # Estimate uncertainty from training loss
        uncertainty = np.full(12, np.sqrt(self._training_loss))

        # Estimate coherence (simple: use last known coherence)
        coherence = self._last_coherence

        return Prediction(
            state=next_state,
            uncertainty=uncertainty,
            coherence=coherence,
            model_confidence=1.0 / (1.0 + self._training_loss),
        )

    def _predict_ensemble(
        self,
        state: Layer12D,
        action: np.ndarray,
    ) -> Prediction:
        """Ensemble prediction with uncertainty."""
        predictions = []

        for A, B in self._ensemble:
            pred = A @ state + B @ action
            pred = np.clip(pred, 0, 1)
            predictions.append(pred)

        predictions = np.array(predictions)

        # Mean prediction
        mean_pred = predictions.mean(axis=0).astype(np.float32)

        # Uncertainty from ensemble disagreement
        uncertainty = predictions.std(axis=0).astype(np.float32)
        disagreement = uncertainty.mean()

        # Confidence inversely related to disagreement
        confidence = 1.0 / (1.0 + disagreement)

        return Prediction(
            state=mean_pred,
            uncertainty=uncertainty,
            coherence=self._last_coherence,
            model_confidence=confidence,
            ensemble_disagreement=disagreement,
        )

    def predict_trajectory(
        self,
        initial_state: Layer12D,
        actions: List[ActuatorCommand],
    ) -> List[Prediction]:
        """
        Predict trajectory given sequence of actions.

        Used for planning in deliberative tier.
        """
        predictions = []
        state = initial_state.copy()

        for action in actions:
            pred = self.predict(state, action)
            predictions.append(pred)
            state = pred.state

        return predictions

    def detect_distribution_shift(
        self,
        recent_states: List[Layer12D],
        threshold: float = 0.5,
    ) -> Tuple[bool, float]:
        """
        Detect if recent data differs from training distribution.

        Uses prediction error as proxy for distribution shift.
        """
        if not self._trained or len(recent_states) < 2:
            return False, 0.0

        errors = []
        for i in range(len(recent_states) - 1):
            state = recent_states[i]
            actual_next = recent_states[i + 1]

            # Predict with zero action (approximation)
            pred = self._A @ state if self._A is not None else state
            error = np.mean((pred - actual_next) ** 2)
            errors.append(error)

        mean_error = np.mean(errors)
        shift_detected = mean_error > threshold * self._training_loss

        return shift_detected, mean_error

    def update_coherence(self, coherence: float) -> None:
        """Update last known coherence for prediction."""
        self._last_coherence = coherence

    def get_metrics(self) -> Dict[str, Any]:
        """Get model metrics."""
        return {
            "trained": self._trained,
            "training_loss": self._training_loss,
            "buffer_size": len(self._buffer),
            "ensemble_size": len(self._ensemble),
            "model_type": self._config.model_type.value,
        }

    def save(self, path: str) -> None:
        """Save model parameters."""
        # Placeholder
        pass

    def load(self, path: str) -> None:
        """Load model parameters."""
        # Placeholder
        pass

    def reset(self) -> None:
        """Reset model (clear buffer, keep trained parameters)."""
        self._last_coherence = 0.0
