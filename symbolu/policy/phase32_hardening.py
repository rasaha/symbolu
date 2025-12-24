"""
Phase 32 Hardening: Acoustic-Safe Insight Window Gating

This module provides governance-critical hardening functions that ensure
observer-only acoustic diagnostics can ONLY reduce insight_depth, never increase it.

CRITICAL INVARIANTS:
- INV-P32-H1: adjusted_insight_depth <= base_insight_depth (ALWAYS)
- INV-P32-H2: Acoustic input can ONLY reduce insight_depth, never increase
- INV-P32-H3: When acoustic_alignment is None, output == input (bitwise)
- INV-P32-H4: If base window is CLOSED, adjusted window MUST remain CLOSED
              (gate monotonicity - acoustic can only close windows, never open)

WHAT ACOUSTIC DIAGNOSTICS CAN DO:
- Reduce insight_depth (within 5% max)
- Leave insight_depth unchanged
- Annotate diagnostics (observer-only)

WHAT ACOUSTIC DIAGNOSTICS CANNOT DO:
- Increase insight_depth
- Flip a CLOSED → OPEN insight window
- Enable insights/reflections previously blocked
- Influence regime (P6), discourse (P7), semantics (P8), or lexical (P9)
- Create new "insight eligibility" paths

This module is designed to be auditable and legally defensible.

Design Principle:
    Sound must obey meaning.
    Meaning must never obey sound.
"""

from __future__ import annotations

from typing import Tuple, Optional, TYPE_CHECKING

# Maximum acoustic penalty: 5% of insight_depth
MAX_ACOUSTIC_PENALTY = 0.05

# Threshold for considering alignment as misaligned (triggers penalty)
MISALIGNMENT_THRESHOLD = 0.4

# Insight window openness thresholds
INSIGHT_COI_THRESHOLD = 0.55
INSIGHT_CSI_THRESHOLD = 0.50

# Insight mode classification thresholds
INSIGHT_DEPTH_DEEP_THRESHOLD = 0.70
INSIGHT_DEPTH_LIGHT_THRESHOLD = 0.40


# =============================================================================
# EXCEPTION CLASS
# =============================================================================


class InsightHardeningViolation(Exception):
    """
    Exception raised when Phase 32 acoustic hardening invariants are violated.

    This exception indicates a critical implementation bug where acoustic
    diagnostics have influenced the insight system in forbidden ways:
    - Increased insight_depth (INV-P32-H1 violation)
    - Opened a window that was closed (INV-P32-H4 violation)
    - Modified authoritative decisions

    This exception should NEVER be raised in production. If it is raised,
    it indicates a governance-critical bug that requires immediate attention.

    Usage:
        if adjusted_depth > base_depth:
            raise InsightHardeningViolation(
                f"INV-P32-H1 VIOLATED: adjusted={adjusted_depth} > base={base_depth}"
            )
    """

    pass


# =============================================================================
# GATE MONOTONICITY HELPER
# =============================================================================


