"""
12D Ontological Backbone for Robotics
======================================

Defines the 12 ontological layers adapted for robotics applications.

Layer Semantics for Robotics:
    O1_POTENTIAL:   Sensor readiness
    O2_IDENTITY:    Localization (x, y, theta)
    O3_EXECUTION:   Motor commands
    O4_STRUCTURE:   Body schema/kinematics
    O5_COGNITION:   Perception processing
    O6_AGENCY:      Control mode/autonomy level
    O7_REASONING:   Path/task planning
    O8_PURPOSE:     Goal hierarchy
    O9_WITNESSES:   World model/scene
    O10_UNIFYING:   Multi-agent coordination
    O11_INTEGRATION: Sensor fusion
    O12_ABSOLVING:  Safety constraints
"""

from typing import Dict, Tuple
import numpy as np

from symbolu_robotics.core.types import OntologicalLayer, Layer12D


# Layer names in canonical order
LAYER_NAMES: Tuple[str, ...] = (
    "O1_POTENTIAL",
    "O2_IDENTITY",
    "O3_EXECUTION",
    "O4_STRUCTURE",
    "O5_COGNITION",
    "O6_AGENCY",
    "O7_REASONING",
    "O8_PURPOSE",
    "O9_WITNESSES",
    "O10_UNIFYING",
    "O11_INTEGRATION",
    "O12_ABSOLVING",
)

# Layer indices for fast lookup
LAYER_INDICES: Dict[str, int] = {name: i for i, name in enumerate(LAYER_NAMES)}

# Robotics-specific layer descriptions
LAYER_ROBOTICS_SEMANTICS: Dict[str, str] = {
    "O1_POTENTIAL": "Sensor readiness and system activation state",
    "O2_IDENTITY": "Localization and self-reference (where am I?)",
    "O3_EXECUTION": "Motor commands and actuator outputs",
    "O4_STRUCTURE": "Body schema, kinematics, joint configuration",
    "O5_COGNITION": "Perception processing and feature extraction",
    "O6_AGENCY": "Control mode and autonomy level",
    "O7_REASONING": "Path planning and logical reasoning",
    "O8_PURPOSE": "Goal hierarchy and task objectives",
    "O9_WITNESSES": "World model and environmental state",
    "O10_UNIFYING": "Multi-agent coordination and swarm behavior",
    "O11_INTEGRATION": "Sensor fusion and multi-modal integration",
    "O12_ABSOLVING": "Safety constraints and operational limits",
}


def layer_to_index(layer: str) -> int:
    """
    Convert layer name to index.

    Args:
        layer: Layer name (e.g., "O3_EXECUTION")

    Returns:
        Layer index (0-11)

    Raises:
        KeyError: If layer name is not valid
    """
    return LAYER_INDICES[layer]


def index_to_layer(index: int) -> str:
    """
    Convert index to layer name.

    Args:
        index: Layer index (0-11)

    Returns:
        Layer name

    Raises:
        IndexError: If index is out of range
    """
    return LAYER_NAMES[index]


def create_layer_vector(
    values: Dict[str, float] = None,
    default: float = 0.0
) -> Layer12D:
    """
    Create a 12D layer vector from named values.

    Args:
        values: Dict mapping layer names to values
        default: Default value for unspecified layers

    Returns:
        12D numpy array of layer values
    """
    vector = np.full(12, default, dtype=np.float32)

    if values:
        for layer, value in values.items():
            if layer in LAYER_INDICES:
                vector[LAYER_INDICES[layer]] = value

    return vector


def normalize_layer_vector(vector: Layer12D, method: str = "max") -> Layer12D:
    """
    Normalize a 12D layer vector.

    Args:
        vector: Input 12D vector
        method: Normalization method ("max", "l2", "softmax")

    Returns:
        Normalized 12D vector
    """
    if method == "max":
        max_val = np.max(np.abs(vector))
        if max_val > 0:
            return vector / max_val
        return vector

    elif method == "l2":
        norm = np.linalg.norm(vector)
        if norm > 0:
            return vector / norm
        return vector

    elif method == "softmax":
        exp_v = np.exp(vector - np.max(vector))  # Numerical stability
        return exp_v / np.sum(exp_v)

    else:
        raise ValueError(f"Unknown normalization method: {method}")


def get_dominant_layer(vector: Layer12D) -> Tuple[str, float]:
    """
    Get the dominant (highest value) layer.

    Args:
        vector: 12D layer vector

    Returns:
        Tuple of (layer_name, value)
    """
    idx = np.argmax(vector)
    return (LAYER_NAMES[idx], float(vector[idx]))


def get_layer_profile(vector: Layer12D) -> Dict[str, float]:
    """
    Convert layer vector to named profile dict.

    Args:
        vector: 12D layer vector

    Returns:
        Dict mapping layer names to values
    """
    return {name: float(vector[i]) for i, name in enumerate(LAYER_NAMES)}


def compute_layer_entropy(vector: Layer12D) -> float:
    """
    Compute entropy of layer activations.

    Higher entropy = more distributed activation.
    Lower entropy = more concentrated activation.

    Args:
        vector: 12D layer vector (non-negative)

    Returns:
        Entropy value
    """
    # Ensure non-negative
    v = np.maximum(vector, 0)

    # Normalize to probability distribution
    total = np.sum(v)
    if total <= 0:
        return 0.0

    p = v / total

    # Compute entropy (avoid log(0))
    p_safe = np.where(p > 0, p, 1)
    entropy = -np.sum(p * np.log(p_safe))

    # Normalize by max entropy (uniform distribution)
    max_entropy = np.log(12)
    return float(entropy / max_entropy)


def combine_layer_vectors(
    vectors: list,
    weights: list = None,
    method: str = "weighted_mean"
) -> Layer12D:
    """
    Combine multiple layer vectors.

    Args:
        vectors: List of 12D vectors
        weights: Optional weights for each vector
        method: Combination method ("weighted_mean", "max", "min")

    Returns:
        Combined 12D vector
    """
    if not vectors:
        return np.zeros(12, dtype=np.float32)

    vectors = np.array(vectors)

    if weights is None:
        weights = np.ones(len(vectors)) / len(vectors)
    else:
        weights = np.array(weights)
        weights = weights / np.sum(weights)

    if method == "weighted_mean":
        return np.sum(vectors * weights[:, np.newaxis], axis=0)

    elif method == "max":
        return np.max(vectors, axis=0)

    elif method == "min":
        return np.min(vectors, axis=0)

    else:
        raise ValueError(f"Unknown combination method: {method}")


# Layer groups for quick access
LOWER_LAYERS = frozenset({
    "O1_POTENTIAL", "O2_IDENTITY", "O3_EXECUTION",
    "O4_STRUCTURE", "O5_COGNITION", "O6_AGENCY"
})

HIGHER_LAYERS = frozenset({
    "O7_REASONING", "O8_PURPOSE", "O9_WITNESSES",
    "O10_UNIFYING", "O11_INTEGRATION", "O12_ABSOLVING"
})

# Perception-related layers
PERCEPTION_LAYERS = frozenset({
    "O1_POTENTIAL", "O5_COGNITION", "O11_INTEGRATION"
})

# Action-related layers
ACTION_LAYERS = frozenset({
    "O3_EXECUTION", "O6_AGENCY", "O7_REASONING"
})

# Safety-related layers
SAFETY_LAYERS = frozenset({
    "O6_AGENCY", "O12_ABSOLVING"
})
