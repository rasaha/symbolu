"""
P12 - Acoustic-Prosodic Consistency Validator

P12 is an AUDIT-ONLY phase that validates consistency between:
- Governance layers (PO1-P7)
- Acoustic intent (P10)
- Prosodic evidence (P11)

P12's responsibility is to:
- Validate that acoustic parameters do not contradict regime constraints
- Validate that prosodic evidence does not contradict discourse act constraints
- Ensure uncertainty preservation rules are respected
- Detect safety invariant violations (no escalation, no certainty inflation)
- Produce a read-only P12ConsistencyReport

P12 does NOT:
- Modify or correct any data
- Override, mutate, or reinterpret upstream decisions
- Generate speech or acoustic output
- Execute actions
- Call LLMs
- Introduce probabilistic behavior

CRITICAL ARCHITECTURAL INVARIANT:
    P12 is not an intelligence layer.
    It is a truth-preserving audit layer that ensures Symbol-U
    never sounds more certain, forceful, or authoritative
    than it is allowed to be.

Usage:
    from symbolu_core.mechanical.pipeline.p12_consistency import (
        maybe_run_p12,
        P12ConsistencyReport,
        ViolationSeverity,
        ViolationType,
    )

    # In pipeline orchestrator, after P11
    maybe_run_p12(ctx)

    # Check consistency
    if ctx.p12_consistency and ctx.p12_consistency.has_critical_violations():
        # Handle critical violations
        pass
"""

# Schema exports
from symbolu_core.mechanical.pipeline.p12_consistency.p12_consistency_schema import (
    # Enums
    ViolationSeverity,
    ViolationType,
    # Dataclasses
    P12Violation,
    P12Warning,
    P12ConsistencyReport,
    # Constants
    P12_VERSION,
    # Helper functions
    create_violation,
    create_warning,
)

# Validator exports
from symbolu_core.mechanical.pipeline.p12_consistency.p12_consistency_validator import (
    # Constants
    FLAT_REQUIRED_REGIMES,
    SOFT_OR_FLAT_REQUIRED_REGIMES,
    NEUTRAL_ALLOWED_REGIMES,
    FULL_SUPPRESSION_REQUIRED_REGIMES,
    FLAT_PITCH_DISCOURSE_ACTS,
    NO_EMPHASIS_DISCOURSE_ACTS,
    AUTHORITY_RESTRICTED_GROUNDING_MODES,
    # Invariant check functions
    check_regime_acoustic_flat,
    check_regime_acoustic_soft_or_flat,
    check_hold_no_pitch_rise,
    check_hold_no_intensity_increase,
    check_hold_no_expressive_modulation,
    check_de_escalate_no_sharp_pitch,
    check_de_escalate_no_rapid_tempo,
    check_de_escalate_no_emphasis_amplification,
    check_reflection_no_interrogative_prosody,
    check_deferral_minimal_prosodic_motion,
    check_question_rising_pitch_only_if_clarify,
    check_explanation_respects_regime,
    check_uncertainty_preservation,
    check_lexical_prosodic_compatibility,
    check_no_authority_escalation_reflexive,
    check_no_authority_escalation_relational,
    check_suppression_consistency,
    # Validator class
    P12ConsistencyValidator,
)

# Integration exports
from symbolu_core.mechanical.pipeline.p12_consistency.p12_integration import (
    # Core functions
    get_p12_validator,
    maybe_run_p12,
    run_p12_directly,
    get_p12_consistency_report,
    # Consistency accessors
    is_consistent,
    has_violations,
    has_critical_violations,
    has_major_violations,
    has_warnings,
    # Violation accessors
    get_violations,
    get_critical_violations,
    get_major_violations,
    get_warnings,
    get_violations_by_type,
    get_violations_by_severity,
    # Metadata accessors
    get_checked_invariants,
    get_audit_notes,
    # Count accessors
    violation_count,
    warning_count,
)


__all__ = [
    # === Schema ===
    # Enums
    "ViolationSeverity",
    "ViolationType",
    # Dataclasses
    "P12Violation",
    "P12Warning",
    "P12ConsistencyReport",
    # Constants
    "P12_VERSION",
    # Helper functions
    "create_violation",
    "create_warning",
    # === Validator ===
    # Constants
    "FLAT_REQUIRED_REGIMES",
    "SOFT_OR_FLAT_REQUIRED_REGIMES",
    "NEUTRAL_ALLOWED_REGIMES",
    "FULL_SUPPRESSION_REQUIRED_REGIMES",
    "FLAT_PITCH_DISCOURSE_ACTS",
    "NO_EMPHASIS_DISCOURSE_ACTS",
    "AUTHORITY_RESTRICTED_GROUNDING_MODES",
    # Invariant check functions
    "check_regime_acoustic_flat",
    "check_regime_acoustic_soft_or_flat",
    "check_hold_no_pitch_rise",
    "check_hold_no_intensity_increase",
    "check_hold_no_expressive_modulation",
    "check_de_escalate_no_sharp_pitch",
    "check_de_escalate_no_rapid_tempo",
    "check_de_escalate_no_emphasis_amplification",
    "check_reflection_no_interrogative_prosody",
    "check_deferral_minimal_prosodic_motion",
    "check_question_rising_pitch_only_if_clarify",
    "check_explanation_respects_regime",
    "check_uncertainty_preservation",
    "check_lexical_prosodic_compatibility",
    "check_no_authority_escalation_reflexive",
    "check_no_authority_escalation_relational",
    "check_suppression_consistency",
    # Validator class
    "P12ConsistencyValidator",
    # === Integration ===
    # Core functions
    "get_p12_validator",
    "maybe_run_p12",
    "run_p12_directly",
    "get_p12_consistency_report",
    # Consistency accessors
    "is_consistent",
    "has_violations",
    "has_critical_violations",
    "has_major_violations",
    "has_warnings",
    # Violation accessors
    "get_violations",
    "get_critical_violations",
    "get_major_violations",
    "get_warnings",
    "get_violations_by_type",
    "get_violations_by_severity",
    # Metadata accessors
    "get_checked_invariants",
    "get_audit_notes",
    # Count accessors
    "violation_count",
    "warning_count",
]
