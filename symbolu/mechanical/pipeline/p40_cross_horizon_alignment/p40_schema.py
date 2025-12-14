"""
P40 Schema - Cross-Horizon Resonance Alignment Engine Types

Defines the data structures for Phase 40: Cross-Horizon Resonance Alignment,
a deterministic observer-only phase that measures coherence between time
horizons from Phase 39's multi-horizon forecasts.

PURPOSE:
    Phase 40 detects alignment vs divergence across time horizons.
    It does NOT decide which horizon is "correct."
    It does NOT adjust forecasts.
    It does NOT influence regimes, discourse, semantics, routing, or action.
    It ONLY measures coherence between horizons.

CRITICAL CONSTRAINTS:
    - Deterministic: Same inputs -> same outputs (no LLM, no randomness)
    - Read-only: Does not modify system behavior
    - Observer-only: Never used for gating, blocking, or behavior modification
    - Non-authoritative: Does not influence regime, discourse, or semantics

    Phase 40 MUST NOT:
        - Modify PipelineContext state outside its own output
        - Affect gating, routing, discourse, or action
        - Import P6-P14 or P50+
        - Perform prediction or optimization
        - Interpret meaning or emotion

INVARIANTS:
    - INV-P40-1: Observer-only (no influence on any authoritative phase)
    - INV-P40-2: Deterministic (same inputs -> same outputs)
    - INV-P40-3: No forecast mutation (Phase 39 values are never changed)
    - INV-P40-4: Alignment monotonicity (greater divergence => lower alignment_score)
    - INV-P40-5: Absence-safe (missing optional inputs degrade or remain neutral, never improve)
"""

from dataclasses import dataclass, field
from typing import Any, Dict, Literal, Optional


# =============================================================================
# Version
# =============================================================================

P40_VERSION = "1.0.0"


# =============================================================================
# Type Aliases
# =============================================================================

AlignmentBand = Literal["aligned", "strained", "fragmented"]
DominantHorizon = Literal["short", "medium", "long", "none"]


# =============================================================================
# Constants - Alignment Thresholds
# =============================================================================

# Alignment band thresholds
BAND_ALIGNED_THRESHOLD = 0.75    # alignment_score >= 0.75 -> "aligned"
BAND_STRAINED_THRESHOLD = 0.45  # alignment_score >= 0.45 -> "strained"
# alignment_score < 0.45 -> "fragmented"

# Dominant horizon threshold
DOMINANT_HORIZON_THRESHOLD = 0.15  # Horizon must exceed others by >= 0.15


# =============================================================================
# Helper Functions
# =============================================================================


def classify_alignment_band(alignment_score: float) -> AlignmentBand:
    """
    Classify an alignment score into an alignment band.

    Thresholds:
        - alignment_score >= 0.75 -> "aligned"
        - alignment_score >= 0.45 -> "strained"
        - alignment_score < 0.45 -> "fragmented"

    Args:
        alignment_score: Alignment score in [0.0, 1.0]

    Returns:
        Alignment band classification
    """
    if alignment_score >= BAND_ALIGNED_THRESHOLD:
        return "aligned"
    elif alignment_score >= BAND_STRAINED_THRESHOLD:
        return "strained"
    else:
        return "fragmented"


# =============================================================================
# Dataclasses
# =============================================================================


