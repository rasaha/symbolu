"""
P38 Schema - Temporal Coherence Forecasting Types

Defines the data structures for Phase 38: Temporal Coherence Forecasting,
a deterministic observer-only phase that forecasts near-future coherence
stability based on recent coherence history.

CRITICAL CONSTRAINTS:
    - Deterministic: Same inputs -> same outputs (no LLM, no randomness)
    - Read-only: Does not modify system behavior
    - Observer-only: Never used for gating, blocking, or behavior modification
    - Non-authoritative: Does not influence regime, discourse, or semantics

    Phase 38 MUST NOT:
        - Influence regime, discourse, semantics, lexical, or action eligibility
        - Modify PipelineContext in a way that affects upstream decisions
        - Import observer modules or renderer modules
        - Introduce intent, emotion, or policy inference

INVARIANTS:
    - INV-P38-1: Forecast never influences current decisions
    - INV-P38-2: Forecast never escalates authority
    - INV-P38-3: Observer-only behavior enforced
    - INV-P38-4: Deterministic math only
    - INV-P38-5: No acoustic dependency
    - INV-P38-6: Monotonic safety (forecast does not amplify instability)
"""

from dataclasses import dataclass, field
from typing import Any, Dict, Literal, Optional


# =============================================================================
# Version
# =============================================================================

P38_VERSION = "1.0.0"


# =============================================================================
# Type Aliases
# =============================================================================

ForecastTrend = Literal["improving", "stable", "declining"]
ForecastHorizon = Literal["near"]


# =============================================================================
# Constants - Formula Weights
# =============================================================================

# Forecast score weights (must sum to 1.0)
W_CURRENT_QUALITY = 0.40  # Current coherence quality contribution
W_HISTORY_MEAN = 0.30  # Mean of last 3 coherence scores contribution
W_DRIFT_FUSION = 0.20  # (1 - drift_fusion_index) contribution
W_TEMPORAL_ENTROPY = 0.10  # (1 - temporal_entropy_diff) contribution

# Trend thresholds
TREND_IMPROVING_THRESHOLD = 0.05  # forecast > current + 0.05 => improving
TREND_DECLINING_THRESHOLD = 0.05  # forecast < current - 0.05 => declining

# Confidence scaling
CONFIDENCE_HISTORY_DIVISOR = 5  # confidence = min(1.0, history_count / 5)


# =============================================================================
# Dataclasses
# =============================================================================


@dataclass(frozen=True)
class Phase38TemporalForecast:
    """
    Immutable report of temporal coherence forecast computation.

    This is the primary output of Phase 38, containing:
    - forecast_score: Predicted near-future coherence stability [0.0, 1.0]
    - forecast_trend: Classification of trend direction
    - confidence: Confidence level based on history availability [0.0, 1.0]
    - horizon: Always "near" for this phase
    - observer_only: Always True (enforced)

    Invariants:
        - forecast_score in [0.0, 1.0]
        - forecast_trend in {"improving", "stable", "declining"}
        - confidence in [0.0, 1.0]
        - horizon == "near"
        - observer_only == True (cannot be False)
    """

    forecast_score: float
    forecast_trend: ForecastTrend
    confidence: float
    horizon: ForecastHorizon = "near"
    observer_only: bool = True

    # Input signals (for observability)
    current_quality: Optional[float] = None
    history_mean: Optional[float] = None
    drift_fusion_index: Optional[float] = None
    temporal_entropy_diff: Optional[float] = None
    history_count: int = 0

    # Debug info
    debug: Dict[str, Any] = field(default_factory=dict)

    # Metadata
    version: str = P38_VERSION
    architectural_phase: str = "P38"

    def __post_init__(self) -> None:
        """Validate invariants."""
        # observer_only must be True
        if not self.observer_only:
            raise ValueError(
                "Phase38TemporalForecast.observer_only must be True. "
                "P38 is observation-only and cannot be used for gating."
            )

        # forecast_score must be in [0.0, 1.0]
        if not isinstance(self.forecast_score, (int, float)):
            raise ValueError(
                f"Phase38TemporalForecast.forecast_score must be numeric, "
                f"got {type(self.forecast_score).__name__}"
            )
        if not 0.0 <= self.forecast_score <= 1.0:
            raise ValueError(
                f"Phase38TemporalForecast.forecast_score must be in [0.0, 1.0], "
                f"got {self.forecast_score}"
            )

        # confidence must be in [0.0, 1.0]
        if not isinstance(self.confidence, (int, float)):
            raise ValueError(
                f"Phase38TemporalForecast.confidence must be numeric, "
                f"got {type(self.confidence).__name__}"
            )
        if not 0.0 <= self.confidence <= 1.0:
            raise ValueError(
                f"Phase38TemporalForecast.confidence must be in [0.0, 1.0], "
                f"got {self.confidence}"
            )

        # forecast_trend must be valid
        if self.forecast_trend not in ("improving", "stable", "declining"):
            raise ValueError(
                f"Phase38TemporalForecast.forecast_trend must be 'improving', "
                f"'stable', or 'declining', got '{self.forecast_trend}'"
            )

        # horizon must be "near"
        if self.horizon != "near":
            raise ValueError(
                f"Phase38TemporalForecast.horizon must be 'near', "
                f"got '{self.horizon}'"
            )

    # -------------------------------------------------------------------------
    # Convenience methods
    # -------------------------------------------------------------------------

    def is_improving(self) -> bool:
        """Return True if forecast trend is improving."""
        return self.forecast_trend == "improving"

    def is_stable(self) -> bool:
        """Return True if forecast trend is stable."""
        return self.forecast_trend == "stable"

    def is_declining(self) -> bool:
        """Return True if forecast trend is declining."""
        return self.forecast_trend == "declining"

    def has_high_confidence(self) -> bool:
        """Return True if confidence >= 0.8."""
        return self.confidence >= 0.8

    def has_low_confidence(self) -> bool:
        """Return True if confidence < 0.4."""
        return self.confidence < 0.4

    def to_dict(self) -> Dict[str, Any]:
        """Serialize report to dictionary for API/JSON output."""
        return {
            "forecast_score": self.forecast_score,
            "forecast_trend": self.forecast_trend,
            "confidence": self.confidence,
            "horizon": self.horizon,
            "observer_only": self.observer_only,
            "inputs": {
                "current_quality": self.current_quality,
                "history_mean": self.history_mean,
                "drift_fusion_index": self.drift_fusion_index,
                "temporal_entropy_diff": self.temporal_entropy_diff,
                "history_count": self.history_count,
            },
            "debug": self.debug,
            "version": self.version,
            "architectural_phase": self.architectural_phase,
        }


