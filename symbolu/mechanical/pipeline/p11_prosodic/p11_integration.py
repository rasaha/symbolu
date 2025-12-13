"""
P11 - Prosodic Evidence Capture Pipeline Integration Module

Provides a thin shim for integrating P11 (Prosodic Evidence Capture)
into the Symbol-U pipeline. Called immediately after P10, before any
downstream speech realization.

P11 is a WITNESS-ONLY phase. It does NOT modify behavior.

Usage in orchestrator:
    from .p11_prosodic.p11_integration import maybe_run_p11

    # After P10 stage
    maybe_run_p11(ctx)
    # ctx.p11_prosodic_evidence is now set (or None if P10 missing)

Authority Model:
    - P11 consumes P10 AcousticParameterFrame (read-only)
    - P11 cannot mutate P10 output
    - P11 cannot block, redirect, alter regime, or alter discourse
    - P11 produces ProsodicEvidenceFrame (read-only, non-actuating)
    - P11 validates invariants but does NOT correct violations

CRITICAL: P11 is witness-only. It observes, records, and attests to
acoustic/prosodic parameters — without modifying them.

ARCHITECTURAL PRINCIPLE:
    P11 exists to observe, not to optimize.
    Sound must obey meaning.
    Meaning must never obey sound.
"""

from typing import Any, Optional

from symbolu.mechanical.pipeline.p11_prosodic.p11_prosodic_schema import (
    ProsodicEvidenceFrame,
)
from symbolu.mechanical.pipeline.p11_prosodic.p11_prosodic_resolver import (
    P11ProsodicResolver,
)


# Singleton P11 resolver instance
_p11_resolver: Optional[P11ProsodicResolver] = None


def get_p11_resolver() -> P11ProsodicResolver:
    """Get or create the singleton P11 prosodic resolver instance."""
    global _p11_resolver
    if _p11_resolver is None:
        _p11_resolver = P11ProsodicResolver()
    return _p11_resolver


def maybe_run_p11(ctx: Any) -> Any:
    """
    Run P11 prosodic evidence capture on the pipeline context.

    This is the main integration function to call from the pipeline orchestrator.
    P11 requires P10 to be present.

    IMPORTANT: This function attaches the result to ctx.p11_prosodic_evidence.
    It returns the context unchanged (for chaining).

    CRITICAL: P11 is witness-only. It cannot block, redirect, alter regime,
    or alter discourse. It only observes and records.

    Rules:
    - If ctx.p11_prosodic_evidence already exists → return ctx unchanged
    - If P10 is not available → set ctx.p11_prosodic_evidence = None
    - Attach ProsodicEvidenceFrame to ctx.p11_prosodic_evidence
    - Must not alter upstream behavior
    - Never raises - returns None on any error

    Args:
        ctx: Pipeline context with p10_acoustic frame.

    Returns:
        The same context object (for chaining).
    """
    # Rule 1: If P11 already ran, don't run again
    if hasattr(ctx, 'p11_prosodic_evidence') and ctx.p11_prosodic_evidence is not None:
        return ctx

    # Run P11 resolver
    resolver = get_p11_resolver()
    evidence = resolver.capture(ctx)

    # Attach to context (may be None if P10 not available)
    ctx.p11_prosodic_evidence = evidence

    return ctx


def run_p11_directly(ctx: Any) -> Optional[ProsodicEvidenceFrame]:
    """
    Run P11 directly with explicit context.

    Useful for testing or standalone prosodic evidence capture.

    CRITICAL: The evidence frame is observational only. It cannot
    modify behavior or correct violations.

    Args:
        ctx: Pipeline context with p10_acoustic frame.

    Returns:
        ProsodicEvidenceFrame with evidence attestation, or None if P10 missing.
    """
    resolver = get_p11_resolver()
    return resolver.capture(ctx)


def get_p11_prosodic_evidence(ctx: Any) -> Optional[ProsodicEvidenceFrame]:
    """
    Get the P11 prosodic evidence frame from context.

    Args:
        ctx: Pipeline context.

    Returns:
        ProsodicEvidenceFrame or None if not available.
    """
    if not hasattr(ctx, 'p11_prosodic_evidence'):
        return None
    return ctx.p11_prosodic_evidence


