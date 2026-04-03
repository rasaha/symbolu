"""
Coherence–Scenario Alignment Engine (CSAE) v1.0 - Phase 44

Deterministic, zero-LLM, observation-only engine that assesses alignment between:
- Phase 38/39 temporal coherence forecasts
- Phase 42 scenario fusion signals
- Phase 37 identity continuity signals (ACE)
- Phase 34/36 identity stability signals

CRITICAL INVARIANTS:
    - Zero-LLM: Purely rule-based, deterministic math only
    - Observation-only: NO changes to routing, TTOR, MLCR, mappers, Fusion, DHA, Renderer
    - Diagnostics/UI only: Feeds coherence state, session summary, unified API, and DILchat badges
    - Non-invasive: Does not modify any existing coherence formulas or behaviors
    - Backward-compatible: All existing tests remain green
    - Deterministic: Same inputs → same outputs always
    - Fully bounded: All outputs [0.0, 1.0] where applicable
    - Graceful degradation: Returns None if insufficient data
"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any
import math


@dataclass
class CoherenceScenarioAlignmentSnapshot:
    """
    Immutable snapshot of coherence–scenario alignment computation.

    This snapshot measures how well temporal forecasts, scenario fusion paths,
    and identity continuity signals align with each other.

    Fields:
        alignment_score: [0.0, 1.0] - overall alignment across horizons and signals
        conflict_index: [0.0, 1.0] - degree of contradiction between signals
        stability_agreement: [0.0, 1.0] - agreement between forecast stability and identity continuity
        overall_alignment_band: "high" | "medium" | "low" | "conflict"
        diagnostic_tags: Pattern indicators (e.g., "alignment_coherence_rising")
        inputs_used: Debug information about what inputs were available
    """

    alignment_score: Optional[float] = None
    conflict_index: Optional[float] = None
    stability_agreement: Optional[float] = None
    overall_alignment_band: Optional[str] = None
    diagnostic_tags: List[str] = field(default_factory=list)
    inputs_used: Dict[str, Any] = field(default_factory=dict)


def _clamp(value: float, min_val: float = 0.0, max_val: float = 1.0) -> float:
    """
    Clamp value to [min_val, max_val] range.

    Args:
        value: Value to clamp
        min_val: Minimum value (default 0.0)
        max_val: Maximum value (default 1.0)

    Returns:
        float: Clamped value
    """
    return max(min_val, min(max_val, value))


def _safe_get_float(data: Optional[Any], key: str, default: float = 0.0) -> float:
    """
    Safely extract float value from dict or object.

    Args:
        data: Data object (dict or object with attributes)
        key: Key/attribute name
        default: Default value if not found

    Returns:
        float: Extracted value or default
    """
    if data is None:
        return default

    # Try dict access
    if isinstance(data, dict):
        value = data.get(key, default)
    # Try attribute access
    elif hasattr(data, key):
        value = getattr(data, key, default)
    else:
        return default

    # Ensure numeric
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return float(value)

    return default


def _safe_get_str(data: Optional[Any], key: str, default: Optional[str] = None) -> Optional[str]:
    """
    Safely extract string value from dict or object.

    Args:
        data: Data object (dict or object with attributes)
        key: Key/attribute name
        default: Default value if not found

    Returns:
        str or None: Extracted value or default
    """
    if data is None:
        return default

    # Try dict access
    if isinstance(data, dict):
        value = data.get(key, default)
    # Try attribute access
    elif hasattr(data, key):
        value = getattr(data, key, default)
    else:
        return default

    return value if isinstance(value, str) else default


def compute_coherence_scenario_alignment(
    *,
    # Phase 38 - Temporal Coherence Forecasting
    forecast_coherence_slope: Optional[float] = None,
    forecast_continuity_slope: Optional[float] = None,
    forecast_drift_influence: Optional[float] = None,
    forecast_entropy_forward_risk: Optional[float] = None,
    forecast_strength: Optional[float] = None,
    forecast_band: Optional[str] = None,
    # Phase 39 - Multi-Horizon Forecasting
    horizon_slope_H1: Optional[float] = None,
    horizon_slope_H2: Optional[float] = None,
    horizon_slope_H3: Optional[float] = None,
    forecast_consensus_index: Optional[float] = None,
    future_stability_envelope: Optional[float] = None,
    # Phase 42 - Scenario Fusion Engine
    scenario_alignment_score: Optional[float] = None,
    scenario_divergence_index: Optional[float] = None,
    dominant_future_path: Optional[str] = None,
    future_uncertainty_band: Optional[str] = None,
    # Phase 37 - Adaptive Continuity Engine (ACE)
    icc: Optional[float] = None,  # Identity Continuity Coefficient
    ncc: Optional[float] = None,  # Narrative Continuity Coefficient
    css: Optional[float] = None,  # Continuity Stability Score
    # Phase 34 - Identity Harmonics
    cih: Optional[float] = None,  # Core Identity Harmonic
    # Phase 26 - Unified Consciousness Formula
    csi: Optional[float] = None,  # Consciousness Stability Index
) -> Optional[CoherenceScenarioAlignmentSnapshot]:
    """
    Compute Coherence–Scenario Alignment Engine v1.0.

    This function assesses alignment between:
      - Temporal forecasts (Phase 38/39)
      - Scenario fusion signals (Phase 42)
      - Identity continuity signals (Phase 37)
      - Identity/consciousness stability (Phase 34/26)

    Args:
        forecast_coherence_slope: Coherence trajectory slope from Phase 38 [-1.0, 1.0]
        forecast_continuity_slope: Continuity trajectory slope from Phase 38 [-1.0, 1.0]
        forecast_drift_influence: Drift influence on forecast from Phase 38 [0.0, 1.0]
        forecast_entropy_forward_risk: Forward entropy risk from Phase 38 [0.0, 1.0]
        forecast_strength: Forecast confidence from Phase 38 [0.0, 1.0]
        forecast_band: Forecast band from Phase 38
        horizon_slope_H1: H1 coherence slope from Phase 39 [-1.0, 1.0]
        horizon_slope_H2: H2 coherence slope from Phase 39 [-1.0, 1.0]
        horizon_slope_H3: H3 coherence slope from Phase 39 [-1.0, 1.0]
        forecast_consensus_index: Forecast consensus from Phase 39 [0.0, 1.0]
        future_stability_envelope: Future stability from Phase 39 [0.0, 1.0]
        scenario_alignment_score: Scenario alignment from Phase 42 [0.0, 1.0]
        scenario_divergence_index: Scenario divergence from Phase 42 [0.0, 1.0]
        dominant_future_path: Dominant scenario path from Phase 42
        future_uncertainty_band: Future uncertainty from Phase 42
        icc: Identity Continuity Coefficient from Phase 37 [0.0, 1.0]
        ncc: Narrative Continuity Coefficient from Phase 37 [0.0, 1.0]
        css: Continuity Stability Score from Phase 37 [0.0, 1.0]
        cih: Core Identity Harmonic from Phase 34 [0.0, 1.0]
        csi: Consciousness Stability Index from Phase 26 [0.0, 1.0]

    Returns:
        CoherenceScenarioAlignmentSnapshot or None if insufficient data

    Formula Design:
        - alignment_score: Weighted combination of:
            * Coherence slope consistency (Phase 38/39)
            * Scenario alignment (Phase 42)
            * ICC support (Phase 37)
            * Future stability (Phase 39 FSE)
            * Uncertainty inverse weighting
        - conflict_index: Based on:
            * Drift influence high
            * Entropy forward risk high
            * Slope direction contradicts scenario path
            * Scenario divergence high
        - stability_agreement: Agreement between:
            * Phase 39 long-term forecasts
            * Identity continuity (ACE)
            * Consciousness stability (UCF)
        - overall_alignment_band:
            * HIGH: alignment_score >= 0.70
            * MEDIUM: alignment_score >= 0.45
            * LOW: alignment_score >= 0.25
            * CONFLICT: alignment_score < 0.25

    Graceful Degradation:
        Returns None if insufficient critical inputs are available.
    """
    # ========================================================================
    # STEP 1: VALIDATE INPUT AND TRACK AVAILABILITY
    # ========================================================================

    inputs_used = {}

    # Count available inputs from each phase
    phase38_available = sum([
        forecast_coherence_slope is not None,
        forecast_continuity_slope is not None,
        forecast_drift_influence is not None,
        forecast_entropy_forward_risk is not None,
        forecast_strength is not None,
    ])

    phase39_available = sum([
        horizon_slope_H1 is not None,
        horizon_slope_H2 is not None,
        horizon_slope_H3 is not None,
        forecast_consensus_index is not None,
        future_stability_envelope is not None,
    ])

    phase42_available = sum([
        scenario_alignment_score is not None,
        scenario_divergence_index is not None,
    ])

    phase37_available = sum([
        icc is not None,
        ncc is not None,
        css is not None,
    ])

    phase34_26_available = sum([
        cih is not None,
        csi is not None,
    ])

    inputs_used["phase38_available"] = phase38_available
    inputs_used["phase39_available"] = phase39_available
    inputs_used["phase42_available"] = phase42_available
    inputs_used["phase37_available"] = phase37_available
    inputs_used["phase34_26_available"] = phase34_26_available

    # Need at least 2 phases with some data to compute alignment
    phases_with_data = sum([
        phase38_available > 0,
        phase39_available > 0,
        phase42_available > 0,
        phase37_available > 0,
    ])

    if phases_with_data < 2:
        return None

    # ========================================================================
    # STEP 2: COMPUTE ALIGNMENT SCORE
    # ========================================================================

    # Alignment score is weighted combination of multiple signals
    alignment_components = []
    alignment_weights = []

    # Component 1: Coherence Slope Consistency (Phase 38/39)
    # Positive slopes indicate rising coherence → better alignment
    if forecast_coherence_slope is not None:
        # Map [-1, 1] → [0, 1] where positive slope = high alignment
        slope_alignment = _clamp((forecast_coherence_slope + 1.0) / 2.0, 0.0, 1.0)
        alignment_components.append(slope_alignment)
        alignment_weights.append(0.20)
        inputs_used["coherence_slope_used"] = True

    # Component 2: Multi-Horizon Slope Agreement
    # If all horizons agree on direction → better alignment
    if horizon_slope_H1 is not None and horizon_slope_H2 is not None and horizon_slope_H3 is not None:
        # Compute average slope
        avg_slope = (horizon_slope_H1 + horizon_slope_H2 + horizon_slope_H3) / 3.0
        # Compute slope variance (low variance = agreement)
        slope_variance = (
            (horizon_slope_H1 - avg_slope) ** 2 +
            (horizon_slope_H2 - avg_slope) ** 2 +
            (horizon_slope_H3 - avg_slope) ** 2
        ) / 3.0
        # Normalize variance to [0, 1] (max variance for [-1, 1] range is 2.0)
        normalized_variance = min(slope_variance / 2.0, 1.0)
        # Agreement = low variance
        slope_agreement = _clamp(1.0 - normalized_variance, 0.0, 1.0)
        # Boost if slopes are positive
        if avg_slope > 0:
            slope_agreement = _clamp(slope_agreement * 1.15, 0.0, 1.0)
        alignment_components.append(slope_agreement)
        alignment_weights.append(0.18)
        inputs_used["multi_horizon_slope_used"] = True

    # Component 3: Scenario Alignment (Phase 42)
    # High scenario alignment → regimes converging
    if scenario_alignment_score is not None:
        alignment_components.append(_clamp(scenario_alignment_score, 0.0, 1.0))
        alignment_weights.append(0.22)
        inputs_used["scenario_alignment_used"] = True

    # Component 4: ICC Support (Phase 37)
    # High ICC → identity continuity → supports alignment
    if icc is not None:
        alignment_components.append(_clamp(icc, 0.0, 1.0))
        alignment_weights.append(0.18)
        inputs_used["icc_used"] = True

    # Component 5: Future Stability Envelope (Phase 39)
    # High FSE → stable future → better alignment
    if future_stability_envelope is not None:
        alignment_components.append(_clamp(future_stability_envelope, 0.0, 1.0))
        alignment_weights.append(0.15)
        inputs_used["fse_used"] = True

    # Component 6: Forecast Consensus (Phase 39)
    # High consensus → horizons agree → better alignment
    if forecast_consensus_index is not None:
        alignment_components.append(_clamp(forecast_consensus_index, 0.0, 1.0))
        alignment_weights.append(0.12)
        inputs_used["fci_used"] = True

    # Component 7: Continuity Stability Score (Phase 37)
    # High CSS → continuity stable → better alignment
    if css is not None:
        alignment_components.append(_clamp(css, 0.0, 1.0))
        alignment_weights.append(0.10)
        inputs_used["css_used"] = True

    # Compute weighted average
    if not alignment_components:
        return None

    # Normalize weights to sum to 1.0
    total_weight = sum(alignment_weights)
    if total_weight <= 0:
        return None

    normalized_weights = [w / total_weight for w in alignment_weights]

    alignment_score = sum(
        comp * weight
        for comp, weight in zip(alignment_components, normalized_weights)
    )

    # Apply uncertainty penalty if uncertainty is high
    if future_uncertainty_band == "high":
        alignment_score *= 0.85  # 15% penalty
    elif future_uncertainty_band == "medium":
        alignment_score *= 0.95  # 5% penalty

    alignment_score = _clamp(alignment_score, 0.0, 1.0)

    # ========================================================================
    # STEP 3: COMPUTE CONFLICT INDEX
    # ========================================================================

    # Conflict index measures contradictory signals
    conflict_components = []
    conflict_weights = []

    # Conflict 1: High Drift Influence (Phase 38)
    # High drift → persona shifting → conflict
    if forecast_drift_influence is not None:
        conflict_components.append(_clamp(forecast_drift_influence, 0.0, 1.0))
        conflict_weights.append(0.25)

    # Conflict 2: High Entropy Forward Risk (Phase 38)
    # High entropy risk → future unpredictable → conflict
    if forecast_entropy_forward_risk is not None:
        conflict_components.append(_clamp(forecast_entropy_forward_risk, 0.0, 1.0))
        conflict_weights.append(0.25)

    # Conflict 3: Scenario Divergence (Phase 42)
    # High divergence → regimes spreading → conflict
    if scenario_divergence_index is not None:
        conflict_components.append(_clamp(scenario_divergence_index, 0.0, 1.0))
        conflict_weights.append(0.22)

    # Conflict 4: Slope Direction Contradiction
    # Negative slopes contradict positive scenario alignment
    if forecast_coherence_slope is not None and scenario_alignment_score is not None:
        # If slope is negative but scenario alignment is high → conflict
        if forecast_coherence_slope < -0.2 and scenario_alignment_score > 0.6:
            contradiction_signal = 0.80
        elif forecast_coherence_slope < 0 and scenario_alignment_score > 0.5:
            contradiction_signal = 0.50
        else:
            contradiction_signal = 0.0
        conflict_components.append(contradiction_signal)
        conflict_weights.append(0.15)

    # Conflict 5: Low Forecast Strength with High Uncertainty
    # Low confidence + high uncertainty → conflict
    if forecast_strength is not None and future_uncertainty_band is not None:
        if forecast_strength < 0.4 and future_uncertainty_band == "high":
            low_confidence_conflict = 0.75
        elif forecast_strength < 0.5 and future_uncertainty_band == "medium":
            low_confidence_conflict = 0.35
        else:
            low_confidence_conflict = 0.0
        conflict_components.append(low_confidence_conflict)
        conflict_weights.append(0.13)

    # Compute weighted average
    if conflict_components:
        total_conflict_weight = sum(conflict_weights)
        if total_conflict_weight > 0:
            normalized_conflict_weights = [w / total_conflict_weight for w in conflict_weights]
            conflict_index = sum(
                comp * weight
                for comp, weight in zip(conflict_components, normalized_conflict_weights)
            )
            conflict_index = _clamp(conflict_index, 0.0, 1.0)
        else:
            conflict_index = 0.0
    else:
        conflict_index = 0.0

    # ========================================================================
    # STEP 4: COMPUTE STABILITY AGREEMENT
    # ========================================================================

    # Stability agreement measures how well long-term forecasts support
    # identity continuity and consciousness stability
    stability_components = []
    stability_weights = []

    # Component 1: Future Stability Envelope (Phase 39)
    if future_stability_envelope is not None:
        stability_components.append(_clamp(future_stability_envelope, 0.0, 1.0))
        stability_weights.append(0.30)

    # Component 2: Identity Continuity Coefficient (Phase 37)
    if icc is not None:
        stability_components.append(_clamp(icc, 0.0, 1.0))
        stability_weights.append(0.25)

    # Component 3: Continuity Stability Score (Phase 37)
    if css is not None:
        stability_components.append(_clamp(css, 0.0, 1.0))
        stability_weights.append(0.20)

    # Component 4: Consciousness Stability Index (Phase 26)
    if csi is not None:
        stability_components.append(_clamp(csi, 0.0, 1.0))
        stability_weights.append(0.15)

    # Component 5: Core Identity Harmonic (Phase 34)
    if cih is not None:
        stability_components.append(_clamp(cih, 0.0, 1.0))
        stability_weights.append(0.10)

    # Compute weighted average
    if stability_components:
        total_stability_weight = sum(stability_weights)
        if total_stability_weight > 0:
            normalized_stability_weights = [w / total_stability_weight for w in stability_weights]
            stability_agreement = sum(
                comp * weight
                for comp, weight in zip(stability_components, normalized_stability_weights)
            )
            stability_agreement = _clamp(stability_agreement, 0.0, 1.0)
        else:
            stability_agreement = None
    else:
        stability_agreement = None

    # ========================================================================
    # STEP 5: CLASSIFY OVERALL ALIGNMENT BAND
    # ========================================================================

    overall_alignment_band = None

    if alignment_score >= 0.70:
        overall_alignment_band = "high"
    elif alignment_score >= 0.45:
        overall_alignment_band = "medium"
    elif alignment_score >= 0.25:
        overall_alignment_band = "low"
    else:
        overall_alignment_band = "conflict"

    # ========================================================================
    # STEP 6: GENERATE DIAGNOSTIC TAGS
    # ========================================================================

    diagnostic_tags = []

    # Alignment tags
    if alignment_score >= 0.75:
        diagnostic_tags.append("strong_alignment_multi_horizon")
    if alignment_score >= 0.70:
        diagnostic_tags.append("alignment_coherence_rising")
    if alignment_score <= 0.30:
        diagnostic_tags.append("alignment_deteriorating")

    # Conflict tags
    if conflict_index >= 0.70:
        diagnostic_tags.append("scenario_contradiction_detected")
    if conflict_index >= 0.65:
        diagnostic_tags.append("drift_conflict")
    if forecast_entropy_forward_risk is not None and forecast_entropy_forward_risk >= 0.70:
        diagnostic_tags.append("entropy_risk_elevated")

    # Stability tags
    if stability_agreement is not None:
        if stability_agreement >= 0.75:
            diagnostic_tags.append("alignment_identity_supported")
        if stability_agreement >= 0.70:
            diagnostic_tags.append("stability_consensus_strong")
        if stability_agreement <= 0.35:
            diagnostic_tags.append("stability_identity_diverging")

    # Forecast tags
    if future_uncertainty_band == "high":
        diagnostic_tags.append("high_future_uncertainty")
    if future_uncertainty_band == "low":
        diagnostic_tags.append("low_future_uncertainty_stable")

    # Scenario tags
    if scenario_alignment_score is not None and scenario_alignment_score >= 0.70:
        diagnostic_tags.append("scenario_regimes_converging")
    if scenario_divergence_index is not None and scenario_divergence_index >= 0.70:
        diagnostic_tags.append("scenario_regimes_diverging")

    # Slope consistency tags
    if (horizon_slope_H1 is not None and horizon_slope_H2 is not None and
        horizon_slope_H3 is not None):
        if horizon_slope_H1 > 0 and horizon_slope_H2 > 0 and horizon_slope_H3 > 0:
            diagnostic_tags.append("all_horizons_upward")
        elif horizon_slope_H1 < 0 and horizon_slope_H2 < 0 and horizon_slope_H3 < 0:
            diagnostic_tags.append("all_horizons_downward")

    # Forecast strength tags
    if forecast_strength is not None:
        if forecast_strength >= 0.75:
            diagnostic_tags.append("forecast_confidence_high")
        elif forecast_strength <= 0.35:
            diagnostic_tags.append("forecast_confidence_low")

    # Identity continuity tags
    if icc is not None and icc >= 0.75:
        diagnostic_tags.append("identity_continuity_robust")
    if icc is not None and icc <= 0.35:
        diagnostic_tags.append("identity_continuity_weak")

    # Overall band tags
    if overall_alignment_band == "high":
        diagnostic_tags.append("alignment_band_high")
    elif overall_alignment_band == "conflict":
        diagnostic_tags.append("alignment_band_conflict")

    # Sort and deduplicate for determinism
    diagnostic_tags = sorted(set(diagnostic_tags))

    # ========================================================================
    # STEP 7: RETURN SNAPSHOT
    # ========================================================================

    return CoherenceScenarioAlignmentSnapshot(
        alignment_score=alignment_score,
        conflict_index=conflict_index,
        stability_agreement=stability_agreement,
        overall_alignment_band=overall_alignment_band,
        diagnostic_tags=diagnostic_tags,
        inputs_used=inputs_used,
    )
