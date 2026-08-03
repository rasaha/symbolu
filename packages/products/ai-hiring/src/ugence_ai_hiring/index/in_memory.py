"""In-memory deterministic evidence index."""

from __future__ import annotations

from typing import Optional

from .interfaces import IndexEntry, SearchQuery
from .search import matches, sort_key


class InMemoryEvidenceIndex:
    """A deterministic, append-style in-memory index over evidence chunks."""

    def __init__(self) -> None:
        self._entries: list[IndexEntry] = []
        self._by_chunk: dict[str, IndexEntry] = {}

    def add(self, entry: IndexEntry) -> None:
        self._entries.append(entry)
        self._by_chunk[entry.chunk_id] = entry

    def query(self, query: SearchQuery) -> tuple[IndexEntry, ...]:
        found = [e for e in self._entries if matches(e, query)]
        return tuple(sorted(found, key=sort_key))

    def get_by_chunk(self, chunk_id: str) -> Optional[IndexEntry]:
        return self._by_chunk.get(chunk_id)

    def all(self) -> tuple[IndexEntry, ...]:
        return tuple(sorted(self._entries, key=sort_key))
