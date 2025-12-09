"""
Symbol-U Policy Engine - Domain Coherence Policy Flags v1.0

Computes deterministic policy flags based on unified output and domain profiles.
Provides behavioral guidance for UI/LLM renderers without modifying pipeline behavior.

Core Function:
    compute_policy_flags(unified: Dict[str, Any], domain: str) -> Dict[str, Any]

Policy Flags:
- needs_grounding: User needs stabilization/grounding
- allow_deep_reflection: Safe for reflective/arc-based reasoning
- prefer_concrete: Favor concrete/practical responses
- prefer_arc_mode: Favor longitudinal/temporal arc reasoning
- coherence_warning: Severe coherence degradation detected
- stability_status: Overall stability assessment
- recommended_style: Suggested response style
- recommended_mapper: Suggested mapper for next turn

Design Principles:
- Zero-LLM: Pure deterministic rule-based logic
- Non-invasive: Does not modify pipeline or routing
- Additive: Provides advisory flags only
- Deterministic: Same input always produces same output
- CI-tested: Comprehensive test coverage

Usage:
    from symbolu.policy import compute_policy_flags

    # After pipeline execution with unified output:
    flags = compute_policy_flags(unified_output, domain="trading")

    if flags["needs_grounding"]:
        # UI can choose to show grounding exercises
        pass

    if flags["coherence_warning"]:
        # UI can alert user or suggest session pause
        pass
"""

from typing import Dict, Any, Literal
from .domain_profiles import get_domain_profile


# Type aliases for clarity
StabilityStatus = Literal["stable", "recovering", "fragmented"]
RecommendedStyle = Literal["precise", "reflective", "exploratory", "neutral"]
RecommendedMapper = Literal["LCM", "HRM", "LAM"]


def compute_policy_flags(unified: Dict[str, Any], domain: str) -> Dict[str, Any]:
    """
    Compute policy flags from unified output and domain profile.

    This is the main policy engine function. It analyzes coherence metrics
    from the unified output and applies domain-specific thresholds to
    generate behavioral policy flags.

    Args:
        unified: Unified output dictionary from USU-API v1.0
        domain: Domain identifier (e.g., "trading", "therapy", "identity")

    Returns:
        Dictionary with policy flags:
        {
            "needs_grounding": bool,
            "allow_deep_reflection": bool,
            "prefer_concrete": bool,
            "prefer_arc_mode": bool,
            "coherence_warning": bool,
            "stability_status": "stable" | "recovering" | "fragmented",
            "recommended_style": str,
            "recommended_mapper": "LCM" | "HRM" | "LAM"
        }

    Raises:
        ValueError: If unified output is missing required coherence data

    Examples:
        >>> unified = {
        ...     "coherence": {
        ...         "coherence_score": 0.45,
        ...         "persona_drift_score": 0.50,
        ...         "mapper_volatility_score": 0.30,
        ...         "temporal_arc_score": 0.70,
        ...     },
        ...     "entropy": {"normalized_entropy": 0.40}
        ... }
        >>> flags = compute_policy_flags(unified, "trading")
        >>> flags["needs_grounding"]
        True
    """
    # Validate input
    if unified is None or not isinstance(unified, dict):
        raise ValueError("unified output must be a non-empty dictionary")

    # Get domain profile
    profile = get_domain_profile(domain)

    # Extract coherence metrics with safe defaults
    coherence = unified.get("coherence", {})
    entropy = unified.get("entropy", {})

    coherence_score = coherence.get("coherence_score", 1.0)
    persona_drift_score = coherence.get("persona_drift_score", 0.0)
    mapper_volatility_score = coherence.get("mapper_volatility_score", 0.0)
    temporal_arc_score = coherence.get("temporal_arc_score", 1.0)
    normalized_entropy = entropy.get("normalized_entropy", 0.0)

    # ========================================================================
    # RULE 1: needs_grounding
    # True if coherence is below minimum OR drift/volatility exceeds maximum
    # ========================================================================
    needs_grounding = (
        coherence_score < profile["min_coherence"]
        or persona_drift_score > profile["max_persona_drift"]
        or mapper_volatility_score > profile["max_mapper_volatility"]
    )

    # ========================================================================
    # RULE 2: allow_deep_reflection
    # True if LAM is allowed AND coherence is adequate AND drift is acceptable
    # ========================================================================
    allow_deep_reflection = (
        profile["allow_lam"] is True
        and coherence_score >= profile["min_coherence"]
        and persona_drift_score <= 0.65
    )

    # ========================================================================
    # RULE 3: prefer_concrete
    # True if LCM is preferred AND coherence is moderate AND entropy is low
    # ========================================================================
    prefer_concrete = (
        "LCM" in profile["prefer_mappers"]
        and coherence_score < 0.65
        and normalized_entropy < 0.60
    )

    # ========================================================================
    # RULE 4: prefer_arc_mode
    # True if LAM is preferred AND coherence is adequate AND drift is low
    # ========================================================================
    prefer_arc_mode = (
        "LAM" in profile["prefer_mappers"]
        and coherence_score >= profile["min_coherence"]
        and persona_drift_score < 0.55
    )

    # ========================================================================
    # RULE 5: coherence_warning
    # True if coherence is significantly below minimum threshold
    # ========================================================================
    coherence_warning = coherence_score < (profile["min_coherence"] - 0.1)

    # ========================================================================
    # RULE 6: stability_status
    # Classify overall system stability
    # ========================================================================
    stability_status = _compute_stability_status(
        coherence_score=coherence_score,
        persona_drift_score=persona_drift_score,
        temporal_arc_score=temporal_arc_score,
    )

    # ========================================================================
    # RULE 7: recommended_style
    # Use profile's style preference
    # ========================================================================
    recommended_style = profile["style"]

    # ========================================================================
    # RULE 8: recommended_mapper
    # Select mapper based on policy flags and profile preferences
    # ========================================================================
    recommended_mapper = _compute_recommended_mapper(
        profile=profile,
        needs_grounding=needs_grounding,
        prefer_arc_mode=prefer_arc_mode,
    )

    # Build policy flags dictionary
    return {
        "needs_grounding": needs_grounding,
        "allow_deep_reflection": allow_deep_reflection,
        "prefer_concrete": prefer_concrete,
        "prefer_arc_mode": prefer_arc_mode,
        "coherence_warning": coherence_warning,
        "stability_status": stability_status,
        "recommended_style": recommended_style,
        "recommended_mapper": recommended_mapper,
    }


