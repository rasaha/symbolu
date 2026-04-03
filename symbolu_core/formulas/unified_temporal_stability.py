"""
Unified Cross-Phase Temporal Stability Engine (UCTSE) v1.0 - Phase 49

Deterministic, zero-LLM, observation-only engine that synthesizes temporal
stability signals across all upstream forecasting, scenario, trajectory,
synthesis, and macro-stability phases.

This engine creates a holistic temporal stability assessment by integrating:
- Phase 35: Predictive Persona Drift (drift predictions)
- Phase 36: Identity Resonance Memory (identity memory)
- Phase 37: Adaptive Continuity Engine (continuity tracking)
- Phase 38: Temporal Coherence Forecasting (single-horizon forecasting)
- Phase 39: Multi-Horizon Temporal Forecasting (multi-horizon forecasting)
- Phase 41: Coherence-Regime Scenario Mapper (regime mapping)
- Phase 42: Scenario Fusion Engine (scenario fusion)
- Phase 44: Coherence-Scenario Alignment (scenario alignment)
- Phase 46: Trajectory Field Convergence (trajectory convergence)
- Phase 47: Unified Trajectory-Scenario Synthesis (unified synthesis)
- Phase 48: Macro-Stability Regulator (macro-stability)

UCTSE produces a unified temporal stability snapshot that quantifies:
1. Temporal Stability Index: Overall temporal stability across all phases
2. Drift Risk: Risk of temporal drift and instability
3. Predictive Entropy: Disagreement/uncertainty across forecasting subsystems
4. Future Consistency: Consistency of future-state predictions
5. Dominant Regime: Primary temporal stability driver
6. Stability Band: Classification (HIGH/MEDIUM/LOW/FRAGMENTED)
7. Diagnostic Tags: Pattern indicators

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
import math


@dataclass
class UnifiedTemporalStabilitySnapshot:
    """
    Immutable snapshot of Unified Cross-Phase Temporal Stability Engine computation.

    This snapshot synthesizes temporal stability signals from all upstream
    forecasting, scenario, trajectory, synthesis, and macro-stability phases.

    Fields:
        temporal_stability_index: [0.0, 1.0] - overall temporal stability
        drift_risk: [0.0, 1.0] - risk of temporal drift/instability
        predictive_entropy: [0.0, 1.0] - disagreement across forecasting subsystems
        future_consistency: [0.0, 1.0] - consistency of future predictions
        dominant_regime: Primary temporal stability driver identifier
        stability_band: "HIGH" | "MEDIUM" | "LOW" | "FRAGMENTED"
        diagnostic_tags: List of temporal stability pattern indicators
    """

    temporal_stability_index: float = 0.0
    drift_risk: float = 0.0
    predictive_entropy: float = 0.0
    future_consistency: float = 0.0
    dominant_regime: str = "unknown"
    stability_band: str = "LOW"
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


def compute_unified_temporal_stability(
    drift: Optional[Any] = None,
    identity: Optional[Any] = None,
    continuity: Optional[Any] = None,
    single_horizon: Optional[Any] = None,
    multi_horizon: Optional[Any] = None,
    scenario_regime: Optional[Any] = None,
    scenario_fusion: Optional[Any] = None,
    scenario_alignment: Optional[Any] = None,
    trajectory_convergence: Optional[Any] = None,
    synthesis_integrity: Optional[Any] = None,
    macro_stability: Optional[Any] = None,
) -> Optional[UnifiedTemporalStabilitySnapshot]:
    """
    Compute Unified Cross-Phase Temporal Stability Engine (UCTSE) v1.0.

    This function synthesizes temporal stability signals from Phases 35-48
    to produce a unified temporal stability assessment.

    Args:
        drift: Phase 35 PredictivePersonaDriftSnapshot
        identity: Phase 36 IdentityResonanceMemorySnapshot
        continuity: Phase 37 AdaptiveContinuitySnapshot
        single_horizon: Phase 38 TemporalCoherenceForecastSnapshot
        multi_horizon: Phase 39 MultiHorizonForecastSnapshot
        scenario_regime: Phase 41 CoherenceRegimeSnapshot
        scenario_fusion: Phase 42 ScenarioFusionSnapshot
        scenario_alignment: Phase 44 CoherenceScenarioAlignmentSnapshot
        trajectory_convergence: Phase 46 TrajectoryFieldConvergenceSnapshot
        synthesis_integrity: Phase 47 UnifiedTrajectoryScenarioSnapshot
        macro_stability: Phase 48 MacroStabilitySnapshot

    Returns:
        UnifiedTemporalStabilitySnapshot or None if insufficient data

    Formula Design:
        - Temporal Stability Index: Weighted synthesis of all stability signals
        - Drift Risk: Complement of stability + drift magnitude signals
        - Predictive Entropy: Normalized disagreement across forecasting signals
        - Future Consistency: Alignment of future-state predictions
        - Dominant Regime: Highest contributing dimension (drift/identity/continuity/horizon/scenario/synthesis)

        Stability Band Classification:
            * HIGH: TSI >= 0.75
            * MEDIUM: TSI >= 0.50
            * LOW: TSI >= 0.30
            * FRAGMENTED: TSI < 0.30

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
        single_horizon is not None,
        multi_horizon is not None,
        scenario_regime is not None,
        scenario_fusion is not None,
        scenario_alignment is not None,
        trajectory_convergence is not None,
        synthesis_integrity is not None,
        macro_stability is not None,
    ])

    # Need at least 4 phases for meaningful temporal stability assessment
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
    p38_forecast_strength = _safe_get(single_horizon, "forecast_strength", 0.0)
    p38_coherence_slope = _safe_get(single_horizon, "coherence_slope", 0.0)

    # Phase 39 - Multi-Horizon Temporal Forecasting
    p39_fci = _safe_get(multi_horizon, "forecast_consensus_index", 0.0)
    p39_fse = _safe_get(multi_horizon, "future_stability_envelope", 0.0)

    # Phase 41 - Coherence-Regime Scenario Mapper
    p41_regime_band = None
    if scenario_regime is not None:
        if hasattr(scenario_regime, "regime_band"):
            p41_regime_band = getattr(scenario_regime, "regime_band", None)
        elif isinstance(scenario_regime, dict):
            p41_regime_band = scenario_regime.get("regime_band", None)

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

    # Phase 47 - Unified Trajectory-Scenario Synthesis
    p47_synthesis_integrity = _safe_get(synthesis_integrity, "synthesis_integrity_score", 0.0)
    p47_future_alignment = _safe_get(synthesis_integrity, "future_state_alignment_score", 0.0)
    p47_future_coherence = _safe_get(synthesis_integrity, "future_state_coherence_score", 0.0)
    p47_convergence_strength = _safe_get(synthesis_integrity, "convergence_signal_strength", 0.0)

    # Phase 48 - Macro-Stability Regulator
    p48_macro_stability_index = _safe_get(macro_stability, "macro_stability_index", 0.0)
    p48_macro_divergence = _safe_get(macro_stability, "macro_divergence_index", 0.0)
    p48_macro_predictive_confidence = _safe_get(macro_stability, "macro_predictive_confidence", 0.0)
    p48_macro_identity_resilience = _safe_get(macro_stability, "macro_identity_resilience", 0.0)

    # ========================================================================
    # STEP 3: COMPUTE TEMPORAL STABILITY INDEX
    # ========================================================================

    # Temporal stability index is a weighted synthesis of all stability signals
    # Priority: Macro-stability (highest) → Synthesis → Convergence → Horizons → Identity/Continuity → Drift
    stability_signals = []
    stability_weights = []

    # Phase 48 - Macro-stability index (master stability signal)
    if macro_stability is not None:
        stability_signals.append(p48_macro_stability_index)
        stability_weights.append(0.22)

    # Phase 47 - Synthesis integrity (high priority)
    if synthesis_integrity is not None:
        stability_signals.append(p47_synthesis_integrity)
        stability_weights.append(0.18)

    # Phase 46 - Trajectory stability (high priority)
    if trajectory_convergence is not None:
        stability_signals.append(p46_stability_index)
        stability_weights.append(0.15)

    # Phase 39 - Future stability envelope (high priority)
    if multi_horizon is not None:
        stability_signals.append(p39_fse)
        stability_weights.append(0.13)

    # Phase 44 - Stability agreement (moderate priority)
    if scenario_alignment is not None:
        stability_signals.append(p44_stability_agreement)
        stability_weights.append(0.10)

    # Phase 42 - Multi-regime consensus (moderate priority)
    if scenario_fusion is not None:
        stability_signals.append(p42_multi_regime_consensus)
        stability_weights.append(0.08)

    # Phase 37 - Continuity stability (supporting)
    if continuity is not None:
        stability_signals.append(p37_css)
        stability_weights.append(0.06)

    # Phase 36 - Identity drift anchoring (supporting)
    if identity is not None:
        stability_signals.append(p36_ida)
        stability_weights.append(0.05)

    # Phase 38 - Forecast strength (supporting)
    if single_horizon is not None:
        stability_signals.append(p38_forecast_strength)
        stability_weights.append(0.03)

    if stability_signals:
        total_weight = sum(stability_weights)
        normalized_weights = [w / total_weight for w in stability_weights]
        temporal_stability_index = sum(
            sig * weight for sig, weight in zip(stability_signals, normalized_weights)
        )
        temporal_stability_index = _clamp(temporal_stability_index, 0.0, 1.0)
    else:
        temporal_stability_index = 0.5  # Default moderate

    # ========================================================================
    # STEP 4: COMPUTE DRIFT RISK
    # ========================================================================

    # Drift risk combines divergence signals and drift magnitude
    drift_risk_signals = []
    drift_risk_weights = []

    # Phase 48 - Macro-divergence (highest weight)
    if macro_stability is not None:
        drift_risk_signals.append(p48_macro_divergence)
        drift_risk_weights.append(0.25)

    # Phase 46 - Trajectory divergence (high weight)
    if trajectory_convergence is not None:
        drift_risk_signals.append(p46_divergence_index)
        drift_risk_weights.append(0.20)

    # Phase 42 - Scenario divergence (high weight)
    if scenario_fusion is not None:
        drift_risk_signals.append(p42_scenario_divergence)
        drift_risk_weights.append(0.18)

    # Phase 44 - Conflict index (moderate weight)
    if scenario_alignment is not None:
        drift_risk_signals.append(p44_conflict_index)
        drift_risk_weights.append(0.15)

    # Phase 35 - Drift magnitude (moderate weight)
    if drift is not None:
        drift_risk_signals.append(p35_drift_magnitude)
        drift_risk_weights.append(0.12)

    # Instability from continuity (low continuity = high risk)
    if continuity is not None:
        continuity_instability = 1.0 - p37_css
        drift_risk_signals.append(continuity_instability)
        drift_risk_weights.append(0.10)

    if drift_risk_signals:
        total_weight = sum(drift_risk_weights)
        normalized_weights = [w / total_weight for w in drift_risk_weights]
        drift_risk = sum(
            sig * weight for sig, weight in zip(drift_risk_signals, normalized_weights)
        )
        drift_risk = _clamp(drift_risk, 0.0, 1.0)
    else:
        drift_risk = 0.5  # Default moderate

    # ========================================================================
    # STEP 5: COMPUTE PREDICTIVE ENTROPY
    # ========================================================================

    # Predictive entropy measures disagreement/uncertainty across forecasting subsystems
    forecast_signals = []

    # Collect all forecasting/alignment signals
    if single_horizon is not None:
        forecast_signals.append(p38_forecast_strength)

    if multi_horizon is not None:
        forecast_signals.append(p39_fci)
        forecast_signals.append(p39_fse)

    if scenario_alignment is not None:
        forecast_signals.append(p44_alignment_score)

    if scenario_fusion is not None:
        forecast_signals.append(p42_scenario_alignment)

    if trajectory_convergence is not None:
        forecast_signals.append(p46_convergence_index)

    if synthesis_integrity is not None:
        forecast_signals.append(p47_future_alignment)
        forecast_signals.append(p47_convergence_strength)

    if macro_stability is not None:
        forecast_signals.append(p48_macro_predictive_confidence)

    # Compute entropy as normalized standard deviation
    if len(forecast_signals) >= 2:
        forecast_std_dev = _compute_std_dev(forecast_signals)
        # Normalize std dev to [0, 1] (max std dev for values in [0,1] is 0.5)
        predictive_entropy = min(forecast_std_dev / 0.5, 1.0)
        predictive_entropy = _clamp(predictive_entropy, 0.0, 1.0)
    else:
        predictive_entropy = 0.5  # Default moderate

    # ========================================================================
    # STEP 6: COMPUTE FUTURE CONSISTENCY
    # ========================================================================

    # Future consistency measures alignment of future-state predictions
    consistency_signals = []
    consistency_weights = []

    # Phase 47 - Future state alignment (highest weight)
    if synthesis_integrity is not None:
        consistency_signals.append(p47_future_alignment)
        consistency_weights.append(0.28)

    # Phase 39 - Forecast consensus (high weight)
    if multi_horizon is not None:
        consistency_signals.append(p39_fci)
        consistency_weights.append(0.24)

    # Phase 46 - Convergence index (high weight)
    if trajectory_convergence is not None:
        consistency_signals.append(p46_convergence_index)
        consistency_weights.append(0.20)

    # Phase 44 - Alignment score (moderate weight)
    if scenario_alignment is not None:
        consistency_signals.append(p44_alignment_score)
        consistency_weights.append(0.15)

    # Phase 42 - Scenario alignment (supporting weight)
    if scenario_fusion is not None:
        consistency_signals.append(p42_scenario_alignment)
        consistency_weights.append(0.13)

    if consistency_signals:
        total_weight = sum(consistency_weights)
        normalized_weights = [w / total_weight for w in consistency_weights]
        future_consistency = sum(
            sig * weight for sig, weight in zip(consistency_signals, normalized_weights)
        )
        future_consistency = _clamp(future_consistency, 0.0, 1.0)
    else:
        future_consistency = 0.5  # Default moderate

    # ========================================================================
    # STEP 7: DETERMINE DOMINANT REGIME
    # ========================================================================

    # Dominant regime is the highest contributing dimension
    regime_scores = {}

    # Drift-led regime (high drift magnitude)
    if drift is not None:
        regime_scores["drift-led"] = p35_drift_magnitude

    # Identity-led regime (high identity memory/anchoring)
    if identity is not None:
        identity_strength = (p36_ims + p36_iep + p36_ida) / 3.0
        regime_scores["identity-led"] = identity_strength

    # Continuity-led regime (high continuity stability)
    if continuity is not None:
        continuity_strength = (p37_ncc + p37_icc + p37_css) / 3.0
        regime_scores["continuity-led"] = continuity_strength

    # Horizon-led regime (high forecast consensus)
    if multi_horizon is not None:
        horizon_strength = (p39_fci + p39_fse) / 2.0
        regime_scores["horizon-led"] = horizon_strength

    # Scenario-led regime (high scenario alignment)
    if scenario_alignment is not None and scenario_fusion is not None:
        scenario_strength = (p44_alignment_score + p42_scenario_alignment) / 2.0
        regime_scores["scenario-led"] = scenario_strength

    # Synthesis-led regime (high synthesis integrity)
    if synthesis_integrity is not None:
        synthesis_strength = (p47_synthesis_integrity + p47_future_alignment) / 2.0
        regime_scores["synthesis-led"] = synthesis_strength

    # Macro-led regime (high macro-stability)
    if macro_stability is not None:
        macro_strength = (p48_macro_stability_index + p48_macro_predictive_confidence) / 2.0
        regime_scores["macro-led"] = macro_strength

    if regime_scores:
        # Sort by score (deterministic tie-breaking by alphabetical order)
        sorted_regimes = sorted(
            regime_scores.items(),
            key=lambda x: (-x[1], x[0])  # Descending score, ascending name
        )
        dominant_regime = sorted_regimes[0][0]
    else:
        dominant_regime = "unknown"

    # ========================================================================
    # STEP 8: CLASSIFY STABILITY BAND
    # ========================================================================

    if temporal_stability_index >= 0.75:
        stability_band = "HIGH"
    elif temporal_stability_index >= 0.50:
        stability_band = "MEDIUM"
    elif temporal_stability_index >= 0.30:
        stability_band = "LOW"
    else:
        stability_band = "FRAGMENTED"

    # ========================================================================
    # STEP 9: GENERATE DIAGNOSTIC TAGS
    # ========================================================================

    tags = []

    # Temporal stability tags
    if temporal_stability_index >= 0.80:
        tags.append("TEMPORAL_STABILITY_OPTIMAL")
    elif temporal_stability_index >= 0.75:
        tags.append("TEMPORAL_STABILITY_STRONG")
    elif temporal_stability_index <= 0.30:
        tags.append("TEMPORAL_STABILITY_FRAGILE")

    # Drift risk tags
    if drift_risk >= 0.75:
        tags.append("DRIFT_RISK_CRITICAL")
    elif drift_risk >= 0.60:
        tags.append("DRIFT_RISK_ELEVATED")
    elif drift_risk <= 0.30:
        tags.append("DRIFT_RISK_MINIMAL")

    # Predictive entropy tags
    if predictive_entropy >= 0.70:
        tags.append("PREDICTIVE_ENTROPY_HIGH")
    elif predictive_entropy <= 0.30:
        tags.append("PREDICTIVE_ENTROPY_LOW")

    # Future consistency tags
    if future_consistency >= 0.75:
        tags.append("FUTURE_CONSISTENCY_STRONG")
    elif future_consistency <= 0.35:
        tags.append("FUTURE_CONSISTENCY_WEAK")

    # Stability band tags
    if stability_band == "HIGH":
        tags.append("STABILITY_BAND_HIGH")
    elif stability_band == "FRAGMENTED":
        tags.append("STABILITY_BAND_FRAGMENTED")

    # Dominant regime tags
    if dominant_regime != "unknown":
        tags.append(f"REGIME_{dominant_regime.upper().replace('-', '_')}")

    # Pattern tags based on combinations
    if (temporal_stability_index >= 0.75 and
        future_consistency >= 0.75 and
        drift_risk <= 0.30):
        tags.append("TEMPORAL_SYSTEM_OPTIMAL")

    if (drift_risk >= 0.70 and
        predictive_entropy >= 0.60 and
        future_consistency <= 0.40):
        tags.append("TEMPORAL_SYSTEM_UNSTABLE")

    if (temporal_stability_index >= 0.70 and
        predictive_entropy <= 0.35):
        tags.append("FORECAST_CONSENSUS_STABLE")

    if (future_consistency >= 0.70 and
        temporal_stability_index >= 0.65):
        tags.append("TEMPORAL_ALIGNMENT_STRONG")

    # Cross-phase integration tags
    if macro_stability is not None and p48_macro_stability_index >= 0.75:
        tags.append("MACRO_STABILITY_CONFIRMED")

    if synthesis_integrity is not None and p47_synthesis_integrity >= 0.75:
        tags.append("SYNTHESIS_INTEGRITY_CONFIRMED")

    if (trajectory_convergence is not None and
        multi_horizon is not None and
        p46_convergence_index >= 0.70 and
        p39_fci >= 0.70):
        tags.append("TRAJECTORY_HORIZON_ALIGNED")

    # Data richness tags
    if phases_available >= 8:
        tags.append("TEMPORAL_DATA_RICH")
    elif phases_available <= 4:
        tags.append("TEMPORAL_DATA_SPARSE")

    # Sort and deduplicate for determinism
    tags = sorted(set(tags))

    # ========================================================================
    # STEP 10: RETURN SNAPSHOT
    # ========================================================================

    return UnifiedTemporalStabilitySnapshot(
        temporal_stability_index=temporal_stability_index,
        drift_risk=drift_risk,
        predictive_entropy=predictive_entropy,
        future_consistency=future_consistency,
        dominant_regime=dominant_regime,
        stability_band=stability_band,
        diagnostic_tags=tags,
    )
