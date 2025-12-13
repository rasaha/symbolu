"""
P13 - Acoustic Safety Envelope Pipeline Integration Module

Provides a thin shim for integrating P13 (Acoustic Safety Envelope)
into the Symbol-U pipeline. Called immediately after P12, before any
downstream acoustic tokenization or speech realization.

P13 is a SAFETY-BINDING phase. It defines absolute bounds that
downstream phases MUST respect.

Usage in orchestrator:
    from .p13_acoustic_safety.p13_integration import maybe_run_p13

    # After P12 stage
    maybe_run_p13(ctx)
    # ctx.p13_safety_envelope is now set (or BLOCKED envelope if insufficient data)

Authority Model:
    - P13 consumes P10, P11, P12, P6, P7 outputs (read-only)
    - P13 cannot mutate any upstream output
    - P13 cannot amplify acoustic expressiveness
    - P13 produces AcousticSafetyEnvelope (read-only, binding)
    - P13 failure forces HOLD downstream (BLOCKED envelope)

CRITICAL: P13 is binding. Downstream renderers violating P13
are considered unsafe by design.

ARCHITECTURAL PRINCIPLE:
    P13 is the last safety lock before sound.
    Phase 1 (acoustic tokenization) must consume P13 verbatim.
    Renderers violating P13 are considered unsafe by design.
"""

from typing import Any, List, Optional

from symbolu.mechanical.pipeline.p13_acoustic_safety.p13_acoustic_safety_schema import (
    AcousticRiskLevel,
    AcousticSafetyEnvelope,
    SafetyViolation,
    get_blocked_envelope,
)
from symbolu.mechanical.pipeline.p13_acoustic_safety.p13_acoustic_safety_resolver import (
    P13AcousticSafetyResolver,
)


# Singleton P13 resolver instance
_p13_resolver: Optional[P13AcousticSafetyResolver] = None


def get_p13_resolver() -> P13AcousticSafetyResolver:
    """Get or create the singleton P13 acoustic safety resolver instance."""
    global _p13_resolver
    if _p13_resolver is None:
        _p13_resolver = P13AcousticSafetyResolver()
    return _p13_resolver


def maybe_run_p13(ctx: Any) -> Any:
    """
    Run P13 acoustic safety envelope resolution on the pipeline context.

    This is the main integration function to call from the pipeline orchestrator.
    P13 requires P12 to have run for complete validation, but will produce
    a BLOCKED envelope if upstream phases are missing.

    IMPORTANT: This function attaches the result to ctx.p13_safety_envelope.
    It returns the context unchanged (for chaining).

    CRITICAL: P13 is binding. The envelope constrains all downstream
    acoustic expression. Violating the envelope is unsafe.

    Rules:
    - If ctx.p13_safety_envelope already exists -> return ctx unchanged
    - If P10 is not available -> attach BLOCKED envelope
    - On any error -> attach BLOCKED envelope
    - P13 failure forces HOLD downstream
    - Attach AcousticSafetyEnvelope to ctx.p13_safety_envelope

    Args:
        ctx: Pipeline context with phase outputs.

    Returns:
        The same context object (for chaining).
    """
    # Rule 1: If P13 already ran, don't run again
    if hasattr(ctx, 'p13_safety_envelope') and ctx.p13_safety_envelope is not None:
        return ctx

    # Run P13 resolver
    try:
        resolver = get_p13_resolver()
        envelope = resolver.resolve(ctx)

        # Attach to context
        if envelope is not None:
            ctx.p13_safety_envelope = envelope
        else:
            # Should not happen (resolver returns BLOCKED on missing P10)
            # but defensive: attach BLOCKED envelope
            ctx.p13_safety_envelope = get_blocked_envelope()
    except Exception:
        # Fail-closed: on any error, attach BLOCKED envelope
        ctx.p13_safety_envelope = get_blocked_envelope()

    return ctx


def run_p13_directly(ctx: Any) -> Optional[AcousticSafetyEnvelope]:
    """
    Run P13 directly with explicit context.

    Useful for testing or standalone safety envelope computation.

    CRITICAL: The envelope is binding. Downstream phases must
    respect all bounds in the envelope.

    Args:
        ctx: Pipeline context with phase outputs.

    Returns:
        AcousticSafetyEnvelope with safety bounds.
    """
    resolver = get_p13_resolver()
    return resolver.resolve(ctx)


def get_p13_safety_envelope(ctx: Any) -> Optional[AcousticSafetyEnvelope]:
    """
    Get the P13 acoustic safety envelope from context.

    Args:
        ctx: Pipeline context.

    Returns:
        AcousticSafetyEnvelope or None if not available.
    """
    if not hasattr(ctx, 'p13_safety_envelope'):
        return None
    return ctx.p13_safety_envelope


def get_risk_level(ctx: Any) -> AcousticRiskLevel:
    """
    Get the current risk level from the safety envelope.

    Args:
        ctx: Pipeline context.

    Returns:
        AcousticRiskLevel (defaults to BLOCKED if not available).
    """
    envelope = get_p13_safety_envelope(ctx)
    if envelope is None:
        return AcousticRiskLevel.BLOCKED  # Conservative default
    return envelope.risk_level


def is_safe(ctx: Any) -> bool:
    """
    Check if acoustic expression is SAFE.

    Args:
        ctx: Pipeline context.

    Returns:
        True if SAFE, False otherwise.
    """
    return get_risk_level(ctx) == AcousticRiskLevel.SAFE


def is_caution(ctx: Any) -> bool:
    """
    Check if acoustic expression is at CAUTION level.

    Args:
        ctx: Pipeline context.

    Returns:
        True if CAUTION, False otherwise.
    """
    return get_risk_level(ctx) == AcousticRiskLevel.CAUTION


