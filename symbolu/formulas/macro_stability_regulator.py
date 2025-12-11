"""
Macro-Stability Regulator (MSR) v1.0 - Phase 48

Deterministic, zero-LLM, observation-only engine that regulates and monitors
macro-level stability across the entire forecasting and scenario subsystem.

This engine synthesizes signals from:
- Phase 35: Predictive Persona Drift (drift predictions)
- Phase 36: Identity Resonance Memory (identity memory)
- Phase 37: Adaptive Continuity Engine (continuity tracking)
- Phase 38: Temporal Coherence Forecasting (single-horizon forecasting)
- Phase 39: Multi-Horizon Temporal Forecasting (multi-horizon forecasting)
- Phase 42: Scenario Fusion Engine (scenario fusion)
- Phase 44: Coherence-Scenario Alignment (scenario alignment)
- Phase 46: Trajectory Field Convergence (trajectory convergence)
- Phase 47: Unified Trajectory-Scenario Synthesis (unified synthesis)

MSR produces a regulatory snapshot that quantifies:
1. Macro-stability index (overall system stability)
2. Macro-divergence index (system fragmentation risk)
3. Macro-predictive confidence (forecasting subsystem reliability)
4. Macro-identity resilience (identity/continuity stability)
5. Stability band classification (high/medium/low/fragmented)
6. Diagnostic tags for regulatory patterns

CRITICAL INVARIANTS:
    - Zero-LLM: Purely rule-based, deterministic math only
    - Observation-only: NO changes to routing, TTOR, MLCR, mappers, Fusion, DHA, Renderer
    - Metadata-only persona integration: NO tone or semantic changes
    - Diagnostics/UI only: Feeds coherence state, session summary, unified API, and DILchat badges
    - Non-invasive: Does not modify any existing coherence formulas or behaviors
    - Backward-compatible: All existing tests remain green
    - Deterministic: Same inputs → same outputs always
    - Fully bounded: All outputs [0.0, 1.0]
    - Graceful degradation: Returns None if insufficient data (<4 upstream phases)
"""

from dataclasses import dataclass, field
from typing import List, Optional, Any


@dataclass
class MacroStabilitySnapshot:
    """
    Immutable snapshot of Macro-Stability Regulator computation.

    This snapshot regulates macro-level stability across the entire forecasting
    and scenario subsystem.

    Fields:
        macro_stability_index: [0.0, 1.0] - overall macro-level system stability
        macro_divergence_index: [0.0, 1.0] - macro-level fragmentation/divergence risk
        macro_predictive_confidence: [0.0, 1.0] - forecasting subsystem reliability
        macro_identity_resilience: [0.0, 1.0] - identity/continuity stability
        stability_band: "high" | "medium" | "low" | "fragmented"
        diagnostic_tags: List of regulatory pattern indicators
    """

    macro_stability_index: float = 0.0
    macro_divergence_index: float = 0.0
    macro_predictive_confidence: float = 0.0
    macro_identity_resilience: float = 0.0
    stability_band: str = "low"
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


