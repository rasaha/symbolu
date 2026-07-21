"""
Deterministic retrieval index: a lexical inverted index plus concept-vector
("semantic") scoring. No network, no learned model — fully reproducible.

Lexical score  = idf-weighted token overlap between query and unit.
Semantic score = cosine similarity over concept-count vectors (concept lexicon in
                 chunking.py). This is a deterministic stand-in for dense retrieval.
"""

from __future__ import annotations

import math
from collections import Counter
from dataclasses import dataclass, field
from typing import Dict, List, Mapping, Tuple

from truth_assurance_pipeline.tap_e2_trusted_retrieval.chunking import (
    concepts_of, tokenize,
)
from truth_assurance_pipeline.tap_e2_trusted_retrieval.evidence_unit import EvidenceUnit


@dataclass
class RetrievalIndex:
    units: Tuple[EvidenceUnit, ...]
    _tokens: Dict[str, List[str]] = field(default_factory=dict)
    _concepts: Dict[str, Counter] = field(default_factory=dict)
    _df: Counter = field(default_factory=Counter)
    _cdf: Counter = field(default_factory=Counter)     # concept document frequency
    _postings: Dict[str, set] = field(default_factory=dict)
    _n: int = 0

    @classmethod
    def build(cls, units: Tuple[EvidenceUnit, ...]) -> "RetrievalIndex":
        idx = cls(units=tuple(units))
        idx._n = len(units)
        for u in units:
            toks = tokenize(u.text)
            idx._tokens[u.unit_id] = toks
            cvec = Counter(concepts_of(toks))
            idx._concepts[u.unit_id] = cvec
            for t in set(toks):
                idx._df[t] += 1
                idx._postings.setdefault(t, set()).add(u.unit_id)
            for c in cvec:
                idx._cdf[c] += 1
        return idx

    def _idf(self, term: str) -> float:
        df = self._df.get(term, 0)
        return math.log((1 + self._n) / (1 + df)) + 1.0

    def _cidf(self, concept: str) -> float:
        # concept-idf: a broad concept present in many units carries little
        # discriminative weight, so unrelated queries sharing only a common concept
        # do not spuriously match (this is what lets missing-evidence gaps surface).
        df = self._cdf.get(concept, 0)
        return math.log((1 + self._n) / (1 + df)) + 0.5

    def by_id(self, unit_id: str) -> EvidenceUnit:
        for u in self.units:
            if u.unit_id == unit_id:
                return u
        raise KeyError(unit_id)

    def lexical_candidates(self, query_terms: Tuple[str, ...]) -> Dict[str, float]:
        scores: Dict[str, float] = {}
        qset = set(query_terms)
        for t in qset:
            for uid in self._postings.get(t, ()):  # only units containing the term
                scores[uid] = scores.get(uid, 0.0) + self._idf(t)
        # normalize by query length so scores are comparable across queries
        denom = sum(self._idf(t) for t in qset) or 1.0
        return {uid: s / denom for uid, s in scores.items()}

    def semantic_candidates(self, query_concepts: Tuple[str, ...]) -> Dict[str, float]:
        raw = Counter(query_concepts)
        if not raw:
            return {}
        # idf-weighted concept vectors (cosine)
        qv = {c: raw[c] * self._cidf(c) for c in raw}
        qnorm = math.sqrt(sum(v * v for v in qv.values()))
        out: Dict[str, float] = {}
        for uid, uraw in self._concepts.items():
            if not uraw:
                continue
            uv = {c: uraw[c] * self._cidf(c) for c in uraw}
            dot = sum(qv.get(c, 0.0) * uv.get(c, 0.0) for c in qv)
            if dot <= 0:
                continue
            unorm = math.sqrt(sum(v * v for v in uv.values()))
            out[uid] = dot / (qnorm * unorm)
        return out

    def lexical_score(self, query_terms: Tuple[str, ...], unit_id: str) -> float:
        return self.lexical_candidates(query_terms).get(unit_id, 0.0)

    def tokens_of(self, unit_id: str) -> List[str]:
        return self._tokens.get(unit_id, [])
