"""
Skill Learning Module
=====================

RL-based skill refinement from robot experience.

Integrates with Symbolu ontology:
- State: 12D Layer representation
- Action: ActuatorCommand
- Reward: Derived from SCC coherence + task success
- Policy: Modulates BCVF action selection weights

Learning Modes:
1. Offline: Learn from collected experience buffer
2. Online: Continuous learning during operation (with safety constraints)
3. Imitation: Learn from demonstrations

Implementation: Hybrid approach using only numpy (no PyTorch/JAX dependency)
- NumpyMLP: Simple feedforward network with manual backprop
- REINFORCE: Policy gradient algorithm with baseline
"""

from dataclasses import dataclass, field
from typing import Optional, List, Dict, Any, Callable, Tuple
from enum import Enum
import numpy as np
import pickle
import logging

from symbolu_robotics.core.types import Layer12D, ActuatorCommand

logger = logging.getLogger(__name__)


# ============================================================================
# Numpy-based Neural Network (No External Dependencies)
# ============================================================================

class NumpyMLP:
    """
    Simple Multi-Layer Perceptron using only numpy.

    Implements forward pass, backward pass, and gradient descent.
    No external ML framework required.
    """

    def __init__(
        self,
        layer_sizes: List[int],
        activation: str = 'relu',
        output_activation: str = 'linear',
    ):
        """
        Initialize MLP with Xavier initialization.

        Args:
            layer_sizes: List of layer dimensions [input, hidden1, ..., output]
            activation: Hidden layer activation ('relu', 'tanh', 'sigmoid')
            output_activation: Output activation ('linear', 'tanh', 'softmax')
        """
        self.layer_sizes = layer_sizes
        self.activation = activation
        self.output_activation = output_activation
        self.n_layers = len(layer_sizes) - 1

        # Initialize weights and biases with Xavier initialization
        self.weights: List[np.ndarray] = []
        self.biases: List[np.ndarray] = []

        for i in range(self.n_layers):
            fan_in = layer_sizes[i]
            fan_out = layer_sizes[i + 1]
            # Xavier initialization
            std = np.sqrt(2.0 / (fan_in + fan_out))
            w = np.random.randn(fan_in, fan_out) * std
            b = np.zeros(fan_out)
            self.weights.append(w)
            self.biases.append(b)

        # For storing activations during forward pass (needed for backprop)
        self._activations: List[np.ndarray] = []
        self._pre_activations: List[np.ndarray] = []

    def forward(self, x: np.ndarray) -> np.ndarray:
        """
        Forward pass through the network.

        Args:
            x: Input array of shape (batch_size, input_dim) or (input_dim,)

        Returns:
            Output array of shape (batch_size, output_dim)
        """
        # Ensure 2D input
        if x.ndim == 1:
            x = x.reshape(1, -1)

        self._activations = [x]
        self._pre_activations = []

        for i in range(self.n_layers):
            # Linear transformation
            z = x @ self.weights[i] + self.biases[i]
            self._pre_activations.append(z)

            # Apply activation
            if i < self.n_layers - 1:
                # Hidden layers
                x = self._apply_activation(z, self.activation)
            else:
                # Output layer
                x = self._apply_activation(z, self.output_activation)

            self._activations.append(x)

        return x

    def backward(
        self,
        grad_output: np.ndarray,
        learning_rate: float = 0.001,
        clip_grad: float = 1.0,
    ) -> None:
        """
        Backward pass with gradient descent update.

        Args:
            grad_output: Gradient of loss w.r.t. output
            learning_rate: Learning rate for SGD
            clip_grad: Maximum gradient norm for clipping
        """
        grad = grad_output

        for i in range(self.n_layers - 1, -1, -1):
            # Gradient through activation
            if i == self.n_layers - 1:
                grad = grad * self._activation_derivative(
                    self._pre_activations[i], self.output_activation
                )
            else:
                grad = grad * self._activation_derivative(
                    self._pre_activations[i], self.activation
                )

            # Compute gradients for weights and biases
            grad_w = self._activations[i].T @ grad
            grad_b = grad.sum(axis=0)

            # Gradient clipping
            grad_w_norm = np.linalg.norm(grad_w)
            if grad_w_norm > clip_grad:
                grad_w = grad_w * clip_grad / grad_w_norm

            # Update weights and biases
            self.weights[i] -= learning_rate * grad_w
            self.biases[i] -= learning_rate * grad_b

            # Propagate gradient to previous layer
            if i > 0:
                grad = grad @ self.weights[i].T

    def _apply_activation(self, z: np.ndarray, activation: str) -> np.ndarray:
        """Apply activation function."""
        if activation == 'relu':
            return np.maximum(0, z)
        elif activation == 'tanh':
            return np.tanh(z)
        elif activation == 'sigmoid':
            return 1 / (1 + np.exp(-np.clip(z, -500, 500)))
        elif activation == 'softmax':
            exp_z = np.exp(z - z.max(axis=-1, keepdims=True))
            return exp_z / exp_z.sum(axis=-1, keepdims=True)
        else:  # linear
            return z

    def _activation_derivative(self, z: np.ndarray, activation: str) -> np.ndarray:
        """Compute derivative of activation function."""
        if activation == 'relu':
            return (z > 0).astype(float)
        elif activation == 'tanh':
            return 1 - np.tanh(z) ** 2
        elif activation == 'sigmoid':
            s = 1 / (1 + np.exp(-np.clip(z, -500, 500)))
            return s * (1 - s)
        else:  # linear, softmax (handled separately)
            return np.ones_like(z)

    def get_weights(self) -> Dict[str, np.ndarray]:
        """Get all weights as a dictionary."""
        return {
            f'w{i}': w.copy() for i, w in enumerate(self.weights)
        } | {
            f'b{i}': b.copy() for i, b in enumerate(self.biases)
        }

    def set_weights(self, weights: Dict[str, np.ndarray]) -> None:
        """Set weights from a dictionary."""
        for i in range(self.n_layers):
            if f'w{i}' in weights:
                self.weights[i] = weights[f'w{i}'].copy()
            if f'b{i}' in weights:
                self.biases[i] = weights[f'b{i}'].copy()

    def copy(self) -> 'NumpyMLP':
        """Create a copy of this network."""
        new_net = NumpyMLP(self.layer_sizes, self.activation, self.output_activation)
        new_net.set_weights(self.get_weights())
        return new_net


