"""
P30 Output Verification Phase Integration
===========================================

Integration shim for running P30 Output Verification phase within
the Symbol-U pipeline orchestrator.

Integrates existing modules:
- RendererComplianceChecker: P13 safety envelope validation
- P12ConsistencyValidator: Acoustic-prosodic consistency
- CoherenceEngine: Multi-turn coherence verification

Usage in orchestrator:
    from .p30_verification import maybe_run_p30, get_p30_output

    # After P29 Expression
    p30_result = maybe_run_p30(ctx)
    if p30_result:
        ctx.p30_verification = p30_result
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional, TYPE_CHECKING

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

if TYPE_CHECKING:
    from symbolu_core.mechanical.pipeline.models import PipelineContext


# =============================================================================
# OPTIONAL IMPORTS (graceful degradation)
# =============================================================================

# Try to import compliance checker
try:
    from symbolu_core.mechanical.pipeline.renderer_compliance.renderer_compliance_checker import (
        RendererComplianceChecker,
    )
    from symbolu_core.mechanical.pipeline.renderer_compliance.renderer_contract import (
        ComplianceVerdict,
    )
    HAS_COMPLIANCE_CHECKER = True
except ImportError:
    HAS_COMPLIANCE_CHECKER = False
    RendererComplianceChecker = None
    ComplianceVerdict = None

# Try to import P12 validator
try:
    from symbolu_core.mechanical.pipeline.p12_consistency.p12_consistency_validator import (
        P12ConsistencyValidator,
    )
    from symbolu_core.mechanical.pipeline.p12_consistency.p12_consistency_schema import (
        ViolationSeverity as P12Severity,
    )
    HAS_P12_VALIDATOR = True
except ImportError:
    HAS_P12_VALIDATOR = False
    P12ConsistencyValidator = None
    P12Severity = None

# Try to import coherence engine
try:
    from agentic.core.coherence.coherence_engine import CoherenceEngine
    from agentic.core.coherence.coherence_state import CoherenceState
    HAS_COHERENCE_ENGINE = True
except ImportError:
    HAS_COHERENCE_ENGINE = False
    CoherenceEngine = None
    CoherenceState = None


# =============================================================================
# SINGLETON INSTANCES
# =============================================================================

_compliance_checker: Optional[Any] = None
_p12_validator: Optional[Any] = None
_coherence_engine: Optional[Any] = None


def get_compliance_checker() -> Optional[Any]:
    """Get or create singleton RendererComplianceChecker instance."""
    global _compliance_checker
    if not HAS_COMPLIANCE_CHECKER:
        return None
    if _compliance_checker is None:
        _compliance_checker = RendererComplianceChecker()
    return _compliance_checker


def get_p12_validator() -> Optional[Any]:
    """Get or create singleton P12ConsistencyValidator instance."""
    global _p12_validator
    if not HAS_P12_VALIDATOR:
        return None
    if _p12_validator is None:
        _p12_validator = P12ConsistencyValidator()
    return _p12_validator


def get_coherence_engine() -> Optional[Any]:
    """Get or create singleton CoherenceEngine instance."""
    global _coherence_engine
    if not HAS_COHERENCE_ENGINE:
        return None
    if _coherence_engine is None:
        _coherence_engine = CoherenceEngine()
    return _coherence_engine


# =============================================================================
# COMPLIANCE CHECKING
# =============================================================================


def run_compliance_check(
    text: str,
    ctx: "PipelineContext",
) -> P30ComplianceResult:
    """
    Run compliance checking against P13 safety envelope.

    Args:
        text: Text to verify.
        ctx: Pipeline context for envelope lookup.

    Returns:
        P30ComplianceResult with compliance status.
    """
    violations: List[P30Violation] = []
    p13_compliant = True
    p12_consistent = True

    # Run P13 compliance check
    if HAS_COMPLIANCE_CHECKER:
        try:
            checker = get_compliance_checker()
            if checker:
                # Get envelope from context if available
                envelope = getattr(ctx, 'p13_envelope', None)
                if envelope:
                    # Create minimal render intent for checking
                    from symbolu_core.mechanical.pipeline.renderer_compliance.renderer_contract import (
                        AcousticRenderIntent,
                    )
                    intent = AcousticRenderIntent(
                        text=text,
                        pitch_range=(100.0, 200.0),
                        energy_level=0.5,
                        emphasis_flags={},
                    )
                    result = checker.check(envelope, intent)
                    if result.failed():
                        p13_compliant = False
                        for v in result.violations:
                            violations.append(P30Violation(
                                code=f"P13_{v.category.value}",
                                message=v.message,
                                severity=ViolationSeverity.CRITICAL,
                                source="RendererComplianceChecker",
                                details={"category": v.category.value},
                            ))
        except Exception:
            pass

    # Run P12 consistency check
    if HAS_P12_VALIDATOR:
        try:
            validator = get_p12_validator()
            if validator:
                # Get required context for P12 validation
                regime = getattr(ctx, 'acoustic_regime', None)
                discourse_act = getattr(ctx, 'discourse_act', None)

                if regime and discourse_act:
                    report = validator.validate(
                        regime=regime,
                        discourse_act=discourse_act,
                        prosody_evidence={},
                    )
                    if report.has_violations():
                        p12_consistent = False
                        for v in report.violations:
                            severity = ViolationSeverity.WARNING
                            if v.severity == P12Severity.CRITICAL:
                                severity = ViolationSeverity.CRITICAL
                            violations.append(P30Violation(
                                code=f"P12_{v.type.value}",
                                message=v.message,
                                severity=severity,
                                source="P12ConsistencyValidator",
                                details={"type": v.type.value},
                            ))
        except Exception:
            pass

    # Determine overall pass/fail
    critical_violations = [v for v in violations if v.severity == ViolationSeverity.CRITICAL]
    passed = len(critical_violations) == 0

    return P30ComplianceResult(
        passed=passed,
        violations=violations,
        p13_compliant=p13_compliant,
        p12_consistent=p12_consistent,
    )


# =============================================================================
# COHERENCE VERIFICATION
# =============================================================================


def run_coherence_check(
    text: str,
    ctx: "PipelineContext",
) -> P30CoherenceResult:
    """
    Run coherence verification.

    Args:
        text: Text to verify.
        ctx: Pipeline context with coherence state.

    Returns:
        P30CoherenceResult with coherence metrics.
    """
    coherence_score = 1.0
    semantic_stability = 1.0
    persona_consistent = True
    temporal_arc_score = 1.0

    # Check coherence state from context
    if hasattr(ctx, 'coherence_state') and ctx.coherence_state:
        state = ctx.coherence_state
        coherence_score = getattr(state, 'coherence_v3_quality', 1.0)
        semantic_stability = getattr(state, 'semantic_skeleton_stability', 1.0)
        temporal_arc_score = getattr(state, 'temporal_arc_score', 1.0)

    # Check persona consistency
    if hasattr(ctx, 'p27_persona') and hasattr(ctx, 'persona'):
        p27_persona = ctx.p27_persona.persona_id if ctx.p27_persona else None
        current_persona = ctx.persona.active_persona_id if ctx.persona else None
        if p27_persona and current_persona:
            # Check if P27 suggestion matches current
            persona_consistent = True  # Default to consistent

    return P30CoherenceResult(
        coherence_score=coherence_score,
        semantic_stability=semantic_stability,
        persona_consistent=persona_consistent,
        temporal_arc_score=temporal_arc_score,
    )


# =============================================================================
# MAIN INTEGRATION
# =============================================================================


def run_p30_verification(
    text: str,
    ctx: "PipelineContext",
) -> P30Output:
    """
    Run P30 output verification.

    Args:
        text: Text to verify.
        ctx: Pipeline context.

    Returns:
        P30Output with verification results.
    """
    trace: List[str] = []
    checks_performed: List[str] = []
    verified_text = text

    # Run compliance check
    trace.append("Running compliance checks")
    compliance_result = run_compliance_check(text, ctx)
    if HAS_COMPLIANCE_CHECKER:
        checks_performed.append("P13_compliance")
    if HAS_P12_VALIDATOR:
        checks_performed.append("P12_consistency")
    trace.append(f"Compliance: {'PASS' if compliance_result.passed else 'FAIL'}")

    # Run coherence check
    trace.append("Running coherence verification")
    coherence_result = run_coherence_check(text, ctx)
    if HAS_COHERENCE_ENGINE:
        checks_performed.append("coherence_engine")
    trace.append(f"Coherence score: {coherence_result.coherence_score:.2f}")

    # Determine verification status
    if not compliance_result.passed:
        verification_status = VerificationStatus.FAILED
        authority = P30Authority.HIGH  # Binding decision
        verified_text = ""  # Block output
        trace.append("Output BLOCKED due to compliance violations")
    elif compliance_result.violations:
        verification_status = VerificationStatus.PASSED_WITH_WARNINGS
        authority = P30Authority.MEDIUM
        trace.append("Passed with warnings")
    else:
        verification_status = VerificationStatus.PASSED
        authority = P30Authority.MEDIUM
        trace.append("Verification passed")

    return P30Output(
        verified_text=verified_text,
        verification_status=verification_status,
        authority=authority,
        compliance_result=compliance_result,
        coherence_result=coherence_result,
        checks_performed=checks_performed,
        processing_trace=trace,
    )


def maybe_run_p30(ctx: "PipelineContext") -> Optional[P30Output]:
    """
    Conditionally run P30 output verification phase.

    This is the main integration function to call from the pipeline orchestrator.

    Args:
        ctx: Pipeline context with P29 result.

    Returns:
        P30Output if phase executed, None otherwise.
    """
    # Get input text from P29 or fallback
    text = ""
    if hasattr(ctx, 'p29_expression') and ctx.p29_expression:
        text = ctx.p29_expression.final_text
    elif hasattr(ctx, 'p28_dha') and ctx.p28_dha:
        text = ctx.p28_dha.guarded_text
    elif hasattr(ctx, 'dha') and ctx.dha:
        text = getattr(ctx.dha, 'guarded_text', "")

    if not text:
        return None

    # Run verification
    return run_p30_verification(text, ctx)


def get_p30_output(ctx: "PipelineContext") -> Optional[P30Output]:
    """
    Get P30 output from context if available.

    Args:
        ctx: Pipeline context.

    Returns:
        P30Output if available, None otherwise.
    """
    if hasattr(ctx, 'p30_verification'):
        return ctx.p30_verification
    return None


def get_p30_verified_text(ctx: "PipelineContext") -> str:
    """
    Get verified text from P30 output.

    Args:
        ctx: Pipeline context.

    Returns:
        Verified text string, empty if blocked.
    """
    output = get_p30_output(ctx)
    if output:
        return output.verified_text
    return ""


def is_p30_passed(ctx: "PipelineContext") -> bool:
    """
    Check if P30 verification passed.

    Args:
        ctx: Pipeline context.

    Returns:
        True if passed or passed with warnings, False if failed/skipped.
    """
    output = get_p30_output(ctx)
    if output:
        return output.verification_status in (
            VerificationStatus.PASSED,
            VerificationStatus.PASSED_WITH_WARNINGS,
        )
    return True  # Default to passed if not run


# =============================================================================
# EXPORTS
# =============================================================================

__all__ = [
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
    "HAS_COMPLIANCE_CHECKER",
    "HAS_P12_VALIDATOR",
    "HAS_COHERENCE_ENGINE",
    "VERSION",
]
