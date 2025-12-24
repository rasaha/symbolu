"""
Ontological Engine - Type Definitions
=====================================

Core types for the learnable 10D ontological engine.
"""

from dataclasses import dataclass, field
from typing import List, Dict, Optional, Tuple, Any
from enum import Enum


# The 10 ontological layer names
LAYER_NAMES: Tuple[str, ...] = (
    "O1_THINKING",
    "O2_FORMING",
    "O3_ACTING",
    "O4_TAGGING",
    "O5_DIRECTING",
    "O6_REASONING",
    "O7_PURPOSING",
    "O8_META_OBSERVING",
    "O9_UNIFYING",
    "O10_ABSOLVING",
)

# Human-readable descriptions for each layer
LAYER_DESCRIPTIONS: Dict[str, str] = {
    "O1_THINKING": "Contemplation, philosophy, reflection",
    "O2_FORMING": "Structure, creation, art, creativity",
    "O3_ACTING": "Procedures, commands, action",
    "O4_TAGGING": "Emotional tagging/classification",
    "O5_DIRECTING": "Guidance, instruction, leadership",
    "O6_REASONING": "Logic, analysis, problem-solving",
    "O7_PURPOSING": "Goals, intention, purposefulness",
    "O8_META_OBSERVING": "Meta-awareness, observation",
    "O9_UNIFYING": "Integration, synthesis, unity",
    "O10_ABSOLVING": "Resolution, completion, transcendence",
}

# Layer indices for quick access
LAYER_INDEX: Dict[str, int] = {name: i for i, name in enumerate(LAYER_NAMES)}

# Key dimensions for specific tasks
REASONING_LAYERS = ["O6_REASONING", "O1_THINKING", "O8_META_OBSERVING"]
CREATIVITY_LAYERS = ["O2_FORMING", "O9_UNIFYING", "O7_PURPOSING"]
ACTION_LAYERS = ["O3_ACTING", "O5_DIRECTING"]
EMOTIONAL_LAYERS = ["O4_TAGGING", "O9_UNIFYING"]


class TaskType(Enum):
    """Types of tasks the engine can handle."""
    REASONING = "reasoning"
    CREATIVITY = "creativity"
    ACTION = "action"
    REFLECTION = "reflection"
    GENERAL = "general"


@dataclass
class OntologicalConfig:
    """Configuration for the ontological engine."""

    # Encoder settings
    encoder_name: str = "distilbert-base-uncased"
    encoder_dim: int = 768  # DistilBERT output dimension
    freeze_encoder: bool = False  # Whether to freeze pretrained encoder

    # Hidden layer architecture
    hidden_dims: Tuple[int, ...] = (512, 256)
    dropout: float = 0.1
    use_skip_connections: bool = True
    use_layer_norm: bool = True

    # Output settings
    ontological_dim: int = 10  # Always 10 for interpretability
    output_activation: str = "tanh"  # tanh keeps values in [-1, 1]

    # Task head settings
    reasoning_head_dims: Tuple[int, ...] = (128, 64)
    creativity_head_dims: Tuple[int, ...] = (128, 64)

    # Loss function settings
    use_purity_loss: bool = True
    purity_weight: float = 0.1  # Weight for dimension orthogonality
    supervision_weight: float = 1.0  # Weight for dimension-specific labels
    task_weight: float = 1.0  # Weight for task-specific losses

    # Training settings
    learning_rate: float = 2e-5
    weight_decay: float = 0.01
    warmup_steps: int = 100
    max_grad_norm: float = 1.0

    # Batch settings
    batch_size: int = 32
    max_seq_length: int = 128

    def to_dict(self) -> Dict[str, Any]:
        """Convert config to dictionary."""
        return {
            "encoder_name": self.encoder_name,
            "encoder_dim": self.encoder_dim,
            "freeze_encoder": self.freeze_encoder,
            "hidden_dims": list(self.hidden_dims),
            "dropout": self.dropout,
            "use_skip_connections": self.use_skip_connections,
            "use_layer_norm": self.use_layer_norm,
            "ontological_dim": self.ontological_dim,
            "output_activation": self.output_activation,
            "reasoning_head_dims": list(self.reasoning_head_dims),
            "creativity_head_dims": list(self.creativity_head_dims),
            "use_purity_loss": self.use_purity_loss,
            "purity_weight": self.purity_weight,
            "supervision_weight": self.supervision_weight,
            "task_weight": self.task_weight,
            "learning_rate": self.learning_rate,
            "weight_decay": self.weight_decay,
            "warmup_steps": self.warmup_steps,
            "max_grad_norm": self.max_grad_norm,
            "batch_size": self.batch_size,
            "max_seq_length": self.max_seq_length,
        }


