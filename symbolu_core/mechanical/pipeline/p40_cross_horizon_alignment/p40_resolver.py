"""
P40 Resolver - Cross-Horizon Resonance Alignment Logic

Implements the deterministic formulas for measuring coherence alignment
between time horizons from Phase 39's multi-horizon forecasts.

FORMULAS (Deterministic):
    Step 1 - Divergence:
        divergence_index = max(horizons) - min(horizons)

    Step 2 - Alignment Score:
        alignment_score = 1.0 - divergence_index
        (Clamped to [0.0, 1.0])

    Step 3 - Alignment Band:
        alignment_score >= 0.75 -> "aligned"
        alignment_score >= 0.45 -> "strained"
        alignment_score < 0.45 -> "fragmented"

    Step 4 - Dominant Horizon:
        If exactly one horizon exceeds others by >= 0.15 -> that horizon
        Else -> "none"

    No smoothing. No correction. No averaging beyond what's stated.

CRITICAL CONSTRAINTS:
    - Deterministic: Same inputs -> same outputs
    - Read-only: Does not modify any state
    - Observer-only: Never influences gating or behavior

INVARIANTS:
    - INV-P40-1: Observer-only (no influence on any authoritative phase)
    - INV-P40-2: Deterministic (same inputs -> same outputs)
    - INV-P40-3: No forecast mutation (Phase 39 values are never changed)
    - INV-P40-4: Alignment monotonicity (greater divergence => lower alignment_score)
    - INV-P40-5: Absence-safe (missing optional inputs degrade or remain neutral, never improve)
"""

from typing import Optional

from symbolu_core.mechanical.pipeline.p40_cross_horizon_alignment.p40_schema import (
    CrossHorizonAlignment,
    AlignmentBand,
    DominantHorizon,
    DOMINANT_HORIZON_THRESHOLD,
    classify_alignment_band,
    create_alignment,
)


# =============================================================================
# Core Functions
# =============================================================================


def clamp(value: float, min_val: float = 0.0, max_val: float = 1.0) -> float:
    """
    Clamp a value to [min_val, max_val].

    Args:
        value: Value to clamp
        min_val: Minimum bound (default 0.0)
        max_val: Maximum bound (default 1.0)

    Returns:
        Clamped value
    """
    return max(min_val, min(max_val, value))


def compute_divergence_index(
    short_term: float,
    medium_term: float,
    long_term: float,
) -> float:
    """
    Compute the divergence index between horizon scores.

    Formula: divergence_index = max(horizons) - min(horizons)

    Args:
        short_term: Short-term score from P39 [0.0, 1.0]
        medium_term: Medium-term score from P39 [0.0, 1.0]
        long_term: Long-term score from P39 [0.0, 1.0]

    Returns:
        Divergence index in [0.0, 1.0]
    """
    scores = [short_term, medium_term, long_term]
    divergence = max(scores) - min(scores)
    return clamp(divergence, 0.0, 1.0)


def compute_alignment_score(divergence_index: float) -> float:
    """
    Compute the alignment score from divergence index.

    Formula: alignment_score = 1.0 - divergence_index

    INV-P40-4: Greater divergence => lower alignment_score (monotonic relationship)

    Args:
        divergence_index: Divergence metric [0.0, 1.0]

    Returns:
        Alignment score in [0.0, 1.0]
    """
    return clamp(1.0 - divergence_index, 0.0, 1.0)


def determine_dominant_horizon(
    short_term: float,
    medium_term: float,
    long_term: float,
) -> DominantHorizon:
    """
    Determine which horizon dominates, if any.

    A horizon is dominant if it exceeds ALL other horizons by >= 0.15.
    If no single horizon dominates, return "none".

    Args:
        short_term: Short-term score from P39 [0.0, 1.0]
        medium_term: Medium-term score from P39 [0.0, 1.0]
        long_term: Long-term score from P39 [0.0, 1.0]

    Returns:
        "short", "medium", "long", or "none"
    """
    threshold = DOMINANT_HORIZON_THRESHOLD

    # Check if short_term dominates
    if (
        short_term - medium_term >= threshold
        and short_term - long_term >= threshold
    ):
        return "short"

    # Check if medium_term dominates
    if (
        medium_term - short_term >= threshold
        and medium_term - long_term >= threshold
    ):
        return "medium"

    # Check if long_term dominates
    if (
        long_term - short_term >= threshold
        and long_term - medium_term >= threshold
    ):
        return "long"

    # No single horizon dominates
    return "none"


