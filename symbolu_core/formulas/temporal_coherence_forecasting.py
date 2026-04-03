"""
Temporal Coherence Forecasting Model (TCFM) v1.0 - Phase 38

Deterministic, zero-LLM, observation-only forecasting engine that predicts how coherence,
continuity, identity, and drift metrics are expected to evolve across future turns.

This is a read-only analytic module used for dashboards and persona tone modulation (optional, bounded).
It MUST NOT alter routing, mappers, scoring, reasoning, or semantic output.

TCFM outputs:
  1. Coherence Trajectory Forecast (CTF): Predicts if coherence_fused will rise/fall/remain stable
  2. Continuity Trajectory Forecast (CNF): Projects NCC/ICC/CSS into next-turn estimates
  3. Drift Forecast Probability (DFP): Likelihood of future coherence disruption due to drift
  4. Forecast Stability Score (FSS): Confidence in the forecast based on variance patterns
  5. Forecast Band: STRONG_UPTREND / MILD_UPTREND / NEUTRAL / MILD_DOWNTREND / STRONG_DOWNTREND
  6. Diagnostic Tags: FORECAST_UPTREND, FORECAST_DOWNTREND, etc.

CRITICAL INVARIANTS:
    - Zero-LLM: Purely rule-based, deterministic math only
    - Observation-only: NO changes to routing, mappers, scoring, reasoning, or semantic output
    - Tone-level only: NEVER semantic changes (bounded ±0.015)
    - Non-invasive: Does not modify any existing coherence formulas or behaviors
    - Backward-compatible: All existing tests remain green
    - Deterministic: Same inputs → same outputs always
    - Fully bounded: All outputs [0.0–1.0]
    - Graceful degradation: Returns None if insufficient data
"""

from dataclasses import dataclass, field
from typing import List, Optional, Dict
import math


@dataclass
class TemporalCoherenceForecastSnapshot:
    """
    Immutable snapshot of Temporal Coherence Forecasting Model computation.

    Fields:
        coherence_slope: Trend slope for coherence_fused [-1.0, 1.0]
        continuity_slope: Trend slope for continuity metrics [-1.0, 1.0]
        drift_influence: Drift risk impact on forecast [0.0, 1.0]
        entropy_forward_risk: Forward-looking entropy risk [0.0, 1.0]
        forecast_strength: Confidence in forecast [0.0, 1.0]
        forecast_band: Classification (STRONG_UPTREND, MILD_UPTREND, NEUTRAL, MILD_DOWNTREND, STRONG_DOWNTREND)
        diagnostic_tags: Deterministic diagnostic tags
        raw_signals: Raw signal values for API exposure
    """

    coherence_slope: float  # Coherence trend slope [-1.0, 1.0]
    continuity_slope: float  # Continuity trend slope [-1.0, 1.0]
    drift_influence: float  # Drift risk impact [0.0, 1.0]
    entropy_forward_risk: float  # Forward entropy risk [0.0, 1.0]
    forecast_strength: float  # Forecast confidence [0.0, 1.0]
    forecast_band: str  # STRONG_UPTREND, MILD_UPTREND, NEUTRAL, MILD_DOWNTREND, STRONG_DOWNTREND
    diagnostic_tags: List[str] = field(default_factory=list)
    raw_signals: Dict[str, float] = field(default_factory=dict)


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


def _safe_get(value: Optional[float], default: float = 0.5) -> float:
    """
    Safely extract float value with fallback.

    Args:
        value: Optional float value
        default: Default value if None (default 0.5)

    Returns:
        float: Value or default
    """
    if value is None:
        return default
    return _clamp(value)


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


def _compute_linear_slope(values: List[float]) -> float:
    """
    Compute linear trend slope using simple linear regression.

    Args:
        values: List of float values (time series)

    Returns:
        float: Slope of trend line (unbounded, but typically in range [-0.5, 0.5])
    """
    if not values or len(values) < 2:
        return 0.0

    n = len(values)
    x = list(range(n))  # Time indices
    y = values

    # Compute means
    x_mean = sum(x) / n
    y_mean = sum(y) / n

    # Compute slope: Σ((x - x_mean) * (y - y_mean)) / Σ((x - x_mean)^2)
    numerator = sum((x[i] - x_mean) * (y[i] - y_mean) for i in range(n))
    denominator = sum((x[i] - x_mean) ** 2 for i in range(n))

    if denominator == 0:
        return 0.0

    slope = numerator / denominator
    return slope


