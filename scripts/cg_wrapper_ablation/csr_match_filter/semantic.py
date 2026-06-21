"""semantic.py — the NON-PHONEMIC S firewall (external semantic coherence).

S compares the *meaning* of a term to the *meaning* of a domain using definitions/keywords (or, in
production, embeddings/RAG metadata). It NEVER reads phonemes. This is the firewall that stops
phoneme-only meaning claims: a term whose sound realizes a lane strongly (high C/R) is still vetoed
here if external meaning disagrees.

Default backend = lexical overlap (Jaccard over gloss/keyword tokens), with an optional curated prior
(stand-in for an embedding model) for clean demos. Swap in a real embedder by passing `embed_fn`.
"""

from __future__ import annotations

import re
from typing import Callable, Dict, Optional, Tuple

from .registry import CURATED_SEMANTIC, DOMAIN_TEMPLATES, TERM_GLOSSES

_WORD = re.compile(r"[a-z]+")
# tiny stoplist so generic glue words don't inflate overlap
_STOP = {"a", "an", "the", "and", "or", "of", "to", "who", "with", "in", "is", "for"}


def _tokens(text: str) -> set:
    return {w for w in _WORD.findall((text or "").lower()) if w not in _STOP and len(w) > 2}


class SemanticCoherenceAdapter:
    """Pluggable non-phonemic semantic backend. similarity(term, domain) -> [0,1]."""

    def __init__(self,
                 term_glosses: Optional[Dict[str, str]] = None,
                 curated: Optional[Dict[Tuple[str, str], float]] = None,
                 embed_fn: Optional[Callable[[str], "object"]] = None,
                 use_curated: bool = True):
        self.term_glosses = dict(TERM_GLOSSES if term_glosses is None else term_glosses)
        self.curated = dict(CURATED_SEMANTIC if curated is None else curated)
        self.embed_fn = embed_fn          # optional: text -> vector with __matmul__/norm
        self.use_curated = use_curated

    def definition(self, term: str) -> str:
        return self.term_glosses.get(term.lower(), term)

    def domain_definition(self, domain: str) -> str:
        t = DOMAIN_TEMPLATES.get(domain)
        return t.definition if t else domain

    def _lexical(self, term: str, domain: str) -> float:
        a, b = _tokens(self.definition(term)), _tokens(self.domain_definition(domain))
        if not a or not b:
            return 0.0
        inter = len(a & b)
        # overlap coefficient (forgiving of definition-length mismatch), still purely meaning-based
        return inter / min(len(a), len(b))

    def _embedding(self, term: str, domain: str) -> float:
        import numpy as np
        va = np.asarray(self.embed_fn(self.definition(term)), dtype=float)
        vb = np.asarray(self.embed_fn(self.domain_definition(domain)), dtype=float)
        d = (np.linalg.norm(va) * np.linalg.norm(vb)) or 1.0
        return float(np.clip(va @ vb / d, 0.0, 1.0))

    def similarity(self, term: str, domain: str) -> float:
        key = (term.lower(), domain)
        if self.use_curated and key in self.curated:
            return float(self.curated[key])
        if self.embed_fn is not None:
            return self._embedding(term, domain)
        return float(self._lexical(term, domain))


_DEFAULT = SemanticCoherenceAdapter()


def compute_semantic_coherence(term: str, domain: str,
                               adapter: Optional[SemanticCoherenceAdapter] = None) -> float:
    return (adapter or _DEFAULT).similarity(term, domain)
