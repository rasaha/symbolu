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
- interaction_mode: Active interaction mode (Phase 15)

Design Principles:
- Zero-LLM: Pure deterministic rule-based logic
- Non-invasive: Does not modify pipeline or routing
- Additive: Provides advisory flags only
- Deterministic: Same input always produces same output
- CI-tested: Comprehensive test coverage

Phase 15 Interaction Modes:
- ANALYTICS_ONLY: Standard Phase 1-12 behavior, no formula influence
- SMART_INSIGHT: Soft UI-layer refinement, v3 scoring if domain allows
- DEEP_ADAPTIVE: Full adaptive mode with VMF/ATH hints

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

    # Phase 15: Check interaction mode
    if flags["interaction_mode"] == "deep_adaptive":
        # Use VMF/ATH-based adaptive hints
        pass
"""

from typing import Dict, Any, Literal, Optional
from .domain_profiles import get_domain_profile
from .interaction_modes import InteractionMode, resolve_interaction_mode


# Type aliases for clarity
StabilityStatus = Literal["stable", "recovering", "fragmented"]
RecommendedStyle = Literal["precise", "reflective", "exploratory", "neutral"]
RecommendedMapper = Literal["LCM", "HRM", "LAM"]


def _get_active_coherence_score(
    unified_output: Dict[str, Any],
    profile: Dict[str, Any],
) -> float:
    """
    Returns the coherence score that should be used for policy rules.

    v1 is always available; v2 and v3 are optional and gated by profile flags.

    Phase 12 Update:
    v3 is now QUALITY-GATED. Even if use_coherence_v3=True, v3 will only be used
    if coherence_v3_quality >= profile.min_v3_quality_for_activation.
    If quality is too low, cascade to v2 (if available), else v1.

    This helper enables Phase 4 coherence v2 and Phase 10 coherence v3 integration
    into policy layer while maintaining complete backward compatibility. By default
    (use_coherence_v2=False, use_coherence_v3=False), this always returns v1 score,
    preserving existing behavior.

    Priority cascade (Phase 12):
        1. v3 (if use_coherence_v3=True AND v3 available AND quality >= threshold)
        2. v2 (if use_coherence_v2=True AND v2 available)
        3. v1 (always fallback)

    Args:
        unified_output: Unified output dictionary from USU-API v1.0
        profile: Domain profile dictionary (from get_domain_profile)

    Returns:
        float: Active coherence score (v3 > v2 > v1 cascade, quality-gated)

    Examples:
        >>> unified = {"coherence": {"coherence_score": 0.6, "coherence_score_v2": 0.75, "coherence_score_v3": 0.82, "coherence_v3_quality": 0.65}}
        >>> profile = {"use_coherence_v3": True, "min_v3_quality_for_activation": 0.40, ...}
        >>> _get_active_coherence_score(unified, profile)
        0.82

        >>> unified_low_quality = {"coherence": {"coherence_score": 0.6, "coherence_score_v2": 0.75, "coherence_score_v3": 0.82, "coherence_v3_quality": 0.20}}
        >>> _get_active_coherence_score(unified_low_quality, profile)
        0.75  # Falls back to v2 due to low quality

        >>> profile_v2 = {"use_coherence_v2": True, "use_coherence_v3": False, ...}
        >>> _get_active_coherence_score(unified, profile_v2)
        0.75

        >>> profile_v1_only = {"use_coherence_v2": False, "use_coherence_v3": False, ...}
        >>> _get_active_coherence_score(unified, profile_v1_only)
        0.6
    """
    coherence = unified_output.get("coherence", {})

    # v1 is always available (default to 1.0 if missing)
    coherence_score_v1 = coherence.get("coherence_score", 1.0)

    # Check if profile enables v3 (Phase 10 experimental megafusion)
    use_v3 = profile.get("use_coherence_v3", False)

    # Phase 12: Quality-gated v3 usage
    if use_v3:
        coherence_score_v3 = coherence.get("coherence_score_v3")
        coherence_v3_quality = coherence.get("coherence_v3_quality")
        min_v3_quality = profile.get("min_v3_quality_for_activation")

        # Only use v3 if:
        # 1. v3 score is available
        # 2. v3 quality is available
        # 3. v3 quality meets or exceeds threshold (if threshold is set)
        if coherence_score_v3 is not None and coherence_v3_quality is not None:
            # If no threshold is set (None), allow v3 unconditionally
            if min_v3_quality is None or coherence_v3_quality >= min_v3_quality:
                return coherence_score_v3
            # If quality is below threshold, fall through to v2/v1

    # Check if profile enables v2 (Phase 4 formula-aware)
    use_v2 = profile.get("use_coherence_v2", False)

    # If v2 is enabled AND v2 score is available, use it (second priority)
    if use_v2:
        coherence_score_v2 = coherence.get("coherence_score_v2")
        if coherence_score_v2 is not None:
            return coherence_score_v2

    # Default: return v1 (backward compatible, always fallback)
    return coherence_score_v1


def _refine_policy_with_formulas(
    flags: Dict[str, Any],
    unified_output: Dict[str, Any],
    profile: Dict[str, Any],
) -> Dict[str, Any]:
    """
    Optionally adjusts UI-focused policy flags based on formula metrics.

    Phase 5: Formula-based UI modulation for therapy/identity domains only.
    This function applies gentle refinement to policy flags using Phase 3/4
    formula signals, ONLY when profile["formula_ui_mode"] == "light".

    Never modifies:
    - needs_grounding (core safety flag)
    - coherence_warning (core safety flag)
    - stability_status (core stability assessment)
    - recommended_mapper (routing decision)

    May refine (UI-layer only):
    - allow_deep_reflection
    - prefer_concrete
    - prefer_arc_mode

    Rules:
    1. Safe deeper reflection gate: Enable if coherence >= 0.50, resonance high, tension low
    2. Arc emphasis: Enable if arc_alignment high AND reflection allowed
    3. Concrete preference: Enable if tension very high (safety override)

    Args:
        flags: Policy flags dictionary from compute_policy_flags()
        unified_output: Unified output dictionary with formula metrics
        profile: Domain profile dictionary with Phase 5 settings

    Returns:
        Refined policy flags dictionary (may be unchanged)

    Examples:
        >>> flags = {"allow_deep_reflection": False, "prefer_arc_mode": False}
        >>> unified = {
        ...     "coherence": {
        ...         "coherence_score_v2": 0.70,
        ...         "resonance_index": 0.75,
        ...         "tension_index": 0.30,
        ...         "arc_alignment_index": 0.65
        ...     }
        ... }
        >>> profile = {
        ...     "formula_ui_mode": "light",
        ...     "min_resonance_for_reflection": 0.50,
        ...     "max_tension_for_reflection": 0.75
        ... }
        >>> refined = _refine_policy_with_formulas(flags, unified, profile)
        >>> refined["allow_deep_reflection"]
        True
        >>> refined["prefer_arc_mode"]
        True
    """
    # Early exit: If formula UI mode is disabled, return flags unchanged
    formula_ui_mode = profile.get("formula_ui_mode", "none")
    if formula_ui_mode == "none":
        return flags

    # Extract coherence metrics
    coherence = unified_output.get("coherence", {})

    # Get active coherence score (v2 if available, else v1)
    coherence_active = _get_active_coherence_score(unified_output, profile)

    # Extract Phase 3/4 formula metrics
    resonance_index = coherence.get("resonance_index")
    tension_index = coherence.get("tension_index")
    arc_alignment_index = coherence.get("arc_alignment_index")

    # If any required metrics are missing, return flags unchanged
    if resonance_index is None or tension_index is None or arc_alignment_index is None:
        return flags

    # Extract profile thresholds
    min_resonance = profile.get("min_resonance_for_reflection", 0.50)
    max_tension = profile.get("max_tension_for_reflection", 0.75)

    # Create a copy of flags to avoid mutating the input
    refined_flags = flags.copy()

    # ========================================================================
    # RULE 1: Safe deeper reflection gate (therapy/identity only)
    # Enable deep reflection if coherence is adequate and formula signals are safe
    # ========================================================================
    if (
        coherence_active >= 0.50
        and resonance_index >= min_resonance
        and tension_index <= max_tension
    ):
        refined_flags["allow_deep_reflection"] = True

    # ========================================================================
    # RULE 2: Arc emphasis when strong arc alignment
    # Enable arc mode if arc alignment is high AND reflection is allowed
    # ========================================================================
    if (
        arc_alignment_index >= 0.60
        and refined_flags.get("allow_deep_reflection", False)
    ):
        refined_flags["prefer_arc_mode"] = True

    # ========================================================================
    # RULE 3: Concrete preference when tension is very high (safety override)
    # Force concrete mode and disable reflection if tension is dangerous
    # ========================================================================
    if tension_index >= 0.75:
        refined_flags["prefer_concrete"] = True
        refined_flags["allow_deep_reflection"] = False
        refined_flags["prefer_arc_mode"] = False

    return refined_flags


def compute_policy_flags(
    unified: Dict[str, Any],
    domain: str,
    user_mode_override: Optional[str] = None,
    admin_mode_override: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Compute policy flags from unified output and domain profile.

    This is the main policy engine function. It analyzes coherence metrics
    from the unified output and applies domain-specific thresholds to
    generate behavioral policy flags.

    Phase 15: Supports interaction mode overrides that control how much
    influence advanced formulas have on the policy output.

    Args:
        unified: Unified output dictionary from USU-API v1.0
        domain: Domain identifier (e.g., "trading", "therapy", "identity")
        user_mode_override: Optional user-specified interaction mode override
        admin_mode_override: Optional admin-specified interaction mode override

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
            "recommended_mapper": "LCM" | "HRM" | "LAM",
            "interaction_mode": str  # Phase 15: Active interaction mode
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
        >>> flags["interaction_mode"]
        'analytics_only'
    """
    # Validate input
    if unified is None or not isinstance(unified, dict):
        raise ValueError("unified output must be a non-empty dictionary")

    # Get domain profile
    profile = get_domain_profile(domain)

    # ========================================================================
    # Phase 15: Resolve interaction mode
    # Priority: admin_override > user_override > domain_default
    # ========================================================================
    active_mode = resolve_interaction_mode(
        domain_profile=profile,
        user_override=user_mode_override,
        admin_override=admin_mode_override,
    )

    # Extract coherence metrics with safe defaults
    coherence = unified.get("coherence", {})
    entropy = unified.get("entropy", {})

    # Phase 4: Use active coherence score (v2 if enabled, else v1)
    coherence_score = _get_active_coherence_score(unified, profile)

    # Other metrics (always from v1 - not affected by v2)
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
    flags = {
        "needs_grounding": needs_grounding,
        "allow_deep_reflection": allow_deep_reflection,
        "prefer_concrete": prefer_concrete,
        "prefer_arc_mode": prefer_arc_mode,
        "coherence_warning": coherence_warning,
        "stability_status": stability_status,
        "recommended_style": recommended_style,
        "recommended_mapper": recommended_mapper,
        # Phase 15: Include active interaction mode
        "interaction_mode": active_mode.value,
    }

    # ========================================================================
    # Phase 15: Apply mode-specific behavior
    # ========================================================================
    # MODE 1: ANALYTICS_ONLY → Use existing Phase 1-12 behavior only
    #         NO formula influence on policy (same as before)
    # MODE 2: SMART_INSIGHT → Enable soft UI-layer refinement from Phase 5
    #         Enable v3 scoring if domain allows (Phase 11)
    #         DO NOT modify routing/mappers
    # MODE 3: DEEP_ADAPTIVE → Enable Phase 5 UI refinement
    #         Enable v3 scoring priority
    #         Leverage VMF/ATH for emotional/arc-based hints
    #         Still no routing or mapper activation changes
    #         Influence ONLY presentation layer (hints/badges), NEVER behavior
    # ========================================================================

    if active_mode == InteractionMode.ANALYTICS_ONLY:
        # ANALYTICS_ONLY: No formula refinement applied
        # Return flags as computed by Phase 1-12 rules only
        pass

    elif active_mode == InteractionMode.SMART_INSIGHT:
        # SMART_INSIGHT: Apply Phase 5 formula-based refinement (UI-layer only)
        flags = _refine_policy_with_formulas(flags, unified, profile)

    elif active_mode == InteractionMode.DEEP_ADAPTIVE:
        # DEEP_ADAPTIVE: Apply Phase 5 refinement PLUS VMF/ATH adaptive hints
        flags = _refine_policy_with_formulas(flags, unified, profile)

        # Apply VMF/ATH-based adaptive hints (presentation layer only)
        flags = _apply_deep_adaptive_hints(flags, unified)

    return flags


