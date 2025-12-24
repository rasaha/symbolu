"""
Acoustic Alignment Report Schema

This module defines the AcousticAlignmentReport dataclass used for optional
acoustic alignment diagnostics in Phase 10 Coherence v3 Fusion.

IMPORTANT ARCHITECTURAL CONSTRAINTS:
- This is an OBSERVER-ONLY input
- NEVER influences regime (P6)
- NEVER influences discourse (P7)
- NEVER influences semantic slots (P8)
- NEVER influences lexical selection (P9)
- NEVER influences DHA, Persona, or Renderer decisions
- Used ONLY for diagnostic annotation and confidence reduction

The acoustic alignment report is produced by observer-only phases (P22, P23, P24)
and provides read-only signals about acoustic-semantic alignment. When present,
it may ONLY be used to:
1. Annotate diagnostics
2. Slightly down-weight confidence/quality bounds (never increase)
3. Add internal diagnostic flags

CRITICAL INVARIANT:
    Sound must obey meaning.
    Meaning must never obey sound.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal, Tuple


# Type alias for pressure band
PressureBand = Literal["low", "moderate", "high"]


@dataclass(frozen=True)
class AcousticAlignmentReport:
    """
    Read-only acoustic alignment report from observer phases.

    This dataclass captures acoustic alignment observations from P22/P23/P24
    for optional use in Phase 10 coherence v3 quality computation.

    IMPORTANT CONSTRAINTS:
    - This input is OPTIONAL. When None, Phase 10 MUST behave identically.
    - This input is READ-ONLY. It cannot influence authoritative decisions.
    - This input can ONLY REDUCE confidence, NEVER increase it.
    - This input is DIAGNOSTIC-ONLY. It annotates but does not control.

    Attributes:
        alignment_score: Alignment between acoustic motion and semantic intent.
                        Range: [0.0, 1.0] where 1.0 = fully aligned.
        pressure_band: Coarse acoustic pressure classification.
                      One of: "low", "moderate", "high"
        mismatch_tags: Descriptive tags for any misalignment observed.
                      Tuple of strings (immutable).

    Invariants:
        - alignment_score is clamped to [0.0, 1.0]
        - pressure_band is one of the allowed literals
        - mismatch_tags is a tuple (not list) for immutability
        - Frozen dataclass ensures immutability

    Example:
        report = AcousticAlignmentReport(
            alignment_score=0.35,
            pressure_band="high",
            mismatch_tags=("inner_outer_tension", "high_pressure_low_authority"),
        )
    """

    alignment_score: float
    pressure_band: PressureBand
    mismatch_tags: Tuple[str, ...]

    def __post_init__(self) -> None:
        """Validate AcousticAlignmentReport invariants."""
        # Validate alignment_score type
        if not isinstance(self.alignment_score, (int, float)):
            raise ValueError(
                f"AcousticAlignmentReport.alignment_score must be numeric, "
                f"got {type(self.alignment_score).__name__}"
            )

        # Validate alignment_score range
        if not (0.0 <= self.alignment_score <= 1.0):
            raise ValueError(
                f"AcousticAlignmentReport.alignment_score must be in [0.0, 1.0], "
                f"got {self.alignment_score}"
            )

        # Validate pressure_band
        valid_bands = {"low", "moderate", "high"}
        if self.pressure_band not in valid_bands:
            raise ValueError(
                f"AcousticAlignmentReport.pressure_band must be one of {valid_bands}, "
                f"got {self.pressure_band!r}"
            )

        # Validate mismatch_tags is a tuple
        if not isinstance(self.mismatch_tags, tuple):
            raise ValueError(
                f"AcousticAlignmentReport.mismatch_tags must be a tuple, "
                f"got {type(self.mismatch_tags).__name__}"
            )

        # Validate all tags are strings
        for tag in self.mismatch_tags:
            if not isinstance(tag, str):
                raise ValueError(
                    f"AcousticAlignmentReport.mismatch_tags must contain only strings, "
                    f"found {type(tag).__name__}"
                )

    def has_misalignment(self) -> bool:
        """Check if alignment score indicates misalignment (< 0.4)."""
        return self.alignment_score < 0.4

    def has_severe_misalignment(self) -> bool:
        """Check if alignment score indicates severe misalignment (< 0.2)."""
        return self.alignment_score < 0.2

    def has_tag(self, tag: str) -> bool:
        """Check if a specific mismatch tag is present."""
        return tag in self.mismatch_tags

    def is_high_pressure(self) -> bool:
        """Check if pressure band is high."""
        return self.pressure_band == "high"

    def to_dict(self) -> dict:
        """Serialize to dictionary for logging/tracing."""
        return {
            "alignment_score": self.alignment_score,
            "pressure_band": self.pressure_band,
            "mismatch_tags": list(self.mismatch_tags),
            "has_misalignment": self.has_misalignment(),
            "has_severe_misalignment": self.has_severe_misalignment(),
        }


# Factory functions for common cases


def create_aligned_report(
    alignment_score: float = 0.8,
    pressure_band: PressureBand = "low",
) -> AcousticAlignmentReport:
    """
    Create an aligned acoustic alignment report.

    Args:
        alignment_score: Alignment score (default 0.8, well-aligned)
        pressure_band: Pressure band (default "low")

    Returns:
        AcousticAlignmentReport with no mismatch tags
    """
    return AcousticAlignmentReport(
        alignment_score=max(0.0, min(1.0, alignment_score)),
        pressure_band=pressure_band,
        mismatch_tags=(),
    )


def create_misaligned_report(
    alignment_score: float = 0.3,
    pressure_band: PressureBand = "high",
    mismatch_tags: Tuple[str, ...] = ("inner_outer_tension",),
) -> AcousticAlignmentReport:
    """
    Create a misaligned acoustic alignment report.

    Args:
        alignment_score: Alignment score (default 0.3, misaligned)
        pressure_band: Pressure band (default "high")
        mismatch_tags: Mismatch tags

    Returns:
        AcousticAlignmentReport with misalignment indicators
    """
    return AcousticAlignmentReport(
        alignment_score=max(0.0, min(1.0, alignment_score)),
        pressure_band=pressure_band,
        mismatch_tags=mismatch_tags,
    )


def create_neutral_report() -> AcousticAlignmentReport:
    """
    Create a neutral acoustic alignment report.

    Used when no specific alignment information is available but
    a report is required. Does not trigger any adjustments.

    Returns:
        AcousticAlignmentReport with neutral values
    """
    return AcousticAlignmentReport(
        alignment_score=0.5,
        pressure_band="moderate",
        mismatch_tags=(),
    )


# Public exports
__all__ = [
    # Type alias
    "PressureBand",
    # Main dataclass
    "AcousticAlignmentReport",
    # Factory functions
    "create_aligned_report",
    "create_misaligned_report",
    "create_neutral_report",
]