def verify_insight_gate_monotonicity(
    base_insight_depth: float,
    adjusted_insight_depth: float,
    base_window_open: bool,
    adjusted_window_open: bool,
) -> bool:
    """
    Verify insight window gate monotonicity invariant (INV-P32-H4).

    Gate monotonicity states that acoustic adjustments can ONLY close windows,
    never open them. This means:
    - If base window is CLOSED, adjusted window MUST remain CLOSED
    - If base window is OPEN, adjusted window may stay open or close

    Since acoustic can only REDUCE insight_depth (INV-P32-H1: adjusted <= base),
    gate monotonicity is automatically satisfied when INV-P32-H1 holds.
    This helper provides explicit verification for audit purposes.

    Args:
        base_insight_depth: Insight depth before acoustic adjustment
        adjusted_insight_depth: Insight depth after acoustic adjustment
        base_window_open: Whether insight window was open before adjustment
        adjusted_window_open: Whether insight window is open after adjustment

    Returns:
        True if gate monotonicity is satisfied, False if violated

    Invariant Logic:
        - If base window is CLOSED, adjusted window MUST be CLOSED
        - Acoustic can NEVER open a closed insight window

    Example:
        >>> verify_insight_gate_monotonicity(0.35, 0.33, False, False)  # CLOSED stays CLOSED
        True
        >>> verify_insight_gate_monotonicity(0.70, 0.68, True, True)    # OPEN stays OPEN
        True
        >>> verify_insight_gate_monotonicity(0.70, 0.50, True, False)   # OPEN → CLOSED (allowed)
        True
        >>> verify_insight_gate_monotonicity(0.35, 0.60, False, True)   # CLOSED → OPEN (FORBIDDEN)
        False
    """
    # First, verify the directional constraint (INV-P32-H1)
    if adjusted_insight_depth > base_insight_depth:
        return False  # Directional violation

    # Gate monotonicity check (INV-P32-H4)
    # Forbidden: base window CLOSED but adjusted window OPEN
    if not base_window_open and adjusted_window_open:
        return False  # Gate monotonicity violation

    return True


def verify_depth_non_increase(
    base_insight_depth: float,
    adjusted_insight_depth: float,
) -> bool:
    """
    Verify that insight_depth has not increased (INV-P32-H1).

    Args:
        base_insight_depth: Insight depth before acoustic adjustment
        adjusted_insight_depth: Insight depth after acoustic adjustment

    Returns:
        True if adjusted <= base, False if violated
    """
    return adjusted_insight_depth <= base_insight_depth


def assert_insight_acoustic_safe(
    base_insight_depth: float,
    adjusted_insight_depth: float,
    base_window_open: bool,
    adjusted_window_open: bool,
) -> None:
    """
    Assert that acoustic adjustment to insight is safe (all hardening invariants hold).

    This is a convenience function for use in tests and validation code.
    It checks all Phase 32 hardening invariants and raises an exception
    if any are violated.

    Args:
        base_insight_depth: Insight depth before acoustic adjustment
        adjusted_insight_depth: Insight depth after acoustic adjustment
        base_window_open: Whether insight window was open before adjustment
        adjusted_window_open: Whether insight window is open after adjustment

    Raises:
        InsightHardeningViolation: If any invariant is violated

    Invariants Checked:
        - INV-P32-H1: adjusted_insight_depth <= base_insight_depth
        - INV-P32-H4: Gate monotonicity (CLOSED stays CLOSED)
    """
    # Check INV-P32-H1: Directional constraint
    if adjusted_insight_depth > base_insight_depth:
        raise InsightHardeningViolation(
            f"INV-P32-H1 VIOLATED: adjusted_insight_depth ({adjusted_insight_depth}) > "
            f"base_insight_depth ({base_insight_depth}). Acoustic adjustment increased insight depth."
        )

    # Check INV-P32-H4: Gate monotonicity
    if not base_window_open and adjusted_window_open:
        raise InsightHardeningViolation(
            f"INV-P32-H4 VIOLATED: Window opened from CLOSED to OPEN. "
            f"base_window_open={base_window_open}, adjusted_window_open={adjusted_window_open}. "
            f"Acoustic adjustment opened a previously closed insight window."
        )


