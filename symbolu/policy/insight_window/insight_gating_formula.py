"""
Phase 32 - Insight Gating Formula (LOCKED)

This module contains the locked formula for computing insight depth.
The formula and weights are immutable and must not be modified.

CORE FORMULA (LOCKED):
    raw_depth =
        0.40 * coherence_v3_quality
      + 0.30 * ucf_score
      + 0.20 * schema_stability
      + 0.10 * (1 - drift_fusion_index)

MONOTONIC PENALTIES (LOCKED):
    - If temporal_entropy_diff > 0.6 → multiply by 0.85
    - If coherence_v3_quality < 0.45 → multiply by 0.80
    - If acoustic_alignment_score < 0.4 → multiply by 0.95 (observer-only)

CRITICAL INVARIANTS:
- INV-P32-1: Insight gating never opens due to observers
- INV-P32-2: Gate monotonicity enforced (penalties can only reduce depth)
- INV-P32-3: No upstream influence
- INV-P32-4: Deterministic behavior

Design Principle:
    Sound must obey meaning.
    Meaning must never obey sound.
    Penalties can ONLY reduce depth, NEVER increase it.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import List, Optional, Tuple


# ============================================================================
# FORMULA WEIGHTS (LOCKED - DO NOT MODIFY)
# ============================================================================

# Core depth weights (MUST sum to 1.0)
W_COHERENCE_V3_QUALITY = 0.40
W_UCF_SCORE = 0.30
W_SCHEMA_STABILITY = 0.20
W_DRIFT_INVERSE = 0.10

# Verify weights sum to 1.0
_WEIGHT_SUM = W_COHERENCE_V3_QUALITY + W_UCF_SCORE + W_SCHEMA_STABILITY + W_DRIFT_INVERSE
assert abs(_WEIGHT_SUM - 1.0) < 1e-9, f"Weights must sum to 1.0, got {_WEIGHT_SUM}"


# ============================================================================
# PENALTY THRESHOLDS (LOCKED - DO NOT MODIFY)
# ============================================================================

# Temporal entropy penalty threshold
TEMPORAL_ENTROPY_THRESHOLD = 0.6
TEMPORAL_ENTROPY_PENALTY = 0.85  # Multiply by this (15% reduction)

# Coherence quality penalty threshold
COHERENCE_QUALITY_THRESHOLD = 0.45
COHERENCE_QUALITY_PENALTY = 0.80  # Multiply by this (20% reduction)

# Acoustic alignment penalty threshold (observer-only)
ACOUSTIC_ALIGNMENT_THRESHOLD = 0.4
ACOUSTIC_ALIGNMENT_PENALTY = 0.95  # Multiply by this (5% reduction)


# ============================================================================
# NEUTRAL DEFAULTS (LOCKED)
# ============================================================================

# Default value when inputs are missing
NEUTRAL_DEFAULT = 0.5


# ============================================================================
# FORMULA RESULT
# ============================================================================


@dataclass
class FormulaResult:
    """
    Result of the insight gating formula computation.

    Attributes:
        raw_depth: Depth before penalties [0.0, 1.0]
        final_depth: Depth after penalties [0.0, 1.0]
        penalties_applied: List of penalty descriptions
        reason_codes: List of reason codes for gating tightening
        inputs_used: Dictionary of input values used in computation
    """
    raw_depth: float
    final_depth: float
    penalties_applied: List[str]
    reason_codes: List[str]
    inputs_used: dict


# ============================================================================
# FORMULA FUNCTIONS (LOCKED)
# ============================================================================


def _clamp(value: float, min_val: float = 0.0, max_val: float = 1.0) -> float:
    """Clamp value to [min_val, max_val] range."""
    return max(min_val, min(max_val, value))


def _safe_value(value: Optional[float], default: float = NEUTRAL_DEFAULT) -> float:
    """Return value if valid, otherwise return default."""
    if value is None or not isinstance(value, (int, float)):
        return default
    return _clamp(float(value))


def compute_raw_depth(
    coherence_v3_quality: Optional[float],
    ucf_score: Optional[float],
    schema_stability: Optional[float],
    drift_fusion_index: Optional[float],
) -> Tuple[float, dict]:
    """
    Compute raw insight depth using the LOCKED formula.

    Formula:
        raw_depth =
            0.40 * coherence_v3_quality
          + 0.30 * ucf_score
          + 0.20 * schema_stability
          + 0.10 * (1 - drift_fusion_index)

    Args:
        coherence_v3_quality: P10/P12 coherence v3 quality [0.0, 1.0]
        ucf_score: P26 unified consciousness formula score [0.0, 1.0]
        schema_stability: P33 schema stability score [0.0, 1.0]
        drift_fusion_index: P19 drift fusion index [0.0, 1.0]

    Returns:
        Tuple of (raw_depth, inputs_used_dict)
    """
    # Safe extraction with defaults
    coh_q = _safe_value(coherence_v3_quality)
    ucf = _safe_value(ucf_score)
    schema = _safe_value(schema_stability)
    drift = _safe_value(drift_fusion_index)

    # Compute raw depth using LOCKED formula
    raw_depth = (
        W_COHERENCE_V3_QUALITY * coh_q
        + W_UCF_SCORE * ucf
        + W_SCHEMA_STABILITY * schema
        + W_DRIFT_INVERSE * (1.0 - drift)
    )

    # Clamp to valid range
    raw_depth = _clamp(raw_depth)

    inputs_used = {
        "coherence_v3_quality": coh_q,
        "ucf_score": ucf,
        "schema_stability": schema,
        "drift_fusion_index": drift,
    }

    return raw_depth, inputs_used


def apply_temporal_entropy_penalty(
    depth: float,
    temporal_entropy_diff: Optional[float],
) -> Tuple[float, Optional[str], Optional[str]]:
    """
    Apply temporal entropy penalty if threshold exceeded.

    Penalty Rule (LOCKED):
        If temporal_entropy_diff > 0.6 → multiply by 0.85

    Args:
        depth: Current depth value
        temporal_entropy_diff: P18 temporal entropy differential [0.0, 1.0]

    Returns:
        Tuple of (adjusted_depth, penalty_description, reason_code)
    """
    if temporal_entropy_diff is None:
        return depth, None, None

    entropy = _safe_value(temporal_entropy_diff)

    if entropy > TEMPORAL_ENTROPY_THRESHOLD:
        adjusted = depth * TEMPORAL_ENTROPY_PENALTY
        return (
            _clamp(adjusted),
            f"temporal_entropy:{entropy:.3f}>0.6→*0.85",
            "HIGH_TEMPORAL_ENTROPY",
        )

    return depth, None, None


def apply_coherence_quality_penalty(
    depth: float,
    coherence_v3_quality: Optional[float],
) -> Tuple[float, Optional[str], Optional[str]]:
    """
    Apply coherence quality penalty if below threshold.

    Penalty Rule (LOCKED):
        If coherence_v3_quality < 0.45 → multiply by 0.80

    Args:
        depth: Current depth value
        coherence_v3_quality: P10/P12 coherence v3 quality [0.0, 1.0]

    Returns:
        Tuple of (adjusted_depth, penalty_description, reason_code)
    """
    if coherence_v3_quality is None:
        # Missing coherence is treated as low coherence
        adjusted = depth * COHERENCE_QUALITY_PENALTY
        return (
            _clamp(adjusted),
            "coherence_v3_quality:missing→*0.80",
            "LOW_COHERENCE_QUALITY",
        )

    coh_q = _safe_value(coherence_v3_quality)

    if coh_q < COHERENCE_QUALITY_THRESHOLD:
        adjusted = depth * COHERENCE_QUALITY_PENALTY
        return (
            _clamp(adjusted),
            f"coherence_v3_quality:{coh_q:.3f}<0.45→*0.80",
            "LOW_COHERENCE_QUALITY",
        )

    return depth, None, None


def apply_acoustic_penalty(
    depth: float,
    acoustic_alignment_score: Optional[float],
) -> Tuple[float, Optional[str], Optional[str]]:
    """
    Apply acoustic alignment penalty if below threshold (OBSERVER-ONLY).

    Penalty Rule (LOCKED):
        If acoustic_alignment_score < 0.4 → multiply by 0.95

    CRITICAL: This penalty is observer-only. Acoustic input can ONLY
    reduce depth, NEVER increase it. When acoustic_alignment is None,
    no penalty is applied (backward compatibility).

    Args:
        depth: Current depth value
        acoustic_alignment_score: Acoustic alignment score [0.0, 1.0]

    Returns:
        Tuple of (adjusted_depth, penalty_description, reason_code)
    """
    # INV-P32-H3: When acoustic_alignment is None, no adjustment
    if acoustic_alignment_score is None:
        return depth, None, None

    alignment = _safe_value(acoustic_alignment_score)

    if alignment < ACOUSTIC_ALIGNMENT_THRESHOLD:
        adjusted = depth * ACOUSTIC_ALIGNMENT_PENALTY
        return (
            _clamp(adjusted),
            f"acoustic_alignment:{alignment:.3f}<0.4→*0.95",
            "ACOUSTIC_MISALIGNMENT",
        )

    return depth, None, None


def compute_insight_depth(
    coherence_v3_quality: Optional[float],
    ucf_score: Optional[float],
    schema_stability: Optional[float],
    drift_fusion_index: Optional[float],
    temporal_entropy_diff: Optional[float],
    acoustic_alignment_score: Optional[float] = None,
) -> FormulaResult:
    """
    Compute insight depth using the LOCKED formula and penalties.

    This is the main entry point for the insight gating formula.

    CORE FORMULA (LOCKED):
        raw_depth =
            0.40 * coherence_v3_quality
          + 0.30 * ucf_score
          + 0.20 * schema_stability
          + 0.10 * (1 - drift_fusion_index)

    MONOTONIC PENALTIES (LOCKED):
        - If temporal_entropy_diff > 0.6 → multiply by 0.85
        - If coherence_v3_quality < 0.45 → multiply by 0.80
        - If acoustic_alignment_score < 0.4 → multiply by 0.95 (observer-only)

    Args:
        coherence_v3_quality: P10/P12 coherence v3 quality [0.0, 1.0]
        ucf_score: P26 unified consciousness formula score [0.0, 1.0]
        schema_stability: P33 schema stability score [0.0, 1.0]
        drift_fusion_index: P19 drift fusion index [0.0, 1.0]
        temporal_entropy_diff: P18 temporal entropy differential [0.0, 1.0]
        acoustic_alignment_score: Optional acoustic alignment [0.0, 1.0]

    Returns:
        FormulaResult with raw_depth, final_depth, and penalty details
    """
    penalties_applied: List[str] = []
    reason_codes: List[str] = []

    # Step 1: Compute raw depth
    raw_depth, inputs_used = compute_raw_depth(
        coherence_v3_quality=coherence_v3_quality,
        ucf_score=ucf_score,
        schema_stability=schema_stability,
        drift_fusion_index=drift_fusion_index,
    )

    # Store temporal_entropy_diff in inputs
    inputs_used["temporal_entropy_diff"] = _safe_value(temporal_entropy_diff) if temporal_entropy_diff is not None else None
    inputs_used["acoustic_alignment_score"] = acoustic_alignment_score

    # Step 2: Apply monotonic penalties (order matters for determinism)
    current_depth = raw_depth

    # Penalty 1: Temporal entropy
    current_depth, penalty, code = apply_temporal_entropy_penalty(
        current_depth, temporal_entropy_diff
    )
    if penalty:
        penalties_applied.append(penalty)
    if code:
        reason_codes.append(code)

    # Penalty 2: Coherence quality
    current_depth, penalty, code = apply_coherence_quality_penalty(
        current_depth, coherence_v3_quality
    )
    if penalty:
        penalties_applied.append(penalty)
    if code:
        reason_codes.append(code)

    # Penalty 3: Acoustic alignment (observer-only)
    current_depth, penalty, code = apply_acoustic_penalty(
        current_depth, acoustic_alignment_score
    )
    if penalty:
        penalties_applied.append(penalty)
    if code:
        reason_codes.append(code)

    # Final clamp
    final_depth = _clamp(current_depth)

    # INV-P32-2: Verify monotonicity
    assert final_depth <= raw_depth + 1e-9, (
        f"Monotonicity violated: final_depth ({final_depth}) > raw_depth ({raw_depth})"
    )

    return FormulaResult(
        raw_depth=raw_depth,
        final_depth=final_depth,
        penalties_applied=penalties_applied,
        reason_codes=reason_codes,
        inputs_used=inputs_used,
    )


# Public exports
__all__ = [
    # Weights (LOCKED)
    "W_COHERENCE_V3_QUALITY",
    "W_UCF_SCORE",
    "W_SCHEMA_STABILITY",
    "W_DRIFT_INVERSE",
    # Thresholds (LOCKED)
    "TEMPORAL_ENTROPY_THRESHOLD",
    "TEMPORAL_ENTROPY_PENALTY",
    "COHERENCE_QUALITY_THRESHOLD",
    "COHERENCE_QUALITY_PENALTY",
    "ACOUSTIC_ALIGNMENT_THRESHOLD",
    "ACOUSTIC_ALIGNMENT_PENALTY",
    "NEUTRAL_DEFAULT",
    # Result type
    "FormulaResult",
    # Functions
    "compute_raw_depth",
    "apply_temporal_entropy_penalty",
    "apply_coherence_quality_penalty",
    "apply_acoustic_penalty",
    "compute_insight_depth",
]
