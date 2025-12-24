"""
P35 - Predictive Persona Drift Formula

Deterministic formula computation for predicting persona drift.
This module contains the locked formula implementation.

FORMULA (LOCKED):

predicted_drift_score =
    0.35 * drift_fusion_index
  + 0.25 * schema_drift
  + 0.20 * temporal_entropy_diff
  + 0.10 * (1 - coherence_v3_quality)
  + 0.10 * (1 - ucf_score)

CRITICAL CONSTRAINTS:
    - Deterministic: Same inputs -> same outputs
    - No LLM, no ML, no learning
    - No probabilistic sampling
    - Pure arithmetic operations only

INVARIANTS:
    - INV-P35-4: Deterministic math only
"""

from __future__ import annotations

from typing import List, Optional

from symbolu.core.predictive.persona_drift.drift_report import (
    W_DRIFT_FUSION_INDEX,
    W_SCHEMA_DRIFT,
    W_TEMPORAL_ENTROPY_DIFF,
    W_COHERENCE_QUALITY,
    W_UCF_SCORE,
    SCHEMA_INSTABILITY_THRESHOLD,
    TEMPORAL_ENTROPY_THRESHOLD,
    COHERENCE_DECAY_THRESHOLD,
    IDENTITY_HARMONICS_THRESHOLD,
    CROSS_SIGNAL_VOLATILITY_THRESHOLD,
)


def clamp(value: float, min_val: float = 0.0, max_val: float = 1.0) -> float:
    """
    Clamp a value to a specified range.

    Args:
        value: The value to clamp
        min_val: Minimum value (default 0.0)
        max_val: Maximum value (default 1.0)

    Returns:
        Value clamped to [min_val, max_val]
    """
    return max(min_val, min(max_val, value))


def compute_base_drift_score(
    drift_fusion_index: float,
    schema_drift: float,
    temporal_entropy_diff: float,
    coherence_v3_quality: float,
    ucf_score: float,
) -> float:
    """
    Compute the base predictive drift score using the locked formula.

    FORMULA (LOCKED):
        predicted_drift_score =
            0.35 * drift_fusion_index
          + 0.25 * schema_drift
          + 0.20 * temporal_entropy_diff
          + 0.10 * (1 - coherence_v3_quality)
          + 0.10 * (1 - ucf_score)

    All inputs are clamped to [0.0, 1.0] before computation.
    Output is clamped to [0.0, 1.0].

    Args:
        drift_fusion_index: P19 drift fusion index [0.0, 1.0]
        schema_drift: P33 schema drift [0.0, 1.0]
        temporal_entropy_diff: P18 temporal entropy diff [0.0, 1.0]
        coherence_v3_quality: P12 coherence v3 quality [0.0, 1.0]
        ucf_score: P26 UCF score [0.0, 1.0]

    Returns:
        Predicted drift score in [0.0, 1.0]
    """
    # Clamp all inputs to [0.0, 1.0]
    dfi = clamp(drift_fusion_index)
    sd = clamp(schema_drift)
    ted = clamp(temporal_entropy_diff)
    cq = clamp(coherence_v3_quality)
    ucf = clamp(ucf_score)

    # Apply the locked formula
    score = (
        W_DRIFT_FUSION_INDEX * dfi
        + W_SCHEMA_DRIFT * sd
        + W_TEMPORAL_ENTROPY_DIFF * ted
        + W_COHERENCE_QUALITY * (1.0 - cq)
        + W_UCF_SCORE * (1.0 - ucf)
    )

    # Clamp output to [0.0, 1.0]
    return clamp(score)


def compute_variance(values: List[float]) -> float:
    """
    Compute the variance of a list of values.

    Args:
        values: List of numeric values

    Returns:
        Variance of the values, or 0.0 if < 2 values
    """
    if len(values) < 2:
        return 0.0

    mean = sum(values) / len(values)
    variance = sum((v - mean) ** 2 for v in values) / len(values)
    return variance


def compute_confidence(
    historical_scores: List[float],
) -> float:
    """
    Compute confidence score from historical drift scores.

    FORMULA (LOCKED):
        confidence = 1.0 - variance(predicted_drift_score over last N snapshots)

    Clamped to [0.0, 1.0].

    Args:
        historical_scores: List of historical predicted_drift_score values

    Returns:
        Confidence score in [0.0, 1.0]
    """
    if len(historical_scores) < 2:
        # No variance possible with < 2 values, return moderate confidence
        return 0.5

    variance = compute_variance(historical_scores)
    confidence = 1.0 - variance

    return clamp(confidence)


