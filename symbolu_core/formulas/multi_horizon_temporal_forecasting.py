"""
Multi-Horizon Temporal Forecasting Engine (MHTFE) v1.0 - Phase 39

Deterministic, zero-LLM, observation-only multi-timescale forecasting engine that predicts
coherence, continuity, identity, and drift evolution across multiple temporal horizons:

Horizons:
  • H1 (Short-Term Forecast): Next 1–3 turns (immediate trajectory)
  • H2 (Mid-Term Forecast): Next 4–8 turns (strategic outlook)
  • H3 (Long-Term Forecast): Next 9–20 turns (stability trajectory)

MHTFE extends Phase 38 TCFM by providing multi-scale temporal predictions, enabling
better long-term coherence planning and early detection of stability risks.

This is a read-only analytic module used for dashboards and persona tone modulation (optional, bounded).
It MUST NOT alter routing, mappers, scoring, reasoning, or semantic output.

MHTFE outputs:
  1. Per-Horizon Metrics (H1, H2, H3):
     • coherence_slope: Trend prediction [-1.0, +1.0]
     • continuity_slope: Continuity trend prediction [-1.0, +1.0]
     • drift_risk: Drift disruption likelihood [0.0, 1.0]
     • entropy_risk: Forward-looking entropy risk [0.0, 1.0]
     • forecast_strength: Confidence in forecast [0.0, 1.0]
     • forecast_band: STRONG_UPTREND / MILD_UPTREND / NEUTRAL / MILD_DOWNTREND / STRONG_DOWNTREND

  2. Cross-Horizon Analytics:
     • Forecast Consensus Index (FCI): Agreement across horizons [0.0, 1.0]
     • Future Stability Envelope (FSE): Uncertainty-modulated stability [0.0, 1.0]

  3. Diagnostic Tags:
     • MULTI_HORIZON_AGREEMENT
     • SHORT_TERM_NOISE
     • LONG_TERM_UNCERTAINTY
     • DRIFT_RISK_RISING
     • IDENTITY_SUPPORTS_FORECAST
     • ENTROPY_WEAKENING_TREND

CRITICAL INVARIANTS:
    - Zero-LLM: Purely rule-based, deterministic math only
    - Observation-only: NO changes to routing, mappers, scoring, reasoning, or semantic output
    - Tone-level only: NEVER semantic changes (bounded ±0.015)
    - Non-invasive: Does not modify any existing coherence formulas or behaviors
    - Backward-compatible: All existing tests remain green
    - Deterministic: Same inputs → same outputs always
    - Fully bounded: All outputs [0.0–1.0] or [-1.0, +1.0] for slopes
    - Graceful degradation: Returns None if insufficient data
"""

from dataclasses import dataclass, field
from typing import List, Optional, Dict
import math


@dataclass
class HorizonForecast:
    """
    Immutable forecast snapshot for a single temporal horizon.

    Fields:
        coherence_slope: Coherence trend slope [-1.0, 1.0]
        continuity_slope: Continuity trend slope [-1.0, 1.0]
        drift_risk: Drift disruption risk [0.0, 1.0]
        entropy_risk: Forward entropy risk [0.0, 1.0]
        forecast_strength: Forecast confidence [0.0, 1.0]
        forecast_band: Classification (STRONG_UPTREND, MILD_UPTREND, NEUTRAL, MILD_DOWNTREND, STRONG_DOWNTREND)
    """

    coherence_slope: float  # [-1.0, 1.0]
    continuity_slope: float  # [-1.0, 1.0]
    drift_risk: float  # [0.0, 1.0]
    entropy_risk: float  # [0.0, 1.0]
    forecast_strength: float  # [0.0, 1.0]
    forecast_band: str  # STRONG_UPTREND, MILD_UPTREND, NEUTRAL, MILD_DOWNTREND, STRONG_DOWNTREND