def has_violations(ctx: Any) -> bool:
    """
    Check if any invariant violations were detected.

    Args:
        ctx: Pipeline context.

    Returns:
        True if violations detected, False otherwise.
        Returns False if P11 hasn't run.
    """
    evidence = get_p11_prosodic_evidence(ctx)
    if evidence is None:
        return False
    return evidence.violations_detected


def get_failed_invariants(ctx: Any) -> list:
    """
    Get list of failed invariant names.

    Args:
        ctx: Pipeline context.

    Returns:
        List of failed invariant names, or empty list if P11 hasn't run.
    """
    evidence = get_p11_prosodic_evidence(ctx)
    if evidence is None:
        return []
    return evidence.get_failed_invariants()


def get_invariant_checks(ctx: Any) -> Optional[dict]:
    """
    Get the full invariant check results.

    Args:
        ctx: Pipeline context.

    Returns:
        Dictionary of invariant name -> pass/fail, or None if P11 hasn't run.
    """
    evidence = get_p11_prosodic_evidence(ctx)
    if evidence is None:
        return None
    return evidence.invariant_checks


def is_fully_suppressed(ctx: Any) -> bool:
    """
    Check if all suppressions are active in the evidence frame.

    Args:
        ctx: Pipeline context.

    Returns:
        True if all suppressions active, False otherwise.
        Returns True (conservative) if P11 hasn't run.
    """
    evidence = get_p11_prosodic_evidence(ctx)
    if evidence is None:
        return True
    return evidence.is_fully_suppressed()


def get_witnessed_speech_rate(ctx: Any) -> Optional[float]:
    """
    Get the witnessed speech rate from the evidence frame.

    Args:
        ctx: Pipeline context.

    Returns:
        Speech rate or None if P11 hasn't run.
    """
    evidence = get_p11_prosodic_evidence(ctx)
    if evidence is None:
        return None
    return evidence.speech_rate


def get_witnessed_energy_level(ctx: Any) -> Optional[float]:
    """
    Get the witnessed energy level from the evidence frame.

    Args:
        ctx: Pipeline context.

    Returns:
        Energy level or None if P11 hasn't run.
    """
    evidence = get_p11_prosodic_evidence(ctx)
    if evidence is None:
        return None
    return evidence.energy_level


def get_witnessed_pitch_range(ctx: Any) -> Optional[tuple]:
    """
    Get the witnessed pitch range from the evidence frame.

    Args:
        ctx: Pipeline context.

    Returns:
        Pitch range (min_hz, max_hz) or None if P11 hasn't run.
    """
    evidence = get_p11_prosodic_evidence(ctx)
    if evidence is None:
        return None
    return evidence.pitch_range


def get_source_p10_version(ctx: Any) -> Optional[str]:
    """
    Get the source P10 version from the evidence frame.

    Args:
        ctx: Pipeline context.

    Returns:
        P10 version string or None if P11 hasn't run.
    """
    evidence = get_p11_prosodic_evidence(ctx)
    if evidence is None:
        return None
    return evidence.source_p10_version


def get_timestamp_utc(ctx: Any) -> Optional[str]:
    """
    Get the evidence capture timestamp.

    Args:
        ctx: Pipeline context.

    Returns:
        ISO-8601 timestamp or None if P11 hasn't run.
    """
    evidence = get_p11_prosodic_evidence(ctx)
    if evidence is None:
        return None
    return evidence.timestamp_utc


__all__ = [
    # Core functions
    "get_p11_resolver",
    "maybe_run_p11",
    "run_p11_directly",
    "get_p11_prosodic_evidence",
    # Violation accessors
    "has_violations",
    "get_failed_invariants",
    "get_invariant_checks",
    # Parameter accessors
    "is_fully_suppressed",
    "get_witnessed_speech_rate",
    "get_witnessed_energy_level",
    "get_witnessed_pitch_range",
    # Provenance accessors
    "get_source_p10_version",
    "get_timestamp_utc",
]
