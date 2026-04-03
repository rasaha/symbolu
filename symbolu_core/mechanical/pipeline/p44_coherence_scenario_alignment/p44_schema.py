"""
Phase 44: Coherence-Scenario Alignment Engine Schema

Frozen dataclass for coherence-scenario alignment measurement output.

Phase 44 answers:
    "How well do the possible scenario trajectories align with the
    system's current coherence state?"

This is alignment measurement only - not forecasting, not choice, not gating.

Invariants:
    INV-P44-1: Measurement only (no ranking, no preference, no selection)
    INV-P44-2: Deterministic math only (no randomness, no learned parameters)
    INV-P44-3: Variant isolation (variants do not influence base alignment)
    INV-P44-4: No authority influence (output never affects regime, discourse, policy)
    INV-P44-5: Absence-safe (missing inputs -> no output)
"""

from dataclasses import dataclass, field
from typing import Any, Dict, Literal

# Version identifier for this phase
P44_VERSION = "1.0.0"

# Alignment band classifications
AlignmentBand = Literal["aligned", "strained", "misaligned"]

# Thresholds for alignment band classification (based on base_alignment_score only)
ALIGNED_THRESHOLD = 0.70
STRAINED_THRESHOLD = 0.45

# Weights for base alignment score computation
COHERENCE_QUALITY_WEIGHT = 0.60
FUSION_CONFIDENCE_WEIGHT = 0.40


@dataclass(frozen=True)
class CoherenceScenarioAlignmentReport:
    """
    Immutable alignment measurement between coherence state and scenario futures.

    This is an observer-only output that measures how well future scenario
    trajectories align with the current coherence state.

    Invariants:
        - base_alignment_score in [0.0, 1.0]
        - variant_alignment values in [0.0, 1.0]
        - alignment_band derived ONLY from base_alignment_score (INV-P44-3)
        - observer_only must be True (enforced)
    """

    # Core outputs (all required)
    base_alignment_score: float
    variant_alignment: Dict[str, float]
    alignment_band: AlignmentBand
    observer_only: Literal[True]

    # Metadata
    debug: Dict[str, Any] = field(default_factory=dict)
    version: str = P44_VERSION
    architectural_phase: str = "P44"

    def __post_init__(self) -> None:
        """Validate invariants on construction."""
        # INV-P44-4: observer_only must be True
        if self.observer_only is not True:
            raise ValueError("observer_only must be True (INV-P44-4)")

        # Clamp base_alignment_score to [0.0, 1.0]
        if not 0.0 <= self.base_alignment_score <= 1.0:
            clamped = max(0.0, min(1.0, self.base_alignment_score))
            object.__setattr__(self, "base_alignment_score", clamped)

        # Validate variant_alignment values
        if self.variant_alignment:
            clamped_variants = {}
            for variant_id, score in self.variant_alignment.items():
                if not isinstance(variant_id, str):
                    raise ValueError(
                        f"variant_alignment keys must be strings, got {type(variant_id)}"
                    )
                # Clamp variant scores to [0.0, 1.0]
                clamped_variants[variant_id] = max(0.0, min(1.0, score))

            if clamped_variants != self.variant_alignment:
                object.__setattr__(self, "variant_alignment", clamped_variants)

        # Validate alignment_band
        if self.alignment_band not in ("aligned", "strained", "misaligned"):
            raise ValueError(
                f"Invalid alignment_band: {self.alignment_band}. "
                f"Must be one of ('aligned', 'strained', 'misaligned')"
            )

        # INV-P44-3: Verify alignment_band matches base_alignment_score
        # (variants must not influence band classification)
        expected_band = _classify_alignment_band(self.base_alignment_score)
        if self.alignment_band != expected_band:
            raise ValueError(
                f"alignment_band '{self.alignment_band}' does not match "
                f"expected band '{expected_band}' for base_alignment_score "
                f"{self.base_alignment_score} (INV-P44-3)"
            )

    def to_dict(self) -> Dict[str, Any]:
        """Serialize to dictionary for observability."""
        return {
            "base_alignment_score": self.base_alignment_score,
            "variant_alignment": dict(self.variant_alignment),
            "alignment_band": self.alignment_band,
            "observer_only": self.observer_only,
            "version": self.version,
            "architectural_phase": self.architectural_phase,
            "debug": dict(self.debug) if self.debug else {},
        }


def _classify_alignment_band(base_alignment_score: float) -> AlignmentBand:
    """
    Classify alignment band based ONLY on base_alignment_score.

    INV-P44-3: Variants never affect the band.

    Thresholds:
        - >= 0.70 -> "aligned"
        - >= 0.45 -> "strained"
        - < 0.45  -> "misaligned"

    Args:
        base_alignment_score: The base alignment score [0.0, 1.0]

    Returns:
        AlignmentBand classification
    """
    if base_alignment_score >= ALIGNED_THRESHOLD:
        return "aligned"
    elif base_alignment_score >= STRAINED_THRESHOLD:
        return "strained"
    else:
        return "misaligned"


def create_alignment_report(
    base_alignment_score: float,
    variant_alignment: Dict[str, float],
    debug: Dict[str, Any] | None = None,
) -> CoherenceScenarioAlignmentReport:
    """
    Factory function to create CoherenceScenarioAlignmentReport safely.

    Always sets observer_only=True (enforced by design).
    Automatically derives alignment_band from base_alignment_score.

    INV-P44-1: No ranking or preference - just measurement.
    INV-P44-3: Band derived only from base score.

    Args:
        base_alignment_score: Score in [0.0, 1.0]
        variant_alignment: Mapping of variant_id -> alignment_score
        debug: Optional debug information

    Returns:
        CoherenceScenarioAlignmentReport
    """
    # Clamp base score
    clamped_base = max(0.0, min(1.0, base_alignment_score))

    # Derive alignment band from base score only (INV-P44-3)
    alignment_band = _classify_alignment_band(clamped_base)

    return CoherenceScenarioAlignmentReport(
        base_alignment_score=clamped_base,
        variant_alignment=variant_alignment,
        alignment_band=alignment_band,
        observer_only=True,
        debug=debug or {},
    )
