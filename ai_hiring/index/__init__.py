"""Deterministic evidence search index (Phase 2)."""

from __future__ import annotations

from .in_memory import InMemoryEvidenceIndex
from .interfaces import EvidenceIndex, IndexEntry, SearchQuery
from .search import matches, tokenize

__all__ = [
    "EvidenceIndex",
    "IndexEntry",
    "SearchQuery",
    "InMemoryEvidenceIndex",
    "matches",
    "tokenize",
]
