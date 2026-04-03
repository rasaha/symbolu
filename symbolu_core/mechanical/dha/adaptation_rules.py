"""
Adaptation Rules Module (v3.0)
==============================

Shared helper utilities used by tone_selector and delivery_modulator.

Contains:
    - Threshold constants for readiness/resistance levels
    - Delivery profile definitions
    - Helper functions for mapping scores to categories
    - Text transformation utilities
"""

from typing import Dict, Any, Tuple
from enum import Enum


# ============================================================================
# DELIVERY PROFILE DEFINITIONS
# ============================================================================

class DeliveryProfile(Enum):
    """
    Available delivery profiles for message adaptation.

    SWEET_RESONANCE: Gentle, supportive tone for high-readiness users
    INVERSE_JOLT: Direct, confrontational tone to break resistance patterns
    SYMBOLIC_METAPHOR: Indirect, metaphorical framing for gradual insight
    """
    SWEET_RESONANCE = "SWEET_RESONANCE"
    INVERSE_JOLT = "INVERSE_JOLT"
    SYMBOLIC_METAPHOR = "SYMBOLIC_METAPHOR"


# ============================================================================
# THRESHOLD CONSTANTS
# ============================================================================

# Readiness score thresholds (0-1 scale)
READINESS_HIGH_THRESHOLD = 0.7
READINESS_MEDIUM_THRESHOLD = 0.4
READINESS_LOW_THRESHOLD = 0.0  # Anything below medium is low

# Resistance score thresholds (0-1 scale)
RESISTANCE_HIGH_THRESHOLD = 0.7
RESISTANCE_MEDIUM_THRESHOLD = 0.4
RESISTANCE_LOW_THRESHOLD = 0.0  # Anything below medium is low

# Emotional entropy thresholds
ENTROPY_HIGH_THRESHOLD = 0.7
ENTROPY_MODERATE_THRESHOLD = 0.4


# ============================================================================
# LEVEL CATEGORIES
# ============================================================================

class Level(Enum):
    """Category levels for readiness/resistance scores."""
    HIGH = "HIGH"
    MEDIUM = "MEDIUM"
    LOW = "LOW"


# ============================================================================
# HELPER FUNCTIONS
# ============================================================================

def score_to_level(score: float, high_threshold: float, medium_threshold: float) -> Level:
    """
    Convert a numerical score to a categorical level.

    Args:
        score: Numerical score (0.0 to 1.0)
        high_threshold: Threshold for HIGH level
        medium_threshold: Threshold for MEDIUM level

    Returns:
        Level enum value (HIGH, MEDIUM, or LOW)
    """
    if score >= high_threshold:
        return Level.HIGH
    elif score >= medium_threshold:
        return Level.MEDIUM
    else:
        return Level.LOW


def readiness_score_to_level(readiness_score: float) -> Level:
    """
    Convert readiness score to categorical level.

    Args:
        readiness_score: Value between 0.0 and 1.0

    Returns:
        Level.HIGH, Level.MEDIUM, or Level.LOW
    """
    return score_to_level(
        readiness_score,
        READINESS_HIGH_THRESHOLD,
        READINESS_MEDIUM_THRESHOLD
    )


def resistance_score_to_level(resistance_score: float) -> Level:
    """
    Convert resistance score to categorical level.

    Args:
        resistance_score: Value between 0.0 and 1.0

    Returns:
        Level.HIGH, Level.MEDIUM, or Level.LOW
    """
    return score_to_level(
        resistance_score,
        RESISTANCE_HIGH_THRESHOLD,
        RESISTANCE_MEDIUM_THRESHOLD
    )


def entropy_to_resistance_boost(emotional_entropy: float) -> float:
    """
    Convert emotional entropy to additional resistance factor.

    High emotional entropy suggests chaotic internal state,
    which often correlates with increased resistance.

    Args:
        emotional_entropy: Value between 0.0 and 1.0

    Returns:
        Boost value to add to resistance score (0.0 to 0.3)
    """
    if emotional_entropy >= ENTROPY_HIGH_THRESHOLD:
        return 0.3
    elif emotional_entropy >= ENTROPY_MODERATE_THRESHOLD:
        return 0.15
    else:
        return 0.0


