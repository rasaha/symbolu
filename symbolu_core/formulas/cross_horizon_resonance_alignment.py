"""
Cross-Horizon Resonance Alignment Engine (CHRAE) v1.0 - Phase 40

Deterministic, zero-LLM, observation-only analytic layer that aligns multi-horizon
temporal forecasts (Phase 39) with resonance, identity, and drift metrics, producing
Cross-Horizon Resonance Alignment signals.

This formula answers the question:
  "How well do the forecasted trends (H1/H2/H3) line up with the resonance, identity,
   and symbolic signals we already trust?"

CHRAE outputs:
  1. Horizon Alignment Scores (HAS) for each horizon:
     • has_H1, has_H2, has_H3 ∈ [0.0, 1.0]
  2. Resonance Alignment Index (RAI):
     • Global alignment between multi-horizon coherence/continuity slopes and
       resonance weighting, symbolic harmonization, identity & drift metrics
     • rai ∈ [0.0, 1.0]
  3. Identity–Forecast Agreement (IFA):
     • How much identity harmonics + IRM support the forecast directions
     • ifa ∈ [0.0, 1.0]
  4. Drift–Forecast Tension (DFT):
     • Measure of conflict between predicted trends and drift risk
     • dft ∈ [0.0, 1.0] (higher = more tension)
  5. Cross-Horizon Alignment Band:
     • HIGH_ALIGNMENT
     • MIXED_ALIGNMENT
     • LOW_ALIGNMENT
  6. Diagnostic Tags:
     • FORECAST_RES_ON_TRACK
     • FORECAST_RES_MISALIGNED
     • IDENTITY_SUPPORTS_TREND
     • IDENTITY_CONFLICTS_WITH_TREND
     • DRIFT_TENSION_HIGH
     • LONG_TERM_ALIGNMENT_WEAK

CHRAE must not change routing, scoring, mappers, or persona semantics.
It is analytics + tone-only metadata only.

CRITICAL INVARIANTS:
    - Zero-LLM: Purely rule-based, deterministic math only
    - Observation-only: NO changes to routing, TTOR, MLCR, mappers, Fusion, DHA, Renderer
    - Tone-level only: NEVER semantic changes (bounded ±0.015)
    - Non-invasive: Does not modify any existing coherence formulas or behaviors
    - Backward-compatible: All existing tests remain green
    - Deterministic: Same inputs → same outputs always
    - Fully bounded: All outputs [0.0–1.0]
    - Graceful degradation: Returns None if insufficient data
"""

from dataclasses import dataclass, field
from typing import List, Optional

# Import Phase 39 snapshot
from symbolu_core.formulas.multi_horizon_temporal_forecasting import (
    MultiHorizonForecastSnapshot,
    HorizonForecast,
)

# Import Phase 24 snapshot
from symbolu_core.formulas.resonance_weighting import ResonanceWeightingSnapshot

# Import Phase 27 snapshot
from symbolu_core.formulas.symbolic_harmonization import SymbolicHarmonizationSnapshot

# Import Phase 34 snapshot
from symbolu_core.formulas.identity_harmonics import IdentityHarmonicsSnapshot

# Import Phase 36 snapshot
from symbolu_core.formulas.identity_resonance_memory import IdentityResonanceMemorySnapshot

# Import Phase 35 snapshot
from symbolu_core.formulas.predictive_persona_drift import PredictivePersonaDriftSnapshot


@dataclass
class CrossHorizonResonanceSnapshot:
    """
    Immutable snapshot of Cross-Horizon Resonance Alignment computation.

    Fields:
        has_H1: Horizon Alignment Score for H1 [0.0, 1.0]
        has_H2: Horizon Alignment Score for H2 [0.0, 1.0]
        has_H3: Horizon Alignment Score for H3 [0.0, 1.0]
        rai: Resonance Alignment Index [0.0, 1.0]
        ifa: Identity–Forecast Agreement [0.0, 1.0]
        dft: Drift–Forecast Tension [0.0, 1.0]
        alignment_band: "HIGH_ALIGNMENT" | "MIXED_ALIGNMENT" | "LOW_ALIGNMENT"
        diagnostic_tags: Deterministic diagnostic tags
    """

    has_H1: float  # H1 alignment score [0.0, 1.0]
    has_H2: float  # H2 alignment score [0.0, 1.0]
    has_H3: float  # H3 alignment score [0.0, 1.0]
    rai: float  # Resonance Alignment Index [0.0, 1.0]
    ifa: float  # Identity–Forecast Agreement [0.0, 1.0]
    dft: float  # Drift–Forecast Tension [0.0, 1.0]
    alignment_band: str  # "HIGH_ALIGNMENT" | "MIXED_ALIGNMENT" | "LOW_ALIGNMENT"
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


