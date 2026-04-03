"""
DHA (Delivery Harmonization Algorithm) Math Utilities
======================================================

Deterministic math functions for DHA computation.

All functions are:
- Pure (no side effects)
- Deterministic (same inputs = same outputs)
- Numerically stable (handles edge cases)

Version: 1.0
Date: 2025-12-22
"""

import math
from typing import Tuple, List


# =============================================================================
# Constants
# =============================================================================

# Natural logarithm constants for entropy normalization
LN_3: float = math.log(3)   # ≈ 1.0986 - for Guna entropy (3 components)
LN_5: float = math.log(5)   # ≈ 1.6094 - for Kosha entropy (5 layers)
LN_10: float = math.log(10)  # ≈ 2.3026 - for Dimensional entropy (10 domains)

# Default epsilon for numerical stability
EPSILON: float = 1e-9

# Maximum exponent for softmax to prevent overflow
MAX_EXP: float = 500.0


# =============================================================================
# Clipping and Clamping
# =============================================================================

def clip(value: float, min_val: float, max_val: float) -> float:
    """
    Clip value to range [min_val, max_val].

    Args:
        value: Value to clip
        min_val: Minimum bound
        max_val: Maximum bound

    Returns:
        Clipped value

    Example:
        >>> clip(1.5, 0.0, 1.0)
        1.0
        >>> clip(-0.1, 0.0, 1.0)
        0.0
        >>> clip(0.5, 0.0, 1.0)
        0.5
    """
    if min_val > max_val:
        raise ValueError(f"min_val ({min_val}) cannot exceed max_val ({max_val})")
    return max(min_val, min(max_val, value))


def clamp(value: float, min_val: float = 0.0, max_val: float = 1.0) -> float:
    """
    Clamp value to range [min_val, max_val].

    Alias for clip with default bounds [0, 1].

    Args:
        value: Value to clamp
        min_val: Minimum bound (default: 0.0)
        max_val: Maximum bound (default: 1.0)

    Returns:
        Clamped value
    """
    return clip(value, min_val, max_val)


# =============================================================================
# Softmax
# =============================================================================

def softmax(logits: Tuple[float, ...], temperature: float = 1.0) -> Tuple[float, ...]:
    """
    Compute numerically stable softmax.

    Uses the log-sum-exp trick for numerical stability:
        softmax(x)_i = exp(x_i - max(x)) / sum(exp(x_j - max(x)))

    Args:
        logits: Tuple of logit values
        temperature: Softmax temperature (default: 1.0)
                    Higher = more uniform, Lower = more peaked

    Returns:
        Tuple of probabilities that sum to 1.0

    Example:
        >>> softmax((1.0, 2.0, 3.0))
        (0.0900..., 0.2447..., 0.6652...)
    """
    if len(logits) == 0:
        return ()

    if temperature <= 0.0:
        raise ValueError(f"temperature must be positive, got {temperature}")

    # Apply temperature scaling
    scaled = tuple(x / temperature for x in logits)

    # Find max for numerical stability
    max_logit = max(scaled)

    # Compute exp(x - max) to prevent overflow
    exp_shifted = []
    for x in scaled:
        diff = x - max_logit
        # Clamp to prevent overflow
        if diff > MAX_EXP:
            diff = MAX_EXP
        elif diff < -MAX_EXP:
            diff = -MAX_EXP
        exp_shifted.append(math.exp(diff))

    # Sum of exponents
    exp_sum = sum(exp_shifted)

    # Prevent division by zero
    if exp_sum < EPSILON:
        # Uniform distribution as fallback
        n = len(logits)
        return tuple(1.0 / n for _ in range(n))

    # Normalize
    probs = tuple(e / exp_sum for e in exp_shifted)

    # Verify sum (should be very close to 1.0)
    prob_sum = sum(probs)
    if abs(prob_sum - 1.0) > EPSILON:
        # Renormalize to ensure exact sum
        probs = tuple(p / prob_sum for p in probs)

    return probs


