"""Control tests for B.0.2 operator-mismatch calibration (calibration only).

    python3 experiments/b0_synthetic_harness/test_mismatch.py
"""
from __future__ import annotations

import sys

import numpy as np

from generators import GenParams, generate_with_assets
from harness_operator import detect_with, operator_fn
from harness_mismatch import (probe_abelian, probe_exact, probe_perturb,
                              probe_random)


def _check(name: str, ok: bool) -> None:
    print(f"[{'PASS' if ok else 'FAIL'}] {name}")
    if not ok:
        raise AssertionError(name)


def _delta(make_probe, p, seed, K=40):
    seqs, y, meta, A = generate_with_assets(300, p, seed)
    N, s0 = make_probe(A["ops"], A["s0"], seed)
    return detect_with(seqs, y, p.n_units, operator_fn(N, s0), K=K, seed=seed)


PROD = GenParams(confound=0.0, effect=1.0, noise=1.0, order_kind="product")


def test_exact_detects() -> None:
    res = _delta(lambda o, s, sd: probe_exact(o, s, sd), PROD, seed=3)
    _check("exact match: detects product signal", res["detected"])


def test_random_weaker_than_exact() -> None:
    ex = _delta(lambda o, s, sd: probe_exact(o, s, sd), PROD, seed=3)
    rn = _delta(lambda o, s, sd: probe_random(o, s, sd), PROD, seed=3)
    _check("random mismatch: delta < exact delta", rn["delta"] < ex["delta"])


def test_abelian_fails_on_product() -> None:
    res = _delta(lambda o, s, sd: probe_abelian(o, s, sd), PROD, seed=4)
    _check("abelian probe: does NOT detect noncommutative product", not res["detected"])


def test_perturbation_monotone_on_average() -> None:
    d0, dbig = [], []
    for seed in (10, 11, 12, 13):
        d0.append(_delta(lambda o, s, sd: probe_perturb(o, s, 0.0, sd), PROD, seed, K=30)["delta"])
        dbig.append(_delta(lambda o, s, sd: probe_perturb(o, s, 1.5, sd), PROD, seed, K=30)["delta"])
    _check("perturbation: mean delta(eps=0) > mean delta(eps=1.5)",
           float(np.mean(d0)) > float(np.mean(dbig)))


def test_determinism() -> None:
    r1 = _delta(lambda o, s, sd: probe_perturb(o, s, 0.3, sd), PROD, seed=8, K=30)
    r2 = _delta(lambda o, s, sd: probe_perturb(o, s, 0.3, sd), PROD, seed=8, K=30)
    _check("determinism: identical delta", r1["delta"] == r2["delta"])
    _check("determinism: identical decision", r1["detected"] == r2["detected"])


def test_stage_a_untouched() -> None:
    _check("Stage A not imported by mismatch harness",
           not any("structural_v1" in m for m in sys.modules))


def main() -> None:
    print("B.0.2 operator-mismatch — control validation (calibration only)\n")
    test_exact_detects()
    test_random_weaker_than_exact()
    test_abelian_fails_on_product()
    test_perturbation_monotone_on_average()
    test_determinism()
    test_stage_a_untouched()
    print("\nAll mismatch control checks passed. Synthetic calibration only; "
          "no semantics, no real data, no Symbol-U claim.")


if __name__ == "__main__":
    main()
