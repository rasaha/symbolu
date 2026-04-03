"""
Kosha Entropy Computation
=========================

╔═══════════════════════════════════════════════════════════════════════════════╗
║                         CORE/SUBSTRATE LAYER                                   ║
║                                                                                ║
║  Deterministic, zero-LLM formula for Kosha entropy computation.                ║
║  Measures layer disagreement between source and target koshas.                 ║
╚═══════════════════════════════════════════════════════════════════════════════╝

Kosha Entropy Definition:
    Measures layer disagreement when:
    - Source kosha (where input originates)
    - Target kosha (what domain is invoked)

    Formula: kosha_entropy = distance(source_kosha, target_kosha)

    Interpretation:
    - Same kosha source/target → low entropy (close to 0.0)
    - Distant kosha layers → high entropy (close to 1.0)

The five koshas (consciousness layers) in order:
    1. Annamaya   - Physical sheath
    2. Pranamaya  - Energy/vital sheath
    3. Manomaya   - Mental sheath
    4. Vijnanamaya - Wisdom/intellect sheath
    5. Anandamaya - Bliss sheath

This module:
    - Computes kosha entropy from source/target profiles
    - Provides explainability trace
    - Is fully deterministic (same input → same output)
    - Has NO side effects

Version: 1.0
Date: 2025-12-21
"""

from typing import Tuple, Dict
import math

from agentic.entropy.types import KoshaProfile, EntropyTraceEntry


# =============================================================================
# Constants
# =============================================================================

# Canonical kosha ordering (5-layer model)
KOSHA_ORDER = (
    "annamaya",      # Physical sheath (Layer 1)
    "pranamaya",     # Energy/vital sheath (Layer 2)
    "manomaya",      # Mental sheath (Layer 3)
    "vijnanamaya",   # Wisdom/intellect sheath (Layer 4)
    "anandamaya",    # Bliss sheath (Layer 5)
)

# Layer indices for distance computation
KOSHA_INDEX = {kosha: idx for idx, kosha in enumerate(KOSHA_ORDER)}

# Maximum distance (between layer 0 and layer 4)
MAX_LAYER_DISTANCE = len(KOSHA_ORDER) - 1

# Human-readable kosha descriptions
KOSHA_DESCRIPTIONS = {
    "annamaya": "Physical",
    "pranamaya": "Energy/Vital",
    "manomaya": "Mental/Emotional",
    "vijnanamaya": "Intellectual/Wisdom",
    "anandamaya": "Bliss/Transcendent",
}


# =============================================================================
# Main Computation Functions
# =============================================================================

def compute_kosha_entropy(
    source_profile: KoshaProfile,
    target_profile: KoshaProfile,
) -> Tuple[float, EntropyTraceEntry]:
    """
    Compute Kosha entropy from source and target kosha profiles.

    This measures the structural distance between where input originates
    (source kosha) and where the output domain is invoked (target kosha).

    Algorithm:
        1. Find dominant kosha in source profile (where input comes from)
        2. Find dominant kosha in target profile (what domain is invoked)
        3. Compute normalized distance between layers
        4. Apply activation-weighted distance for smoother gradients

    Args:
        source_profile: KoshaProfile representing input origin
        target_profile: KoshaProfile representing output domain

    Returns:
        Tuple of (entropy_value, trace_entry) where:
        - entropy_value is in [0.0, 1.0]
        - trace_entry contains explainability information

    Determinism Guarantee:
        Same input profiles always produce same output.

    Examples:
        # Same layer (emotional input → emotional output)
        source = KoshaProfile(0.1, 0.1, 0.8, 0.0, 0.0)  # manomaya dominant
        target = KoshaProfile(0.1, 0.1, 0.8, 0.0, 0.0)  # manomaya dominant
        entropy, _ = compute_kosha_entropy(source, target)
        # entropy ≈ 0.0 (same layer)

        # Distant layers (emotional input → intellectual output)
        source = KoshaProfile(0.1, 0.1, 0.8, 0.0, 0.0)  # manomaya (layer 3)
        target = KoshaProfile(0.0, 0.0, 0.1, 0.9, 0.0)  # vijnanamaya (layer 4)
        entropy, _ = compute_kosha_entropy(source, target)
        # entropy ≈ 0.25 (1 layer distance / 4 max)
    """
    # Get dominant koshas
    source_dominant = source_profile.get_dominant_kosha()
    target_dominant = target_profile.get_dominant_kosha()

    # Get layer indices
    source_idx = KOSHA_INDEX[source_dominant]
    target_idx = KOSHA_INDEX[target_dominant]

    # Compute absolute layer distance
    layer_distance = abs(source_idx - target_idx)

    # Normalize to [0, 1]
    if MAX_LAYER_DISTANCE > 0:
        base_entropy = layer_distance / MAX_LAYER_DISTANCE
    else:
        base_entropy = 0.0

    # Apply activation weighting for smoother gradients
    # The entropy is reduced if both profiles have strong agreement
    # in their dominant layers (high activation values)
    source_activation = getattr(source_profile, source_dominant)
    target_activation = getattr(target_profile, target_dominant)

    # Activation confidence (how certain we are about the dominants)
    activation_confidence = (source_activation + target_activation) / 2.0

    # Compute weighted entropy considering activation spread
    activation_entropy = _compute_activation_spread_entropy(source_profile, target_profile)

    # Final entropy is weighted combination
    # - Base entropy from layer distance (60%)
    # - Activation spread entropy (40%)
    entropy = 0.6 * base_entropy + 0.4 * activation_entropy

    # Clamp to [0.0, 1.0]
    entropy = max(0.0, min(1.0, entropy))

    # Generate explanation
    reason = _generate_reason(
        source_dominant, target_dominant,
        source_activation, target_activation,
        layer_distance, entropy
    )
    trace = _create_trace(entropy, source_profile, target_profile, reason)

    return entropy, trace