def compute_contributing_factors(
    drift_fusion_index: Optional[float],
    schema_drift: Optional[float],
    temporal_entropy_diff: Optional[float],
    coherence_v3_quality: Optional[float],
    ucf_score: Optional[float],
    identity_harmonics_score: Optional[float],
    signal_variance: Optional[float] = None,
) -> List[str]:
    """
    Compute contributing factors based on threshold rules.

    Contributing factors are explanatory tags that indicate why
    drift is predicted, never prescribing what to do.

    RULES:
        - SCHEMA_INSTABILITY: schema_drift >= 0.50
        - TEMPORAL_ENTROPY_RISING: temporal_entropy_diff >= 0.55
        - COHERENCE_DECAY: coherence_v3_quality < 0.45
        - IDENTITY_HARMONICS_WEAKENING: identity_harmonics_score < 0.45
        - CROSS_SIGNAL_VOLATILITY: signal_variance > 0.10

    Args:
        drift_fusion_index: P19 drift fusion index
        schema_drift: P33 schema drift
        temporal_entropy_diff: P18 temporal entropy diff
        coherence_v3_quality: P12 coherence v3 quality
        ucf_score: P26 UCF score
        identity_harmonics_score: P34 identity harmonics score
        signal_variance: Variance across input signals

    Returns:
        List of contributing factor tags
    """
    factors: List[str] = []

    # SCHEMA_INSTABILITY
    if schema_drift is not None and schema_drift >= SCHEMA_INSTABILITY_THRESHOLD:
        factors.append("SCHEMA_INSTABILITY")

    # TEMPORAL_ENTROPY_RISING
    if temporal_entropy_diff is not None and temporal_entropy_diff >= TEMPORAL_ENTROPY_THRESHOLD:
        factors.append("TEMPORAL_ENTROPY_RISING")

    # COHERENCE_DECAY
    if coherence_v3_quality is not None and coherence_v3_quality < COHERENCE_DECAY_THRESHOLD:
        factors.append("COHERENCE_DECAY")

    # IDENTITY_HARMONICS_WEAKENING
    if identity_harmonics_score is not None and identity_harmonics_score < IDENTITY_HARMONICS_THRESHOLD:
        factors.append("IDENTITY_HARMONICS_WEAKENING")

    # CROSS_SIGNAL_VOLATILITY
    if signal_variance is not None and signal_variance > CROSS_SIGNAL_VOLATILITY_THRESHOLD:
        factors.append("CROSS_SIGNAL_VOLATILITY")

    return factors


def compute_signal_variance(
    drift_fusion_index: Optional[float],
    schema_drift: Optional[float],
    temporal_entropy_diff: Optional[float],
    coherence_v3_quality: Optional[float],
    ucf_score: Optional[float],
) -> float:
    """
    Compute variance across the input signals to detect cross-signal volatility.

    Args:
        drift_fusion_index: P19 drift fusion index
        schema_drift: P33 schema drift
        temporal_entropy_diff: P18 temporal entropy diff
        coherence_v3_quality: P12 coherence v3 quality
        ucf_score: P26 UCF score

    Returns:
        Variance of the signals, or 0.0 if no signals
    """
    signals = []

    # Collect available signals, inverting quality metrics to align with drift direction
    if drift_fusion_index is not None:
        signals.append(drift_fusion_index)
    if schema_drift is not None:
        signals.append(schema_drift)
    if temporal_entropy_diff is not None:
        signals.append(temporal_entropy_diff)
    if coherence_v3_quality is not None:
        # Invert quality to drift direction
        signals.append(1.0 - coherence_v3_quality)
    if ucf_score is not None:
        # Invert quality to drift direction
        signals.append(1.0 - ucf_score)

    if len(signals) < 2:
        return 0.0

    return compute_variance(signals)


# Public exports
__all__ = [
    "clamp",
    "compute_base_drift_score",
    "compute_variance",
    "compute_confidence",
    "compute_contributing_factors",
    "compute_signal_variance",
]
