"""
Phase 45: Multi-Trajectory Stability Field Schema

Frozen dataclass for multi-trajectory stability field output.

Phase 45 answers:
    "Across all possible trajectories, how stable is the future space as a whole?"

This is field-level structural analysis - not decision-making,
not trajectory selection, not outcome prediction.

Invariants:
    INV-P45-1: No trajectory preference (no ranking, sorting, or selection)
    INV-P45-2: Deterministic aggregation only (pure math, no heuristics, no learning)
    INV-P45-3: Field-level semantics only (individual variants do not influence bands)
    INV-P45-4: Observer-only (output never influences routing or governance)
    INV-P45-5: Absence-safe (missing inputs -> no output)
"""

from dataclasses import dataclass, field
from typing import Any, Dict, Literal

# Version identifier for this phase
P45_VERSION = "1.0.0"

# Stability band classifications
StabilityBand = Literal["stable", "strained", "chaotic"]

# Thresholds for stability band classification (based on stability_index only)
STABLE_THRESHOLD = 0.70
STRAINED_THRESHOLD = 0.45


@dataclass(frozen=True)
class MultiTrajectoryStabilityField:
    """
    Immutable stability field measurement across multiple trajectories.

    This is an observer-only output that measures the structural stability
    of the future space without preferring or selecting any trajectory.

    Invariants:
        - stability_index in [0.0, 1.0]
        - volatility_index in [0.0, 1.0]
        - convergence_index in [0.0, 1.0]
        - trajectory_count >= 1
        - stability_band derived ONLY from stability_index (INV-P45-3)
        - observer_only must be True (enforced)
    """

    # Core outputs (all required)
    stability_index: float
    volatility_index: float
    convergence_index: float
    trajectory_count: int
    stability_band: StabilityBand
    observer_only: Literal[True]

    # Metadata
    debug: Dict[str, Any] = field(default_factory=dict)
    version: str = P45_VERSION
    architectural_phase: str = "P45"

    def __post_init__(self) -> None:
        """Validate invariants on construction."""
        # INV-P45-4: observer_only must be True
        if self.observer_only is not True:
            raise ValueError("observer_only must be True (INV-P45-4)")

        # Clamp stability_index to [0.0, 1.0]
        if not 0.0 <= self.stability_index <= 1.0:
            clamped = max(0.0, min(1.0, self.stability_index))
            object.__setattr__(self, "stability_index", clamped)

        # Clamp volatility_index to [0.0, 1.0]
        if not 0.0 <= self.volatility_index <= 1.0:
            clamped = max(0.0, min(1.0, self.volatility_index))
            object.__setattr__(self, "volatility_index", clamped)

        # Clamp convergence_index to [0.0, 1.0]
        if not 0.0 <= self.convergence_index <= 1.0:
            clamped = max(0.0, min(1.0, self.convergence_index))
            object.__setattr__(self, "convergence_index", clamped)

        # Validate trajectory_count
        if self.trajectory_count < 1:
            raise ValueError(
                f"trajectory_count must be >= 1, got {self.trajectory_count}"
            )

        # Validate stability_band
        if self.stability_band not in ("stable", "strained", "chaotic"):
            raise ValueError(
                f"Invalid stability_band: {self.stability_band}. "
                f"Must be one of ('stable', 'strained', 'chaotic')"
            )

        # INV-P45-3: Verify stability_band matches stability_index
        # (individual variants must not influence band classification)
        expected_band = _classify_stability_band(self.stability_index)
        if self.stability_band != expected_band:
            raise ValueError(
                f"stability_band '{self.stability_band}' does not match "
                f"expected band '{expected_band}' for stability_index "
                f"{self.stability_index} (INV-P45-3)"
            )

    def to_dict(self) -> Dict[str, Any]:
        """Serialize to dictionary for observability."""
        return {
            "stability_index": self.stability_index,
            "volatility_index": self.volatility_index,
            "convergence_index": self.convergence_index,
            "trajectory_count": self.trajectory_count,
            "stability_band": self.stability_band,
            "observer_only": self.observer_only,
            "version": self.version,
            "architectural_phase": self.architectural_phase,
            "debug": dict(self.debug) if self.debug else {},
        }


def _classify_stability_band(stability_index: float) -> StabilityBand:
    """
    Classify stability band based ONLY on stability_index.

    INV-P45-3: Individual variants never affect the band.

    Thresholds:
        - >= 0.70 -> "stable"
        - >= 0.45 -> "strained"
        - < 0.45  -> "chaotic"

    Args:
        stability_index: The stability index [0.0, 1.0]

    Returns:
        StabilityBand classification
    """
    if stability_index >= STABLE_THRESHOLD:
        return "stable"
    elif stability_index >= STRAINED_THRESHOLD:
        return "strained"
    else:
        return "chaotic"


def create_stability_field(
    stability_index: float,
    volatility_index: float,
    convergence_index: float,
    trajectory_count: int,
    debug: Dict[str, Any] | None = None,
) -> MultiTrajectoryStabilityField:
    """
    Factory function to create MultiTrajectoryStabilityField safely.

    Always sets observer_only=True (enforced by design).
    Automatically derives stability_band from stability_index.

    INV-P45-1: No ranking or preference - just measurement.
    INV-P45-3: Band derived only from stability_index.

    Args:
        stability_index: Stability score in [0.0, 1.0]
        volatility_index: Volatility score in [0.0, 1.0]
        convergence_index: Convergence score in [0.0, 1.0]
        trajectory_count: Number of trajectories analyzed
        debug: Optional debug information

    Returns:
        MultiTrajectoryStabilityField
    """
    # Clamp indices
    clamped_stability = max(0.0, min(1.0, stability_index))
    clamped_volatility = max(0.0, min(1.0, volatility_index))
    clamped_convergence = max(0.0, min(1.0, convergence_index))

    # Derive stability band from stability_index only (INV-P45-3)
    stability_band = _classify_stability_band(clamped_stability)

    return MultiTrajectoryStabilityField(
        stability_index=clamped_stability,
        volatility_index=clamped_volatility,
        convergence_index=clamped_convergence,
        trajectory_count=trajectory_count,
        stability_band=stability_band,
        observer_only=True,
        debug=debug or {},
    )
