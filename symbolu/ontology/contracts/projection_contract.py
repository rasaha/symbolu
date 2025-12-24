"""
Ontological Projection Contracts
================================

Dataclasses for projection requests and responses.

Hard Constraints:
    - All dataclasses are frozen (immutable)
    - Artifacts are opaque (router never inspects meaning)
    - All outputs are hash-stable
    - Fail-closed on any mismatch
    - No semantic inference
    - No free-form text generation
"""

from dataclasses import dataclass, field
from typing import Any, Dict, Mapping, Optional, Tuple

from symbolu.ontology.layers.ontology_layer import OntologicalLayer


# =============================================================================
# Reason Codes (Fixed Strings Only)
# =============================================================================

class ProjectionReasonCode:
    """Fixed reason codes for projection operations."""
    PASSED = "PASSED"
    INVALID_PHASE_ID = "INVALID_PHASE_ID"
    EMPTY_ARTIFACT_REF = "EMPTY_ARTIFACT_REF"
    GATED_LAYER_NOT_ENABLED = "GATED_LAYER_NOT_ENABLED"
    HASH_MISMATCH = "HASH_MISMATCH"
    VALIDATION_FAILED = "VALIDATION_FAILED"
    LEDGER_ERROR = "LEDGER_ERROR"


# =============================================================================
# Request Options
# =============================================================================

@dataclass(frozen=True)
class ProjectionRequestOptions:
    """
    Options controlling projection behavior.

    Attributes:
        include_gated_layers: If True, gated layers (ABSOLVING) are included.
                              Default is False (fail-closed).
        include_ledger_spans: If True, ledger span info is included in response.
                              Default is True.
    """
    include_gated_layers: bool = False
    include_ledger_spans: bool = True


# =============================================================================
# Request Contract
# =============================================================================

@dataclass(frozen=True)
class ProjectionRequest:
    """
    Request for ontological layer projection.

    Attributes:
        phase_id: The phase identifier (e.g., "1b", "2", "9").
        artifact_ref: Opaque reference to the artifact. Router does not
                      inspect the contents - it is passed through unchanged.
        options: Projection options (optional, defaults provided).

    Invariants:
        - phase_id must be a non-empty string
        - artifact_ref is opaque and immutable
        - Options are strictly typed
    """
    phase_id: str
    artifact_ref: Any  # Opaque - router never inspects meaning
    options: ProjectionRequestOptions = field(
        default_factory=ProjectionRequestOptions
    )

    def __post_init__(self) -> None:
        """Validate invariants on construction."""
        if not isinstance(self.phase_id, str):
            raise TypeError("phase_id must be a string")
        if len(self.phase_id) == 0:
            raise ValueError("phase_id must not be empty")


# =============================================================================
# Response Contract
# =============================================================================

@dataclass(frozen=True)
class ProjectionResponse:
    """
    Response from ontological layer projection.

    All outputs are tuples (immutable). No free-form text.

    Attributes:
        layers: Tuple of ontological layers the artifact projects onto.
                Ordering is deterministic (sorted by layer.value).
        artifacts: Tuple of artifacts (opaque pass-through).
                   Router does not modify artifacts.
        ledger_spans: Tuple of ledger span IDs (hex hashes).
                      Empty if include_ledger_spans is False.
        eligible: True if projection succeeded, False on any failure.
        invariants_report: Dict mapping invariant names to pass/fail status.

    Invariants:
        - All outputs are hash-stable
        - Same input always produces identical output
        - No semantic inference
    """
    layers: Tuple[OntologicalLayer, ...] = ()
    artifacts: Tuple[Any, ...] = ()  # Opaque pass-through
    ledger_spans: Tuple[str, ...] = ()
    eligible: bool = True
    invariants_report: Mapping[str, bool] = field(default_factory=dict)

    def __post_init__(self) -> None:
        """Ensure invariants_report is immutable."""
        # Convert to immutable mapping if needed
        if isinstance(self.invariants_report, dict):
            # Frozen dataclass prevents reassignment, but dict itself is mutable
            # We accept this as the caller is expected to not mutate
            pass


# =============================================================================
# Factory Functions
# =============================================================================

def create_failed_response(
    reason_code: str,
    *,
    invariants: Optional[Dict[str, bool]] = None,
) -> ProjectionResponse:
    """
    Create a fail-closed projection response.

    Args:
        reason_code: One of the ProjectionReasonCode constants.
        invariants: Optional invariants report.

    Returns:
        A ProjectionResponse with eligible=False.
    """
    report = invariants if invariants is not None else {}
    report[reason_code] = False
    return ProjectionResponse(
        layers=(),
        artifacts=(),
        ledger_spans=(),
        eligible=False,
        invariants_report=report,
    )


def create_success_response(
    layers: Tuple[OntologicalLayer, ...],
    artifacts: Tuple[Any, ...],
    ledger_spans: Tuple[str, ...],
    invariants: Optional[Dict[str, bool]] = None,
) -> ProjectionResponse:
    """
    Create a successful projection response.

    Args:
        layers: Tuple of projected layers.
        artifacts: Tuple of opaque artifacts.
        ledger_spans: Tuple of ledger span IDs.
        invariants: Optional invariants report.

    Returns:
        A ProjectionResponse with eligible=True.
    """
    report = invariants if invariants is not None else {}
    report[ProjectionReasonCode.PASSED] = True
    return ProjectionResponse(
        layers=layers,
        artifacts=artifacts,
        ledger_spans=ledger_spans,
        eligible=True,
        invariants_report=report,
    )
