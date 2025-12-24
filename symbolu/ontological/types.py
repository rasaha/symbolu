"""
Ontological Types and Definitions
=================================

Core type definitions for the 10-dimensional ontological engine.
"""

from typing import Tuple, Dict, List, Optional, Any
from dataclasses import dataclass, field


# The 10 Ontological Layers
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

# Layer name to index mapping
LAYER_INDEX: Dict[str, int] = {name: i for i, name in enumerate(LAYER_NAMES)}


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
