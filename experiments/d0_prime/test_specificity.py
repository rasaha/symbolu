"""Control tests for the D0'.1 specificity nulls (structural only).

    python3 experiments/d0_prime/test_specificity.py
"""
from __future__ import annotations

import numpy as np

from specificity import (NULLS, STAT_KEYS, load_frozen, null_A_permute_rows,
                         null_B_independent_global, null_C_preserve_norms,
                         null_D_preserve_cosines, null_E_maxent_first_order,
                         stat_vector)

# small controlled feature matrix (norms < 1 so clip is inactive -> exact invariants)
_FSMALL = np.array([[0.2, -0.1, 0.0, 0.3],
                    [-0.3, 0.2, 0.1, -0.2],
                    [0.1, 0.1, -0.2, 0.0],
                    [0.0, -0.3, 0.2, 0.1]])


def _check(name, ok):
    print(f"[{'PASS' if ok else 'FAIL'}] {name}")
    if not ok:
        raise AssertionError(name)


def test_A_preserves_multiset():
    out = null_A_permute_rows(_FSMALL, np.random.default_rng(0))
    _check("A: row multiset preserved",
           np.allclose(np.sort(out, axis=0), np.sort(_FSMALL, axis=0)))


def test_C_preserves_norms():
    out = null_C_preserve_norms(_FSMALL, np.random.default_rng(1))
    _check("C: per-row norms preserved",
           np.allclose(np.linalg.norm(out, axis=1), np.linalg.norm(_FSMALL, axis=1), atol=1e-9))


def test_D_preserves_cosines():
    out = null_D_preserve_cosines(_FSMALL, np.random.default_rng(2))
    def cos(M):
        n = M / (np.linalg.norm(M, axis=1, keepdims=True) + 1e-12)
        return n @ n.T
    _check("D: pairwise cosines preserved", np.allclose(cos(out), cos(_FSMALL), atol=1e-9))


def test_E_draws_from_column_support():
    out = null_E_maxent_first_order(_FSMALL, np.random.default_rng(3))
    ok = all(set(np.round(out[:, j], 9)).issubset(set(np.round(_FSMALL[:, j], 9)))
             for j in range(_FSMALL.shape[1]))
    _check("E: each column drawn from its own marginal", ok)


def test_B_draws_from_pool():
    out = null_B_independent_global(_FSMALL, np.random.default_rng(4))
    pool = set(np.round(_FSMALL.ravel(), 9))
    _check("B: values drawn from pooled global distribution",
           set(np.round(out.ravel(), 9)).issubset(pool))


def test_determinism():
    a = null_D_preserve_cosines(_FSMALL, np.random.default_rng(7))
    b = null_D_preserve_cosines(_FSMALL, np.random.default_rng(7))
    _check("null determinism under fixed seed", np.array_equal(a, b))


def test_stage_a_stat_vector_regression():
    units, F, feature_operators, s0 = load_frozen()
    sv = stat_vector(feature_operators(F), s0)
    _check("Stage A stat vector has all keys", set(sv) == set(STAT_KEYS))
    _check("Stage A algebra dim == 16 (matches D0')", sv["algebra_dim"] == 16.0)
    _check("all 5 nulls registered", set(NULLS) >= {"A_permute_rows", "B_independent_global",
           "C_preserve_norms", "D_preserve_cosines", "E_maxent_first_order"})


def main():
    print("D0'.1 specificity-null control tests (structural only)\n")
    for name, fn in sorted(globals().items()):
        if name.startswith("test_") and callable(fn):
            fn()
    print("\nAll specificity-null control tests passed.")


if __name__ == "__main__":
    main()
