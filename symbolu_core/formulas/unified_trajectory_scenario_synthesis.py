"""
Unified Trajectory–Scenario Synthesis Engine (UTSSE) v1.0 - Phase 47

Deterministic, zero-LLM, observation-only engine that synthesizes signals from
Phases 35, 36, 37, 38, 39, 42, 44, and 46 into a unified prediction of
future-state coherence.

This engine creates a holistic synthesis of:
- Phase 35: Predictive Persona Drift (drift predictions)
- Phase 36: Identity Resonance Memory (identity memory)
- Phase 37: Adaptive Continuity Engine (continuity tracking)
- Phase 38: Temporal Coherence Forecasting (single-horizon forecasting)
- Phase 39: Multi-Horizon Temporal Forecasting (multi-horizon forecasting)
- Phase 42: Scenario Fusion Engine (scenario fusion)
- Phase 44: Coherence-Scenario Alignment (scenario alignment)
- Phase 46: Trajectory Field Convergence (trajectory convergence)

UTSSE produces a unified snapshot that quantifies:
1. How well all trajectory and scenario signals align
2. Future-state coherence prediction
3. Cross-horizon consistency
4. Synthesis integrity and stability

CRITICAL INVARIANTS:
    - Zero-LLM: Purely rule-based, deterministic math only
    - Observation-only: NO changes to routing, TTOR, MLCR, mappers, Fusion, DHA, Renderer
    - Metadata-only persona integration: NO tone or semantic changes
    - Diagnostics/UI only: Feeds coherence state, session summary, unified API, and DILchat badges
    - Non-invasive: Does not modify any existing coherence formulas or behaviors
    - Backward-compatible: All existing tests remain green
    - Deterministic: Same inputs → same outputs always
    - Fully bounded: All outputs [0.0, 1.0]
    - Graceful degradation: Returns None if insufficient data (<3 upstream phases)
"""

from dataclasses import dataclass, field
from typing import List, Optional, Any
import math


@dataclass
class UnifiedTrajectoryScenarioSnapshot:
    """
    Immutable snapshot of Unified Trajectory–Scenario Synthesis Engine computation.

    This snapshot synthesizes signals from multiple upstream phases to predict
    future-state coherence and alignment.

    Fields:
        synthesis_integrity_score: [0.0, 1.0] - overall synthesis integrity/reliability
        future_state_alignment_score: [0.0, 1.0] - how aligned future-state predictions are
        future_state_coherence_score: [0.0, 1.0] - predicted future coherence quality
        cross_horizon_consistency_score: [0.0, 1.0] - consistency across time horizons
        future_divergence_risk: [0.0, 1.0] - risk of future divergence/fragmentation
        convergence_signal_strength: [0.0, 1.0] - strength of convergence signals
        dominant_future_path: Dominant trajectory/scenario descriptor or None
        synthesis_band: "HIGH" | "MEDIUM" | "LOW" | "FRAGMENTED"
        diagnostic_tags: List of diagnostic pattern indicators
    """

    synthesis_integrity_score: float = 0.0
    future_state_alignment_score: float = 0.0
    future_state_coherence_score: float = 0.0
    cross_horizon_consistency_score: float = 0.0
    future_divergence_risk: float = 0.0
    convergence_signal_strength: float = 0.0
    dominant_future_path: Optional[str] = None
    synthesis_band: str = "LOW"
    diagnostic_tags: List[str] = field(default_factory=list)


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


def _compute_mean(values: List[float]) -> float:
    """
    Compute mean of a list of values.

    Args:
        values: List of float values

    Returns:
        float: Mean value or 0.0 if empty
    """
    if not values:
        return 0.0
    return sum(values) / len(values)


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

    mean = _compute_mean(values)
    variance = sum((x - mean) ** 2 for x in values) / len(values)

    return variance


def _compute_std_dev(values: List[float]) -> float:
    """
    Compute standard deviation of a list of values.

    Args:
        values: List of float values

    Returns:
        float: Standard deviation [0.0, ∞)
    """
    variance = _compute_variance(values)
    return math.sqrt(variance)


