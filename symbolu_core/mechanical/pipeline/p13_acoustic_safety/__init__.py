"""
P13 - Acoustic Safety Envelope

P13 defines the ABSOLUTE SAFETY BOUNDS for acoustic expression.
It is the last safety lock before any acoustic realization.

P13's responsibility is to:
- Define hard upper and lower bounds on acoustic expressiveness
- Prevent emotion amplification
- Prevent authority signaling (certainty, dominance, persuasion)
- Prevent prosodic manipulation
- Guarantee downstream renderers cannot exceed intent

P13 does NOT:
- Generate sound
- Modify P10 parameters
- Interpret prosody
- Infer emotion

P13 only CAPS, CONSTRAINS, and VETOES downstream acoustic realization.
P13 is BINDING. Lower phases cannot override it.

CRITICAL ARCHITECTURAL INVARIANT:
    P13 is the last safety lock before sound.
    Phase 1 (acoustic tokenization) must consume P13 verbatim.
    Renderers violating P13 are considered unsafe by design.
"""

# Schema exports
from symbolu_core.mechanical.pipeline.p13_acoustic_safety.p13_acoustic_safety_schema import (
    # Enums
    AcousticRiskLevel,
    SafetyViolation,
    # Dataclasses
    AcousticSafetyEnvelope,
    # Constants - absolute bounds
    ABSOLUTE_PITCH_MIN,
    ABSOLUTE_PITCH_MAX,
    ABSOLUTE_ENERGY_MIN,
    ABSOLUTE_ENERGY_MAX,
    ABSOLUTE_VARIANCE_MIN,
    ABSOLUTE_VARIANCE_MAX,
    # Constants - regime-specific bounds
    HOLD_PITCH_MIN,
    HOLD_PITCH_MAX,
    HOLD_ENERGY_MIN,
    HOLD_ENERGY_MAX,
    HOLD_VARIANCE_MAX,
    DE_ESCALATE_PITCH_MIN,
    DE_ESCALATE_PITCH_MAX,
    DE_ESCALATE_ENERGY_MIN,
    DE_ESCALATE_ENERGY_MAX,
    DE_ESCALATE_VARIANCE_MAX,
    REFLEXIVE_ENERGY_MAX,
    REFLEXIVE_VARIANCE_MAX,
    # Constants - version
    P13_VERSION,
    # Helper functions
    clamp_pitch_to_absolute,
    clamp_energy_to_absolute,
    clamp_variance_to_absolute,
    get_blocked_envelope,
)

# Resolver exports
from symbolu_core.mechanical.pipeline.p13_acoustic_safety.p13_acoustic_safety_resolver import (
    # Constants
    BLOCKED_REGIMES,
    RESTRICTIVE_REGIMES,
    EMOTIONAL_DISCOURSE_ACTS,
    MINIMAL_MOTION_DISCOURSE_ACTS,
    AUTHORITY_RESTRICTED_GROUNDING_MODES,
    MANIPULATION_ENERGY_THRESHOLD,
    MANIPULATION_VARIANCE_THRESHOLD,
    # Safety check functions
    detect_emotion_amplification,
    detect_certainty_escalation,
    detect_authority_signaling,
    detect_excessive_variance,
    detect_prosodic_manipulation,
    # Bounds computation functions
    compute_pitch_bounds,
    compute_energy_bounds,
    compute_variance_bounds,
    compute_expression_flags,
    # Resolver class
    P13AcousticSafetyResolver,
)

# Integration exports
from symbolu_core.mechanical.pipeline.p13_acoustic_safety.p13_integration import (
    # Core functions
    get_p13_resolver,
    maybe_run_p13,
    run_p13_directly,
    get_p13_safety_envelope,
    # Risk level accessors
    get_risk_level,
    is_safe,
    is_caution,
    is_blocked,
    # Violation accessors
    has_violations,
    get_violations,
    has_violation,
    # Expression flag accessors
    allows_emphasis,
    allows_pitch_contours,
    allows_rhythm_variation,
    allows_intonation_shift,
    is_fully_restricted,
    # Bounds accessors
    get_allowed_pitch_range,
    get_allowed_energy_range,
    get_max_energy,
    get_pitch_variance_limit,
    get_allowed_variance_range,
)


__all__ = [
    # Enums
    "AcousticRiskLevel",
    "SafetyViolation",
    # Dataclasses
    "AcousticSafetyEnvelope",
    # Constants - absolute bounds
    "ABSOLUTE_PITCH_MIN",
    "ABSOLUTE_PITCH_MAX",
    "ABSOLUTE_ENERGY_MIN",
    "ABSOLUTE_ENERGY_MAX",
    "ABSOLUTE_VARIANCE_MIN",
    "ABSOLUTE_VARIANCE_MAX",
    # Constants - regime-specific bounds
    "HOLD_PITCH_MIN",
    "HOLD_PITCH_MAX",
    "HOLD_ENERGY_MIN",
    "HOLD_ENERGY_MAX",
    "HOLD_VARIANCE_MAX",
    "DE_ESCALATE_PITCH_MIN",
    "DE_ESCALATE_PITCH_MAX",
    "DE_ESCALATE_ENERGY_MIN",
    "DE_ESCALATE_ENERGY_MAX",
    "DE_ESCALATE_VARIANCE_MAX",
    "REFLEXIVE_ENERGY_MAX",
    "REFLEXIVE_VARIANCE_MAX",
    # Constants - version
    "P13_VERSION",
    # Helper functions
    "clamp_pitch_to_absolute",
    "clamp_energy_to_absolute",
    "clamp_variance_to_absolute",
    "get_blocked_envelope",
    # Constants - resolver
    "BLOCKED_REGIMES",
    "RESTRICTIVE_REGIMES",
    "EMOTIONAL_DISCOURSE_ACTS",
    "MINIMAL_MOTION_DISCOURSE_ACTS",
    "AUTHORITY_RESTRICTED_GROUNDING_MODES",
    "MANIPULATION_ENERGY_THRESHOLD",
    "MANIPULATION_VARIANCE_THRESHOLD",
    # Safety check functions
    "detect_emotion_amplification",
    "detect_certainty_escalation",
    "detect_authority_signaling",
    "detect_excessive_variance",
    "detect_prosodic_manipulation",
    # Bounds computation functions
    "compute_pitch_bounds",
    "compute_energy_bounds",
    "compute_variance_bounds",
    "compute_expression_flags",
    # Resolver class
    "P13AcousticSafetyResolver",
    # Core integration functions
    "get_p13_resolver",
    "maybe_run_p13",
    "run_p13_directly",
    "get_p13_safety_envelope",
    # Risk level accessors
    "get_risk_level",
    "is_safe",
    "is_caution",
    "is_blocked",
    # Violation accessors
    "has_violations",
    "get_violations",
    "has_violation",
    # Expression flag accessors
    "allows_emphasis",
    "allows_pitch_contours",
    "allows_rhythm_variation",
    "allows_intonation_shift",
    "is_fully_restricted",
    # Bounds accessors
    "get_allowed_pitch_range",
    "get_allowed_energy_range",
    "get_max_energy",
    "get_pitch_variance_limit",
    "get_allowed_variance_range",
]
