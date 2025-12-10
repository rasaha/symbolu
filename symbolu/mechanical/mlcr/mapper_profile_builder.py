"""
Mapper Profile Builder - TTOR to Renderer/DHA Integration
==========================================================

Builds MapperProfile from TTOR RoutingPlan deterministically.
Converts mapper activation signals into modulation parameters
for Fusion Renderer, DHA Engine, and LLM Enhancement Renderer.

Key Principle: Modulate EXPRESSION, not semantic truth.

Version: v2.0 (Phase 9: Guna/Kosha resonance modulation)
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


def apply_resonance_biases(
    profile: MapperProfile,
    guna_resonance: Optional[float],
    kosha_resonance: Optional[float],
    kosha_vector: Optional[List[float]]
) -> MapperProfile:
    """
    Apply Phase 9 Guna/Kosha resonance biases to mapper profile.

    Modulates expression biases ONLY. Does NOT affect routing or mappers.
    All changes are deterministic and observation-only.

    Rules (v1.0 canonical):
    -----------------------
    Guna resonance → symbolic/practical balance:
        - If guna_resonance > 0.65: detail_bias += 0.05 (more symbolic)
        - If guna_resonance < 0.35: practical_bias += 0.05 (more practical)
        - Clamp to [0,1]

    Kosha resonance → reflective depth shaping:
        - If kosha_resonance > 0.60: reflective_bias += 0.05
        - If kosha_resonance < 0.40: reflective_bias -= 0.05
        - Clamp to [0,1]

    Kosha vector → expression harmonics:
        - Compute deviation from mean: [round(v - mean(kosha_vector), 4) ...]
        - Store in profile.expression_harmonics
        - Used only by FusionRenderer & DHA for expression nuance

    Args:
        profile: MapperProfile to modulate
        guna_resonance: Guna resonance index from CoherenceState [0.0, 1.0]
        kosha_resonance: Kosha resonance index from CoherenceState [0.0, 1.0]
        kosha_vector: Kosha activation vector from CoherenceState

    Returns:
        Modulated MapperProfile (new instance)
    """
    # If no resonance metrics available, return unchanged
    if guna_resonance is None and kosha_resonance is None and kosha_vector is None:
        return profile

    # Create modulated copy
    detail_bias = profile.detail_bias
    practical_bias = profile.practical_bias
    reflective_bias = profile.reflective_bias
    guna_bias = 0.0
    kosha_bias = 0.0
    harmonics = None

    # Apply Guna resonance modulation
    if guna_resonance is not None:
        if guna_resonance > 0.65:
            # High guna resonance → more symbolic/detailed
            detail_bias = min(1.0, detail_bias + 0.05)
            guna_bias = 0.05
        elif guna_resonance < 0.35:
            # Low guna resonance → more practical
            practical_bias = min(1.0, practical_bias + 0.05)
            guna_bias = -0.05

        # Clamp biases
        detail_bias = max(0.0, min(1.0, detail_bias))
        practical_bias = max(0.0, min(1.0, practical_bias))

    # Apply Kosha resonance modulation
    if kosha_resonance is not None:
        if kosha_resonance > 0.60:
            # High kosha resonance → more reflective
            reflective_bias = min(1.0, reflective_bias + 0.05)
            kosha_bias = 0.05
        elif kosha_resonance < 0.40:
            # Low kosha resonance → less reflective
            reflective_bias = max(0.0, reflective_bias - 0.05)
            kosha_bias = -0.05

        # Clamp reflective bias
        reflective_bias = max(0.0, min(1.0, reflective_bias))

    # Compute expression harmonics from kosha vector
    if kosha_vector is not None and len(kosha_vector) > 0:
        # Compute mean
        mean_value = sum(kosha_vector) / len(kosha_vector)
        # Compute deviations from mean
        harmonics = [round(v - mean_value, 4) for v in kosha_vector]

    # Return new profile with modulated values
    return MapperProfile(
        resolution_level=profile.resolution_level,
        arc_mode=profile.arc_mode,
        detail_bias=detail_bias,
        practical_bias=practical_bias,
        reflective_bias=reflective_bias,
        guna_resonance_bias=guna_bias,
        kosha_resonance_bias=kosha_bias,
        expression_harmonics=harmonics,
    )


def build_mapper_profile_with_resonance(
    routing_plan: "RoutingPlan",
    coherence_state: Optional[Any] = None
) -> MapperProfile:
    """
    Build mapper profile from routing plan with Phase 9 resonance modulation.

    This is the main entry point for Phase 9. It:
    1. Computes base mapper profile from routing plan (v2.0 logic)
    2. Applies Guna/Kosha resonance biases if available

    Args:
        routing_plan: TTOR routing plan with mapper activation flags
        coherence_state: Optional CoherenceState with guna/kosha metrics

    Returns:
        MapperProfile with resonance biases applied
    """
    # Step 1: Compute base profile from routing plan
    profile = compute_mapper_profile(routing_plan)

    # Step 2: Apply resonance biases if coherence state available
    if coherence_state is not None:
        guna_resonance = getattr(coherence_state, "guna_resonance_index", None)
        kosha_resonance = getattr(coherence_state, "kosha_resonance_index", None)
        kosha_vector = getattr(coherence_state, "kosha_activation_vector", None)

        profile = apply_resonance_biases(
            profile,
            guna_resonance,
            kosha_resonance,
            kosha_vector
        )

    return profile


# Public exports
__all__ = [
    "compute_mapper_profile",
    "apply_resonance_biases",
    "build_mapper_profile_with_resonance"
]
