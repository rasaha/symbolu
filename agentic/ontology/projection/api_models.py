"""
API Models for Ontological Projection Engine
=============================================

Dataclasses and enums for projection requests/responses.

Hard Constraints:
    - All dataclasses are frozen (immutable)
    - Outputs use tuples, not lists
    - No free-form text generation
    - All strings are either hex hashes or fixed reason codes
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Tuple

from agentic.ontology.layers.ontology_layer import OntologicalLayer  # canonical source


# =============================================================================
# Enums
# =============================================================================

class InputRefKind(Enum):
    """Kind of input reference for projection."""
    PHASE5_RESULT = "phase5_result"
    PHASE9_GRAPH = "phase9_graph"
    GENERIC = "generic"


class ProjectionProfile(Enum):
    """Projection profile levels."""
    MINIMAL = "minimal"
    STANDARD = "standard"
    AUDIT = "audit"


class OutputMode(Enum):
    """Output mode for projection results."""
    NON_TEXTUAL = "non_textual"
    TEMPLATE_TEXT = "template_text"


class Strictness(Enum):
    """Strictness level for projection validation."""
    STRICT = "strict"
    AUDIT_STRICT = "audit_strict"


# =============================================================================
# Reason Codes (fixed strings only)
# =============================================================================

class ReasonCode:
    """Fixed reason codes for invariant failures."""
    LAYER_NOT_IMPLEMENTED = "LAYER_NOT_IMPLEMENTED"
    EXCEPTION_BLOCKED = "EXCEPTION_BLOCKED"
    INVALID_MAX_ARTIFACTS = "INVALID_MAX_ARTIFACTS"
    FORBIDDEN_MODULE_IMPORTED = "FORBIDDEN_MODULE_IMPORTED"
    TIMESTAMP_DETECTED = "TIMESTAMP_DETECTED"
    FREEFORM_TEXT_DETECTED = "FREEFORM_TEXT_DETECTED"
    VALIDATION_FAILED = "VALIDATION_FAILED"
    READ_ONLY_VIOLATION = "READ_ONLY_VIOLATION"
    INVALID_OUTPUT_MODE = "INVALID_OUTPUT_MODE"
    PASSED = "PASSED"


# =============================================================================
# Input Models
# =============================================================================

@dataclass(frozen=True)
class FrozenSnapshot:
    """
    Immutable snapshot for projection input.

    Attributes:
        snapshot_id: Unique identifier for the snapshot (hex hash)
        payload: Opaque immutable payload (tests use dicts/tuples)
        content_hash: Hex hash of the payload content
    """
    snapshot_id: str
    payload: Any  # Opaque immutable payload
    content_hash: str


@dataclass(frozen=True)
class InputRef:
    """
    Reference to an input object for projection.

    Attributes:
        kind: Type of input reference (InputRefKind enum)
        object_id: Unique identifier for the object (hex hash or id string)
    """
    kind: InputRefKind
    object_id: str


@dataclass(frozen=True)
class ProjectionOptions:
    """
    Options controlling projection behavior.

    Attributes:
        include_ledger: Whether to include ledger spans in output
        max_artifacts: Maximum number of artifacts to produce (must be > 0)
        output_mode: Output mode (NON_TEXTUAL or TEMPLATE_TEXT)
        strictness: Strictness level for validation
    """
    include_ledger: bool = True
    max_artifacts: int = 100
    output_mode: OutputMode = OutputMode.NON_TEXTUAL
    strictness: Strictness = Strictness.STRICT


@dataclass(frozen=True)
class ProjectionRequest:
    """
    Request for an ontological projection.

    Attributes:
        snapshot_id: ID of the snapshot to project
        layer: Ontological layer to project onto
        input_ref: Reference to the input object
        projection_profile: Profile level (MINIMAL, STANDARD, AUDIT)
        options: Projection options
    """
    snapshot_id: str
    layer: OntologicalLayer
    input_ref: InputRef
    projection_profile: ProjectionProfile = ProjectionProfile.STANDARD
    options: ProjectionOptions = field(default_factory=ProjectionOptions)


# =============================================================================
# Output Models
# =============================================================================

@dataclass(frozen=True)
class InvariantsReport:
    """
    Report on invariant checks during projection.

    Attributes:
        passed: Whether all invariants passed
        reason_codes: Tuple of fixed reason strings (empty if passed)
    """
    passed: bool
    reason_codes: Tuple[str, ...] = ()


@dataclass(frozen=True)
class ProjectionResponse:
    """
    Response from an ontological projection.

    All outputs are tuples (immutable). No free-form text.

    Attributes:
        projection_id: Deterministic hash of projection parameters
        snapshot_id: ID of the projected snapshot
        layer: Ontological layer that was projected
        input_ref: Reference to the input object
        artifacts: Tuple of projection artifacts (hashes, counts, bools)
        ledger_spans: Tuple of ledger span entries
        invariants_report: Report on invariant checks
        eligible: Whether projection was successful
    """
    projection_id: str
    snapshot_id: str
    layer: OntologicalLayer
    input_ref: InputRef
    artifacts: Tuple[Any, ...] = ()
    ledger_spans: Tuple[Any, ...] = ()
    invariants_report: InvariantsReport = field(
        default_factory=lambda: InvariantsReport(passed=True, reason_codes=())
    )
    eligible: bool = True
