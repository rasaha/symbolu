"""
Multi-Trajectory Stability Field (MTSF) v1.0 - Phase 45

Deterministic, zero-LLM, observation-only engine that assesses trajectory stability
and convergence across multiple forecasting layers:

- Phase 38 Temporal Coherence Forecasting
- Phase 39 Multi-Horizon Temporal Forecasting
- Phase 42 Scenario Fusion Engine
- Phase 44 Coherence–Scenario Alignment Engine

MTSF produces a unified stability field that measures:
  1. Trajectory Stability Index (TSI): Cross-phase trajectory convergence [0.0, 1.0]
  2. Trajectory Volatility Index (TVI): Variance across forecast slopes [0.0, 1.0]
  3. Cross-Horizon Flux (CHF): Disagreement between H1/H2/H3 [0.0, 1.0]
  4. Scenario-Coherence Coupling (SCC): Alignment with scenario fusion + CSAE [0.0, 1.0]
  5. Stability Band: HIGH | MEDIUM | LOW | CHAOTIC
  6. Diagnostic Tags

CRITICAL INVARIANTS:
    - Zero-LLM: Purely rule-based, deterministic math only
    - Observation-only: NO changes to routing, TTOR, MLCR, mappers, Fusion, DHA, Renderer
    - Diagnostics/UI only: Feeds coherence state, session summary, unified API, and DILchat badges
    - Non-invasive: Does not modify any existing coherence formulas or behaviors
    - Backward-compatible: All existing tests remain green
    - Deterministic: Same inputs → same outputs always
    - Fully bounded: All outputs [0.0, 1.0]
    - Graceful degradation: Returns None if insufficient data
"""

from dataclasses import dataclass, field
from typing import List, Optional, Any
import math


@dataclass
class MultiTrajectoryStabilityFieldSnapshot:
    """
    Immutable snapshot of Multi-Trajectory Stability Field computation.

    This snapshot measures trajectory stability and convergence across
    multiple forecasting layers (Phase 38, 39, 42, 44).

    Fields:
        tsi: Trajectory Stability Index [0.0, 1.0] - cross-phase convergence
        tvi: Trajectory Volatility Index [0.0, 1.0] - variance across forecast slopes
        chf: Cross-Horizon Flux [0.0, 1.0] - disagreement between H1/H2/H3
        scc: Scenario-Coherence Coupling [0.0, 1.0] - alignment with scenario fusion + CSAE
        band: Stability band classification: "HIGH" | "MEDIUM" | "LOW" | "CHAOTIC"
        tags: Diagnostic tags (e.g., "TRAJECTORY_CONVERGING", "STABILITY_STRONG")
    """

    tsi: float  # Trajectory Stability Index [0.0, 1.0]
    tvi: float  # Trajectory Volatility Index [0.0, 1.0]
    chf: float  # Cross-Horizon Flux [0.0, 1.0]
    scc: float  # Scenario-Coherence Coupling [0.0, 1.0]
    band: str  # "HIGH" | "MEDIUM" | "LOW" | "CHAOTIC"
    tags: List[str] = field(default_factory=list)


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


def _safe_get(data: Optional[Any], attr: str, default: float = 0.0) -> float:
    """
    Safely extract float value from dict or object.

    Args:
        data: Data object (dict or object with attributes)
        attr: Attribute/key name
        default: Default value if not found

    Returns:
        float: Extracted value or default
    """
    if data is None:
        return default

    # Try dict access
    if isinstance(data, dict):
        value = data.get(attr, default)
    # Try attribute access
    elif hasattr(data, attr):
        value = getattr(data, attr, default)
    else:
        return default

    # Ensure numeric
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return float(value)

    return default


def _compute_variance(values: List[float]) -> float:
    """
    Compute variance of a list of values.

    Args:
        values: List of float values

    Returns:
        float: Variance [0.0, ∞)
    """
    if not values or len(values) < 2:
        return 0.0

    mean = sum(values) / len(values)
    variance = sum((x - mean) ** 2 for x in values) / len(values)

    return variance


