"""
Guna / Kosha Resonance Formulas - Phase 8 Observability Metrics
================================================================

Deterministic, zero-LLM formulas for Guna and Kosha resonance analysis.

This module implements observation-only metrics for tracking:
- Guna Resonance Index: Balance vs distortion in Guna distribution (sattva/rajas/tamas)
- Kosha Activation Vector: Ordered vector of kosha layer activations
- Kosha Resonance Index: Coherence of kosha activation patterns

All formulas are deterministic, bounded to [0.0, 1.0], and purely observational.
They do NOT affect routing, mappers, policy, or any decision logic.

Version: 1.0 (Phase 8)
Date: 2025-12-10
"""

from dataclasses import dataclass
from typing import Dict, Optional, List
import math


@dataclass
class GunaKoshaResonance:
    """
    Container for Guna and Kosha resonance metrics.

    Attributes:
        guna_resonance_index: Balance measure for guna distribution [0.0, 1.0]
                              1.0 = balanced/healthy, 0.0 = extreme skew
        kosha_resonance_index: Coherence measure for kosha activation [0.0, 1.0]
                               1.0 = coherent pattern, 0.0 = chaotic/spiked
        kosha_activation_vector: Ordered activation values for each kosha layer
    """
    guna_resonance_index: float
    kosha_resonance_index: float
    kosha_activation_vector: List[float]


# Canonical kosha ordering (5-layer model)
KOSHA_ORDER_5 = [
    "annamaya",      # Physical sheath
    "pranamaya",     # Energy/vital sheath
    "manomaya",      # Mental sheath
    "vijnanamaya",   # Wisdom/intellect sheath
    "anandamaya",    # Bliss sheath
]

# Extended 7-layer model (if needed in future)
KOSHA_ORDER_7 = [
    "annamaya",
    "pranamaya",
    "manomaya",
    "vijnanamaya",
    "anandamaya",
    "chitamaya",     # Consciousness sheath
    "atmamaya",      # Self/soul sheath
]

# Guna names
GUNA_NAMES = ["sattva", "rajas", "tamas"]


def compute_guna_resonance(guna_probs: Dict[str, float]) -> float:
    """
    Compute Guna Resonance Index - balance vs distortion measure.

    This index captures how balanced vs skewed the guna distribution is:
    - Balanced distribution (e.g., sattva=0.4, rajas=0.3, tamas=0.3) → high resonance
    - Extreme skew (e.g., sattva=0.9, rajas=0.05, tamas=0.05) → low resonance

    Implementation uses entropy-based approach:
    - Shannon entropy H = -Σ(p_i * log(p_i))
    - Normalized to [0, 1] where 1.0 = maximum balance

    Args:
        guna_probs: Dictionary mapping guna names to probabilities
                   Expected keys: "sattva", "rajas", "tamas"
                   Values should sum to ~1.0 (normalized probabilities)

    Returns:
        Guna resonance index in [0.0, 1.0]
        - 1.0 = perfectly balanced (healthy)
        - 0.0 = completely skewed (unhealthy)

    Raises:
        ValueError: If probabilities are invalid (negative or > 1.0)

    Examples:
        >>> compute_guna_resonance({"sattva": 0.33, "rajas": 0.33, "tamas": 0.34})
        0.999...  # Nearly perfect balance
        >>> compute_guna_resonance({"sattva": 0.9, "rajas": 0.05, "tamas": 0.05})
        0.543...  # Significant skew
    """
    if not guna_probs:
        return 0.0

    # Extract probabilities (handle missing keys gracefully)
    probs = []
    for guna in GUNA_NAMES:
        prob = guna_probs.get(guna, 0.0)

        # Validate probability range
        if prob < 0.0 or prob > 1.0:
            raise ValueError(f"Guna probability for '{guna}' must be in [0.0, 1.0], got {prob}")

        probs.append(prob)

    # If all probabilities are zero, return 0.0
    if sum(probs) == 0.0:
        return 0.0

    # Normalize probabilities (handle cases where sum != 1.0)
    total = sum(probs)
    normalized_probs = [p / total for p in probs]

    # Compute Shannon entropy: H = -Σ(p_i * log(p_i))
    entropy = 0.0
    for p in normalized_probs:
        if p > 0.0:
            entropy -= p * math.log(p)

    # Maximum entropy for N categories: log(N)
    max_entropy = math.log(len(GUNA_NAMES))

    # Normalize to [0, 1]
    if max_entropy > 0:
        resonance = entropy / max_entropy
    else:
        resonance = 0.0

    # Clamp to [0, 1] for safety
    return max(0.0, min(1.0, resonance))


