"""Null feature streams the Symbol-U vector `U` must beat to earn its place.

Every null is a feature matrix aligned row-for-row with the items, the same way
`U` is. The complementarity claim (`E + U` beats `E`) is only meaningful if it
ALSO beats `E + null` for every relevant null below — otherwise the gain came
from generic added capacity, surface form, or raw phonology, not from the
Symbol-U *ontology*.

Nulls (per SYMBOL_U_RESEARCH_STRATEGY.md §7):
- ``shuffled_U``        : `U` rows permuted across items — same marginal stats,
                          broken item↔U correspondence. Tests content vs capacity.
- ``random``            : Gaussian noise, matched dim. Generic fusion capacity.
- ``surface``           : length, vowel/consonant counts, char-bigram hashing.
                          The spelling/orthography confound.
- ``phonological``      : SoundClass histogram only — raw sound structure WITHOUT
                          the Vritti ontology mapping. Isolates "ontology vs sound".

All deterministic given a seed.
"""
from __future__ import annotations

import hashlib
from typing import List, Sequence

import numpy as np

from .symbolu_engine import SymbolUEngine, SOUNDCLASS_ORDER, char_sound_class


def shuffled_U(U: np.ndarray, seed: int = 0) -> np.ndarray:
    rng = np.random.default_rng(seed)
    perm = rng.permutation(len(U))
    return U[perm].copy()


def random_features(n: int, dim: int, seed: int = 0) -> np.ndarray:
    rng = np.random.default_rng(seed)
    return rng.standard_normal((n, dim))


def surface_features(texts: Sequence[str], n_buckets: int = 16) -> np.ndarray:
    """Length, vowel count, consonant count, + char-bigram hashing buckets."""
    vowels = set("aeiou")
    rows: List[np.ndarray] = []
    for t in texts:
        s = "".join(c for c in t.lower() if c.isalpha())
        nv = sum(c in vowels for c in s)
        nc = len(s) - nv
        buckets = np.zeros(n_buckets, dtype=np.float64)
        pad = f"#{s}#"
        for i in range(len(pad) - 1):
            bg = pad[i : i + 2]
            h = int(hashlib.md5(bg.encode()).hexdigest(), 16)
            buckets[h % n_buckets] += 1.0
        if buckets.sum() > 0:
            buckets /= buckets.sum()
        rows.append(np.concatenate([[len(s), nv, nc], buckets]))
    return np.stack(rows)


def phonological_features(texts: Sequence[str]) -> np.ndarray:
    """SoundClass histogram per item — raw phonology, no Vritti ontology."""
    rows: List[np.ndarray] = []
    idx = {s: i for i, s in enumerate(SOUNDCLASS_ORDER)}
    for t in texts:
        h = np.zeros(len(SOUNDCLASS_ORDER), dtype=np.float64)
        letters = [c for c in t.lower() if c.isalpha()]
        for c in letters:
            cls = char_sound_class(c)
            if cls in idx:
                h[idx[cls]] += 1.0
        if h.sum() > 0:
            h /= h.sum()
        rows.append(h)
    return np.stack(rows)


def all_nulls(texts: Sequence[str], U: np.ndarray, seed: int = 0) -> dict:
    """Return every null aligned with `texts`/`U`, keyed by name."""
    n = len(texts)
    return {
        "shuffled_U": shuffled_U(U, seed=seed),
        "random": random_features(n, U.shape[1], seed=seed),
        "surface": surface_features(texts),
        "phonological": phonological_features(texts),
    }


def symbolu_matrix(texts: Sequence[str], engine: SymbolUEngine | None = None) -> np.ndarray:
    eng = engine or SymbolUEngine()
    return np.stack([np.asarray(eng.encode(t), dtype=np.float64) for t in texts])