# =============================================================================
# Helper Functions
# =============================================================================


def create_forecast(
    forecast_score: float,
    forecast_trend: ForecastTrend,
    confidence: float,
    current_quality: Optional[float] = None,
    history_mean: Optional[float] = None,
    drift_fusion_index: Optional[float] = None,
    temporal_entropy_diff: Optional[float] = None,
    history_count: int = 0,
    debug: Optional[Dict[str, Any]] = None,
) -> Phase38TemporalForecast:
    """
    Factory function to create a Phase38TemporalForecast.

    Args:
        forecast_score: Predicted coherence stability [0.0, 1.0]
        forecast_trend: Trend classification
        confidence: Confidence level [0.0, 1.0]
        current_quality: Current P12 quality input
        history_mean: Mean of last 3 coherence scores
        drift_fusion_index: P19 drift fusion input
        temporal_entropy_diff: P18 entropy diff input
        history_count: Number of history points used
        debug: Optional debug dictionary

    Returns:
        Phase38TemporalForecast instance
    """
    return Phase38TemporalForecast(
        forecast_score=forecast_score,
        forecast_trend=forecast_trend,
        confidence=confidence,
        horizon="near",
        observer_only=True,
        current_quality=current_quality,
        history_mean=history_mean,
        drift_fusion_index=drift_fusion_index,
        temporal_entropy_diff=temporal_entropy_diff,
        history_count=history_count,
        debug=debug or {},
    )


def create_empty_forecast() -> Phase38TemporalForecast:
    """
    Create an empty/default forecast when no inputs are available.

    Returns:
        Phase38TemporalForecast with neutral values
    """
    return Phase38TemporalForecast(
        forecast_score=0.5,
        forecast_trend="stable",
        confidence=0.0,
        horizon="near",
        observer_only=True,
        current_quality=None,
        history_mean=None,
        drift_fusion_index=None,
        temporal_entropy_diff=None,
        history_count=0,
        debug={"reason": "no_inputs_available"},
    )


# Public exports
__all__ = [
    # Version
    "P38_VERSION",
    # Type Aliases
    "ForecastTrend",
    "ForecastHorizon",
    # Constants
    "W_CURRENT_QUALITY",
    "W_HISTORY_MEAN",
    "W_DRIFT_FUSION",
    "W_TEMPORAL_ENTROPY",
    "TREND_IMPROVING_THRESHOLD",
    "TREND_DECLINING_THRESHOLD",
    "CONFIDENCE_HISTORY_DIVISOR",
    # Dataclasses
    "Phase38TemporalForecast",
    # Helpers
    "create_forecast",
    "create_empty_forecast",
]
