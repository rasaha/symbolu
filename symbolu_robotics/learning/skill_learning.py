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
"""

from dataclasses import dataclass, field
from typing import Optional, List, Dict, Any, Callable, Tuple
from enum import Enum
import numpy as np

from symbolu_robotics.core.types import Layer12D, ActuatorCommand


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

    Skeleton Implementation:
    - Core data structures and interfaces defined
    - Neural network training requires external framework (PyTorch/JAX)
    - Provides hooks for integration
    """

    def __init__(self, config: Optional[SkillConfig] = None):
        self._config = config or SkillConfig()
        self._mode = LearningMode.DISABLED

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
        Perform one training step.

        Skeleton: Returns placeholder metrics.
        Actual implementation requires neural network framework.
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

        # Placeholder: Actual training would happen here
        # This would involve:
        # 1. Extract states, actions, rewards, next_states
        # 2. Compute TD targets
        # 3. Update policy network
        # 4. Update value network
        # 5. Update priorities

        return {
            "status": "trained",
            "batch_size": len(valid_batch),
            "avg_coherence": np.mean([e.coherence for e in valid_batch]),
        }

    def get_action_modifier(
        self,
        state: Layer12D,
        base_action: ActuatorCommand,
    ) -> Tuple[ActuatorCommand, float]:
        """
        Get learned action modification.

        Skeleton: Returns base action unchanged.
        Actual implementation would apply learned policy.

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

        # Placeholder: Would apply policy here
        confidence = skill.success_rate * skill.avg_coherence

        return base_action, confidence

    def get_bcvf_modifier(self, state: Layer12D) -> np.ndarray:
        """
        Get learned modifier for BCVF action selection.

        Returns array of weights to multiply with BCVF scores.
        Skeleton: Returns ones (no modification).
        """
        return np.ones(4)  # Placeholder for 4 action types

    def save(self, path: str) -> None:
        """Save learned skills to file."""
        # Placeholder: Would serialize skills
        pass

    def load(self, path: str) -> None:
        """Load learned skills from file."""
        # Placeholder: Would deserialize skills
        pass

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