def _compute_horizon_alignment_score(
    horizon_forecast: HorizonForecast,
    resonance_entropy: float,
    symbolic_harmonization: float,
    identity_stability: float,
    drift_risk_tolerance: float = 0.5,
) -> float:
    """
    Compute Horizon Alignment Score (HAS) for a single horizon.

    HAS measures how well the forecasted trend for this horizon aligns with
    trusted signals (resonance, symbolic, identity).

    Higher HAS when:
      - Forecast shows positive trend (upward coherence/continuity slopes)
      - Resonance is focused (low entropy)
      - Symbolic harmonization is strong
      - Identity is stable
      - Drift risk is low
      - Forecast strength is high

    Args:
        horizon_forecast: Forecast for this horizon (H1, H2, or H3)
        resonance_entropy: Resonance weighting entropy [0.0, 1.0]
        symbolic_harmonization: Symbolic harmonization index [0.0, 1.0]
        identity_stability: Identity stability score [0.0, 1.0]
        drift_risk_tolerance: Drift risk tolerance threshold [0.0, 1.0]

    Returns:
        float: Horizon Alignment Score [0.0, 1.0]
    """
    # Component 1: Trend quality (positive slopes + high strength)
    # Average slope (normalized to [0, 1] range)
    avg_slope = (horizon_forecast.coherence_slope + horizon_forecast.continuity_slope) / 2.0
    trend_direction = (avg_slope + 1.0) / 2.0  # Map [-1, 1] to [0, 1]

    # Weight by forecast strength
    trend_quality = trend_direction * horizon_forecast.forecast_strength

    # Component 2: Resonance focus (inverse of entropy)
    resonance_focus = _clamp(1.0 - resonance_entropy, 0.0, 1.0)

    # Component 3: Symbolic alignment
    symbolic_alignment = symbolic_harmonization

    # Component 4: Identity anchoring
    identity_anchoring = identity_stability

    # Component 5: Risk dampening (low drift/entropy risk)
    drift_dampening = _clamp(1.0 - horizon_forecast.drift_risk, 0.0, 1.0)
    entropy_dampening = _clamp(1.0 - horizon_forecast.entropy_risk, 0.0, 1.0)
    risk_dampening = (drift_dampening + entropy_dampening) / 2.0

    # Weighted blend (canonical v1.0 coefficients)
    has_raw = (
        0.30 * trend_quality +
        0.20 * resonance_focus +
        0.20 * symbolic_alignment +
        0.15 * identity_anchoring +
        0.15 * risk_dampening
    )

    return _clamp(has_raw, 0.0, 1.0)


def _compute_resonance_alignment_index(
    has_H1: float,
    has_H2: float,
    has_H3: float,
    forecast_consensus_index: float,
    symbolic_harmonization: float,
    resonance_entropy: float,
    consciousness_order: float,
) -> float:
    """
    Compute Resonance Alignment Index (RAI).

    RAI is a global alignment measure between multi-horizon forecasts and
    resonance/symbolic/consciousness signals.

    Args:
        has_H1: H1 alignment score [0.0, 1.0]
        has_H2: H2 alignment score [0.0, 1.0]
        has_H3: H3 alignment score [0.0, 1.0]
        forecast_consensus_index: FCI from Phase 39 [0.0, 1.0]
        symbolic_harmonization: SHI from Phase 27 [0.0, 1.0]
        resonance_entropy: Resonance weighting entropy [0.0, 1.0]
        consciousness_order: COI from Phase 26 [0.0, 1.0]

    Returns:
        float: Resonance Alignment Index [0.0, 1.0]
    """
    # Component 1: Weighted average of HAS (prioritize mid/long-term)
    has_weighted_avg = (
        0.25 * has_H1 +
        0.35 * has_H2 +
        0.40 * has_H3
    )

    # Component 2: Forecast consensus (all horizons agree)
    consensus_contribution = forecast_consensus_index

    # Component 3: Symbolic harmonization
    symbolic_contribution = symbolic_harmonization

    # Component 4: Resonance focus (inverse of entropy)
    resonance_focus = _clamp(1.0 - resonance_entropy, 0.0, 1.0)

    # Component 5: Consciousness order
    consciousness_contribution = consciousness_order

    # Weighted blend (canonical v1.0 coefficients)
    rai_raw = (
        0.35 * has_weighted_avg +
        0.20 * consensus_contribution +
        0.20 * symbolic_contribution +
        0.15 * resonance_focus +
        0.10 * consciousness_contribution
    )

    return _clamp(rai_raw, 0.0, 1.0)


