"""Ranking/retrieval scoring (MRR) + assignment-scramble null.

Scoring REQUIRES a realization: opaque canonical atoms carry no content, so they cannot be
ranked against meanings (score_opaque raises). Within a realization, the real varṇa→atom
assignment is compared to scrambled assignments. Deterministic; synthetic; no external
embeddings, no LLM, no result files written.
"""
from __future__ import annotations

import pathlib
import sys

import numpy as np

_HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(_HERE))
sys.path.insert(0, str(_HERE.parent))
import canonical as C   # noqa: E402


def _cos(a, b) -> float:
    na, nb = np.linalg.norm(a), np.linalg.norm(b)
    return float(a @ b / (na * nb)) if na > 0 and nb > 0 else 0.0


def score_opaque(seq):
    """Opaque canonical atoms cannot be scored — they have no content. A realization is required."""
    raise ValueError("cannot score opaque canonical atoms; a realization R_j is required")


def reciprocal_rank(word, words, realization, tau) -> float:
    """Reciprocal rank of the word's own meaning among all candidate meanings."""
    query = realization.render_query(C.canonical_sequence(word, tau))
    sims = [_cos(query, realization.meaning_vector(w)) for w in words]
    # rank the true meaning (deterministic tie-break by word label)
    order = sorted(range(len(words)), key=lambda i: (-sims[i], str(words[i])))
    rank = 1 + order.index(words.index(word))
    return 1.0 / rank


def mrr(words, realization, tau) -> float:
    return float(np.mean([reciprocal_rank(w, words, realization, tau) for w in words]))


def scramble_null_mrr(words, realization, tau_real, n_scram: int = 50, seed: int = 0) -> np.ndarray:
    vals = [mrr(words, realization, C.scramble_assignment(tau_real, seed=seed + s))
            for s in range(n_scram)]
    return np.array(vals)


def delta_j(words, realization, tau_real, n_scram: int = 50, seed: int = 0) -> dict:
    """Per-realization real-vs-scramble result: MRR_real, scramble mean, Δ, scramble percentile."""
    real = mrr(words, realization, tau_real)
    null = scramble_null_mrr(words, realization, tau_real, n_scram=n_scram, seed=seed)
    return {"realization": realization.name,
            "mrr_real": real,
            "mrr_scram_mean": float(null.mean()),
            "delta": real - float(null.mean()),
            "scramble_pct": float((null < real).mean())}