@dataclass
class MultiHorizonForecastSnapshot:
    """
    Immutable snapshot of Multi-Horizon Temporal Forecasting Engine computation.

    Fields:
        h1_forecast: Short-term forecast (1-3 turns)
        h2_forecast: Mid-term forecast (4-8 turns)
        h3_forecast: Long-term forecast (9-20 turns)
        forecast_consensus_index: Agreement across horizons [0.0, 1.0]
        future_stability_envelope: Uncertainty-modulated stability [0.0, 1.0]
        diagnostic_tags: Deterministic diagnostic tags
        raw_signals: Raw signal values for API exposure
    """

    h1_forecast: HorizonForecast  # Short-term (1-3 turns)
    h2_forecast: HorizonForecast  # Mid-term (4-8 turns)
    h3_forecast: HorizonForecast  # Long-term (9-20 turns)
    forecast_consensus_index: float  # [0.0, 1.0]
    future_stability_envelope: float  # [0.0, 1.0]
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


def _compute_drift_risk(
    drift_magnitude: float,
    drift_stability: float,
    entropy_volatility: float,
    horizon_scale: float = 1.0
) -> float:
    """
    Compute drift risk for a specific horizon.

    High drift magnitude + low drift stability + high entropy = high risk
    Risk amplifies with longer horizons.

    Args:
        drift_magnitude: Drift magnitude from Phase 35 [0.0, 1.0]
        drift_stability: Drift stability from Phase 35 [0.0, 1.0]
        entropy_volatility: Temporal entropy volatility [0.0, 1.0]
        horizon_scale: Horizon amplification factor (1.0 for H1, 1.2 for H2, 1.5 for H3)

    Returns:
        float: Drift risk [0.0, 1.0]
    """
    # Base drift risk: high magnitude, low stability
    base_risk = drift_magnitude * (1.0 - drift_stability)

    # Entropy multiplier
    entropy_multiplier = 1.0 + (0.4 * entropy_volatility)

    # Horizon amplification (longer horizons = more risk)
    drift_risk = _clamp(base_risk * entropy_multiplier * horizon_scale, 0.0, 1.0)

    return drift_risk


def _compute_entropy_risk(
    entropy_volatility: float,
    entropy_diff: float,
    horizon_scale: float = 1.0
) -> float:
    """
    Compute forward-looking entropy risk for a specific horizon.

    High current volatility + rising entropy trend = high forward risk
    Risk amplifies with longer horizons.

    Args:
        entropy_volatility: Current entropy volatility [0.0, 1.0]
        entropy_diff: Current entropy diff [0.0, 1.0]
        horizon_scale: Horizon amplification factor (1.0 for H1, 1.1 for H2, 1.3 for H3)

    Returns:
        float: Forward entropy risk [0.0, 1.0]
    """
    # Base risk from current volatility
    base_risk = entropy_volatility

    # Entropy diff contribution (high diff = more chaos)
    diff_risk = entropy_diff * 0.5

    # Weighted blend
    forward_risk = (
        0.65 * base_risk +
        0.35 * diff_risk
    )

    # Horizon amplification
    forward_risk = _clamp(forward_risk * horizon_scale, 0.0, 1.0)

    return forward_risk


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


