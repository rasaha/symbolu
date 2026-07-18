"""Realization layer R_j — maps OPAQUE atoms to CONTENT (a rendering). NOT ontology.

Each realization supplies (a) an atom -> content-vector renderer and (b) a meaning encoder
in the same space, so a rendered primitive sequence can be compared to candidate meanings.
English-gloss concatenation is ONE realization among several (see
make_english_gloss_realization) — it is not privileged and it is not the ontology.

All synthetic and deterministic: toy random content vectors, seeded. No real glosses, no
external embeddings, no LLM.
"""
from __future__ import annotations

import pathlib
import sys

import numpy as np

_HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(_HERE))
sys.path.insert(0, str(_HERE.parent))
from common import stats           # noqa: E402
import canonical as C              # noqa: E402


class Realization:
    """A synthetic realization: atom content vectors + a meaning encoder in one space."""

    def __init__(self, name, atom_vecs: dict, meaning_vecs: dict):
        self.name = name
        self.atom_vecs = atom_vecs          # atom_id -> np.ndarray  (the atom's CONTENT)
        self.meaning_vecs = meaning_vecs     # word    -> np.ndarray  (candidate meaning embedding)

    def render_query(self, seq) -> np.ndarray:
        """Aggregate opaque-atom CONTENT into a query vector. Requires content = a realization."""
        d = next(iter(self.atom_vecs.values())).shape[0]
        v = np.zeros(d)
        for a in seq:
            v = v + self.atom_vecs[a]
        return v

    def meaning_vector(self, word) -> np.ndarray:
        return self.meaning_vecs[word]


def _rand_vecs(keys, d, g) -> dict:
    return {k: g.standard_normal(d) for k in keys}


def make_signal_realization(name, words, atoms, tau_real, d: int = 8, seed: int = 0) -> Realization:
    """PLANT signal: meaning_vec(w) = aggregate of w's REAL atoms, so real τ recovers it
    exactly and scrambled τ does not. (Synthetic fixture — proves the machinery, not the theory.)"""
    g = stats.rng(seed)
    atom_vecs = _rand_vecs(atoms, d, g)
    meaning_vecs = {}
    for w in words:
        v = np.zeros(d)
        for a in C.canonical_sequence(w, tau_real):
            v = v + atom_vecs[a]
        meaning_vecs[w] = v
    return Realization(name, atom_vecs, meaning_vecs)


def make_noise_realization(name, words, atoms, d: int = 8, seed: int = 0) -> Realization:
    """NO signal: the meaning encoder is independent of atom content."""
    g = stats.rng(seed)
    atom_vecs = _rand_vecs(atoms, d, g)
    meaning_vecs = _rand_vecs(words, d, stats.rng(seed + 777))
    return Realization(name, atom_vecs, meaning_vecs)


def make_english_gloss_realization(words, atoms, tau_real, d: int = 8, seed: int = 0) -> Realization:
    """English-gloss concatenation as ONE realization (labeled), NOT the ontology."""
    r = make_signal_realization("english_gloss", words, atoms, tau_real, d=d, seed=seed)
    return r