def _normalize_slope(slope: float, scale: float = 5.0) -> float:
    """
    Normalize slope to [-1.0, 1.0] range using tanh scaling.

    Args:
        slope: Raw slope value
        scale: Scaling factor (default 5.0)

    Returns:
        float: Normalized slope [-1.0, 1.0]
    """
    # tanh provides smooth non-linear normalization
    # slope * scale = 0.5 → tanh = ~0.46
    # slope * scale = 1.0 → tanh = ~0.76
    return math.tanh(slope * scale)


def _compute_forecast_strength(
    history: List[float],
    slope: float,
    window: int = 5
) -> float:
    """
    Compute forecast strength (confidence) based on variance and slope consistency.

    Low variance + consistent slope = high strength
    High variance + erratic slope = low strength

    Args:
        history: Historical values (most recent last)
        slope: Trend slope
        window: Window size for variance computation

    Returns:
        float: Forecast strength [0.0, 1.0]
    """
    if not history or len(history) < 2:
        return 0.5  # Neutral

    recent = history[-window:] if len(history) >= window else history
    variance = _compute_variance(recent)

    # Convert variance to stability (inverse relationship)
    # Variance of 0.25 or more = very unstable
    stability = _clamp(1.0 - min(variance * 4.0, 1.0), 0.0, 1.0)

    # Slope magnitude factor: stronger trends = more confident
    slope_magnitude = abs(slope)
    slope_confidence = _clamp(slope_magnitude * 2.0, 0.0, 1.0)

    # Weighted blend
    forecast_strength = (
        0.70 * stability +
        0.30 * slope_confidence
    )

    return _clamp(forecast_strength, 0.0, 1.0)


def _compute_drift_amplification(
    drift_magnitude: float,
    drift_stability: float,
    entropy_volatility: float
) -> float:
    """
    Compute drift amplification factor for forecast.

    High drift magnitude + low drift stability + high entropy = high amplification

    Args:
        drift_magnitude: Drift magnitude from Phase 35 [0.0, 1.0]
        drift_stability: Drift stability from Phase 35 [0.0, 1.0]
        entropy_volatility: Temporal entropy volatility [0.0, 1.0]

    Returns:
        float: Drift amplification factor [0.0, 1.0]
    """
    # Drift risk: high magnitude, low stability
    drift_risk = drift_magnitude * (1.0 - drift_stability)

    # Entropy multiplier
    entropy_multiplier = 1.0 + (0.5 * entropy_volatility)

    # Amplification
    amplification = _clamp(drift_risk * entropy_multiplier, 0.0, 1.0)

    return amplification


def _compute_entropy_forward_risk(
    entropy_volatility: float,
    entropy_diff: float,
    entropy_history: Optional[List[float]] = None
) -> float:
    """
    Compute forward-looking entropy risk.

    High current volatility + rising entropy trend = high forward risk

    Args:
        entropy_volatility: Current entropy volatility [0.0, 1.0]
        entropy_diff: Current entropy diff [0.0, 1.0]
        entropy_history: Historical entropy volatility values

    Returns:
        float: Forward entropy risk [0.0, 1.0]
    """
    # Base risk from current volatility
    base_risk = entropy_volatility

    # Trend risk: is entropy volatility rising?
    trend_risk = 0.5  # Neutral
    if entropy_history and len(entropy_history) >= 3:
        slope = _compute_linear_slope(entropy_history[-5:])
        # Positive slope = rising risk
        trend_risk = _clamp(0.5 + slope * 2.0, 0.0, 1.0)

    # Entropy diff contribution (high diff = more chaos)
    diff_risk = entropy_diff * 0.5

    # Weighted blend
    forward_risk = (
        0.50 * base_risk +
        0.30 * trend_risk +
        0.20 * diff_risk
    )

    return _clamp(forward_risk, 0.0, 1.0)


