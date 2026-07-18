"""D0' — gauge-invariant operator-algebra analysis (STRUCTURAL ONLY).

Reads the frozen Stage A operators ``{M_sigma}`` (feature-derived, SO(4)) as
**read-only** inputs and computes coordinate-free / gauge-aware structural
diagnostics. See ``SYMBOL_U_UNBLOCKED_RESEARCH_PLAN.md`` (D0') and
``MILESTONE_A_PRIME_PREREGISTRATION_AMENDMENT_1.md``.

Scope guards (binding):
* Structural / gauge / operator-algebra ONLY. No semantic ``Y``, no L2 ``F``,
  no decoder, no A' analysis, no PASS/FAIL/bottom for Symbol-U *semantics*.
* Stage A is never modified; operators are reproduced read-only.
* A *positive* (nontrivial) result means only "nontrivial frozen operator
  algebra", NOT semantic validity and NOT validation of the "true" operators.
* A *negative* (abelian) result is a structural falsification of THIS frozen
  operator instance's non-commutativity claim, nothing more.

Gauge note. The operators are reproduced as orthogonal matrices, but the
identifiability gauge of a linear automaton ``(d, s0, {M}, u)`` is the full
similarity group ``M -> P M P^-1``. Quantities are tagged:
  * GL-invariant (true gauge invariants): commutator *rank*, generated-algebra
    dimension, eigenvalues, trace, determinant, Hankel rank, trace-of-word.
  * orthogonal-invariant only (basis-dependent under general gauge, reported as
    diagnostics): Frobenius norms, singular values, normalized commutator norm.
"""
from __future__ import annotations

import itertools
import pathlib
import sys
from dataclasses import dataclass, field

import numpy as np

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))
from common.stats import numerical_rank, random_orthogonal_family  # noqa: E402,F401

# ---- pre-registered numerical thresholds (fixed BEFORE execution) ----
TOL_COMMUTE = 1e-8      # normalized commutator norm below this -> pair "commutes"
TOL_ABELIAN = 1e-6      # joint-diagonalization off-diagonal defect below -> abelian
RANK_TOL = 1e-9         # relative SVD tolerance for numerical rank
GENERIC_SEED = 20260629  # deterministic coefficients for the generic combination


# ----------------------------------------------------------------------
# read-only access to the frozen Stage A operators
# ----------------------------------------------------------------------
def load_stage_a_operators() -> tuple[list[str], list[np.ndarray], np.ndarray]:
    """Reproduce the frozen Stage A operators READ-ONLY. Returns (units, ops, s0).

    The two frozen source modules (``features.py``, ``operators.py``) import only
    numpy and use no relative imports, so they are loaded directly by file path —
    bypassing ``symbolu_neural/__init__`` (which pulls in torch) without modifying,
    importing, or executing anything else in Stage A. ``s0`` mirrors the documented
    constant in ``structural_v1/engine.py`` (S0 = normalize([1,0,0,0])).
    """
    import importlib.util
    from pathlib import Path
    sv1 = Path(__file__).resolve().parents[2] / "symbolu_neural" / "structural_v1"

    def _load(name: str, path: Path):
        spec = importlib.util.spec_from_file_location(name, path)
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        return mod

    features = _load("sv1_features", sv1 / "features.py")
    operators = _load("sv1_operators", sv1 / "operators.py")
    ops = operators.feature_operators(features.feature_matrix())
    s0 = np.array([1.0, 0.0, 0.0, 0.0]); s0 = s0 / np.linalg.norm(s0)
    return list(features.UNITS), [np.asarray(M, float) for M in ops], s0


# ----------------------------------------------------------------------
# numerical helpers
# ----------------------------------------------------------------------
def _frob(M: np.ndarray) -> float:
    return float(np.linalg.norm(M, "fro"))


# ----------------------------------------------------------------------
# 1. inventory
# ----------------------------------------------------------------------
def inventory(ops: list[np.ndarray]) -> dict:
    dets, traces, fro, conds, ranks = [], [], [], [], []
    for M in ops:
        dets.append(float(np.linalg.det(M)))
        traces.append(float(np.trace(M)))
        fro.append(_frob(M))
        s = np.linalg.svd(M, compute_uv=False)
        conds.append(float(s[0] / s[-1]) if s[-1] > 0 else np.inf)
        ranks.append(numerical_rank(M))
    return {
        "n_operators": len(ops),
        "shapes": sorted({M.shape for M in ops}),
        "frobenius_norm": {"min": min(fro), "max": max(fro)},
        "rank": {"min": min(ranks), "max": max(ranks)},
        "condition_number": {"min": min(conds), "max": max(conds)},
        "determinant": {"min": min(dets), "max": max(dets)},
        "trace": {"min": min(traces), "max": max(traces)},
    }