def _apply_deep_adaptive_hints(
    flags: Dict[str, Any],
    unified_output: Dict[str, Any],
) -> Dict[str, Any]:
    """
    Apply VMF/ATH-based adaptive hints for DEEP_ADAPTIVE mode.

    Phase 15: This function adds emotional/arc-based hint flags based on
    Vritti Momentum Formula (VMF) and Arc-Tension Harmonizer (ATH) signals.

    IMPORTANT:
    - Influence ONLY presentation layer (hints/badges), NEVER behavior
    - Does NOT modify routing, mappers, DHA, or Fusion
    - Does NOT change existing safety flags (needs_grounding, coherence_warning)
    - Additive only: adds hint flags, does not remove or modify core flags

    Hint Flags Added:
    - vmf_emotional_momentum: "rising" | "falling" | "stable" | None
    - ath_arc_tension_state: "harmonized" | "building" | "releasing" | None

    Args:
        flags: Policy flags dictionary from compute_policy_flags()
        unified_output: Unified output dictionary with formula metrics

    Returns:
        Refined policy flags dictionary with VMF/ATH hints

    Examples:
        >>> flags = {"needs_grounding": False, ...}
        >>> unified = {"formulas": {"vritti_momentum": 0.75, "arc_tension_harmonizer": 0.60}}
        >>> refined = _apply_deep_adaptive_hints(flags, unified)
        >>> refined["vmf_emotional_momentum"]
        'rising'
    """
    # Create a copy to avoid mutating input
    refined_flags = flags.copy()

    # Extract formula metrics from unified output
    formulas = unified_output.get("formulas", {})

    if not formulas:
        # No formula data available, return flags unchanged
        refined_flags["vmf_emotional_momentum"] = None
        refined_flags["ath_arc_tension_state"] = None
        return refined_flags

    # ========================================================================
    # VMF-based emotional momentum hint
    # ========================================================================
    vritti_momentum = formulas.get("vritti_momentum")

    if vritti_momentum is not None:
        if vritti_momentum >= 0.65:
            refined_flags["vmf_emotional_momentum"] = "rising"
        elif vritti_momentum <= 0.35:
            refined_flags["vmf_emotional_momentum"] = "falling"
        else:
            refined_flags["vmf_emotional_momentum"] = "stable"
    else:
        refined_flags["vmf_emotional_momentum"] = None

    # ========================================================================
    # ATH-based arc-tension state hint
    # ========================================================================
    arc_tension_harmonizer = formulas.get("arc_tension_harmonizer")

    if arc_tension_harmonizer is not None:
        if arc_tension_harmonizer >= 0.70:
            refined_flags["ath_arc_tension_state"] = "harmonized"
        elif arc_tension_harmonizer >= 0.40:
            refined_flags["ath_arc_tension_state"] = "building"
        else:
            refined_flags["ath_arc_tension_state"] = "releasing"
    else:
        refined_flags["ath_arc_tension_state"] = None

    return refined_flags


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
