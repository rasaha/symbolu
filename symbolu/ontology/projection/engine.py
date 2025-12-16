"""
Ontological Projection Engine
=============================

Main dispatcher for ontological projections.

Hard Constraints:
    - Read-only: never mutates input objects
    - Deterministic: same input => identical output
    - Non-semantic: no NLP, no embeddings
    - Fail-closed: any error => eligible=False
"""

import hashlib
import json
from typing import Any, Tuple

from symbolu.ontology.projection.api_models import (
    FrozenSnapshot,
    ProjectionRequest,
    ProjectionResponse,
    InvariantsReport,
    OntologicalLayer,
    ReasonCode,
)
from symbolu.ontology.projection.validators import (
    validate_request,
    validate_response_non_textual,
    run_invariant_checks,
    fail_closed_response,
)


# =============================================================================
# Deterministic Hashing
# =============================================================================

def _stable_hash(obj: Any) -> str:
    """
    Compute a stable SHA256 hash of an object.

    For JSONable objects: uses json.dumps with sorted keys.
    For non-JSONable: uses repr() (must be stable for test types).

    Args:
        obj: Object to hash

    Returns:
        First 32 chars of lowercase hex SHA256 hash
    """
    try:
        # Try JSON serialization first (stable for JSONable objects)
        serialized = json.dumps(
            obj,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=True,
            default=_json_default
        )
    except (TypeError, ValueError):
        # Fall back to repr for non-JSONable objects
        serialized = repr(obj)

    return hashlib.sha256(serialized.encode("utf-8")).hexdigest()[:32]


def _json_default(obj: Any) -> Any:
    """
    Default JSON serializer for non-standard types.

    Args:
        obj: Object to serialize

    Returns:
        Serializable representation

    Raises:
        TypeError: If object cannot be serialized
    """
    if hasattr(obj, "value"):
        # Enum values
        return obj.value
    if hasattr(obj, "__dataclass_fields__"):
        # Dataclass - convert to dict
        return {
            k: getattr(obj, k)
            for k in obj.__dataclass_fields__.keys()
        }
    raise TypeError(f"Object of type {type(obj).__name__} is not JSON serializable")


def compute_projection_id(
    snapshot: FrozenSnapshot,
    request: ProjectionRequest
) -> str:
    """
    Compute deterministic projection ID.

    Formula: sha256(snapshot_id + layer + input_ref.kind + input_ref.object_id +
                    profile + options + snapshot.content_hash)[:32]

    Args:
        snapshot: Frozen snapshot
        request: Projection request

    Returns:
        32-char lowercase hex projection ID
    """
    components = (
        request.snapshot_id,
        str(request.layer.value),
        request.input_ref.kind.value,
        request.input_ref.object_id,
        request.projection_profile.value,
        request.options.output_mode.value,
        request.options.strictness.value,
        str(request.options.include_ledger),
        str(request.options.max_artifacts),
        snapshot.content_hash,
    )
    combined = "|".join(components)
    return hashlib.sha256(combined.encode("utf-8")).hexdigest()[:32]


# =============================================================================
# Layer Dispatching
# =============================================================================

def _dispatch_layer(
    layer: OntologicalLayer,
    snapshot: FrozenSnapshot,
    request: ProjectionRequest
) -> Tuple[Tuple[Any, ...], Tuple[Any, ...]]:
    """
    Dispatch projection to appropriate layer handler.

    Args:
        layer: Ontological layer to project
        snapshot: Frozen snapshot
        request: Projection request

    Returns:
        Tuple of (artifacts, ledger_spans)

    Raises:
        NotImplementedError: If layer is not implemented
    """
    if layer == OntologicalLayer.THINKING:
        from symbolu.ontology.projection.layers.thinking import project_thinking
        return project_thinking(snapshot, request)

    elif layer == OntologicalLayer.META_OBSERVING:
        from symbolu.ontology.projection.layers.meta_observing import project_meta_observing
        return project_meta_observing(snapshot, request)

    elif layer == OntologicalLayer.UNIFYING:
        from symbolu.ontology.projection.layers.unifying import project_unifying
        return project_unifying(snapshot, request)

    else:
        raise NotImplementedError(f"Layer {layer.name} not implemented")


