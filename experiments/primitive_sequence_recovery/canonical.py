"""Canonical primitive representation — ordered tuple over OPAQUE atom IDs (P*).

The ontology (see varna_lens/CANONICAL_PRIMITIVE_REPRESENTATION.md): a word maps to an
ordered tuple of opaque primitive atoms. An "atom" is a bare identity — a plain int with
NO content: no gloss, no vector, no coordinates. Realization is elsewhere (realization.py).

Includes an order-aware, permutation-invariant opaque similarity, used to DEMONSTRATE the
relabeling-invariance theorem: real and scrambled assignments are indistinguishable here.
Synthetic only; no lexicon, no Stage A.
"""
from __future__ import annotations

import pathlib
import sys

import numpy as np

_HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(_HERE))
sys.path.insert(0, str(_HERE.parent))
from common import stats  # noqa: E402  (rng)

Atom = int  # an opaque identity — nothing but distinctness


def real_assignment(varnas, seed: int = 0) -> dict:
    """τ : varṇa -> opaque atom ID (injective). Atom IDs are 0..K-1 (relabeled by seed)."""
    g = stats.rng(seed)
    perm = g.permutation(len(varnas))
    return {v: int(perm[i]) for i, v in enumerate(varnas)}


def scramble_assignment(tau: dict, seed: int = 0) -> dict:
    """τ' = π∘τ : relabel atom IDs by a permutation π (a bijection on the atom set)."""
    atoms = sorted(set(tau.values()))
    g = stats.rng(seed)
    pi = {a: int(b) for a, b in zip(atoms, g.permutation(atoms))}
    return {v: pi[a] for v, a in tau.items()}


def canonical_sequence(word, tau: dict) -> tuple:
    """word (iterable of varṇas) -> tuple of OPAQUE atom IDs. No realization involved."""
    return tuple(tau[ch] for ch in word)


# ---- permutation-invariant opaque similarity (relabeling-invariance demonstrator) --------
def _lcs_len(a, b) -> int:
    n, m = len(a), len(b)
    dp = [[0] * (m + 1) for _ in range(n + 1)]
    for i in range(n - 1, -1, -1):
        for j in range(m - 1, -1, -1):
            dp[i][j] = dp[i + 1][j + 1] + 1 if a[i] == b[j] else max(dp[i + 1][j], dp[i][j + 1])
    return dp[0][0]


def opaque_similarity(u, v) -> float:
    """Order-aware similarity over opaque atoms: normalized LCS. Depends ONLY on the
    equality pattern of atom IDs, hence invariant under any relabeling of atoms."""
    if not u and not v:
        return 1.0
    denom = max(len(u), len(v))
    return _lcs_len(u, v) / denom if denom else 1.0


def opaque_similarity_matrix(words, tau: dict) -> np.ndarray:
    seqs = [canonical_sequence(w, tau) for w in words]
    n = len(seqs)
    M = np.zeros((n, n))
    for i in range(n):
        for j in range(n):
            M[i, j] = opaque_similarity(seqs[i], seqs[j])
    return M