class GaussianPolicy:
    """
    Gaussian policy for continuous action spaces.

    Outputs mean and log_std for each action dimension.
    """

    def __init__(self, state_dim: int, action_dim: int, hidden_dims: List[int]):
        self.state_dim = state_dim
        self.action_dim = action_dim

        # Network outputs mean for each action
        layer_sizes = [state_dim] + hidden_dims + [action_dim]
        self.mean_net = NumpyMLP(layer_sizes, activation='tanh', output_activation='tanh')

        # Learnable log standard deviation (state-independent for stability)
        self.log_std = np.zeros(action_dim)
        self._log_std_min = -20
        self._log_std_max = 2

    def forward(self, state: np.ndarray) -> Tuple[np.ndarray, np.ndarray]:
        """
        Get action distribution parameters.

        Returns:
            mean: Action mean
            std: Action standard deviation
        """
        mean = self.mean_net.forward(state)
        std = np.exp(np.clip(self.log_std, self._log_std_min, self._log_std_max))
        return mean, std

    def sample(self, state: np.ndarray) -> Tuple[np.ndarray, np.ndarray]:
        """
        Sample action from policy.

        Returns:
            action: Sampled action
            log_prob: Log probability of the action
        """
        mean, std = self.forward(state)

        # Sample from Gaussian
        noise = np.random.randn(*mean.shape)
        action = mean + std * noise

        # Compute log probability
        log_prob = -0.5 * (
            ((action - mean) / std) ** 2 +
            2 * np.log(std) +
            np.log(2 * np.pi)
        ).sum(axis=-1)

        return action, log_prob

    def log_prob(self, state: np.ndarray, action: np.ndarray) -> np.ndarray:
        """Compute log probability of action given state."""
        mean, std = self.forward(state)
        return -0.5 * (
            ((action - mean) / std) ** 2 +
            2 * np.log(std) +
            np.log(2 * np.pi)
        ).sum(axis=-1)

    def get_weights(self) -> Dict[str, np.ndarray]:
        """Get all policy weights."""
        weights = self.mean_net.get_weights()
        weights['log_std'] = self.log_std.copy()
        return weights

    def set_weights(self, weights: Dict[str, np.ndarray]) -> None:
        """Set policy weights."""
        self.mean_net.set_weights(weights)
        if 'log_std' in weights:
            self.log_std = weights['log_std'].copy()


