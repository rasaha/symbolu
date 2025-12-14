"""
Phase 50: Cognitive Consistency Regression Schema

Frozen dataclass for cognitive consistency regression output.

Phase 50 answers:
    "Is the system contradicting itself compared to its own prior cognitive state?"

This is the first phase in the final governance band, but it is still non-actuating.
P50 is self-reflection without self-control.

It witnesses contradiction, but never corrects it.

No action.
No gating.
No decision authority.
No delivery modulation.
No advice.
No warnings to user.

INPUTS (Read-Only):
    Phase 50 MAY read:
        - P6 RegimeEnvelope
        - P7 DiscourseEnvelope
        - P8 SemanticFrame
        - P9 LexicalFrame
        - P10-P14 (for trace continuity only, not evaluation)
        - P16 Regression Guard history
        - P18 Temporal Entropy Differential
        - P19 Drift Fusion Report
        - P20 Unified Cognitive Snapshot
        - Historical snapshots (previous turns)

    Phase 50 MUST NOT read:
        - Raw user text
        - Acoustic content
        - Ontology interpretation
        - Any future forecast (P38+)
        - Any observer-only acoustic reports (P22-P24)

Invariants:
    INV-P50-A1: P50 cannot modify any upstream phase output
    INV-P50-A2: P50 cannot gate any action or delivery
    INV-P50-A3: P50 cannot be read by P6-P21
    INV-P50-A4: P50 output is observer-only
    INV-P50-D1: Same history + same input -> same report (bitwise)
    INV-P50-D2: No randomness, no thresholds learned at runtime
    INV-P50-S1: No semantic reinterpretation
    INV-P50-S2: No acoustic interpretation
    INV-P50-S3: No persona influence
"""

from dataclasses import dataclass, field
from typing import Any, Dict, Literal, Tuple

# Version identifier for this phase
P50_VERSION = "1.0.0"

# Consistency band classifications
ConsistencyBand = Literal["stable", "strained", "inconsistent"]

# Valid consistency bands (for validation)
VALID_CONSISTENCY_BANDS = frozenset({"stable", "strained", "inconsistent"})

# Thresholds for consistency band classification
STABLE_THRESHOLD = 0.70
STRAINED_THRESHOLD = 0.45

# Formula weights (must sum to 1.0)
W_REGIME_STABILITY = 0.25       # Regime stability across turns
W_DISCOURSE_CONTINUITY = 0.20   # Discourse act continuity
W_SEMANTIC_PRESERVATION = 0.20  # Semantic slot preservation
W_LEXICAL_POLARITY = 0.15       # Lexical polarity reversals
W_DRIFT_ENTROPY = 0.20          # Drift vs entropy disagreement


