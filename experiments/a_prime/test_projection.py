"""Pipeline-validation tests for the A1.4 projection — ENGINEERING ONLY.

Validates the deterministic projection ``P`` on SYNTHETIC data with known
ground truth, so the test is fully reproducible and depends on NO third-party
dataset. It asserts mechanical correctness only:

* determinism / bit-stability,
* exact recovery of planted per-phoneme values in the identifiable case,
* deterministic handling of the rank-deficient (constant-length) case,
* correctness of the section-4 aggregation.

It computes NO A' result: no Y, no probe, no baseline, no inference, no
PASS/FAIL/bottom decision. Run as a plain script (no pytest):

    python3 experiments/a_prime/test_projection.py
"""
from __future__ import annotations

import numpy as np

from projection import aggregate_to_items, build_incidence, project_per_phoneme


def _check(name: str, ok: bool) -> None:
    print(f"[{'PASS' if ok else 'FAIL'}] {name}")
    if not ok:
        raise AssertionError(name)


def test_determinism() -> None:
    seqs = [["k", "a", "m", "a"], ["b", "u", "b", "u"], ["t", "i", "k", "i"]]
    ratings = [6.0, 2.0, 5.0]
    v1, e1 = project_per_phoneme(seqs, ratings)
    v2, e2 = project_per_phoneme(seqs, ratings)
    _check("determinism: vocab identical", v1 == v2)
    _check("determinism: values bit-identical", np.array_equal(e1, e2))


def test_exact_recovery_identifiable() -> None:
    """Varied-length stimuli + singletons make [X | 1] full column rank, so the
    additive model is identifiable and recovery is exact."""
    rng = np.random.default_rng(0)
    vocab = list("abcdefgh")
    true_e = {p: float(rng.normal()) for p in vocab}
    intercept = 1.7
    seqs: list[list[str]] = [[p] for p in vocab]              # singletons
    seqs += [[p, q] for p in vocab for q in vocab if p < q]   # all pairs
    for _ in range(30):
        seqs.append(list(rng.choice(vocab, size=int(rng.integers(1, 5)))))
    ratings = [sum(true_e[p] for p in s) + intercept for s in seqs]
    vocab_out, e = project_per_phoneme(seqs, ratings, vocab=vocab)
    recovered = np.array([e[vocab_out.index(p)] for p in vocab])
    target = np.array([true_e[p] for p in vocab])
    _check("exact recovery: per-phoneme values match planted truth",
           np.allclose(recovered, target, atol=1e-6))


def test_rank_deficient_constant_length_is_deterministic() -> None:
    """All length-4 CVCV stimuli (constant phoneme count) make the intercept
    collinear with the count total -> rank-deficient. pinv still returns the
    unique minimum-norm solution, which must be deterministic and reconstruct
    the ratings in the column space."""
    rng = np.random.default_rng(1)
    vocab = list("ptkbmnaiu")
    seqs = [list(rng.choice(vocab, size=4)) for _ in range(60)]
    ratings = [float(rng.normal()) for _ in seqs]
    v1, e1 = project_per_phoneme(seqs, ratings, vocab=vocab)
    v2, e2 = project_per_phoneme(seqs, ratings, vocab=vocab)
    _check("rank-deficient: deterministic", np.array_equal(e1, e2))
    # reconstruction: X e should be the projection of r onto col(X); the
    # residual is orthogonal to the column space (least-squares property).
    X, _ = build_incidence(seqs, vocab=vocab, add_intercept=True)
    coef = np.linalg.pinv(X) @ np.asarray(ratings)
    resid = np.asarray(ratings) - X @ coef
    _check("rank-deficient: residual orthogonal to column space",
           np.allclose(X.T @ resid, 0.0, atol=1e-8))


def test_aggregation() -> None:
    vocab = ["a", "b", "c"]
    vals = [1.0, 2.0, 4.0]
    items = [["a", "b"], ["c", "c", "a"], ["z"]]  # 'z' uncovered
    feat = aggregate_to_items(items, vocab, vals,
                              aggs=("mean", "sum", "min", "max"))
    ok = (
        np.allclose(feat[0], [1.5, 3.0, 1.0, 2.0])               # a,b
        and np.allclose(feat[1], [3.0, 9.0, 1.0, 4.0])           # c,c,a
        and np.all(np.isnan(feat[2]))                            # uncovered -> NaN
    )
    _check("aggregation: mean/sum/min/max + uncovered->NaN", ok)


def main() -> None:
    print("A1.4 projection pipeline validation (synthetic; no A' result)\n")
    test_determinism()
    test_exact_recovery_identifiable()
    test_rank_deficient_constant_length_is_deterministic()
    test_aggregation()
    print("\nAll pipeline-validation checks passed. "
          "No Y, no inference, no decision emitted.")


if __name__ == "__main__":
    main()