# ----------------------------------------------------------------------
# 2. pairwise non-commutativity
# ----------------------------------------------------------------------
def commutator(a: np.ndarray, b: np.ndarray) -> np.ndarray:
    return a @ b - b @ a


def pairwise_noncommutativity(ops: list[np.ndarray],
                              tol: float = TOL_COMMUTE) -> dict:
    n = len(ops)
    norms, ranks, near = [], [], []
    for i, j in itertools.combinations(range(n), 2):
        C = commutator(ops[i], ops[j])
        denom = _frob(ops[i]) * _frob(ops[j])
        nn = _frob(C) / denom if denom > 0 else 0.0
        norms.append(nn)
        ranks.append(numerical_rank(C))
        if nn < tol:
            near.append((i, j, nn))
    norms = np.array(norms) if norms else np.array([0.0])
    return {
        "n_pairs": len(norms),
        "normalized_commutator_norm": {
            "min": float(norms.min()), "median": float(np.median(norms)),
            "max": float(norms.max()), "mean": float(norms.mean()),
        },
        "commutator_rank": {"min": int(min(ranks)) if ranks else 0,
                            "max": int(max(ranks)) if ranks else 0},
        "n_near_commuting_pairs": len(near),
        "near_commuting_pairs": near[:20],
    }


# ----------------------------------------------------------------------
# 3. joint-diagonalization / abelianity proxy
# ----------------------------------------------------------------------
def abelianity_defect(ops: list[np.ndarray], seed: int = GENERIC_SEED) -> dict:
    """Generic-combination shared-eigenbasis defect.

    A commuting (simultaneously diagonalizable) family is diagonalized by the
    eigenbasis of a generic linear combination ``C = sum c_k M_k``. We diagonalize
    C, change every operator into that basis, and measure the off-diagonal mass.
    ~0 across all operators => effectively abelian.
    """
    rng = np.random.default_rng(seed)
    c = rng.standard_normal(len(ops))
    C = sum(ck * M for ck, M in zip(c, ops))
    w, V = np.linalg.eig(C)            # complex in general
    Vinv = np.linalg.pinv(V)
    defects = []
    for M in ops:
        D = Vinv @ M.astype(complex) @ V
        off = D - np.diag(np.diag(D))
        denom = np.linalg.norm(D, "fro")
        defects.append(float(np.linalg.norm(off, "fro") / denom) if denom > 0 else 0.0)
    defects = np.array(defects)
    return {
        "offdiag_defect": {"mean": float(defects.mean()),
                           "max": float(defects.max())},
        "generic_combination_cond": float(np.linalg.cond(V)),
    }


# ----------------------------------------------------------------------
# 4 & 5. generated algebra dimension + word-trace order sensitivity + Hankel
# ----------------------------------------------------------------------
def generated_algebra_dimension(ops: list[np.ndarray], max_len: int = 4,
                                rel_tol: float = RANK_TOL) -> dict:
    """dim span{ products M_w : |w| <= max_len } as a subspace of R^{d*d}.

    GL-invariant. Identity included (length 0). Commuting families stay small;
    a richly non-abelian family fills toward d^2.
    """
    d = ops[0].shape[0]
    vecs = [np.eye(d).ravel()]
    frontier = [np.eye(d)]
    by_len = {0: 1}
    for L in range(1, max_len + 1):
        new_frontier = []
        for P in frontier:
            for M in ops:
                W = M @ P
                new_frontier.append(W)
                vecs.append(W.ravel())
        frontier = new_frontier
        rank = numerical_rank(np.array(vecs), rel_tol)
        by_len[L] = rank
        if rank >= d * d:          # saturated the full matrix space
            by_len[L] = d * d
            break
    return {"d2_ceiling": d * d, "dim_by_length": by_len,
            "final_dim": max(by_len.values())}


def trace_word_order_sensitivity(ops: list[np.ndarray], n_samples: int = 2000,
                                 seed: int = GENERIC_SEED) -> dict:
    """tr(M_a M_b M_c) vs tr(M_a M_c M_b). Trace is conjugation-invariant ->
    a fully GL-invariant witness of order dependence at word length 3."""
    rng = np.random.default_rng(seed)
    n = len(ops)
    diffs = []
    for _ in range(n_samples):
        a, b, c = rng.integers(0, n, size=3)
        t1 = float(np.trace(ops[a] @ ops[b] @ ops[c]))
        t2 = float(np.trace(ops[a] @ ops[c] @ ops[b]))
        diffs.append(abs(t1 - t2))
    diffs = np.array(diffs)
    return {"n_samples": int(n_samples),
            "max_abs_trace_diff": float(diffs.max()),
            "frac_order_sensitive": float(np.mean(diffs > 1e-9))}


