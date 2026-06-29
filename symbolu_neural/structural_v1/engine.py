"""Reading engines (Stage A).

Two engines, run side by side:
  - matrix-product (order-SENSITIVE):  s = M_{i_n} ... M_{i_1} s0
  - bag (order-BLIND baseline):         s = (sum_j A(f_j)) applied additively

The bag reading is additive over units, so permuting the sequence cannot change
it -> its order-effect is identically zero by construction. It is the mandatory
null for G1.
"""
from __future__ import annotations

from typing import List, Sequence

import numpy as np

from .operators import D, GENERATORS

# Frozen initial reading state: fixed, generic, off-axis so it is not accidentally
# an eigenvector of any single operator. Normalized.
S0 = np.array([1.0, 0.0, 0.0, 0.0])
S0 = S0 / np.linalg.norm(S0)


def read_product(seq: Sequence[int], ops: List[np.ndarray], s0: np.ndarray = S0) -> np.ndarray:
    """Order-sensitive reading: apply operators left-to-right as a matrix product."""
    s = np.array(s0, dtype=np.float64)
    for i in seq:
        s = ops[i] @ s
        if not np.all(np.isfinite(s)):
            raise FloatingPointError("non-finite state in product reading")
    return s


def read_bag(seq: Sequence[int], F: np.ndarray, s0: np.ndarray = S0) -> np.ndarray:
    """Order-blind baseline: sum the per-unit generators, then apply once.

    Additive aggregation -> identical for any permutation of `seq`.
    """
    A = np.zeros((D, D))
    for i in seq:
        row = F[i]
        for fj, G in zip(row, GENERATORS):
            A = A + fj * G
    s = (np.eye(D) + A) @ np.array(s0, dtype=np.float64)
    if not np.all(np.isfinite(s)):
        raise FloatingPointError("non-finite state in bag reading")
    return s
