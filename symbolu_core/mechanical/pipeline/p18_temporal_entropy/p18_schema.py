"""
P18 - Temporal Entropy Differential Schema Definitions

P18 is an observation-only governance phase that computes temporal entropy
metrics to track pipeline state stability over time. It measures:
- entropy_now: Current instability level [0,1]
- entropy_prev: Previous turn's entropy [0,1] if available
- delta_entropy: Change in entropy [-1,+1]
- trend: INCREASING / DECREASING / STABLE / INSUFFICIENT_HISTORY
- volatility_band: LOW / MED / HIGH based on recent deltas

P18 does NOT:
- Modify upstream decisions
- Block pipeline execution
- Perform semantic interpretation
- Call LLMs
- Introduce probabilistic behavior
- Change routing, planner actions, regime, discourse, or lexical selection

Design Principles:
- Observation-Only: Reads upstream state, produces report, changes nothing
- Deterministic: No LLM calls, no probabilistic sampling
- Conservative: Uses neutral defaults for missing inputs
- Fixed Formula: Weighted blend of instability sources

Authority Model:
- P18 runs after P17 and after coherence computation
- P18 receives read-only signals from coherence and upstream phases
- P18 produces P18TemporalEntropyReport for downstream observability
- P18 report is advisory; it never gates or blocks
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional


# ============================================================================
# VERSION
# ============================================================================

P18_VERSION = "1.0.0"


# ============================================================================
# ENUMS - Trend and volatility classification
# ============================================================================


class EntropyTrend(str, Enum):
    """
    Classification of entropy trend based on delta.

    INCREASING: delta > epsilon, entropy is rising
    DECREASING: delta < -epsilon, entropy is falling
    STABLE: |delta| <= epsilon, entropy is stable
    INSUFFICIENT_HISTORY: No previous entropy available to compute delta
    """
    INCREASING = "INCREASING"
    DECREASING = "DECREASING"
    STABLE = "STABLE"
    INSUFFICIENT_HISTORY = "INSUFFICIENT_HISTORY"


class VolatilityBand(str, Enum):
    """
    Classification of entropy volatility based on recent deltas.

    LOW: Deltas are consistently small
    MED: Deltas show moderate variation
    HIGH: Deltas show high variation
    UNKNOWN: Insufficient data to classify volatility
    """
    LOW = "LOW"
    MED = "MED"
    HIGH = "HIGH"
    UNKNOWN = "UNKNOWN"


# ============================================================================
# DATACLASSES - Core envelope objects
# ============================================================================


@dataclass(frozen=True)
class P18TemporalEntropyReport:
    """
    P18 output envelope: Temporal entropy differential analysis report.

    This envelope is read-only and captures entropy metrics computed from
    upstream pipeline signals. It does NOT modify any upstream state or
    block pipeline execution directly.

    Invariants:
    - entropy_now must be in [0.0, 1.0]
    - entropy_prev must be in [0.0, 1.0] if present
    - delta_entropy must be in [-1.0, 1.0] if present
    - delta_entropy = entropy_now - entropy_prev when both present
    - trend must be INSUFFICIENT_HISTORY if entropy_prev is None

    Attributes:
        entropy_now: Current entropy level in [0.0, 1.0] (higher = more instability)
        entropy_prev: Previous turn's entropy in [0.0, 1.0], or None if no history
        delta_entropy: Change in entropy in [-1.0, 1.0], or None if no history
        trend: Trend classification based on delta
        volatility_band: Volatility classification based on recent deltas
        window_size_used: Number of historical deltas used for volatility computation
        debug: Additional debug/trace information
        version: Schema version for compatibility checking
        architectural_phase: Identifier for this phase ("P18")
    """
    entropy_now: float
    entropy_prev: Optional[float]
    delta_entropy: Optional[float]
    trend: EntropyTrend
    volatility_band: VolatilityBand
    window_size_used: int
    debug: Dict[str, Any] = field(default_factory=dict)
    version: str = P18_VERSION
    architectural_phase: str = "P18"

    def __post_init__(self) -> None:
        """Validate P18TemporalEntropyReport invariants."""
        # entropy_now must be in [0.0, 1.0]
        if not isinstance(self.entropy_now, (int, float)):
            raise ValueError(
                f"P18TemporalEntropyReport.entropy_now must be numeric, "
                f"got {type(self.entropy_now).__name__}"
            )
        if not 0.0 <= self.entropy_now <= 1.0:
            raise ValueError(
                f"P18TemporalEntropyReport.entropy_now must be in [0.0, 1.0], "
                f"got {self.entropy_now}"
            )

        # entropy_prev must be in [0.0, 1.0] if present
        if self.entropy_prev is not None:
            if not isinstance(self.entropy_prev, (int, float)):
                raise ValueError(
                    f"P18TemporalEntropyReport.entropy_prev must be numeric, "
                    f"got {type(self.entropy_prev).__name__}"
                )
            if not 0.0 <= self.entropy_prev <= 1.0:
                raise ValueError(
                    f"P18TemporalEntropyReport.entropy_prev must be in [0.0, 1.0], "
                    f"got {self.entropy_prev}"
                )

        # delta_entropy must be in [-1.0, 1.0] if present
        if self.delta_entropy is not None:
            if not isinstance(self.delta_entropy, (int, float)):
                raise ValueError(
                    f"P18TemporalEntropyReport.delta_entropy must be numeric, "
                    f"got {type(self.delta_entropy).__name__}"
                )
            if not -1.0 <= self.delta_entropy <= 1.0:
                raise ValueError(
                    f"P18TemporalEntropyReport.delta_entropy must be in [-1.0, 1.0], "
                    f"got {self.delta_entropy}"
                )

        # trend must be a valid EntropyTrend
        if self.trend is None:
            raise ValueError("P18TemporalEntropyReport.trend cannot be None")
        if not isinstance(self.trend, EntropyTrend):
            raise ValueError(
                f"P18TemporalEntropyReport.trend must be EntropyTrend, "
                f"got {type(self.trend).__name__}"
            )

        # volatility_band must be a valid VolatilityBand
        if self.volatility_band is None:
            raise ValueError("P18TemporalEntropyReport.volatility_band cannot be None")
        if not isinstance(self.volatility_band, VolatilityBand):
            raise ValueError(
                f"P18TemporalEntropyReport.volatility_band must be VolatilityBand, "
                f"got {type(self.volatility_band).__name__}"
            )

        # window_size_used must be non-negative
        if not isinstance(self.window_size_used, int):
            raise ValueError(
                f"P18TemporalEntropyReport.window_size_used must be int, "
                f"got {type(self.window_size_used).__name__}"
            )
        if self.window_size_used < 0:
            raise ValueError(
                f"P18TemporalEntropyReport.window_size_used must be non-negative, "
                f"got {self.window_size_used}"
            )

        # Consistency checks
        # If entropy_prev is None, trend must be INSUFFICIENT_HISTORY
        if self.entropy_prev is None and self.trend != EntropyTrend.INSUFFICIENT_HISTORY:
            raise ValueError(
                "P18TemporalEntropyReport.trend must be INSUFFICIENT_HISTORY "
                "when entropy_prev is None"
            )

        # If entropy_prev is None, delta_entropy must be None
        if self.entropy_prev is None and self.delta_entropy is not None:
            raise ValueError(
                "P18TemporalEntropyReport.delta_entropy must be None "
                "when entropy_prev is None"
            )

        # If both are present, delta_entropy must equal entropy_now - entropy_prev
        if self.entropy_prev is not None and self.delta_entropy is not None:
            expected_delta = self.entropy_now - self.entropy_prev
            if abs(self.delta_entropy - expected_delta) > 1e-9:
                raise ValueError(
                    f"P18TemporalEntropyReport.delta_entropy must equal "
                    f"entropy_now - entropy_prev, expected {expected_delta}, "
                    f"got {self.delta_entropy}"
                )

    def is_increasing(self) -> bool:
        """Check if entropy trend is INCREASING."""
        return self.trend == EntropyTrend.INCREASING

    def is_decreasing(self) -> bool:
        """Check if entropy trend is DECREASING."""
        return self.trend == EntropyTrend.DECREASING

    def is_stable(self) -> bool:
        """Check if entropy trend is STABLE."""
        return self.trend == EntropyTrend.STABLE

    def has_history(self) -> bool:
        """Check if historical entropy is available."""
        return self.trend != EntropyTrend.INSUFFICIENT_HISTORY

    def is_high_volatility(self) -> bool:
        """Check if volatility band is HIGH."""
        return self.volatility_band == VolatilityBand.HIGH

    def is_low_volatility(self) -> bool:
        """Check if volatility band is LOW."""
        return self.volatility_band == VolatilityBand.LOW

    def to_dict(self) -> Dict[str, Any]:
        """Serialize to dictionary for logging/tracing."""
        return {
            "entropy_now": self.entropy_now,
            "entropy_prev": self.entropy_prev,
            "delta_entropy": self.delta_entropy,
            "trend": self.trend.value,
            "volatility_band": self.volatility_band.value,
            "window_size_used": self.window_size_used,
            "debug": self.debug,
            "version": self.version,
            "architectural_phase": self.architectural_phase,
        }


# ============================================================================
# HELPER FUNCTIONS
# ============================================================================


def create_report(
    entropy_now: float,
    entropy_prev: Optional[float] = None,
    delta_entropy: Optional[float] = None,
    trend: EntropyTrend = EntropyTrend.INSUFFICIENT_HISTORY,
    volatility_band: VolatilityBand = VolatilityBand.UNKNOWN,
    window_size_used: int = 0,
    debug: Optional[Dict[str, Any]] = None,
) -> P18TemporalEntropyReport:
    """
    Helper to create a P18TemporalEntropyReport.

    Args:
        entropy_now: Current entropy level in [0.0, 1.0]
        entropy_prev: Previous turn's entropy, or None
        delta_entropy: Change in entropy, or None
        trend: Trend classification
        volatility_band: Volatility classification
        window_size_used: Number of historical deltas used
        debug: Optional debug/trace information

    Returns:
        A validated P18TemporalEntropyReport instance
    """
    return P18TemporalEntropyReport(
        entropy_now=entropy_now,
        entropy_prev=entropy_prev,
        delta_entropy=delta_entropy,
        trend=trend,
        volatility_band=volatility_band,
        window_size_used=window_size_used,
        debug=debug or {},
    )


# Public exports
__all__ = [
    # Version
    "P18_VERSION",
    # Enums
    "EntropyTrend",
    "VolatilityBand",
    # Dataclasses
    "P18TemporalEntropyReport",
    # Helpers
    "create_report",
]
