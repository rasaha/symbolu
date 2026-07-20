#!/usr/bin/env python3
"""
HybridRetriever — lexical (BM25) + semantic (embedding) fusion.

Represents today's production-style RAG retrieval, which typically combines a
sparse lexical signal with a dense semantic one. Scores are min-max normalised to
[0, 1] within each channel and summed. Inherits the same fallback caveat as
EmbeddingExtractor (no neural model available in this environment).
"""

from __future__ import annotations

from agentic.hybrid_handover.schema import Corpus

from .base import BaseRetrieverExtractor
from .bm25 import BM25Extractor
from .embedding import EmbeddingExtractor


def _normalise(scored):
    if not scored:
        return {}
    vals = [s for s, *_ in scored]
    lo, hi = min(vals), max(vals)
    rng = hi - lo
    out = {}
    for score, doc, sent, start in scored:
        out[(doc.doc_id, start)] = 0.0 if rng == 0 else (score - lo) / rng
    return out


class HybridRetriever(BaseRetrieverExtractor):
    name = "hybrid_retriever"
    mode = "BM25 + char-3gram fusion (lexical+semantic RAG-style; fallback embedding)"

    def __init__(self):
        self._bm25 = BM25Extractor()
        self._emb = EmbeddingExtractor()

    def rank(self, question: str, corpus: Corpus):
        bm = self._bm25.rank(question, corpus)
        em = self._emb.rank(question, corpus)
        bmn = _normalise(bm)
        emn = _normalise(em)
        ranked = []
        for score, doc, sent, start in bm:  # bm and em share the same sentence set
            key = (doc.doc_id, start)
            fused = bmn.get(key, 0.0) + emn.get(key, 0.0)
            ranked.append((fused, doc, sent, start))
        return ranked
