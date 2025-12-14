"""
P39 Schema - Multi-Horizon Temporal Forecasting Types

Defines the data structures for Phase 39: Multi-Horizon Temporal Forecasting,
a deterministic observer-only phase that extends Phase 38's single-horizon
forecast into parallel short/medium/long horizon projections.

CRITICAL CONSTRAINTS:
    - Deterministic: Same inputs -> same outputs (no LLM, no randomness)
    - Read-only: Does not modify system behavior
    - Observer-only: Never used for gating, blocking, or behavior modification
    - Non-authoritative: Does not influence regime, discourse, or semantics

    Phase 39 MUST NOT:
        - Influence regime, discourse, semantics, lexical, or action eligibility
        - Modify PipelineContext in a way that affects upstream decisions
        - Import observer modules or renderer modules
        - Introduce intent, emotion, or policy inference

INVARIANTS:
    - INV-P39-1: Observer-only (no influence on any authoritative phase)
    - INV-P39-2: Deterministic (same inputs -> same outputs)
    - INV-P39-3: Horizon monotonicity (flag if long_term > short_term, do not correct)
    - INV-P39-4: No horizon can exceed Phase 38 base forecast
    - INV-P39-5: Absence-safe (missing inputs degrade confidence, never inflate)
"""

from dataclasses import dataclass, field
from typing import Any, Dict, Literal, Optional


# =============================================================================
# Version
# =============================================================================

P39_VERSION = "1.0.0"


# =============================================================================
# Type Aliases
# =============================================================================

HorizonBand = Literal["stable", "strained", "volatile"]


# =============================================================================
# Constants - Formula Weights
# =============================================================================

# Multi-horizon degradation weights
# short_term = P38.score (no degradation)
# medium_term = P38.score - ALPHA * drift_index
# long_term = P38.score - BETA * drift_index - GAMMA * entropy_volatility

ALPHA = 0.15  # Drift degradation for medium term
BETA = 0.25   # Drift degradation for long term
GAMMA = 0.15  # Entropy volatility degradation for long term

# All weights must satisfy constraint: ALPHA + BETA + GAMMA <= 1.0
_WEIGHT_SUM = ALPHA + BETA + GAMMA
assert _WEIGHT_SUM <= 1.0, f"Weight sum {_WEIGHT_SUM} exceeds 1.0"

# Risk band thresholds
BAND_STABLE_THRESHOLD = 0.75   # score >= 0.75 -> "stable"
BAND_STRAINED_THRESHOLD = 0.45  # score >= 0.45 -> "strained"
# score < 0.45 -> "volatile"


# =============================================================================
# Helper Functions
# =============================================================================


def classify_band(score: float) -> HorizonBand:
    """
    Classify a horizon score into a risk band.

    Thresholds:
        - score >= 0.75 -> "stable"
        - score >= 0.45 -> "strained"
        - score < 0.45 -> "volatile"

    Args:
        score: Horizon score in [0.0, 1.0]

    Returns:
        Risk band classification
    """
    if score >= BAND_STABLE_THRESHOLD:
        return "stable"
    elif score >= BAND_STRAINED_THRESHOLD:
        return "strained"
    else:
        return "volatile"


# =============================================================================
# Dataclasses
# =============================================================================