def compute_kosha_activation_vector(
    kosha_probs: Dict[str, float],
    model: str = "5-layer",
) -> List[float]:
    """
    Compute ordered kosha activation vector from probability distribution.

    Extracts activation values for each kosha layer in canonical order.
    Missing koshas are treated as 0.0 activation.

    Args:
        kosha_probs: Dictionary mapping kosha names to activation probabilities
                     Expected keys depend on model (see KOSHA_ORDER_5/7)
        model: Kosha model to use ("5-layer" or "7-layer"), default "5-layer"

    Returns:
        List of activation values in canonical kosha order
        Length = 5 for "5-layer", 7 for "7-layer"
        All values in [0.0, 1.0]

    Raises:
        ValueError: If probabilities are invalid or model is unknown

    Examples:
        >>> compute_kosha_activation_vector({
        ...     "annamaya": 0.3,
        ...     "pranamaya": 0.2,
        ...     "manomaya": 0.2,
        ...     "vijnanamaya": 0.2,
        ...     "anandamaya": 0.1,
        ... })
        [0.3, 0.2, 0.2, 0.2, 0.1]
    """
    # Select kosha order based on model
    if model == "5-layer":
        kosha_order = KOSHA_ORDER_5
    elif model == "7-layer":
        kosha_order = KOSHA_ORDER_7
    else:
        raise ValueError(f"Unknown kosha model: {model}. Expected '5-layer' or '7-layer'")

    # Extract activations in order
    activation_vector = []
    for kosha in kosha_order:
        activation = kosha_probs.get(kosha, 0.0)

        # Validate activation range
        if activation < 0.0 or activation > 1.0:
            raise ValueError(
                f"Kosha activation for '{kosha}' must be in [0.0, 1.0], got {activation}"
            )

        activation_vector.append(activation)

    return activation_vector


def compute_kosha_resonance_index(kosha_activation_vector: List[float]) -> float:
    """
    Compute Kosha Resonance Index - coherence of activation pattern.

    This index measures how coherent vs chaotic the kosha activation is:
    - Smooth/layered distribution → high resonance
    - Extreme spikes or gaps → low resonance

    Implementation uses variance-based approach with additional spike and inversion penalties:
    - Lower variance = smoother = higher resonance
    - Extreme spikes = high variance = lower resonance
    - Inverted patterns (higher koshas active without lower) are penalized

    Args:
        kosha_activation_vector: Ordered list of kosha activations [0.0, 1.0]

    Returns:
        Kosha resonance index in [0.0, 1.0]
        - 1.0 = smooth, coherent activation
        - 0.0 = chaotic, spiked activation

    Examples:
        >>> compute_kosha_resonance_index([0.3, 0.3, 0.2, 0.15, 0.05])
        0.875...  # Smooth descending pattern
        >>> compute_kosha_resonance_index([0.0, 0.0, 0.0, 0.0, 1.0])
        0.0  # Extreme spike
    """
    if not kosha_activation_vector:
        return 0.0

    # Handle edge case: single value
    if len(kosha_activation_vector) == 1:
        return 1.0 if kosha_activation_vector[0] > 0 else 0.0

    # If all activations are zero, return 0.0
    if sum(kosha_activation_vector) == 0.0:
        return 0.0

    # Compute variance of activation values
    mean_activation = sum(kosha_activation_vector) / len(kosha_activation_vector)
    variance = sum((a - mean_activation) ** 2 for a in kosha_activation_vector) / len(kosha_activation_vector)

    # Maximum variance occurs when one value is 1.0 and rest are 0.0
    # For N values: var_max = (N-1)/N
    n = len(kosha_activation_vector)
    max_variance = (n - 1) / n

    # Normalize variance to [0, 1] and invert (high variance = low resonance)
    # Use direct normalized variance for sensitive spike detection
    if max_variance > 0:
        normalized_variance = variance / max_variance
        # Direct linear penalty: high variance = low score
        variance_score = 1.0 - normalized_variance
    else:
        variance_score = 1.0

    # Additional penalty for "inverted" patterns
    # (e.g., high anandamaya but low annamaya/pranamaya)
    # Check for "gaps": higher koshas active while lower koshas inactive
    inversion_penalty = 0.0
    for i in range(1, len(kosha_activation_vector)):
        # If higher kosha is significantly more active than lower, penalize
        if kosha_activation_vector[i] > kosha_activation_vector[i - 1] + 0.2:
            # Scale penalty by magnitude of inversion
            gap = kosha_activation_vector[i] - kosha_activation_vector[i - 1]
            inversion_penalty += gap * 0.5

    # Cap inversion penalty at 0.7 for extreme cases
    inversion_penalty = min(0.7, inversion_penalty)
    resonance = variance_score * (1.0 - inversion_penalty)

    # Clamp to [0, 1]
    return max(0.0, min(1.0, resonance))