def _compute_horizon_forecast(
    horizon_name: str,
    window_size: int,
    coherence_history: List[float],
    continuity_history: List[float],
    drift_magnitude: float,
    drift_stability: float,
    entropy_volatility: float,
    entropy_diff: float,
    identity_anchoring: float,
    symbolic_stabilization: float,
    ucf_contribution: float,
    horizon_scale: float
) -> HorizonForecast:
    """
    Compute forecast for a single temporal horizon.

    Args:
        horizon_name: "H1", "H2", or "H3"
        window_size: Number of historical points to use for slope calculation
        coherence_history: Historical coherence values
        continuity_history: Historical continuity values
        drift_magnitude: Current drift magnitude [0.0, 1.0]
        drift_stability: Current drift stability [0.0, 1.0]
        entropy_volatility: Current entropy volatility [0.0, 1.0]
        entropy_diff: Current entropy diff [0.0, 1.0]
        identity_anchoring: Identity anchoring factor [0.0, 1.0]
        symbolic_stabilization: Symbolic stabilization factor [0.0, 1.0]
        ucf_contribution: UCF stability contribution [0.0, 1.0]
        horizon_scale: Horizon-specific risk amplification factor

    Returns:
        HorizonForecast: Forecast for this horizon
    """
    # Compute coherence slope using appropriate window
    coherence_window = coherence_history[-window_size:] if len(coherence_history) >= window_size else coherence_history
    coherence_slope_raw = _compute_linear_slope(coherence_window) if coherence_window else 0.0
    coherence_slope = _normalize_slope(coherence_slope_raw, scale=5.0)

    # Compute continuity slope using appropriate window
    continuity_window = continuity_history[-window_size:] if len(continuity_history) >= window_size else continuity_history
    continuity_slope_raw = _compute_linear_slope(continuity_window) if continuity_window else 0.0
    continuity_slope = _normalize_slope(continuity_slope_raw, scale=5.0)

    # Compute drift risk for this horizon
    drift_risk = _compute_drift_risk(
        drift_magnitude=drift_magnitude,
        drift_stability=drift_stability,
        entropy_volatility=entropy_volatility,
        horizon_scale=horizon_scale
    )

    # Compute entropy risk for this horizon
    entropy_risk = _compute_entropy_risk(
        entropy_volatility=entropy_volatility,
        entropy_diff=entropy_diff,
        horizon_scale=horizon_scale
    )

    # Compute forecast strength
    base_strength = _compute_forecast_strength(
        history=coherence_history,
        slope=coherence_slope_raw,
        window=window_size
    )

    # Apply stabilization factors
    drift_damping = _clamp(1.0 - (0.30 * drift_risk), 0.70, 1.0)
    entropy_damping = _clamp(1.0 - (0.25 * entropy_risk), 0.75, 1.0)

    forecast_strength = (
        base_strength *
        (0.85 + 0.15 * identity_anchoring) *
        (0.90 + 0.10 * symbolic_stabilization) *
        (0.90 + 0.10 * ucf_contribution) *
        drift_damping *
        entropy_damping
    )

    forecast_strength = _clamp(forecast_strength, 0.0, 1.0)

    # Compute weighted trajectory score
    trajectory_score = (
        0.55 * coherence_slope +
        0.45 * continuity_slope
    )

    # Apply forecast strength weighting
    weighted_trajectory = trajectory_score * (0.5 + 0.5 * forecast_strength)

    # Classify forecast band
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

    return HorizonForecast(
        coherence_slope=coherence_slope,
        continuity_slope=continuity_slope,
        drift_risk=drift_risk,
        entropy_risk=entropy_risk,
        forecast_strength=forecast_strength,
        forecast_band=forecast_band
    )


def _compute_forecast_consensus_index(
    h1: HorizonForecast,
    h2: HorizonForecast,
    h3: HorizonForecast
) -> float:
    """
    Compute Forecast Consensus Index (FCI) measuring agreement across horizons.

    High FCI = all horizons agree on direction
    Low FCI = horizons disagree

    Args:
        h1: Short-term forecast
        h2: Mid-term forecast
        h3: Long-term forecast

    Returns:
        float: Forecast Consensus Index [0.0, 1.0]
    """
    # Extract slope directions (sign)
    slopes = [
        h1.coherence_slope,
        h2.coherence_slope,
        h3.coherence_slope
    ]

    # Compute pairwise alignment
    alignments = []
    for i in range(len(slopes)):
        for j in range(i + 1, len(slopes)):
            # Alignment based on dot product of normalized vectors
            # If slopes have same sign and similar magnitude = high alignment
            alignment = 1.0 - abs(slopes[i] - slopes[j]) / 2.0
            alignments.append(alignment)

    # Average alignment
    fci = sum(alignments) / len(alignments) if alignments else 0.5

    return _clamp(fci, 0.0, 1.0)


def _compute_future_stability_envelope(
    h1: HorizonForecast,
    h2: HorizonForecast,
    h3: HorizonForecast,
    coherence_history: List[float],
    identity_anchoring: float,
    symbolic_stabilization: float
) -> float:
    """
    Compute Future Stability Envelope (FSE) measuring stability projection.

    High FSE = stable, predictable future trajectory
    Low FSE = unstable, uncertain future

    Args:
        h1: Short-term forecast
        h2: Mid-term forecast
        h3: Long-term forecast
        coherence_history: Historical coherence values
        identity_anchoring: Identity anchoring factor [0.0, 1.0]
        symbolic_stabilization: Symbolic stabilization factor [0.0, 1.0]

    Returns:
        float: Future Stability Envelope [0.0, 1.0]
    """
    # Component 1: Average forecast strength across horizons
    avg_strength = (h1.forecast_strength + h2.forecast_strength + h3.forecast_strength) / 3.0

    # Component 2: Low drift risk (average across horizons)
    avg_drift_risk = (h1.drift_risk + h2.drift_risk + h3.drift_risk) / 3.0
    drift_stability = 1.0 - avg_drift_risk

    # Component 3: Low entropy risk (average across horizons)
    avg_entropy_risk = (h1.entropy_risk + h2.entropy_risk + h3.entropy_risk) / 3.0
    entropy_stability = 1.0 - avg_entropy_risk

    # Component 4: Historical variance (low variance = stable)
    historical_variance = _compute_variance(coherence_history[-10:]) if len(coherence_history) >= 3 else 0.25
    historical_stability = _clamp(1.0 - min(historical_variance * 4.0, 1.0), 0.0, 1.0)

    # Weighted blend
    fse = (
        0.30 * avg_strength +
        0.25 * drift_stability +
        0.20 * entropy_stability +
        0.15 * historical_stability +
        0.05 * identity_anchoring +
        0.05 * symbolic_stabilization
    )

    return _clamp(fse, 0.0, 1.0)


