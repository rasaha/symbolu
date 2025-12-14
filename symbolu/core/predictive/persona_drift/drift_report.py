"""
P35 - Predictive Persona Drift Report Schema Definitions

P35 is an observation-only forecasting phase that predicts whether the user's
expressed identity is likely to drift in the near future. It produces a
forecast signal, NOT a decision.

P35 answers: "Given current trajectories, is the user's expressed identity
likely to drift in the near future?"

P35 does NOT:
- Predict behavior
- Infer intent
- Trigger interventions
- Modify persona delivery
- Influence regime or discourse
- Change semantics or lexical selection (P8-P9)
- Influence DHA, Persona Engine, Renderer
- Influence insight gating (P32)

P35 MAY:
- Produce numeric drift forecasts
- Label drift risk bands
- Emit explanatory tags

CRITICAL CONSTRAINTS:
    - Deterministic: Same inputs -> same outputs (no LLM, no randomness)
    - Read-only: Does not modify system behavior
    - Non-invasive: Zero impact on routing, TTOR, MLCR, Fusion, DHA, Renderer
    - Observation-only: Never used for gating, blocking, or behavior modification
    - No acoustic dependency: P22-P24 observers are FORBIDDEN as direct inputs

INVARIANTS:
    - INV-P35-1: Forecast never influences current decisions
    - INV-P35-2: Prediction never escalates authority
    - INV-P35-3: Observer-only behavior enforced
    - INV-P35-4: Deterministic math only
    - INV-P35-5: No acoustic dependency
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, FrozenSet, List, Optional, Tuple


# =============================================================================
# VERSION
# =============================================================================

P35_VERSION = "1.0.0"


# =============================================================================
# ENUMS
# =============================================================================


class DriftRiskBand(str, Enum):
    """
    Classification of predicted drift risk severity.

    LOW: Predicted drift score < 0.35
    MODERATE: Predicted drift score >= 0.35 and < 0.65
    HIGH: Predicted drift score >= 0.65
    """
    LOW = "low"
    MODERATE = "moderate"
    HIGH = "high"


class TrendDirection(str, Enum):
    """
    Classification of drift trend direction based on historical snapshots.

    STABLE: No significant change detected
    WORSENING: 2+ signals increased > +0.05
    IMPROVING: 2+ signals decreased > -0.05
    """
    STABLE = "stable"
    WORSENING = "worsening"
    IMPROVING = "improving"


class ForecastHorizon(str, Enum):
    """
    Forecast time horizon classification.

    For Phase 35, only SHORT is used.
    """
    SHORT = "short"


# =============================================================================
# CONTRIBUTING FACTOR TAGS
# =============================================================================

ALLOWED_CONTRIBUTING_FACTORS: FrozenSet[str] = frozenset({
    "SCHEMA_INSTABILITY",
    "TEMPORAL_ENTROPY_RISING",
    "COHERENCE_DECAY",
    "IDENTITY_HARMONICS_WEAKENING",
    "CROSS_SIGNAL_VOLATILITY",
})


# =============================================================================
# FORMULA WEIGHTS - LOCKED
# =============================================================================

# Base predictive drift score weights (must sum to 1.0)
W_DRIFT_FUSION_INDEX = 0.35
W_SCHEMA_DRIFT = 0.25
W_TEMPORAL_ENTROPY_DIFF = 0.20
W_COHERENCE_QUALITY = 0.10  # (1 - coherence_v3_quality)
W_UCF_SCORE = 0.10  # (1 - ucf_score)

# Risk band thresholds
RISK_BAND_LOW_THRESHOLD = 0.35  # score < 0.35 -> "low"
RISK_BAND_HIGH_THRESHOLD = 0.65  # score >= 0.65 -> "high"

# Trend detection threshold
TREND_CHANGE_THRESHOLD = 0.05  # |delta| > 0.05 counts as change
TREND_MIN_SIGNALS = 2  # At least 2 signals must show change

# Contributing factor thresholds
SCHEMA_INSTABILITY_THRESHOLD = 0.50
TEMPORAL_ENTROPY_THRESHOLD = 0.55
COHERENCE_DECAY_THRESHOLD = 0.45  # coherence_v3_quality < threshold
IDENTITY_HARMONICS_THRESHOLD = 0.45  # identity_harmonics_score < threshold
CROSS_SIGNAL_VOLATILITY_THRESHOLD = 0.10  # variance > threshold


# =============================================================================
# DATACLASSES
# =============================================================================


@dataclass(frozen=True)
class PredictivePersonaDriftReport:
    """
    Immutable report of predictive persona drift computation.

    This is the primary output of Phase 35, containing:
    - predicted_drift_score: Overall drift forecast [0.0, 1.0]
    - drift_risk_band: Risk classification (low/moderate/high)
    - trend_direction: Direction of drift (stable/worsening/improving)
    - forecast_horizon: Time horizon (always "short" for P35)
    - contributing_factors: List of factors driving the forecast
    - confidence: Confidence in the forecast [0.0, 1.0]

    Plus the input signals used for computation (for observability).

    INVARIANTS:
        - predicted_drift_score in [0.0, 1.0]
        - confidence in [0.0, 1.0]
        - drift_risk_band in {"low", "moderate", "high"}
        - trend_direction in {"stable", "worsening", "improving"}
        - forecast_horizon is always "short"
        - observer_only is always True
    """

    # Core outputs
    predicted_drift_score: float
    drift_risk_band: str
    trend_direction: str
    forecast_horizon: str
    contributing_factors: Tuple[str, ...]  # Immutable tuple
    confidence: float

    # Input signals (for observability)
    drift_fusion_index: Optional[float] = None
    schema_drift: Optional[float] = None
    temporal_entropy_diff: Optional[float] = None
    coherence_v3_quality: Optional[float] = None
    ucf_score: Optional[float] = None
    identity_harmonics_score: Optional[float] = None

    # History snapshot count used for trend/confidence calculation
    history_snapshot_count: int = 0

    # Debug info
    debug: Dict[str, Any] = field(default_factory=dict)

    # Authority markers - MUST be True
    observer_only: bool = True
    architectural_phase: str = "P35"
    version: str = P35_VERSION

    def __post_init__(self) -> None:
        """Validate invariants."""
        # INV-P35-3: observer_only must always be True
        if not self.observer_only:
            raise ValueError(
                "PredictivePersonaDriftReport.observer_only must be True. "
                "P35 is observation-only and non-authoritative."
            )

        # Clamp predicted_drift_score to [0.0, 1.0]
        if not isinstance(self.predicted_drift_score, (int, float)):
            raise ValueError(
                f"predicted_drift_score must be numeric, "
                f"got {type(self.predicted_drift_score).__name__}"
            )
        if not (0.0 <= self.predicted_drift_score <= 1.0):
            object.__setattr__(
                self, 'predicted_drift_score',
                max(0.0, min(1.0, self.predicted_drift_score))
            )

        # Validate confidence in [0.0, 1.0]
        if not isinstance(self.confidence, (int, float)):
            raise ValueError(
                f"confidence must be numeric, "
                f"got {type(self.confidence).__name__}"
            )
        if not (0.0 <= self.confidence <= 1.0):
            object.__setattr__(
                self, 'confidence',
                max(0.0, min(1.0, self.confidence))
            )

        # Validate drift_risk_band
        if self.drift_risk_band not in ("low", "moderate", "high"):
            raise ValueError(
                f"drift_risk_band must be 'low', 'moderate', or 'high', "
                f"got '{self.drift_risk_band}'"
            )

        # Validate trend_direction
        if self.trend_direction not in ("stable", "worsening", "improving"):
            raise ValueError(
                f"trend_direction must be 'stable', 'worsening', or 'improving', "
                f"got '{self.trend_direction}'"
            )

        # Validate forecast_horizon (must be "short" for P35)
        if self.forecast_horizon != "short":
            raise ValueError(
                f"forecast_horizon must be 'short' for P35, "
                f"got '{self.forecast_horizon}'"
            )

        # Validate contributing_factors - must be subset of allowed tags
        if not isinstance(self.contributing_factors, tuple):
            raise ValueError(
                f"contributing_factors must be tuple, "
                f"got {type(self.contributing_factors).__name__}"
            )
        invalid_factors = set(self.contributing_factors) - ALLOWED_CONTRIBUTING_FACTORS
        if invalid_factors:
            raise ValueError(
                f"contributing_factors contains invalid tags: {invalid_factors}"
            )

    # -------------------------------------------------------------------------
    # Convenience methods
    # -------------------------------------------------------------------------

    def is_low_risk(self) -> bool:
        """Return True if predicted drift risk is low."""
        return self.drift_risk_band == "low"

    def is_moderate_risk(self) -> bool:
        """Return True if predicted drift risk is moderate."""
        return self.drift_risk_band == "moderate"

    def is_high_risk(self) -> bool:
        """Return True if predicted drift risk is high."""
        return self.drift_risk_band == "high"

    def is_stable(self) -> bool:
        """Return True if trend direction is stable."""
        return self.trend_direction == "stable"

    def is_worsening(self) -> bool:
        """Return True if trend direction is worsening."""
        return self.trend_direction == "worsening"

    def is_improving(self) -> bool:
        """Return True if trend direction is improving."""
        return self.trend_direction == "improving"

    def has_schema_instability(self) -> bool:
        """Return True if SCHEMA_INSTABILITY factor is present."""
        return "SCHEMA_INSTABILITY" in self.contributing_factors

    def has_temporal_entropy_rising(self) -> bool:
        """Return True if TEMPORAL_ENTROPY_RISING factor is present."""
        return "TEMPORAL_ENTROPY_RISING" in self.contributing_factors

    def has_coherence_decay(self) -> bool:
        """Return True if COHERENCE_DECAY factor is present."""
        return "COHERENCE_DECAY" in self.contributing_factors

    def has_identity_harmonics_weakening(self) -> bool:
        """Return True if IDENTITY_HARMONICS_WEAKENING factor is present."""
        return "IDENTITY_HARMONICS_WEAKENING" in self.contributing_factors

    def has_cross_signal_volatility(self) -> bool:
        """Return True if CROSS_SIGNAL_VOLATILITY factor is present."""
        return "CROSS_SIGNAL_VOLATILITY" in self.contributing_factors

    def factor_count(self) -> int:
        """Return the number of contributing factors."""
        return len(self.contributing_factors)

    def to_dict(self) -> Dict[str, Any]:
        """Serialize report to dictionary for API/JSON output."""
        return {
            "predicted_drift_score": self.predicted_drift_score,
            "drift_risk_band": self.drift_risk_band,
            "trend_direction": self.trend_direction,
            "forecast_horizon": self.forecast_horizon,
            "contributing_factors": list(self.contributing_factors),
            "confidence": self.confidence,
            "inputs": {
                "drift_fusion_index": self.drift_fusion_index,
                "schema_drift": self.schema_drift,
                "temporal_entropy_diff": self.temporal_entropy_diff,
                "coherence_v3_quality": self.coherence_v3_quality,
                "ucf_score": self.ucf_score,
                "identity_harmonics_score": self.identity_harmonics_score,
            },
            "history_snapshot_count": self.history_snapshot_count,
            "debug": self.debug,
            "observer_only": self.observer_only,
            "architectural_phase": self.architectural_phase,
            "version": self.version,
        }


# =============================================================================
# HELPER FUNCTIONS
# =============================================================================


def create_report(
    predicted_drift_score: float,
    drift_risk_band: str,
    trend_direction: str,
    contributing_factors: List[str],
    confidence: float,
    drift_fusion_index: Optional[float] = None,
    schema_drift: Optional[float] = None,
    temporal_entropy_diff: Optional[float] = None,
    coherence_v3_quality: Optional[float] = None,
    ucf_score: Optional[float] = None,
    identity_harmonics_score: Optional[float] = None,
    history_snapshot_count: int = 0,
    debug: Optional[Dict[str, Any]] = None,
) -> PredictivePersonaDriftReport:
    """
    Factory function to create a PredictivePersonaDriftReport.

    Args:
        predicted_drift_score: Overall drift forecast [0.0, 1.0]
        drift_risk_band: Risk band ("low", "moderate", "high")
        trend_direction: Trend direction ("stable", "worsening", "improving")
        contributing_factors: List of contributing factor tags
        confidence: Confidence in forecast [0.0, 1.0]
        drift_fusion_index: P19 drift fusion index input
        schema_drift: P33 schema drift input
        temporal_entropy_diff: P18 temporal entropy diff input
        coherence_v3_quality: P12 coherence quality input
        ucf_score: P26 UCF score input
        identity_harmonics_score: P34 identity harmonics input
        history_snapshot_count: Number of historical snapshots used
        debug: Optional debug dictionary

    Returns:
        PredictivePersonaDriftReport instance
    """
    return PredictivePersonaDriftReport(
        predicted_drift_score=predicted_drift_score,
        drift_risk_band=drift_risk_band,
        trend_direction=trend_direction,
        forecast_horizon="short",  # Always "short" for P35
        contributing_factors=tuple(contributing_factors),
        confidence=confidence,
        drift_fusion_index=drift_fusion_index,
        schema_drift=schema_drift,
        temporal_entropy_diff=temporal_entropy_diff,
        coherence_v3_quality=coherence_v3_quality,
        ucf_score=ucf_score,
        identity_harmonics_score=identity_harmonics_score,
        history_snapshot_count=history_snapshot_count,
        debug=debug or {},
        observer_only=True,  # Always True
    )


def risk_band_from_score(score: float) -> str:
    """
    Determine risk band from predicted drift score.

    Args:
        score: Predicted drift score [0.0, 1.0]

    Returns:
        Risk band string: "low", "moderate", or "high"
    """
    if score < RISK_BAND_LOW_THRESHOLD:
        return "low"
    elif score < RISK_BAND_HIGH_THRESHOLD:
        return "moderate"
    else:
        return "high"


def create_empty_report() -> PredictivePersonaDriftReport:
    """
    Create an empty report with default values.

    Used when P35 cannot compute meaningful metrics (e.g., missing inputs).

    Returns:
        A minimal PredictivePersonaDriftReport with neutral defaults
    """
    return create_report(
        predicted_drift_score=0.0,
        drift_risk_band="low",
        trend_direction="stable",
        contributing_factors=[],
        confidence=0.0,
        history_snapshot_count=0,
        debug={"reason": "empty_report_insufficient_inputs"},
    )


# Public exports
__all__ = [
    # Version
    "P35_VERSION",
    # Enums
    "DriftRiskBand",
    "TrendDirection",
    "ForecastHorizon",
    # Constants
    "ALLOWED_CONTRIBUTING_FACTORS",
    "W_DRIFT_FUSION_INDEX",
    "W_SCHEMA_DRIFT",
    "W_TEMPORAL_ENTROPY_DIFF",
    "W_COHERENCE_QUALITY",
    "W_UCF_SCORE",
    "RISK_BAND_LOW_THRESHOLD",
    "RISK_BAND_HIGH_THRESHOLD",
    "TREND_CHANGE_THRESHOLD",
    "TREND_MIN_SIGNALS",
    "SCHEMA_INSTABILITY_THRESHOLD",
    "TEMPORAL_ENTROPY_THRESHOLD",
    "COHERENCE_DECAY_THRESHOLD",
    "IDENTITY_HARMONICS_THRESHOLD",
    "CROSS_SIGNAL_VOLATILITY_THRESHOLD",
    # Dataclasses
    "PredictivePersonaDriftReport",
    # Helpers
    "create_report",
    "risk_band_from_score",
    "create_empty_report",
]
