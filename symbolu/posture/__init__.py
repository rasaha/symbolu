"""
Configurable Decision Posture
=============================

╔═══════════════════════════════════════════════════════════════════════════════╗
║                    BEHAVIORAL SOVEREIGNTY LAYER                                ║
║                                                                                ║
║  Gives operators control over HOW the system behaves,                          ║
║  while the system itself remains incapable of choosing WHAT is true.           ║
╚═══════════════════════════════════════════════════════════════════════════════╝

This module provides operator-defined behavioral modulation within immutable
truth constraints.

HARD CONSTRAINTS (Non-Negotiable):
    ❌ Must NEVER override STL truth evaluation
    ❌ Must NEVER modify ontology or symbolic grounding
    ❌ Must NEVER perform moral judgments
    ❌ Must NEVER classify users ethically or psychologically
    ❌ Must NEVER introduce stochastic behavior
    ❌ Must NEVER affect Tier-1 invariant outputs

ALLOWED SCOPE:
    ✅ Threshold modulation (escalation, ambiguity tolerance)
    ✅ Routing sensitivity (confidence cutoffs, cascade timing)
    ✅ Response shaping (explanation depth, conservatism)
    ✅ Feedback gating (learning activation, decay rates)

Usage:
    from symbolu.posture import (
        DecisionPostureProfile,
        BALANCED_DEFAULT,
        CONSERVATIVE_ENTERPRISE,
        apply_posture_to_routing,
    )

    # Use a preset profile
    result = apply_posture_to_routing(
        base_confidence=0.75,
        posture=CONSERVATIVE_ENTERPRISE,
        tier=PostureTier.TIER_2,
    )

    # Create a custom profile
    custom = DecisionPostureProfile(
        coherence_bias=0.5,
        exploration_bias=0.3,
        constraint_bias=0.2,
    ).normalize()

Tier Application Rules:
    Tier 1 (STL):     ❌ No posture influence (read-only reference only)
    Tier 2 (STL+7B):  Routing thresholds, explanation depth
    Consumer Tier:     Cascade behavior, feedback loops

Version: 1.0
Date: 2025-12-22
"""

# Types (Public API)
from symbolu.posture.types import (
    # Main Profile
    DecisionPostureProfile,
    # Configuration
    PostureConfig,
    PostureApplicationResult,
    PostureAuditRecord,
    # Enums
    PostureTier,
    PostureInfluenceScope,
    PostureConstraint,
    # Constants
    HARD_CONSTRAINTS,
    TIER_ALLOWED_INFLUENCES,
)

# Preset Profiles
from symbolu.posture.config import (
    BALANCED_DEFAULT,
    CONSERVATIVE_ENTERPRISE,
    EXPLORATORY_RESEARCH,
    HIGH_COHERENCE,
    HIGH_CONSTRAINT,
    get_preset_profile,
    list_presets,
    get_tier_default_config,
    create_custom_profile,
    create_config,
)

# Modulation Functions
from symbolu.posture.modulation import (
    apply_posture_to_routing,
    apply_posture_to_escalation,
    apply_posture_to_response_depth,
    apply_posture_to_conservatism,
    apply_posture_to_cascade_aggressiveness,
    apply_posture_to_feedback_activation,
    apply_posture_to_all,
    is_influence_allowed,
)

# Audit Functions
from symbolu.posture.audit import (
    create_audit_record,
    format_audit_for_api_response,
    format_audit_for_detailed_log,
    format_audit_for_compliance_report,
    validate_audit_record,
    summarize_applications,
)


__all__ = [
    # Types
    "DecisionPostureProfile",
    "PostureConfig",
    "PostureApplicationResult",
    "PostureAuditRecord",
    "PostureTier",
    "PostureInfluenceScope",
    "PostureConstraint",
    "HARD_CONSTRAINTS",
    "TIER_ALLOWED_INFLUENCES",
    # Presets
    "BALANCED_DEFAULT",
    "CONSERVATIVE_ENTERPRISE",
    "EXPLORATORY_RESEARCH",
    "HIGH_COHERENCE",
    "HIGH_CONSTRAINT",
    "get_preset_profile",
    "list_presets",
    "get_tier_default_config",
    "create_custom_profile",
    "create_config",
    # Modulation
    "apply_posture_to_routing",
    "apply_posture_to_escalation",
    "apply_posture_to_response_depth",
    "apply_posture_to_conservatism",
    "apply_posture_to_cascade_aggressiveness",
    "apply_posture_to_feedback_activation",
    "apply_posture_to_all",
    "is_influence_allowed",
    # Audit
    "create_audit_record",
    "format_audit_for_api_response",
    "format_audit_for_detailed_log",
    "format_audit_for_compliance_report",
    "validate_audit_record",
    "summarize_applications",
]
