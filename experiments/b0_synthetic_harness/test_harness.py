"""Control tests for the B.0 synthetic harness (calibration only; no semantics).

Run as a plain script (no pytest):
    python3 experiments/b0_synthetic_harness/test_harness.py
"""
from __future__ import annotations

from generators import GenParams, generate
from harness import (MIN_DELTA_R2, decision_label, detect_order,
                     relabel_invariance, _shuffle_within)
import numpy as np


def _check(name: str, ok: bool) -> None:
    print(f"[{'PASS' if ok else 'FAIL'}] {name}")
    if not ok:
        raise AssertionError(name)


def test_null_bag_returns_null() -> None:
    p = GenParams(confound=1.0, effect=0.0, noise=1.0)
    seqs, y, meta = generate(300, p, seed=1)
    res = detect_order(seqs, y, p.n_units, K=60, seed=1)
    _check("null/bag: not detected", not res["detected"])
    _check("null/bag: label CORRECT_NULL",
           decision_label(res, meta["order_present"]) == "CORRECT_NULL")


def test_pure_noise_returns_null() -> None:
    p = GenParams(confound=0.0, effect=0.0, noise=1.0)
    seqs, y, meta = generate(300, p, seed=2)
    res = detect_order(seqs, y, p.n_units, K=60, seed=2)
    _check("pure-noise: not detected", not res["detected"])


def test_order_signal_detected() -> None:
    p = GenParams(confound=0.0, effect=1.0, noise=1.0)
    seqs, y, meta = generate(300, p, seed=3)
    res = detect_order(seqs, y, p.n_units, K=60, seed=3)
    _check("order: detected", res["detected"])
    _check("order: delta > MIN_DELTA_R2", res["delta"] > MIN_DELTA_R2)
    _check("order: label DETECTED",
           decision_label(res, meta["order_present"]) == "DETECTED_PLANTED_SIGNAL")


def test_bag_baseline_cannot_recover_pure_order() -> None:
    p = GenParams(confound=0.0, effect=1.0, noise=0.3)
    seqs, y, _ = generate(300, p, seed=4)
    res = detect_order(seqs, y, p.n_units, K=40, seed=4)
    _check("pure-order: bag baseline R^2 near 0 (< 0.10)", res["r2_bag"] < 0.10)
    _check("pure-order: order probe R^2 > bag", res["r2_order"] > res["r2_bag"])


def test_shuffle_destroys_order_signal() -> None:
    p = GenParams(confound=0.0, effect=1.0, noise=1.0)
    seqs, y, _ = generate(300, p, seed=5)
    rng = np.random.default_rng(99)
    shuffled = _shuffle_within(seqs, rng)         # break order; keep y
    res = detect_order(shuffled, y, p.n_units, K=60, seed=5)
    _check("shuffled-order: order signal no longer detected", not res["detected"])


def test_determinism() -> None:
    p = GenParams(confound=0.0, effect=0.5, noise=1.0)
    seqs, y, _ = generate(200, p, seed=7)
    r1 = detect_order(seqs, y, p.n_units, K=40, seed=7)
    r2 = detect_order(seqs, y, p.n_units, K=40, seed=7)
    _check("determinism: identical delta", r1["delta"] == r2["delta"])
    _check("determinism: identical decision", r1["detected"] == r2["detected"])


def test_relabel_invariance() -> None:
    p = GenParams(confound=0.0, effect=1.0, noise=1.0)
    seqs, y, _ = generate(200, p, seed=8)
    inv = relabel_invariance(seqs, y, p.n_units, seed=8)
    _check("relabel: linear probe is permutation-invariant", inv["invariant"])


def main() -> None:
    print("B.0 synthetic harness — control validation (calibration only)\n")
    test_null_bag_returns_null()
    test_pure_noise_returns_null()
    test_order_signal_detected()
    test_bag_baseline_cannot_recover_pure_order()
    test_shuffle_destroys_order_signal()
    test_determinism()
    test_relabel_invariance()
    print("\nAll harness control checks passed. Synthetic calibration only; "
          "no semantics, no real data, no Symbol-U claim.")


if __name__ == "__main__":
    main()