def is_blocked(ctx: Any) -> bool:
    """
    Check if acoustic expression is BLOCKED.

    Args:
        ctx: Pipeline context.

    Returns:
        True if BLOCKED, False otherwise.
        Returns True if P13 hasn't run (conservative default).
    """
    envelope = get_p13_safety_envelope(ctx)
    if envelope is None:
        return True  # Conservative: BLOCKED if no envelope
    return envelope.is_blocked()


def has_violations(ctx: Any) -> bool:
    """
    Check if any safety violations were detected.

    Args:
        ctx: Pipeline context.

    Returns:
        True if violations detected, False otherwise.
        Returns False if P13 hasn't run.
    """
    envelope = get_p13_safety_envelope(ctx)
    if envelope is None:
        return False
    return envelope.has_violations()


def get_violations(ctx: Any) -> List[SafetyViolation]:
    """
    Get all safety violations from the envelope.

    Args:
        ctx: Pipeline context.

    Returns:
        List of violations, or empty list if P13 hasn't run.
    """
    envelope = get_p13_safety_envelope(ctx)
    if envelope is None:
        return []
    return list(envelope.violations)


def has_violation(ctx: Any, violation: SafetyViolation) -> bool:
    """
    Check if a specific violation type was detected.

    Args:
        ctx: Pipeline context.
        violation: The violation type to check.

    Returns:
        True if the violation was detected, False otherwise.
    """
    envelope = get_p13_safety_envelope(ctx)
    if envelope is None:
        return False
    return envelope.has_violation(violation)


def allows_emphasis(ctx: Any) -> bool:
    """
    Check if emphasis/stress is permitted.

    Args:
        ctx: Pipeline context.

    Returns:
        True if emphasis is allowed, False otherwise.
        Returns False if P13 hasn't run (conservative).
    """
    envelope = get_p13_safety_envelope(ctx)
    if envelope is None:
        return False
    return envelope.allow_emphasis


def allows_pitch_contours(ctx: Any) -> bool:
    """
    Check if pitch contours are permitted.

    Args:
        ctx: Pipeline context.

    Returns:
        True if pitch contours are allowed, False otherwise.
        Returns False if P13 hasn't run (conservative).
    """
    envelope = get_p13_safety_envelope(ctx)
    if envelope is None:
        return False
    return envelope.allow_pitch_contours


def allows_rhythm_variation(ctx: Any) -> bool:
    """
    Check if rhythm variation is permitted.

    Args:
        ctx: Pipeline context.

    Returns:
        True if rhythm variation is allowed, False otherwise.
        Returns False if P13 hasn't run (conservative).
    """
    envelope = get_p13_safety_envelope(ctx)
    if envelope is None:
        return False
    return envelope.allow_rhythm_variation


def allows_intonation_shift(ctx: Any) -> bool:
    """
    Check if intonation shifts are permitted.

    Args:
        ctx: Pipeline context.

    Returns:
        True if intonation shifts are allowed, False otherwise.
        Returns False if P13 hasn't run (conservative).
    """
    envelope = get_p13_safety_envelope(ctx)
    if envelope is None:
        return False
    return envelope.allow_intonation_shift


def is_fully_restricted(ctx: Any) -> bool:
    """
    Check if all expressive flags are False.

    Args:
        ctx: Pipeline context.

    Returns:
        True if fully restricted, False otherwise.
        Returns True if P13 hasn't run (conservative).
    """
    envelope = get_p13_safety_envelope(ctx)
    if envelope is None:
        return True  # Conservative default
    return envelope.is_fully_restricted()


def get_allowed_pitch_range(ctx: Any) -> Optional[tuple]:
    """
    Get the allowed pitch range.

    Args:
        ctx: Pipeline context.

    Returns:
        Tuple of (min_hz, max_hz), or None if P13 hasn't run.
    """
    envelope = get_p13_safety_envelope(ctx)
    if envelope is None:
        return None
    return envelope.allowed_pitch_range


def get_allowed_energy_range(ctx: Any) -> Optional[tuple]:
    """
    Get the allowed energy range.

    Args:
        ctx: Pipeline context.

    Returns:
        Tuple of (min, max), or None if P13 hasn't run.
    """
    envelope = get_p13_safety_envelope(ctx)
    if envelope is None:
        return None
    return envelope.allowed_energy_range


def get_max_energy(ctx: Any) -> float:
    """
    Get the maximum allowed energy level.

    Args:
        ctx: Pipeline context.

    Returns:
        Maximum energy level, or 0.35 (HOLD max) if P13 hasn't run.
    """
    envelope = get_p13_safety_envelope(ctx)
    if envelope is None:
        return 0.35  # Conservative: HOLD max
    return envelope.get_max_energy()


def get_pitch_variance_limit(ctx: Any) -> int:
    """
    Get the maximum allowed pitch variance in Hz.

    Args:
        ctx: Pipeline context.

    Returns:
        Maximum variance in Hz, or 10 (HOLD max) if P13 hasn't run.
    """
    envelope = get_p13_safety_envelope(ctx)
    if envelope is None:
        return 10  # Conservative: HOLD max
    return envelope.get_pitch_variance_limit()


def get_allowed_variance_range(ctx: Any) -> Optional[tuple]:
    """
    Get the allowed variance range.

    Args:
        ctx: Pipeline context.

    Returns:
        Tuple of (min, max), or None if P13 hasn't run.
    """
    envelope = get_p13_safety_envelope(ctx)
    if envelope is None:
        return None
    return envelope.allowed_variance_range


__all__ = [
    # Core functions
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
