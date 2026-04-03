"""
P33 - Schema Adaptive Routing Snapshot Schema Definitions

P33 is an observation-only phase that computes schema-level stability and
alignment metrics WITHOUT influencing any behavior or routing decisions.

P33 answers: "Which internal cognitive schema is currently most stable and
aligned — without influencing behavior?"

P33 does NOT:
- Modify upstream decisions (regime, discourse, semantics, lexical, delivery)
- Block pipeline execution
- Gate or route anything
- Influence P10/P12 results
- Import P6, P7, P8, P9, Policy, Planner, Renderer, or Observer modules (P22-P24)
- Call LLMs or use any randomness
- Use observer acoustic data as input

P33 MAY read from PipelineContext (read-only):
- ctx.coherence_state (coherence_v3, coherence_v3_quality)
- ctx.p18_temporal_entropy (entropy metrics)
- ctx.p19_drift_fusion (drift fusion index)
- ctx.identity_harmonics (if present)
- ctx.persona_schema_metadata (static definitions only)

Design Principles:
- Observation-Only: Reads upstream state, produces snapshot, changes nothing
- Deterministic: Same inputs → same outputs (bitwise), no LLM calls, no randomness
- Conservative: Uses neutral defaults for missing inputs
- Fixed Formula: Weighted blend of stability sources

Invariants:
- INV-P33-1: Phase 33 cannot influence any decision
- INV-P33-2: Schema scores are observational only
- INV-P33-3: Dominant schema selection has zero side effects
- INV-P33-4: Observer data (P22-P24) cannot enter Phase 33
- INV-P33-5: Absence of schema metadata does not break pipeline
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, FrozenSet, List, Optional, Tuple


# ============================================================================
# VERSION
# ============================================================================

P33_VERSION = "1.0.0"


# ============================================================================
# ENUMS - Stability and alignment classification
# ============================================================================


class SchemaStabilityBand(str, Enum):
    """
    Classification of schema stability based on composite score.

    HIGH: Schema is highly stable (score >= 0.7)
    MODERATE: Schema has moderate stability (0.4 <= score < 0.7)
    LOW: Schema has low stability (score < 0.4)
    UNKNOWN: Insufficient data to classify stability
    """
    HIGH = "HIGH"
    MODERATE = "MODERATE"
    LOW = "LOW"
    UNKNOWN = "UNKNOWN"


class SchemaConfidenceBand(str, Enum):
    """
    Classification of confidence in schema assessment.

    HIGH: High confidence in assessment (confidence >= 0.7)
    MODERATE: Moderate confidence (0.4 <= confidence < 0.7)
    LOW: Low confidence (confidence < 0.4)
    INSUFFICIENT: Not enough data for reliable assessment
    """
    HIGH = "HIGH"
    MODERATE = "MODERATE"
    LOW = "LOW"
    INSUFFICIENT = "INSUFFICIENT"


# ============================================================================
# ALLOWED DIAGNOSTIC TAGS - Frozen set of permitted tags
# ============================================================================

ALLOWED_SCHEMA_TAGS: FrozenSet[str] = frozenset({
    # Stability indicators
    "HIGHLY_STABLE",
    "MODERATELY_STABLE",
    "LOW_STABILITY",
    "INSUFFICIENT_HISTORY",
    # Alignment indicators
    "ALIGNED",
    "MISALIGNED",
    "NEUTRAL_ALIGNMENT",
    # Drift indicators
    "LOW_DRIFT",
    "MODERATE_DRIFT",
    "HIGH_DRIFT",
    # Confidence indicators
    "HIGH_CONFIDENCE",
    "MODERATE_CONFIDENCE",
    "LOW_CONFIDENCE",
    # Schema state indicators
    "DOMINANT_CLEAR",
    "DOMINANT_UNCLEAR",
    "MULTIPLE_CANDIDATES",
    "NO_SCHEMAS_DEFINED",
})


# ============================================================================
# DATACLASSES - Core envelope objects
# ============================================================================


@dataclass(frozen=True)
class SchemaAdaptiveRoutingSnapshot:
    """
    P33 output envelope: Schema adaptive routing observation snapshot.

    This is a read-only, immutable snapshot of schema-level metrics.
    It is NEVER used for routing - only for diagnostics and observability.

    Invariants:
    - All score values must be in [0.0, 1.0]
    - observer_only must always be True
    - This snapshot MUST NOT be used to influence any pipeline decision
    - Same inputs MUST produce identical outputs (determinism)

    Attributes:
        schema_alignment_scores: Per-schema alignment scores [0.0, 1.0]
        schema_stability_scores: Per-schema stability scores [0.0, 1.0]
        schema_drift_scores: Per-schema drift scores [0.0, 1.0]
        dominant_schema: Most stable/aligned schema, or None if unclear
        confidence: Overall confidence in assessment [0.0, 1.0]
        stability_band: Overall stability classification
        confidence_band: Confidence level classification
        diagnostic_tags: Frozen set of diagnostic tags
        debug: Additional debug/trace information
        observer_only: Always True - marks this as non-authoritative
        architectural_phase: Identifier for this phase ("P33")
        version: Schema version for compatibility checking
    """
    # Core scores - per schema
    schema_alignment_scores: Dict[str, float]
    schema_stability_scores: Dict[str, float]
    schema_drift_scores: Dict[str, float]

    # Dominant schema identification
    dominant_schema: Optional[str]
    confidence: float

    # Classifications
    stability_band: SchemaStabilityBand
    confidence_band: SchemaConfidenceBand

    # Diagnostic metadata
    diagnostic_tags: FrozenSet[str] = field(default_factory=frozenset)
    debug: Dict[str, Any] = field(default_factory=dict)

    # Authority markers - MUST be True
    observer_only: bool = True
    architectural_phase: str = "P33"
    version: str = P33_VERSION

    def __post_init__(self) -> None:
        """Validate SchemaAdaptiveRoutingSnapshot invariants."""
        # INV-P33-2: observer_only must always be True
        if not self.observer_only:
            raise ValueError(
                "SchemaAdaptiveRoutingSnapshot.observer_only must be True. "
                "P33 is observation-only and non-authoritative."
            )

        # Validate schema_alignment_scores
        if not isinstance(self.schema_alignment_scores, dict):
            raise ValueError(
                f"SchemaAdaptiveRoutingSnapshot.schema_alignment_scores must be dict, "
                f"got {type(self.schema_alignment_scores).__name__}"
            )
        for schema_id, score in self.schema_alignment_scores.items():
            if not isinstance(schema_id, str):
                raise ValueError(
                    f"Schema IDs must be strings, got {type(schema_id).__name__}"
                )
            if not isinstance(score, (int, float)):
                raise ValueError(
                    f"Alignment score for '{schema_id}' must be numeric, "
                    f"got {type(score).__name__}"
                )
            if not 0.0 <= score <= 1.0:
                raise ValueError(
                    f"Alignment score for '{schema_id}' must be in [0.0, 1.0], "
                    f"got {score}"
                )

        # Validate schema_stability_scores
        if not isinstance(self.schema_stability_scores, dict):
            raise ValueError(
                f"SchemaAdaptiveRoutingSnapshot.schema_stability_scores must be dict, "
                f"got {type(self.schema_stability_scores).__name__}"
            )
        for schema_id, score in self.schema_stability_scores.items():
            if not isinstance(schema_id, str):
                raise ValueError(
                    f"Schema IDs must be strings, got {type(schema_id).__name__}"
                )
            if not isinstance(score, (int, float)):
                raise ValueError(
                    f"Stability score for '{schema_id}' must be numeric, "
                    f"got {type(score).__name__}"
                )
            if not 0.0 <= score <= 1.0:
                raise ValueError(
                    f"Stability score for '{schema_id}' must be in [0.0, 1.0], "
                    f"got {score}"
                )

        # Validate schema_drift_scores
        if not isinstance(self.schema_drift_scores, dict):
            raise ValueError(
                f"SchemaAdaptiveRoutingSnapshot.schema_drift_scores must be dict, "
                f"got {type(self.schema_drift_scores).__name__}"
            )
        for schema_id, score in self.schema_drift_scores.items():
            if not isinstance(schema_id, str):
                raise ValueError(
                    f"Schema IDs must be strings, got {type(schema_id).__name__}"
                )
            if not isinstance(score, (int, float)):
                raise ValueError(
                    f"Drift score for '{schema_id}' must be numeric, "
                    f"got {type(score).__name__}"
                )
            if not 0.0 <= score <= 1.0:
                raise ValueError(
                    f"Drift score for '{schema_id}' must be in [0.0, 1.0], "
                    f"got {score}"
                )

        # Validate dominant_schema
        if self.dominant_schema is not None:
            if not isinstance(self.dominant_schema, str):
                raise ValueError(
                    f"SchemaAdaptiveRoutingSnapshot.dominant_schema must be str or None, "
                    f"got {type(self.dominant_schema).__name__}"
                )

        # Validate confidence
        if not isinstance(self.confidence, (int, float)):
            raise ValueError(
                f"SchemaAdaptiveRoutingSnapshot.confidence must be numeric, "
                f"got {type(self.confidence).__name__}"
            )
        if not 0.0 <= self.confidence <= 1.0:
            raise ValueError(
                f"SchemaAdaptiveRoutingSnapshot.confidence must be in [0.0, 1.0], "
                f"got {self.confidence}"
            )

        # Validate stability_band
        if not isinstance(self.stability_band, SchemaStabilityBand):
            raise ValueError(
                f"SchemaAdaptiveRoutingSnapshot.stability_band must be SchemaStabilityBand, "
                f"got {type(self.stability_band).__name__}"
            )

        # Validate confidence_band
        if not isinstance(self.confidence_band, SchemaConfidenceBand):
            raise ValueError(
                f"SchemaAdaptiveRoutingSnapshot.confidence_band must be SchemaConfidenceBand, "
                f"got {type(self.confidence_band).__name__}"
            )

        # Validate diagnostic_tags - must be subset of allowed tags
        if not isinstance(self.diagnostic_tags, frozenset):
            raise ValueError(
                f"SchemaAdaptiveRoutingSnapshot.diagnostic_tags must be frozenset, "
                f"got {type(self.diagnostic_tags).__name__}"
            )
        invalid_tags = self.diagnostic_tags - ALLOWED_SCHEMA_TAGS
        if invalid_tags:
            raise ValueError(
                f"SchemaAdaptiveRoutingSnapshot.diagnostic_tags contains invalid tags: {invalid_tags}"
            )

    # ========================================================================
    # CONVENIENCE METHODS - For downstream observability access
    # ========================================================================

    def is_highly_stable(self) -> bool:
        """Check if overall stability is HIGH."""
        return self.stability_band == SchemaStabilityBand.HIGH

    def is_low_stability(self) -> bool:
        """Check if overall stability is LOW."""
        return self.stability_band == SchemaStabilityBand.LOW

    def has_dominant_schema(self) -> bool:
        """Check if a dominant schema was identified."""
        return self.dominant_schema is not None

    def is_high_confidence(self) -> bool:
        """Check if confidence in assessment is HIGH."""
        return self.confidence_band == SchemaConfidenceBand.HIGH

    def is_low_confidence(self) -> bool:
        """Check if confidence in assessment is LOW or INSUFFICIENT."""
        return self.confidence_band in (
            SchemaConfidenceBand.LOW,
            SchemaConfidenceBand.INSUFFICIENT
        )

    def get_schema_count(self) -> int:
        """Get the number of schemas analyzed."""
        return len(self.schema_stability_scores)

    def has_tag(self, tag: str) -> bool:
        """Check if a specific diagnostic tag is present."""
        return tag in self.diagnostic_tags

    def get_alignment_for_schema(self, schema_id: str) -> Optional[float]:
        """Get alignment score for a specific schema."""
        return self.schema_alignment_scores.get(schema_id)

    def get_stability_for_schema(self, schema_id: str) -> Optional[float]:
        """Get stability score for a specific schema."""
        return self.schema_stability_scores.get(schema_id)

    def get_drift_for_schema(self, schema_id: str) -> Optional[float]:
        """Get drift score for a specific schema."""
        return self.schema_drift_scores.get(schema_id)

    def to_dict(self) -> Dict[str, Any]:
        """Serialize to dictionary for logging/tracing."""
        return {
            "schema_alignment_scores": dict(self.schema_alignment_scores),
            "schema_stability_scores": dict(self.schema_stability_scores),
            "schema_drift_scores": dict(self.schema_drift_scores),
            "dominant_schema": self.dominant_schema,
            "confidence": self.confidence,
            "stability_band": self.stability_band.value,
            "confidence_band": self.confidence_band.value,
            "diagnostic_tags": sorted(self.diagnostic_tags),
            "debug": self.debug,
            "observer_only": self.observer_only,
            "architectural_phase": self.architectural_phase,
            "version": self.version,
        }


# ============================================================================
# HELPER FUNCTIONS
# ============================================================================


def create_snapshot(
    schema_alignment_scores: Optional[Dict[str, float]] = None,
    schema_stability_scores: Optional[Dict[str, float]] = None,
    schema_drift_scores: Optional[Dict[str, float]] = None,
    dominant_schema: Optional[str] = None,
    confidence: float = 0.5,
    stability_band: SchemaStabilityBand = SchemaStabilityBand.UNKNOWN,
    confidence_band: SchemaConfidenceBand = SchemaConfidenceBand.INSUFFICIENT,
    diagnostic_tags: Optional[FrozenSet[str]] = None,
    debug: Optional[Dict[str, Any]] = None,
) -> SchemaAdaptiveRoutingSnapshot:
    """
    Helper to create a SchemaAdaptiveRoutingSnapshot.

    Args:
        schema_alignment_scores: Per-schema alignment scores
        schema_stability_scores: Per-schema stability scores
        schema_drift_scores: Per-schema drift scores
        dominant_schema: Most stable/aligned schema identifier
        confidence: Confidence in assessment [0.0, 1.0]
        stability_band: Overall stability classification
        confidence_band: Confidence level classification
        diagnostic_tags: Set of diagnostic tags
        debug: Optional debug/trace information

    Returns:
        A validated SchemaAdaptiveRoutingSnapshot instance
    """
    return SchemaAdaptiveRoutingSnapshot(
        schema_alignment_scores=schema_alignment_scores or {},
        schema_stability_scores=schema_stability_scores or {},
        schema_drift_scores=schema_drift_scores or {},
        dominant_schema=dominant_schema,
        confidence=confidence,
        stability_band=stability_band,
        confidence_band=confidence_band,
        diagnostic_tags=diagnostic_tags or frozenset(),
        debug=debug or {},
        observer_only=True,  # Always True
    )


def create_empty_snapshot() -> SchemaAdaptiveRoutingSnapshot:
    """
    Create an empty snapshot with default values.

    Used when P33 cannot compute meaningful metrics (e.g., missing inputs).

    Returns:
        A minimal SchemaAdaptiveRoutingSnapshot with neutral defaults
    """
    return create_snapshot(
        schema_alignment_scores={},
        schema_stability_scores={},
        schema_drift_scores={},
        dominant_schema=None,
        confidence=0.0,
        stability_band=SchemaStabilityBand.UNKNOWN,
        confidence_band=SchemaConfidenceBand.INSUFFICIENT,
        diagnostic_tags=frozenset({"INSUFFICIENT_HISTORY", "NO_SCHEMAS_DEFINED"}),
        debug={"reason": "empty_snapshot"},
    )


# Public exports
__all__ = [
    # Version
    "P33_VERSION",
    # Enums
    "SchemaStabilityBand",
    "SchemaConfidenceBand",
    # Constants
    "ALLOWED_SCHEMA_TAGS",
    # Dataclasses
    "SchemaAdaptiveRoutingSnapshot",
    # Helpers
    "create_snapshot",
    "create_empty_snapshot",
]
