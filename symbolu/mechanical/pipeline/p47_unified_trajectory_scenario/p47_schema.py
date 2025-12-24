"""
Phase 47: Unified Trajectory-Scenario Synthesis Schema

Frozen dataclass for unified trajectory-scenario synthesis output.

Phase 47 answers:
    "Do the scenario space (what-if worlds) and the trajectory field
    (future paths) agree structurally, or are they drifting apart?"

This is structural synthesis, not prediction and not action.
First and only place where scenario space and trajectory space are
synthesized into a single observational construct.

Invariants:
    INV-P47-1: No prediction (no future selection or ranking)
    INV-P47-2: Symmetric synthesis (scenario and trajectory treated as peers)
    INV-P47-3: Deterministic math only (pure weighted aggregation)
    INV-P47-4: Observer-only (cannot influence any authority phase)
    INV-P47-5: Absence-safe (missing inputs -> no output)
"""

from dataclasses import dataclass, field
from typing import Any, Dict, Literal

# Version identifier for this phase
P47_VERSION = "1.0.0"

# Alignment band classifications
AlignmentBand = Literal["aligned", "strained", "misaligned"]

# Dominant factor classifications
DominantFactor = Literal["trajectory", "scenario", "balanced"]

# Thresholds for alignment band classification
ALIGNED_THRESHOLD = 0.70
STRAINED_THRESHOLD = 0.45

# Threshold for dominant factor detection
DOMINANCE_THRESHOLD = 0.10


@dataclass(frozen=True)
class UnifiedTrajectoryScenarioReport:
    """
    Immutable synthesis report combining trajectory and scenario spaces.

    This is an observer-only output that measures structural alignment
    between scenario coherence and trajectory stability without
    predicting, selecting, or ranking futures.

    Invariants:
        - alignment_score in [0.0, 1.0]
        - alignment_band derived from alignment_score
        - dominant_factor derived from symmetric comparison
        - observer_only must be True (enforced)
    """

    # Core outputs (all required)
    alignment_score: float
    alignment_band: AlignmentBand
    dominant_factor: DominantFactor
    observer_only: Literal[True]

    # Metadata
    debug: Dict[str, Any] = field(default_factory=dict)
    version: str = P47_VERSION
    architectural_phase: str = "P47"

    def __post_init__(self) -> None:
        """Validate invariants on construction."""
        # INV-P47-4: observer_only must be True
        if self.observer_only is not True:
            raise ValueError("observer_only must be True (INV-P47-4)")

        # Clamp alignment_score to [0.0, 1.0]
        if not 0.0 <= self.alignment_score <= 1.0:
            clamped = max(0.0, min(1.0, self.alignment_score))
            object.__setattr__(self, "alignment_score", clamped)

        # Validate alignment_band
        if self.alignment_band not in ("aligned", "strained", "misaligned"):
            raise ValueError(
                f"Invalid alignment_band: {self.alignment_band}. "
                f"Must be one of ('aligned', 'strained', 'misaligned')"
            )

        # Validate dominant_factor
        if self.dominant_factor not in ("trajectory", "scenario", "balanced"):
            raise ValueError(
                f"Invalid dominant_factor: {self.dominant_factor}. "
                f"Must be one of ('trajectory', 'scenario', 'balanced')"
            )

        # Verify alignment_band matches alignment_score
        expected_band = _classify_alignment_band(self.alignment_score)
        if self.alignment_band != expected_band:
            raise ValueError(
                f"alignment_band '{self.alignment_band}' does not match "
                f"expected band '{expected_band}' for alignment_score "
                f"{self.alignment_score}"
            )

    def to_dict(self) -> Dict[str, Any]:
        """Serialize to dictionary for observability."""
        return {
            "alignment_score": self.alignment_score,
            "alignment_band": self.alignment_band,
            "dominant_factor": self.dominant_factor,
            "observer_only": self.observer_only,
            "version": self.version,
            "architectural_phase": self.architectural_phase,
            "debug": dict(self.debug) if self.debug else {},
        }


def _classify_alignment_band(alignment_score: float) -> AlignmentBand:
    """
    Classify alignment band based on alignment_score.

    Thresholds:
        - >= 0.70 -> "aligned"
        - >= 0.45 -> "strained"
        - < 0.45  -> "misaligned"

    Args:
        alignment_score: The alignment score [0.0, 1.0]

    Returns:
        AlignmentBand classification
    """
    if alignment_score >= ALIGNED_THRESHOLD:
        return "aligned"
    elif alignment_score >= STRAINED_THRESHOLD:
        return "strained"
    else:
        return "misaligned"


def _classify_dominant_factor(
    trajectory_value: float,
    scenario_value: float,
) -> DominantFactor:
    """
    Classify dominant factor based on symmetric comparison.

    INV-P47-2: Scenario and trajectory treated as peers.

    Decision rule:
        - If T > S + 0.10 -> "trajectory"
        - If S > T + 0.10 -> "scenario"
        - Otherwise -> "balanced"

    Args:
        trajectory_value: Trajectory stability index
        scenario_value: Scenario coherence score

    Returns:
        DominantFactor classification
    """
    if trajectory_value > scenario_value + DOMINANCE_THRESHOLD:
        return "trajectory"
    elif scenario_value > trajectory_value + DOMINANCE_THRESHOLD:
        return "scenario"
    else:
        return "balanced"


def create_unified_trajectory_scenario_report(
    alignment_score: float,
    dominant_factor: DominantFactor,
    debug: Dict[str, Any] | None = None,
) -> UnifiedTrajectoryScenarioReport:
    """
    Factory function to create UnifiedTrajectoryScenarioReport safely.

    Always sets observer_only=True (enforced by design).
    Automatically derives alignment_band from alignment_score.

    INV-P47-1: No prediction - just measurement.
    INV-P47-2: Symmetric synthesis.
    INV-P47-3: Deterministic math only.

    Args:
        alignment_score: Alignment score in [0.0, 1.0]
        dominant_factor: Which factor dominates
        debug: Optional debug information

    Returns:
        UnifiedTrajectoryScenarioReport
    """
    # Clamp alignment score
    clamped_score = max(0.0, min(1.0, alignment_score))

    # Derive alignment band from alignment_score
    alignment_band = _classify_alignment_band(clamped_score)

    return UnifiedTrajectoryScenarioReport(
        alignment_score=clamped_score,
        alignment_band=alignment_band,
        dominant_factor=dominant_factor,
        observer_only=True,
        debug=debug or {},
    )
