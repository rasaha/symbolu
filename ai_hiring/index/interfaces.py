"""Search index contracts.

Deterministic, keyword-and-metadata retrieval only — no embeddings, no vector
search, no semantic ranking. An index entry is created per evidence *chunk* so
retrieval by chunk and by keyword both work; evidence-level fields are carried on
every chunk entry.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Mapping, Optional, Protocol, runtime_checkable


@dataclass(frozen=True)
class IndexEntry:
    """One indexed evidence chunk plus its evidence-level facets."""

    evidence_id: str
    version: int
    chunk_id: str
    chunk_index: int
    candidate_id: str
    role_id: str
    assessment_item_id: str
    assessment_type: str
    document_type: str
    filename: str
    keywords: frozenset[str]
    metadata: Mapping[str, str]
    text: str


@dataclass(frozen=True)
class SearchQuery:
    """Conjunctive (AND) filters. All fields optional; unset fields are ignored."""

    candidate_id: Optional[str] = None
    role_id: Optional[str] = None
    assessment_item_id: Optional[str] = None
    assessment_type: Optional[str] = None
    document_type: Optional[str] = None
    evidence_id: Optional[str] = None
    chunk_id: Optional[str] = None
    filename: Optional[str] = None
    keyword: Optional[str] = None
    metadata: Mapping[str, str] = field(default_factory=dict)


@runtime_checkable
class EvidenceIndex(Protocol):
    def add(self, entry: IndexEntry) -> None: ...
    def query(self, query: SearchQuery) -> tuple[IndexEntry, ...]: ...
    def get_by_chunk(self, chunk_id: str) -> Optional[IndexEntry]: ...
    def all(self) -> tuple[IndexEntry, ...]: ...
