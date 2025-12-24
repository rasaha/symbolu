"""
Phase 48: Macro-Stability Regime Analyzer

Core regime classification engine with deterministic logic.

Phase 48 answers:
    "What kind of long-range stability regime is the system currently in?"

This is classification, not prediction, not action, not gating.

INPUTS (Read-Only):
    Phase 48 MAY read:
        - ctx.p45_multi_trajectory_stability (stability_index, trajectory_count)
        - ctx.p46_trajectory_convergence (convergence_score, field_state)
        - ctx.p47_unified_trajectory_scenario (alignment_score, alignment_band)

    Phase 48 MUST NOT read:
        - Regime (P6)
        - Discourse / semantics / lexical phases
        - Acoustic / vrtti / kosha observers
        - Governance phases (>=50)
        - Renderer or persona layers

INVARIANTS:
    INV-P48-1: Classification-only (no numeric synthesis beyond confidence)
    INV-P48-2: No future selection (no path choice, no ranking)
    INV-P48-3: Deterministic (pure rule + arithmetic)
    INV-P48-4: Observer-only (cannot influence authority layers)
    INV-P48-5: Absence-safe (missing input -> None)
"""

from __future__ import annotations

from typing import Any, Optional

from .p48_schema import (
    MacroRegime,
    MacroStabilityRegimeReport,
    create_macro_stability_report,
)


# ============================================================================
# CLASSIFICATION THRESHOLDS
# ============================================================================

# Stability thresholds (T = stability_index from P45)
T_HIGH = 0.70  # Stable threshold
T_LOW = 0.45   # Chaotic threshold

# Convergence thresholds (C = convergence_score from P46)
C_HIGH = 0.65  # For stable_convergent
C_MED = 0.60   # For fragile_convergent
C_LOW = 0.45   # For stable_divergent / chaotic

# Alignment thresholds (A = alignment_score from P47)
A_HIGH = 0.65  # For stable_convergent
A_MED = 0.50   # For fragile_convergent


# ============================================================================
# REGIME CLASSIFICATION
# ============================================================================


def _classify_macro_regime(
    stability_index: float,
    convergence_score: float,
    alignment_score: float,
) -> MacroRegime:
    """
    Classify macro regime based on deterministic rules.

    INV-P48-1: Classification-only - returns a category, not a score.
    INV-P48-2: No future selection - just categorization.
    INV-P48-3: Deterministic - pure rule application.

    Rules are applied in order (first match wins):
        1. Stable Convergent: T >= 0.70 AND C >= 0.65 AND A >= 0.65
        2. Stable Divergent:  T >= 0.70 AND C < 0.45
        3. Fragile Convergent: T < 0.70 AND C >= 0.60 AND A >= 0.50
        4. Chaotic: T < 0.45 AND C < 0.45
        5. Indeterminate: else

    Args:
        stability_index: T from P45 [0.0, 1.0]
        convergence_score: C from P46 [0.0, 1.0]
        alignment_score: A from P47 [0.0, 1.0]

    Returns:
        MacroRegime classification
    """
    T = stability_index
    C = convergence_score
    A = alignment_score

    # Rule 1: Stable Convergent
    if T >= T_HIGH and C >= C_HIGH and A >= A_HIGH:
        return "stable_convergent"

    # Rule 2: Stable Divergent
    if T >= T_HIGH and C < C_LOW:
        return "stable_divergent"

    # Rule 3: Fragile Convergent
    if T < T_HIGH and C >= C_MED and A >= A_MED:
        return "fragile_convergent"

    # Rule 4: Chaotic
    if T < T_LOW and C < C_LOW:
        return "chaotic"

    # Rule 5: Indeterminate (default)
    return "indeterminate"