def _identity_anchoring_factor(
    identity_memory_strength: float,
    identity_drift_anchoring: float,
    identity_stability: float
) -> float:
    """
    Compute identity anchoring factor for forecast stabilization.

    Strong identity memory + anchoring + stability = stabilizes forecast

    Args:
        identity_memory_strength: IMS from Phase 36 [0.0, 1.0]
        identity_drift_anchoring: IDA from Phase 36 [0.0, 1.0]
        identity_stability: Identity stability from Phase 34 [0.0, 1.0]

    Returns:
        float: Identity anchoring factor [0.0, 1.0]
    """
    anchoring = (
        0.40 * identity_memory_strength +
        0.35 * identity_drift_anchoring +
        0.25 * identity_stability
    )

    return _clamp(anchoring, 0.0, 1.0)


def _symbolic_harmonization_stabilizer(
    symbolic_harmonization_index: float,
    symbolic_harmonization_history: Optional[List[float]] = None
) -> float:
    """
    Compute symbolic harmonization stabilization factor.

    High symbolic harmonization + stable history = stabilizes forecast

    Args:
        symbolic_harmonization_index: SHI from Phase 27 [0.0, 1.0]
        symbolic_harmonization_history: Historical SHI values

    Returns:
        float: Symbolic stabilization factor [0.0, 1.0]
    """
    # Base stabilization from current SHI
    base_stabilization = symbolic_harmonization_index

    # History stability
    history_stability = 0.5  # Neutral
    if symbolic_harmonization_history and len(symbolic_harmonization_history) >= 3:
        variance = _compute_variance(symbolic_harmonization_history[-5:])
        history_stability = _clamp(1.0 - min(variance * 4.0, 1.0), 0.0, 1.0)

    # Weighted blend
    stabilization = (
        0.60 * base_stabilization +
        0.40 * history_stability
    )

    return _clamp(stabilization, 0.0, 1.0)


def _ucf_stability_contribution(
    consciousness_order_index: float,
    consciousness_stability_index: float,
    consciousness_order_history: Optional[List[float]] = None
) -> float:
    """
    Compute UCF stability contribution to forecast.

    High COI + high CSI + stable history = positive forecast contribution

    Args:
        consciousness_order_index: COI from Phase 26 [0.0, 1.0]
        consciousness_stability_index: CSI from Phase 26 [0.0, 1.0]
        consciousness_order_history: Historical COI values

    Returns:
        float: UCF stability contribution [0.0, 1.0]
    """
    # Base contribution
    base_contribution = (
        0.50 * consciousness_order_index +
        0.50 * consciousness_stability_index
    )

    # History trend: rising COI = positive
    trend_bonus = 0.0
    if consciousness_order_history and len(consciousness_order_history) >= 3:
        slope = _compute_linear_slope(consciousness_order_history[-5:])
        # Positive slope = upward trend = bonus
        trend_bonus = _clamp(slope * 2.0, -0.1, 0.1)

    contribution = _clamp(base_contribution + trend_bonus, 0.0, 1.0)

    return contribution


