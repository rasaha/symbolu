"""
Phase 12 Hardening: Acoustic-Safe Quality Gating

This module provides governance-critical hardening functions that ensure
acoustic diagnostics can ONLY reduce quality, never increase it.

CRITICAL INVARIANTS:
- INV-P12-H1: adjusted_quality <= base_quality (ALWAYS)
- INV-P12-H2: Acoustic input can ONLY reduce quality, never increase
- INV-P12-H3: When acoustic_alignment is None, output == input (bitwise)
- INV-P12-H4: If base_quality < threshold, adjusted_quality cannot cross threshold
              (gate monotonicity - acoustic can only close gates, never open)

WHAT ACOUSTIC DIAGNOSTICS CAN DO:
- Reduce quality (within 5% max)
- Leave quality unchanged
- Annotate diagnostics (observer-only)

WHAT ACOUSTIC DIAGNOSTICS CANNOT DO:
- Increase quality
- Flip a CLOSED → OPEN gate
- Enable insights/actions previously blocked
- Influence regime, discourse, semantics, or lexical layers

This module is designed to be auditable and legally defensible.
"""

from __future__ import annotations

from typing import Tuple, Optional


# =============================================================================
# EXCEPTION CLASS
# =============================================================================


class AcousticHardeningViolation(Exception):
    """
    Exception raised when Phase 12 acoustic hardening invariants are violated.

    This exception indicates a critical implementation bug where acoustic
    diagnostics have influenced the system in forbidden ways:
    - Increased quality (INV-P12-H1 violation)
    - Opened a gate that was closed (INV-P12-H4 violation)
    - Modified authoritative data

    This exception should NEVER be raised in production. If it is raised,
    it indicates a governance-critical bug that requires immediate attention.

    Usage:
        if adjusted_quality > base_quality:
            raise AcousticHardeningViolation(
                f"INV-P12-H1 VIOLATED: adjusted={adjusted_quality} > base={base_quality}"
            )
    """

    pass


# =============================================================================
# GATE MONOTONICITY HELPER
# =============================================================================


def verify_gate_monotonicity(
    base_quality: float,
    adjusted_quality: float,
    threshold: float,
) -> bool:
    """
    Verify gate monotonicity invariant (INV-P12-H4).

    Gate monotonicity states that acoustic adjustments can ONLY close gates,
    never open them. This means:
    - If base_quality < threshold (gate is CLOSED), adjusted cannot cross upward
    - If base_quality >= threshold (gate is OPEN), adjusted may stay open or close

    Since acoustic can only REDUCE quality (INV-P12-H1: adjusted <= base),
    gate monotonicity is automatically satisfied when INV-P12-H1 holds.
    This helper provides explicit verification for audit purposes.

    Args:
        base_quality: Quality score before acoustic adjustment
        adjusted_quality: Quality score after acoustic adjustment
        threshold: The gating threshold (e.g., 0.40 for therapy, 0.45 for identity)

    Returns:
        True if gate monotonicity is satisfied, False if violated

    Invariant Logic:
        - If base_quality < threshold (CLOSED), adjusted MUST be < threshold
        - This follows from adjusted <= base < threshold
        - Acoustic can NEVER open a closed gate

    Example:
        >>> verify_gate_monotonicity(0.35, 0.35, 0.40)  # CLOSED, stays CLOSED
        True
        >>> verify_gate_monotonicity(0.50, 0.48, 0.40)  # OPEN, stays OPEN
        True
        >>> verify_gate_monotonicity(0.50, 0.38, 0.40)  # OPEN → CLOSED (allowed)
        True
        >>> verify_gate_monotonicity(0.35, 0.42, 0.40)  # CLOSED → OPEN (FORBIDDEN)
        False
    """
    # First, verify the directional constraint (INV-P12-H1)
    if adjusted_quality > base_quality:
        return False  # Directional violation

    # Gate monotonicity check (INV-P12-H4)
    base_gate_open = base_quality >= threshold
    adjusted_gate_open = adjusted_quality >= threshold

    # Forbidden: base gate CLOSED but adjusted gate OPEN
    if not base_gate_open and adjusted_gate_open:
        return False  # Gate monotonicity violation

    return True


