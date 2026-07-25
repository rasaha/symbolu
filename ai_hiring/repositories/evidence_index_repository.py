"""Repository-pattern adapter over the deterministic evidence index.

Wraps an :class:`~ai_hiring.index.interfaces.EvidenceIndex` so services depend on
a repository port (injected) rather than a concrete index. Retrieval is
deterministic; there is no ranking or semantic search.
"""

from __future__ import annotations

from typing import Optional, Protocol, runtime_checkable

from ..index.in_memory import InMemoryEvidenceIndex
from ..index.interfaces import EvidenceIndex, IndexEntry, SearchQuery


@runtime_checkable
class EvidenceIndexRepository(Protocol):
    def index(self, entry: IndexEntry) -> None: ...
    def search(self, query: SearchQuery) -> tuple[IndexEntry, ...]: ...
    def get_by_chunk(self, chunk_id: str) -> Optional[IndexEntry]: ...
    def all(self) -> tuple[IndexEntry, ...]: ...


class InMemoryEvidenceIndexRepository:
    """Default adapter backed by :class:`InMemoryEvidenceIndex`."""

    def __init__(self, index: Optional[EvidenceIndex] = None) -> None:
        self._index: EvidenceIndex = index or InMemoryEvidenceIndex()

    def index(self, entry: IndexEntry) -> None:
        self._index.add(entry)

    def search(self, query: SearchQuery) -> tuple[IndexEntry, ...]:
        return self._index.query(query)

    def get_by_chunk(self, chunk_id: str) -> Optional[IndexEntry]:
        return self._index.get_by_chunk(chunk_id)

    def all(self) -> tuple[IndexEntry, ...]:
        return self._index.all()
