"""Search service — deterministic evidence retrieval only.

Thin service over the evidence index repository. Supports retrieval by
candidate, role, assessment, evidence id, chunk id, assessment type, document
type, filename, keyword, and metadata. No semantic search, embeddings, or
ranking — results are returned in a deterministic order.
"""

from __future__ import annotations

from typing import Optional

from ..index.interfaces import IndexEntry, SearchQuery
from ..repositories.evidence_index_repository import EvidenceIndexRepository


class SearchService:
    def __init__(self, index_repository: EvidenceIndexRepository) -> None:
        self._index = index_repository

    def search(self, query: SearchQuery) -> tuple[IndexEntry, ...]:
        return self._index.search(query)

    def by_candidate(self, candidate_id: str) -> tuple[IndexEntry, ...]:
        return self._index.search(SearchQuery(candidate_id=candidate_id))

    def by_assessment(self, assessment_item_id: str) -> tuple[IndexEntry, ...]:
        return self._index.search(SearchQuery(assessment_item_id=assessment_item_id))

    def by_evidence(self, evidence_id: str) -> tuple[IndexEntry, ...]:
        return self._index.search(SearchQuery(evidence_id=evidence_id))

    def by_chunk(self, chunk_id: str) -> Optional[IndexEntry]:
        return self._index.get_by_chunk(chunk_id)

    def keyword(self, keyword: str) -> tuple[IndexEntry, ...]:
        return self._index.search(SearchQuery(keyword=keyword))