def assert_acoustic_safe(
    base_quality: float,
    adjusted_quality: float,
    thresholds: Tuple[float, ...] = (0.40, 0.45),
) -> None:
    """
    Assert that acoustic adjustment is safe (all hardening invariants hold).

    This is a convenience function for use in tests and validation code.
    It checks all Phase 12 hardening invariants and raises an exception
    if any are violated.

    Args:
        base_quality: Quality score before acoustic adjustment
        adjusted_quality: Quality score after acoustic adjustment
        thresholds: Tuple of gating thresholds to check (default: therapy 0.40, identity 0.45)

    Raises:
        AcousticHardeningViolation: If any invariant is violated

    Invariants Checked:
        - INV-P12-H1: adjusted_quality <= base_quality
        - INV-P12-H4: Gate monotonicity for all provided thresholds
    """
    # Check INV-P12-H1: Directional constraint
    if adjusted_quality > base_quality:
        raise AcousticHardeningViolation(
            f"INV-P12-H1 VIOLATED: adjusted_quality ({adjusted_quality}) > "
            f"base_quality ({base_quality}). Acoustic adjustment increased quality."
        )

    # Check INV-P12-H4: Gate monotonicity for each threshold
    for threshold in thresholds:
        if not verify_gate_monotonicity(base_quality, adjusted_quality, threshold):
            raise AcousticHardeningViolation(
                f"INV-P12-H4 VIOLATED: Gate monotonicity failed for threshold {threshold}. "
                f"base_quality={base_quality}, adjusted_quality={adjusted_quality}. "
                f"Acoustic adjustment opened a previously closed gate."
            )


def verify_backward_compatibility(
    quality_with_acoustic: Optional[float],
    quality_without_acoustic: Optional[float],
    acoustic_alignment_present: bool,
) -> bool:
    """
    Verify backward compatibility: when no acoustic input, output is identical.

    INV-P12-H3 states that when acoustic_alignment is None, the output
    must be bitwise identical to the pre-extension version.

    Args:
        quality_with_acoustic: Quality computed with acoustic extension enabled
        quality_without_acoustic: Quality computed with original formula only
        acoustic_alignment_present: Whether acoustic alignment data was provided

    Returns:
        True if backward compatibility is satisfied, False otherwise

    Note:
        When acoustic_alignment is None (acoustic_alignment_present=False),
        both values MUST be exactly equal (no floating-point drift).
    """
    if not acoustic_alignment_present:
        # When no acoustic input, values must be exactly equal
        return quality_with_acoustic == quality_without_acoustic
    else:
        # When acoustic input is present, adjusted quality may differ (but only downward)
        if quality_with_acoustic is None and quality_without_acoustic is None:
            return True
        if quality_with_acoustic is None or quality_without_acoustic is None:
            return False
        return quality_with_acoustic <= quality_without_acoustic


# =============================================================================
# QUALITY GATING THRESHOLDS (from domain_profiles.py)
# =============================================================================

# Known quality thresholds used in the system
THERAPY_QUALITY_THRESHOLD = 0.40
IDENTITY_QUALITY_THRESHOLD = 0.45
ALL_QUALITY_THRESHOLDS = (THERAPY_QUALITY_THRESHOLD, IDENTITY_QUALITY_THRESHOLD)


# =============================================================================
# PUBLIC EXPORTS
# =============================================================================

__all__ = [
    # Exception
    "AcousticHardeningViolation",
    # Verification functions
    "verify_gate_monotonicity",
    "assert_acoustic_safe",
    "verify_backward_compatibility",
    # Constants
    "THERAPY_QUALITY_THRESHOLD",
    "IDENTITY_QUALITY_THRESHOLD",
    "ALL_QUALITY_THRESHOLDS",
]