@dataclass
class OntologicalVector:
    """
    A 10D ontological vector with named dimensions.

    Provides easy access to individual layer activations and
    interpretable outputs.
    """
    values: Tuple[float, ...]
    text: Optional[str] = None

    def __post_init__(self):
        if len(self.values) != 10:
            raise ValueError(f"OntologicalVector must have 10 values, got {len(self.values)}")

    @property
    def thinking(self) -> float:
        return self.values[0]

    @property
    def forming(self) -> float:
        return self.values[1]

    @property
    def acting(self) -> float:
        return self.values[2]

    @property
    def tagging(self) -> float:
        return self.values[3]

    @property
    def directing(self) -> float:
        return self.values[4]

    @property
    def reasoning(self) -> float:
        return self.values[5]

    @property
    def purposing(self) -> float:
        return self.values[6]

    @property
    def meta_observing(self) -> float:
        return self.values[7]

    @property
    def unifying(self) -> float:
        return self.values[8]

    @property
    def absolving(self) -> float:
        return self.values[9]

    def get_layer(self, name: str) -> float:
        """Get activation for a specific layer by name."""
        if name not in LAYER_INDEX:
            raise ValueError(f"Unknown layer: {name}")
        return self.values[LAYER_INDEX[name]]

    def dominant_layer(self) -> Tuple[str, float]:
        """Get the layer with highest activation."""
        max_idx = max(range(10), key=lambda i: self.values[i])
        return LAYER_NAMES[max_idx], self.values[max_idx]

    def top_layers(self, n: int = 3) -> List[Tuple[str, float]]:
        """Get the top N layers by activation."""
        indexed = [(LAYER_NAMES[i], self.values[i]) for i in range(10)]
        return sorted(indexed, key=lambda x: x[1], reverse=True)[:n]

    def to_dict(self) -> Dict[str, float]:
        """Convert to dictionary with layer names as keys."""
        return {LAYER_NAMES[i]: self.values[i] for i in range(10)}

    def __repr__(self) -> str:
        top = self.top_layers(3)
        top_str = ", ".join(f"{name}={val:.3f}" for name, val in top)
        return f"OntologicalVector({top_str})"


@dataclass
class TrainingExample:
    """
    A single training example for the ontological engine.

    Can have optional dimension-specific labels for supervised learning.
    """
    text: str

    # Optional: full 10D target vector
    target_vector: Optional[Tuple[float, ...]] = None

    # Optional: labels for specific dimensions only
    dimension_labels: Optional[Dict[str, float]] = None

    # Optional: task type for multi-task learning
    task_type: Optional[TaskType] = None

    # Optional: task-specific labels
    reasoning_label: Optional[float] = None  # 0-1 score for reasoning quality
    creativity_label: Optional[float] = None  # 0-1 score for creativity quality

    # Optional: metadata
    source: Optional[str] = None  # Dataset source

    def has_supervision(self) -> bool:
        """Check if this example has any supervision signals."""
        return (
            self.target_vector is not None or
            self.dimension_labels is not None or
            self.reasoning_label is not None or
            self.creativity_label is not None
        )


@dataclass
class TrainingBatch:
    """A batch of training examples."""
    texts: List[str]
    target_vectors: Optional[List[Optional[Tuple[float, ...]]]] = None
    dimension_labels: Optional[List[Optional[Dict[str, float]]]] = None
    task_types: Optional[List[Optional[TaskType]]] = None
    reasoning_labels: Optional[List[Optional[float]]] = None
    creativity_labels: Optional[List[Optional[float]]] = None

    @classmethod
    def from_examples(cls, examples: List[TrainingExample]) -> "TrainingBatch":
        """Create a batch from a list of examples."""
        return cls(
            texts=[e.text for e in examples],
            target_vectors=[e.target_vector for e in examples],
            dimension_labels=[e.dimension_labels for e in examples],
            task_types=[e.task_type for e in examples],
            reasoning_labels=[e.reasoning_label for e in examples],
            creativity_labels=[e.creativity_label for e in examples],
        )


@dataclass
class TrainingMetrics:
    """Metrics from a training step or epoch."""
    step: int
    epoch: int
    total_loss: float
    ontological_loss: float
    purity_loss: float
    reasoning_loss: Optional[float] = None
    creativity_loss: Optional[float] = None

    # Evaluation metrics
    reasoning_accuracy: Optional[float] = None
    creativity_score: Optional[float] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "step": self.step,
            "epoch": self.epoch,
            "total_loss": self.total_loss,
            "ontological_loss": self.ontological_loss,
            "purity_loss": self.purity_loss,
            "reasoning_loss": self.reasoning_loss,
            "creativity_loss": self.creativity_loss,
            "reasoning_accuracy": self.reasoning_accuracy,
            "creativity_score": self.creativity_score,
        }
