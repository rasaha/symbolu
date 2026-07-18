"""Control tests for the B.0.1 operator-aware probe (calibration only).

Run as a plain script (no pytest):
    python3 experiments/b0_synthetic_harness/test_operator_probe.py
"""
from __future__ import annotations

import numpy as np

from generators import GenParams, generate_with_assets
from harness import bag_features, ridge_oof_r2, _shuffle_within
from harness_operator import (bigram_fn, detect_with, operator_fn,
                              operator_product_features, random_operator_family)


def _check(name: str, ok: bool) -> None:
    print(f"[{'PASS' if ok else 'FAIL'}] {name}")
    if not ok:
        raise AssertionError(name)


def _bag_fn(n):
    # an "order feature" that adds nothing beyond bag (zero columns) -> bag-only
    return lambda seqs: np.zeros((len(seqs), 1))


def test_operator_probe_detects_product() -> None:
    p = GenParams(confound=0.0, effect=1.0, noise=1.0, order_kind="product")
    seqs, y, meta, A = generate_with_assets(300, p, seed=3)
    res = detect_with(seqs, y, p.n_units, operator_fn(A["ops"], A["s0"]), K=60, seed=3)
    _check("operator-aware: detects planted product signal", res["detected"])
    _check("operator-aware: delta > 0.01", res["delta"] > 0.01)


def test_bag_fails_on_pure_product() -> None:
    p = GenParams(confound=0.0, effect=1.0, noise=0.3, order_kind="product")
    seqs, y, meta, A = generate_with_assets(300, p, seed=4)
    Xb = bag_features(seqs, p.n_units)
    r2_bag = ridge_oof_r2(Xb, y, seed=4)
    _check("bag baseline: R^2 near 0 on pure product (< 0.10)", r2_bag < 0.10)


def test_bigram_weak_on_product() -> None:
    p = GenParams(confound=0.0, effect=1.0, noise=1.0, order_kind="product")
    seqs, y, meta, A = generate_with_assets(300, p, seed=3)
    op = detect_with(seqs, y, p.n_units, operator_fn(A["ops"], A["s0"]), K=40, seed=3)
    bg = detect_with(seqs, y, p.n_units, bigram_fn(p.n_units), K=40, seed=3)
    _check("operator-aware delta > bigram delta on product signal",
           op["delta"] > bg["delta"])


def test_shuffle_destroys_operator_detection() -> None:
    p = GenParams(confound=0.0, effect=1.0, noise=1.0, order_kind="product")
    seqs, y, meta, A = generate_with_assets(300, p, seed=5)
    rng = np.random.default_rng(99)
    shuffled = _shuffle_within(seqs, rng)            # break order; keep y
    res = detect_with(shuffled, y, p.n_units, operator_fn(A["ops"], A["s0"]), K=60, seed=5)
    _check("shuffled product: operator-aware no longer detects", not res["detected"])


def test_null_and_noise_return_null() -> None:
    # bag-only data + operator-aware probe must NOT fire (no order signal present)
    p = GenParams(confound=1.0, effect=0.0, noise=1.0, order_kind="product")
    seqs, y, meta, A = generate_with_assets(300, p, seed=6)
    res = detect_with(seqs, y, p.n_units, operator_fn(A["ops"], A["s0"]), K=60, seed=6)
    _check("null/bag: operator-aware returns null", not res["detected"])
    pn = GenParams(confound=0.0, effect=0.0, noise=1.0, order_kind="product")
    s2, y2, m2, A2 = generate_with_assets(300, pn, seed=7)
    r2 = detect_with(s2, y2, pn.n_units, operator_fn(A2["ops"], A2["s0"]), K=60, seed=7)
    _check("pure-noise: operator-aware returns null", not r2["detected"])


def test_determinism() -> None:
    p = GenParams(confound=0.0, effect=0.6, noise=1.0, order_kind="product")
    seqs, y, meta, A = generate_with_assets(200, p, seed=8)
    r1 = detect_with(seqs, y, p.n_units, operator_fn(A["ops"], A["s0"]), K=30, seed=8)
    r2 = detect_with(seqs, y, p.n_units, operator_fn(A["ops"], A["s0"]), K=30, seed=8)
    _check("determinism: identical delta", r1["delta"] == r2["delta"])
    _check("determinism: identical decision", r1["detected"] == r2["detected"])


def main() -> None:
    print("B.0.1 operator-aware probe — control validation (calibration only)\n")
    test_operator_probe_detects_product()
    test_bag_fails_on_pure_product()
    test_bigram_weak_on_product()
    test_shuffle_destroys_operator_detection()
    test_null_and_noise_return_null()
    test_determinism()
    print("\nAll operator-probe control checks passed. Synthetic calibration only; "
          "no semantics, no real data, no Symbol-U claim.")


if __name__ == "__main__":
    main()