def _compute_stability_status(
    coherence_score: float,
    persona_drift_score: float,
    temporal_arc_score: float,
) -> StabilityStatus:
    """
    Compute stability status from coherence metrics.

    Classification rules:
    - stable: High coherence + low drift
    - recovering: Good temporal arc + moderate drift
    - fragmented: All other cases

    Args:
        coherence_score: Current coherence score (0-1)
        persona_drift_score: Current persona drift (0-1)
        temporal_arc_score: Temporal arc coherence (0-1)

    Returns:
        Stability status: "stable", "recovering", or "fragmented"
    """
    # Stable: High coherence + low drift
    if coherence_score >= 0.65 and persona_drift_score <= 0.40:
        return "stable"

    # Recovering: Good temporal arc + moderate drift
    if temporal_arc_score >= 0.60 and persona_drift_score <= 0.55:
        return "recovering"

    # Fragmented: Everything else
    return "fragmented"


def _compute_recommended_mapper(
    profile: Dict[str, Any],
    needs_grounding: bool,
    prefer_arc_mode: bool,
) -> RecommendedMapper:
    """
    Compute recommended mapper based on policy flags and profile.

    Priority order:
    1. If needs_grounding=True → LCM (grounding/concrete)
    2. If prefer_arc_mode=True → LAM (temporal/arc reasoning)
    3. Otherwise → First preferred mapper from profile
    4. Fallback → HRM (balanced default)

    Args:
        profile: Domain profile dictionary
        needs_grounding: Whether grounding is needed
        prefer_arc_mode: Whether arc mode is preferred

    Returns:
        Recommended mapper: "LCM", "HRM", or "LAM"
    """
    # Override: grounding needed → use LCM
    if needs_grounding:
        return "LCM"

    # Override: arc mode preferred → use LAM
    if prefer_arc_mode:
        return "LAM"

    # Use first preferred mapper from profile
    prefer_mappers = profile.get("prefer_mappers", [])
    if prefer_mappers and len(prefer_mappers) > 0:
        first_preferred = prefer_mappers[0]
        # Validate it's a known mapper
        if first_preferred in ["LCM", "HRM", "LAM"]:
            return first_preferred

    # Fallback to HRM (balanced default)
    return "HRM"


def explain_policy_flags(flags: Dict[str, Any]) -> str:
    """
    Generate human-readable explanation of policy flags.

    This is a convenience function for debugging and logging.

    Args:
        flags: Policy flags dictionary from compute_policy_flags()

    Returns:
        Multi-line string explaining the policy decisions

    Examples:
        >>> flags = {"needs_grounding": True, "stability_status": "fragmented"}
        >>> explanation = explain_policy_flags(flags)
        >>> "GROUNDING NEEDED" in explanation
        True
    """
    lines = ["Policy Flags Summary:", "=" * 50]

    # Stability status
    status = flags.get("stability_status", "unknown")
    lines.append(f"Stability: {status.upper()}")

    # Critical flags
    if flags.get("coherence_warning"):
        lines.append("⚠️  COHERENCE WARNING - Severe degradation detected")

    if flags.get("needs_grounding"):
        lines.append("🔧 GROUNDING NEEDED - User should be stabilized")

    # Behavioral recommendations
    if flags.get("allow_deep_reflection"):
        lines.append("✓ Deep reflection allowed (LAM safe)")

    if flags.get("prefer_concrete"):
        lines.append("→ Prefer concrete responses (LCM)")

    if flags.get("prefer_arc_mode"):
        lines.append("→ Prefer arc mode (LAM)")

    # Recommendations
    lines.append(f"\nRecommended Style: {flags.get('recommended_style', 'neutral')}")
    lines.append(f"Recommended Mapper: {flags.get('recommended_mapper', 'HRM')}")

    return "\n".join(lines)


# Public API
__all__ = [
    'compute_policy_flags',
    'explain_policy_flags',
]
