#!/usr/bin/env python3
"""Registry of baseline extractors. Add a factory here to include an extractor in
the comparison; nothing else changes."""

from __future__ import annotations

from .bm25 import BM25Extractor
from .embedding import EmbeddingExtractor
from .hybrid import HybridRetriever
from .keyword import KeywordExtractor

BASELINES = {
    "keyword": KeywordExtractor,
    "bm25": BM25Extractor,
    "embedding": EmbeddingExtractor,
    "hybrid_retriever": HybridRetriever,
}

ORDER = ["keyword", "bm25", "embedding", "hybrid_retriever"]


def build(name: str):
    return BASELINES[name]()