# =============================================================================
# Main Entry Point
# =============================================================================

def run_projection(
    snapshot: FrozenSnapshot,
    request: ProjectionRequest
) -> ProjectionResponse:
    """
    Execute an ontological projection.

    Flow:
        1. Compute deterministic projection_id
        2. Validate request schema constraints
        3. Run pre-projection invariant checks
        4. Dispatch to layer handler
        5. Run post-projection validation
        6. Return response (fail-closed on any error)

    Args:
        snapshot: Frozen snapshot containing payload
        request: Projection request

    Returns:
        ProjectionResponse (always returns, never raises)
    """
    # Always compute projection_id first (even for failures)
    projection_id = compute_projection_id(snapshot, request)

    # Validate request
    request_valid, request_reasons = validate_request(request)
    if not request_valid:
        return fail_closed_response(
            projection_id=projection_id,
            snapshot_id=request.snapshot_id,
            layer=request.layer,
            input_ref=request.input_ref,
            reason_codes=tuple(request_reasons)
        )

    # Run pre-projection invariant checks
    pre_report = run_invariant_checks()
    if not pre_report.passed:
        return fail_closed_response(
            projection_id=projection_id,
            snapshot_id=request.snapshot_id,
            layer=request.layer,
            input_ref=request.input_ref,
            reason_codes=pre_report.reason_codes
        )

    # Dispatch to layer
    try:
        artifacts, ledger_spans = _dispatch_layer(
            request.layer,
            snapshot,
            request
        )
    except NotImplementedError:
        return fail_closed_response(
            projection_id=projection_id,
            snapshot_id=request.snapshot_id,
            layer=request.layer,
            input_ref=request.input_ref,
            reason_codes=(ReasonCode.LAYER_NOT_IMPLEMENTED,)
        )
    except Exception:
        return fail_closed_response(
            projection_id=projection_id,
            snapshot_id=request.snapshot_id,
            layer=request.layer,
            input_ref=request.input_ref,
            reason_codes=(ReasonCode.EXCEPTION_BLOCKED,)
        )

    # Ensure artifacts is tuple
    if not isinstance(artifacts, tuple):
        artifacts = tuple(artifacts) if artifacts else ()
    if not isinstance(ledger_spans, tuple):
        ledger_spans = tuple(ledger_spans) if ledger_spans else ()

    # Apply max_artifacts limit
    if len(artifacts) > request.options.max_artifacts:
        artifacts = artifacts[:request.options.max_artifacts]

    # Build response
    response = ProjectionResponse(
        projection_id=projection_id,
        snapshot_id=request.snapshot_id,
        layer=request.layer,
        input_ref=request.input_ref,
        artifacts=artifacts,
        ledger_spans=ledger_spans if request.options.include_ledger else (),
        invariants_report=InvariantsReport(
            passed=True,
            reason_codes=(ReasonCode.PASSED,)
        ),
        eligible=True
    )

    # Validate response (post-projection)
    resp_valid, resp_reasons = validate_response_non_textual(response)
    if not resp_valid:
        return fail_closed_response(
            projection_id=projection_id,
            snapshot_id=request.snapshot_id,
            layer=request.layer,
            input_ref=request.input_ref,
            reason_codes=tuple(resp_reasons)
        )

    # Run post-projection invariant checks
    post_report = run_invariant_checks()
    if not post_report.passed:
        return fail_closed_response(
            projection_id=projection_id,
            snapshot_id=request.snapshot_id,
            layer=request.layer,
            input_ref=request.input_ref,
            reason_codes=post_report.reason_codes
        )

    return response


# Export _stable_hash for layers to use
__all__ = ["run_projection", "_stable_hash", "compute_projection_id"]