def _compute_identity_forecast_agreement(
    identity_harmonics: IdentityHarmonicsSnapshot,
    identity_resonance_memory: IdentityResonanceMemorySnapshot,
    h2_forecast: HorizonForecast,
    h3_forecast: HorizonForecast,
) -> float:
    """
    Compute Identity–Forecast Agreement (IFA).

    IFA measures how much identity stability supports the forecasted directions.

    High IFA when:
      - Identity is stable (high CIH, IMS, IDA)
      - Forecast shows positive or neutral trends
      - Identity memory supports forecast direction

    Low IFA when:
      - Identity is stable but forecast predicts sharp disruption
      - Identity memory shows anchoring but forecast predicts large shift

    Args:
        identity_harmonics: Identity harmonics snapshot from Phase 34
        identity_resonance_memory: IRM snapshot from Phase 36
        h2_forecast: Mid-term forecast (H2)
        h3_forecast: Long-term forecast (H3)

    Returns:
        float: Identity–Forecast Agreement [0.0, 1.0]
    """
    # Component 1: Identity stability
    identity_stability = identity_harmonics.identity_stability_score

    # Component 2: Identity memory strength
    identity_memory = identity_resonance_memory.identity_memory_strength

    # Component 3: Identity drift anchoring
    identity_anchoring = identity_resonance_memory.identity_drift_anchoring

    # Component 4: Forecast direction alignment with identity
    # If identity is stable, we expect neutral or positive forecast
    # Negative forecast with stable identity = conflict
    h2_avg_slope = (h2_forecast.coherence_slope + h2_forecast.continuity_slope) / 2.0
    h3_avg_slope = (h3_forecast.coherence_slope + h3_forecast.continuity_slope) / 2.0

    # Convert slopes to alignment scores
    # Positive slope + stable identity = high agreement
    # Negative slope + stable identity = low agreement
    h2_identity_alignment = _clamp((h2_avg_slope + 1.0) / 2.0, 0.0, 1.0)
    h3_identity_alignment = _clamp((h3_avg_slope + 1.0) / 2.0, 0.0, 1.0)

    # Weight by identity stability (stable identity has more weight)
    forecast_identity_alignment = (
        0.45 * h2_identity_alignment +
        0.55 * h3_identity_alignment
    ) * (0.5 + 0.5 * identity_stability)

    # Weighted blend (canonical v1.0 coefficients)
    ifa_raw = (
        0.30 * identity_stability +
        0.25 * identity_memory +
        0.25 * identity_anchoring +
        0.20 * forecast_identity_alignment
    )

    return _clamp(ifa_raw, 0.0, 1.0)


