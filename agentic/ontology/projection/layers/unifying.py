"""
Unifying Layer Projection
=========================

Structural-only projection for the UNIFYING ontological layer.

Output:
    - EquivalenceClasses artifact: tuple of (rep_hash, count) pairs
    - Grouping by structural hash, no semantic analysis
"""

from typing import Any, Dict, List, Tuple

from agentic.ontology.projection.api_models import (
    FrozenSnapshot,
    ProjectionRequest,
)
from agentic.ontology.projection.engine import _stable_hash


def project_unifying(
    snapshot: FrozenSnapshot,
    request: ProjectionRequest
) -> Tuple[Tuple[Any, ...], Tuple[Any, ...]]:
    """
    Project onto the UNIFYING layer.

    Performs purely structural "equivalence" grouping:
        - If payload is a tuple/list of JSONable items, group by _stable_hash
        - Output EquivalenceClasses: tuple of (rep_hash, count_int)
        - Canonical representative = smallest rep_hash lexicographically
        - If payload not list/tuple => output empty classes

    Args:
        snapshot: Frozen snapshot containing payload
        request: Projection request

    Returns:
        Tuple of (artifacts, ledger_spans)
    """
    payload = snapshot.payload

    # Check if payload is a list or tuple
    if not isinstance(payload, (list, tuple)):
        # Not a collection - return empty equivalence classes
        artifacts = ((),)  # Empty EquivalenceClasses
        ledger_spans = ((request.layer.value, 0),)
        return (artifacts, ledger_spans)

    # Group items by stable hash
    hash_counts: Dict[str, int] = {}
    hash_items: Dict[str, List[Any]] = {}

    for item in payload:
        try:
            item_hash = _stable_hash(item)
        except Exception:
            # Non-hashable item - skip
            continue

        if item_hash not in hash_counts:
            hash_counts[item_hash] = 0
            hash_items[item_hash] = []

        hash_counts[item_hash] += 1
        hash_items[item_hash].append(item)

    # Build equivalence classes sorted by hash (lexicographic)
    sorted_hashes = sorted(hash_counts.keys())

    equivalence_classes: List[Tuple[str, int]] = []
    for h in sorted_hashes:
        equivalence_classes.append((h, hash_counts[h]))

    # EquivalenceClasses artifact
    eq_artifact = tuple(equivalence_classes)

    # Artifacts tuple
    artifacts = (eq_artifact,)

    # Ledger spans: record class count
    ledger_spans = (
        (request.layer.value, len(equivalence_classes)),
    )

    return (artifacts, ledger_spans)
