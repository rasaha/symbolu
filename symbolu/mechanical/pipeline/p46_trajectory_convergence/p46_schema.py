"""
Phase 46: Trajectory Field Convergence Schema

Frozen dataclass for trajectory field convergence measurement.

Phase 46 answers:
    "Is the trajectory field converging, diverging, or unresolved over time?"

This is field convergence measurement - not prediction,
not decision-making, not trajectory selection.

Invariants:
    INV-P46-1: No trajectory ranking (individual futures are never compared)
    INV-P46-2: Temporal comparison only (uses only past vs current convergence)
    INV-P46-3: Deterministic math (no learning, no heuristics)
    INV-P46-4: Observer-only (cannot influence routing, gating, or decisions)
    INV-P46-5: Absence-safe (missing inputs -> no output)
"""

from dataclasses import dataclass, field
from typing import Any, Dict, Literal

# Version identifier for this phase
P46_VERSION = "1.0.0"

# Convergence trend classifications
ConvergenceTrend = Literal["increasing", "flat", "decreasing"]

# Field state classifications
FieldState = Literal["converging", "neutral", "diverging"]

# Thresholds for field state classification (based on convergence_score only)
CONVERGING_THRESHOLD = 0.70
NEUTRAL_THRESHOLD = 0.45

# Threshold for trend detection
TREND_DELTA_THRESHOLD = 0.05


@dataclass(frozen=True)
class TrajectoryFieldConvergenceReport:
    """
    Immutable convergence measurement for the trajectory field.

    This is an observer-only output that measures whether possible futures
    are structurally collapsing toward coherence or remaining fragmented,
    without ranking or selecting any trajectory.

    Invariants:
        - convergence_score in [0.0, 1.0]
        - convergence_trend in ("increasing", "flat", "decreasing")
        - field_state in ("converging", "neutral", "diverging")
        - sample_window >= 1
        - observer_only must be True (enforced)
    """

    # Core outputs (all required)
    convergence_score: float
    convergence_trend: ConvergenceTrend
    field_state: FieldState
    sample_window: int
    observer_only: Literal[True]

    # Metadata
    debug: Dict[str, Any] = field(default_factory=dict)
    version: str = P46_VERSION
    architectural_phase: str = "P46"

    def __post_init__(self) -> None:
        """Validate invariants on construction."""
        # INV-P46-4: observer_only must be True
        if self.observer_only is not True:
            raise ValueError("observer_only must be True (INV-P46-4)")

        # Clamp convergence_score to [0.0, 1.0]
        if not 0.0 <= self.convergence_score <= 1.0:
            clamped = max(0.0, min(1.0, self.convergence_score))
            object.__setattr__(self, "convergence_score", clamped)

        # Validate convergence_trend
        if self.convergence_trend not in ("increasing", "flat", "decreasing"):
            raise ValueError(
                f"Invalid convergence_trend: {self.convergence_trend}. "
                f"Must be one of ('increasing', 'flat', 'decreasing')"
            )

        # Validate field_state
        if self.field_state not in ("converging", "neutral", "diverging"):
            raise ValueError(
                f"Invalid field_state: {self.field_state}. "
                f"Must be one of ('converging', 'neutral', 'diverging')"
            )

        # Validate sample_window
        if self.sample_window < 1:
            raise ValueError(
                f"sample_window must be >= 1, got {self.sample_window}"
            )

        # Verify field_state matches convergence_score thresholds
        expected_state = _classify_field_state(self.convergence_score)
        if self.field_state != expected_state:
            raise ValueError(
                f"field_state '{self.field_state}' does not match "
                f"expected state '{expected_state}' for convergence_score "
                f"{self.convergence_score}"
            )

    def to_dict(self) -> Dict[str, Any]:
        """Serialize to dictionary for observability."""
        return {
            "convergence_score": self.convergence_score,
            "convergence_trend": self.convergence_trend,
            "field_state": self.field_state,
            "sample_window": self.sample_window,
            "observer_only": self.observer_only,
            "version": self.version,
            "architectural_phase": self.architectural_phase,
            "debug": dict(self.debug) if self.debug else {},
        }


def _classify_field_state(convergence_score: float) -> FieldState:
    """
    Classify field state based ONLY on convergence_score.

    INV-P46-1: Individual trajectories never affect the classification.

    Thresholds:
        - >= 0.70 -> "converging"
        - >= 0.45 -> "neutral"
        - < 0.45  -> "diverging"

    Args:
        convergence_score: The convergence score [0.0, 1.0]

    Returns:
        FieldState classification
    """
    if convergence_score >= CONVERGING_THRESHOLD:
        return "converging"
    elif convergence_score >= NEUTRAL_THRESHOLD:
        return "neutral"
    else:
        return "diverging"


def _classify_convergence_trend(delta: float) -> ConvergenceTrend:
    """
    Classify convergence trend based on temporal delta.

    INV-P46-2: Uses only past vs current convergence difference.

    Thresholds:
        - delta > +0.05 -> "increasing"
        - delta < -0.05 -> "decreasing"
        - otherwise -> "flat"

    Args:
        delta: Difference between current and previous convergence

    Returns:
        ConvergenceTrend classification
    """
    if delta > TREND_DELTA_THRESHOLD:
        return "increasing"
    elif delta < -TREND_DELTA_THRESHOLD:
        return "decreasing"
    else:
        return "flat"


def create_convergence_report(
    convergence_score: float,
    convergence_trend: ConvergenceTrend,
    sample_window: int,
    debug: Dict[str, Any] | None = None,
) -> TrajectoryFieldConvergenceReport:
    """
    Factory function to create TrajectoryFieldConvergenceReport safely.

    Always sets observer_only=True (enforced by design).
    Automatically derives field_state from convergence_score.

    INV-P46-1: No ranking - just measurement.
    INV-P46-4: Observer-only enforced.

    Args:
        convergence_score: Convergence score in [0.0, 1.0]
        convergence_trend: Trend classification
        sample_window: Number of snapshots used
        debug: Optional debug information

    Returns:
        TrajectoryFieldConvergenceReport
    """
    # Clamp convergence_score
    clamped_score = max(0.0, min(1.0, convergence_score))

    # Derive field_state from convergence_score only
    field_state = _classify_field_state(clamped_score)

    return TrajectoryFieldConvergenceReport(
        convergence_score=clamped_score,
        convergence_trend=convergence_trend,
        field_state=field_state,
        sample_window=sample_window,
        observer_only=True,
        debug=debug or {},
    )