def resolve_cross_horizon_alignment(
    short_term_score: Optional[float] = None,
    medium_term_score: Optional[float] = None,
    long_term_score: Optional[float] = None,
    drift_fusion_index: Optional[float] = None,
    temporal_entropy_diff: Optional[float] = None,
) -> Optional[CrossHorizonAlignment]:
    """
    Resolve the cross-horizon alignment from input signals.

    This is the main resolver function that:
    1. Validates mandatory inputs (all three horizon scores from P39)
    2. Computes divergence_index = max(horizons) - min(horizons)
    3. Computes alignment_score = 1.0 - divergence_index
    4. Classifies alignment band
    5. Determines dominant horizon
    6. Returns immutable alignment report

    INV-P40-2: Deterministic - same inputs always produce same outputs.
    INV-P40-3: P39 values are read but never modified.
    INV-P40-4: Greater divergence => lower alignment_score.
    INV-P40-5: Missing optional inputs (P18, P19) do not inflate alignment.

    Args:
        short_term_score: P39 short-term score [0.0, 1.0] (REQUIRED)
        medium_term_score: P39 medium-term score [0.0, 1.0] (REQUIRED)
        long_term_score: P39 long-term score [0.0, 1.0] (REQUIRED)
        drift_fusion_index: P19 drift fusion index [0.0, 1.0] (optional, for observability)
        temporal_entropy_diff: P18 temporal entropy diff [0.0, 1.0] (optional, for observability)

    Returns:
        CrossHorizonAlignment if computation possible, None if
        any required horizon score is missing
    """
    # All three horizon scores are mandatory
    if short_term_score is None:
        return None
    if medium_term_score is None:
        return None
    if long_term_score is None:
        return None

    # Step 1: Compute divergence index
    divergence_index = compute_divergence_index(
        short_term=short_term_score,
        medium_term=medium_term_score,
        long_term=long_term_score,
    )

    # Step 2: Compute alignment score (INV-P40-4: monotonic relationship)
    alignment_score = compute_alignment_score(divergence_index)

    # Step 3: Classify alignment band
    alignment_band = classify_alignment_band(alignment_score)

    # Step 4: Determine dominant horizon
    dominant_horizon = determine_dominant_horizon(
        short_term=short_term_score,
        medium_term=medium_term_score,
        long_term=long_term_score,
    )

    # Build debug info
    debug = {
        "computation": {
            "divergence_formula": "max(horizons) - min(horizons)",
            "alignment_formula": "1.0 - divergence_index",
            "dominant_threshold": DOMINANT_HORIZON_THRESHOLD,
        },
        "horizon_values": {
            "short_term": short_term_score,
            "medium_term": medium_term_score,
            "long_term": long_term_score,
            "max": max(short_term_score, medium_term_score, long_term_score),
            "min": min(short_term_score, medium_term_score, long_term_score),
        },
        "optional_inputs_present": {
            "drift_fusion_index": drift_fusion_index is not None,
            "temporal_entropy_diff": temporal_entropy_diff is not None,
        },
    }

    return create_alignment(
        alignment_score=alignment_score,
        alignment_band=alignment_band,
        divergence_index=divergence_index,
        dominant_horizon=dominant_horizon,
        short_term_score=short_term_score,
        medium_term_score=medium_term_score,
        long_term_score=long_term_score,
        drift_fusion_index=drift_fusion_index,
        temporal_entropy_diff=temporal_entropy_diff,
        debug=debug,
    )


# Public exports
__all__ = [
    # Core functions
    "clamp",
    "compute_divergence_index",
    "compute_alignment_score",
    "determine_dominant_horizon",
    "resolve_cross_horizon_alignment",
]
