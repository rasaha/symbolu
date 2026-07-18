"""Per-axis control codes for each pilot arm.

Every arm is the SAME conditional generator differing only in *what vector
encodes each axis* during training and generation. This isolates the content of
the code from the act of conditioning.

Arms / code schemes (one code vector per axis):
- ``symbolu``    : centroid of the Symbol-U vector (a chosen backend) over that
                   axis's training sentences. The hypothesis under test.
- ``random``     : a fixed seeded random vector per axis. Distinct, meaningless.
                   Tests "any distinct switch steers" (vacuous controllability).
- ``shuffled``   : the Symbol-U centroids assigned to the WRONG axes (permuted).
                   Breaks the code↔axis correspondence.
- ``sentiment``  : centroid of a known-feature vector (axis-keyword counts) — a
                   strong "known taxonomy" baseline that directly encodes the axis.
- ``relabel``    : Symbol-U centroids with their DIMENSIONS permuted by one fixed
                   permutation. A relabeling of the ontology axes. (By construction
                   an invertible basis change, so it should steer ~identically to
                   ``symbolu`` — demonstrating the specific ontology labels are a
                   basis choice the adapter is invariant to.)

The ``base`` (unconditional) and ``prompt`` (natural-language) arms use no code.
"""
from __future__ import annotations

from typing import Dict, List

import numpy as np

from .data import AXES, axis_lexicons
from symbolu_neural.complementarity_probe.backends import get_backend


def _centroids(corpus, encode, dim) -> Dict[str, np.ndarray]:
    acc = {a: np.zeros(dim) for a in AXES}
    cnt = {a: 0 for a in AXES}
    for text, axis in corpus:
        acc[axis] += np.asarray(encode(text), dtype=np.float64)
        cnt[axis] += 1
    return {a: (acc[a] / max(cnt[a], 1)) for a in AXES}


def symbolu_codes(corpus, u_backend: str = "pse_meaning") -> Dict[str, np.ndarray]:
    b = get_backend(u_backend)
    return _centroids(corpus, b.encode, b.dim)


def sentiment_codes(corpus) -> Dict[str, np.ndarray]:
    lex = axis_lexicons()
    keys = AXES

    def encode(text: str):
        toks = text.lower().split()
        v = np.zeros(len(keys))
        for i, a in enumerate(keys):
            s = set(lex[a])
            v[i] = sum(1 for t in toks if t in s)
        n = v.sum()
        return v / n if n > 0 else v

    return _centroids(corpus, encode, len(keys))


def random_codes(dim: int = 16, seed: int = 0) -> Dict[str, np.ndarray]:
    rng = np.random.default_rng(seed)
    return {a: rng.standard_normal(dim) for a in AXES}


def shuffled_codes(symbolu: Dict[str, np.ndarray], seed: int = 0) -> Dict[str, np.ndarray]:
    rng = np.random.default_rng(seed + 1)
    perm = list(AXES)
    # derangement-ish: rotate so no axis keeps its own code
    rng.shuffle(perm)
    if all(perm[i] == AXES[i] for i in range(len(AXES))):
        perm = perm[1:] + perm[:1]
    return {AXES[i]: symbolu[perm[i]] for i in range(len(AXES))}


def relabel_codes(symbolu: Dict[str, np.ndarray], seed: int = 0) -> Dict[str, np.ndarray]:
    dim = len(next(iter(symbolu.values())))
    rng = np.random.default_rng(seed + 2)
    p = rng.permutation(dim)
    return {a: symbolu[a][p] for a in AXES}


def build_all(corpus, u_backend: str = "pse_meaning", seed: int = 0):
    su = symbolu_codes(corpus, u_backend)
    return {
        "symbolu": su,
        "random": random_codes(seed=seed),
        "shuffled": shuffled_codes(su, seed=seed),
        "sentiment": sentiment_codes(corpus),
        "relabel": relabel_codes(su, seed=seed),
    }