def compute_unified_trajectory_scenario_synthesis(
    drift: Optional[Any] = None,
    identity: Optional[Any] = None,
    continuity: Optional[Any] = None,
    forecast_single: Optional[Any] = None,
    forecast_multi: Optional[Any] = None,
    scenario_fusion: Optional[Any] = None,
    scenario_alignment: Optional[Any] = None,
    trajectory_convergence: Optional[Any] = None,
) -> Optional[UnifiedTrajectoryScenarioSnapshot]:
    """
    Compute Unified Trajectory–Scenario Synthesis Engine (UTSSE) v1.0.

    This function synthesizes signals from Phases 35-46 to predict future-state
    coherence and measure synthesis integrity.

    Args:
        drift: Phase 35 PredictivePersonaDriftSnapshot
        identity: Phase 36 IdentityResonanceMemorySnapshot
        continuity: Phase 37 AdaptiveContinuitySnapshot
        forecast_single: Phase 38 TemporalCoherenceForecastSnapshot
        forecast_multi: Phase 39 MultiHorizonForecastSnapshot
        scenario_fusion: Phase 42 ScenarioFusionSnapshot
        scenario_alignment: Phase 44 CoherenceScenarioAlignmentSnapshot
        trajectory_convergence: Phase 46 TrajectoryFieldConvergenceSnapshot

    Returns:
        UnifiedTrajectoryScenarioSnapshot or None if insufficient data

    Formula Design:
        - Convergence Index: Weighted combination of trajectory convergence + scenario alignment
        - Divergence Index: Weighted combination of drift risk + divergence signals
        - Stability Index: Weighted combination of identity + continuity + horizon stability
        - Synthesis Integrity Score: Weighted blend based on data availability and consistency
        - Future State Alignment: How aligned all future predictions are
        - Future State Coherence: Predicted coherence quality at future horizons
        - Cross-Horizon Consistency: Consistency across H1/H2/H3 horizons
        - Future Divergence Risk: Risk of future fragmentation
        - Convergence Signal Strength: Strength of convergence signals

        Synthesis Band Classification:
            * HIGH: synthesis_integrity >= 0.70 and alignment >= 0.70
            * MEDIUM: synthesis_integrity >= 0.50 and alignment >= 0.50
            * LOW: synthesis_integrity >= 0.35 or alignment >= 0.35
            * FRAGMENTED: synthesis_integrity < 0.35 and alignment < 0.35

    Graceful Degradation:
        Returns None if fewer than 3 upstream phases are available.
    """
    # ========================================================================
    # STEP 1: VALIDATE INPUT AND COUNT AVAILABLE PHASES
    # ========================================================================

    phases_available = sum([
        drift is not None,
        identity is not None,
        continuity is not None,
        forecast_single is not None,
        forecast_multi is not None,
        scenario_fusion is not None,
        scenario_alignment is not None,
        trajectory_convergence is not None,
    ])

    # Need at least 3 phases for meaningful synthesis
    if phases_available < 3:
        return None

    # ========================================================================
    # STEP 2: EXTRACT SIGNALS FROM EACH PHASE
    # ========================================================================

    # Phase 35 - Predictive Persona Drift
    p35_drift_magnitude = _safe_get(drift, "drift_magnitude_prediction", 0.0)
    p35_drift_stability = _safe_get(drift, "drift_stability_score", 0.0)

    # Phase 36 - Identity Resonance Memory
    p36_ims = _safe_get(identity, "ims", 0.0)  # Identity Memory Strength
    p36_iep = _safe_get(identity, "iep", 0.0)  # Identity Echo Persistence
    p36_ida = _safe_get(identity, "ida", 0.0)  # Identity Drift Anchoring

    # Phase 37 - Adaptive Continuity Engine
    p37_ncc = _safe_get(continuity, "ncc", 0.0)  # Narrative Continuity Coefficient
    p37_icc = _safe_get(continuity, "icc", 0.0)  # Identity Continuity Coefficient
    p37_css = _safe_get(continuity, "css", 0.0)  # Continuity Stability Score

    # Phase 38 - Temporal Coherence Forecasting (single-horizon)
    p38_forecast_strength = _safe_get(forecast_single, "forecast_strength", 0.0)
    p38_coherence_slope = _safe_get(forecast_single, "coherence_slope", 0.0)

    # Phase 39 - Multi-Horizon Temporal Forecasting
    p39_fci = _safe_get(forecast_multi, "forecast_consensus_index", 0.0)
    p39_fse = _safe_get(forecast_multi, "future_stability_envelope", 0.0)

    # Phase 42 - Scenario Fusion Engine
    p42_scenario_alignment = _safe_get(scenario_fusion, "scenario_alignment_score", 0.0)
    p42_scenario_divergence = _safe_get(scenario_fusion, "scenario_divergence_index", 0.0)
    p42_multi_regime_consensus = _safe_get(scenario_fusion, "multi_regime_consensus", 0.0)

    # Phase 44 - Coherence-Scenario Alignment
    p44_alignment_score = _safe_get(scenario_alignment, "alignment_score", 0.0)
    p44_conflict_index = _safe_get(scenario_alignment, "conflict_index", 0.0)
    p44_stability_agreement = _safe_get(scenario_alignment, "stability_agreement", 0.0)

    # Phase 46 - Trajectory Field Convergence
    p46_convergence_index = _safe_get(trajectory_convergence, "convergence_index", 0.0)
    p46_divergence_index = _safe_get(trajectory_convergence, "divergence_index", 0.0)
    p46_stability_index = _safe_get(trajectory_convergence, "stability_index", 0.0)

    # ========================================================================
    # STEP 3: COMPUTE CONVERGENCE INDEX
    # ========================================================================

    # Convergence index measures how much all signals are converging toward
    # a unified future state
    convergence_signals = []

    # Trajectory convergence (Phase 46) - strongest signal
    if trajectory_convergence is not None:
        convergence_signals.append(p46_convergence_index)

    # Scenario alignment (Phase 44) - strong signal
    if scenario_alignment is not None:
        convergence_signals.append(p44_alignment_score)

    # Scenario fusion consensus (Phase 42) - moderate signal
    if scenario_fusion is not None:
        convergence_signals.append(p42_multi_regime_consensus)

    # Forecast consensus (Phase 39) - moderate signal
    if forecast_multi is not None:
        convergence_signals.append(p39_fci)

    # Continuity stability (Phase 37) - supporting signal
    if continuity is not None:
        convergence_signals.append(p37_css)

    if not convergence_signals:
        convergence_index = 0.5  # Default moderate
    else:
        convergence_index = _compute_mean(convergence_signals)

    convergence_index = _clamp(convergence_index, 0.0, 1.0)

    # ========================================================================
    # STEP 4: COMPUTE DIVERGENCE INDEX
    # ========================================================================

    # Divergence index measures risk of fragmentation/divergence
    divergence_signals = []

    # Trajectory divergence (Phase 46) - strongest signal
    if trajectory_convergence is not None:
        divergence_signals.append(p46_divergence_index)

    # Scenario divergence (Phase 42) - strong signal
    if scenario_fusion is not None:
        divergence_signals.append(p42_scenario_divergence)

    # Drift magnitude (Phase 35) - moderate signal
    if drift is not None:
        divergence_signals.append(p35_drift_magnitude)

    # Conflict index (Phase 44) - moderate signal
    if scenario_alignment is not None:
        divergence_signals.append(p44_conflict_index)

    if not divergence_signals:
        divergence_index = 0.5  # Default moderate
    else:
        divergence_index = _compute_mean(divergence_signals)

    divergence_index = _clamp(divergence_index, 0.0, 1.0)

    # ========================================================================
    # STEP 5: COMPUTE STABILITY INDEX
    # ========================================================================

    # Stability index measures how stable the synthesis is
    stability_signals = []
    stability_weights = []

    # Trajectory stability (Phase 46) - highest weight
    if trajectory_convergence is not None:
        stability_signals.append(p46_stability_index)
        stability_weights.append(0.25)

    # Future stability envelope (Phase 39) - high weight
    if forecast_multi is not None:
        stability_signals.append(p39_fse)
        stability_weights.append(0.20)

    # Stability agreement (Phase 44) - high weight
    if scenario_alignment is not None:
        stability_signals.append(p44_stability_agreement)
        stability_weights.append(0.20)

    # Continuity stability (Phase 37) - moderate weight
    if continuity is not None:
        stability_signals.append(p37_css)
        stability_weights.append(0.15)

    # Identity drift anchoring (Phase 36) - moderate weight
    if identity is not None:
        stability_signals.append(p36_ida)
        stability_weights.append(0.10)

    # Drift stability (Phase 35) - supporting weight
    if drift is not None:
        stability_signals.append(p35_drift_stability)
        stability_weights.append(0.10)

    if stability_signals:
        total_weight = sum(stability_weights)
        normalized_weights = [w / total_weight for w in stability_weights]
        stability_index = sum(
            sig * weight for sig, weight in zip(stability_signals, normalized_weights)
        )
        stability_index = _clamp(stability_index, 0.0, 1.0)
    else:
        stability_index = 0.5  # Default moderate

    # ========================================================================
    # STEP 6: COMPUTE SYNTHESIS INTEGRITY SCORE
    # ========================================================================

    # Synthesis integrity measures how reliable/consistent the synthesis is
    # High integrity = low variance, high stability, good data availability

    # Component 1: Data availability factor (how many phases are available)
    data_availability_factor = phases_available / 8.0  # Max 8 phases
    data_availability_factor = _clamp(data_availability_factor, 0.0, 1.0)

    # Component 2: Consistency factor (low variance in convergence signals)
    if len(convergence_signals) >= 2:
        convergence_std_dev = _compute_std_dev(convergence_signals)
        # Normalize std dev to [0, 1] (max std dev for values in [0,1] is 0.5)
        normalized_std_dev = min(convergence_std_dev / 0.5, 1.0)
        consistency_factor = 1.0 - normalized_std_dev
    else:
        consistency_factor = 0.5  # Default moderate

    # Component 3: Stability factor (from stability index)
    stability_factor = stability_index

    # Component 4: Convergence factor (from convergence index)
    convergence_factor = convergence_index

    # Weighted combination
    synthesis_integrity_score = (
        0.30 * data_availability_factor +
        0.25 * consistency_factor +
        0.25 * stability_factor +
        0.20 * convergence_factor
    )
    synthesis_integrity_score = _clamp(synthesis_integrity_score, 0.0, 1.0)

    # ========================================================================
    # STEP 7: COMPUTE FUTURE STATE ALIGNMENT SCORE
    # ========================================================================

    # Future state alignment measures how aligned all future predictions are
    alignment_signals = []

    # Trajectory convergence (Phase 46)
    if trajectory_convergence is not None:
        alignment_signals.append(p46_convergence_index)

    # Scenario alignment (Phase 44)
    if scenario_alignment is not None:
        alignment_signals.append(p44_alignment_score)

    # Scenario fusion alignment (Phase 42)
    if scenario_fusion is not None:
        alignment_signals.append(p42_scenario_alignment)

    # Forecast consensus (Phase 39)
    if forecast_multi is not None:
        alignment_signals.append(p39_fci)

    if alignment_signals:
        future_state_alignment_score = _compute_mean(alignment_signals)
        future_state_alignment_score = _clamp(future_state_alignment_score, 0.0, 1.0)
    else:
        future_state_alignment_score = 0.5  # Default moderate

    # ========================================================================
    # STEP 8: COMPUTE FUTURE STATE COHERENCE SCORE
    # ========================================================================

    # Future state coherence predicts the quality of future coherence
    coherence_signals = []

    # Future stability envelope (Phase 39) - strongest predictor
    if forecast_multi is not None:
        coherence_signals.append(p39_fse)

    # Forecast strength (Phase 38)
    if forecast_single is not None:
        coherence_signals.append(p38_forecast_strength)

    # Stability agreement (Phase 44)
    if scenario_alignment is not None:
        coherence_signals.append(p44_stability_agreement)

    # Continuity coefficients (Phase 37)
    if continuity is not None:
        continuity_avg = (p37_ncc + p37_icc + p37_css) / 3.0
        coherence_signals.append(continuity_avg)

    # Identity resonance (Phase 36)
    if identity is not None:
        identity_avg = (p36_ims + p36_iep + p36_ida) / 3.0
        coherence_signals.append(identity_avg)

    # Inverse drift (Phase 35)
    if drift is not None:
        coherence_signals.append(1.0 - p35_drift_magnitude)

    if coherence_signals:
        future_state_coherence_score = _compute_mean(coherence_signals)
        future_state_coherence_score = _clamp(future_state_coherence_score, 0.0, 1.0)
    else:
        future_state_coherence_score = 0.5  # Default moderate

    # ========================================================================
    # STEP 9: COMPUTE CROSS-HORIZON CONSISTENCY SCORE
    # ========================================================================

    # Cross-horizon consistency measures consistency across H1/H2/H3 horizons
    # This is primarily based on Phase 39 multi-horizon forecasting

    if forecast_multi is not None:
        # Use forecast consensus index as primary measure
        cross_horizon_consistency_score = p39_fci
    else:
        # Fall back to general stability measures
        if continuity is not None and identity is not None:
            cross_horizon_consistency_score = (p37_css + p36_ida) / 2.0
        elif continuity is not None:
            cross_horizon_consistency_score = p37_css
        elif identity is not None:
            cross_horizon_consistency_score = p36_ida
        else:
            cross_horizon_consistency_score = 0.5  # Default moderate

    cross_horizon_consistency_score = _clamp(cross_horizon_consistency_score, 0.0, 1.0)

    # ========================================================================
    # STEP 10: COMPUTE FUTURE DIVERGENCE RISK
    # ========================================================================

    # Future divergence risk is the divergence index we already computed
    future_divergence_risk = divergence_index

    # ========================================================================
    # STEP 11: COMPUTE CONVERGENCE SIGNAL STRENGTH
    # ========================================================================

    # Convergence signal strength measures how strong the convergence signals are
    # Based on both magnitude and consistency

    # Magnitude: convergence index
    convergence_magnitude = convergence_index

    # Consistency: inverse of variance in convergence signals
    if len(convergence_signals) >= 2:
        convergence_std_dev = _compute_std_dev(convergence_signals)
        normalized_std_dev = min(convergence_std_dev / 0.5, 1.0)
        convergence_consistency = 1.0 - normalized_std_dev
    else:
        convergence_consistency = 0.5

    # Combine magnitude and consistency
    convergence_signal_strength = (
        0.65 * convergence_magnitude +
        0.35 * convergence_consistency
    )
    convergence_signal_strength = _clamp(convergence_signal_strength, 0.0, 1.0)

    # ========================================================================
    # STEP 12: DETERMINE DOMINANT FUTURE PATH
    # ========================================================================

    # Dominant future path is determined by the strongest signal source
    path_scores = {}

    # Check trajectory convergence dominant signal (Phase 46)
    if trajectory_convergence is not None and hasattr(trajectory_convergence, "dominant_convergence_signal"):
        dominant_signal = getattr(trajectory_convergence, "dominant_convergence_signal", None)
        if dominant_signal and dominant_signal != "UNKNOWN":
            path_scores[f"TRAJECTORY_{dominant_signal}"] = p46_convergence_index

    # Check scenario fusion dominant path (Phase 42)
    if scenario_fusion is not None and hasattr(scenario_fusion, "dominant_future_path"):
        dominant_path = getattr(scenario_fusion, "dominant_future_path", None)
        if dominant_path:
            path_scores[f"SCENARIO_{dominant_path}"] = p42_scenario_alignment

    # Check continuity vs drift
    if continuity is not None and drift is not None:
        continuity_strength = (p37_ncc + p37_icc + p37_css) / 3.0
        drift_strength = p35_drift_magnitude
        if continuity_strength > drift_strength:
            path_scores["CONTINUITY_STABLE"] = continuity_strength
        else:
            path_scores["DRIFT_ACTIVE"] = drift_strength

    # Check identity anchoring
    if identity is not None and p36_ida >= 0.65:
        identity_strength = (p36_ims + p36_iep + p36_ida) / 3.0
        path_scores["IDENTITY_ANCHORED"] = identity_strength

    if path_scores:
        # Sort by score (deterministic tie-breaking by alphabetical order)
        sorted_paths = sorted(
            path_scores.items(),
            key=lambda x: (-x[1], x[0])  # Descending score, ascending name
        )
        dominant_future_path = sorted_paths[0][0]
    else:
        dominant_future_path = "SYNTHESIS_UNCERTAIN"

    # ========================================================================
    # STEP 13: CLASSIFY SYNTHESIS BAND
    # ========================================================================

    if synthesis_integrity_score >= 0.70 and future_state_alignment_score >= 0.70:
        synthesis_band = "HIGH"
    elif synthesis_integrity_score >= 0.50 and future_state_alignment_score >= 0.50:
        synthesis_band = "MEDIUM"
    elif synthesis_integrity_score >= 0.35 or future_state_alignment_score >= 0.35:
        synthesis_band = "LOW"
    else:
        synthesis_band = "FRAGMENTED"

    # ========================================================================
    # STEP 14: GENERATE DIAGNOSTIC TAGS
    # ========================================================================

    tags = []

    # Synthesis integrity tags
    if synthesis_integrity_score >= 0.75:
        tags.append("SYNTHESIS_HIGHLY_RELIABLE")
    elif synthesis_integrity_score <= 0.35:
        tags.append("SYNTHESIS_FRAGILE")

    # Future alignment tags
    if future_state_alignment_score >= 0.75:
        tags.append("FUTURE_STRONGLY_ALIGNED")
    elif future_state_alignment_score <= 0.35:
        tags.append("FUTURE_POORLY_ALIGNED")

    # Future coherence tags
    if future_state_coherence_score >= 0.75:
        tags.append("FUTURE_COHERENCE_HIGH")
    elif future_state_coherence_score <= 0.35:
        tags.append("FUTURE_COHERENCE_LOW")

    # Divergence risk tags
    if future_divergence_risk >= 0.70:
        tags.append("DIVERGENCE_RISK_HIGH")
    elif future_divergence_risk <= 0.30:
        tags.append("DIVERGENCE_RISK_LOW")

    # Convergence strength tags
    if convergence_signal_strength >= 0.75:
        tags.append("CONVERGENCE_STRONG")
    elif convergence_signal_strength <= 0.35:
        tags.append("CONVERGENCE_WEAK")

    # Cross-horizon consistency tags
    if cross_horizon_consistency_score >= 0.75:
        tags.append("HORIZON_CONSISTENCY_HIGH")
    elif cross_horizon_consistency_score <= 0.35:
        tags.append("HORIZON_CONSISTENCY_LOW")

    # Synthesis band tags
    if synthesis_band == "HIGH":
        tags.append("SYNTHESIS_BAND_HIGH")
    elif synthesis_band == "FRAGMENTED":
        tags.append("SYNTHESIS_BAND_FRAGMENTED")

    # Pattern tags based on combinations
    if (convergence_signal_strength >= 0.70 and
        future_state_alignment_score >= 0.70 and
        future_divergence_risk <= 0.35):
        tags.append("TRAJECTORY_CONVERGING_STABLE")

    if (future_divergence_risk >= 0.70 and
        future_state_alignment_score <= 0.40 and
        convergence_signal_strength <= 0.40):
        tags.append("TRAJECTORY_DIVERGING_UNSTABLE")

    if (cross_horizon_consistency_score >= 0.70 and
        future_state_coherence_score >= 0.70):
        tags.append("FUTURE_PATH_COHERENT")

    if (synthesis_integrity_score >= 0.70 and
        future_state_coherence_score >= 0.70 and
        future_divergence_risk <= 0.35):
        tags.append("SYNTHESIS_OPTIMAL")

    if phases_available >= 6:
        tags.append("DATA_RICH_SYNTHESIS")
    elif phases_available <= 3:
        tags.append("DATA_SPARSE_SYNTHESIS")

    # Sort and deduplicate for determinism
    tags = sorted(set(tags))

    # ========================================================================
    # STEP 15: RETURN SNAPSHOT
    # ========================================================================

    return UnifiedTrajectoryScenarioSnapshot(
        synthesis_integrity_score=synthesis_integrity_score,
        future_state_alignment_score=future_state_alignment_score,
        future_state_coherence_score=future_state_coherence_score,
        cross_horizon_consistency_score=cross_horizon_consistency_score,
        future_divergence_risk=future_divergence_risk,
        convergence_signal_strength=convergence_signal_strength,
        dominant_future_path=dominant_future_path,
        synthesis_band=synthesis_band,
        diagnostic_tags=tags,
    )
