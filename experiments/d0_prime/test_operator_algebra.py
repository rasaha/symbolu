"""Validation tests for the D0' operator-algebra analysis (STRUCTURAL ONLY).

Validates the analysis primitives against synthetic control families with KNOWN
algebraic structure, so the tooling is trustworthy before it is pointed at the
frozen Stage A operators. No external data, no semantic Y, no inference.

Run as a plain script (no pytest):
    python3 experiments/d0_prime/test_operator_algebra.py
"""
from __future__ import annotations

import numpy as np

from operator_algebra import (
    analyze_family, commuting_diagonal_family, generated_algebra_dimension,
    identity_family, numerical_rank, pairwise_noncommutativity,
    random_orthogonal_family,
)


def _check(name: str, ok: bool) -> None:
    print(f"[{'PASS' if ok else 'FAIL'}] {name}")
    if not ok:
        raise AssertionError(name)


def test_numerical_rank() -> None:
    _check("rank(I_4) == 4", numerical_rank(np.eye(4)) == 4)
    _check("rank(zeros) == 0", numerical_rank(np.zeros((4, 4))) == 0)
    M = np.outer([1, 2, 3, 4], [1, 0, 0, 0])
    _check("rank(rank-1) == 1", numerical_rank(M) == 1)


def test_identity_is_abelian() -> None:
    rep = analyze_family("identity", identity_family(6, 4))
    _check("identity: max commutator ~ 0",
           rep.noncommutativity["normalized_commutator_norm"]["max"] < 1e-12)
    _check("identity: algebra dim == 1", rep.algebra["final_dim"] == 1)
    _check("identity: no trace order-sensitivity",
           rep.trace_order["frac_order_sensitive"] == 0.0)
    _check("identity: decision == abelian", rep.decision["is_effectively_abelian"])
    _check("identity: order separation == 0",
           rep.reachability["order_separation_frac"] == 0.0)


def test_commuting_diagonal_is_abelian() -> None:
    rep = analyze_family("commuting_diag", commuting_diagonal_family(6, 4, seed=1))
    _check("commuting-diag: max commutator ~ 0",
           rep.noncommutativity["normalized_commutator_norm"]["max"] < 1e-10)
    _check("commuting-diag: algebra dim <= d (=4)", rep.algebra["final_dim"] <= 4)
    _check("commuting-diag: decision == abelian",
           rep.decision["is_effectively_abelian"])
    _check("commuting-diag: order separation == 0",
           rep.reachability["order_separation_frac"] == 0.0)


def test_random_orthogonal_is_nonabelian() -> None:
    rep = analyze_family("random_orth", random_orthogonal_family(6, 4, seed=2))
    _check("random-orth: max commutator > 0.1",
           rep.noncommutativity["normalized_commutator_norm"]["max"] > 0.1)
    _check("random-orth: algebra dim > d (=4)", rep.algebra["final_dim"] > 4)
    _check("random-orth: trace order-sensitive > 0",
           rep.trace_order["frac_order_sensitive"] > 0.0)
    _check("random-orth: decision == nontrivial",
           not rep.decision["is_effectively_abelian"])
    _check("random-orth: order separation > 0",
           rep.reachability["order_separation_frac"] > 0.0)


def test_algebra_dim_monotone_and_bounded() -> None:
    ops = random_orthogonal_family(5, 4, seed=3)
    alg = generated_algebra_dimension(ops, max_len=4)
    dims = list(alg["dim_by_length"].values())
    _check("algebra dim non-decreasing", all(b >= a for a, b in zip(dims, dims[1:])))
    _check("algebra dim bounded by d^2=16", alg["final_dim"] <= 16)


def test_commutator_symmetry_count() -> None:
    ops = random_orthogonal_family(5, 4, seed=4)
    comm = pairwise_noncommutativity(ops)
    _check("n_pairs == C(5,2) == 10", comm["n_pairs"] == 10)


def main() -> None:
    print("D0' operator-algebra analysis — control validation (structural only)\n")
    test_numerical_rank()
    test_identity_is_abelian()
    test_commuting_diagonal_is_abelian()
    test_random_orthogonal_is_nonabelian()
    test_algebra_dim_monotone_and_bounded()
    test_commutator_symmetry_count()
    print("\nAll control-validation checks passed. Structural only; no semantics, "
          "no inference, no A'.")


if __name__ == "__main__":
    main()
