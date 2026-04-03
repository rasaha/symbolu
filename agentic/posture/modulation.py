"""
Posture Modulation Functions
============================

╔═══════════════════════════════════════════════════════════════════════════════╗
║                    BEHAVIORAL MODULATION LAYER                                 ║
║                                                                                ║
║  Deterministic functions that apply posture to decision points.                ║
║  No randomness. Fully auditable. Never affects truth evaluation.               ║
╚═══════════════════════════════════════════════════════════════════════════════╝

Posture may influence:
    1. Threshold Modulation (escalation, ambiguity tolerance)
    2. Routing Sensitivity (confidence cutoffs, cascade aggressiveness)
    3. Response Shaping (explanation depth, conservatism)
    4. Feedback Gating (learning activation, decay rates)

Posture must NEVER:
    - Override STL truth evaluation
    - Modify ontology or symbolic grounding
    - Perform moral judgments
    - Introduce stochastic behavior

Version: 1.0
Date: 2025-12-22
"""

from typing import Optional, List
from agentic.posture.types import (
    DecisionPostureProfile,
    PostureApplicationResult,
    PostureInfluenceScope,
    PostureTier,
    TIER_ALLOWED_INFLUENCES,
    PostureConfig,
)
from agentic.posture._guna_mapping import _compute_modulation_factor


# =============================================================================
# Utility Functions
# =============================================================================

def clamp(value: float, min_val: float, max_val: float) -> float:
    """Clamp a value to a range."""
    return max(min_val, min(max_val, value))


def is_influence_allowed(tier: PostureTier, scope: PostureInfluenceScope) -> bool:
    """Check if a posture influence is allowed for a tier."""
    allowed = TIER_ALLOWED_INFLUENCES.get(tier, ())
    return scope in allowed


# =============================================================================
# Core Modulation Functions
# =============================================================================

def apply_posture_to_routing(
    base_confidence: float,
    posture: DecisionPostureProfile,
    tier: PostureTier,
    config: Optional[PostureConfig] = None,
) -> PostureApplicationResult:
    """
    Adjust routing sensitivity without changing classification.

    This modulates the confidence threshold for routing decisions,
    NOT the classification itself.

    Args:
        base_confidence: Original confidence score [0.0, 1.0]
        posture: The posture profile to apply
        tier: The tier making this decision
        config: Optional configuration for adjustment limits

    Returns:
        PostureApplicationResult with adjusted value and audit trail

    Determinism:
        Same inputs always produce same outputs. No randomness.
    """
    scope = PostureInfluenceScope.ROUTING_THRESHOLD

    # Check if this tier allows this influence
    if not is_influence_allowed(tier, scope):
        return PostureApplicationResult(
            original_value=base_confidence,
            adjusted_value=base_confidence,
            adjustment_delta=0.0,
            influence_scope=scope,
            tier=tier,
            posture_applied=posture,
            was_influenced=False,
        )

    # Compute adjustment using internal dynamics
    # coherence_bias raises threshold (more careful routing)
    # constraint_bias lowers threshold (more conservative)
    # exploration_bias adds slight sensitivity
    adjustment = (
        posture.coherence_bias * 0.05
        - posture.constraint_bias * 0.05
        + posture.exploration_bias * 0.02
    )

    # Apply config limits if provided
    max_mag = config.max_adjustment_magnitude if config else 0.10
    adjustment = clamp(adjustment, -max_mag, max_mag)

    adjusted = clamp(base_confidence + adjustment, 0.0, 1.0)

    return PostureApplicationResult(
        original_value=base_confidence,
        adjusted_value=adjusted,
        adjustment_delta=adjusted - base_confidence,
        influence_scope=scope,
        tier=tier,
        posture_applied=posture,
        was_influenced=abs(adjustment) > 0.001,
    )


