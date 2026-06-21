"""semantic.py — the NON-PHONEMIC S firewall (external semantic coherence).

S compares the *meaning* of a term to the *meaning* of a domain. It NEVER reads phonemes — it is the
firewall that stops phoneme-only meaning claims: a term whose sound realizes a lane strongly (high
C/R) is still vetoed here if external meaning disagrees.

Scalable design — no per-word dictionary required:
  * term meaning text comes from a `definition_provider(term) -> text` (dictionary/KB/WordNet/LLM).
    If none is given, the raw term text is used. Per-term curated glosses are NOT required.
  * similarity is computed by `embed_fn` (a real sentence embedder) when provided, else by a built-in
    deterministic offline embedder (hashed, stemmed bag-of-words) so unknown terms are still scored
    without over-rejection, else (explicitly) by lexical overlap.
  * curated (term,domain) scores and curated glosses are DEMO/TEST fixtures only — opt-in via
    `use_curated`, never part of the production path.
"""

from __future__ import annotations

import hashlib
import re
from typing import Callable, Dict, Optional, Tuple

from .registry import DEMO_CURATED_SEMANTIC, DEMO_TERM_GLOSSES, DOMAIN_TEMPLATES

_WORD = re.compile(r"[a-z]+")
# tiny stoplist so generic glue words don't inflate overlap
_STOP = {"a", "an", "the", "and", "or", "of", "to", "who", "with", "in", "is", "for", "by", "on"}
_EMBED_DIM = 512


def _tokens(text: str) -> set:
    return {w for w in _WORD.findall((text or "").lower()) if w not in _STOP and len(w) > 2}


def _stems(text: str):
    """Crude prefix stems so morphological variants align (diagnoses/diagnosis -> 'diag')."""
    return [w[:4] for w in _tokens(text)]


def hashing_embed(text: str, dim: int = _EMBED_DIM):
    """Deterministic offline embedding: signed feature-hash of stemmed tokens.

    Non-phonemic (operates on meaning words), deterministic across runs (hashlib, not builtin hash),
    and dependency-light. A weak stand-in for a real sentence embedder — good enough to avoid the
    automatic over-rejection that pure exact-token overlap causes, and to score unknown terms.
    """
    import numpy as np
    vec = np.zeros(dim, dtype=float)
    for s in _stems(text):
        h = int(hashlib.md5(s.encode("utf-8")).hexdigest(), 16)
        sign = 1.0 if ((h >> 8) & 1) else -1.0
        vec[h % dim] += sign
    return vec


def _cosine_text(embed, a: str, b: str) -> float:
    import numpy as np
    va, vb = np.asarray(embed(a), dtype=float), np.asarray(embed(b), dtype=float)
    den = (np.linalg.norm(va) * np.linalg.norm(vb)) or 1.0
    return float(np.clip(va @ vb / den, 0.0, 1.0))


class SemanticCoherenceAdapter:
    """Pluggable non-phonemic semantic backend. similarity(term, domain) -> [0,1].

    Production: pass `embed_fn` (real sentence embedder) and optionally `definition_provider`.
    Offline/CPU: leave `embed_fn=None` -> built-in deterministic hashing embedder (default), or set
    `offline_backend="lexical"` for pure token overlap. Curated tables are opt-in demo fixtures.
    """

    def __init__(self,
                 embed_fn: Optional[Callable[[str], "object"]] = None,
                 definition_provider: Optional[Callable[[str], str]] = None,
                 domain_definitions: Optional[Dict[str, str]] = None,
                 term_glosses: Optional[Dict[str, str]] = None,
                 curated: Optional[Dict[Tuple[str, str], float]] = None,
                 use_curated: bool = False,
                 offline_backend: str = "hashing"):
        self.embed_fn = embed_fn
        self.definition_provider = definition_provider
        self.domain_definitions = dict(domain_definitions or {})
        self.term_glosses = dict(term_glosses or {})       # DEMO fixture; empty in production
        self.curated = dict(curated or {})                 # DEMO/TEST fixture
        self.use_curated = use_curated
        if offline_backend not in ("hashing", "lexical"):
            raise ValueError("offline_backend must be 'hashing' or 'lexical'")
        self.offline_backend = offline_backend

    # --- meaning text (no per-term dictionary required) -------------------------------------------
    def definition(self, term: str) -> str:
        if self.definition_provider is not None:
            try:
                d = self.definition_provider(term)
                if d:
                    return d
            except Exception:
                pass
        if term.lower() in self.term_glosses:              # demo fixture, only if explicitly supplied
            return self.term_glosses[term.lower()]
        return term                                        # fall back to the raw term text

    def domain_definition(self, domain: str) -> str:
        if domain in self.domain_definitions:
            return self.domain_definitions[domain]
        t = DOMAIN_TEMPLATES.get(domain)
        return t.definition if t else domain

    # --- backends ---------------------------------------------------------------------------------
    def _lexical(self, term: str, domain: str) -> float:
        a, b = _tokens(self.definition(term)), _tokens(self.domain_definition(domain))
        if not a or not b:
            return 0.0
        return len(a & b) / min(len(a), len(b))            # overlap coefficient

    def similarity(self, term: str, domain: str) -> float:
        key = (term.lower(), domain)
        if self.use_curated and key in self.curated:       # opt-in demo/test override
            return float(self.curated[key])
        td, dd = self.definition(term), self.domain_definition(domain)
        if self.embed_fn is not None:                      # production: real embeddings
            return _cosine_text(self.embed_fn, td, dd)
        if self.offline_backend == "hashing":              # default offline: deterministic embedding
            return _cosine_text(hashing_embed, td, dd)
        return float(self._lexical(term, domain))          # explicit lexical fallback


# default production-style adapter: deterministic offline embedding, no curation, raw-term definitions
_DEFAULT = SemanticCoherenceAdapter()


def make_demo_adapter() -> "SemanticCoherenceAdapter":
    """Adapter wired with the DEMO fixtures (curated glosses + curated S) for the canonical example."""
    return SemanticCoherenceAdapter(term_glosses=DEMO_TERM_GLOSSES, curated=DEMO_CURATED_SEMANTIC,
                                    use_curated=True)


def compute_semantic_coherence(term: str, domain: str,
                               adapter: Optional[SemanticCoherenceAdapter] = None) -> float:
    return (adapter or _DEFAULT).similarity(term, domain)
