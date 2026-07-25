"""Deterministic search matching and tokenization.

Keyword search is exact-token match over a deterministically tokenized text
(lowercase, split on non-alphanumeric). There is no stemming, ranking, or
semantic similarity — retrieval is fully reproducible.
"""

from __future__ import annotations

import re

from .interfaces import IndexEntry, SearchQuery

_TOKEN_RE = re.compile(r"[a-z0-9]+")


def tokenize(text: str) -> frozenset[str]:
    """Lowercase, split on non-alphanumeric; return the distinct token set."""
    return frozenset(_TOKEN_RE.findall(text.lower()))


def matches(entry: IndexEntry, query: SearchQuery) -> bool:
    """Return True if the entry satisfies every set filter in the query (AND)."""
    checks = (
        (query.candidate_id, entry.candidate_id),
        (query.role_id, entry.role_id),
        (query.assessment_item_id, entry.assessment_item_id),
        (query.assessment_type, entry.assessment_type),
        (query.document_type, entry.document_type),
        (query.evidence_id, entry.evidence_id),
        (query.chunk_id, entry.chunk_id),
        (query.filename, entry.filename),
    )
    for wanted, actual in checks:
        if wanted is not None and wanted != actual:
            return False

    if query.keyword is not None:
        wanted_tokens = tokenize(query.keyword)
        if not wanted_tokens or not wanted_tokens.issubset(entry.keywords):
            return False

    for key, value in query.metadata.items():
        if entry.metadata.get(key) != value:
            return False

    return True


def sort_key(entry: IndexEntry) -> tuple[str, int, int]:
    """Deterministic ordering: evidence_id, version, chunk_index."""
    return (entry.evidence_id, entry.version, entry.chunk_index)