def softmax3(l1: float, l2: float, l3: float, temperature: float = 1.0) -> Tuple[float, float, float]:
    """
    Specialized softmax for 3 logits (tone selection).

    Args:
        l1: First logit (sweet)
        l2: Second logit (jolt)
        l3: Third logit (metaphor)
        temperature: Softmax temperature

    Returns:
        Tuple of (w1, w2, w3) probabilities
    """
    result = softmax((l1, l2, l3), temperature)
    return (result[0], result[1], result[2])


# =============================================================================
# Entropy Normalization
# =============================================================================

def normalize_entropy_guna(H_G: float) -> float:
    """
    Normalize Guna entropy (Option A).

    Formula: H = H_G / ln(3)

    Args:
        H_G: Raw Guna entropy [0, ln(3)]

    Returns:
        Normalized entropy [0, 1]
    """
    if H_G is None:
        return 0.0
    return clamp(H_G / LN_3)


def normalize_entropy_dimensional(H_D: float) -> float:
    """
    Normalize Dimensional entropy (Option B).

    Formula: H = H_D / ln(10)

    Args:
        H_D: Raw Dimensional entropy [0, ln(10)]

    Returns:
        Normalized entropy [0, 1]
    """
    if H_D is None:
        return 0.0
    return clamp(H_D / LN_10)


def normalize_entropy_kosha(H_K: float) -> float:
    """
    Normalize Kosha entropy (Option C).

    Formula: H = H_K / ln(5)

    Args:
        H_K: Raw Kosha entropy [0, ln(5)]

    Returns:
        Normalized entropy [0, 1]
    """
    if H_K is None:
        return 0.0
    return clamp(H_K / LN_5)


def get_normalized_entropy(
    H_G: float = None,
    H_D: float = None,
    H_K: float = None,
    source: str = "guna"
) -> Tuple[float, str, float]:
    """
    Get normalized entropy based on source selection.

    Args:
        H_G: Guna entropy (Option A)
        H_D: Dimensional entropy (Option B)
        H_K: Kosha entropy (Option C)
        source: Which source to use ("guna", "dimensional", "kosha")

    Returns:
        Tuple of (normalized_H, entropy_source_used, raw_value)

    Default fallback if requested source is missing:
        1. Try requested source
        2. Fall back to any available source
        3. Return 0.0 if none available
    """
    # Try requested source first
    if source == "guna" and H_G is not None:
        return (normalize_entropy_guna(H_G), "guna", H_G)
    elif source == "dimensional" and H_D is not None:
        return (normalize_entropy_dimensional(H_D), "dimensional", H_D)
    elif source == "kosha" and H_K is not None:
        return (normalize_entropy_kosha(H_K), "kosha", H_K)

    # Fallback order: guna -> dimensional -> kosha
    if H_G is not None:
        return (normalize_entropy_guna(H_G), "guna", H_G)
    if H_D is not None:
        return (normalize_entropy_dimensional(H_D), "dimensional", H_D)
    if H_K is not None:
        return (normalize_entropy_kosha(H_K), "kosha", H_K)

    # No entropy available
    return (0.0, "none", 0.0)


# =============================================================================
# Tone Logit Computation
# =============================================================================

def compute_tone_logits(
    s: float,
    r: float,
    t: float,
    H: float,
    C_contr: float,
    k1: float,
    k2: float,
    k3: float,
    k4: float,
    k5: float,
    k6: float,
) -> Tuple[float, float, float]:
    """
    Compute tone logits for softmax.

    Formulas:
        l_sweet = k1*s - k2*t
        l_jolt  = k3*r + k4*C_contr
        l_meta  = k5*H + k6*r

    Args:
        s: Sattva component [0, 1]
        r: Rajas component [0, 1]
        t: Tamas component [0, 1]
        H: Normalized entropy [0, 1]
        C_contr: Contradiction metric [0, 1]
        k1-k6: Coefficients from ToneLogitConfig

    Returns:
        Tuple of (l_sweet, l_jolt, l_meta)
    """
    l_sweet = k1 * s - k2 * t
    l_jolt = k3 * r + k4 * C_contr
    l_meta = k5 * H + k6 * r

    return (l_sweet, l_jolt, l_meta)


# =============================================================================
# Intensity and Restraint
# =============================================================================

