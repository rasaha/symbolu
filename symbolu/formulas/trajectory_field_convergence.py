"""
Trajectory Field Convergence Engine (TFCE) v1.0 - Phase 46

Deterministic, zero-LLM, observation-only engine that measures how multiple
predictive trajectories are converging vs. diverging over time.

This engine analyzes trajectory alignment across:
- Phase 35: Predictive Persona Drift (drift trajectory)
- Phase 36: Identity Resonance Memory (identity trajectory)
- Phase 37: Adaptive Continuity Engine (continuity trajectory)
- Phase 38: Temporal Coherence Forecasting (symbolic trajectory)
- Phase 39: Multi-Horizon Temporal Forecasting (scenario trajectory)
- Phase 42: Scenario Fusion Engine (multi-horizon temporal trajectory)
- Phase 44: Coherence-Scenario Alignment

TFCE produces a unified trajectory convergence snapshot that quantifies whether
the system's predicted paths are stabilizing toward a coherent future or
fragmenting across possibilities.

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
from typing import List, Optional, Any, Dict
import math


@dataclass
class TrajectoryFieldConvergenceSnapshot:
    """
    Immutable snapshot of Trajectory Field Convergence Engine computation.

    This snapshot measures how multiple predictive trajectories are converging
    vs. diverging over time.

    Fields:
        drift_alignment: Drift trajectory alignment [0.0, 1.0] (optional)
        identity_alignment: Identity trajectory alignment [0.0, 1.0] (optional)
        symbolic_alignment: Symbolic trajectory alignment [0.0, 1.0] (optional)
        continuity_alignment: Continuity trajectory alignment [0.0, 1.0] (optional)
        scenario_alignment: Scenario trajectory alignment [0.0, 1.0] (optional)
        horizon_alignment: Multi-horizon temporal alignment [0.0, 1.0] (optional)
        convergence_index: Overall convergence measure [0.0, 1.0]
        divergence_index: Overall divergence measure [0.0, 1.0]
        stability_index: Trajectory stability measure [0.0, 1.0]
        convergence_band: Convergence classification: "high" | "medium" | "low" | "fragmented"
        dominant_convergence_signal: Primary convergence signal descriptor
        diagnostic_tags: List of diagnostic tags
    """

    drift_alignment: Optional[float] = None
    identity_alignment: Optional[float] = None
    symbolic_alignment: Optional[float] = None
    continuity_alignment: Optional[float] = None
    scenario_alignment: Optional[float] = None
    horizon_alignment: Optional[float] = None
    convergence_index: float = 0.0
    divergence_index: float = 0.0
    stability_index: float = 0.0
    convergence_band: str = "low"
    dominant_convergence_signal: str = "UNKNOWN"
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


def _compute_pairwise_alignment(values: List[float]) -> float:
    """
    Compute pairwise alignment using normalized distance.

    High alignment = values are close together
    Low alignment = values are far apart

    Args:
        values: List of float values in [0.0, 1.0]

    Returns:
        float: Alignment score [0.0, 1.0]
    """
    if not values or len(values) < 2:
        return 0.5  # Default moderate alignment

    # Compute pairwise distances
    total_distance = 0.0
    pair_count = 0

    for i in range(len(values)):
        for j in range(i + 1, len(values)):
            total_distance += abs(values[i] - values[j])
            pair_count += 1

    if pair_count == 0:
        return 0.5

    # Average pairwise distance
    avg_distance = total_distance / pair_count

    # Convert distance to alignment (1.0 = perfect alignment, 0.0 = maximum divergence)
    # Maximum possible average distance is 1.0 (when values are at extremes)
    alignment = 1.0 - _clamp(avg_distance, 0.0, 1.0)

    return alignment


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


def compute_trajectory_field_convergence(
    predictive_drift_phase35: Optional[Any] = None,
    identity_resonance_phase36: Optional[Any] = None,
    continuity_phase37: Optional[Any] = None,
    forecast_phase38: Optional[Any] = None,
    multi_horizon_phase39: Optional[Any] = None,
    scenario_fusion_phase42: Optional[Any] = None,
    mtsf_phase45: Optional[Any] = None,
) -> Optional[TrajectoryFieldConvergenceSnapshot]:
    """
    Compute Trajectory Field Convergence Engine (TFCE) v1.0.

    This function measures how multiple predictive trajectories (drift, identity,
    symbolic, continuity, scenario, and multi-horizon temporal) are converging
    vs. diverging over time.

    Args:
        predictive_drift_phase35: Phase 35 PredictivePersonaDriftSnapshot
        identity_resonance_phase36: Phase 36 IdentityResonanceMemorySnapshot
        continuity_phase37: Phase 37 AdaptiveContinuitySnapshot
        forecast_phase38: Phase 38 TemporalCoherenceForecastSnapshot
        multi_horizon_phase39: Phase 39 MultiHorizonForecastSnapshot
        scenario_fusion_phase42: Phase 42 ScenarioFusionSnapshot
        mtsf_phase45: Phase 45 MultiTrajectoryStabilityFieldSnapshot

    Returns:
        TrajectoryFieldConvergenceSnapshot or None if insufficient data

    Formula Design:
        - Drift Alignment: Measures alignment between drift prediction and other trajectories
        - Identity Alignment: Measures alignment between identity memory and other trajectories
        - Symbolic Alignment: Measures alignment between temporal forecast and other trajectories
        - Continuity Alignment: Measures alignment between continuity and other trajectories
        - Scenario Alignment: Measures alignment between scenario fusion and other trajectories
        - Horizon Alignment: Measures alignment between multi-horizon forecasts

        - Convergence Index: Mean of all alignment signals (high = converging)
        - Divergence Index: 1 - Convergence Index (high = diverging)
        - Stability Index: Weighted combination of horizon + identity + continuity stability

        - Convergence Band Classification:
            * high: convergence_index >= 0.70
            * medium: 0.50 <= convergence_index < 0.70
            * low: 0.35 <= convergence_index < 0.50
            * fragmented: convergence_index < 0.35

    Graceful Degradation:
        Returns None if fewer than 3 upstream phases are available.
    """
    # ========================================================================
    # STEP 1: VALIDATE INPUT AND COUNT AVAILABLE PHASES
    # ========================================================================

    phases_available = sum([
        predictive_drift_phase35 is not None,
        identity_resonance_phase36 is not None,
        continuity_phase37 is not None,
        forecast_phase38 is not None,
        multi_horizon_phase39 is not None,
        scenario_fusion_phase42 is not None,
        mtsf_phase45 is not None,
    ])

    # Need at least 3 phases for meaningful convergence computation
    if phases_available < 3:
        return None

    # ========================================================================
    # STEP 2: EXTRACT SIGNALS FROM EACH PHASE
    # ========================================================================

    # Phase 35 - Predictive Persona Drift
    p35_drift_magnitude = _safe_get(predictive_drift_phase35, "drift_magnitude_prediction", 0.0)
    p35_drift_stability = _safe_get(predictive_drift_phase35, "drift_stability_score", 0.0)

    # Phase 36 - Identity Resonance Memory
    p36_ims = _safe_get(identity_resonance_phase36, "ims", 0.0)  # Identity Memory Strength
    p36_ida = _safe_get(identity_resonance_phase36, "ida", 0.0)  # Identity Drift Anchoring

    # Phase 37 - Adaptive Continuity Engine
    p37_ncc = _safe_get(continuity_phase37, "ncc", 0.0)  # Narrative Continuity Coefficient
    p37_icc = _safe_get(continuity_phase37, "icc", 0.0)  # Identity Continuity Coefficient
    p37_css = _safe_get(continuity_phase37, "css", 0.0)  # Continuity Stability Score

    # Phase 38 - Temporal Coherence Forecasting
    p38_coherence_slope = _safe_get(forecast_phase38, "coherence_slope", 0.0)
    p38_forecast_strength = _safe_get(forecast_phase38, "forecast_strength", 0.5)

    # Phase 39 - Multi-Horizon Temporal Forecasting
    p39_fci = _safe_get(multi_horizon_phase39, "forecast_consensus_index", 0.0)
    p39_fse = _safe_get(multi_horizon_phase39, "future_stability_envelope", 0.0)

    # Phase 42 - Scenario Fusion Engine
    p42_scenario_alignment = _safe_get(scenario_fusion_phase42, "scenario_alignment_score", 0.0)
    p42_multi_regime_consensus = _safe_get(scenario_fusion_phase42, "multi_regime_consensus", 0.0)

    # Phase 45 - Multi-Trajectory Stability Field
    p45_tsi = _safe_get(mtsf_phase45, "tsi", 0.0)  # Trajectory Stability Index

    # ========================================================================
    # STEP 3: COMPUTE TRAJECTORY ALIGNMENTS
    # ========================================================================

    # Collect trajectory signals for alignment computation
    # Each trajectory represents a different predictive dimension

    # Drift Trajectory Signal: inverse of drift magnitude (low drift = high alignment)
    drift_signal = 1.0 - _clamp(p35_drift_magnitude, 0.0, 1.0) if predictive_drift_phase35 else None

    # Identity Trajectory Signal: combination of memory strength and drift anchoring
    identity_signal = (
        _clamp((p36_ims + p36_ida) / 2.0, 0.0, 1.0)
        if identity_resonance_phase36
        else None
    )

    # Continuity Trajectory Signal: combination of continuity coefficients
    continuity_signal = (
        _clamp((p37_ncc + p37_icc + p37_css) / 3.0, 0.0, 1.0)
        if continuity_phase37
        else None
    )

    # Symbolic Trajectory Signal: forecast strength (normalized slope as direction indicator)
    symbolic_signal = (
        _clamp(p38_forecast_strength, 0.0, 1.0)
        if forecast_phase38
        else None
    )

    # Scenario Trajectory Signal: combination of consensus and alignment
    scenario_signal = (
        _clamp((p39_fci + p39_fse) / 2.0, 0.0, 1.0)
        if multi_horizon_phase39
        else None
    )

    # Horizon Trajectory Signal: scenario alignment and consensus
    horizon_signal = (
        _clamp((p42_scenario_alignment + p42_multi_regime_consensus) / 2.0, 0.0, 1.0)
        if scenario_fusion_phase42
        else None
    )

    # Collect all available signals
    all_signals = []
    if drift_signal is not None:
        all_signals.append(drift_signal)
    if identity_signal is not None:
        all_signals.append(identity_signal)
    if continuity_signal is not None:
        all_signals.append(continuity_signal)
    if symbolic_signal is not None:
        all_signals.append(symbolic_signal)
    if scenario_signal is not None:
        all_signals.append(scenario_signal)
    if horizon_signal is not None:
        all_signals.append(horizon_signal)

    # If insufficient signals, return None
    if len(all_signals) < 3:
        return None

    # Compute pairwise alignment for each trajectory
    drift_alignment = None
    identity_alignment = None
    symbolic_alignment = None
    continuity_alignment = None
    scenario_alignment_score = None
    horizon_alignment_score = None

    # Drift alignment: alignment with all other signals
    if drift_signal is not None:
        other_signals = [s for s in all_signals if s != drift_signal]
        drift_alignment = _compute_pairwise_alignment([drift_signal] + other_signals[:3])

    # Identity alignment: alignment with all other signals
    if identity_signal is not None:
        other_signals = [s for s in all_signals if s != identity_signal]
        identity_alignment = _compute_pairwise_alignment([identity_signal] + other_signals[:3])

    # Symbolic alignment: alignment with all other signals
    if symbolic_signal is not None:
        other_signals = [s for s in all_signals if s != symbolic_signal]
        symbolic_alignment = _compute_pairwise_alignment([symbolic_signal] + other_signals[:3])

    # Continuity alignment: alignment with all other signals
    if continuity_signal is not None:
        other_signals = [s for s in all_signals if s != continuity_signal]
        continuity_alignment = _compute_pairwise_alignment([continuity_signal] + other_signals[:3])

    # Scenario alignment: alignment with all other signals
    if scenario_signal is not None:
        other_signals = [s for s in all_signals if s != scenario_signal]
        scenario_alignment_score = _compute_pairwise_alignment([scenario_signal] + other_signals[:3])

    # Horizon alignment: alignment with all other signals
    if horizon_signal is not None:
        other_signals = [s for s in all_signals if s != horizon_signal]
        horizon_alignment_score = _compute_pairwise_alignment([horizon_signal] + other_signals[:3])

    # ========================================================================
    # STEP 4: COMPUTE CONVERGENCE INDEX
    # ========================================================================

    # Convergence index is the mean of all alignment signals
    alignment_signals = []
    if drift_alignment is not None:
        alignment_signals.append(drift_alignment)
    if identity_alignment is not None:
        alignment_signals.append(identity_alignment)
    if symbolic_alignment is not None:
        alignment_signals.append(symbolic_alignment)
    if continuity_alignment is not None:
        alignment_signals.append(continuity_alignment)
    if scenario_alignment_score is not None:
        alignment_signals.append(scenario_alignment_score)
    if horizon_alignment_score is not None:
        alignment_signals.append(horizon_alignment_score)

    if not alignment_signals:
        return None

    convergence_index = sum(alignment_signals) / len(alignment_signals)
    convergence_index = _clamp(convergence_index, 0.0, 1.0)

    # ========================================================================
    # STEP 5: COMPUTE DIVERGENCE INDEX
    # ========================================================================

    divergence_index = 1.0 - convergence_index

    # ========================================================================
    # STEP 6: COMPUTE STABILITY INDEX
    # ========================================================================

    # Stability index is a weighted combination of:
    # - Horizon stability (from Phase 39 FSE)
    # - Identity stability (from Phase 36 IDA)
    # - Continuity stability (from Phase 37 CSS)
    # - MTSF stability (from Phase 45 TSI)

    stability_components = []
    stability_weights = []

    if multi_horizon_phase39 is not None:
        stability_components.append(_clamp(p39_fse, 0.0, 1.0))
        stability_weights.append(0.30)

    if identity_resonance_phase36 is not None:
        stability_components.append(_clamp(p36_ida, 0.0, 1.0))
        stability_weights.append(0.25)

    if continuity_phase37 is not None:
        stability_components.append(_clamp(p37_css, 0.0, 1.0))
        stability_weights.append(0.25)

    if mtsf_phase45 is not None:
        stability_components.append(_clamp(p45_tsi, 0.0, 1.0))
        stability_weights.append(0.20)

    if stability_components:
        total_weight = sum(stability_weights)
        normalized_weights = [w / total_weight for w in stability_weights]
        stability_index = sum(
            comp * weight for comp, weight in zip(stability_components, normalized_weights)
        )
        stability_index = _clamp(stability_index, 0.0, 1.0)
    else:
        stability_index = 0.5  # Default moderate stability

    # ========================================================================
    # STEP 7: CLASSIFY CONVERGENCE BAND
    # ========================================================================

    if convergence_index >= 0.70:
        convergence_band = "high"
    elif convergence_index >= 0.50:
        convergence_band = "medium"
    elif convergence_index >= 0.35:
        convergence_band = "low"
    else:
        convergence_band = "fragmented"

    # ========================================================================
    # STEP 8: IDENTIFY DOMINANT CONVERGENCE SIGNAL
    # ========================================================================

    # Find the trajectory with highest alignment score
    trajectory_scores = {}
    if drift_alignment is not None:
        trajectory_scores["DRIFT"] = drift_alignment
    if identity_alignment is not None:
        trajectory_scores["IDENTITY"] = identity_alignment
    if symbolic_alignment is not None:
        trajectory_scores["SYMBOLIC"] = symbolic_alignment
    if continuity_alignment is not None:
        trajectory_scores["CONTINUITY"] = continuity_alignment
    if scenario_alignment_score is not None:
        trajectory_scores["SCENARIO"] = scenario_alignment_score
    if horizon_alignment_score is not None:
        trajectory_scores["HORIZON"] = horizon_alignment_score

    if trajectory_scores:
        # Sort by score (deterministic tie-breaking by alphabetical order)
        sorted_trajectories = sorted(
            trajectory_scores.items(),
            key=lambda x: (-x[1], x[0])  # Descending score, ascending name
        )
        dominant_convergence_signal = sorted_trajectories[0][0]
    else:
        dominant_convergence_signal = "UNKNOWN"

    # ========================================================================
    # STEP 9: GENERATE DIAGNOSTIC TAGS
    # ========================================================================

    tags = []

    # Convergence/Divergence tags
    if convergence_index >= 0.75:
        tags.append("TRAJECTORY_CONVERGING")
    if divergence_index >= 0.75:
        tags.append("TRAJECTORY_DIVERGING")

    # Consensus tags
    if convergence_index >= 0.70 and stability_index >= 0.70:
        tags.append("TRAJECTORY_CONSENSUS")

    # Fragmentation tags
    if convergence_band == "fragmented":
        tags.append("TRAJECTORY_FRAGMENTED")

    # Stability tags
    if stability_index >= 0.75:
        tags.append("STABILITY_STRONG")
    elif stability_index <= 0.35:
        tags.append("STABILITY_WEAK")

    # Individual trajectory tags
    if drift_alignment is not None and drift_alignment >= 0.75:
        tags.append("DRIFT_ALIGNED")
    if identity_alignment is not None and identity_alignment >= 0.75:
        tags.append("IDENTITY_ALIGNED")
    if symbolic_alignment is not None and symbolic_alignment >= 0.75:
        tags.append("SYMBOLIC_ALIGNED")
    if continuity_alignment is not None and continuity_alignment >= 0.75:
        tags.append("CONTINUITY_ALIGNED")
    if scenario_alignment_score is not None and scenario_alignment_score >= 0.75:
        tags.append("SCENARIO_ALIGNED")
    if horizon_alignment_score is not None and horizon_alignment_score >= 0.75:
        tags.append("HORIZON_ALIGNED")

    # Convergence band tags
    if convergence_band == "high":
        tags.append("CONVERGENCE_HIGH")
    elif convergence_band == "fragmented":
        tags.append("CONVERGENCE_FRAGMENTED")

    # Cross-trajectory patterns
    if (
        identity_alignment is not None
        and continuity_alignment is not None
        and identity_alignment >= 0.70
        and continuity_alignment >= 0.70
    ):
        tags.append("IDENTITY_CONTINUITY_COUPLED")

    if (
        scenario_alignment_score is not None
        and horizon_alignment_score is not None
        and scenario_alignment_score >= 0.70
        and horizon_alignment_score >= 0.70
    ):
        tags.append("SCENARIO_HORIZON_COUPLED")

    # Sort and deduplicate for determinism
    tags = sorted(set(tags))

    # ========================================================================
    # STEP 10: RETURN SNAPSHOT
    # ========================================================================

    return TrajectoryFieldConvergenceSnapshot(
        drift_alignment=drift_alignment,
        identity_alignment=identity_alignment,
        symbolic_alignment=symbolic_alignment,
        continuity_alignment=continuity_alignment,
        scenario_alignment=scenario_alignment_score,
        horizon_alignment=horizon_alignment_score,
        convergence_index=convergence_index,
        divergence_index=divergence_index,
        stability_index=stability_index,
        convergence_band=convergence_band,
        dominant_convergence_signal=dominant_convergence_signal,
        diagnostic_tags=tags,
    )
