"""
Phase 49: Temporal Stability Index Schema

Frozen dataclass for temporal stability index output.

Phase 49 answers:
    "How stable is this system over time, as a single interpretable index?"

This is the final observer-only stability signal before governance begins.

No action.
No gating.
No decision authority.

Invariants:
    INV-P49-1: Observer-only (no downstream influence)
    INV-P49-2: Deterministic (pure math, no state)
    INV-P49-3: No authority (cannot gate, block, or trigger)
    INV-P49-4: Absence-safe (missing inputs -> None)
    INV-P49-5: Temporal meaning only (index reflects time stability, not intent or emotion)
"""

from dataclasses import dataclass, field
from typing import Any, Dict, Literal

# Version identifier for this phase
P49_VERSION = "1.0.0"

# Stability band classifications
StabilityBand = Literal["stable", "strained", "unstable"]

# Valid stability bands (for validation)
VALID_STABILITY_BANDS = frozenset({"stable", "strained", "unstable"})

# Thresholds for stability band classification
STABLE_THRESHOLD = 0.70
STRAINED_THRESHOLD = 0.45

# Formula weights (must sum to 1.0)
W_FORECAST = 0.25       # P38 forecast_score weight
W_HORIZON = 0.20        # P40 alignment_score weight
W_TRAJECTORY = 0.20     # P45 stability_index weight
W_CONVERGENCE = 0.20    # P46 convergence_score weight
W_ALIGNMENT = 0.15      # P47 alignment_score weight


@dataclass(frozen=True)
class TemporalStabilityIndex:
    """
    Immutable temporal stability index report.

    This is an observer-only output that synthesizes temporal stability
    signals into a single interpretable index without influencing
    any downstream behavior, governance, or decisions.

    Invariants:
        - temporal_stability_index in [0.0, 1.0]
        - stability_band in VALID_STABILITY_BANDS
        - observer_only must be True (enforced)
    """

    # Core outputs (all required)
    temporal_stability_index: float
    stability_band: StabilityBand
    observer_only: Literal[True]

    # Metadata
    debug: Dict[str, Any] = field(default_factory=dict)
    version: str = P49_VERSION
    architectural_phase: str = "P49"

    def __post_init__(self) -> None:
        """Validate invariants on construction."""
        # INV-P49-1: observer_only must be True
        if self.observer_only is not True:
            raise ValueError("observer_only must be True (INV-P49-1)")

        # Validate stability_band
        if self.stability_band not in VALID_STABILITY_BANDS:
            raise ValueError(
                f"Invalid stability_band: {self.stability_band}. "
                f"Must be one of {sorted(VALID_STABILITY_BANDS)}"
            )

        # Clamp temporal_stability_index to [0.0, 1.0]
        if not 0.0 <= self.temporal_stability_index <= 1.0:
            clamped = max(0.0, min(1.0, self.temporal_stability_index))
            object.__setattr__(self, "temporal_stability_index", clamped)

        # Verify stability_band matches temporal_stability_index thresholds
        expected_band = _classify_stability_band(self.temporal_stability_index)
        if self.stability_band != expected_band:
            raise ValueError(
                f"stability_band '{self.stability_band}' does not match "
                f"expected band '{expected_band}' for temporal_stability_index "
                f"{self.temporal_stability_index}"
            )

    def to_dict(self) -> Dict[str, Any]:
        """Serialize to dictionary for observability."""
        return {
            "temporal_stability_index": self.temporal_stability_index,
            "stability_band": self.stability_band,
            "observer_only": self.observer_only,
            "version": self.version,
            "architectural_phase": self.architectural_phase,
            "debug": dict(self.debug) if self.debug else {},
        }


def _classify_stability_band(temporal_stability_index: float) -> StabilityBand:
    """
    Classify stability band based on temporal_stability_index.

    Thresholds:
        - >= 0.70 -> "stable"
        - >= 0.45 -> "strained"
        - < 0.45  -> "unstable"

    Args:
        temporal_stability_index: The index value [0.0, 1.0]

    Returns:
        StabilityBand classification
    """
    if temporal_stability_index >= STABLE_THRESHOLD:
        return "stable"
    elif temporal_stability_index >= STRAINED_THRESHOLD:
        return "strained"
    else:
        return "unstable"


def create_temporal_stability_index(
    temporal_stability_index: float,
    debug: Dict[str, Any] | None = None,
) -> TemporalStabilityIndex:
    """
    Factory function to create TemporalStabilityIndex safely.

    Always sets observer_only=True (enforced by design).
    Automatically derives stability_band from temporal_stability_index.

    INV-P49-1: Observer-only enforced.
    INV-P49-2: Deterministic math only.

    Args:
        temporal_stability_index: Index value in [0.0, 1.0]
        debug: Optional debug information

    Returns:
        TemporalStabilityIndex
    """
    # Clamp temporal_stability_index
    clamped_index = max(0.0, min(1.0, temporal_stability_index))

    # Derive stability band from index
    stability_band = _classify_stability_band(clamped_index)

    return TemporalStabilityIndex(
        temporal_stability_index=clamped_index,
        stability_band=stability_band,
        observer_only=True,
        debug=debug or {},
    )


# Public exports
__all__ = [
    # Version
    "P49_VERSION",
    # Type Aliases
    "StabilityBand",
    # Constants
    "VALID_STABILITY_BANDS",
    "STABLE_THRESHOLD",
    "STRAINED_THRESHOLD",
    "W_FORECAST",
    "W_HORIZON",
    "W_TRAJECTORY",
    "W_CONVERGENCE",
    "W_ALIGNMENT",
    # Helpers
    "_classify_stability_band",
    # Dataclasses
    "TemporalStabilityIndex",
    # Factory
    "create_temporal_stability_index",
]