def compute_multi_horizon_forecast(
    *,
    # Phase 16: Formula Fusion Stabilizer
    coherence_fused_history: Optional[List[float]] = None,
    # Phase 37: Adaptive Continuity Engine
    ncc_history: Optional[List[float]] = None,
    icc_history: Optional[List[float]] = None,
    css_history: Optional[List[float]] = None,
    # Phase 35: Predictive Persona Drift
    drift_magnitude_prediction: Optional[float] = None,
    drift_stability_score: Optional[float] = None,
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
) -> Optional[MultiHorizonForecastSnapshot]:
    """
    Compute Multi-Horizon Temporal Forecasting Engine (MHTFE) v1.0.

    This formula predicts how coherence, continuity, identity, and drift metrics
    are expected to evolve across three temporal horizons:
      • H1 (Short-Term): 1-3 turns
      • H2 (Mid-Term): 4-8 turns
      • H3 (Long-Term): 9-20 turns

    The result is a multi-horizon forecast snapshot containing:
      1. Per-Horizon Forecasts (H1, H2, H3): Each with slopes, risks, strength, band
      2. Forecast Consensus Index (FCI): Agreement across horizons
      3. Future Stability Envelope (FSE): Stability projection
      4. Diagnostic Tags: MULTI_HORIZON_AGREEMENT, SHORT_TERM_NOISE, etc.

    Args:
        coherence_fused_history: Historical fused coherence values
        ncc_history: Historical NCC values (Phase 37)
        icc_history: Historical ICC values (Phase 37)
        css_history: Historical CSS values (Phase 37)
        drift_magnitude_prediction: DMP from Phase 35 [0.0, 1.0]
        drift_stability_score: DSS from Phase 35 [0.0, 1.0]
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

    Returns:
        MultiHorizonForecastSnapshot or None if insufficient data

    Graceful Degradation:
        Returns None if we lack core required signals:
          - At least ONE coherence signal with sufficient history (≥5 points)
          - At least ONE continuity signal with sufficient history (≥5 points)
    """
    tags = []
    raw_signals = {}

    # ========================================================================
    # STEP 1: CHECK CORE INPUT AVAILABILITY (Graceful Degradation)
    # ========================================================================

    # Require coherence history with at least 5 points
    has_coherence_history = (
        coherence_fused_history and len(coherence_fused_history) >= 5
    )

    # Require continuity history with at least 5 points
    has_continuity_history = any([
        ncc_history and len(ncc_history) >= 5,
        icc_history and len(icc_history) >= 5,
        css_history and len(css_history) >= 5,
    ])

    if not (has_coherence_history and has_continuity_history):
        # Insufficient data for MHTFE computation
        return None

    # ========================================================================
    # STEP 2: EXTRACT SIGNALS WITH SAFE FALLBACKS
    # ========================================================================

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

    # ========================================================================
    # STEP 3: PREPARE COHERENCE AND CONTINUITY HISTORIES
    # ========================================================================

    # Use coherence_fused_history as primary coherence signal
    coherence_history = coherence_fused_history if coherence_fused_history else []

    # Construct continuity history (prefer NCC, fallback to ICC, then CSS)
    continuity_history: List[float] = []
    if ncc_history:
        continuity_history = ncc_history
        raw_signals["continuity_source"] = "ncc"
    elif icc_history:
        continuity_history = icc_history
        raw_signals["continuity_source"] = "icc"
        tags.append("continuity_from_icc")
    elif css_history:
        continuity_history = css_history
        raw_signals["continuity_source"] = "css"
        tags.append("continuity_from_css")

    # ========================================================================
    # STEP 4: COMPUTE STABILIZATION FACTORS
    # ========================================================================

    identity_anchoring = _identity_anchoring_factor(
        identity_memory_strength=ims,
        identity_drift_anchoring=ida,
        identity_stability=identity_stability
    )

    symbolic_stabilization = _symbolic_harmonization_stabilizer(
        symbolic_harmonization_index=sym_harm,
        symbolic_harmonization_history=symbolic_harmonization_history
    )

    # UCF contribution
    ucf_contribution = (
        0.50 * coi +
        0.50 * csi
    )
    ucf_contribution = _clamp(ucf_contribution, 0.0, 1.0)

    raw_signals["identity_anchoring"] = identity_anchoring
    raw_signals["symbolic_stabilization"] = symbolic_stabilization
    raw_signals["ucf_contribution"] = ucf_contribution

    # ========================================================================
    # STEP 5: COMPUTE H1 FORECAST (SHORT-TERM: 1-3 TURNS)
    # ========================================================================

    h1_forecast = _compute_horizon_forecast(
        horizon_name="H1",
        window_size=5,  # Recent 5 points for short-term trend
        coherence_history=coherence_history,
        continuity_history=continuity_history,
        drift_magnitude=drift_magnitude,
        drift_stability=drift_stability,
        entropy_volatility=temp_entropy_vol,
        entropy_diff=temp_entropy_diff,
        identity_anchoring=identity_anchoring,
        symbolic_stabilization=symbolic_stabilization,
        ucf_contribution=ucf_contribution,
        horizon_scale=1.0  # No amplification for short-term
    )

    # ========================================================================
    # STEP 6: COMPUTE H2 FORECAST (MID-TERM: 4-8 TURNS)
    # ========================================================================

    h2_forecast = _compute_horizon_forecast(
        horizon_name="H2",
        window_size=8,  # Mid-range 8 points
        coherence_history=coherence_history,
        continuity_history=continuity_history,
        drift_magnitude=drift_magnitude,
        drift_stability=drift_stability,
        entropy_volatility=temp_entropy_vol,
        entropy_diff=temp_entropy_diff,
        identity_anchoring=identity_anchoring,
        symbolic_stabilization=symbolic_stabilization,
        ucf_contribution=ucf_contribution,
        horizon_scale=1.15  # Moderate risk amplification
    )

    # ========================================================================
    # STEP 7: COMPUTE H3 FORECAST (LONG-TERM: 9-20 TURNS)
    # ========================================================================

    h3_forecast = _compute_horizon_forecast(
        horizon_name="H3",
        window_size=min(len(coherence_history), 15),  # Up to 15 points for long-term
        coherence_history=coherence_history,
        continuity_history=continuity_history,
        drift_magnitude=drift_magnitude,
        drift_stability=drift_stability,
        entropy_volatility=temp_entropy_vol,
        entropy_diff=temp_entropy_diff,
        identity_anchoring=identity_anchoring,
        symbolic_stabilization=symbolic_stabilization,
        ucf_contribution=ucf_contribution,
        horizon_scale=1.35  # Higher risk amplification for long-term
    )

    # ========================================================================
    # STEP 8: COMPUTE FORECAST CONSENSUS INDEX (FCI)
    # ========================================================================

    forecast_consensus_index = _compute_forecast_consensus_index(
        h1=h1_forecast,
        h2=h2_forecast,
        h3=h3_forecast
    )

    raw_signals["forecast_consensus_index"] = forecast_consensus_index

    # ========================================================================
    # STEP 9: COMPUTE FUTURE STABILITY ENVELOPE (FSE)
    # ========================================================================

    future_stability_envelope = _compute_future_stability_envelope(
        h1=h1_forecast,
        h2=h2_forecast,
        h3=h3_forecast,
        coherence_history=coherence_history,
        identity_anchoring=identity_anchoring,
        symbolic_stabilization=symbolic_stabilization
    )

    raw_signals["future_stability_envelope"] = future_stability_envelope

    # ========================================================================
    # STEP 10: GENERATE DIAGNOSTIC TAGS
    # ========================================================================

    # Multi-horizon agreement
    if forecast_consensus_index >= 0.75:
        tags.append("MULTI_HORIZON_AGREEMENT")
    elif forecast_consensus_index <= 0.40:
        tags.append("multi_horizon_divergence")

    # Short-term noise (H1 differs significantly from H2/H3)
    h1_slope_avg = (h1_forecast.coherence_slope + h1_forecast.continuity_slope) / 2.0
    h23_slope_avg = (
        h2_forecast.coherence_slope + h2_forecast.continuity_slope +
        h3_forecast.coherence_slope + h3_forecast.continuity_slope
    ) / 4.0

    if abs(h1_slope_avg - h23_slope_avg) >= 0.40:
        tags.append("SHORT_TERM_NOISE")

    # Long-term uncertainty
    if h3_forecast.forecast_strength <= 0.35:
        tags.append("LONG_TERM_UNCERTAINTY")

    # Drift risk rising
    if h3_forecast.drift_risk >= 0.65 and h3_forecast.drift_risk > h1_forecast.drift_risk:
        tags.append("DRIFT_RISK_RISING")

    # Identity supports forecast
    if identity_anchoring >= 0.70 and future_stability_envelope >= 0.65:
        tags.append("IDENTITY_SUPPORTS_FORECAST")

    # Entropy weakening trend
    if h3_forecast.entropy_risk >= 0.65:
        tags.append("ENTROPY_WEAKENING_TREND")

    # All horizons uptrend
    if all(h.forecast_band in ["STRONG_UPTREND", "MILD_UPTREND"] for h in [h1_forecast, h2_forecast, h3_forecast]):
        tags.append("all_horizons_uptrend")

    # All horizons downtrend
    if all(h.forecast_band in ["STRONG_DOWNTREND", "MILD_DOWNTREND"] for h in [h1_forecast, h2_forecast, h3_forecast]):
        tags.append("all_horizons_downtrend")

    # High stability envelope
    if future_stability_envelope >= 0.75:
        tags.append("high_stability_envelope")
    elif future_stability_envelope <= 0.35:
        tags.append("low_stability_envelope")

    # Strong consensus with uptrend
    if forecast_consensus_index >= 0.70 and h23_slope_avg > 0.15:
        tags.append("consensus_uptrend")

    # Strong consensus with downtrend
    if forecast_consensus_index >= 0.70 and h23_slope_avg < -0.15:
        tags.append("consensus_downtrend")

    # ========================================================================
    # STEP 11: STORE ALL RAW SIGNALS FOR API EXPOSURE
    # ========================================================================

    raw_signals.update({
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
        "h1_coherence_slope": h1_forecast.coherence_slope,
        "h1_continuity_slope": h1_forecast.continuity_slope,
        "h1_drift_risk": h1_forecast.drift_risk,
        "h1_entropy_risk": h1_forecast.entropy_risk,
        "h1_forecast_strength": h1_forecast.forecast_strength,
        "h1_forecast_band": h1_forecast.forecast_band,
        "h2_coherence_slope": h2_forecast.coherence_slope,
        "h2_continuity_slope": h2_forecast.continuity_slope,
        "h2_drift_risk": h2_forecast.drift_risk,
        "h2_entropy_risk": h2_forecast.entropy_risk,
        "h2_forecast_strength": h2_forecast.forecast_strength,
        "h2_forecast_band": h2_forecast.forecast_band,
        "h3_coherence_slope": h3_forecast.coherence_slope,
        "h3_continuity_slope": h3_forecast.continuity_slope,
        "h3_drift_risk": h3_forecast.drift_risk,
        "h3_entropy_risk": h3_forecast.entropy_risk,
        "h3_forecast_strength": h3_forecast.forecast_strength,
        "h3_forecast_band": h3_forecast.forecast_band,
    })

    # ========================================================================
    # STEP 12: RETURN SNAPSHOT
    # ========================================================================

    return MultiHorizonForecastSnapshot(
        h1_forecast=h1_forecast,
        h2_forecast=h2_forecast,
        h3_forecast=h3_forecast,
        forecast_consensus_index=forecast_consensus_index,
        future_stability_envelope=future_stability_envelope,
        diagnostic_tags=sorted(set(tags)),  # Deduplicate and sort for determinism
        raw_signals=raw_signals,
    )