@dataclass(frozen=True)
class CrossHorizonAlignment:
    """
    Immutable report of cross-horizon resonance alignment.

    This is the primary output of Phase 40, containing:
    - alignment_score: Overall alignment between horizons [0.0, 1.0]
    - alignment_band: Classification ("aligned", "strained", "fragmented")
    - divergence_index: max(horizons) - min(horizons) [0.0, 1.0]
    - dominant_horizon: Which horizon dominates ("short", "medium", "long", "none")
    - observer_only: Always True (enforced)

    Invariants:
        - alignment_score in [0.0, 1.0]
        - alignment_band in {"aligned", "strained", "fragmented"}
        - divergence_index in [0.0, 1.0]
        - dominant_horizon in {"short", "medium", "long", "none"}
        - observer_only == True (cannot be False)
    """

    # Core outputs (all required)
    alignment_score: float
    alignment_band: AlignmentBand
    divergence_index: float
    dominant_horizon: DominantHorizon
    observer_only: Literal[True]

    # Input signals (for observability)
    short_term_score: Optional[float] = None
    medium_term_score: Optional[float] = None
    long_term_score: Optional[float] = None
    drift_fusion_index: Optional[float] = None
    temporal_entropy_diff: Optional[float] = None

    # Debug info
    debug: Dict[str, Any] = field(default_factory=dict)

    # Metadata
    version: str = P40_VERSION
    architectural_phase: str = "P40"

    def __post_init__(self) -> None:
        """Validate invariants."""
        # observer_only must be True (INV-P40-1)
        if self.observer_only is not True:
            raise ValueError(
                "CrossHorizonAlignment.observer_only must be True. "
                "P40 is observation-only and cannot be used for gating."
            )

        # Validate alignment_score range
        if not isinstance(self.alignment_score, (int, float)):
            raise ValueError(
                f"CrossHorizonAlignment.alignment_score must be numeric, "
                f"got {type(self.alignment_score).__name__}"
            )
        if not 0.0 <= self.alignment_score <= 1.0:
            raise ValueError(
                f"CrossHorizonAlignment.alignment_score must be in [0.0, 1.0], "
                f"got {self.alignment_score}"
            )

        # Validate divergence_index range
        if not isinstance(self.divergence_index, (int, float)):
            raise ValueError(
                f"CrossHorizonAlignment.divergence_index must be numeric, "
                f"got {type(self.divergence_index).__name__}"
            )
        if not 0.0 <= self.divergence_index <= 1.0:
            raise ValueError(
                f"CrossHorizonAlignment.divergence_index must be in [0.0, 1.0], "
                f"got {self.divergence_index}"
            )

        # Validate alignment_band
        valid_bands = ("aligned", "strained", "fragmented")
        if self.alignment_band not in valid_bands:
            raise ValueError(
                f"CrossHorizonAlignment.alignment_band must be one of {valid_bands}, "
                f"got '{self.alignment_band}'"
            )

        # Validate dominant_horizon
        valid_horizons = ("short", "medium", "long", "none")
        if self.dominant_horizon not in valid_horizons:
            raise ValueError(
                f"CrossHorizonAlignment.dominant_horizon must be one of {valid_horizons}, "
                f"got '{self.dominant_horizon}'"
            )

    # -------------------------------------------------------------------------
    # Convenience methods
    # -------------------------------------------------------------------------

    def is_aligned(self) -> bool:
        """Return True if alignment band is aligned."""
        return self.alignment_band == "aligned"

    def is_strained(self) -> bool:
        """Return True if alignment band is strained."""
        return self.alignment_band == "strained"

    def is_fragmented(self) -> bool:
        """Return True if alignment band is fragmented."""
        return self.alignment_band == "fragmented"

    def has_dominant_horizon(self) -> bool:
        """Return True if there is a dominant horizon."""
        return self.dominant_horizon != "none"

    def has_high_divergence(self, threshold: float = 0.3) -> bool:
        """Return True if divergence_index exceeds threshold."""
        return self.divergence_index >= threshold

    def to_dict(self) -> Dict[str, Any]:
        """Serialize report to dictionary for API/JSON output."""
        return {
            "alignment_score": self.alignment_score,
            "alignment_band": self.alignment_band,
            "divergence_index": self.divergence_index,
            "dominant_horizon": self.dominant_horizon,
            "observer_only": self.observer_only,
            "inputs": {
                "short_term_score": self.short_term_score,
                "medium_term_score": self.medium_term_score,
                "long_term_score": self.long_term_score,
                "drift_fusion_index": self.drift_fusion_index,
                "temporal_entropy_diff": self.temporal_entropy_diff,
            },
            "debug": self.debug,
            "version": self.version,
            "architectural_phase": self.architectural_phase,
        }


# =============================================================================
# Factory Functions
# =============================================================================


def create_alignment(
    alignment_score: float,
    alignment_band: AlignmentBand,
    divergence_index: float,
    dominant_horizon: DominantHorizon,
    short_term_score: Optional[float] = None,
    medium_term_score: Optional[float] = None,
    long_term_score: Optional[float] = None,
    drift_fusion_index: Optional[float] = None,
    temporal_entropy_diff: Optional[float] = None,
    debug: Optional[Dict[str, Any]] = None,
) -> CrossHorizonAlignment:
    """
    Factory function to create a CrossHorizonAlignment.

    Args:
        alignment_score: Overall alignment [0.0, 1.0]
        alignment_band: Classification band
        divergence_index: Divergence metric [0.0, 1.0]
        dominant_horizon: Which horizon dominates
        short_term_score: P39 short-term score (input traceback)
        medium_term_score: P39 medium-term score (input traceback)
        long_term_score: P39 long-term score (input traceback)
        drift_fusion_index: P19 drift fusion input
        temporal_entropy_diff: P18 temporal entropy input
        debug: Optional debug dictionary

    Returns:
        CrossHorizonAlignment instance
    """
    return CrossHorizonAlignment(
        alignment_score=alignment_score,
        alignment_band=alignment_band,
        divergence_index=divergence_index,
        dominant_horizon=dominant_horizon,
        observer_only=True,
        short_term_score=short_term_score,
        medium_term_score=medium_term_score,
        long_term_score=long_term_score,
        drift_fusion_index=drift_fusion_index,
        temporal_entropy_diff=temporal_entropy_diff,
        debug=debug or {},
    )


# Public exports
__all__ = [
    # Version
    "P40_VERSION",
    # Type Aliases
    "AlignmentBand",
    "DominantHorizon",
    # Constants
    "BAND_ALIGNED_THRESHOLD",
    "BAND_STRAINED_THRESHOLD",
    "DOMINANT_HORIZON_THRESHOLD",
    # Helpers
    "classify_alignment_band",
    # Dataclasses
    "CrossHorizonAlignment",
    # Factory
    "create_alignment",
]
