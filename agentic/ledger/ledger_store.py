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

from typing import Iterator, Optional, Tuple

from agentic.ledger.ledger_replay_verifier import (
    MAPPING_VERSION,
    LedgerEntry,
    LedgerProjectionEntry,
    create_entry,
    create_ledger_entry,
)
from agentic.ontology.router.ontological_router_r1 import (
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


# =============================================================================
# LedgerEntryStore (Spec-Compliant)
# =============================================================================

class LedgerEntryStore:
    """
    Append-only ledger store for LedgerEntry (with hash chain).

    Methods (per specification):
        - append(entry) -> entry_id
        - get(entry_id) -> Optional[LedgerEntry]
        - head() -> Optional[LedgerEntry]
        - iter_all() -> Iterator[LedgerEntry]

    Rules:
        - Append-only
        - No deletion
        - No mutation
        - Deterministic ordering
    """

    def __init__(self) -> None:
        """Initialize an empty ledger entry store."""
        self._entries: list[LedgerEntry] = []
        self._index_by_id: dict[str, int] = {}

    def append(self, entry: LedgerEntry) -> str:
        """
        Append an entry to the ledger.

        Args:
            entry: The LedgerEntry to append.

        Returns:
            The entry_id of the appended entry.

        Raises:
            ValueError: If the entry's seq does not match expected,
                        or if prev_entry_id doesn't match head's entry_id.

        Note:
            - Entries are immutable (frozen dataclass)
            - seq must be sequential and monotonic
            - prev_entry_id must match head's entry_id (or None for first)
            - No gaps or duplicates allowed
        """
        expected_seq = len(self._entries)

        if entry.seq != expected_seq:
            raise ValueError(
                f"seq mismatch: expected {expected_seq}, got {entry.seq}"
            )

        expected_prev = self._entries[-1].entry_id if self._entries else None
        if entry.prev_entry_id != expected_prev:
            raise ValueError(
                f"prev_entry_id mismatch: expected {expected_prev}, "
                f"got {entry.prev_entry_id}"
            )

        self._entries.append(entry)
        self._index_by_id[entry.entry_id] = expected_seq

        return entry.entry_id

    def get(self, entry_id: str) -> Optional[LedgerEntry]:
        """
        Get an entry by its entry_id.

        Args:
            entry_id: The entry_id to look up.

        Returns:
            The LedgerEntry if found, None otherwise.
        """
        idx = self._index_by_id.get(entry_id)
        if idx is None:
            return None
        return self._entries[idx]

    def head(self) -> Optional[LedgerEntry]:
        """
        Get the most recent (head) entry.

        Returns:
            The last LedgerEntry if any entries exist, None otherwise.
        """
        if not self._entries:
            return None
        return self._entries[-1]

    def iter_all(self) -> Iterator[LedgerEntry]:
        """
        Iterate over all entries in order.

        Yields:
            LedgerEntry instances in sequential order.
        """
        return iter(self._entries)

    def read_all(self) -> Tuple[LedgerEntry, ...]:
        """
        Read all entries from the ledger.

        Returns:
            Tuple of all LedgerEntry instances in order.

        Note:
            Returns a tuple (immutable) to prevent external mutation.
        """
        return tuple(self._entries)

    def __len__(self) -> int:
        """Return the number of entries in the ledger."""
        return len(self._entries)


def record_ledger_entry(
    store: LedgerEntryStore,
    artifact_id: str,
    artifact_hash: str,
    phase_id: str,
    router: OntologicalLayerRouter,
    declared_hint: OntologicalLayer | None = None,
) -> LedgerEntry:
    """
    Record a projection to the ledger entry store with hash chain.

    This is a convenience function that:
        1. Projects the artifact through the R1 router
        2. Computes the span_id via LedgerAdapter
        3. Creates a LedgerEntry with computed entry_id and hash chain link
        4. Appends the entry to the store

    Args:
        store: The LedgerEntryStore to append to.
        artifact_id: Opaque artifact identifier.
        artifact_hash: Precomputed artifact hash.
        phase_id: Phase identifier.
        router: The OntologicalLayerRouter to use.
        declared_hint: Optional declared projection hint.

    Returns:
        The created and appended LedgerEntry.
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

    head_entry = store.head()
    prev_entry_id = head_entry.entry_id if head_entry else None
    seq = len(store)

    entry = create_ledger_entry(
        prev_entry_id=prev_entry_id,
        span_id=span_id,
        artifact_id=artifact_id,
        artifact_hash=artifact_hash,
        phase_id=phase_id,
        projected_layers=response.projected_layers,
        router_version=response.router_version,
        mapping_version=MAPPING_VERSION,
        seq=seq,
    )

    store.append(entry)

    return entry