def apply_posture_to_escalation(
    base_threshold: float,
    posture: DecisionPostureProfile,
    tier: PostureTier,
    config: Optional[PostureConfig] = None,
) -> PostureApplicationResult:
    """
    Adjust escalation threshold to higher model tiers.

    This modulates when the system escalates from 7B to 175B models,
    NOT whether it escalates at all.

    Args:
        base_threshold: Original escalation threshold [0.0, 1.0]
        posture: The posture profile to apply
        tier: The tier making this decision
        config: Optional configuration for adjustment limits

    Returns:
        PostureApplicationResult with adjusted threshold
    """
    scope = PostureInfluenceScope.ESCALATION_THRESHOLD

    if not is_influence_allowed(tier, scope):
        return PostureApplicationResult(
            original_value=base_threshold,
            adjusted_value=base_threshold,
            adjustment_delta=0.0,
            influence_scope=scope,
            tier=tier,
            posture_applied=posture,
            was_influenced=False,
        )

    # coherence_bias: lower threshold (escalate more readily for quality)
    # constraint_bias: raise threshold (avoid escalation)
    # exploration_bias: lower threshold slightly (allow variety)
    adjustment = (
        - posture.coherence_bias * 0.06
        + posture.constraint_bias * 0.08
        - posture.exploration_bias * 0.03
    )

    max_mag = config.max_adjustment_magnitude if config else 0.10
    adjustment = clamp(adjustment, -max_mag, max_mag)

    adjusted = clamp(base_threshold + adjustment, 0.0, 1.0)

    return PostureApplicationResult(
        original_value=base_threshold,
        adjusted_value=adjusted,
        adjustment_delta=adjusted - base_threshold,
        influence_scope=scope,
        tier=tier,
        posture_applied=posture,
        was_influenced=abs(adjustment) > 0.001,
    )


def apply_posture_to_response_depth(
    base_depth: float,
    posture: DecisionPostureProfile,
    tier: PostureTier,
    config: Optional[PostureConfig] = None,
) -> PostureApplicationResult:
    """
    Adjust response depth/verbosity.

    This modulates how detailed responses are,
    NOT what information they contain.

    Args:
        base_depth: Original depth level [0.0, 1.0]
        posture: The posture profile to apply
        tier: The tier making this decision
        config: Optional configuration

    Returns:
        PostureApplicationResult with adjusted depth
    """
    scope = PostureInfluenceScope.RESPONSE_DEPTH

    if not is_influence_allowed(tier, scope):
        return PostureApplicationResult(
            original_value=base_depth,
            adjusted_value=base_depth,
            adjustment_delta=0.0,
            influence_scope=scope,
            tier=tier,
            posture_applied=posture,
            was_influenced=False,
        )

    # coherence_bias: increase depth (more thorough explanations)
    # exploration_bias: slight decrease (faster, more concise)
    # constraint_bias: decrease (conservative, less verbose)
    adjustment = (
        posture.coherence_bias * 0.08
        - posture.exploration_bias * 0.03
        - posture.constraint_bias * 0.05
    )

    max_mag = config.max_adjustment_magnitude if config else 0.10
    adjustment = clamp(adjustment, -max_mag, max_mag)

    adjusted = clamp(base_depth + adjustment, 0.0, 1.0)

    return PostureApplicationResult(
        original_value=base_depth,
        adjusted_value=adjusted,
        adjustment_delta=adjusted - base_depth,
        influence_scope=scope,
        tier=tier,
        posture_applied=posture,
        was_influenced=abs(adjustment) > 0.001,
    )


def apply_posture_to_conservatism(
    base_level: float,
    posture: DecisionPostureProfile,
    tier: PostureTier,
    config: Optional[PostureConfig] = None,
) -> PostureApplicationResult:
    """
    Adjust conservatism level for refusal decisions.

    This modulates how strict refusal criteria are,
    NOT what is fundamentally allowed or disallowed.

    Args:
        base_level: Original conservatism level [0.0, 1.0]
        posture: The posture profile to apply
        tier: The tier making this decision
        config: Optional configuration

    Returns:
        PostureApplicationResult with adjusted conservatism
    """
    scope = PostureInfluenceScope.CONSERVATISM_LEVEL

    if not is_influence_allowed(tier, scope):
        return PostureApplicationResult(
            original_value=base_level,
            adjusted_value=base_level,
            adjustment_delta=0.0,
            influence_scope=scope,
            tier=tier,
            posture_applied=posture,
            was_influenced=False,
        )

    # constraint_bias: increase conservatism
    # exploration_bias: decrease conservatism
    # coherence_bias: slight increase (structured approach)
    adjustment = (
        posture.constraint_bias * 0.10
        - posture.exploration_bias * 0.08
        + posture.coherence_bias * 0.02
    )

    max_mag = config.max_adjustment_magnitude if config else 0.10
    adjustment = clamp(adjustment, -max_mag, max_mag)

    adjusted = clamp(base_level + adjustment, 0.0, 1.0)

    return PostureApplicationResult(
        original_value=base_level,
        adjusted_value=adjusted,
        adjustment_delta=adjusted - base_level,
        influence_scope=scope,
        tier=tier,
        posture_applied=posture,
        was_influenced=abs(adjustment) > 0.001,
    )