def _compute_drift_forecast_tension(
    predictive_drift: PredictivePersonaDriftSnapshot,
    h1_forecast: HorizonForecast,
    h2_forecast: HorizonForecast,
    h3_forecast: HorizonForecast,
) -> float:
    """
    Compute Drift–Forecast Tension (DFT).

    DFT measures conflict between predicted trends and drift risk.

    High tension when:
      - Forecast indicates uptrend but drift risk is high
      - Forecast indicates stability but drift is accelerating
      - Forecast direction conflicts with drift direction

    Low tension when:
      - Forecast and drift are aligned
      - Both indicate stability or both indicate disruption

    Args:
        predictive_drift: Predictive persona drift snapshot from Phase 35
        h1_forecast: Short-term forecast (H1)
        h2_forecast: Mid-term forecast (H2)
        h3_forecast: Long-term forecast (H3)

    Returns:
        float: Drift–Forecast Tension [0.0, 1.0]
    """
    # Component 1: Drift magnitude vs forecast direction
    # High drift magnitude + positive forecast = tension
    # High drift magnitude + negative forecast = alignment
    avg_forecast_slope = (
        h1_forecast.coherence_slope +
        h2_forecast.coherence_slope +
        h3_forecast.coherence_slope
    ) / 3.0

    # Normalize slope to [0, 1]
    forecast_direction = (avg_forecast_slope + 1.0) / 2.0

    # Drift magnitude
    drift_magnitude = predictive_drift.drift_magnitude_prediction

    # Tension when forecast is positive but drift is high
    directional_tension = drift_magnitude * forecast_direction

    # Component 2: Drift risk vs forecast risk
    avg_drift_risk = (
        h1_forecast.drift_risk +
        h2_forecast.drift_risk +
        h3_forecast.drift_risk
    ) / 3.0

    # Tension when forecast shows low risk but predictive drift is high
    risk_mismatch = abs(drift_magnitude - (1.0 - avg_drift_risk))

    # Component 3: Drift momentum vs forecast strength
    # High drift momentum + high forecast strength pointing different ways = tension
    drift_momentum = predictive_drift.drift_momentum_score
    avg_forecast_strength = (
        h1_forecast.forecast_strength +
        h2_forecast.forecast_strength +
        h3_forecast.forecast_strength
    ) / 3.0

    momentum_tension = drift_momentum * avg_forecast_strength * abs(avg_forecast_slope)

    # Component 4: Drift stability vs forecast consensus
    # Low drift stability + high forecast confidence = tension
    drift_instability = 1.0 - predictive_drift.drift_stability_score

    # Weighted blend (canonical v1.0 coefficients)
    dft_raw = (
        0.35 * directional_tension +
        0.25 * risk_mismatch +
        0.25 * momentum_tension +
        0.15 * drift_instability
    )

    return _clamp(dft_raw, 0.0, 1.0)


def _classify_alignment_band(rai: float, dft: float) -> str:
    """
    Classify cross-horizon alignment band based on RAI and DFT.

    Args:
        rai: Resonance Alignment Index [0.0, 1.0]
        dft: Drift–Forecast Tension [0.0, 1.0]

    Returns:
        str: Alignment band ("HIGH_ALIGNMENT" | "MIXED_ALIGNMENT" | "LOW_ALIGNMENT")
    """
    # HIGH: Strong alignment + low tension
    if rai >= 0.70 and dft <= 0.35:
        return "HIGH_ALIGNMENT"

    # LOW: Weak alignment or high tension
    if rai < 0.40 or dft >= 0.65:
        return "LOW_ALIGNMENT"

    # MIXED: Everything else
    return "MIXED_ALIGNMENT"


def _generate_diagnostic_tags(
    has_H1: float,
    has_H2: float,
    has_H3: float,
    rai: float,
    ifa: float,
    dft: float,
    alignment_band: str,
) -> List[str]:
    """
    Generate diagnostic tags based on CHRAE metrics.

    Args:
        has_H1: H1 alignment score [0.0, 1.0]
        has_H2: H2 alignment score [0.0, 1.0]
        has_H3: H3 alignment score [0.0, 1.0]
        rai: Resonance Alignment Index [0.0, 1.0]
        ifa: Identity–Forecast Agreement [0.0, 1.0]
        dft: Drift–Forecast Tension [0.0, 1.0]
        alignment_band: Alignment band classification

    Returns:
        List[str]: Diagnostic tags
    """
    tags = []

    # RAI-based tags
    if rai >= 0.70:
        tags.append("FORECAST_RES_ON_TRACK")
    elif rai <= 0.40:
        tags.append("FORECAST_RES_MISALIGNED")

    # IFA-based tags
    if ifa >= 0.70:
        tags.append("IDENTITY_SUPPORTS_TREND")
    elif ifa <= 0.35:
        tags.append("IDENTITY_CONFLICTS_WITH_TREND")

    # DFT-based tags
    if dft >= 0.65:
        tags.append("DRIFT_TENSION_HIGH")
    elif dft <= 0.30:
        tags.append("drift_tension_low")

    # Long-term alignment
    if has_H3 <= 0.35:
        tags.append("LONG_TERM_ALIGNMENT_WEAK")
    elif has_H3 >= 0.70:
        tags.append("long_term_alignment_strong")

    # Short-term vs long-term divergence
    if abs(has_H1 - has_H3) >= 0.40:
        tags.append("horizon_alignment_divergent")
    elif abs(has_H1 - has_H3) <= 0.15:
        tags.append("horizon_alignment_consistent")

    # All horizons aligned
    if has_H1 >= 0.65 and has_H2 >= 0.65 and has_H3 >= 0.65:
        tags.append("all_horizons_aligned")

    # Mid-term strength
    if has_H2 >= 0.70:
        tags.append("mid_term_alignment_strong")
    elif has_H2 <= 0.35:
        tags.append("mid_term_alignment_weak")

    # Alignment band tags
    if alignment_band == "HIGH_ALIGNMENT":
        tags.append("chrae_high_alignment")
    elif alignment_band == "LOW_ALIGNMENT":
        tags.append("chrae_low_alignment")
    else:
        tags.append("chrae_mixed_alignment")

    # Complex interaction tags
    if rai >= 0.65 and dft >= 0.60:
        tags.append("aligned_but_tense")
    elif rai <= 0.40 and dft <= 0.35:
        tags.append("misaligned_but_stable")

    if ifa >= 0.70 and dft >= 0.60:
        tags.append("identity_supports_despite_tension")

    return tags


