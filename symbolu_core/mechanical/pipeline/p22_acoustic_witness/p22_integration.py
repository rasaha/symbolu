"""
P22 - Acoustic-Vrtti Witness Extractor Integration

This phase is witness-only and has zero authority over cognition or delivery.

Integration functions for running P22 within the pipeline.
Provides singleton access and pipeline-friendly entry points.

Usage:
    from symbolu_core.mechanical.pipeline.p22_acoustic_witness import maybe_run_p22

    # In pipeline after P21:
    maybe_run_p22(ctx)

    # Access witness:
    if ctx.p22_acoustic_witness is not None:
        print(f"Signature: {ctx.p22_acoustic_witness.acoustic_signature}")
        print(f"Dominant: {ctx.p22_acoustic_witness.dominant_motion}")

CRITICAL CONSTRAINTS:
    - Must not block pipeline execution
    - Must not modify routing, MLCR, TTOR, Fusion, DHA
    - Must not read intent, regime, discourse, semantics
    - Must not feed back into P1-P21
    - Attaches result to ctx.p22_acoustic_witness only
    - No downstream routing effect
"""

from __future__ import annotations

from typing import Any, Optional

from symbolu_core.mechanical.pipeline.p22_acoustic_witness.p22_schema import (
    P22_VERSION,
    MotionPrimitive,
    MotionBalance,
    P22AcousticVrittiWitness,
    P22InvariantViolation,
    create_empty_witness,
)
from symbolu_core.mechanical.pipeline.p22_acoustic_witness.p22_resolver import (
    AcousticVrittiWitnessResolver,
)


# ============================================================================
# SINGLETON INSTANCE
# ============================================================================


_p22_resolver: Optional[AcousticVrittiWitnessResolver] = None


def get_p22_resolver() -> AcousticVrittiWitnessResolver:
    """
    Get the singleton AcousticVrittiWitnessResolver instance.

    This phase is witness-only and has zero authority over cognition or delivery.

    Returns:
        The shared AcousticVrittiWitnessResolver instance
    """
    global _p22_resolver
    if _p22_resolver is None:
        _p22_resolver = AcousticVrittiWitnessResolver()
    return _p22_resolver


# ============================================================================
# INTEGRATION FUNCTIONS
# ============================================================================


def maybe_run_p22(ctx: Any) -> Optional[P22AcousticVrittiWitness]:
    """
    Run P22 acoustic witness extraction if prerequisites are met.

    This phase is witness-only and has zero authority over cognition or delivery.

    This is the main integration entry point. It:
        1. Checks if P22 should run
        2. Extracts acoustic witness from user input
        3. Attaches the witness to ctx.p22_acoustic_witness
        4. Never blocks pipeline execution (returns None on skip)

    P22 is designed to run after P21 (delivery barrier) and has no
    downstream routing effect.

    CRITICAL: This function:
        - Must NOT modify routing, MLCR, TTOR, Fusion, DHA
        - Must NOT read intent, regime, discourse, semantics
        - Must NOT feed back into P1-P21
        - Must NOT block pipeline execution

    Args:
        ctx: PipelineContext or compatible object

    Returns:
        The P22AcousticVrittiWitness if run, None if skipped
    """
    # Check if P22 is disabled on this context
    if is_p22_disabled(ctx):
        return None

    # P22 can run with minimal context
    # Only skip if context is completely invalid
    if ctx is None:
        return None

    # Run the resolver
    try:
        resolver = get_p22_resolver()
        witness = resolver.resolve_from_context(ctx)
    except P22InvariantViolation:
        # Re-raise invariant violations - these are critical
        raise
    except Exception:
        # For other errors, return None to not block pipeline
        # In production, this should be logged
        return None

    # Attach to context (witness-only attribute)
    _attach_witness(ctx, witness)

    return witness


def run_p22(ctx: Any) -> P22AcousticVrittiWitness:
    """
    Run P22 directly, always returning a witness.

    This phase is witness-only and has zero authority over cognition or delivery.

    Unlike maybe_run_p22, this always runs and returns a witness.
    Use this for testing or when you need guaranteed output.

    Args:
        ctx: PipelineContext or compatible object

    Returns:
        P22AcousticVrittiWitness (always returns, never None)
    """
    resolver = get_p22_resolver()
    return resolver.resolve_from_context(ctx)


def run_p22_directly(
    user_raw_text: str,
    delivery_mode_suppressed: bool = False,
) -> P22AcousticVrittiWitness:
    """
    Run P22 directly with explicit inputs (for testing).

    This phase is witness-only and has zero authority over cognition or delivery.

    This bypasses context extraction and allows direct testing
    of the acoustic witness extraction with mock values.

    Args:
        user_raw_text: The raw user input text
        delivery_mode_suppressed: Whether delivery is suppressed

    Returns:
        P22AcousticVrittiWitness with acoustic observations
    """
    from symbolu_core.mechanical.pipeline.p21_delivery.p21_delivery_schema import DeliveryMode

    delivery_mode = DeliveryMode.SUPPRESSED if delivery_mode_suppressed else None

    resolver = get_p22_resolver()
    return resolver.resolve(user_raw_text, delivery_mode)


# ============================================================================
# HELPER FUNCTIONS
# ============================================================================


