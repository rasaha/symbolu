"""
Phase 32 - Insight Window Envelope Schema

Immutable output envelope for insight window gating decisions.

This module defines the InsightWindowEnvelope dataclass which represents
the single-responsibility output of Phase 32: determining whether deeper
insights may be surfaced.

CRITICAL INVARIANTS:
- INV-P32-1: Insight gating never opens due to observers
- INV-P32-2: Gate monotonicity enforced (can only close, never open)
- INV-P32-3: No upstream influence
- INV-P32-4: Deterministic behavior
- INV-P32-5: Envelope is advisory only

The envelope is read-only downstream and does NOT:
- Trigger regime changes (P6)
- Select discourse acts (P7)
- Modify semantics or lexical frames (P8-P9)
- Influence persona, DHA, renderer
- Trigger actions or agent handoff

Design Principle:
    Insight gating decides WHEN insight is allowed, NOT what insight is given.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, FrozenSet, List, Optional, Tuple


# ============================================================================
# VERSION
# ============================================================================

P32_VERSION = "1.0.0"


# ============================================================================
# ENUMS
# ============================================================================


class ConfidenceBand(str, Enum):
    """
    Classification of confidence in the gating decision.

    LOW: Low confidence in gating decision (confidence < 0.4)
    MEDIUM: Moderate confidence (0.4 <= confidence < 0.7)
    HIGH: High confidence (confidence >= 0.7)
    """
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


# ============================================================================
# ALLOWED REASON CODES - Frozen set of permitted gating reason codes
# ============================================================================

ALLOWED_REASON_CODES: FrozenSet[str] = frozenset({
    # Coherence-related closures
    "LOW_COHERENCE_QUALITY",
    "COHERENCE_BELOW_THRESHOLD",
    # Entropy-related closures
    "HIGH_TEMPORAL_ENTROPY",
    "ENTROPY_VOLATILITY",
    # Drift-related closures
    "ELEVATED_DRIFT",
    "HIGH_DRIFT_FUSION",
    # Schema-related closures
    "SCHEMA_INSTABILITY",
    "LOW_SCHEMA_STABILITY",
    # UCF-related closures
    "LOW_UCF_SCORE",
    "UCF_BELOW_THRESHOLD",
    # Acoustic-related closures (observer-only)
    "ACOUSTIC_MISALIGNMENT",
    "ACOUSTIC_PENALTY_APPLIED",
    # Gate state indicators
    "GATE_OPEN",
    "GATE_CLOSED",
    "DEPTH_BELOW_THRESHOLD",
    # Input availability
    "MISSING_INPUTS",
    "INSUFFICIENT_DATA",
})


# ============================================================================
# THRESHOLDS (LOCKED)
# ============================================================================

# Gate opening threshold
INSIGHT_GATE_THRESHOLD = 0.55

# Confidence band thresholds
CONFIDENCE_HIGH_THRESHOLD = 0.70
CONFIDENCE_LOW_THRESHOLD = 0.40


# ============================================================================
# DATACLASS - InsightWindowEnvelope
# ============================================================================


@dataclass(frozen=True)
class InsightWindowEnvelope:
    """
    P32 output envelope: Insight window gating decision.

    This is a read-only, immutable envelope representing whether deeper
    insights may be surfaced at the current moment.

    CRITICAL: This envelope is advisory only. It MUST NOT be used to:
    - Trigger regime changes
    - Select discourse acts
    - Modify semantics or lexical frames
    - Influence persona, DHA, renderer
    - Trigger actions or agent handoff

    Invariants:
    - is_open is True only when insight_depth >= 0.55
    - insight_depth is always in [0.0, 1.0]
    - gating_reason_codes only contains allowed codes
    - observer_only must always be True
    - This envelope MUST NOT be used to open gates (monotonic-restrictive)

    Attributes:
        is_open: Whether the insight window is open (depth >= 0.55)
        insight_depth: Computed depth score [0.0, 1.0]
        gating_reason_codes: Reason codes explaining why gating tightened
        confidence_band: Confidence level in the gating decision
        raw_depth: Pre-penalty depth score (for audit)
        penalties_applied: List of penalties that were applied
        debug: Additional debug/trace information
        observer_only: Always True - marks this as non-authoritative
        architectural_phase: Identifier for this phase ("P32")
        version: Schema version for compatibility checking
    """
    # Core gating decision
    is_open: bool
    insight_depth: float
    gating_reason_codes: Tuple[str, ...]
    confidence_band: ConfidenceBand

    # Audit trail
    raw_depth: float = 0.0
    penalties_applied: Tuple[str, ...] = field(default_factory=tuple)

    # Debug/trace
    debug: Dict[str, Any] = field(default_factory=dict)

    # Authority markers - MUST be True
    observer_only: bool = True
    architectural_phase: str = "P32"
    version: str = P32_VERSION

    def __post_init__(self) -> None:
        """Validate InsightWindowEnvelope invariants."""
        # INV-P32-5: observer_only must always be True
        if not self.observer_only:
            raise ValueError(
                "InsightWindowEnvelope.observer_only must be True. "
                "P32 is observation-only and non-authoritative."
            )

        # Validate insight_depth is in [0.0, 1.0]
        if not isinstance(self.insight_depth, (int, float)):
            raise ValueError(
                f"InsightWindowEnvelope.insight_depth must be numeric, "
                f"got {type(self.insight_depth).__name__}"
            )
        if not 0.0 <= self.insight_depth <= 1.0:
            raise ValueError(
                f"InsightWindowEnvelope.insight_depth must be in [0.0, 1.0], "
                f"got {self.insight_depth}"
            )

        # Validate raw_depth is in [0.0, 1.0]
        if not isinstance(self.raw_depth, (int, float)):
            raise ValueError(
                f"InsightWindowEnvelope.raw_depth must be numeric, "
                f"got {type(self.raw_depth).__name__}"
            )
        if not 0.0 <= self.raw_depth <= 1.0:
            raise ValueError(
                f"InsightWindowEnvelope.raw_depth must be in [0.0, 1.0], "
                f"got {self.raw_depth}"
            )

        # INV-P32-2: Monotonicity - final depth must not exceed raw depth
        if self.insight_depth > self.raw_depth + 1e-9:  # Small epsilon for float comparison
            raise ValueError(
                f"InsightWindowEnvelope violates monotonicity: "
                f"insight_depth ({self.insight_depth}) > raw_depth ({self.raw_depth})"
            )

        # Validate is_open matches the threshold rule
        expected_open = self.insight_depth >= INSIGHT_GATE_THRESHOLD
        if self.is_open != expected_open:
            raise ValueError(
                f"InsightWindowEnvelope.is_open ({self.is_open}) does not match "
                f"threshold rule: insight_depth ({self.insight_depth}) >= {INSIGHT_GATE_THRESHOLD} "
                f"should be {expected_open}"
            )

        # Validate confidence_band
        if not isinstance(self.confidence_band, ConfidenceBand):
            raise ValueError(
                f"InsightWindowEnvelope.confidence_band must be ConfidenceBand, "
                f"got {type(self.confidence_band).__name__}"
            )

        # Validate gating_reason_codes - must be tuple of allowed codes
        if not isinstance(self.gating_reason_codes, tuple):
            raise ValueError(
                f"InsightWindowEnvelope.gating_reason_codes must be tuple, "
                f"got {type(self.gating_reason_codes).__name__}"
            )
        invalid_codes = set(self.gating_reason_codes) - ALLOWED_REASON_CODES
        if invalid_codes:
            raise ValueError(
                f"InsightWindowEnvelope.gating_reason_codes contains invalid codes: {invalid_codes}"
            )

        # Validate penalties_applied - must be tuple
        if not isinstance(self.penalties_applied, tuple):
            raise ValueError(
                f"InsightWindowEnvelope.penalties_applied must be tuple, "
                f"got {type(self.penalties_applied).__name__}"
            )

    # ========================================================================
    # CONVENIENCE METHODS - For downstream observability access
    # ========================================================================

    def is_gate_open(self) -> bool:
        """Check if the insight gate is open."""
        return self.is_open

    def is_gate_closed(self) -> bool:
        """Check if the insight gate is closed."""
        return not self.is_open

    def is_high_confidence(self) -> bool:
        """Check if confidence in gating decision is HIGH."""
        return self.confidence_band == ConfidenceBand.HIGH

    def is_low_confidence(self) -> bool:
        """Check if confidence in gating decision is LOW."""
        return self.confidence_band == ConfidenceBand.LOW

    def has_reason_code(self, code: str) -> bool:
        """Check if a specific reason code is present."""
        return code in self.gating_reason_codes

    def reason_code_count(self) -> int:
        """Get the number of gating reason codes."""
        return len(self.gating_reason_codes)

    def penalty_count(self) -> int:
        """Get the number of penalties applied."""
        return len(self.penalties_applied)

    def has_acoustic_penalty(self) -> bool:
        """Check if an acoustic penalty was applied."""
        return "ACOUSTIC_PENALTY_APPLIED" in self.gating_reason_codes

    def get_depth_reduction(self) -> float:
        """Get the total depth reduction from penalties."""
        return self.raw_depth - self.insight_depth

    def to_dict(self) -> Dict[str, Any]:
        """Serialize to dictionary for logging/tracing."""
        return {
            "is_open": self.is_open,
            "insight_depth": self.insight_depth,
            "gating_reason_codes": list(self.gating_reason_codes),
            "confidence_band": self.confidence_band.value,
            "raw_depth": self.raw_depth,
            "penalties_applied": list(self.penalties_applied),
            "debug": self.debug,
            "observer_only": self.observer_only,
            "architectural_phase": self.architectural_phase,
            "version": self.version,
        }


# ============================================================================
# HELPER FUNCTIONS
# ============================================================================


def create_envelope(
    insight_depth: float,
    raw_depth: Optional[float] = None,
    gating_reason_codes: Optional[List[str]] = None,
    confidence_band: Optional[ConfidenceBand] = None,
    penalties_applied: Optional[List[str]] = None,
    debug: Optional[Dict[str, Any]] = None,
) -> InsightWindowEnvelope:
    """
    Helper to create an InsightWindowEnvelope.

    Args:
        insight_depth: Final gated depth score [0.0, 1.0]
        raw_depth: Pre-penalty depth score (defaults to insight_depth)
        gating_reason_codes: List of reason codes
        confidence_band: Confidence level (auto-computed if None)
        penalties_applied: List of penalty descriptions
        debug: Optional debug/trace information

    Returns:
        A validated InsightWindowEnvelope instance
    """
    # Clamp depth to valid range
    insight_depth = max(0.0, min(1.0, insight_depth))

    # Default raw_depth to insight_depth if not provided
    if raw_depth is None:
        raw_depth = insight_depth
    raw_depth = max(0.0, min(1.0, raw_depth))

    # Ensure monotonicity
    if insight_depth > raw_depth:
        insight_depth = raw_depth

    # Determine is_open based on threshold
    is_open = insight_depth >= INSIGHT_GATE_THRESHOLD

    # Build reason codes
    codes = list(gating_reason_codes or [])
    if is_open:
        if "GATE_OPEN" not in codes:
            codes.append("GATE_OPEN")
    else:
        if "GATE_CLOSED" not in codes:
            codes.append("GATE_CLOSED")
        if insight_depth < INSIGHT_GATE_THRESHOLD and "DEPTH_BELOW_THRESHOLD" not in codes:
            codes.append("DEPTH_BELOW_THRESHOLD")

    # Auto-compute confidence band if not provided
    if confidence_band is None:
        # Higher depth and fewer penalties = higher confidence
        if raw_depth >= 0.7 and len(penalties_applied or []) == 0:
            confidence_band = ConfidenceBand.HIGH
        elif raw_depth < 0.4 or len(penalties_applied or []) > 2:
            confidence_band = ConfidenceBand.LOW
        else:
            confidence_band = ConfidenceBand.MEDIUM

    return InsightWindowEnvelope(
        is_open=is_open,
        insight_depth=insight_depth,
        gating_reason_codes=tuple(codes),
        confidence_band=confidence_band,
        raw_depth=raw_depth,
        penalties_applied=tuple(penalties_applied or []),
        debug=debug or {},
        observer_only=True,
    )


def create_closed_envelope(
    reason: str = "INSUFFICIENT_DATA",
    debug: Optional[Dict[str, Any]] = None,
) -> InsightWindowEnvelope:
    """
    Create a closed envelope with default values.

    Used when P32 cannot compute meaningful metrics (e.g., missing inputs).

    Args:
        reason: Primary reason code for closure
        debug: Optional debug/trace information

    Returns:
        A minimal InsightWindowEnvelope with closed gate
    """
    return create_envelope(
        insight_depth=0.0,
        raw_depth=0.0,
        gating_reason_codes=[reason, "GATE_CLOSED"],
        confidence_band=ConfidenceBand.LOW,
        penalties_applied=[],
        debug=debug or {"reason": "closed_envelope"},
    )


# Public exports
__all__ = [
    # Version
    "P32_VERSION",
    # Enums
    "ConfidenceBand",
    # Constants
    "ALLOWED_REASON_CODES",
    "INSIGHT_GATE_THRESHOLD",
    "CONFIDENCE_HIGH_THRESHOLD",
    "CONFIDENCE_LOW_THRESHOLD",
    # Dataclasses
    "InsightWindowEnvelope",
    # Helpers
    "create_envelope",
    "create_closed_envelope",
]
