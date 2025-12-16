"""
Ledger Store (Append-Only)
==========================

Append-only storage for ledger projection entries.

Hard Constraints:
    - Append-only
    - No deletion
    - No mutation
    - No reordering

Allowed imports:
    - hashlib
    - json
    - dataclasses
    - typing
    - enum
"""

from __future__ import annotations

from typing import Tuple

from symbolu.ledger.ledger_replay_verifier import (
    LedgerProjectionEntry,
    create_entry,
)
from symbolu.ontology.router.ontological_router_r1 import (
    LedgerAdapter,
    LedgerSpanInput,
    OntologicalLayer,
    OntologicalLayerRouter,
    ProjectionRequest,
)


class LedgerStore:
    """
    Append-only ledger store for projection entries.

    Rules:
        - Append-only
        - No deletion
        - No mutation
        - No reordering

    The store maintains an immutable sequence of entries.
    Each new entry is assigned a sequential ledger_index.
    """

    def __init__(self) -> None:
        """Initialize an empty ledger store."""
        self._entries: list[LedgerProjectionEntry] = []

    def append(self, entry: LedgerProjectionEntry) -> None:
        """
        Append an entry to the ledger.

        Args:
            entry: The LedgerProjectionEntry to append.

        Raises:
            ValueError: If the entry's ledger_index does not match
                        the expected next index.

        Note:
            - Entries are immutable (frozen dataclass)
            - ledger_index must be sequential
            - No gaps or duplicates allowed
        """
        expected_index = len(self._entries)

        if entry.ledger_index != expected_index:
            raise ValueError(
                f"ledger_index mismatch: expected {expected_index}, "
                f"got {entry.ledger_index}"
            )

        self._entries.append(entry)

    def read_all(self) -> Tuple[LedgerProjectionEntry, ...]:
        """
        Read all entries from the ledger.

        Returns:
            Tuple of all LedgerProjectionEntry instances in order.

        Note:
            Returns a tuple (immutable) to prevent external mutation.
        """
        return tuple(self._entries)

    def __len__(self) -> int:
        """Return the number of entries in the ledger."""
        return len(self._entries)


def record_projection(
    store: LedgerStore,
    artifact_id: str,
    artifact_hash: str,
    phase_id: str,
    router: OntologicalLayerRouter,
    declared_hint: OntologicalLayer | None = None,
) -> LedgerProjectionEntry:
    """
    Record a projection to the ledger store.

    This is a convenience function that:
        1. Projects the artifact through the R1 router
        2. Computes the span_id via LedgerAdapter
        3. Creates a LedgerProjectionEntry with computed entry_hash
        4. Appends the entry to the store

    Args:
        store: The LedgerStore to append to.
        artifact_id: Opaque artifact identifier.
        artifact_hash: Precomputed artifact hash.
        phase_id: Phase identifier.
        router: The OntologicalLayerRouter to use.
        declared_hint: Optional declared projection hint.

    Returns:
        The created and appended LedgerProjectionEntry.
    """
    request = ProjectionRequest(
        artifact_id=artifact_id,
        phase_id=phase_id,
        artifact_hash=artifact_hash,
        declared_projection_hint=declared_hint,
    )

    response = router.project(request)

    span_input = LedgerSpanInput(
        artifact_hash=artifact_hash,
        phase_id=phase_id,
        projected_layers=response.projected_layers,
    )
    span_id = LedgerAdapter.generate_span_id(span_input)

    entry = create_entry(
        ledger_index=len(store),
        artifact_id=artifact_id,
        artifact_hash=artifact_hash,
        phase_id=phase_id,
        projected_layers=response.projected_layers,
        span_id=span_id,
        router_version=response.router_version,
    )

    store.append(entry)

    return entry
