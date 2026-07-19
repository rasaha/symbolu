#!/usr/bin/env python3
"""
BM25Extractor — classical lexical retrieval (Okapi BM25), pure-Python.

Scores every sentence against the question with standard BM25 and selects the
top-K as evidence. Represents keyword-search-quality retrieval that is
query-conditioned (unlike the fixed-keyword baseline).
"""

from __future__ import annotations

import math
from collections import Counter

from agentic.hybrid_handover.schema import Corpus

from .base import BaseRetrieverExtractor, iter_sentences, tokens

_K1 = 1.5
_B = 0.75


class BM25Extractor(BaseRetrieverExtractor):
    name = "bm25"
    mode = "Okapi BM25 lexical retrieval (pure-python)"

    def rank(self, question: str, corpus: Corpus):
        sents = list(iter_sentences(corpus))
        docs_tok = [tokens(s) for _, s, _ in sents]
        N = len(docs_tok)
        if N == 0:
            return []
        avgdl = sum(len(d) for d in docs_tok) / N
        df = Counter()
        for d in docs_tok:
            for term in set(d):
                df[term] += 1

        def idf(term: str) -> float:
            n = df.get(term, 0)
            return math.log(1 + (N - n + 0.5) / (n + 0.5))

        q_terms = tokens(question)
        ranked = []
        for (doc, sent, start), dtok in zip(sents, docs_tok):
            tf = Counter(dtok)
            dl = len(dtok)
            score = 0.0
            for t in q_terms:
                if t not in tf:
                    continue
                f = tf[t]
                denom = f + _K1 * (1 - _B + _B * dl / avgdl) if avgdl else 1.0
                score += idf(t) * (f * (_K1 + 1)) / denom
            ranked.append((score, doc, sent, start))
        return ranked