def compute_kosha_entropy_simple(
    source_kosha: str,
    target_kosha: str,
) -> Tuple[float, EntropyTraceEntry]:
    """
    Simplified kosha entropy computation from kosha names.

    Args:
        source_kosha: Name of source kosha (e.g., "manomaya")
        target_kosha: Name of target kosha (e.g., "vijnanamaya")

    Returns:
        Tuple of (entropy_value, trace_entry)
    """
    # Validate kosha names
    if source_kosha not in KOSHA_INDEX:
        raise ValueError(f"Unknown source kosha: {source_kosha}")
    if target_kosha not in KOSHA_INDEX:
        raise ValueError(f"Unknown target kosha: {target_kosha}")

    # Get layer indices
    source_idx = KOSHA_INDEX[source_kosha]
    target_idx = KOSHA_INDEX[target_kosha]

    # Compute normalized distance
    layer_distance = abs(source_idx - target_idx)
    entropy = layer_distance / MAX_LAYER_DISTANCE if MAX_LAYER_DISTANCE > 0 else 0.0

    # Generate explanation
    source_desc = KOSHA_DESCRIPTIONS.get(source_kosha, source_kosha)
    target_desc = KOSHA_DESCRIPTIONS.get(target_kosha, target_kosha)

    if layer_distance == 0:
        reason = f"Same layer ({source_desc})"
    else:
        direction = "higher" if target_idx > source_idx else "lower"
        reason = f"{source_desc} input routed to {target_desc} output ({layer_distance} layer{'s' if layer_distance > 1 else ''} {direction})"

    trace = EntropyTraceEntry(
        metric_name="kosha_entropy",
        value=entropy,
        reason=reason,
        components=(
            ("source_kosha", float(source_idx)),
            ("target_kosha", float(target_idx)),
            ("layer_distance", float(layer_distance)),
        ),
    )

    return entropy, trace


# =============================================================================
# Helper Functions
# =============================================================================

def _compute_activation_spread_entropy(
    source_profile: KoshaProfile,
    target_profile: KoshaProfile,
) -> float:
    """
    Compute entropy from activation spread between profiles.

    Measures how much the activation patterns differ across all layers.
    Uses Euclidean distance in the 5D kosha activation space.
    """
    source_vec = source_profile.get_activation_vector()
    target_vec = target_profile.get_activation_vector()

    # Compute squared differences
    squared_diffs = [(s - t) ** 2 for s, t in zip(source_vec, target_vec)]

    # Euclidean distance
    distance = math.sqrt(sum(squared_diffs))

    # Maximum possible distance is sqrt(2) (e.g., [1,0,0,0,0] vs [0,1,0,0,0])
    # For normalized [0,1] vectors of length 5, max distance is sqrt(2)
    max_distance = math.sqrt(2.0)

    # Normalize to [0, 1]
    return min(1.0, distance / max_distance)


def _create_trace(
    entropy: float,
    source_profile: KoshaProfile,
    target_profile: KoshaProfile,
    reason: str,
) -> EntropyTraceEntry:
    """Create an explainability trace entry."""
    source_dominant = source_profile.get_dominant_kosha()
    target_dominant = target_profile.get_dominant_kosha()

    components = (
        ("source_dominant", float(KOSHA_INDEX[source_dominant])),
        ("target_dominant", float(KOSHA_INDEX[target_dominant])),
        ("source_activation", getattr(source_profile, source_dominant)),
        ("target_activation", getattr(target_profile, target_dominant)),
    )

    return EntropyTraceEntry(
        metric_name="kosha_entropy",
        value=entropy,
        reason=reason,
        components=components,
    )


def _generate_reason(
    source_dominant: str,
    target_dominant: str,
    source_activation: float,
    target_activation: float,
    layer_distance: int,
    entropy: float,
) -> str:
    """Generate human-readable explanation for the entropy value."""
    source_desc = KOSHA_DESCRIPTIONS.get(source_dominant, source_dominant)
    target_desc = KOSHA_DESCRIPTIONS.get(target_dominant, target_dominant)

    # Same layer
    if layer_distance == 0:
        if entropy < 0.1:
            return f"Coherent {source_desc} processing"
        else:
            return f"Same layer ({source_desc}) with diffused activation"

    # Different layers
    if layer_distance == 1:
        return f"{source_desc} input routed to adjacent {target_desc} output"
    elif layer_distance == 2:
        return f"{source_desc} input routed to {target_desc} output (moderate gap)"
    elif layer_distance >= 3:
        return f"{source_desc} input routed to distant {target_desc} output (significant gap)"
    else:
        return f"{source_desc} → {target_desc} (distance: {layer_distance})"


# =============================================================================
# Utility Functions
# =============================================================================

def get_kosha_index(kosha_name: str) -> int:
    """Get the layer index for a kosha name."""
    if kosha_name not in KOSHA_INDEX:
        raise ValueError(f"Unknown kosha: {kosha_name}")
    return KOSHA_INDEX[kosha_name]


def get_kosha_name(index: int) -> str:
    """Get the kosha name for a layer index."""
    if index < 0 or index >= len(KOSHA_ORDER):
        raise ValueError(f"Invalid kosha index: {index}")
    return KOSHA_ORDER[index]


def kosha_distance(kosha_a: str, kosha_b: str) -> int:
    """Compute the layer distance between two koshas."""
    return abs(KOSHA_INDEX[kosha_a] - KOSHA_INDEX[kosha_b])