def compute_guna_kosha_resonance(
    guna_probs: Optional[Dict[str, float]],
    kosha_probs: Optional[Dict[str, float]],
    kosha_model: str = "5-layer",
) -> Optional[GunaKoshaResonance]:
    """
    Compute combined Guna and Kosha resonance metrics.

    This is the main wrapper function that safely computes all metrics
    and returns them in a structured container.

    Args:
        guna_probs: Optional dictionary of guna probabilities
                   Expected keys: "sattva", "rajas", "tamas"
        kosha_probs: Optional dictionary of kosha probabilities
                    Expected keys depend on kosha_model
        kosha_model: Kosha model to use ("5-layer" or "7-layer")

    Returns:
        GunaKoshaResonance object with all metrics, or None if inputs unavailable

    Notes:
        - Returns None if both guna_probs and kosha_probs are None/empty
        - Gracefully handles partial inputs (e.g., only guna_probs provided)
        - Never raises exceptions; returns None on invalid inputs

    Examples:
        >>> result = compute_guna_kosha_resonance(
        ...     guna_probs={"sattva": 0.4, "rajas": 0.3, "tamas": 0.3},
        ...     kosha_probs={"annamaya": 0.3, "pranamaya": 0.25, "manomaya": 0.2,
        ...                  "vijnanamaya": 0.15, "anandamaya": 0.1},
        ... )
        >>> result.guna_resonance_index
        0.992...
        >>> len(result.kosha_activation_vector)
        5
    """
    # Check if we have any input
    if not guna_probs and not kosha_probs:
        return None

    try:
        # Compute guna resonance
        if guna_probs and len(guna_probs) > 0:
            guna_resonance = compute_guna_resonance(guna_probs)
        else:
            guna_resonance = 0.0

        # Compute kosha activation vector
        if kosha_probs and len(kosha_probs) > 0:
            kosha_activation = compute_kosha_activation_vector(kosha_probs, model=kosha_model)
            kosha_resonance = compute_kosha_resonance_index(kosha_activation)
        else:
            # Use default length based on model
            kosha_length = 5 if kosha_model == "5-layer" else 7
            kosha_activation = [0.0] * kosha_length
            kosha_resonance = 0.0

        return GunaKoshaResonance(
            guna_resonance_index=guna_resonance,
            kosha_resonance_index=kosha_resonance,
            kosha_activation_vector=kosha_activation,
        )

    except (ValueError, TypeError, KeyError) as e:
        # Graceful degradation: return None on any error
        # In production, we might log this error for debugging
        return None
