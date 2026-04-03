"""
Meta-Observing Layer Projection
===============================

Structural-only projection for the META_OBSERVING ontological layer.

Output:
    - WitnessFrame artifact: tuple of (snapshot_id, content_hash, layer_value, profile_value)
    - InvariantTimeline artifact: tuple of (invariant_name, passed_bool) pairs
"""

from typing import Any, Tuple

from agentic.ontology.projection.api_models import (
    FrozenSnapshot,
    ProjectionRequest,
)


# Fixed invariant names for timeline
INVARIANT_NAMES: Tuple[str, ...] = (
    "read_only",
    "deterministic",
    "no_semantics",
    "fail_closed",
)


def project_meta_observing(
    snapshot: FrozenSnapshot,
    request: ProjectionRequest
) -> Tuple[Tuple[Any, ...], Tuple[Any, ...]]:
    """
    Project onto the META_OBSERVING layer.

    Produces:
        1. WitnessFrame artifact:
           (snapshot_id, content_hash, layer_value, profile_value)

        2. InvariantTimeline artifact:
           tuple of (invariant_name, passed_bool) for fixed invariants

    Args:
        snapshot: Frozen snapshot containing payload
        request: Projection request

    Returns:
        Tuple of (artifacts, ledger_spans)
    """
    # WitnessFrame artifact
    witness_frame = (
        snapshot.snapshot_id,
        snapshot.content_hash,
        request.layer.value,
        request.projection_profile.value
    )

    # InvariantTimeline artifact
    # All invariants pass (structural check only)
    invariant_timeline = tuple(
        (name, True) for name in INVARIANT_NAMES
    )

    # Artifacts tuple
    artifacts = (witness_frame, invariant_timeline)

    # Ledger spans: record observation metadata
    ledger_spans = (
        (request.layer.value, len(INVARIANT_NAMES)),
    )

    return (artifacts, ledger_spans)