def reachability_order(ops: list[np.ndarray], s0: np.ndarray,
                       alphabet: list[int], max_len: int = 3,
                       n_perm_samples: int = 2000, seed: int = GENERIC_SEED,
                       rel_tol: float = RANK_TOL) -> dict:
    """Reachability (scalar Hankel) rank and behaviour-level order separation.

    * ``reachability_rank`` = dim span{ M_w s0 : |w| <= max_len } = the minimal
      linear-realization dimension of the series w -> M_w s0 (an exact Hankel
      rank with the identity readout). GL-invariant. Bounded by ``d``, so in a
      ``d``-dimensional model it cannot exceed ``d`` for ANY family (abelian or
      not) — it is reported descriptively, NOT as an emergence separation.
    * ``order_separation`` = fraction of sampled words (len >= 2) whose state
      ``M_w s0`` changes under a random reordering of ``w``. This is the clean,
      gauge-invariant "order carries information" test (VSO E1): identically 0
      for any commuting/abelian family, > 0 only under genuine non-commutativity.

    The emergence "rank beyond the abelian baseline" is carried by
    ``generated_algebra_dimension`` (<= d^2), compared against the commuting
    control in the runner — the scalar reachability rank cannot show it here.
    """
    rng = np.random.default_rng(seed)
    words = []
    for L in range(1, max_len + 1):
        words.extend(itertools.product(alphabet, repeat=L))

    def state(seq):
        s = np.array(s0, float)
        for i in seq:
            s = ops[i] @ s
        return s

    R = np.array([state(w) for w in words]).T          # d x n_words
    reach_rank = numerical_rank(R, rel_tol)

    # order separation over sampled multi-letter words from the full inventory
    n = len(ops)
    changed = 0
    total = 0
    for _ in range(n_perm_samples):
        L = int(rng.integers(2, 5))
        w = list(rng.integers(0, n, size=L))
        perm = w[:]
        rng.shuffle(perm)
        if perm == w:
            continue
        total += 1
        if not np.allclose(state(w), state(perm), atol=1e-9):
            changed += 1
    return {"alphabet_size": len(alphabet), "max_len": max_len,
            "reachability_rank": reach_rank, "d_ceiling": ops[0].shape[0],
            "order_separation_frac": (changed / total) if total else 0.0,
            "order_separation_pairs": total}


# ----------------------------------------------------------------------
# decision (structural only; pre-registered)
# ----------------------------------------------------------------------
def structural_decision(comm: dict, abel: dict, algebra: dict, trace: dict,
                        d: int) -> dict:
    is_abelian = (
        comm["normalized_commutator_norm"]["max"] < TOL_COMMUTE
        and abel["offdiag_defect"]["max"] < TOL_ABELIAN
        and algebra["final_dim"] <= d
        and trace["frac_order_sensitive"] == 0.0
    )
    if is_abelian:
        verdict = ("STRUCTURALLY ABELIAN -> possible structural falsification of "
                   "this frozen Stage A operator instance (non-commutativity claim)")
    else:
        verdict = ("STRUCTURALLY NONTRIVIAL non-commutative family "
                   "(structure only; NOT semantic validity)")
    return {"is_effectively_abelian": bool(is_abelian), "verdict": verdict}


# ----------------------------------------------------------------------
# synthetic control families (calibration + tests)
# ----------------------------------------------------------------------
def identity_family(n: int, d: int = 4) -> list[np.ndarray]:
    return [np.eye(d) for _ in range(n)]


def commuting_diagonal_family(n: int, d: int = 4, seed: int = 0) -> list[np.ndarray]:
    rng = np.random.default_rng(seed)
    return [np.diag(rng.standard_normal(d)) for _ in range(n)]


@dataclass
class FamilyReport:
    name: str
    inventory: dict = field(default_factory=dict)
    noncommutativity: dict = field(default_factory=dict)
    abelianity: dict = field(default_factory=dict)
    algebra: dict = field(default_factory=dict)
    trace_order: dict = field(default_factory=dict)
    reachability: dict = field(default_factory=dict)
    decision: dict = field(default_factory=dict)


def analyze_family(name: str, ops: list[np.ndarray], s0: np.ndarray | None = None,
                   alphabet: list[int] | None = None, max_word: int = 4) -> FamilyReport:
    d = ops[0].shape[0]
    if s0 is None:
        s0 = np.eye(d)[0]
    if alphabet is None:
        alphabet = list(range(min(4, len(ops))))
    inv = inventory(ops)
    comm = pairwise_noncommutativity(ops)
    abel = abelianity_defect(ops)
    alg = generated_algebra_dimension(ops, max_len=max_word)
    tr = trace_word_order_sensitivity(ops)
    rch = reachability_order(ops, s0, alphabet, max_len=3)
    dec = structural_decision(comm, abel, alg, tr, d)
    return FamilyReport(name, inv, comm, abel, alg, tr, rch, dec)