def compute_macro_stability_regulator(
    drift: Optional[Any] = None,
    identity: Optional[Any] = None,
    continuity: Optional[Any] = None,
    forecast: Optional[Any] = None,
    multi_horizon: Optional[Any] = None,
    scenario_fusion: Optional[Any] = None,
    scenario_alignment: Optional[Any] = None,
    convergence: Optional[Any] = None,
    synthesis: Optional[Any] = None,
) -> Optional[MacroStabilitySnapshot]:
    """
    Compute Macro-Stability Regulator (MSR) v1.0.

    This function synthesizes signals from Phases 35-47 to regulate and monitor
    macro-level system stability.

    Args:
        drift: Phase 35 PredictivePersonaDriftSnapshot
        identity: Phase 36 IdentityResonanceMemorySnapshot
        continuity: Phase 37 AdaptiveContinuitySnapshot
        forecast: Phase 38 TemporalCoherenceForecastSnapshot
        multi_horizon: Phase 39 MultiHorizonForecastSnapshot
        scenario_fusion: Phase 42 ScenarioFusionSnapshot
        scenario_alignment: Phase 44 CoherenceScenarioAlignmentSnapshot
        convergence: Phase 46 TrajectoryFieldConvergenceSnapshot
        synthesis: Phase 47 UnifiedTrajectoryScenarioSnapshot

    Returns:
        MacroStabilitySnapshot or None if insufficient data

    Formula Design:
        - Macro-Stability Index: Weighted mean of upstream stability signals
        - Macro-Divergence Index: 1.0 - Macro-Stability Index
        - Macro-Predictive Confidence: Alignment of forecasting subsystems
        - Macro-Identity Resilience: Identity/continuity/drift stability

        Stability Band Classification:
            * high: MSI >= 0.70 and MPC >= 0.70
            * medium: MSI >= 0.50 and MPC >= 0.50
            * low: MSI >= 0.35 or MPC >= 0.35
            * fragmented: MSI < 0.35 and MPC < 0.35

    Graceful Degradation:
        Returns None if fewer than 4 upstream phases are available.
    """
    # ========================================================================
    # STEP 1: VALIDATE INPUT AND COUNT AVAILABLE PHASES
    # ========================================================================

    phases_available = sum([
        drift is not None,
        identity is not None,
        continuity is not None,
        forecast is not None,
        multi_horizon is not None,
        scenario_fusion is not None,
        scenario_alignment is not None,
        convergence is not None,
        synthesis is not None,
    ])

    # Need at least 4 phases for meaningful macro-stability regulation
    if phases_available < 4:
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
    p38_forecast_strength = _safe_get(forecast, "forecast_strength", 0.0)
    p38_coherence_slope = _safe_get(forecast, "coherence_slope", 0.0)

    # Phase 39 - Multi-Horizon Temporal Forecasting
    p39_fci = _safe_get(multi_horizon, "forecast_consensus_index", 0.0)
    p39_fse = _safe_get(multi_horizon, "future_stability_envelope", 0.0)

    # Phase 42 - Scenario Fusion Engine
    p42_scenario_alignment = _safe_get(scenario_fusion, "scenario_alignment_score", 0.0)
    p42_scenario_divergence = _safe_get(scenario_fusion, "scenario_divergence_index", 0.0)
    p42_multi_regime_consensus = _safe_get(scenario_fusion, "multi_regime_consensus", 0.0)

    # Phase 44 - Coherence-Scenario Alignment
    p44_alignment_score = _safe_get(scenario_alignment, "alignment_score", 0.0)
    p44_conflict_index = _safe_get(scenario_alignment, "conflict_index", 0.0)
    p44_stability_agreement = _safe_get(scenario_alignment, "stability_agreement", 0.0)

    # Phase 46 - Trajectory Field Convergence
    p46_convergence_index = _safe_get(convergence, "convergence_index", 0.0)
    p46_divergence_index = _safe_get(convergence, "divergence_index", 0.0)
    p46_stability_index = _safe_get(convergence, "stability_index", 0.0)

    # Phase 47 - Unified Trajectory-Scenario Synthesis
    p47_synthesis_integrity = _safe_get(synthesis, "synthesis_integrity_score", 0.0)
    p47_future_alignment = _safe_get(synthesis, "future_state_alignment_score", 0.0)
    p47_future_coherence = _safe_get(synthesis, "future_state_coherence_score", 0.0)
    p47_convergence_strength = _safe_get(synthesis, "convergence_signal_strength", 0.0)

    # ========================================================================
    # STEP 3: COMPUTE MACRO-STABILITY INDEX
    # ========================================================================

    # Macro-stability index measures overall system stability
    # High stability = high synthesis integrity + high convergence + low divergence
    stability_signals = []
    stability_weights = []

    # Phase 47 synthesis integrity - highest weight (master stability signal)
    if synthesis is not None:
        stability_signals.append(p47_synthesis_integrity)
        stability_weights.append(0.25)

    # Phase 46 trajectory stability - high weight
    if convergence is not None:
        stability_signals.append(p46_stability_index)
        stability_weights.append(0.20)

    # Phase 39 future stability envelope - high weight
    if multi_horizon is not None:
        stability_signals.append(p39_fse)
        stability_weights.append(0.15)

    # Phase 44 stability agreement - moderate weight
    if scenario_alignment is not None:
        stability_signals.append(p44_stability_agreement)
        stability_weights.append(0.12)

    # Phase 42 multi-regime consensus - moderate weight
    if scenario_fusion is not None:
        stability_signals.append(p42_multi_regime_consensus)
        stability_weights.append(0.10)

    # Phase 37 continuity stability - supporting weight
    if continuity is not None:
        stability_signals.append(p37_css)
        stability_weights.append(0.08)

    # Phase 36 identity drift anchoring - supporting weight
    if identity is not None:
        stability_signals.append(p36_ida)
        stability_weights.append(0.06)

    # Phase 35 drift stability - supporting weight
    if drift is not None:
        stability_signals.append(p35_drift_stability)
        stability_weights.append(0.04)

    if stability_signals:
        total_weight = sum(stability_weights)
        normalized_weights = [w / total_weight for w in stability_weights]
        macro_stability_index = sum(
            sig * weight for sig, weight in zip(stability_signals, normalized_weights)
        )
        macro_stability_index = _clamp(macro_stability_index, 0.0, 1.0)
    else:
        macro_stability_index = 0.5  # Default moderate

    # ========================================================================
    # STEP 4: COMPUTE MACRO-DIVERGENCE INDEX
    # ========================================================================

    # Macro-divergence index is the complement of macro-stability index
    # This represents the risk of macro-level system fragmentation
    macro_divergence_index = 1.0 - macro_stability_index
    macro_divergence_index = _clamp(macro_divergence_index, 0.0, 1.0)

    # ========================================================================
    # STEP 5: COMPUTE MACRO-PREDICTIVE CONFIDENCE
    # ========================================================================

    # Macro-predictive confidence measures how aligned and reliable the
    # forecasting subsystems are (Phases 38, 39, 42, 44, 46, 47)
    predictive_signals = []
    predictive_weights = []

    # Phase 47 future state alignment - highest weight
    if synthesis is not None:
        predictive_signals.append(p47_future_alignment)
        predictive_weights.append(0.25)

    # Phase 47 convergence signal strength - high weight
    if synthesis is not None:
        predictive_signals.append(p47_convergence_strength)
        predictive_weights.append(0.20)

    # Phase 46 convergence index - high weight
    if convergence is not None:
        predictive_signals.append(p46_convergence_index)
        predictive_weights.append(0.18)

    # Phase 39 forecast consensus index - high weight
    if multi_horizon is not None:
        predictive_signals.append(p39_fci)
        predictive_weights.append(0.15)

    # Phase 44 alignment score - moderate weight
    if scenario_alignment is not None:
        predictive_signals.append(p44_alignment_score)
        predictive_weights.append(0.12)

    # Phase 42 scenario alignment - moderate weight
    if scenario_fusion is not None:
        predictive_signals.append(p42_scenario_alignment)
        predictive_weights.append(0.10)

    if predictive_signals:
        total_weight = sum(predictive_weights)
        normalized_weights = [w / total_weight for w in predictive_weights]
        macro_predictive_confidence = sum(
            sig * weight for sig, weight in zip(predictive_signals, normalized_weights)
        )
        macro_predictive_confidence = _clamp(macro_predictive_confidence, 0.0, 1.0)
    else:
        macro_predictive_confidence = 0.5  # Default moderate

    # ========================================================================
    # STEP 6: COMPUTE MACRO-IDENTITY RESILIENCE
    # ========================================================================

    # Macro-identity resilience measures how stable identity/continuity/drift
    # subsystems are (Phases 35, 36, 37)
    resilience_signals = []
    resilience_weights = []

    # Phase 37 continuity metrics - high weight
    if continuity is not None:
        continuity_avg = (p37_ncc + p37_icc + p37_css) / 3.0
        resilience_signals.append(continuity_avg)
        resilience_weights.append(0.35)

    # Phase 36 identity metrics - high weight
    if identity is not None:
        identity_avg = (p36_ims + p36_iep + p36_ida) / 3.0
        resilience_signals.append(identity_avg)
        resilience_weights.append(0.35)

    # Phase 35 drift stability (inverse of drift magnitude) - moderate weight
    if drift is not None:
        drift_resilience = (p35_drift_stability + (1.0 - p35_drift_magnitude)) / 2.0
        resilience_signals.append(drift_resilience)
        resilience_weights.append(0.30)

    if resilience_signals:
        total_weight = sum(resilience_weights)
        normalized_weights = [w / total_weight for w in resilience_weights]
        macro_identity_resilience = sum(
            sig * weight for sig, weight in zip(resilience_signals, normalized_weights)
        )
        macro_identity_resilience = _clamp(macro_identity_resilience, 0.0, 1.0)
    else:
        macro_identity_resilience = 0.5  # Default moderate

    # ========================================================================
    # STEP 7: CLASSIFY STABILITY BAND
    # ========================================================================

    if macro_stability_index >= 0.70 and macro_predictive_confidence >= 0.70:
        stability_band = "high"
    elif macro_stability_index >= 0.50 and macro_predictive_confidence >= 0.50:
        stability_band = "medium"
    elif macro_stability_index >= 0.35 or macro_predictive_confidence >= 0.35:
        stability_band = "low"
    else:
        stability_band = "fragmented"

    # ========================================================================
    # STEP 8: GENERATE DIAGNOSTIC TAGS
    # ========================================================================

    tags = []

    # Stability consensus tags
    if macro_stability_index >= 0.75:
        tags.append("STABILITY_CONSENSUS")
    elif macro_stability_index <= 0.35:
        tags.append("HIGH_DIVERGENCE_RISK")

    # Identity resilience tags
    if macro_identity_resilience >= 0.75:
        tags.append("IDENTITY_RESILIENT")
    elif macro_identity_resilience <= 0.40:
        tags.append("IDENTITY_DRIFT_PRESSURE")

    # Predictive confidence tags
    if macro_predictive_confidence >= 0.75:
        tags.append("PREDICTIVE_ALIGNMENT_STRONG")
    elif macro_predictive_confidence <= 0.40:
        tags.append("PREDICTIVE_ALIGNMENT_WEAK")

    # Multi-horizon inconsistency detection
    if multi_horizon is not None and p39_fci <= 0.40:
        tags.append("MULTI_HORIZON_INCONSISTENCY")

    # Scenario contradiction detection
    if (scenario_fusion is not None and scenario_alignment is not None and
        p42_scenario_divergence >= 0.70 and p44_conflict_index >= 0.60):
        tags.append("SCENARIO_CONTRADICTION")

    # Synthesis conflict detection
    if synthesis is not None and p47_synthesis_integrity <= 0.40:
        tags.append("SYNTHESIS_CONFLICT")

    # Stability band tags
    if stability_band == "high":
        tags.append("MACRO_STABILITY_HIGH")
    elif stability_band == "fragmented":
        tags.append("MACRO_STABILITY_FRAGMENTED")

    # Pattern tags based on combinations
    if (macro_stability_index >= 0.70 and
        macro_predictive_confidence >= 0.70 and
        macro_identity_resilience >= 0.70):
        tags.append("MACRO_SYSTEM_OPTIMAL")

    if (macro_divergence_index >= 0.70 and
        macro_predictive_confidence <= 0.40 and
        macro_identity_resilience <= 0.40):
        tags.append("MACRO_SYSTEM_UNSTABLE")

    if (macro_stability_index >= 0.65 and
        macro_identity_resilience >= 0.65):
        tags.append("IDENTITY_CONTINUITY_STABLE")

    if (macro_predictive_confidence >= 0.70 and
        convergence is not None and p46_convergence_index >= 0.70):
        tags.append("FORECAST_TRAJECTORY_ALIGNED")

    if phases_available >= 7:
        tags.append("MACRO_DATA_RICH")
    elif phases_available <= 4:
        tags.append("MACRO_DATA_SPARSE")

    # Sort and deduplicate for determinism
    tags = sorted(set(tags))

    # ========================================================================
    # STEP 9: RETURN SNAPSHOT
    # ========================================================================

    return MacroStabilitySnapshot(
        macro_stability_index=macro_stability_index,
        macro_divergence_index=macro_divergence_index,
        macro_predictive_confidence=macro_predictive_confidence,
        macro_identity_resilience=macro_identity_resilience,
        stability_band=stability_band,
        diagnostic_tags=tags,
    )
