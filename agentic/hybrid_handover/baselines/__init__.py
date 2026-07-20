#!/usr/bin/env python3
"""
Conventional baseline extractors for SEEB v1.0.0.

Establishes strong-conventional reference points (keyword, BM25, dense-embedding,
lexical+semantic hybrid) that every future HybridPhaseTransformer extractor is
compared against — all behind the identical frozen ``ExtractorProtocol``, all run
through the unchanged benchmark.

Nothing here modifies the frozen handover package or the SEEB benchmark.
"""

from .base import BaseRetrieverExtractor
from .bm25 import BM25Extractor
from .embedding import EmbeddingExtractor
from .hybrid import HybridRetriever
from .keyword import KeywordExtractor
from .registry import BASELINES, ORDER, build

__all__ = [
    "BaseRetrieverExtractor",
    "KeywordExtractor", "BM25Extractor", "EmbeddingExtractor", "HybridRetriever",
    "BASELINES", "ORDER", "build",
]
