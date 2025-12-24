"""
Ontological Types and Definitions
=================================

Core type definitions for the 10-dimensional ontological engine.
"""

from typing import Tuple, Dict, List, Optional, Any
from dataclasses import dataclass, field


# The 10 Ontological Layers (Patent-Exact Sequence)
# Lowest (most concrete) → Highest (most abstract)
# Karma → Identification → Body → Mind → Ego → Intellect → Soul → Witness → Atman → Brahman
LAYER_NAMES: Tuple[str, ...] = (
    "O1_EXECUTION",     # Karma - Actions, behaviors, consequences, output
    "O2_IDENTITY",      # Identification - Labels, roles, references, self-object
    "O3_FORM",          # Body - Structural, physical, representational form
    "O4_COGNITION",     # Mind - Attention, emotion, perception, mental movement
    "O5_AGENCY",        # Ego - Control, intent, authorship, decision authority
    "O6_REASONING",     # Intellect - Logic, inference, analysis, structured thinking
    "O7_PURPOSE",       # Soul - Meaning, motivation, intrinsic direction, why
    "O8_OBSERVATION",   # Witness - Meta-awareness, reflection, monitoring
    "O9_CORE",          # Atman - Unified self-reference, stable identity
    "O10_UNIVERSAL",    # Brahman - Coherence, absoluteness, highest abstraction
)

# Layer name to index mapping
LAYER_INDEX: Dict[str, int] = {name: i for i, name in enumerate(LAYER_NAMES)}

# Layer groups for task heads (patent-aligned indices)
REASONING_LAYERS: Tuple[int, ...] = (3, 5, 7)  # O4_COGNITION, O6_REASONING, O8_OBSERVATION
CREATIVITY_LAYERS: Tuple[int, ...] = (2, 6, 8)  # O3_FORM, O7_PURPOSE, O9_CORE

# Task types for training
class TaskType:
    REASONING = "reasoning"
    CREATIVITY = "creativity"
    GENERAL = "general"


@dataclass
class OntologicalConfig:
    """Configuration for the ontological engine."""
    input_dim: int = 768  # DistilBERT output
    hidden_dims: Tuple[int, ...] = (512, 256)
    output_dim: int = 10  # 10 ontological layers
    bhava_dim: int = 100  # 9 pairs × 10 sub-layers + 10 onto
    dropout: float = 0.1
    use_skip_connections: bool = True
    use_layer_norm: bool = True


@dataclass
class OntologicalVector:
    """
    A 10-dimensional vector representing ontological activations.
    """
    values: List[float] = field(default_factory=lambda: [0.0] * 10)

    def __post_init__(self):
        if len(self.values) != 10:
            raise ValueError(f"Expected 10 values, got {len(self.values)}")

    def to_dict(self) -> Dict[str, float]:
        """Convert to layer name -> value dictionary."""
        return {LAYER_NAMES[i]: self.values[i] for i in range(10)}

    @classmethod
    def from_dict(cls, d: Dict[str, float]) -> "OntologicalVector":
        """Create from layer name -> value dictionary."""
        values = [d.get(name, 0.0) for name in LAYER_NAMES]
        return cls(values=values)

    def dominant_layer(self) -> str:
        """Return the name of the dominant (highest) layer."""
        max_idx = self.values.index(max(self.values))
        return LAYER_NAMES[max_idx]

    def reasoning_score(self) -> float:
        """O6_REASONING activation."""
        return self.values[5]

    def creativity_score(self) -> float:
        """O2_FORMING activation."""
        return self.values[1]


@dataclass
class TrainingExample:
    """A training example with text and optional labels."""
    text: str
    onto_labels: Optional[Dict[str, float]] = None
    bhava_labels: Optional[List[float]] = None
    is_reasoning: bool = False
    is_creativity: bool = False
    reasoning_score: Optional[float] = None
    creativity_score: Optional[float] = None
    domain: Optional[int] = None  # 0-4: technical, reasoning, creative, action, governance

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for batch processing."""
        return {
            "text": self.text,
            "onto_labels": self.onto_labels,
            "bhava_labels": self.bhava_labels,
            "is_reasoning": self.is_reasoning,
            "is_creativity": self.is_creativity,
            "reasoning_score": self.reasoning_score,
            "creativity_score": self.creativity_score,
            "domain": self.domain,
        }


@dataclass
class TrainingBatch:
    """A batch of training examples."""
    texts: List[str]
    onto_targets: Optional[List[List[float]]] = None
    bhava_targets: Optional[List[List[float]]] = None
    reasoning_targets: Optional[List[float]] = None
    creativity_targets: Optional[List[float]] = None
    domains: Optional[List[int]] = None

    @classmethod
    def from_examples(cls, examples: List[TrainingExample]) -> "TrainingBatch":
        """Create batch from list of examples."""
        texts = [e.text for e in examples]

        # Collect onto labels if any exist
        onto_targets = None
        if any(e.onto_labels for e in examples):
            onto_targets = [
                [e.onto_labels.get(name, 0.0) for name in LAYER_NAMES] if e.onto_labels else [0.0] * 10
                for e in examples
            ]

        # Collect reasoning scores
        reasoning_targets = None
        if any(e.reasoning_score is not None for e in examples):
            reasoning_targets = [e.reasoning_score or 0.0 for e in examples]

        # Collect creativity scores
        creativity_targets = None
        if any(e.creativity_score is not None for e in examples):
            creativity_targets = [e.creativity_score or 0.0 for e in examples]

        # Collect domains
        domains = None
        if any(e.domain is not None for e in examples):
            domains = [e.domain or 0 for e in examples]

        return cls(
            texts=texts,
            onto_targets=onto_targets,
            reasoning_targets=reasoning_targets,
            creativity_targets=creativity_targets,
            domains=domains,
        )
