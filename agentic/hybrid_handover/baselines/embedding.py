#!/usr/bin/env python3
"""
EmbeddingExtractor — dense semantic retrieval by nearest-neighbour cosine.

HONEST SCOPE NOTE: no neural sentence-embedding model (sentence-transformers) and
no numpy/scikit-learn were available in this environment, and model download was
not attempted. This baseline therefore runs in a **character-n-gram fallback**
mode: each sentence and the question are vectorised as character-3-gram term
frequencies and ranked by cosine similarity. This is a *lexical proxy* for a
dense retriever — it captures subword overlap (terminate/termination) and fuzzy
matches, but NOT true synonymy (e.g. exit ≈ terminate). Consequently these
numbers **understate** what a real neural embedding model would achieve; treat
Embedding results here as a conservative lower bound, not a ceiling.

The interface is identical to a true dense retriever; substituting a real model
requires only replacing `vectorise`.
"""

from __future__ import annotations

from agentic.hybrid_handover.schema import Corpus

from .base import BaseRetrieverExtractor, char_ngrams, cosine, iter_sentences


class EmbeddingExtractor(BaseRetrieverExtractor):
    name = "embedding"
    mode = "char-3gram cosine fallback (NO neural model available — lower bound)"

    def vectorise(self, text: str):
        return char_ngrams(text, n=3)

    def rank(self, question: str, corpus: Corpus):
        qv = self.vectorise(question)
        ranked = []
        for doc, sent, start in iter_sentences(corpus):
            ranked.append((cosine(qv, self.vectorise(sent)), doc, sent, start))
        return ranked