def compute_temporal_coherence_forecast(
    *,
    # Phase 16: Formula Fusion Stabilizer
    coherence_fused: Optional[float] = None,
    coherence_fused_history: Optional[List[float]] = None,
    # Phase 37: Adaptive Continuity Engine
    ncc: Optional[float] = None,  # Narrative Continuity Coefficient
    icc: Optional[float] = None,  # Identity Continuity Coefficient
    css: Optional[float] = None,  # Continuity Stability Score
    ncc_history: Optional[List[float]] = None,
    icc_history: Optional[List[float]] = None,
    css_history: Optional[List[float]] = None,
    # Phase 35: Predictive Persona Drift
    drift_magnitude_prediction: Optional[float] = None,
    drift_stability_score: Optional[float] = None,
    drift_magnitude_history: Optional[List[float]] = None,
    # Phase 36: Identity Resonance Memory
    identity_memory_strength: Optional[float] = None,  # IMS
    identity_drift_anchoring: Optional[float] = None,  # IDA
    # Phase 34: Identity Harmonics
    identity_stability_score: Optional[float] = None,
    # Phase 27: Symbolic Harmonization
    symbolic_harmonization_index: Optional[float] = None,
    symbolic_harmonization_history: Optional[List[float]] = None,
    # Phase 26: Unified Consciousness Formula
    consciousness_order_index: Optional[float] = None,  # COI
    consciousness_stability_index: Optional[float] = None,  # CSI
    consciousness_order_history: Optional[List[float]] = None,
    # Phase 18: Temporal Entropy
    temporal_entropy_volatility: Optional[float] = None,
    temporal_entropy_diff: Optional[float] = None,
    temporal_entropy_volatility_history: Optional[List[float]] = None,
) -> Optional[TemporalCoherenceForecastSnapshot]:
    """
    Compute Temporal Coherence Forecasting Model (TCFM) v1.0.

    This formula predicts how coherence, continuity, identity, and drift metrics
    are expected to evolve across future turns.

    The result is a forecast snapshot containing:
      1. Coherence Trajectory Forecast (coherence_slope): Trend prediction
      2. Continuity Trajectory Forecast (continuity_slope): Continuity trend prediction
      3. Drift Forecast Probability (drift_influence): Drift disruption likelihood
      4. Forecast Stability Score (forecast_strength): Confidence in forecast
      5. Forecast Band: Classification of trajectory
      6. Diagnostic Tags: FORECAST_UPTREND, FORECAST_DOWNTREND, etc.

    Args:
        coherence_fused: Current fused coherence from Phase 16 [0.0, 1.0]
        coherence_fused_history: Historical fused coherence values
        ncc: Narrative Continuity Coefficient from Phase 37 [0.0, 1.0]
        icc: Identity Continuity Coefficient from Phase 37 [0.0, 1.0]
        css: Continuity Stability Score from Phase 37 [0.0, 1.0]
        ncc_history: Historical NCC values
        icc_history: Historical ICC values
        css_history: Historical CSS values
        drift_magnitude_prediction: DMP from Phase 35 [0.0, 1.0]
        drift_stability_score: DSS from Phase 35 [0.0, 1.0]
        drift_magnitude_history: Historical drift magnitude values
        identity_memory_strength: IMS from Phase 36 [0.0, 1.0]
        identity_drift_anchoring: IDA from Phase 36 [0.0, 1.0]
        identity_stability_score: Identity stability from Phase 34 [0.0, 1.0]
        symbolic_harmonization_index: SHI from Phase 27 [0.0, 1.0]
        symbolic_harmonization_history: Historical SHI values
        consciousness_order_index: COI from Phase 26 [0.0, 1.0]
        consciousness_stability_index: CSI from Phase 26 [0.0, 1.0]
        consciousness_order_history: Historical COI values
        temporal_entropy_volatility: Entropy volatility from Phase 18 [0.0, 1.0]
        temporal_entropy_diff: Entropy diff from Phase 18 [0.0, 1.0]
        temporal_entropy_volatility_history: Historical entropy volatility

    Returns:
        TemporalCoherenceForecastSnapshot or None if insufficient data

    Graceful Degradation:
        Returns None if we lack core required signals:
          - At least ONE coherence signal (coherence_fused OR ncc OR icc)
          - At least ONE continuity signal (ncc OR icc OR css)
          - Sufficient history (at least 3 turns) for trend analysis
    """
    tags = []
    raw_signals = {}

    # ========================================================================
    # STEP 1: CHECK CORE INPUT AVAILABILITY (Graceful Degradation)
    # ========================================================================

    # Require at least ONE coherence signal
    has_coherence_signal = any([
        coherence_fused is not None,
        ncc is not None,
        icc is not None,
    ])

    # Require at least ONE continuity signal
    has_continuity_signal = any([
        ncc is not None,
        icc is not None,
        css is not None,
    ])

    # Require sufficient history for trend analysis (at least 3 turns)
    has_sufficient_history = any([
        coherence_fused_history and len(coherence_fused_history) >= 3,
        ncc_history and len(ncc_history) >= 3,
        icc_history and len(icc_history) >= 3,
    ])

    if not (has_coherence_signal and has_continuity_signal and has_sufficient_history):
        # Insufficient data for TCFM computation
        return None

    # ========================================================================
    # STEP 2: EXTRACT SIGNALS WITH SAFE FALLBACKS
    # ========================================================================

    # Phase 16: Coherence Fusion
    coh_fused = _safe_get(coherence_fused, 0.5)

    # Phase 37: Adaptive Continuity Engine
    ncc_val = _safe_get(ncc, 0.5)
    icc_val = _safe_get(icc, 0.5)
    css_val = _safe_get(css, 0.5)

    # Phase 35: Predictive Drift
    drift_magnitude = _safe_get(drift_magnitude_prediction, 0.5)
    drift_stability = _safe_get(drift_stability_score, 0.5)

    # Phase 36: Identity Resonance Memory
    ims = _safe_get(identity_memory_strength, 0.5)
    ida = _safe_get(identity_drift_anchoring, 0.5)

    # Phase 34: Identity Harmonics
    identity_stability = _safe_get(identity_stability_score, 0.5)

    # Phase 27: Symbolic Harmonization
    sym_harm = _safe_get(symbolic_harmonization_index, 0.5)

    # Phase 26: Unified Consciousness
    coi = _safe_get(consciousness_order_index, 0.5)
    csi = _safe_get(consciousness_stability_index, 0.5)

    # Phase 18: Temporal Entropy
    temp_entropy_vol = _safe_get(temporal_entropy_volatility, 0.5)
    temp_entropy_diff = _safe_get(temporal_entropy_diff, 0.5)

    # Track fallbacks for diagnostics
    if coherence_fused is None:
        tags.append("coherence_fused_fallback")
    if ncc is None:
        tags.append("ncc_fallback")

    # ========================================================================
    # STEP 3: COMPUTE COHERENCE TRAJECTORY SLOPE
    # ========================================================================
    # Use coherence_fused_history to compute trend slope

    coherence_slope_raw = 0.0
    coherence_slope_source = "none"

    if coherence_fused_history and len(coherence_fused_history) >= 3:
        coherence_slope_raw = _compute_linear_slope(coherence_fused_history[-7:])
        coherence_slope_source = "coherence_fused_history"
    elif ncc_history and len(ncc_history) >= 3:
        # Fallback to NCC history
        coherence_slope_raw = _compute_linear_slope(ncc_history[-7:])
        coherence_slope_source = "ncc_history"
        tags.append("coherence_slope_from_ncc")

    # Normalize slope to [-1.0, 1.0]
    coherence_slope = _normalize_slope(coherence_slope_raw, scale=5.0)

    raw_signals["coherence_slope"] = coherence_slope
    raw_signals["coherence_slope_raw"] = coherence_slope_raw
    raw_signals["coherence_slope_source"] = coherence_slope_source

    # ========================================================================
    # STEP 4: COMPUTE CONTINUITY TRAJECTORY SLOPE
    # ========================================================================
    # Blend NCC, ICC, CSS slopes to get overall continuity trajectory

    continuity_slope_raw = 0.0
    continuity_slope_components = []

    if ncc_history and len(ncc_history) >= 3:
        ncc_slope = _compute_linear_slope(ncc_history[-7:])
        continuity_slope_components.append(("ncc", ncc_slope, 0.40))

    if icc_history and len(icc_history) >= 3:
        icc_slope = _compute_linear_slope(icc_history[-7:])
        continuity_slope_components.append(("icc", icc_slope, 0.35))

    if css_history and len(css_history) >= 3:
        css_slope = _compute_linear_slope(css_history[-7:])
        continuity_slope_components.append(("css", css_slope, 0.25))

    # Weighted blend of slopes
    if continuity_slope_components:
        total_weight = sum(weight for _, _, weight in continuity_slope_components)
        continuity_slope_raw = sum(
            slope * weight for _, slope, weight in continuity_slope_components
        ) / total_weight
    else:
        # Fallback: use coherence slope as proxy
        continuity_slope_raw = coherence_slope_raw
        tags.append("continuity_slope_from_coherence")

    # Normalize slope to [-1.0, 1.0]
    continuity_slope = _normalize_slope(continuity_slope_raw, scale=5.0)

    raw_signals["continuity_slope"] = continuity_slope
    raw_signals["continuity_slope_raw"] = continuity_slope_raw

    # ========================================================================
    # STEP 5: COMPUTE DRIFT INFLUENCE (AMPLIFICATION FACTOR)
    # ========================================================================
    # How much will drift disrupt the forecast?

    drift_influence = _compute_drift_amplification(
        drift_magnitude=drift_magnitude,
        drift_stability=drift_stability,
        entropy_volatility=temp_entropy_vol
    )

    raw_signals["drift_influence"] = drift_influence

    # ========================================================================
    # STEP 6: COMPUTE ENTROPY FORWARD RISK
    # ========================================================================
    # Forward-looking entropy risk based on current volatility and trend

    entropy_forward_risk = _compute_entropy_forward_risk(
        entropy_volatility=temp_entropy_vol,
        entropy_diff=temp_entropy_diff,
        entropy_history=temporal_entropy_volatility_history
    )

    raw_signals["entropy_forward_risk"] = entropy_forward_risk

    # ========================================================================
    # STEP 7: COMPUTE FORECAST STRENGTH (CONFIDENCE)
    # ========================================================================
    # Confidence in the forecast based on variance and slope consistency

    # Use primary history (coherence_fused or NCC)
    primary_history = coherence_fused_history if coherence_fused_history else ncc_history
    primary_slope = coherence_slope_raw

    base_forecast_strength = _compute_forecast_strength(
        history=primary_history if primary_history else [],
        slope=primary_slope,
        window=5
    )

    # Apply stabilization factors
    identity_anchoring = _identity_anchoring_factor(
        identity_memory_strength=ims,
        identity_drift_anchoring=ida,
        identity_stability=identity_stability
    )

    symbolic_stabilization = _symbolic_harmonization_stabilizer(
        symbolic_harmonization_index=sym_harm,
        symbolic_harmonization_history=symbolic_harmonization_history
    )

    ucf_contribution = _ucf_stability_contribution(
        consciousness_order_index=coi,
        consciousness_stability_index=csi,
        consciousness_order_history=consciousness_order_history
    )

    # Apply drift and entropy damping
    drift_damping = _clamp(1.0 - (0.30 * drift_influence), 0.70, 1.0)
    entropy_damping = _clamp(1.0 - (0.25 * entropy_forward_risk), 0.75, 1.0)

    # Final forecast strength
    forecast_strength = (
        base_forecast_strength *
        (0.85 + 0.15 * identity_anchoring) *
        (0.90 + 0.10 * symbolic_stabilization) *
        (0.90 + 0.10 * ucf_contribution) *
        drift_damping *
        entropy_damping
    )

    forecast_strength = _clamp(forecast_strength, 0.0, 1.0)

    raw_signals["forecast_strength"] = forecast_strength
    raw_signals["base_forecast_strength"] = base_forecast_strength
    raw_signals["identity_anchoring"] = identity_anchoring
    raw_signals["symbolic_stabilization"] = symbolic_stabilization
    raw_signals["ucf_contribution"] = ucf_contribution

    # ========================================================================
    # STEP 8: COMPUTE FORECAST BAND
    # ========================================================================
    # Classify forecast into band based on weighted slope and strength

    # Weighted trajectory score: blend coherence and continuity slopes
    trajectory_score = (
        0.55 * coherence_slope +
        0.45 * continuity_slope
    )

    # Apply forecast strength weighting (low strength → pulls toward neutral)
    weighted_trajectory = trajectory_score * (0.5 + 0.5 * forecast_strength)

    # Band classification
    if weighted_trajectory >= 0.30:
        forecast_band = "STRONG_UPTREND"
    elif weighted_trajectory >= 0.10:
        forecast_band = "MILD_UPTREND"
    elif weighted_trajectory <= -0.30:
        forecast_band = "STRONG_DOWNTREND"
    elif weighted_trajectory <= -0.10:
        forecast_band = "MILD_DOWNTREND"
    else:
        forecast_band = "NEUTRAL"

    raw_signals["trajectory_score"] = trajectory_score
    raw_signals["weighted_trajectory"] = weighted_trajectory

    # ========================================================================
    # STEP 9: GENERATE DIAGNOSTIC TAGS
    # ========================================================================

    # Forecast direction tags
    if forecast_band in ["STRONG_UPTREND", "MILD_UPTREND"]:
        tags.append("FORECAST_UPTREND")
    elif forecast_band in ["STRONG_DOWNTREND", "MILD_DOWNTREND"]:
        tags.append("FORECAST_DOWNTREND")
    else:
        tags.append("FORECAST_NEUTRAL")

    # Forecast strength tags
    if forecast_strength >= 0.70:
        tags.append("forecast_confident")
    elif forecast_strength <= 0.35:
        tags.append("FORECAST_UNCERTAIN")

    # Entropy risk tags
    if entropy_forward_risk >= 0.65:
        tags.append("HIGH_ENTROPY_RISK")
    elif entropy_forward_risk <= 0.35:
        tags.append("low_entropy_risk")

    # Drift influence tags
    if drift_influence >= 0.60:
        tags.append("drift_disruption_risk")
    elif drift_influence <= 0.30:
        tags.append("drift_minimal")

    # Identity continuity support
    if identity_anchoring >= 0.65 and forecast_band in ["STRONG_UPTREND", "MILD_UPTREND"]:
        tags.append("IDENTITY_CONTINUITY_SUPPORTS_TREND")

    # Coherence-continuity alignment
    if abs(coherence_slope - continuity_slope) <= 0.15:
        tags.append("coherence_continuity_aligned")
    elif abs(coherence_slope - continuity_slope) >= 0.40:
        tags.append("coherence_continuity_divergent")

    # Band-specific tags
    tags.append(f"forecast_band_{forecast_band.lower()}")

    # Strong trajectory despite risk
    if forecast_band in ["STRONG_UPTREND", "MILD_UPTREND"] and (drift_influence >= 0.60 or entropy_forward_risk >= 0.60):
        tags.append("uptrend_despite_risk")

    # Weak forecast with risk amplification
    if forecast_band in ["STRONG_DOWNTREND", "MILD_DOWNTREND"] and (drift_influence >= 0.60 or entropy_forward_risk >= 0.60):
        tags.append("downtrend_amplified_by_risk")

    # ========================================================================
    # STEP 10: STORE ALL RAW SIGNALS FOR API EXPOSURE
    # ========================================================================

    raw_signals.update({
        "coherence_fused": coh_fused,
        "ncc": ncc_val,
        "icc": icc_val,
        "css": css_val,
        "drift_magnitude": drift_magnitude,
        "drift_stability": drift_stability,
        "identity_memory_strength": ims,
        "identity_drift_anchoring": ida,
        "identity_stability": identity_stability,
        "symbolic_harmonization_index": sym_harm,
        "consciousness_order_index": coi,
        "consciousness_stability_index": csi,
        "temporal_entropy_volatility": temp_entropy_vol,
        "temporal_entropy_diff": temp_entropy_diff,
    })

    # ========================================================================
    # STEP 11: RETURN SNAPSHOT
    # ========================================================================

    return TemporalCoherenceForecastSnapshot(
        coherence_slope=coherence_slope,
        continuity_slope=continuity_slope,
        drift_influence=drift_influence,
        entropy_forward_risk=entropy_forward_risk,
        forecast_strength=forecast_strength,
        forecast_band=forecast_band,
        diagnostic_tags=sorted(set(tags)),  # Deduplicate and sort for determinism
        raw_signals=raw_signals,
    )
