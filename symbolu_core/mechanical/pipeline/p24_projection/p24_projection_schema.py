"""
P24 - Acoustic-Ontology Projection Observer Schema Definitions

This phase is observer-only and non-authoritative.

P24 estimates outer human interpretation (10-layer ontology projection) from
already-resolved pipeline artifacts (regime, discourse act, semantic slots,
lexical frame, grammar evidence) and compares it against inner acoustic
witness (P22) + alignment/tension (P23).

P24 MUST NOT:
    - Read raw input text
    - Read token lists
    - Change any upstream decision
    - Affect routing, gating, regime, discourse, semantics, lexical, renderer
    - Override PO1-P23 decisions
    - Mutate existing envelopes (only attach its own report)
    - Call LLMs
    - Introduce non-deterministic behavior

P24 MUST:
    - Be deterministic: same context snapshot -> same output
    - Be observation-only
    - Use conservative defaults when evidence is absent
    - Enforce strict allow-lists for tags
    - Cap projected layers to maximum 3

CRITICAL ARCHITECTURAL INVARIANT:
    P24 is purely observational. It projects ontology layers without authority.
    The projection report is immutable and has no downstream effect on routing.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, FrozenSet, Tuple


# ============================================================================
# VERSION CONSTANT
# ============================================================================


P24_VERSION = "1.0.0"


# ============================================================================
# ALLOWED PROJECTION TAGS - Strict Allow-List (LOCKED)
# ============================================================================


ALLOWED_PROJECTION_TAGS: FrozenSet[str] = frozenset({
    "inner_outer_tension",
    "outer_overreach_risk",
    "high_pressure_low_authority",
    "imperative_under_careful",
    "lexical_certainty_leak",
    "missing_grammar_evidence",
    "missing_lexical_frame",
    "missing_semantic_frame",
    "blocked_context",
    "low_evidence",
})


# ============================================================================
# ENUMS - Ontology Layer Classification (LOCKED)
# ============================================================================


class OntologyLayer(str, Enum):
    """
    10-layer ontology for outer human interpretation projection.

    This phase is observer-only and non-authoritative.

    These layers represent the abstract dimensions of human understanding
    that P24 projects from resolved pipeline artifacts.

    Attributes:
        EXECUTION: Action and task-oriented layer
        IDENTITY: Self and personal reference layer
        FORM: Structure and shape layer
        COGNITION: Mental processing layer
        AGENCY: Autonomy and control layer
        REASONING: Logic and inference layer
        PURPOSE: Goal and intent layer
        OBSERVATION: Witnessing and perceiving layer
        CORE: Fundamental essence layer
        UNIVERSAL: Transcendent/general layer
    """
    EXECUTION = "execution"
    IDENTITY = "identity"
    FORM = "form"
    COGNITION = "cognition"
    AGENCY = "agency"
    REASONING = "reasoning"
    PURPOSE = "purpose"
    OBSERVATION = "observation"
    CORE = "core"
    UNIVERSAL = "universal"


class ProjectionRiskBand(str, Enum):
    """
    Classification of projection risk (potential for misinterpretation).

    This phase is observer-only and non-authoritative.

    Attributes:
        LOW: Risk score <= 0.33
        MODERATE: Risk score > 0.33 and <= 0.66
        HIGH: Risk score > 0.66
    """
    LOW = "low"
    MODERATE = "moderate"
    HIGH = "high"


class ProjectionMismatchType(str, Enum):
    """
    Classification of mismatch between inner (acoustic) and outer (projected).

    This phase is observer-only and non-authoritative.

    Attributes:
        NONE: Inner and outer are aligned
        SOFT_MISMATCH: Minor tension between inner and outer
        STRONG_MISMATCH: Significant contradiction between inner and outer
    """
    NONE = "none"
    SOFT_MISMATCH = "soft_mismatch"
    STRONG_MISMATCH = "strong_mismatch"


# ============================================================================
# DATACLASSES - Projection Report (IMMUTABLE)
# ============================================================================


@dataclass(frozen=True)
class P24ProjectionReport:
    """
    Immutable projection report for acoustic-ontology observation.

    This phase is observer-only and non-authoritative.

    This dataclass captures the projected ontology layers and compares them
    against inner acoustic witness (P22) and alignment state (P23).
    It contains no authority to change routing or upstream decisions.

    Invariants:
        - All fields are read-only (frozen dataclass)
        - observer_only is always True
        - len(projected_layers) <= 3
        - confidence in [0.0, 1.0]
        - projection_tags is subset of ALLOWED_PROJECTION_TAGS
        - Values are deterministic given same input

    Attributes (Observation):
        projected_layers: Tuple of 0-3 ontology layers
        projection_risk_band: Risk band classification (LOW/MODERATE/HIGH)
        mismatch_type: Mismatch between inner and outer (NONE/SOFT/STRONG)
        projection_tags: Descriptive tags from allow-list
        confidence: Evidence completeness score in [0.0, 1.0]

    Attributes (Debug):
        debug: Optional debug info (scoring components only)

    Attributes (Metadata):
        observer_only: Always True - enforces observer-only semantics
        architectural_phase: Identifier for this phase ("P24")
        version: P24 version string for provenance
    """

    # === Observation ===
    projected_layers: Tuple[OntologyLayer, ...]
    projection_risk_band: ProjectionRiskBand
    mismatch_type: ProjectionMismatchType
    projection_tags: FrozenSet[str]
    confidence: float

    # === Debug ===
    debug: Dict[str, Any] = field(default_factory=dict)

    # === Metadata ===
    observer_only: bool = True
    architectural_phase: str = "P24"
    version: str = P24_VERSION

    def __post_init__(self) -> None:
        """
        Validate P24ProjectionReport invariants.

        This phase is observer-only and non-authoritative.
        """
        # Validate observer_only is True
        if not self.observer_only:
            raise ValueError(
                "P24ProjectionReport.observer_only must be True"
            )

        # Validate projected_layers is a tuple
        if not isinstance(self.projected_layers, tuple):
            raise ValueError(
                f"P24ProjectionReport.projected_layers must be tuple, "
                f"got {type(self.projected_layers).__name__}"
            )

        # Validate projected_layers length <= 3
        if len(self.projected_layers) > 3:
            raise ValueError(
                f"P24ProjectionReport.projected_layers must have at most 3 layers, "
                f"got {len(self.projected_layers)}"
            )

        # Validate all layers are OntologyLayer enum values
        for layer in self.projected_layers:
            if not isinstance(layer, OntologyLayer):
                raise ValueError(
                    f"P24ProjectionReport.projected_layers must contain only "
                    f"OntologyLayer values, got {type(layer).__name__}"
                )

        # Validate projection_risk_band is ProjectionRiskBand
        if not isinstance(self.projection_risk_band, ProjectionRiskBand):
            raise ValueError(
                f"P24ProjectionReport.projection_risk_band must be ProjectionRiskBand, "
                f"got {type(self.projection_risk_band).__name__}"
            )

        # Validate mismatch_type is ProjectionMismatchType
        if not isinstance(self.mismatch_type, ProjectionMismatchType):
            raise ValueError(
                f"P24ProjectionReport.mismatch_type must be ProjectionMismatchType, "
                f"got {type(self.mismatch_type).__name__}"
            )

        # Validate projection_tags is a frozenset
        if not isinstance(self.projection_tags, frozenset):
            raise ValueError(
                f"P24ProjectionReport.projection_tags must be frozenset, "
                f"got {type(self.projection_tags).__name__}"
            )

        # Validate all tags are strings
        for tag in self.projection_tags:
            if not isinstance(tag, str):
                raise ValueError(
                    f"P24ProjectionReport.projection_tags must contain only strings, "
                    f"found {type(tag).__name__}"
                )

        # Validate all tags are from allow-list
        invalid_tags = self.projection_tags - ALLOWED_PROJECTION_TAGS
        if invalid_tags:
            raise ValueError(
                f"P24ProjectionReport.projection_tags contains invalid tags: "
                f"{sorted(invalid_tags)}. "
                f"Allowed tags: {sorted(ALLOWED_PROJECTION_TAGS)}"
            )

        # Validate confidence is float in [0.0, 1.0]
        if not isinstance(self.confidence, (int, float)):
            raise ValueError(
                f"P24ProjectionReport.confidence must be float, "
                f"got {type(self.confidence).__name__}"
            )
        if not (0.0 <= self.confidence <= 1.0):
            raise ValueError(
                f"P24ProjectionReport.confidence must be in [0.0, 1.0], "
                f"got {self.confidence}"
            )

    def is_high_risk(self) -> bool:
        """Check if projection risk band is HIGH."""
        return self.projection_risk_band == ProjectionRiskBand.HIGH

    def is_moderate_risk(self) -> bool:
        """Check if projection risk band is MODERATE."""
        return self.projection_risk_band == ProjectionRiskBand.MODERATE

    def is_low_risk(self) -> bool:
        """Check if projection risk band is LOW."""
        return self.projection_risk_band == ProjectionRiskBand.LOW

    def has_strong_mismatch(self) -> bool:
        """Check if mismatch type is STRONG_MISMATCH."""
        return self.mismatch_type == ProjectionMismatchType.STRONG_MISMATCH

    def has_soft_mismatch(self) -> bool:
        """Check if mismatch type is SOFT_MISMATCH."""
        return self.mismatch_type == ProjectionMismatchType.SOFT_MISMATCH

    def has_no_mismatch(self) -> bool:
        """Check if mismatch type is NONE."""
        return self.mismatch_type == ProjectionMismatchType.NONE

    def has_tag(self, tag: str) -> bool:
        """Check if a specific tag is present."""
        return tag in self.projection_tags

    def layer_count(self) -> int:
        """Get the number of projected layers."""
        return len(self.projected_layers)

    def to_dict(self) -> Dict[str, Any]:
        """
        Serialize to dictionary for logging/tracing.

        This phase is observer-only and non-authoritative.
        """
        return {
            # Observation
            "projected_layers": [layer.value for layer in self.projected_layers],
            "projection_risk_band": self.projection_risk_band.value,
            "mismatch_type": self.mismatch_type.value,
            "projection_tags": sorted(self.projection_tags),
            "confidence": self.confidence,
            # Debug
            "debug": self.debug,
            # Metadata
            "observer_only": self.observer_only,
            "architectural_phase": self.architectural_phase,
            "version": self.version,
            # Derived
            "layer_count": len(self.projected_layers),
        }


# ============================================================================
# EXCEPTIONS
# ============================================================================


class P24InvariantViolation(Exception):
    """
    Exception raised when P24 invariants are violated.

    This phase is observer-only and non-authoritative.

    This is raised when:
        - P24 attempts to read forbidden data (raw text, tokens, etc.)
        - P24 attempts to write to ctx outside p24_*
        - P24 output is used for gating or policy
        - Non-determinism is detected
        - Invalid tags are used
    """

    def __init__(self, message: str, violation_type: str = "UNKNOWN") -> None:
        """
        Initialize the violation exception.

        Args:
            message: Human-readable description of the violation
            violation_type: Category of violation (FORBIDDEN_ACCESS, INVALID_TAG, etc.)
        """
        super().__init__(message)
        self.violation_type = violation_type
        self.message = message

    def __str__(self) -> str:
        return f"[P24:{self.violation_type}] {self.message}"


# ============================================================================
# FACTORY FUNCTIONS
# ============================================================================


def create_empty_report() -> P24ProjectionReport:
    """
    Create an empty/neutral projection report.

    This phase is observer-only and non-authoritative.

    Used when PO1 is blocked or when minimal evidence is available.

    Returns:
        P24ProjectionReport with empty layers and conservative defaults
    """
    return P24ProjectionReport(
        projected_layers=(),
        projection_risk_band=ProjectionRiskBand.LOW,
        mismatch_type=ProjectionMismatchType.NONE,
        projection_tags=frozenset(),
        confidence=0.0,
    )


def create_blocked_report() -> P24ProjectionReport:
    """
    Create a report for blocked context.

    This phase is observer-only and non-authoritative.

    Used when PO1 indicates blocking.

    Returns:
        P24ProjectionReport with blocked_context tag
    """
    return P24ProjectionReport(
        projected_layers=(),
        projection_risk_band=ProjectionRiskBand.HIGH,
        mismatch_type=ProjectionMismatchType.STRONG_MISMATCH,
        projection_tags=frozenset({"blocked_context"}),
        confidence=0.0,
    )


# ============================================================================
# PUBLIC EXPORTS
# ============================================================================


__all__ = [
    # Version
    "P24_VERSION",
    # Allow-list
    "ALLOWED_PROJECTION_TAGS",
    # Enums
    "OntologyLayer",
    "ProjectionRiskBand",
    "ProjectionMismatchType",
    # Dataclasses
    "P24ProjectionReport",
    # Exceptions
    "P24InvariantViolation",
    # Factory functions
    "create_empty_report",
    "create_blocked_report",
]