class LearningMode(Enum):
    """Learning operation mode."""
    OFFLINE = "offline"
    ONLINE = "online"
    IMITATION = "imitation"
    DISABLED = "disabled"


@dataclass
class SkillConfig:
    """Configuration for skill learning."""
    # Learning parameters
    learning_rate: float = 0.001
    discount_factor: float = 0.99
    batch_size: int = 64
    buffer_size: int = 10000

    # Safety constraints
    max_online_update_rate: float = 0.1  # Max policy change per step
    require_coherence_threshold: float = 0.5  # Min SCC coherence to learn

    # Reward shaping
    coherence_reward_weight: float = 0.3  # Weight for SCC coherence in reward
    task_reward_weight: float = 0.7  # Weight for task success

    # Architecture
    hidden_dims: List[int] = field(default_factory=lambda: [256, 256])
    use_layer_norm: bool = True


@dataclass
class Experience:
    """Single experience tuple for learning."""
    state: Layer12D  # 12D ontological state
    action: np.ndarray  # Action taken (from ActuatorCommand)
    reward: float  # Combined reward signal
    next_state: Layer12D  # Resulting state
    done: bool  # Episode termination

    # Metadata
    coherence: float = 0.0  # SCC coherence at time of experience
    timestamp: float = 0.0
    skill_name: str = ""

    def is_valid(self, min_coherence: float = 0.3) -> bool:
        """Check if experience is valid for learning."""
        return self.coherence >= min_coherence


@dataclass
class LearnedSkill:
    """Represents a learned skill/policy."""
    name: str
    description: str = ""

    # Policy weights (placeholder for actual NN weights)
    policy_weights: Optional[Dict[str, np.ndarray]] = None
    value_weights: Optional[Dict[str, np.ndarray]] = None

    # Performance metrics
    success_rate: float = 0.0
    avg_coherence: float = 0.0
    training_episodes: int = 0

    # Version tracking
    version: int = 1

    def is_trained(self) -> bool:
        """Check if skill has been trained."""
        return self.policy_weights is not None and self.training_episodes > 0