@dataclass(frozen=True)
class MultiHorizonForecast:
    """
    Immutable report of multi-horizon temporal forecasting.

    This is the primary output of Phase 39, containing:
    - short_term_score: Short-horizon stability forecast [0.0, 1.0]
    - medium_term_score: Medium-horizon stability forecast [0.0, 1.0]
    - long_term_score: Long-horizon stability forecast [0.0, 1.0]
    - short_term_band: Risk classification for short horizon
    - medium_term_band: Risk classification for medium horizon
    - long_term_band: Risk classification for long horizon
    - horizon_divergence: max(scores) - min(scores)
    - observer_only: Always True (enforced)

    Invariants:
        - All scores in [0.0, 1.0]
        - All bands in {"stable", "strained", "volatile"}
        - observer_only == True (cannot be False)
        - horizon_divergence >= 0.0
    """

    # Core outputs (all required)
    short_term_score: float
    medium_term_score: float
    long_term_score: float
    short_term_band: HorizonBand
    medium_term_band: HorizonBand
    long_term_band: HorizonBand
    horizon_divergence: float
    observer_only: Literal[True]

    # Input signals (for observability)
    p38_forecast_score: Optional[float] = None
    drift_fusion_index: Optional[float] = None
    entropy_volatility: Optional[float] = None
    monotonicity_violated: bool = False  # True if long_term > short_term

    # Debug info
    debug: Dict[str, Any] = field(default_factory=dict)

    # Metadata
    version: str = P39_VERSION
    architectural_phase: str = "P39"

    def __post_init__(self) -> None:
        """Validate invariants."""
        # observer_only must be True (INV-P39-1)
        if self.observer_only is not True:
            raise ValueError(
                "MultiHorizonForecast.observer_only must be True. "
                "P39 is observation-only and cannot be used for gating."
            )

        # Validate score ranges
        for name, score in [
            ("short_term_score", self.short_term_score),
            ("medium_term_score", self.medium_term_score),
            ("long_term_score", self.long_term_score),
        ]:
            if not isinstance(score, (int, float)):
                raise ValueError(
                    f"MultiHorizonForecast.{name} must be numeric, "
                    f"got {type(score).__name__}"
                )
            if not 0.0 <= score <= 1.0:
                raise ValueError(
                    f"MultiHorizonForecast.{name} must be in [0.0, 1.0], "
                    f"got {score}"
                )

        # Validate bands
        valid_bands = ("stable", "strained", "volatile")
        for name, band in [
            ("short_term_band", self.short_term_band),
            ("medium_term_band", self.medium_term_band),
            ("long_term_band", self.long_term_band),
        ]:
            if band not in valid_bands:
                raise ValueError(
                    f"MultiHorizonForecast.{name} must be one of {valid_bands}, "
                    f"got '{band}'"
                )

        # Validate horizon_divergence
        if not isinstance(self.horizon_divergence, (int, float)):
            raise ValueError(
                f"MultiHorizonForecast.horizon_divergence must be numeric, "
                f"got {type(self.horizon_divergence).__name__}"
            )
        if self.horizon_divergence < 0.0:
            raise ValueError(
                f"MultiHorizonForecast.horizon_divergence must be >= 0.0, "
                f"got {self.horizon_divergence}"
            )

    # -------------------------------------------------------------------------
    # Convenience methods
    # -------------------------------------------------------------------------

    def is_short_term_stable(self) -> bool:
        """Return True if short-term band is stable."""
        return self.short_term_band == "stable"

    def is_medium_term_stable(self) -> bool:
        """Return True if medium-term band is stable."""
        return self.medium_term_band == "stable"

    def is_long_term_stable(self) -> bool:
        """Return True if long-term band is stable."""
        return self.long_term_band == "stable"

    def all_horizons_stable(self) -> bool:
        """Return True if all horizons are stable."""
        return (
            self.short_term_band == "stable"
            and self.medium_term_band == "stable"
            and self.long_term_band == "stable"
        )

    def any_horizon_volatile(self) -> bool:
        """Return True if any horizon is volatile."""
        return "volatile" in (
            self.short_term_band,
            self.medium_term_band,
            self.long_term_band,
        )

    def has_high_divergence(self, threshold: float = 0.3) -> bool:
        """Return True if horizon_divergence exceeds threshold."""
        return self.horizon_divergence >= threshold

    def to_dict(self) -> Dict[str, Any]:
        """Serialize report to dictionary for API/JSON output."""
        return {
            "short_term_score": self.short_term_score,
            "medium_term_score": self.medium_term_score,
            "long_term_score": self.long_term_score,
            "short_term_band": self.short_term_band,
            "medium_term_band": self.medium_term_band,
            "long_term_band": self.long_term_band,
            "horizon_divergence": self.horizon_divergence,
            "observer_only": self.observer_only,
            "monotonicity_violated": self.monotonicity_violated,
            "inputs": {
                "p38_forecast_score": self.p38_forecast_score,
                "drift_fusion_index": self.drift_fusion_index,
                "entropy_volatility": self.entropy_volatility,
            },
            "debug": self.debug,
            "version": self.version,
            "architectural_phase": self.architectural_phase,
        }


# =============================================================================
# Factory Functions
# =============================================================================


def create_forecast(
    short_term_score: float,
    medium_term_score: float,
    long_term_score: float,
    short_term_band: HorizonBand,
    medium_term_band: HorizonBand,
    long_term_band: HorizonBand,
    horizon_divergence: float,
    p38_forecast_score: Optional[float] = None,
    drift_fusion_index: Optional[float] = None,
    entropy_volatility: Optional[float] = None,
    monotonicity_violated: bool = False,
    debug: Optional[Dict[str, Any]] = None,
) -> MultiHorizonForecast:
    """
    Factory function to create a MultiHorizonForecast.

    Args:
        short_term_score: Short-horizon stability [0.0, 1.0]
        medium_term_score: Medium-horizon stability [0.0, 1.0]
        long_term_score: Long-horizon stability [0.0, 1.0]
        short_term_band: Risk band for short horizon
        medium_term_band: Risk band for medium horizon
        long_term_band: Risk band for long horizon
        horizon_divergence: max(scores) - min(scores)
        p38_forecast_score: Phase 38 base forecast input
        drift_fusion_index: P19 drift fusion input
        entropy_volatility: P18 entropy volatility input
        monotonicity_violated: True if long_term > short_term
        debug: Optional debug dictionary

    Returns:
        MultiHorizonForecast instance
    """
    return MultiHorizonForecast(
        short_term_score=short_term_score,
        medium_term_score=medium_term_score,
        long_term_score=long_term_score,
        short_term_band=short_term_band,
        medium_term_band=medium_term_band,
        long_term_band=long_term_band,
        horizon_divergence=horizon_divergence,
        observer_only=True,
        p38_forecast_score=p38_forecast_score,
        drift_fusion_index=drift_fusion_index,
        entropy_volatility=entropy_volatility,
        monotonicity_violated=monotonicity_violated,
        debug=debug or {},
    )


# Public exports
__all__ = [
    # Version
    "P39_VERSION",
    # Type Aliases
    "HorizonBand",
    # Constants
    "ALPHA",
    "BETA",
    "GAMMA",
    "BAND_STABLE_THRESHOLD",
    "BAND_STRAINED_THRESHOLD",
    # Helpers
    "classify_band",
    # Dataclasses
    "MultiHorizonForecast",
    # Factory
    "create_forecast",
]