def _compute_confidence(
    stability_index: float,
    convergence_score: float,
    alignment_score: float,
) -> float:
    """
    Compute confidence reflecting how far inputs are from ambiguity.

    INV-P48-3: Deterministic - pure arithmetic, no smoothing, no history.

    Formula:
        confidence = clamp(
            (abs(T - 0.5) + abs(C - 0.5) + abs(A - 0.5)) / 1.5,
            0.0,
            1.0
        )

    Args:
        stability_index: T from P45 [0.0, 1.0]
        convergence_score: C from P46 [0.0, 1.0]
        alignment_score: A from P47 [0.0, 1.0]

    Returns:
        Confidence score in [0.0, 1.0]
    """
    T = stability_index
    C = convergence_score
    A = alignment_score

    # Distance from ambiguity (0.5 is most ambiguous)
    distance_sum = abs(T - 0.5) + abs(C - 0.5) + abs(A - 0.5)

    # Normalize by maximum possible distance (1.5 when all at extremes)
    confidence = distance_sum / 1.5

    # Clamp to [0.0, 1.0]
    return max(0.0, min(1.0, confidence))


# ============================================================================
# ENTRY POINTS
# ============================================================================


def compute_macro_stability_regime(
    stability_index: float,
    convergence_score: float,
    alignment_score: float,
) -> MacroStabilityRegimeReport:
    """
    Compute macro-stability regime classification from raw inputs.

    INV-P48-1: Classification-only - categorizes regime, confidence is derived.
    INV-P48-2: No future selection - no ranking or path choice.
    INV-P48-3: Deterministic - same inputs always produce same output.
    INV-P48-4: Observer-only - creates report with observer_only=True.

    Args:
        stability_index: T from P45 [0.0, 1.0]
        convergence_score: C from P46 [0.0, 1.0]
        alignment_score: A from P47 [0.0, 1.0]

    Returns:
        MacroStabilityRegimeReport
    """
    # Classify regime
    macro_regime = _classify_macro_regime(
        stability_index=stability_index,
        convergence_score=convergence_score,
        alignment_score=alignment_score,
    )

    # Compute confidence
    confidence = _compute_confidence(
        stability_index=stability_index,
        convergence_score=convergence_score,
        alignment_score=alignment_score,
    )

    # Create report with debug info
    debug = {
        "inputs": {
            "T": stability_index,
            "C": convergence_score,
            "A": alignment_score,
        },
        "thresholds": {
            "T_HIGH": T_HIGH,
            "T_LOW": T_LOW,
            "C_HIGH": C_HIGH,
            "C_MED": C_MED,
            "C_LOW": C_LOW,
            "A_HIGH": A_HIGH,
            "A_MED": A_MED,
        },
    }

    return create_macro_stability_report(
        macro_regime=macro_regime,
        confidence=confidence,
        debug=debug,
    )


def run_p48_directly(
    p45_multi_trajectory_stability: Any,
    p46_trajectory_convergence: Any,
    p47_unified_trajectory_scenario: Any,
) -> Optional[MacroStabilityRegimeReport]:
    """
    Run P48 regime analyzer directly with upstream reports.

    This is the direct computation entry point for testing and
    bypassing context extraction.

    INV-P48-5: Absence-safe - returns None if any input is missing or invalid.

    Args:
        p45_multi_trajectory_stability: P45 report (needs stability_index)
        p46_trajectory_convergence: P46 report (needs convergence_score)
        p47_unified_trajectory_scenario: P47 report (needs alignment_score)

    Returns:
        MacroStabilityRegimeReport if all inputs valid, None otherwise
    """
    # INV-P48-5: Guard against missing inputs
    if p45_multi_trajectory_stability is None:
        return None
    if p46_trajectory_convergence is None:
        return None
    if p47_unified_trajectory_scenario is None:
        return None

    # Extract required fields with safe getattr
    stability_index = getattr(p45_multi_trajectory_stability, "stability_index", None)
    convergence_score = getattr(p46_trajectory_convergence, "convergence_score", None)
    alignment_score = getattr(p47_unified_trajectory_scenario, "alignment_score", None)

    # INV-P48-5: Guard against missing fields
    if stability_index is None:
        return None
    if convergence_score is None:
        return None
    if alignment_score is None:
        return None

    # Run classification
    return compute_macro_stability_regime(
        stability_index=stability_index,
        convergence_score=convergence_score,
        alignment_score=alignment_score,
    )