class ExperienceBuffer:
    """
    Circular buffer for storing experiences.

    Implements prioritized experience replay based on:
    - TD error (standard)
    - Coherence (Symbolu-specific): Prioritize high-coherence experiences
    """

    def __init__(self, capacity: int = 10000, prioritized: bool = True):
        self._capacity = capacity
        self._prioritized = prioritized
        self._buffer: List[Experience] = []
        self._priorities: np.ndarray = np.zeros(capacity)
        self._position = 0
        self._size = 0

    def add(self, experience: Experience, priority: Optional[float] = None) -> None:
        """Add experience to buffer."""
        if len(self._buffer) < self._capacity:
            self._buffer.append(experience)
        else:
            self._buffer[self._position] = experience

        # Set priority (default: max priority for new experiences)
        if priority is None:
            priority = self._priorities[:self._size].max() if self._size > 0 else 1.0
        self._priorities[self._position] = priority

        self._position = (self._position + 1) % self._capacity
        self._size = min(self._size + 1, self._capacity)

    def sample(self, batch_size: int) -> List[Experience]:
        """Sample batch of experiences."""
        if self._size == 0:
            return []

        batch_size = min(batch_size, self._size)

        if self._prioritized and self._size > 0:
            # Prioritized sampling
            probs = self._priorities[:self._size]
            probs = probs / probs.sum()
            indices = np.random.choice(self._size, batch_size, p=probs, replace=False)
        else:
            # Uniform sampling
            indices = np.random.choice(self._size, batch_size, replace=False)

        return [self._buffer[i] for i in indices]

    def update_priorities(self, indices: List[int], priorities: List[float]) -> None:
        """Update priorities for experiences."""
        for idx, priority in zip(indices, priorities):
            if idx < self._size:
                self._priorities[idx] = priority

    def clear(self) -> None:
        """Clear buffer."""
        self._buffer.clear()
        self._priorities = np.zeros(self._capacity)
        self._position = 0
        self._size = 0

    def __len__(self) -> int:
        return self._size


