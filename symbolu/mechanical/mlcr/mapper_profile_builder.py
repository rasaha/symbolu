"""
Mapper Profile Builder - TTOR to Renderer/DHA Integration
==========================================================

Builds MapperProfile from TTOR RoutingPlan deterministically.
Converts mapper activation signals into modulation parameters
for Fusion Renderer, DHA Engine, and LLM Enhancement Renderer.

Key Principle: Modulate EXPRESSION, not semantic truth.

Version: v2.1
Status: Production
"""

from typing import Optional, List, Any
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


def apply_symbolic_harmony_bias(
    profile: MapperProfile,
    shi: Optional[float]
) -> MapperProfile:
    """
    Apply Phase 28 Symbolic Harmonization bias to mapper profile.

    Modulates symbolic expression richness ONLY. Does NOT affect routing or mappers.
    All changes are deterministic and observation-only.

    Rules (v1.0 canonical):
    -----------------------
    Symbolic harmony → symbolic richness balance:
        - If SHI >= 0.70: symbolic_harmony_bias = +0.05 (more symbolic richness)
        - If SHI <= 0.35: symbolic_harmony_bias = -0.05 (less symbolic nuance)
        - Otherwise: symbolic_harmony_bias = 0.0 (neutral)

    Symbolic resonance tags:
        - If SHI >= 0.70: ["HIGH_HARMONY"]
        - If 0.35 < SHI < 0.70: ["MEDIUM_HARMONY"]
        - If SHI <= 0.35: ["LOW_HARMONY"]

    Args:
        profile: MapperProfile to modulate
        shi: Symbolic Harmonization Index from CoherenceState [0.0, 1.0]

    Returns:
        Modulated MapperProfile (new instance)
    """
    # If no SHI available, return unchanged
    if shi is None:
        return profile

    # Compute symbolic harmony bias based on SHI
    symbolic_bias = 0.0
    resonance_tags = []

    if shi >= 0.70:
        # High SHI → more symbolic richness
        symbolic_bias = 0.05
        resonance_tags = ["HIGH_HARMONY"]
    elif shi <= 0.35:
        # Low SHI → reduce symbolic nuance
        symbolic_bias = -0.05
        resonance_tags = ["LOW_HARMONY"]
    else:
        # Medium SHI → neutral
        symbolic_bias = 0.0
        resonance_tags = ["MEDIUM_HARMONY"]

    # Clamp bias to [-0.05, +0.05]
    symbolic_bias = max(-0.05, min(0.05, symbolic_bias))

    # Return new profile with symbolic harmony bias applied
    return MapperProfile(
        resolution_level=profile.resolution_level,
        arc_mode=profile.arc_mode,
        detail_bias=profile.detail_bias,
        practical_bias=profile.practical_bias,
        reflective_bias=profile.reflective_bias,
        guna_resonance_bias=profile.guna_resonance_bias,
        kosha_resonance_bias=profile.kosha_resonance_bias,
        expression_harmonics=profile.expression_harmonics,
        symbolic_harmony_bias=symbolic_bias,
        symbolic_resonance_tags=resonance_tags,
    )


# Public exports
__all__ = [
    "compute_mapper_profile",
    "apply_resonance_biases",
    "build_mapper_profile_with_resonance",
    "apply_symbolic_harmony_bias"
]