def compute_intensity(
    C_s: float,
    M: float,
    H: float,
    alpha1: float,
    alpha2: float,
    alpha3: float,
    I_min: float,
    I_max: float,
) -> float:
    """
    Compute intensity scalar.

    Formula:
        I = clip(alpha1*C_s + alpha2*M - alpha3*H, I_min, I_max)

    Args:
        C_s: Structural coherence score [0, 1]
        M: Motion/transformation magnitude [0, 1]
        H: Normalized entropy [0, 1]
        alpha1-alpha3: Coefficients from IntensityConfig
        I_min: Minimum intensity
        I_max: Maximum intensity

    Returns:
        Intensity scalar in [I_min, I_max]
    """
    raw_I = alpha1 * C_s + alpha2 * M - alpha3 * H
    return clip(raw_I, I_min, I_max)


def compute_restraint(
    risk_bias: float,
    escalation_bias: float,
) -> float:
    """
    Compute restraint scalar.

    Formula:
        R = clamp(1 - risk_bias - escalation_bias, 0, 1)

    Args:
        risk_bias: Risk bias value [0, 1]
        escalation_bias: Escalation bias value [0, 1]

    Returns:
        Restraint scalar in [0, 1]
    """
    raw_R = 1.0 - risk_bias - escalation_bias
    return clamp(raw_R, 0.0, 1.0)


# =============================================================================
# Delivery Modulation Factor
# =============================================================================

def compute_delivery_factor(
    tone_weights: Tuple[float, float, float],
    I: float,
    R: float,
) -> float:
    """
    Compute delivery modulation factor D.

    Formula:
        D = T × I × R

    Where T is the norm of the tone weights vector.
    Since weights sum to 1, T is effectively 1.0.

    For the final output:
        OUTPUT_final = BASE_output × D

    Args:
        tone_weights: (sweet, jolt, metaphor) weights
        I: Intensity scalar
        R: Restraint scalar

    Returns:
        Delivery modulation factor D
    """
    # T = norm of tone weights
    # Since weights always sum to 1, we use the max weight as the effective T
    # This gives more modulation when tone is strongly dominant
    T = max(tone_weights)

    D = T * I * R
    return D


def compute_delivery_factor_simple(I: float, R: float) -> float:
    """
    Simplified delivery factor (T = 1).

    Formula:
        D = I × R

    Use this when T is always 1 (normalized tone weights).

    Args:
        I: Intensity scalar
        R: Restraint scalar

    Returns:
        Delivery modulation factor D
    """
    return I * R


# =============================================================================
# Rounding for Audits
# =============================================================================

def round_for_audit(value: float, precision: int = 6) -> float:
    """
    Round value for audit output.

    Ensures consistent float representation in audits.

    Args:
        value: Value to round
        precision: Decimal places (default: 6)

    Returns:
        Rounded value
    """
    return round(value, precision)


def round_dict_for_audit(d: dict, precision: int = 6) -> dict:
    """
    Round all float values in a dictionary for audit.

    Args:
        d: Dictionary with float values
        precision: Decimal places

    Returns:
        Dictionary with rounded float values
    """
    result = {}
    for k, v in d.items():
        if isinstance(v, float):
            result[k] = round_for_audit(v, precision)
        elif isinstance(v, dict):
            result[k] = round_dict_for_audit(v, precision)
        elif isinstance(v, (list, tuple)):
            result[k] = [
                round_for_audit(x, precision) if isinstance(x, float) else x
                for x in v
            ]
        else:
            result[k] = v
    return result


# =============================================================================
# Public Exports
# =============================================================================

__all__ = [
    # Constants
    "LN_3",
    "LN_5",
    "LN_10",
    "EPSILON",
    # Clipping
    "clip",
    "clamp",
    # Softmax
    "softmax",
    "softmax3",
    # Entropy normalization
    "normalize_entropy_guna",
    "normalize_entropy_dimensional",
    "normalize_entropy_kosha",
    "get_normalized_entropy",
    # Tone computation
    "compute_tone_logits",
    # Intensity and restraint
    "compute_intensity",
    "compute_restraint",
    # Delivery factor
    "compute_delivery_factor",
    "compute_delivery_factor_simple",
    # Rounding
    "round_for_audit",
    "round_dict_for_audit",
]