def compute_cross_horizon_resonance(
    multi_horizon_forecast: Optional[MultiHorizonForecastSnapshot],
    resonance_snapshot: Optional[ResonanceWeightingSnapshot] = None,
    symbolic_harmonization: Optional[SymbolicHarmonizationSnapshot] = None,
    identity_harmonics: Optional[IdentityHarmonicsSnapshot] = None,
    identity_resonance_memory: Optional[IdentityResonanceMemorySnapshot] = None,
    predictive_persona_drift: Optional[PredictivePersonaDriftSnapshot] = None,
) -> Optional[CrossHorizonResonanceSnapshot]:
    """
    Compute Cross-Horizon Resonance Alignment Engine (CHRAE) v1.0.

    This formula aligns multi-horizon temporal forecasts (Phase 39) with resonance,
    identity, and drift metrics, producing alignment signals that answer:

    "How well do the forecasted trends (H1/H2/H3) line up with the resonance,
     identity, and symbolic signals we already trust?"

    The result is a cross-horizon resonance snapshot containing:
      1. Horizon Alignment Scores (HAS): has_H1, has_H2, has_H3 [0.0, 1.0]
      2. Resonance Alignment Index (RAI): Global alignment [0.0, 1.0]
      3. Identity–Forecast Agreement (IFA): Identity support [0.0, 1.0]
      4. Drift–Forecast Tension (DFT): Forecast/drift conflict [0.0, 1.0]
      5. Alignment Band: HIGH_ALIGNMENT | MIXED_ALIGNMENT | LOW_ALIGNMENT
      6. Diagnostic Tags: FORECAST_RES_ON_TRACK, IDENTITY_SUPPORTS_TREND, etc.

    Args:
        multi_horizon_forecast: Multi-horizon forecast snapshot from Phase 39
        resonance_snapshot: Resonance weighting snapshot from Phase 24
        symbolic_harmonization: Symbolic harmonization snapshot from Phase 27
        identity_harmonics: Identity harmonics snapshot from Phase 34
        identity_resonance_memory: IRM snapshot from Phase 36
        predictive_persona_drift: Predictive persona drift snapshot from Phase 35

    Returns:
        CrossHorizonResonanceSnapshot or None if insufficient data

    Graceful Degradation:
        Returns None if multi_horizon_forecast is missing (core requirement).
        Uses neutral fallbacks (0.5) for missing optional signals.
    """
    # ========================================================================
    # STEP 1: CHECK CORE INPUT AVAILABILITY (Graceful Degradation)
    # ========================================================================

    # Require multi-horizon forecast (core requirement)
    if multi_horizon_forecast is None:
        return None

    # ========================================================================
    # STEP 2: EXTRACT SIGNALS WITH SAFE FALLBACKS
    # ========================================================================

    # Phase 24: Resonance weighting
    resonance_entropy = 0.5  # Default: neutral
    if resonance_snapshot:
        resonance_entropy = _safe_get(resonance_snapshot.entropy_of_weights, 0.5)

    # Phase 27: Symbolic harmonization
    symbolic_harm_index = 0.5  # Default: neutral
    if symbolic_harmonization:
        symbolic_harm_index = _safe_get(symbolic_harmonization.symbolic_harmonization_index, 0.5)

    # Phase 34: Identity harmonics
    identity_stability = 0.5  # Default: neutral
    core_identity_harmonic = 0.5
    if identity_harmonics:
        identity_stability = _safe_get(identity_harmonics.identity_stability_score, 0.5)
        core_identity_harmonic = _safe_get(identity_harmonics.core_identity_harmonic, 0.5)

    # Phase 26: Unified Consciousness (from multi-horizon raw signals)
    consciousness_order = 0.5  # Default: neutral
    if hasattr(multi_horizon_forecast, 'raw_signals') and 'consciousness_order_index' in multi_horizon_forecast.raw_signals:
        consciousness_order = _safe_get(multi_horizon_forecast.raw_signals.get('consciousness_order_index'), 0.5)

    # ========================================================================
    # STEP 3: COMPUTE HORIZON ALIGNMENT SCORES (HAS)
    # ========================================================================

    has_H1 = _compute_horizon_alignment_score(
        horizon_forecast=multi_horizon_forecast.h1_forecast,
        resonance_entropy=resonance_entropy,
        symbolic_harmonization=symbolic_harm_index,
        identity_stability=identity_stability,
    )

    has_H2 = _compute_horizon_alignment_score(
        horizon_forecast=multi_horizon_forecast.h2_forecast,
        resonance_entropy=resonance_entropy,
        symbolic_harmonization=symbolic_harm_index,
        identity_stability=identity_stability,
    )

    has_H3 = _compute_horizon_alignment_score(
        horizon_forecast=multi_horizon_forecast.h3_forecast,
        resonance_entropy=resonance_entropy,
        symbolic_harmonization=symbolic_harm_index,
        identity_stability=identity_stability,
    )

    # ========================================================================
    # STEP 4: COMPUTE RESONANCE ALIGNMENT INDEX (RAI)
    # ========================================================================

    rai = _compute_resonance_alignment_index(
        has_H1=has_H1,
        has_H2=has_H2,
        has_H3=has_H3,
        forecast_consensus_index=multi_horizon_forecast.forecast_consensus_index,
        symbolic_harmonization=symbolic_harm_index,
        resonance_entropy=resonance_entropy,
        consciousness_order=consciousness_order,
    )

    # ========================================================================
    # STEP 5: COMPUTE IDENTITY–FORECAST AGREEMENT (IFA)
    # ========================================================================

    # If identity signals are missing, use neutral fallback
    if identity_harmonics and identity_resonance_memory:
        ifa = _compute_identity_forecast_agreement(
            identity_harmonics=identity_harmonics,
            identity_resonance_memory=identity_resonance_memory,
            h2_forecast=multi_horizon_forecast.h2_forecast,
            h3_forecast=multi_horizon_forecast.h3_forecast,
        )
    else:
        # Neutral fallback when identity signals unavailable
        ifa = 0.5

    # ========================================================================
    # STEP 6: COMPUTE DRIFT–FORECAST TENSION (DFT)
    # ========================================================================

    # If drift signals are missing, use neutral fallback
    if predictive_persona_drift:
        dft = _compute_drift_forecast_tension(
            predictive_drift=predictive_persona_drift,
            h1_forecast=multi_horizon_forecast.h1_forecast,
            h2_forecast=multi_horizon_forecast.h2_forecast,
            h3_forecast=multi_horizon_forecast.h3_forecast,
        )
    else:
        # Neutral fallback when drift signals unavailable
        dft = 0.5

    # ========================================================================
    # STEP 7: CLASSIFY ALIGNMENT BAND
    # ========================================================================

    alignment_band = _classify_alignment_band(rai=rai, dft=dft)

    # ========================================================================
    # STEP 8: GENERATE DIAGNOSTIC TAGS
    # ========================================================================

    diagnostic_tags = _generate_diagnostic_tags(
        has_H1=has_H1,
        has_H2=has_H2,
        has_H3=has_H3,
        rai=rai,
        ifa=ifa,
        dft=dft,
        alignment_band=alignment_band,
    )

    # ========================================================================
    # STEP 9: RETURN SNAPSHOT
    # ========================================================================

    return CrossHorizonResonanceSnapshot(
        has_H1=has_H1,
        has_H2=has_H2,
        has_H3=has_H3,
        rai=rai,
        ifa=ifa,
        dft=dft,
        alignment_band=alignment_band,
        diagnostic_tags=sorted(set(diagnostic_tags)),  # Deduplicate and sort for determinism
    )