def clamp(value: float, min_val: float = 0.0, max_val: float = 1.0) -> float:
    """
    Clamp a value between min and max bounds.

    Args:
        value: Value to clamp
        min_val: Minimum allowed value
        max_val: Maximum allowed value

    Returns:
        Clamped value
    """
    return max(min_val, min(max_val, value))


def extract_metadata_score(
    metadata: Dict[str, Any],
    key: str,
    default: float = 0.5
) -> float:
    """
    Safely extract a score from metadata dictionary.

    Args:
        metadata: Dictionary containing scores
        key: Key to extract
        default: Default value if key not found

    Returns:
        Extracted score (clamped to 0-1)
    """
    value = metadata.get(key, default)

    if isinstance(value, (int, float)):
        return clamp(float(value))

    return default


def get_delivery_profile_metadata(profile: DeliveryProfile) -> Dict[str, Any]:
    """
    Get metadata describing a delivery profile's characteristics.

    Args:
        profile: The delivery profile

    Returns:
        Dictionary with profile characteristics
    """
    profile_metadata = {
        DeliveryProfile.SWEET_RESONANCE: {
            "tone": "warm",
            "directness": 0.3,
            "metaphor_density": 0.2,
            "emotional_safety": 0.9,
            "description": "Gentle and supportive delivery for receptive users"
        },
        DeliveryProfile.INVERSE_JOLT: {
            "tone": "direct",
            "directness": 0.9,
            "metaphor_density": 0.1,
            "emotional_safety": 0.4,
            "description": "Direct confrontation to break through resistance"
        },
        DeliveryProfile.SYMBOLIC_METAPHOR: {
            "tone": "poetic",
            "directness": 0.4,
            "metaphor_density": 0.8,
            "emotional_safety": 0.7,
            "description": "Indirect metaphorical framing for gradual insight"
        }
    }

    return profile_metadata.get(profile, {})


# ============================================================================
# TEXT TRANSFORMATION UTILITIES
# ============================================================================

# Common softening phrases for SWEET_RESONANCE
SOFTENING_PREFIXES = [
    "Perhaps ",
    "It seems that ",
    "You might find that ",
    "Consider that ",
    "Gently speaking, ",
]

# Direct transition phrases for INVERSE_JOLT
DIRECT_PREFIXES = [
    "Here's the truth: ",
    "Simply put: ",
    "The reality is: ",
    "Directly: ",
    "Let's be clear: ",
]

# Metaphorical framing for SYMBOLIC_METAPHOR
SYMBOLIC_FRAMES = {
    "opening": [
        "Like a river finding its path, ",
        "In the garden of understanding, ",
        "As light reveals shadows, ",
        "Through the lens of time, ",
    ],
    "closing": [
        "...and so the journey continues.",
        "...as all things find their place.",
        "...revealing what was always there.",
        "...the pattern becomes clear.",
    ]
}


def get_profile_transform_hints(profile: DeliveryProfile) -> Dict[str, Any]:
    """
    Get transformation hints for a given delivery profile.

    Args:
        profile: The delivery profile

    Returns:
        Dictionary with transform hints (prefixes, frames, etc.)
    """
    if profile == DeliveryProfile.SWEET_RESONANCE:
        return {
            "prefixes": SOFTENING_PREFIXES,
            "tone_words": ["perhaps", "might", "consider", "gently"],
            "avoid_words": ["must", "always", "never", "wrong"]
        }
    elif profile == DeliveryProfile.INVERSE_JOLT:
        return {
            "prefixes": DIRECT_PREFIXES,
            "tone_words": ["clearly", "directly", "simply", "truth"],
            "compress": True
        }
    elif profile == DeliveryProfile.SYMBOLIC_METAPHOR:
        return {
            "frames": SYMBOLIC_FRAMES,
            "use_metaphor": True,
            "indirect": True
        }

    return {}