def _attach_witness(ctx: Any, witness: P22AcousticVrittiWitness) -> None:
    """
    Attach the witness report to context.

    This phase is witness-only and has zero authority over cognition or delivery.

    Attaches to ctx.p22_acoustic_witness only.
    P22 must NOT write to any other ctx attribute.

    Args:
        ctx: PipelineContext
        witness: The P22 witness report
    """
    # Attach to p22_acoustic_witness (standard attribute)
    if hasattr(ctx, "p22_acoustic_witness"):
        ctx.p22_acoustic_witness = witness
    else:
        try:
            setattr(ctx, "p22_acoustic_witness", witness)
        except AttributeError:
            pass  # Context is frozen

    # Also attach to p22 for consistency with other phases
    if hasattr(ctx, "p22"):
        ctx.p22 = witness
    else:
        try:
            setattr(ctx, "p22", witness)
        except AttributeError:
            pass  # Context is frozen


def is_p22_disabled(ctx: Any) -> bool:
    """
    Check if P22 is disabled on this context.

    This phase is witness-only and has zero authority over cognition or delivery.

    P22 can be disabled by setting ctx._p22_disabled = True.

    Args:
        ctx: PipelineContext or compatible object

    Returns:
        True if P22 is disabled, False otherwise
    """
    return getattr(ctx, "_p22_disabled", False)


def has_p22_witness(ctx: Any) -> bool:
    """
    Check if context has a P22 witness attached.

    This phase is witness-only and has zero authority over cognition or delivery.

    Args:
        ctx: PipelineContext or compatible object

    Returns:
        True if ctx.p22_acoustic_witness or ctx.p22 is set
    """
    return (
        getattr(ctx, "p22_acoustic_witness", None) is not None or
        getattr(ctx, "p22", None) is not None
    )


def get_p22_witness(ctx: Any) -> Optional[P22AcousticVrittiWitness]:
    """
    Get the P22 witness from context if present.

    This phase is witness-only and has zero authority over cognition or delivery.

    Args:
        ctx: PipelineContext or compatible object

    Returns:
        The P22AcousticVrittiWitness if present, None otherwise
    """
    witness = getattr(ctx, "p22_acoustic_witness", None)
    if witness is None:
        witness = getattr(ctx, "p22", None)
    return witness


def get_acoustic_signature(ctx: Any) -> str:
    """
    Get the acoustic signature from context.

    This phase is witness-only and has zero authority over cognition or delivery.

    Convenience function for downstream access.

    Args:
        ctx: PipelineContext or compatible object

    Returns:
        Acoustic signature string, or empty string if no witness
    """
    witness = get_p22_witness(ctx)
    if witness is None:
        return ""
    return witness.acoustic_signature


def get_dominant_motion(ctx: Any) -> Optional[MotionPrimitive]:
    """
    Get the dominant motion from context.

    This phase is witness-only and has zero authority over cognition or delivery.

    Convenience function for downstream access.

    Args:
        ctx: PipelineContext or compatible object

    Returns:
        MotionPrimitive or None
    """
    witness = get_p22_witness(ctx)
    if witness is None:
        return None
    return witness.dominant_motion


def get_motion_balance(ctx: Any) -> MotionBalance:
    """
    Get the motion balance from context.

    This phase is witness-only and has zero authority over cognition or delivery.

    Convenience function for downstream access.

    Args:
        ctx: PipelineContext or compatible object

    Returns:
        MotionBalance (BALANCED as default if no witness)
    """
    witness = get_p22_witness(ctx)
    if witness is None:
        return MotionBalance.BALANCED
    return witness.motion_balance


def get_pressure_band(ctx: Any) -> str:
    """
    Get the pressure band from context.

    This phase is witness-only and has zero authority over cognition or delivery.

    Convenience function for downstream access.

    Args:
        ctx: PipelineContext or compatible object

    Returns:
        Pressure band string ("low" as default if no witness)
    """
    witness = get_p22_witness(ctx)
    if witness is None:
        return "low"
    return witness.pressure_band


def get_vritti_vector(ctx: Any) -> dict:
    """
    Get the vritti vector from context.

    This phase is witness-only and has zero authority over cognition or delivery.

    Convenience function for downstream access.

    Args:
        ctx: PipelineContext or compatible object

    Returns:
        Dict of motion values, or empty dict if no witness
    """
    witness = get_p22_witness(ctx)
    if witness is None:
        return {}
    return dict(witness.vritti_vector)


def get_p22_version() -> str:
    """
    Get the current P22 schema version.

    This phase is witness-only and has zero authority over cognition or delivery.

    Returns:
        Version string (e.g., "1.0.0")
    """
    return P22_VERSION


# ============================================================================
# PUBLIC EXPORTS
# ============================================================================


__all__ = [
    # Singleton
    "get_p22_resolver",
    # Integration
    "maybe_run_p22",
    "run_p22",
    "run_p22_directly",
    # Helpers
    "is_p22_disabled",
    "has_p22_witness",
    "get_p22_witness",
    "get_acoustic_signature",
    "get_dominant_motion",
    "get_motion_balance",
    "get_pressure_band",
    "get_vritti_vector",
    "get_p22_version",
]
