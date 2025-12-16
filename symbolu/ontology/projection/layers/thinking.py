"""
Thinking Layer Projection
=========================

Structural-only projection for the THINKING ontological layer.

Output:
    - DerivationChain artifact: tuple of hashes
    - No semantics, no text
"""

from typing import Any, Tuple

from symbolu.ontology.projection.api_models import (
    FrozenSnapshot,
    ProjectionRequest,
)
from symbolu.ontology.projection.engine import _stable_hash


def project_thinking(
    snapshot: FrozenSnapshot,
    request: ProjectionRequest
) -> Tuple[Tuple[Any, ...], Tuple[Any, ...]]:
    """
    Project onto the THINKING layer.

    Produces a DerivationChain artifact as a tuple of hashes:
        - snapshot.content_hash
        - stable_hash(input_ref)
        - stable_hash(request.options)

    Args:
        snapshot: Frozen snapshot containing payload
        request: Projection request

    Returns:
        Tuple of (artifacts, ledger_spans)
    """
    # Compute derivation chain hashes
    input_ref_hash = _stable_hash({
        "kind": request.input_ref.kind.value,
        "object_id": request.input_ref.object_id
    })

    options_hash = _stable_hash({
        "include_ledger": request.options.include_ledger,
        "max_artifacts": request.options.max_artifacts,
        "output_mode": request.options.output_mode.value,
        "strictness": request.options.strictness.value
    })

    # DerivationChain artifact: tuple of three hashes
    derivation_chain = (
        snapshot.content_hash,
        input_ref_hash,
        options_hash
    )

    # Artifacts tuple containing the derivation chain
    artifacts = (derivation_chain,)

    # Ledger spans: record the layer and profile
    ledger_spans = (
        (request.layer.value, request.projection_profile.value),
    )

    return (artifacts, ledger_spans)