def verify_backward_compatibility(
    result_with_acoustic: Optional[object],
    result_without_acoustic: Optional[object],
    acoustic_alignment_present: bool,
) -> bool:
    """
    Verify backward compatibility: when no acoustic input, output is identical.

    INV-P32-H3 states that when acoustic_alignment is None, the output
    must be bitwise identical to the pre-extension version.

    Args:
        result_with_acoustic: InsightWindowResult computed with acoustic extension enabled
        result_without_acoustic: InsightWindowResult computed with original formula only
        acoustic_alignment_present: Whether acoustic alignment data was provided

    Returns:
        True if backward compatibility is satisfied, False otherwise

    Note:
        When acoustic_alignment is None (acoustic_alignment_present=False),
        both values MUST be exactly equal (no floating-point drift).
    """
    if not acoustic_alignment_present:
        # When no acoustic input, results must be exactly equal
        if result_with_acoustic is None and result_without_acoustic is None:
            return True
        if result_with_acoustic is None or result_without_acoustic is None:
            return False

        # Compare key fields
        w_depth = getattr(result_with_acoustic, 'insight_depth', None)
        wo_depth = getattr(result_without_acoustic, 'insight_depth', None)
        w_open = getattr(result_with_acoustic, 'insight_window_open', None)
        wo_open = getattr(result_without_acoustic, 'insight_window_open', None)
        w_mode = getattr(result_with_acoustic, 'insight_mode', None)
        wo_mode = getattr(result_without_acoustic, 'insight_mode', None)

        return (
            w_depth == wo_depth and
            w_open == wo_open and
            w_mode == wo_mode
        )
    else:
        # When acoustic input is present, adjusted values may differ (but only downward)
        if result_with_acoustic is None and result_without_acoustic is None:
            return True
        if result_with_acoustic is None or result_without_acoustic is None:
            return False

        w_depth = getattr(result_with_acoustic, 'insight_depth', 0.0)
        wo_depth = getattr(result_without_acoustic, 'insight_depth', 0.0)

        # Adjusted depth must not exceed base depth
        return w_depth <= wo_depth


def compute_acoustic_penalty(
    alignment_score: float,
    high_pressure: bool = False,
) -> float:
    """
    Compute the acoustic penalty to apply to insight_depth.

    The penalty is computed based on the alignment score, with:
    - alignment_score >= MISALIGNMENT_THRESHOLD: no penalty (0.0)
    - alignment_score < MISALIGNMENT_THRESHOLD: linear penalty up to MAX_ACOUSTIC_PENALTY

    The penalty formula:
        if alignment_score >= 0.4:
            penalty = 0.0
        else:
            penalty = MAX_ACOUSTIC_PENALTY * (0.4 - alignment_score) / 0.4
            if high_pressure:
                penalty *= 1.0  # No additional penalty for high pressure (bounded)

    Args:
        alignment_score: Alignment score from AcousticAlignmentReport [0.0, 1.0]
        high_pressure: Whether pressure band is "high" (optional, for diagnostics)

    Returns:
        Penalty to subtract from insight_depth [0.0, MAX_ACOUSTIC_PENALTY]

    Example:
        >>> compute_acoustic_penalty(0.8)  # Well-aligned
        0.0
        >>> compute_acoustic_penalty(0.4)  # At threshold
        0.0
        >>> compute_acoustic_penalty(0.2)  # Misaligned
        0.025
        >>> compute_acoustic_penalty(0.0)  # Completely misaligned
        0.05
    """
    if alignment_score >= MISALIGNMENT_THRESHOLD:
        return 0.0

    # Linear penalty: 0.0 at threshold, MAX at 0.0
    # penalty = MAX * (threshold - score) / threshold
    penalty = MAX_ACOUSTIC_PENALTY * (MISALIGNMENT_THRESHOLD - alignment_score) / MISALIGNMENT_THRESHOLD

    # Clamp to [0.0, MAX_ACOUSTIC_PENALTY] for safety
    return max(0.0, min(penalty, MAX_ACOUSTIC_PENALTY))


# =============================================================================
# PUBLIC EXPORTS
# =============================================================================

__all__ = [
    # Exception
    "InsightHardeningViolation",
    # Verification functions
    "verify_insight_gate_monotonicity",
    "verify_depth_non_increase",
    "assert_insight_acoustic_safe",
    "verify_backward_compatibility",
    "compute_acoustic_penalty",
    # Constants
    "MAX_ACOUSTIC_PENALTY",
    "MISALIGNMENT_THRESHOLD",
    "INSIGHT_COI_THRESHOLD",
    "INSIGHT_CSI_THRESHOLD",
    "INSIGHT_DEPTH_DEEP_THRESHOLD",
    "INSIGHT_DEPTH_LIGHT_THRESHOLD",
]