def _compute_range(values: List[float]) -> float:
    """
    Compute range (max - min) of values.

    Args:
        values: List of float values

    Returns:
        float: Range [0.0, ∞)
    """
    if not values:
        return 0.0

    return max(values) - min(values)


def compute_multi_trajectory_stability_field(
    forecast_phase38: Optional[Any] = None,
    multi_horizon_phase39: Optional[Any] = None,
    scenario_fusion_phase42: Optional[Any] = None,
    csae_phase44: Optional[Any] = None,
) -> Optional[MultiTrajectoryStabilityFieldSnapshot]:
    """
    Compute Multi-Trajectory Stability Field (MTSF) v1.0.

    This function assesses trajectory stability across multiple forecasting layers:
      - Phase 38: Temporal Coherence Forecasting
      - Phase 39: Multi-Horizon Forecasting
      - Phase 42: Scenario Fusion
      - Phase 44: Coherence–Scenario Alignment

    Args:
        forecast_phase38: Phase 38 TemporalCoherenceForecastSnapshot
        multi_horizon_phase39: Phase 39 MultiHorizonForecastSnapshot
        scenario_fusion_phase42: Phase 42 ScenarioFusionSnapshot
        csae_phase44: Phase 44 CoherenceScenarioAlignmentSnapshot

    Returns:
        MultiTrajectoryStabilityFieldSnapshot or None if insufficient data

    Formula Design:
        - TSI (Trajectory Stability Index):
            * Measures cross-phase convergence
            * High TSI = forecasts agree, low volatility
            * Based on: forecast strength, consensus index, alignment score

        - TVI (Trajectory Volatility Index):
            * Measures variance across forecast slopes
            * High TVI = slopes diverge, unstable trajectory
            * Based on: slope variance from Phase 38/39

        - CHF (Cross-Horizon Flux):
            * Measures disagreement between H1/H2/H3
            * High CHF = horizons diverge
            * Based on: horizon slope variance, strength variance

        - SCC (Scenario-Coherence Coupling):
            * Measures alignment between scenario fusion and CSAE
            * High SCC = strong coupling between scenarios and coherence
            * Based on: scenario alignment, CSAE alignment score, stability agreement

        - Band Classification:
            * HIGH: TSI >= 0.70, TVI <= 0.35, CHF <= 0.35
            * MEDIUM: 0.45 <= TSI < 0.70 OR moderate TVI/CHF
            * LOW: TSI < 0.45 OR high TVI/CHF
            * CHAOTIC: TSI < 0.30 AND (TVI > 0.70 OR CHF > 0.70)

    Graceful Degradation:
        Returns None if fewer than 2 upstream phases are available.
    """
    # ========================================================================
    # STEP 1: VALIDATE INPUT AND COUNT AVAILABLE PHASES
    # ========================================================================

    phases_available = sum([
        forecast_phase38 is not None,
        multi_horizon_phase39 is not None,
        scenario_fusion_phase42 is not None,
        csae_phase44 is not None,
    ])

    # Need at least 2 phases for meaningful stability field computation
    if phases_available < 2:
        return None

    # ========================================================================
    # STEP 2: EXTRACT SIGNALS FROM EACH PHASE
    # ========================================================================

    # Phase 38 - Temporal Coherence Forecasting
    p38_coherence_slope = _safe_get(forecast_phase38, "coherence_slope", 0.0)
    p38_continuity_slope = _safe_get(forecast_phase38, "continuity_slope", 0.0)
    p38_forecast_strength = _safe_get(forecast_phase38, "forecast_strength", 0.5)
    p38_drift_influence = _safe_get(forecast_phase38, "drift_influence", 0.5)

    # Phase 39 - Multi-Horizon Forecasting
    p39_h1_slope = None
    p39_h2_slope = None
    p39_h3_slope = None
    p39_h1_strength = None
    p39_h2_strength = None
    p39_h3_strength = None
    p39_fci = _safe_get(multi_horizon_phase39, "forecast_consensus_index", 0.0)
    p39_fse = _safe_get(multi_horizon_phase39, "future_stability_envelope", 0.0)

    if multi_horizon_phase39 is not None:
        # Extract H1, H2, H3 forecasts
        if hasattr(multi_horizon_phase39, "h1_forecast") and multi_horizon_phase39.h1_forecast:
            p39_h1_slope = _safe_get(multi_horizon_phase39.h1_forecast, "coherence_slope", 0.0)
            p39_h1_strength = _safe_get(multi_horizon_phase39.h1_forecast, "forecast_strength", 0.5)
        if hasattr(multi_horizon_phase39, "h2_forecast") and multi_horizon_phase39.h2_forecast:
            p39_h2_slope = _safe_get(multi_horizon_phase39.h2_forecast, "coherence_slope", 0.0)
            p39_h2_strength = _safe_get(multi_horizon_phase39.h2_forecast, "forecast_strength", 0.5)
        if hasattr(multi_horizon_phase39, "h3_forecast") and multi_horizon_phase39.h3_forecast:
            p39_h3_slope = _safe_get(multi_horizon_phase39.h3_forecast, "coherence_slope", 0.0)
            p39_h3_strength = _safe_get(multi_horizon_phase39.h3_forecast, "forecast_strength", 0.5)

    # Phase 42 - Scenario Fusion
    p42_scenario_alignment = _safe_get(scenario_fusion_phase42, "scenario_alignment_score", 0.0)
    p42_scenario_divergence = _safe_get(scenario_fusion_phase42, "scenario_divergence_index", 0.0)
    p42_multi_regime_consensus = _safe_get(scenario_fusion_phase42, "multi_regime_consensus", 0.0)

    # Phase 44 - Coherence–Scenario Alignment
    p44_alignment_score = _safe_get(csae_phase44, "alignment_score", 0.0)
    p44_conflict_index = _safe_get(csae_phase44, "conflict_index", 0.0)
    p44_stability_agreement = _safe_get(csae_phase44, "stability_agreement", 0.0)

    # ========================================================================
    # STEP 3: COMPUTE TSI (Trajectory Stability Index)
    # ========================================================================

    # TSI measures cross-phase convergence
    # Components:
    #   - Forecast strength (Phase 38)
    #   - Forecast Consensus Index (Phase 39)
    #   - Alignment score (Phase 44)
    #   - Future Stability Envelope (Phase 39)
    #   - Inverse of drift influence (Phase 38)

    tsi_components = []
    tsi_weights = []

    # Component 1: Forecast strength from Phase 38
    if forecast_phase38 is not None:
        tsi_components.append(_clamp(p38_forecast_strength, 0.0, 1.0))
        tsi_weights.append(0.25)

    # Component 2: Forecast Consensus Index from Phase 39
    if multi_horizon_phase39 is not None:
        tsi_components.append(_clamp(p39_fci, 0.0, 1.0))
        tsi_weights.append(0.25)

    # Component 3: Alignment score from Phase 44
    if csae_phase44 is not None:
        tsi_components.append(_clamp(p44_alignment_score, 0.0, 1.0))
        tsi_weights.append(0.30)

    # Component 4: Future Stability Envelope from Phase 39
    if multi_horizon_phase39 is not None:
        tsi_components.append(_clamp(p39_fse, 0.0, 1.0))
        tsi_weights.append(0.15)

    # Component 5: Inverse of drift influence (low drift = high stability)
    if forecast_phase38 is not None:
        tsi_components.append(_clamp(1.0 - p38_drift_influence, 0.0, 1.0))
        tsi_weights.append(0.05)

    # Compute weighted average
    if not tsi_components:
        return None

    total_tsi_weight = sum(tsi_weights)
    normalized_tsi_weights = [w / total_tsi_weight for w in tsi_weights]
    tsi = sum(comp * weight for comp, weight in zip(tsi_components, normalized_tsi_weights))
    tsi = _clamp(tsi, 0.0, 1.0)

    # ========================================================================
    # STEP 4: COMPUTE TVI (Trajectory Volatility Index)
    # ========================================================================

    # TVI measures variance across forecast slopes
    # Collect all available slopes (normalized to [0, 1])

    slopes = []

    # Phase 38 slopes (map [-1, 1] → [0, 1])
    if forecast_phase38 is not None:
        slopes.append((p38_coherence_slope + 1.0) / 2.0)
        slopes.append((p38_continuity_slope + 1.0) / 2.0)

    # Phase 39 horizon slopes (map [-1, 1] → [0, 1])
    if p39_h1_slope is not None:
        slopes.append((p39_h1_slope + 1.0) / 2.0)
    if p39_h2_slope is not None:
        slopes.append((p39_h2_slope + 1.0) / 2.0)
    if p39_h3_slope is not None:
        slopes.append((p39_h3_slope + 1.0) / 2.0)

    # Compute variance
    if len(slopes) >= 2:
        slope_variance = _compute_variance(slopes)
        # Normalize variance to [0, 1]
        # Max variance for [0, 1] range is 0.25 (when half are 0, half are 1)
        tvi = _clamp(slope_variance / 0.25, 0.0, 1.0)
    else:
        # Not enough slopes, use default moderate volatility
        tvi = 0.5

    # ========================================================================
    # STEP 5: COMPUTE CHF (Cross-Horizon Flux)
    # ========================================================================

    # CHF measures disagreement between H1/H2/H3 horizons
    # Based on:
    #   - Variance of horizon slopes
    #   - Variance of horizon strengths
    #   - Inverse of Forecast Consensus Index

    chf_components = []
    chf_weights = []

    # Component 1: Horizon slope variance
    horizon_slopes = []
    if p39_h1_slope is not None:
        horizon_slopes.append(p39_h1_slope)
    if p39_h2_slope is not None:
        horizon_slopes.append(p39_h2_slope)
    if p39_h3_slope is not None:
        horizon_slopes.append(p39_h3_slope)

    if len(horizon_slopes) >= 2:
        horizon_slope_variance = _compute_variance(horizon_slopes)
        # Normalize variance (max variance for [-1, 1] range is ~2.0)
        horizon_slope_flux = _clamp(horizon_slope_variance / 2.0, 0.0, 1.0)
        chf_components.append(horizon_slope_flux)
        chf_weights.append(0.40)

    # Component 2: Horizon strength variance
    horizon_strengths = []
    if p39_h1_strength is not None:
        horizon_strengths.append(p39_h1_strength)
    if p39_h2_strength is not None:
        horizon_strengths.append(p39_h2_strength)
    if p39_h3_strength is not None:
        horizon_strengths.append(p39_h3_strength)

    if len(horizon_strengths) >= 2:
        horizon_strength_variance = _compute_variance(horizon_strengths)
        # Normalize variance
        horizon_strength_flux = _clamp(horizon_strength_variance / 0.25, 0.0, 1.0)
        chf_components.append(horizon_strength_flux)
        chf_weights.append(0.30)

    # Component 3: Inverse of Forecast Consensus Index
    if multi_horizon_phase39 is not None:
        chf_components.append(_clamp(1.0 - p39_fci, 0.0, 1.0))
        chf_weights.append(0.30)

    # Compute weighted average
    if chf_components:
        total_chf_weight = sum(chf_weights)
        normalized_chf_weights = [w / total_chf_weight for w in chf_weights]
        chf = sum(comp * weight for comp, weight in zip(chf_components, normalized_chf_weights))
        chf = _clamp(chf, 0.0, 1.0)
    else:
        # No cross-horizon data, use moderate flux
        chf = 0.5

    # ========================================================================
    # STEP 6: COMPUTE SCC (Scenario-Coherence Coupling)
    # ========================================================================

    # SCC measures alignment between scenario fusion and CSAE
    # Components:
    #   - Scenario alignment score (Phase 42)
    #   - CSAE alignment score (Phase 44)
    #   - Stability agreement (Phase 44)
    #   - Multi-regime consensus (Phase 42)
    #   - Inverse of conflict index (Phase 44)

    scc_components = []
    scc_weights = []

    # Component 1: Scenario alignment score
    if scenario_fusion_phase42 is not None:
        scc_components.append(_clamp(p42_scenario_alignment, 0.0, 1.0))
        scc_weights.append(0.25)

    # Component 2: CSAE alignment score
    if csae_phase44 is not None:
        scc_components.append(_clamp(p44_alignment_score, 0.0, 1.0))
        scc_weights.append(0.30)

    # Component 3: Stability agreement
    if csae_phase44 is not None and p44_stability_agreement > 0.0:
        scc_components.append(_clamp(p44_stability_agreement, 0.0, 1.0))
        scc_weights.append(0.20)

    # Component 4: Multi-regime consensus
    if scenario_fusion_phase42 is not None:
        scc_components.append(_clamp(p42_multi_regime_consensus, 0.0, 1.0))
        scc_weights.append(0.15)

    # Component 5: Inverse of conflict index
    if csae_phase44 is not None:
        scc_components.append(_clamp(1.0 - p44_conflict_index, 0.0, 1.0))
        scc_weights.append(0.10)

    # Compute weighted average
    if scc_components:
        total_scc_weight = sum(scc_weights)
        normalized_scc_weights = [w / total_scc_weight for w in scc_weights]
        scc = sum(comp * weight for comp, weight in zip(scc_components, normalized_scc_weights))
        scc = _clamp(scc, 0.0, 1.0)
    else:
        # No scenario/alignment data, use moderate coupling
        scc = 0.5

    # ========================================================================
    # STEP 7: CLASSIFY STABILITY BAND
    # ========================================================================

    band = None

    # CHAOTIC: Very low TSI AND (very high TVI OR very high CHF)
    if tsi < 0.30 and (tvi > 0.70 or chf > 0.70):
        band = "CHAOTIC"
    # HIGH: High TSI, low TVI, low CHF
    elif tsi >= 0.70 and tvi <= 0.35 and chf <= 0.35:
        band = "HIGH"
    # MEDIUM: Moderate TSI OR moderate TVI/CHF
    elif tsi >= 0.45 or (tvi <= 0.60 and chf <= 0.60):
        band = "MEDIUM"
    # LOW: Low TSI OR high TVI/CHF
    else:
        band = "LOW"

    # ========================================================================
    # STEP 8: GENERATE DIAGNOSTIC TAGS
    # ========================================================================

    tags = []

    # TSI tags
    if tsi >= 0.75:
        tags.append("STABILITY_STRONG")
    elif tsi <= 0.35:
        tags.append("STABILITY_FRAGILE")

    # TVI tags
    if tvi >= 0.70:
        tags.append("TRAJECTORY_DIVERGING")
    elif tvi <= 0.35:
        tags.append("TRAJECTORY_CONVERGING")

    # CHF tags
    if chf >= 0.65:
        tags.append("CROSS_HORIZON_CONFLICT")
    elif chf <= 0.35:
        tags.append("CROSS_HORIZON_ALIGNED")

    # SCC tags
    if scc >= 0.70:
        tags.append("SCENARIO_COHERENCE_COUPLED")
    elif scc <= 0.35:
        tags.append("SCENARIO_MISMATCH")

    # Band tags
    if band == "HIGH":
        tags.append("MTSF_BAND_HIGH")
    elif band == "CHAOTIC":
        tags.append("MTSF_BAND_CHAOTIC")

    # Convergence/divergence patterns
    if tvi <= 0.30 and chf <= 0.30 and tsi >= 0.65:
        tags.append("TRAJECTORY_STRONGLY_CONVERGING")
    if tvi >= 0.70 and chf >= 0.70:
        tags.append("TRAJECTORY_STRONGLY_DIVERGING")

    # Stability patterns
    if tsi >= 0.70 and scc >= 0.70:
        tags.append("STABILITY_SCENARIO_REINFORCED")
    if tsi <= 0.35 and p44_conflict_index >= 0.65:
        tags.append("STABILITY_CONFLICT_DETECTED")

    # Sort and deduplicate for determinism
    tags = sorted(set(tags))

    # ========================================================================
    # STEP 9: RETURN SNAPSHOT
    # ========================================================================

    return MultiTrajectoryStabilityFieldSnapshot(
        tsi=tsi,
        tvi=tvi,
        chf=chf,
        scc=scc,
        band=band,
        tags=tags,
    )
