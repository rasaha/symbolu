"""
Guna Entropy Computation
========================

╔═══════════════════════════════════════════════════════════════════════════════╗
║                         CORE/SUBSTRATE LAYER                                   ║
║                                                                                ║
║  Deterministic, zero-LLM formula for Guna entropy computation.                 ║
║  Measures internal imbalance across detected gunas.                            ║
╚═══════════════════════════════════════════════════════════════════════════════╝

Guna Entropy Definition:
    Measures internal imbalance across the three gunas (sattva, rajas, tamas).

    Formula: guna_entropy = 1 - normalized_variance(guna_distribution)

    Interpretation:
    - Balanced gunas → low entropy (close to 0.0)
    - Conflicting/skewed gunas → high entropy (close to 1.0)

This module:
    - Computes guna entropy from distribution
    - Provides explainability trace
    - Is fully deterministic (same input → same output)
    - Has NO side effects

Version: 1.0
Date: 2025-12-21
"""

from typing import Dict, Tuple, Optional
import math

from agentic.entropy.types import GunaProfile, EntropyTraceEntry


# =============================================================================
# Constants
# =============================================================================

GUNA_NAMES = ("sattva", "rajas", "tamas")

# Ideal balanced distribution (equal parts)
IDEAL_BALANCED = 1.0 / len(GUNA_NAMES)

# Shannon entropy of uniform distribution over 3 gunas
MAX_SHANNON_ENTROPY = math.log(len(GUNA_NAMES))


# =============================================================================
# Main Computation Function
# =============================================================================

def compute_guna_entropy(
    profile: GunaProfile,
) -> Tuple[float, EntropyTraceEntry]:
    """
    Compute Guna entropy from a guna distribution profile.

    This measures how imbalanced the guna distribution is:
    - Perfectly balanced (1/3, 1/3, 1/3) → entropy = 0.0 (perfect coherence)
    - Extremely skewed (1.0, 0.0, 0.0) → entropy = 1.0 (maximum incoherence)

    Algorithm:
        1. Normalize the distribution to sum to 1.0
        2. Compute normalized variance from ideal balanced state
        3. Return 1 - normalized_variance as entropy measure

    Args:
        profile: GunaProfile with sattva, rajas, tamas values

    Returns:
        Tuple of (entropy_value, trace_entry) where:
        - entropy_value is in [0.0, 1.0]
        - trace_entry contains explainability information

    Determinism Guarantee:
        Same input profile always produces same output.
    """
    # Get normalized profile (sum to 1.0)
    normalized = profile.normalized
    probs = [normalized.sattva, normalized.rajas, normalized.tamas]

    # Check for edge case: all zeros (shouldn't happen after normalization)
    if sum(probs) == 0.0:
        return 0.5, _create_trace(0.5, probs, "Undefined distribution (all zeros)")

    # Compute variance from ideal balanced state
    # variance = Σ(p_i - ideal)² / n
    variance = sum((p - IDEAL_BALANCED) ** 2 for p in probs) / len(probs)

    # Maximum variance occurs when one guna is 1.0 and others are 0.0
    # max_var = ((1 - 1/3)² + (0 - 1/3)² + (0 - 1/3)²) / 3
    #         = ((2/3)² + (1/3)² + (1/3)²) / 3
    #         = (4/9 + 1/9 + 1/9) / 3 = (6/9) / 3 = 2/9
    max_variance = 2.0 / 9.0

    # Normalize variance to [0, 1]
    if max_variance > 0:
        normalized_variance = variance / max_variance
    else:
        normalized_variance = 0.0

    # Entropy is the normalized variance
    # (high variance from balance = high entropy)
    entropy = normalized_variance

    # Clamp to [0.0, 1.0]
    entropy = max(0.0, min(1.0, entropy))

    # Generate explanation
    reason = _generate_reason(normalized, entropy)
    trace = _create_trace(entropy, probs, reason)

    return entropy, trace


def compute_guna_entropy_from_dict(
    guna_probs: Dict[str, float],
) -> Tuple[float, EntropyTraceEntry]:
    """
    Convenience function to compute guna entropy from a dictionary.

    Args:
        guna_probs: Dictionary with keys "sattva", "rajas", "tamas"
                   Missing keys are treated as 0.0

    Returns:
        Tuple of (entropy_value, trace_entry)
    """
    profile = GunaProfile(
        sattva=guna_probs.get("sattva", 0.0),
        rajas=guna_probs.get("rajas", 0.0),
        tamas=guna_probs.get("tamas", 0.0),
    )
    return compute_guna_entropy(profile)


# =============================================================================
# Helper Functions
# =============================================================================

def _create_trace(
    entropy: float,
    probs: list,
    reason: str,
) -> EntropyTraceEntry:
    """Create an explainability trace entry."""
    components = tuple(zip(GUNA_NAMES, probs))
    return EntropyTraceEntry(
        metric_name="guna_entropy",
        value=entropy,
        reason=reason,
        components=components,
    )


def _generate_reason(
    profile: GunaProfile,
    entropy: float,
) -> str:
    """Generate human-readable explanation for the entropy value."""
    # Identify dominant guna
    gunas = [
        ("Sattva", profile.sattva),
        ("Rajas", profile.rajas),
        ("Tamas", profile.tamas),
    ]
    sorted_gunas = sorted(gunas, key=lambda x: x[1], reverse=True)
    dominant = sorted_gunas[0]
    suppressed = sorted_gunas[2]

    # Check for balance
    variance = sum((g[1] - IDEAL_BALANCED) ** 2 for g in gunas)
    if variance < 0.01:
        return "Well-balanced guna distribution"

    # Generate description based on dominance pattern
    if entropy < 0.2:
        return f"Near-balanced with slight {dominant[0]} emphasis"
    elif entropy < 0.4:
        return f"Moderate {dominant[0]} dominance with balanced secondary gunas"
    elif entropy < 0.6:
        return f"{dominant[0]} dominance with reduced {suppressed[0]}"
    elif entropy < 0.8:
        return f"Strong {dominant[0]} dominance with suppressed {suppressed[0]}"
    else:
        return f"Extreme {dominant[0]} dominance with heavily suppressed {suppressed[0]}"


# =============================================================================
# Validation Functions
# =============================================================================

def validate_guna_profile(profile: GunaProfile) -> Optional[str]:
    """
    Validate a guna profile.

    Returns:
        None if valid, error message string if invalid
    """
    for guna in GUNA_NAMES:
        val = getattr(profile, guna)
        if not isinstance(val, (int, float)):
            return f"Guna '{guna}' must be numeric, got {type(val)}"
        if val < 0.0 or val > 1.0:
            return f"Guna '{guna}' must be in [0.0, 1.0], got {val}"

    total = profile.sattva + profile.rajas + profile.tamas
    if total == 0.0:
        return "At least one guna must be non-zero"

    return None
