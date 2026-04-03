"""
Intent Arc Types - Enum-style constants for deterministic arc classification

This module defines the canonical set of intent arc types that can be detected
by the Intent Arc Engine v1.0. All arc types are deterministically classified
based on multi-turn session metrics, memory events, mapper journeys, and
policy signals.

Design Principles:
    - Zero-LLM (purely rule-based)
    - Deterministic (same input → same output)
    - Non-invasive (does not modify pipeline)
    - Additive (optional analytical layer)

Arc Type Definitions:
    - stabilization_arc: Coherence rising, low volatility
    - insight_arc: Breakthrough events + high temporal arc
    - identity_arc: LAM dominance + improving trajectory
    - resolution_arc: Fragmentation → stabilization → breakthrough
    - dissonance_arc: High persona drift + oscillating trajectory
    - avoidance_arc: Flat coherence + low temporal progression
    - expansion_arc: HRM+LAM synergy + strong upward arc
    - chaotic_arc: High mapper volatility + incoherent patterns
"""

from typing import Dict, List

# ============================================================================
# Intent Arc Type Constants
# ============================================================================

INTENT_ARCS = {
    "stabilization_arc": {
        "display_name": "Stabilization Arc",
        "description": "Coherence is steadily rising with low volatility",
        "typical_confidence_range": (0.70, 0.90),
    },
    "insight_arc": {
        "display_name": "Insight Arc",
        "description": "Breakthrough events detected with strong upward temporal arc",
        "typical_confidence_range": (0.75, 0.95),
    },
    "identity_arc": {
        "display_name": "Identity Arc",
        "description": "LAM-driven identity exploration with improving trajectory",
        "typical_confidence_range": (0.60, 0.85),
    },
    "resolution_arc": {
        "display_name": "Resolution Arc",
        "description": "Recovery from fragmentation through stabilization",
        "typical_confidence_range": (0.65, 0.90),
    },
    "dissonance_arc": {
        "display_name": "Dissonance Arc",
        "description": "High persona drift with oscillating or declining trajectory",
        "typical_confidence_range": (0.55, 0.80),
    },
    "avoidance_arc": {
        "display_name": "Avoidance Arc",
        "description": "Flat coherence with minimal temporal progression",
        "typical_confidence_range": (0.50, 0.75),
    },
    "expansion_arc": {
        "display_name": "Expansion Arc",
        "description": "HRM+LAM synergy with expanding context and upward arc",
        "typical_confidence_range": (0.70, 0.95),
    },
    "chaotic_arc": {
        "display_name": "Chaotic Arc",
        "description": "High mapper volatility with unstable coherence patterns",
        "typical_confidence_range": (0.60, 0.85),
    },
}

# Deterministic tiebreak priority (higher index = higher priority)
# Used when multiple arcs have the same confidence score
ARC_PRIORITY = [
    "stabilization_arc",
    "insight_arc",
    "identity_arc",
    "resolution_arc",
    "expansion_arc",
    "avoidance_arc",
    "dissonance_arc",
    "chaotic_arc",
]

# ============================================================================
# Arc Type Validation
# ============================================================================


def is_valid_arc_type(arc_type: str) -> bool:
    """
    Check if the given arc type is valid.

    Args:
        arc_type: Arc type string to validate

    Returns:
        True if arc type is valid, False otherwise
    """
    return arc_type in INTENT_ARCS


def get_arc_display_name(arc_type: str) -> str:
    """
    Get display name for arc type.

    Args:
        arc_type: Arc type string

    Returns:
        Human-readable display name
    """
    if arc_type not in INTENT_ARCS:
        return "Unknown Arc"
    return INTENT_ARCS[arc_type]["display_name"]


def get_arc_description(arc_type: str) -> str:
    """
    Get description for arc type.

    Args:
        arc_type: Arc type string

    Returns:
        Arc type description
    """
    if arc_type not in INTENT_ARCS:
        return "Unknown arc type"
    return INTENT_ARCS[arc_type]["description"]


# ============================================================================
# Public API
# ============================================================================

__all__ = [
    "INTENT_ARCS",
    "ARC_PRIORITY",
    "is_valid_arc_type",
    "get_arc_display_name",
    "get_arc_description",
]
