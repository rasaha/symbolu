"""
Internal Guna Mapping (PRIVATE)
===============================

╔═══════════════════════════════════════════════════════════════════════════════╗
║                    PRIVATE INTERNAL MODULE                                     ║
║                                                                                ║
║  This mapping is NOT exposed in public documentation or APIs.                  ║
║  It provides the internal conceptual foundation for posture dynamics.          ║
╚═══════════════════════════════════════════════════════════════════════════════╝

The posture system maps to Guna-like dynamics internally:
    - Sattva → coherence_bias (clarity, balance, harmony)
    - Rajas → exploration_bias (activity, change, adaptation)
    - Tamas → constraint_bias (inertia, stability, restraint)

IMPORTANT:
    - This is an INTERNAL implementation detail
    - No moral labels are applied
    - No ethical inference is performed
    - This mapping MUST NOT appear in:
        - Public documentation
        - API responses
        - User-facing strings
        - Error messages

Version: 1.0 (PRIVATE)
Date: 2025-12-22
"""

from typing import Dict, Tuple
from symbolu.posture.types import DecisionPostureProfile


# =============================================================================
# Internal Guna Mapping (NOT EXPORTED)
# =============================================================================

# This mapping is for internal computation only
_INTERNAL_GUNA_MAP: Dict[str, str] = {
    "sattva": "coherence_bias",
    "rajas": "exploration_bias",
    "tamas": "constraint_bias",
}

# Reverse mapping
_INTERNAL_BIAS_TO_GUNA: Dict[str, str] = {v: k for k, v in _INTERNAL_GUNA_MAP.items()}


# =============================================================================
# Internal Conversion Functions (NOT EXPORTED)
# =============================================================================

def _profile_to_internal_weights(profile: DecisionPostureProfile) -> Dict[str, float]:
    """
    Convert a public posture profile to internal weight representation.

    PRIVATE: Not for external use.
    """
    return {
        "sattva": profile.coherence_bias,
        "rajas": profile.exploration_bias,
        "tamas": profile.constraint_bias,
    }


def _internal_weights_to_profile(weights: Dict[str, float]) -> DecisionPostureProfile:
    """
    Convert internal weights back to a public posture profile.

    PRIVATE: Not for external use.
    """
    return DecisionPostureProfile(
        coherence_bias=weights.get("sattva", 1/3),
        exploration_bias=weights.get("rajas", 1/3),
        constraint_bias=weights.get("tamas", 1/3),
    )


# =============================================================================
# Internal Dynamics Computation (NOT EXPORTED)
# =============================================================================

def _compute_modulation_factor(
    profile: DecisionPostureProfile,
    dimension: str,
) -> float:
    """
    Compute the modulation factor for a specific dimension.

    This uses internal guna dynamics to determine how much
    a value should be adjusted based on the posture profile.

    PRIVATE: Not for external use.

    Args:
        profile: The posture profile
        dimension: One of "threshold", "sensitivity", "depth", "conservatism"

    Returns:
        Modulation factor in range [-1.0, 1.0]
    """
    weights = _profile_to_internal_weights(profile)
    s, r, t = weights["sattva"], weights["rajas"], weights["tamas"]

    # Different dimensions respond differently to guna weights
    if dimension == "threshold":
        # Thresholds: sattva raises (more careful), tamas lowers (more lenient)
        return (s - t) * 0.5 + r * 0.1

    elif dimension == "sensitivity":
        # Sensitivity: rajas increases (more reactive), tamas decreases
        return (r - t) * 0.6

    elif dimension == "depth":
        # Depth: sattva increases (more thorough), rajas decreases (faster)
        return (s - r) * 0.4

    elif dimension == "conservatism":
        # Conservatism: tamas increases (more cautious), rajas decreases (bolder)
        return (t - r) * 0.5 + s * 0.1

    elif dimension == "exploration":
        # Exploration: rajas increases, tamas decreases, sattva neutral
        return r * 0.6 - t * 0.4

    elif dimension == "cascade":
        # Cascade aggressiveness: rajas increases, sattva balances
        return r * 0.5 - s * 0.2

    else:
        # Unknown dimension: no modulation
        return 0.0


def _get_dominant_quality(profile: DecisionPostureProfile) -> Tuple[str, float]:
    """
    Determine the dominant quality in the profile.

    PRIVATE: Not for external use.

    Returns:
        Tuple of (internal_quality_name, dominance_factor)
    """
    weights = _profile_to_internal_weights(profile)

    max_weight = max(weights.values())
    for quality, weight in weights.items():
        if weight == max_weight:
            # Calculate dominance as difference from balanced
            dominance = (weight - 1/3) * 3  # Normalized to [0, 2]
            return (quality, dominance)

    return ("sattva", 0.0)  # Default fallback


# =============================================================================
# Balance Computation (NOT EXPORTED)
# =============================================================================

def _compute_balance_score(profile: DecisionPostureProfile) -> float:
    """
    Compute how balanced the profile is across all qualities.

    PRIVATE: Not for external use.

    Returns:
        Score in [0.0, 1.0] where 1.0 = perfectly balanced
    """
    weights = _profile_to_internal_weights(profile)
    ideal = 1/3

    # Compute variance from ideal
    variance = sum((w - ideal) ** 2 for w in weights.values()) / 3

    # Maximum variance is when one quality is 1.0 and others are 0.0
    # max_var = ((1-1/3)² + (0-1/3)² + (0-1/3)²) / 3 = 2/9
    max_variance = 2/9

    # Balance score is inverse of normalized variance
    if max_variance > 0:
        return 1.0 - (variance / max_variance)
    return 1.0
