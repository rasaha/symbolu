"""
Determinism Attestation for Ontological Projection Engine
==========================================================

Tools for attesting that projections are deterministic.

Hard Constraints:
    - No time usage
    - No randomness
    - Run multiple times and verify identical outputs
"""

import hashlib
from typing import Tuple

from symbolu.ontology.projection.api_models import (
    FrozenSnapshot,
    ProjectionRequest,
)
from symbolu.ontology.projection.engine import run_projection


def attest_determinism(
    snapshot: FrozenSnapshot,
    request: ProjectionRequest,
    runs: int = 50
) -> Tuple[bool, str, Tuple[str, ...]]:
    """
    Attest that a projection is deterministic.

    Runs the projection multiple times and verifies:
        1. All projection_ids are identical
        2. All repr(response) are identical

    Args:
        snapshot: Frozen snapshot for projection
        request: Projection request
        runs: Number of runs to perform (default 50)

    Returns:
        Tuple of:
            - ok: bool indicating if all runs were identical
            - attestation_hash: hash of the first response repr
            - run_hashes: tuple of hashes for each run
    """
    if runs < 1:
        runs = 1

    responses = []
    run_hashes = []

    for _ in range(runs):
        response = run_projection(snapshot, request)
        response_repr = repr(response)
        response_hash = hashlib.sha256(response_repr.encode("utf-8")).hexdigest()[:32]
        responses.append(response)
        run_hashes.append(response_hash)

    # Check all projection_ids are identical
    first_id = responses[0].projection_id
    ids_identical = all(r.projection_id == first_id for r in responses)

    # Check all repr are identical
    first_hash = run_hashes[0]
    reprs_identical = all(h == first_hash for h in run_hashes)

    ok = ids_identical and reprs_identical
    attestation_hash = first_hash

    return (ok, attestation_hash, tuple(run_hashes))