class SkillLearner:
    """
    RL-based skill learning integrated with Symbolu ontology.

    Key Features:
    - Uses 12D Layer as state representation
    - Reward derived from SCC coherence + task success
    - Safety-constrained online learning
    - Modulates BCVF action selection

    Implementation: REINFORCE with baseline using numpy-only neural networks.
    No external ML frameworks required.
    """

    # Dimensions
    STATE_DIM = 12  # 12D ontological state
    ACTION_DIM = 7  # Default: 6 joints + 1 gripper

    def __init__(self, config: Optional[SkillConfig] = None, action_dim: int = 7):
        self._config = config or SkillConfig()
        self._mode = LearningMode.DISABLED
        self._action_dim = action_dim

        # Experience storage
        self._buffer = ExperienceBuffer(
            capacity=self._config.buffer_size,
            prioritized=True
        )

        # Learned skills
        self._skills: Dict[str, LearnedSkill] = {}
        self._active_skill: Optional[str] = None

        # Current episode tracking
        self._current_episode: List[Experience] = []
        self._episode_count = 0

        # Learning metrics
        self._total_experiences = 0
        self._avg_reward = 0.0
        self._avg_coherence = 0.0

        # Neural networks (numpy-based)
        self._policy: Optional[GaussianPolicy] = None
        self._value_net: Optional[NumpyMLP] = None
        self._initialize_networks()

        # Training state
        self._training_step = 0

        logger.info(f"SkillLearner initialized with state_dim={self.STATE_DIM}, action_dim={action_dim}")

    def _initialize_networks(self) -> None:
        """Initialize policy and value networks."""
        hidden_dims = self._config.hidden_dims

        # Policy network: state -> action distribution
        self._policy = GaussianPolicy(
            state_dim=self.STATE_DIM,
            action_dim=self._action_dim,
            hidden_dims=hidden_dims,
        )

        # Value network: state -> scalar value (baseline)
        value_layers = [self.STATE_DIM] + hidden_dims + [1]
        self._value_net = NumpyMLP(
            layer_sizes=value_layers,
            activation='tanh',
            output_activation='linear',
        )

        logger.debug(f"Networks initialized: policy hidden={hidden_dims}, value hidden={hidden_dims}")

    @property
    def mode(self) -> LearningMode:
        """Current learning mode."""
        return self._mode

    def set_mode(self, mode: LearningMode) -> None:
        """Set learning mode."""
        self._mode = mode

    def create_skill(self, name: str, description: str = "") -> LearnedSkill:
        """Create a new skill to learn."""
        skill = LearnedSkill(name=name, description=description)
        self._skills[name] = skill
        return skill

    def get_skill(self, name: str) -> Optional[LearnedSkill]:
        """Get learned skill by name."""
        return self._skills.get(name)

    def set_active_skill(self, name: str) -> bool:
        """Set active skill for learning/execution."""
        if name in self._skills:
            self._active_skill = name
            return True
        return False

    def record_experience(
        self,
        state: Layer12D,
        action: ActuatorCommand,
        reward: float,
        next_state: Layer12D,
        done: bool,
        coherence: float = 0.0,
    ) -> None:
        """
        Record an experience for learning.

        Called by tier during operation to collect training data.
        """
        # Convert action to array
        action_array = self._action_to_array(action)

        experience = Experience(
            state=state.copy(),
            action=action_array,
            reward=reward,
            next_state=next_state.copy(),
            done=done,
            coherence=coherence,
            skill_name=self._active_skill or "",
        )

        # Add to current episode
        self._current_episode.append(experience)

        # If episode done, process and add to buffer
        if done:
            self._process_episode()

        self._total_experiences += 1

    def _action_to_array(self, action: ActuatorCommand) -> np.ndarray:
        """Convert ActuatorCommand to array for learning."""
        # Flatten all action components
        components = []

        if action.target_velocities is not None:
            components.extend(action.target_velocities.flatten())
        if action.target_positions is not None:
            components.extend(action.target_positions.flatten())
        if action.target_torques is not None:
            components.extend(action.target_torques.flatten())
        if action.gripper_position is not None:
            components.append(action.gripper_position)

        return np.array(components, dtype=np.float32)

    def _process_episode(self) -> None:
        """Process completed episode."""
        if not self._current_episode:
            return

        # Compute discounted returns
        returns = self._compute_returns(self._current_episode)

        # Add to buffer with coherence-weighted priority
        for exp, ret in zip(self._current_episode, returns):
            priority = abs(ret) * (1 + exp.coherence)  # Coherence boosts priority
            self._buffer.add(exp, priority)

        # Update metrics
        ep_reward = sum(e.reward for e in self._current_episode)
        ep_coherence = np.mean([e.coherence for e in self._current_episode])

        self._avg_reward = 0.9 * self._avg_reward + 0.1 * ep_reward
        self._avg_coherence = 0.9 * self._avg_coherence + 0.1 * ep_coherence

        # Clear episode
        self._current_episode = []
        self._episode_count += 1

    def _compute_returns(self, episode: List[Experience]) -> List[float]:
        """Compute discounted returns for episode."""
        returns = []
        G = 0.0
        gamma = self._config.discount_factor

        for exp in reversed(episode):
            G = exp.reward + gamma * G
            returns.insert(0, G)

        return returns

    def compute_reward(
        self,
        task_reward: float,
        coherence: float,
        safety_violation: bool = False,
    ) -> float:
        """
        Compute combined reward signal.

        Integrates task success with SCC coherence.
        """
        # Weighted combination
        reward = (
            self._config.task_reward_weight * task_reward +
            self._config.coherence_reward_weight * coherence
        )

        # Strong penalty for safety violations
        if safety_violation:
            reward -= 10.0

        return reward

    def train_step(self) -> Dict[str, float]:
        """
        Perform one training step using REINFORCE with baseline.

        Uses numpy-based neural networks - no external ML framework required.
        """
        if self._mode == LearningMode.DISABLED:
            return {"status": "disabled"}

        if len(self._buffer) < self._config.batch_size:
            return {"status": "insufficient_data", "buffer_size": len(self._buffer)}

        # Sample batch
        batch = self._buffer.sample(self._config.batch_size)

        # Filter by coherence threshold
        valid_batch = [
            exp for exp in batch
            if exp.is_valid(self._config.require_coherence_threshold)
        ]

        if len(valid_batch) < self._config.batch_size // 2:
            return {"status": "low_quality_data", "valid_samples": len(valid_batch)}

        # Extract batch data
        states = np.array([exp.state for exp in valid_batch])
        actions = np.array([exp.action for exp in valid_batch])
        coherences = np.array([exp.coherence for exp in valid_batch])

        # Compute returns for each experience
        returns = np.array([
            self._compute_single_return(exp, valid_batch)
            for exp in valid_batch
        ])

        # Normalize returns for stability
        returns = (returns - returns.mean()) / (returns.std() + 1e-8)

        # === Value Network Update (baseline) ===
        values = self._value_net.forward(states).flatten()
        value_loss = np.mean((values - returns) ** 2)

        # Gradient: d(MSE)/d(output) = 2 * (values - returns) / n
        value_grad = 2 * (values - returns).reshape(-1, 1) / len(valid_batch)
        self._value_net.backward(value_grad, learning_rate=self._config.learning_rate)

        # === Policy Network Update (REINFORCE) ===
        # Compute advantages (returns - baseline)
        advantages = returns - values

        # Weight by coherence (Symbolu-specific: trust high-coherence experiences more)
        weighted_advantages = advantages * (0.5 + 0.5 * coherences)

        # Compute policy gradient
        policy_loss = self._update_policy(states, actions, weighted_advantages)

        # Update training state
        self._training_step += 1

        # Update priorities in buffer based on TD error
        td_errors = np.abs(returns - values)
        indices = list(range(len(valid_batch)))
        priorities = (td_errors * (1 + coherences)).tolist()
        self._buffer.update_priorities(indices, priorities)

        # Update active skill metrics if applicable
        if self._active_skill and self._active_skill in self._skills:
            skill = self._skills[self._active_skill]
            skill.avg_coherence = 0.9 * skill.avg_coherence + 0.1 * coherences.mean()
            skill.policy_weights = self._policy.get_weights()
            skill.value_weights = self._value_net.get_weights()

        metrics = {
            "status": "trained",
            "batch_size": len(valid_batch),
            "policy_loss": float(policy_loss),
            "value_loss": float(value_loss),
            "avg_advantage": float(advantages.mean()),
            "avg_coherence": float(coherences.mean()),
            "training_step": self._training_step,
        }

        logger.debug(f"Training step {self._training_step}: policy_loss={policy_loss:.4f}, value_loss={value_loss:.4f}")

        return metrics

    def _compute_single_return(self, exp: Experience, batch: List[Experience]) -> float:
        """Compute return for a single experience."""
        # For now, use the reward directly weighted by coherence
        # In a full implementation, this would trace through the episode
        return exp.reward * (1 + exp.coherence)

    def _update_policy(
        self,
        states: np.ndarray,
        actions: np.ndarray,
        advantages: np.ndarray,
    ) -> float:
        """
        Update policy using REINFORCE gradient.

        Policy gradient: ∇J = E[∇log π(a|s) * A(s,a)]
        """
        # Ensure actions match network output dimension
        if actions.shape[1] > self._action_dim:
            actions = actions[:, :self._action_dim]
        elif actions.shape[1] < self._action_dim:
            # Pad with zeros if needed
            padded = np.zeros((actions.shape[0], self._action_dim))
            padded[:, :actions.shape[1]] = actions
            actions = padded

        # Get current policy output
        means, stds = self._policy.forward(states)

        # Compute log probability gradient
        # For Gaussian: ∇_μ log π = (a - μ) / σ²
        # ∇_σ log π = ((a - μ)² - σ²) / σ³
        action_diff = actions - means

        # Policy gradient for mean network
        # ∇_θ J = ∇_θ μ * ∇_μ log π * A
        # = ∇_θ μ * (a - μ) / σ² * A
        grad_mean = action_diff / (stds ** 2)
        weighted_grad = grad_mean * advantages.reshape(-1, 1)

        # Backpropagate through mean network
        # Negate because we want to maximize (gradient ascent)
        self._policy.mean_net.backward(
            -weighted_grad / len(states),
            learning_rate=self._config.learning_rate,
            clip_grad=self._config.max_online_update_rate,
        )

        # Update log_std (simple gradient descent)
        # ∇_log_σ J = ((a - μ)² / σ² - 1) * A
        grad_log_std = ((action_diff ** 2) / (stds ** 2) - 1) * advantages.reshape(-1, 1)
        self._policy.log_std -= self._config.learning_rate * grad_log_std.mean(axis=0)

        # Clip log_std
        self._policy.log_std = np.clip(
            self._policy.log_std,
            self._policy._log_std_min,
            self._policy._log_std_max,
        )

        # Compute policy loss for logging (negative expected advantage)
        log_probs = self._policy.log_prob(states, actions)
        policy_loss = -np.mean(log_probs * advantages)

        return policy_loss

    def get_action_modifier(
        self,
        state: Layer12D,
        base_action: ActuatorCommand,
    ) -> Tuple[ActuatorCommand, float]:
        """
        Get learned action modification.

        Applies the learned policy to modify the base action.

        Returns:
            Modified action and confidence score.
        """
        if self._mode == LearningMode.DISABLED:
            return base_action, 0.0

        if self._active_skill is None:
            return base_action, 0.0

        skill = self._skills.get(self._active_skill)
        if skill is None or not skill.is_trained():
            return base_action, 0.0

        # Load skill weights if different from current
        if skill.policy_weights is not None:
            self._policy.set_weights(skill.policy_weights)

        # Get policy action
        state_array = np.array(state).reshape(1, -1)
        action, log_prob = self._policy.sample(state_array)
        action = action.flatten()

        # Blend policy action with base action based on skill confidence
        confidence = skill.success_rate * skill.avg_coherence
        blend_factor = min(confidence, self._config.max_online_update_rate)

        # Create modified action
        modified = ActuatorCommand(
            target_velocities=base_action.target_velocities,
            target_positions=base_action.target_positions,
            target_torques=base_action.target_torques,
            gripper_position=base_action.gripper_position,
        )

        # Apply learned modifications (scaled by blend factor)
        if modified.target_velocities is not None and len(action) >= 6:
            policy_vel = action[:6] * blend_factor
            modified.target_velocities = (
                (1 - blend_factor) * modified.target_velocities +
                blend_factor * policy_vel
            )

        if modified.gripper_position is not None and len(action) >= 7:
            policy_grip = action[6] * blend_factor
            modified.gripper_position = (
                (1 - blend_factor) * modified.gripper_position +
                blend_factor * np.clip(policy_grip, 0, 1)
            )

        return modified, confidence

    def get_bcvf_modifier(self, state: Layer12D) -> np.ndarray:
        """
        Get learned modifier for BCVF action selection.

        Returns array of weights to multiply with BCVF scores.
        Based on value network's assessment of state.
        """
        if self._mode == LearningMode.DISABLED or self._value_net is None:
            return np.ones(4)

        # Use value network to assess state quality
        state_array = np.array(state).reshape(1, -1)
        value = self._value_net.forward(state_array).flatten()[0]

        # Convert value to modifier weights
        # Higher value -> more confident in learned behaviors
        # Weights for: [move_to, grasp, release, wait]
        base_weight = 1.0 + 0.5 * np.tanh(value)  # Range: [0.5, 1.5]

        # Different weights for different action types based on training
        modifiers = np.array([
            base_weight,        # move_to
            base_weight * 0.8,  # grasp (more conservative)
            base_weight * 0.9,  # release
            1.0,                # wait (always neutral)
        ])

        return modifiers

    def save(self, path: str) -> None:
        """
        Save learned skills to file using pickle (stdlib).

        Saves:
        - Configuration
        - All learned skills with their weights
        - Training metrics
        """
        data = {
            'version': 2,
            'config': {
                'learning_rate': self._config.learning_rate,
                'discount_factor': self._config.discount_factor,
                'batch_size': self._config.batch_size,
                'buffer_size': self._config.buffer_size,
                'hidden_dims': self._config.hidden_dims,
                'coherence_reward_weight': self._config.coherence_reward_weight,
                'task_reward_weight': self._config.task_reward_weight,
            },
            'action_dim': self._action_dim,
            'skills': {},
            'metrics': {
                'total_experiences': self._total_experiences,
                'episode_count': self._episode_count,
                'avg_reward': self._avg_reward,
                'avg_coherence': self._avg_coherence,
                'training_step': self._training_step,
            },
            'policy_weights': self._policy.get_weights() if self._policy else None,
            'value_weights': self._value_net.get_weights() if self._value_net else None,
        }

        # Save each skill
        for name, skill in self._skills.items():
            data['skills'][name] = {
                'name': skill.name,
                'description': skill.description,
                'policy_weights': skill.policy_weights,
                'value_weights': skill.value_weights,
                'success_rate': skill.success_rate,
                'avg_coherence': skill.avg_coherence,
                'training_episodes': skill.training_episodes,
                'version': skill.version,
            }

        with open(path, 'wb') as f:
            pickle.dump(data, f, protocol=pickle.HIGHEST_PROTOCOL)

        logger.info(f"Saved {len(self._skills)} skills to {path}")

    def load(self, path: str) -> None:
        """
        Load learned skills from file.

        Restores skills and optionally the current network weights.
        """
        with open(path, 'rb') as f:
            data = pickle.load(f)

        # Version check
        version = data.get('version', 1)
        if version < 1:
            raise ValueError(f"Incompatible save format version: {version}")

        # Restore action dimension if saved
        if 'action_dim' in data and data['action_dim'] != self._action_dim:
            logger.warning(
                f"Action dimension mismatch: saved={data['action_dim']}, "
                f"current={self._action_dim}. Re-initializing networks."
            )
            self._action_dim = data['action_dim']
            self._initialize_networks()

        # Restore skills
        self._skills = {}
        for name, skill_data in data.get('skills', {}).items():
            self._skills[name] = LearnedSkill(
                name=skill_data['name'],
                description=skill_data.get('description', ''),
                policy_weights=skill_data.get('policy_weights'),
                value_weights=skill_data.get('value_weights'),
                success_rate=skill_data.get('success_rate', 0.0),
                avg_coherence=skill_data.get('avg_coherence', 0.0),
                training_episodes=skill_data.get('training_episodes', 0),
                version=skill_data.get('version', 1),
            )

        # Restore metrics
        metrics = data.get('metrics', {})
        self._total_experiences = metrics.get('total_experiences', 0)
        self._episode_count = metrics.get('episode_count', 0)
        self._avg_reward = metrics.get('avg_reward', 0.0)
        self._avg_coherence = metrics.get('avg_coherence', 0.0)
        self._training_step = metrics.get('training_step', 0)

        # Restore current network weights
        if data.get('policy_weights') and self._policy:
            self._policy.set_weights(data['policy_weights'])
        if data.get('value_weights') and self._value_net:
            self._value_net.set_weights(data['value_weights'])

        logger.info(f"Loaded {len(self._skills)} skills from {path}")

    def get_metrics(self) -> Dict[str, Any]:
        """Get learning metrics."""
        return {
            "mode": self._mode.value,
            "total_experiences": self._total_experiences,
            "episode_count": self._episode_count,
            "buffer_size": len(self._buffer),
            "avg_reward": self._avg_reward,
            "avg_coherence": self._avg_coherence,
            "skills": {
                name: {
                    "trained": skill.is_trained(),
                    "success_rate": skill.success_rate,
                    "episodes": skill.training_episodes,
                }
                for name, skill in self._skills.items()
            },
        }

    def reset(self) -> None:
        """Reset learner state (not learned skills)."""
        self._current_episode = []
        self._avg_reward = 0.0
        self._avg_coherence = 0.0
