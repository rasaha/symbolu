"""
Drift Fusion Formula v1.0 - Phase 19

Deterministic, zero-LLM "drift fusion" layer that combines:
  • semantic_integrity_score (Phase 17)
  • cognitive_drift_v3 (Phase 17)
  • temporal entropy metrics (Phase 18): normalized_entropy_diff, entropy_volatility
  • coherence_fused (Phase 16)

...into higher-level diagnostic drift metrics for analytics and dashboards:
  • drift_fusion_index ∈ [0.0, 1.0] - overall drift severity
  • drift_risk_band: "low" | "moderate" | "high"
  • drift_pattern_tags: List[str] - pattern indicators

CRITICAL:
    - Zero-LLM: Pure math + rule-based logic only
    - Non-invasive: NO changes to TTOR, MLCR, mappers, Fusion, DHA, Renderer
    - Observation-only: NOT used in routing, coherence scoring, or guardrails
    - Backward-compatible: All existing behavior remains unchanged
    - Deterministic: Same input → same output
"""

from dataclasses import dataclass, field
from typing import List, Optional


@dataclass
class DriftFusionSnapshot:
    """
    Immutable snapshot of drift fusion computation.

    Fields:
        drift_fusion_index: Final drift index [0.0, 1.0] (higher = more drift)
        semantic_integrity_score: Semantic coherence/self-consistency [0.0, 1.0]
        cognitive_drift_v3: Semantic center-of-gravity drift [0.0, 1.0]
        temporal_entropy_diff: Normalized entropy difference [0.0, 1.0]
        temporal_entropy_volatility: Entropy volatility [0.0, 1.0]
        drift_risk_band: Risk classification ("low" | "moderate" | "high")
        drift_pattern_tags: List of detected drift patterns
    """

    drift_fusion_index: float
    semantic_integrity_score: Optional[float]
    cognitive_drift_v3: Optional[float]
    temporal_entropy_diff: Optional[float]
    temporal_entropy_volatility: Optional[float]
    drift_risk_band: str
    drift_pattern_tags: List[str] = field(default_factory=list)


def _clamp(value: float, min_val: float, max_val: float) -> float:
    """
    Clamp value to [min_val, max_val] range.

    Args:
        value: Value to clamp
        min_val: Minimum value
        max_val: Maximum value

    Returns:
        float: Clamped value
    """
    return max(min_val, min(max_val, value))


def compute_drift_fusion_snapshot(
    semantic_integrity_score: Optional[float],
    cognitive_drift_v3: Optional[float],
    temporal_entropy_diff: Optional[float],
    temporal_entropy_volatility: Optional[float],
    coherence_fused: Optional[float] = None,
) -> Optional[DriftFusionSnapshot]:
    """
    Compute drift fusion snapshot from input metrics.

    Combines multiple drift/integrity signals into a unified drift index
    and diagnostic tags. Purely deterministic, zero-LLM computation.

    Args:
        semantic_integrity_score: Semantic integrity [0.0, 1.0] or None
        cognitive_drift_v3: Cognitive drift [0.0, 1.0] or None
        temporal_entropy_diff: Normalized entropy diff [0.0, 1.0] or None (0.5 = neutral)
        temporal_entropy_volatility: Entropy volatility [0.0, 1.0] or None
        coherence_fused: Fused coherence score [0.0, 1.0] or None

    Returns:
        DriftFusionSnapshot or None if all inputs are None

    Formula:
        drift_fusion_index = weighted combination of:
          - inverted semantic_integrity (low integrity → high drift)
          - cognitive_drift_v3 (direct contribution)
          - temporal_entropy_volatility (instability)
          - abs(temporal_entropy_diff - 0.5) (deviation from neutral)
          - inverted coherence_fused (low coherence → drift)

    Weights:
        - cognitive_drift: 35%
        - integrity_term: 25%
        - temporal_volatility: 20%
        - entropy_shift: 15%
        - coherence_term: 5%
    """
    # Check if we have any input data
    if all(
        x is None
        for x in [
            semantic_integrity_score,
            cognitive_drift_v3,
            temporal_entropy_diff,
            temporal_entropy_volatility,
            coherence_fused,
        ]
    ):
        return None

    # Normalize/clamp inputs and handle None values
    # Semantic integrity: invert so low integrity → high drift
    integrity_term = 1.0 - _clamp(semantic_integrity_score or 0.0, 0.0, 1.0)

    # Cognitive drift: direct contribution (already normalized to [0,1])
    drift_term = _clamp(cognitive_drift_v3 or 0.0, 0.0, 1.0)

    # Temporal entropy diff: distance from neutral (0.5)
    # 0.5 = no change, 0.0 = strong decrease, 1.0 = strong increase
    temp_diff = _clamp(temporal_entropy_diff or 0.5, 0.0, 1.0)

    # Temporal volatility: direct contribution
    temp_vol = _clamp(temporal_entropy_volatility or 0.0, 0.0, 1.0)

    # Coherence fused: invert so low coherence → high drift
    coherence_term = 1.0 - _clamp(coherence_fused or 0.5, 0.0, 1.0)

    # Compute drift_fusion_index using weighted formula
    # Weights: drift(35%) + integrity(25%) + volatility(20%) + entropy_shift(15%) + coherence(5%)
    drift_fusion_index = (
        0.35 * drift_term
        + 0.25 * integrity_term
        + 0.20 * temp_vol
        + 0.15 * abs(temp_diff - 0.5)  # Distance from neutral
        + 0.05 * coherence_term
    )

    # Clamp final index to [0.0, 1.0]
    drift_fusion_index = _clamp(drift_fusion_index, 0.0, 1.0)

    # Determine drift_risk_band based on thresholds
    if drift_fusion_index < 0.30:
        drift_risk_band = "low"
    elif drift_fusion_index < 0.65:
        drift_risk_band = "moderate"
    else:
        drift_risk_band = "high"

    # Generate drift_pattern_tags based on individual metrics
    drift_pattern_tags = []

    # Semantic drift: low semantic integrity
    if semantic_integrity_score is not None and semantic_integrity_score < 0.55:
        drift_pattern_tags.append("semantic_drift")

    # Cognitive drift: high drift v3
    if cognitive_drift_v3 is not None and cognitive_drift_v3 > 0.55:
        drift_pattern_tags.append("cognitive_drift")

    # Temporal instability: high entropy volatility
    if temporal_entropy_volatility is not None and temporal_entropy_volatility > 0.55:
        drift_pattern_tags.append("temporal_instability")

    # Entropy shift: significant deviation from neutral
    if temporal_entropy_diff is not None and abs(temporal_entropy_diff - 0.5) > 0.25:
        drift_pattern_tags.append("entropy_shift")

    # Low coherence context
    if coherence_fused is not None and coherence_fused < 0.45:
        drift_pattern_tags.append("low_coherence_context")

    return DriftFusionSnapshot(
        drift_fusion_index=drift_fusion_index,
        semantic_integrity_score=semantic_integrity_score,
        cognitive_drift_v3=cognitive_drift_v3,
        temporal_entropy_diff=temporal_entropy_diff,
        temporal_entropy_volatility=temporal_entropy_volatility,
        drift_risk_band=drift_risk_band,
        drift_pattern_tags=drift_pattern_tags,
    )