@dataclass(frozen=True)
class CognitiveConsistencyReport:
    """
    Immutable cognitive consistency regression report.

    This is an observer-only output that evaluates whether cognition
    has remained internally consistent over time without influencing
    any downstream behavior, governance, or decisions.

    It witnesses contradiction, but never corrects it.

    Invariants:
        - consistency_score in [0.0, 1.0]
        - consistency_band in VALID_CONSISTENCY_BANDS
        - observer_only must be True (enforced)
    """

    # Core outputs (all required)
    consistency_score: float
    consistency_band: ConsistencyBand
    detected_contradictions: Tuple[str, ...]
    regression_flags: Tuple[str, ...]
    observer_only: Literal[True]

    # Metadata
    debug: Dict[str, Any] = field(default_factory=dict)
    version: str = P50_VERSION
    architectural_phase: str = "P50"

    def __post_init__(self) -> None:
        """Validate invariants on construction."""
        # INV-P50-A4: observer_only must be True
        if self.observer_only is not True:
            raise ValueError("observer_only must be True (INV-P50-A4)")

        # Validate consistency_band
        if self.consistency_band not in VALID_CONSISTENCY_BANDS:
            raise ValueError(
                f"Invalid consistency_band: {self.consistency_band}. "
                f"Must be one of {sorted(VALID_CONSISTENCY_BANDS)}"
            )

        # Clamp consistency_score to [0.0, 1.0]
        if not 0.0 <= self.consistency_score <= 1.0:
            clamped = max(0.0, min(1.0, self.consistency_score))
            object.__setattr__(self, "consistency_score", clamped)

        # Verify consistency_band matches consistency_score thresholds
        expected_band = _classify_consistency_band(self.consistency_score)
        if self.consistency_band != expected_band:
            raise ValueError(
                f"consistency_band '{self.consistency_band}' does not match "
                f"expected band '{expected_band}' for consistency_score "
                f"{self.consistency_score}"
            )

        # Ensure detected_contradictions is tuple
        if not isinstance(self.detected_contradictions, tuple):
            object.__setattr__(
                self, "detected_contradictions",
                tuple(self.detected_contradictions)
            )

        # Ensure regression_flags is tuple
        if not isinstance(self.regression_flags, tuple):
            object.__setattr__(
                self, "regression_flags",
                tuple(self.regression_flags)
            )

    def to_dict(self) -> Dict[str, Any]:
        """Serialize to dictionary for observability."""
        return {
            "consistency_score": self.consistency_score,
            "consistency_band": self.consistency_band,
            "detected_contradictions": list(self.detected_contradictions),
            "regression_flags": list(self.regression_flags),
            "observer_only": self.observer_only,
            "version": self.version,
            "architectural_phase": self.architectural_phase,
            "debug": dict(self.debug) if self.debug else {},
        }

    def has_contradictions(self) -> bool:
        """Check if any contradictions were detected."""
        return len(self.detected_contradictions) > 0

    def has_regression_flags(self) -> bool:
        """Check if any regression flags were raised."""
        return len(self.regression_flags) > 0

    def contradiction_count(self) -> int:
        """Return the number of detected contradictions."""
        return len(self.detected_contradictions)

    def flag_count(self) -> int:
        """Return the number of regression flags."""
        return len(self.regression_flags)

    def is_stable(self) -> bool:
        """Check if consistency band is stable."""
        return self.consistency_band == "stable"

    def is_strained(self) -> bool:
        """Check if consistency band is strained."""
        return self.consistency_band == "strained"

    def is_inconsistent(self) -> bool:
        """Check if consistency band is inconsistent."""
        return self.consistency_band == "inconsistent"


def _classify_consistency_band(consistency_score: float) -> ConsistencyBand:
    """
    Classify consistency band based on consistency_score.

    Thresholds:
        - >= 0.70 -> "stable"
        - >= 0.45 -> "strained"
        - < 0.45  -> "inconsistent"

    Args:
        consistency_score: The score value [0.0, 1.0]

    Returns:
        ConsistencyBand classification
    """
    if consistency_score >= STABLE_THRESHOLD:
        return "stable"
    elif consistency_score >= STRAINED_THRESHOLD:
        return "strained"
    else:
        return "inconsistent"


def create_cognitive_consistency_report(
    consistency_score: float,
    detected_contradictions: Tuple[str, ...] = (),
    regression_flags: Tuple[str, ...] = (),
    debug: Dict[str, Any] | None = None,
) -> CognitiveConsistencyReport:
    """
    Factory function to create CognitiveConsistencyReport safely.

    Always sets observer_only=True (enforced by design).
    Automatically derives consistency_band from consistency_score.

    INV-P50-A4: Observer-only enforced.
    INV-P50-D1: Deterministic math only.

    Args:
        consistency_score: Score value in [0.0, 1.0]
        detected_contradictions: Tuple of contradiction descriptions
        regression_flags: Tuple of regression flag strings
        debug: Optional debug information

    Returns:
        CognitiveConsistencyReport
    """
    # Clamp consistency_score
    clamped_score = max(0.0, min(1.0, consistency_score))

    # Derive consistency band from score
    consistency_band = _classify_consistency_band(clamped_score)

    return CognitiveConsistencyReport(
        consistency_score=clamped_score,
        consistency_band=consistency_band,
        detected_contradictions=tuple(detected_contradictions),
        regression_flags=tuple(regression_flags),
        observer_only=True,
        debug=debug or {},
    )


# Public exports
__all__ = [
    # Version
    "P50_VERSION",
    # Type Aliases
    "ConsistencyBand",
    # Constants
    "VALID_CONSISTENCY_BANDS",
    "STABLE_THRESHOLD",
    "STRAINED_THRESHOLD",
    "W_REGIME_STABILITY",
    "W_DISCOURSE_CONTINUITY",
    "W_SEMANTIC_PRESERVATION",
    "W_LEXICAL_POLARITY",
    "W_DRIFT_ENTROPY",
    # Helpers
    "_classify_consistency_band",
    # Dataclasses
    "CognitiveConsistencyReport",
    # Factory
    "create_cognitive_consistency_report",
]
