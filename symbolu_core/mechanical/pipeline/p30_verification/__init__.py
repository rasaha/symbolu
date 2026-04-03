"""
P30 Output Verification Phase
================================

Output quality and constraint verification before delivery.
Integrates existing modules:

- RendererComplianceChecker: P13 safety envelope validation
- P12ConsistencyValidator: Acoustic-prosodic consistency
- CoherenceEngine: Multi-turn coherence verification

Phase Authority: MEDIUM (HIGH when violations block output)
Band Position: P30 (Fourth in Delivery Adaptation Band)

Purpose:
    - P13 safety envelope compliance checking
    - P12 acoustic-prosodic consistency validation
    - Multi-turn coherence verification
    - Phase authority chain validation

Usage:
    from symbolu_core.mechanical.pipeline.p30_verification import (
        maybe_run_p30,
        get_p30_output,
        get_p30_verified_text,
        is_p30_passed,
    )

    # In orchestrator (after P29)
    p30_result = maybe_run_p30(ctx)
    if p30_result:
        ctx.p30_verification = p30_result
"""

from .p30_verification_schema import (
    VERSION,
    P30Authority,
    VerificationStatus,
    ViolationSeverity,
    P30Violation,
    P30ComplianceResult,
    P30CoherenceResult,
    P30Output,
)

from .p30_integration import (
    get_compliance_checker,
    get_p12_validator,
    get_coherence_engine,
    run_compliance_check,
    run_coherence_check,
    run_p30_verification,
    maybe_run_p30,
    get_p30_output,
    get_p30_verified_text,
    is_p30_passed,
    HAS_COMPLIANCE_CHECKER,
    HAS_P12_VALIDATOR,
    HAS_COHERENCE_ENGINE,
)

# New modules (Phase 1 & 2 implementation)
from .semantic_drift_monitor import (
    DriftAnalysis,
    SemanticDriftMonitor,
    get_semantic_drift_monitor,
    analyze_drift,
)

from .persona_consistency_checker import (
    PersonaConsistencyResult,
    PersonaConsistencyChecker,
    get_persona_consistency_checker,
    check_persona_consistency,
)

from .authority_cascade_validator import (
    AuthorityLevel,
    ViolationType,
    PhaseAuthority,
    PHASE_AUTHORITIES,
    AuthorityViolation,
    CascadeValidation,
    AuthorityCascadeValidator,
    get_authority_cascade_validator,
    validate_authority_cascade,
)

PHASE_STATUS = "implemented"

__version__ = VERSION
__all__ = [
    # Schema
    "VERSION",
    "P30Authority",
    "VerificationStatus",
    "ViolationSeverity",
    "P30Violation",
    "P30ComplianceResult",
    "P30CoherenceResult",
    "P30Output",
    # Integration
    "get_compliance_checker",
    "get_p12_validator",
    "get_coherence_engine",
    "run_compliance_check",
    "run_coherence_check",
    "run_p30_verification",
    "maybe_run_p30",
    "get_p30_output",
    "get_p30_verified_text",
    "is_p30_passed",
    # Semantic Drift Monitor
    "DriftAnalysis",
    "SemanticDriftMonitor",
    "get_semantic_drift_monitor",
    "analyze_drift",
    # Persona Consistency Checker
    "PersonaConsistencyResult",
    "PersonaConsistencyChecker",
    "get_persona_consistency_checker",
    "check_persona_consistency",
    # Authority Cascade Validator
    "AuthorityLevel",
    "ViolationType",
    "PhaseAuthority",
    "PHASE_AUTHORITIES",
    "AuthorityViolation",
    "CascadeValidation",
    "AuthorityCascadeValidator",
    "get_authority_cascade_validator",
    "validate_authority_cascade",
    # Feature flags
    "HAS_COMPLIANCE_CHECKER",
    "HAS_P12_VALIDATOR",
    "HAS_COHERENCE_ENGINE",
    "PHASE_STATUS",
]
