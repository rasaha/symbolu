"""Vṛtti-as-deterministic-operator composition (scaffolding; synthetic only).

Documents the DETERMINISTIC-operator branch of THEORY_VRTTI_KERNEL_FORMALIZATION.md:
each varṇa maps to a deterministic operator (a d×d matrix); a word's representation is
the ORDERED OPERATOR PRODUCT. Deterministic operators are the point-mass / zero-conditional-
entropy special case of the Markov-kernel frame (not implemented here).

This module uses SYNTHETIC toy operators (seeded orthogonal matrices). A frozen operator
table (e.g. a Stage-A M_σ table) could be supplied through the same `op_map` interface
WITHOUT modification, but the scaffold neither imports nor reads Stage A. No fit, no
semantic claim, no validation.
"""
from __future__ import annotations

import pathlib
import sys

import numpy as np

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))
from common import stats  # noqa: E402  (rng, random_orthogonal_matrices)


# ---------------------------------------------------------------- operators ----
def random_operators(keys, d: int = 4, seed: int = 0) -> dict:
    """SYNTHETIC toy table: varṇa key -> deterministic d×d orthogonal operator.

    Orthogonal (like SO(d)) so ordered products stay norm-stable. Seeded -> reproducible.
    """
    g = stats.rng(seed)
    mats = stats.random_orthogonal_matrices(len(keys), d, g)
    return {k: mats[i] for i, k in enumerate(keys)}


def with_identity(op_map: dict, key: str = "_id") -> dict:
    """Return a copy with an explicit identity operator under `key`."""
    d = next(iter(op_map.values())).shape[0]
    out = dict(op_map)
    out[key] = np.eye(d)
    return out


# ------------------------------------------------------------- composition ----
def word_operator(seq, op_map: dict) -> np.ndarray:
    """Ordered operator product P = M_{σ_n} · … · M_{σ_1}  (later symbols apply later)."""
    d = next(iter(op_map.values())).shape[0]
    P = np.eye(d)
    for k in seq:
        P = op_map[k] @ P
    return P


def word_representation(seq, op_map: dict, h0: np.ndarray | None = None) -> np.ndarray:
    """Apply the composed operator to a base vector h0 (default e_0)."""
    P = word_operator(seq, op_map)
    if h0 is None:
        h0 = np.zeros(P.shape[0]); h0[0] = 1.0
    return P @ h0


# ---------------------------------------------- order-INVARIANT baselines -----
def bag_operator_sum(seq, op_map: dict) -> np.ndarray:
    """Commutative aggregate: sum of per-varṇa operators (order-invariant)."""
    d = next(iter(op_map.values())).shape[0]
    S = np.zeros((d, d))
    for k in seq:
        S = S + op_map[k]
    return S


def vector_map(op_map: dict) -> dict:
    """Derive a per-varṇa vector (first column) for the additive baseline."""
    return {k: M[:, 0].copy() for k, M in op_map.items()}


def additive_vector_model(seq, vec_map: dict) -> np.ndarray:
    """Commutative aggregate: sum of per-varṇa vectors (order-invariant)."""
    d = next(iter(vec_map.values())).shape[0]
    v = np.zeros(d)
    for k in seq:
        v = v + vec_map[k]
    return v
