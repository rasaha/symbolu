"""Operator initialization + baselines (Stage A).

Primary initializer (option b from STRUCTURAL_V1_OPERATOR_INITIALIZATION.md):
    M_sigma = expm( sum_j f_{sigma,j} * G_j )

with d = 4 (2 (x) 2 tensor layout) and fixed, pre-registered, skew-symmetric
4x4 generators G_A..G_D. exp(skew) is orthogonal, so M_sigma is norm-preserving
and cannot blow up over long sequences.

Generators (frozen):
    G_A = J (x) I    factor-1 slot rotation
    G_B = I (x) J    factor-2 slot rotation        [G_A, G_B] = 0  (DISJOINT/COMMUTE)
    G_C = J (x) Z    coupling                       does not commute with G_B
    G_D = X (x) J    coupling                       does not commute with G_A
where  J=[[0,-1],[1,0]], I=eye(2), Z=diag(1,-1), X=[[0,1],[1,0]].

No fitting, no tuning, one operator per unit, shared across all sequences.
"""
from __future__ import annotations

from typing import List

import numpy as np

D = 4  # 2 (x) 2

# ---- 2x2 building blocks ----
_I2 = np.eye(2)
_J = np.array([[0.0, -1.0], [1.0, 0.0]])      # skew (rotation)
_Z = np.array([[1.0, 0.0], [0.0, -1.0]])      # symmetric
_X = np.array([[0.0, 1.0], [1.0, 0.0]])       # symmetric


def _kron(a: np.ndarray, b: np.ndarray) -> np.ndarray:
    return np.kron(a, b)


# ---- pre-registered generators (skew-symmetric 4x4), in feature order ----
GENERATORS: List[np.ndarray] = [
    _kron(_J, _I2),   # G_A
    _kron(_I2, _J),   # G_B
    _kron(_J, _Z),    # G_C  (skew: J (x) symmetric)
    _kron(_X, _J),    # G_D  (skew: symmetric (x) J)
]
GENERATOR_NAMES = ("G_A", "G_B", "G_C", "G_D")


def _commutator(a: np.ndarray, b: np.ndarray) -> np.ndarray:
    return a @ b - b @ a


def assert_generator_algebra() -> None:
    """Pre-registration guards: skew-symmetry, the commuting (A,B) pair, and that
    the set is genuinely non-abelian. Raises on violation (no silent pass)."""
    for name, G in zip(GENERATOR_NAMES, GENERATORS):
        if not np.allclose(G, -G.T, atol=1e-12):
            raise ValueError(f"{name} is not skew-symmetric")
    # disjoint factors commute
    if not np.allclose(_commutator(GENERATORS[0], GENERATORS[1]), 0.0, atol=1e-12):
        raise ValueError("[G_A, G_B] != 0 (disjoint factors must commute)")
    # coupling generators must NOT all commute (else no order-effects possible)
    noncommuting = [
        (0, 3),  # G_A, G_D
        (1, 2),  # G_B, G_C
    ]
    for a, b in noncommuting:
        if np.allclose(_commutator(GENERATORS[a], GENERATORS[b]), 0.0, atol=1e-12):
            raise ValueError(
                f"[{GENERATOR_NAMES[a]}, {GENERATOR_NAMES[b]}] == 0 "
                "(coupling generators must not commute)"
            )


def commuting_generator_pairs() -> List[tuple]:
    """Return the (a,b) generator-index pairs whose commutator is ~0."""
    pairs = []
    for a in range(len(GENERATORS)):
        for b in range(a + 1, len(GENERATORS)):
            if np.allclose(_commutator(GENERATORS[a], GENERATORS[b]), 0.0, atol=1e-10):
                pairs.append((a, b))
    return pairs


# ---- matrix exponential (numpy-only; scaling-and-squaring + Taylor) ----
def expm(A: np.ndarray, terms: int = 18) -> np.ndarray:
    """Matrix exponential via scaling-and-squaring with a truncated Taylor series.

    For the bounded skew-symmetric inputs used here this is accurate to ~machine
    precision and yields an (approximately) orthogonal matrix.
    """
    A = np.asarray(A, dtype=np.float64)
    nrm = np.linalg.norm(A, ord=2)
    if not np.isfinite(nrm):
        raise FloatingPointError("non-finite matrix in expm")
    s = max(0, int(np.ceil(np.log2(nrm + 1e-30))) + 1)
    B = A / (2.0 ** s)
    term = np.eye(A.shape[0])
    result = np.eye(A.shape[0])
    for k in range(1, terms + 1):
        term = term @ B / k
        result = result + term
    for _ in range(s):
        result = result @ result
    return result


def feature_operators(F: np.ndarray) -> List[np.ndarray]:
    """Primary initializer: M_sigma = expm(sum_j f_{sigma,j} G_j), orthogonal."""
    assert_generator_algebra()
    ops: List[np.ndarray] = []
    for row in F:
        A = np.zeros((D, D))
        for fj, G in zip(row, GENERATORS):
            A = A + fj * G
        M = expm(A)
        if not np.all(np.isfinite(M)):
            raise FloatingPointError("non-finite operator from feature init")
        if not np.allclose(M @ M.T, np.eye(D), atol=1e-6):
            raise ValueError("feature operator not orthogonal (norm not preserved)")
        ops.append(M)
    return ops


def random_orthogonal_operators(n: int, rng: np.random.Generator) -> List[np.ndarray]:
    """Feature-blind control: n random orthogonal 4x4 operators (QR of gaussian)."""
    ops: List[np.ndarray] = []
    for _ in range(n):
        A = rng.standard_normal((D, D))
        Q, R = np.linalg.qr(A)
        # fix sign so Q is a proper, deterministic orthogonal matrix
        Q = Q @ np.diag(np.sign(np.diag(R)) + (np.diag(R) == 0))
        ops.append(Q)
    return ops


def relabel_operators(ops: List[np.ndarray], perm: np.ndarray) -> List[np.ndarray]:
    """Relabel control: permute which operator is assigned to which unit slot."""
    return [ops[i] for i in perm]


def weak_coupling_operators(F: np.ndarray, eps: float = 1e-2) -> List[np.ndarray]:
    """Control (option a): M = I + eps*sum_j f_j G_j. Order-effects are O(eps^2);
    confirms order-effect scales with coupling strength."""
    ops: List[np.ndarray] = []
    for row in F:
        A = np.zeros((D, D))
        for fj, G in zip(row, GENERATORS):
            A = A + fj * G
        ops.append(np.eye(D) + eps * A)
    return ops
