"""
Mapper Profile Builder - TTOR to Renderer/DHA Integration
==========================================================

Builds MapperProfile from TTOR RoutingPlan deterministically.
Converts mapper activation signals into modulation parameters
for Fusion Renderer, DHA Engine, and LLM Enhancement Renderer.

Key Principle: Modulate EXPRESSION, not semantic truth.

Version: v1.0
Status: Production
"""

from typing import Optional
from symbolu.mechanical.pipeline.models import MapperProfile
from symbolu.mechanical.pipeline.ttor.models import RoutingPlan


def compute_mapper_profile(routing_plan: RoutingPlan) -> MapperProfile:
    """
    Compute mapper profile from TTOR routing plan.

    Applies deterministic rules to convert mapper activation flags
    and routing signals into modulation parameters.

    Rules:
    ------
    HRM Effects:
        - resolution_level = "high"
        - detail_bias ↑ (increases by +0.3)
        - reflective_bias ↑ (increases by +0.2)

    LCM Effects:
        - resolution_level = "low"
        - practical_bias ↑ (increases by +0.4)
        - detail_bias ↓ (decreases by -0.3)
        - reflective_bias ↓ (decreases by -0.2)

    LAM Effects:
        - arc_mode = "temporal" (if long_arc_tension > 0.6)
        - arc_mode = "identity" (if domain contains "identity" or "therapy")
        - arc_mode = "deep_context" (if normalized_entropy > 0.70)
        - reflective_bias ↑↑ (increases by +0.3)

    Args:
        routing_plan: TTOR routing plan with mapper activation flags

    Returns:
        MapperProfile with computed biases and modes
    """
    # Start with neutral defaults
    resolution_level = "medium"
    arc_mode = "none"
    detail_bias = 0.5
    practical_bias = 0.5
    reflective_bias = 0.5

    # Apply HRM effects
    if routing_plan.use_hrm:
        resolution_level = "high"
        detail_bias = min(1.0, detail_bias + 0.3)
        reflective_bias = min(1.0, reflective_bias + 0.2)

    # Apply LCM effects
    if routing_plan.use_lcm:
        resolution_level = "low"
        practical_bias = min(1.0, practical_bias + 0.4)
        detail_bias = max(0.0, detail_bias - 0.3)
        reflective_bias = max(0.0, reflective_bias - 0.2)

    # LCM overrides HRM for resolution level (LCM is more concrete)
    if routing_plan.use_lcm and routing_plan.use_hrm:
        resolution_level = "medium"  # Compromise when both active

    # Apply LAM effects
    if routing_plan.use_lam:
        reflective_bias = min(1.0, reflective_bias + 0.3)

        # Determine arc_mode based on routing signals
        if routing_plan.long_arc_tension > 0.6:
            arc_mode = "temporal"
        elif _is_identity_domain(routing_plan.domain):
            arc_mode = "identity"
        elif routing_plan.normalized_entropy > 0.70:
            arc_mode = "deep_context"
        else:
            # Default LAM arc mode when activated
            arc_mode = "temporal"

    return MapperProfile(
        resolution_level=resolution_level,
        arc_mode=arc_mode,
        detail_bias=detail_bias,
        practical_bias=practical_bias,
        reflective_bias=reflective_bias,
    )


def _is_identity_domain(domain: str) -> bool:
    """Check if domain is identity-related."""
    identity_keywords = ["identity", "therapy", "self", "personal", "relationships"]
    domain_lower = domain.lower()
    return any(keyword in domain_lower for keyword in identity_keywords)


# Public exports
__all__ = ["compute_mapper_profile"]
