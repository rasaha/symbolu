"""
P15 Regression Guard — Integration Module

This module provides the integration functions for using the P15 Regression Guard
within the pipeline:

- capture_p15_snapshot(): Capture and store snapshot after P15 completes
- enforce_p15_regression_guard(): Validate context at start of phases >= 16

Usage in pipeline:
    # After P15 completes:
    ctx = run_p15(ctx)
    capture_p15_snapshot(ctx)  # Captures and stores snapshot on ctx

    # At start of P16, P17, etc:
    enforce_p15_regression_guard(ctx, phase_number=16)  # Raises on violation

Design Principles:
- Snapshot captured ONCE immediately after P15
- Guard enforced at the START of every phase >= 16
- Any violation raises P15RegressionViolationError (deterministic, non-bypassable)
- No auto-correction, no silent failure
"""

from __future__ import annotations

from typing import Any, Optional

from symbolu.mechanical.pipeline.p15_authority_guard.p15_regression_schema import (
    P15AuthoritySnapshot,
    P15RegressionViolationError,
)
from symbolu.mechanical.pipeline.p15_authority_guard.p15_regression_guard import (
    P15RegressionGuard,
)


# ============================================================================
# MODULE-LEVEL GUARD INSTANCE
# ============================================================================


# Single, stateless guard instance for use throughout the pipeline
_guard = P15RegressionGuard()


# ============================================================================
# SNAPSHOT STORAGE KEY
# ============================================================================


# Attribute name used to store the snapshot on the context
_SNAPSHOT_ATTR = "_p15_authority_snapshot"


# ============================================================================
# PUBLIC FUNCTIONS
# ============================================================================


def capture_p15_snapshot(ctx: Any) -> None:
    """
    Capture the P15 authority snapshot and store it on the context.

    This function MUST be called exactly once, immediately after P15 completes.
    The snapshot is stored as an attribute on the context object.

    Args:
        ctx: The PipelineContext after P15 has completed

    Raises:
        ValueError: If required context fields are missing
        RuntimeError: If snapshot has already been captured (double-capture)

    Side Effects:
        Adds _p15_authority_snapshot attribute to ctx
    """
    # Check for double-capture
    if hasattr(ctx, _SNAPSHOT_ATTR) and getattr(ctx, _SNAPSHOT_ATTR) is not None:
        raise RuntimeError(
            "P15 authority snapshot has already been captured. "
            "Snapshot capture must happen exactly once after P15."
        )

    # Capture the snapshot
    snapshot = _guard.capture(ctx)

    # Store on context
    setattr(ctx, _SNAPSHOT_ATTR, snapshot)


def enforce_p15_regression_guard(ctx: Any, phase_number: int) -> None:
    """
    Enforce the P15 regression guard at the start of a phase.

    This function MUST be called at the START of every phase >= 16.
    If any violations are detected, it raises P15RegressionViolationError.

    For phases < 16, this function is a no-op (guard inactive).

    Args:
        ctx: The PipelineContext being processed
        phase_number: The phase number being entered (e.g., 16, 17, 18...)

    Raises:
        P15RegressionViolationError: If any violations are detected
        RuntimeError: If snapshot was not captured (missing snapshot)
    """
    # Guard inactive for phases < 16
    if phase_number < _guard.GUARD_ACTIVE_FROM_PHASE:
        return

    # Get the snapshot
    snapshot = get_p15_snapshot(ctx)

    if snapshot is None:
        raise RuntimeError(
            f"P15 authority snapshot not found at phase {phase_number}. "
            f"capture_p15_snapshot() must be called after P15 completes."
        )

    # Validate
    violations = _guard.validate(snapshot, ctx, phase_number)

    # If violations, raise deterministic exception
    if violations:
        raise P15RegressionViolationError(
            violations=violations,
            phase=phase_number,
        )


def get_p15_snapshot(ctx: Any) -> Optional[P15AuthoritySnapshot]:
    """
    Get the P15 authority snapshot from the context.

    Args:
        ctx: The PipelineContext

    Returns:
        The P15AuthoritySnapshot if it exists, None otherwise
    """
    return getattr(ctx, _SNAPSHOT_ATTR, None)


def has_p15_snapshot(ctx: Any) -> bool:
    """
    Check if the context has a P15 authority snapshot.

    Args:
        ctx: The PipelineContext

    Returns:
        True if snapshot exists, False otherwise
    """
    return get_p15_snapshot(ctx) is not None


def validate_p15_snapshot_without_raise(
    ctx: Any, phase_number: int
) -> Optional[P15RegressionViolationError]:
    """
    Validate the P15 regression guard without raising an exception.

    This is useful for testing and diagnostic purposes where you want
    to inspect violations without halting execution.

    Args:
        ctx: The PipelineContext being processed
        phase_number: The phase number being entered

    Returns:
        P15RegressionViolationError if violations detected, None otherwise
    """
    # Guard inactive for phases < 16
    if phase_number < _guard.GUARD_ACTIVE_FROM_PHASE:
        return None

    # Get the snapshot
    snapshot = get_p15_snapshot(ctx)
    if snapshot is None:
        return None

    # Validate
    violations = _guard.validate(snapshot, ctx, phase_number)

    if violations:
        return P15RegressionViolationError(
            violations=violations,
            phase=phase_number,
        )

    return None


# ============================================================================
# DIRECT GUARD ACCESS (FOR TESTING)
# ============================================================================


def get_guard() -> P15RegressionGuard:
    """
    Get the module-level guard instance.

    Primarily for testing purposes.

    Returns:
        The P15RegressionGuard instance
    """
    return _guard


def capture_snapshot_directly(ctx: Any) -> P15AuthoritySnapshot:
    """
    Capture a snapshot without storing it on the context.

    Primarily for testing purposes.

    Args:
        ctx: The PipelineContext

    Returns:
        P15AuthoritySnapshot
    """
    return _guard.capture(ctx)


def validate_directly(
    snapshot: P15AuthoritySnapshot,
    ctx: Any,
    phase_number: int,
) -> list:
    """
    Validate directly without raising an exception.

    Primarily for testing purposes.

    Args:
        snapshot: The P15AuthoritySnapshot
        ctx: The PipelineContext
        phase_number: The phase number

    Returns:
        List of P15RegressionViolation objects
    """
    return _guard.validate(snapshot, ctx, phase_number)


# ============================================================================
# PUBLIC EXPORTS
# ============================================================================


__all__ = [
    # Primary integration functions
    "capture_p15_snapshot",
    "enforce_p15_regression_guard",
    "get_p15_snapshot",
    "has_p15_snapshot",
    # Diagnostic function
    "validate_p15_snapshot_without_raise",
    # Testing helpers
    "get_guard",
    "capture_snapshot_directly",
    "validate_directly",
]