def apply_posture_to_cascade_aggressiveness(
    base_aggressiveness: float,
    posture: DecisionPostureProfile,
    tier: PostureTier,
    config: Optional[PostureConfig] = None,
) -> PostureApplicationResult:
    """
    Adjust cascade aggressiveness (how quickly to try larger models).

    Only applicable to Consumer tier (Tier 3).

    Args:
        base_aggressiveness: Original aggressiveness [0.0, 1.0]
        posture: The posture profile to apply
        tier: The tier making this decision
        config: Optional configuration

    Returns:
        PostureApplicationResult with adjusted aggressiveness
    """
    scope = PostureInfluenceScope.CASCADE_AGGRESSIVENESS

    if not is_influence_allowed(tier, scope):
        return PostureApplicationResult(
            original_value=base_aggressiveness,
            adjusted_value=base_aggressiveness,
            adjustment_delta=0.0,
            influence_scope=scope,
            tier=tier,
            posture_applied=posture,
            was_influenced=False,
        )

    # exploration_bias: increase aggressiveness (try more)
    # constraint_bias: decrease (stay conservative)
    # coherence_bias: slight decrease (favor first good result)
    adjustment = (
        posture.exploration_bias * 0.08
        - posture.constraint_bias * 0.06
        - posture.coherence_bias * 0.02
    )

    max_mag = config.max_adjustment_magnitude if config else 0.10
    adjustment = clamp(adjustment, -max_mag, max_mag)

    adjusted = clamp(base_aggressiveness + adjustment, 0.0, 1.0)

    return PostureApplicationResult(
        original_value=base_aggressiveness,
        adjusted_value=adjusted,
        adjustment_delta=adjusted - base_aggressiveness,
        influence_scope=scope,
        tier=tier,
        posture_applied=posture,
        was_influenced=abs(adjustment) > 0.001,
    )


def apply_posture_to_feedback_activation(
    base_activation: float,
    posture: DecisionPostureProfile,
    tier: PostureTier,
    config: Optional[PostureConfig] = None,
) -> PostureApplicationResult:
    """
    Adjust whether feedback loops activate.

    Only applicable to Consumer tier (Tier 3).

    Args:
        base_activation: Original activation threshold [0.0, 1.0]
        posture: The posture profile to apply
        tier: The tier making this decision
        config: Optional configuration

    Returns:
        PostureApplicationResult with adjusted activation
    """
    scope = PostureInfluenceScope.FEEDBACK_ACTIVATION

    if not is_influence_allowed(tier, scope):
        return PostureApplicationResult(
            original_value=base_activation,
            adjusted_value=base_activation,
            adjustment_delta=0.0,
            influence_scope=scope,
            tier=tier,
            posture_applied=posture,
            was_influenced=False,
        )

    # exploration_bias: lower threshold (more feedback)
    # constraint_bias: raise threshold (less feedback)
    # coherence_bias: neutral
    adjustment = (
        - posture.exploration_bias * 0.07
        + posture.constraint_bias * 0.07
    )

    max_mag = config.max_adjustment_magnitude if config else 0.10
    adjustment = clamp(adjustment, -max_mag, max_mag)

    adjusted = clamp(base_activation + adjustment, 0.0, 1.0)

    return PostureApplicationResult(
        original_value=base_activation,
        adjusted_value=adjusted,
        adjustment_delta=adjusted - base_activation,
        influence_scope=scope,
        tier=tier,
        posture_applied=posture,
        was_influenced=abs(adjustment) > 0.001,
    )


# =============================================================================
# Batch Application
# =============================================================================

def apply_posture_to_all(
    posture: DecisionPostureProfile,
    tier: PostureTier,
    base_values: dict,
    config: Optional[PostureConfig] = None,
) -> List[PostureApplicationResult]:
    """
    Apply posture to all applicable decision points for a tier.

    Args:
        posture: The posture profile to apply
        tier: The tier context
        base_values: Dict mapping scope names to base values
        config: Optional configuration

    Returns:
        List of PostureApplicationResult for all applications
    """
    results = []
    scope_to_function = {
        PostureInfluenceScope.ROUTING_THRESHOLD: apply_posture_to_routing,
        PostureInfluenceScope.ESCALATION_THRESHOLD: apply_posture_to_escalation,
        PostureInfluenceScope.RESPONSE_DEPTH: apply_posture_to_response_depth,
        PostureInfluenceScope.CONSERVATISM_LEVEL: apply_posture_to_conservatism,
        PostureInfluenceScope.CASCADE_AGGRESSIVENESS: apply_posture_to_cascade_aggressiveness,
        PostureInfluenceScope.FEEDBACK_ACTIVATION: apply_posture_to_feedback_activation,
    }

    for scope, func in scope_to_function.items():
        base_value = base_values.get(scope.value, 0.5)
        result = func(base_value, posture, tier, config)
        results.append(result)

    return results
