"""Synthetic tests for the target→vṛtti rubric bridge (no real data, no network, no fit).

Verifies: the reliability gate (reliable pass / unreliable -> MEASUREMENT_FAILURE /
insider-vs-naïve divergence -> CIRCULARITY_FAILURE), the Rubric A primary / Rubric B
sensitivity logic, and that everything runs on SYNTHETIC arrays with no real target or
synonym data loaded. No semantic claim is made.

    python3 experiments/synonym_selection/test_rubric.py
"""
from __future__ import annotations

import pathlib
import sys

import numpy as np

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import reliability as REL                          # noqa: E402
import rubric as RB                                # noqa: E402


def _check(name, ok):
    print(f"[{'PASS' if ok else 'FAIL'}] {name}")
    if not ok:
        raise AssertionError(name)


# ---- synthetic rating generator: base [n_targets, n_traits] + per-coder noise -> pool ----
def synth_pool(base, noise, n_coders, seed):
    rng = np.random.default_rng(seed)
    base = np.asarray(base, float)
    return base[..., None] + noise * rng.standard_normal(base.shape + (n_coders,))


# a base with real spread across items (so expected disagreement De > 0)
BASE = np.array([[0.0, 3.0, 1.0],
                 [2.0, 0.0, 3.0],
                 [3.0, 1.0, 0.0],
                 [1.0, 2.0, 2.0]])     # [4 targets x 3 traits]


def test_reliable_ratings_pass():
    insider = synth_pool(BASE, noise=0.15, n_coders=5, seed=1)
    naive = synth_pool(BASE, noise=0.15, n_coders=5, seed=2)      # same base -> pools agree
    gate = REL.reliability_gate(insider, naive)
    _check("reliable: status OK", gate["status"] == "OK")
    _check("reliable: within α_insider ≥ floor", gate["alpha_insider"] >= REL.FLOOR)
    _check("reliable: within α_naive ≥ floor", gate["alpha_naive"] >= REL.FLOOR)
    _check("reliable: between α ≥ floor", gate["alpha_between"] >= REL.FLOOR)


def test_unreliable_ratings_fail():
    insider = synth_pool(BASE, noise=4.0, n_coders=5, seed=3)     # huge within-pool noise
    naive = synth_pool(BASE, noise=0.15, n_coders=5, seed=4)
    gate = REL.reliability_gate(insider, naive)
    _check("unreliable: MEASUREMENT_FAILURE", gate["status"] == "MEASUREMENT_FAILURE")
    _check("unreliable: within α below floor", gate["alpha_insider"] < REL.FLOOR)
    _check("unreliable: between not computed", gate["alpha_between"] is None)


def test_insider_naive_divergence_circularity():
    # both pools internally reliable (low noise) but their BASES diverge systematically
    base_naive = BASE
    base_insider = BASE[::-1]                                      # reversed per-item -> pool means differ
    insider = synth_pool(base_insider, noise=0.15, n_coders=5, seed=5)
    naive = synth_pool(base_naive, noise=0.15, n_coders=5, seed=6)
    gate = REL.reliability_gate(insider, naive)
    _check("divergence: within α_insider still ≥ floor", gate["alpha_insider"] >= REL.FLOOR)
    _check("divergence: within α_naive still ≥ floor", gate["alpha_naive"] >= REL.FLOOR)
    _check("divergence: CIRCULARITY_FAILURE", gate["status"] == "CIRCULARITY_FAILURE")
    _check("divergence: between α below floor", gate["alpha_between"] < REL.FLOOR)


def test_rubric_A_primary_B_sensitivity():
    insider = synth_pool(BASE, noise=0.15, n_coders=5, seed=7)
    naive = synth_pool(BASE, noise=0.15, n_coders=5, seed=8)
    # two DIFFERENT rubrics over the same trait inventory (independent authoring)
    W_A = RB.make_rubric({"t_intensity": [1, 0, 0, 0], "t_hardness": [0, 1, 0, 0],
                          "t_brightness": [0, 0, 1, 0]})
    W_B = RB.make_rubric({"t_intensity": [0, 0, 0, 1], "t_hardness": [1, 0, 0, 0],
                          "t_brightness": [0, 1, 0, 0]})
    res = RB.bridge(insider, naive, W_A, W_B)
    _check("bridge: gate OK -> profiles produced", res["status"] == "OK")
    _check("bridge: profiles_A shape [n_targets x n_vrtti]",
           res["profiles_A"].shape == (BASE.shape[0], len(RB.VRTTI_VOCAB)))
    _check("bridge: A and B differ (sensitivity)",
           not np.allclose(res["profiles_A"], res["profiles_B"]))
    # identical rubrics -> identical profiles
    res_same = RB.bridge(insider, naive, W_A, W_A)
    _check("bridge: identical rubrics -> identical profiles",
           np.allclose(res_same["profiles_A"], res_same["profiles_B"]))

    # verdict logic: A dispositive, B can only downgrade
    _check("verdict: A pass + B pass -> A_AND_B_PASS",
           RB.rubric_verdict(True, True) == "RUBRIC_A_AND_B_PASS")
    _check("verdict: A pass + B fail -> RUBRIC_DEPENDENT",
           RB.rubric_verdict(True, False) == "RUBRIC_DEPENDENT")
    _check("verdict: A fail -> RUBRIC_A_FAIL (B cannot rescue)",
           RB.rubric_verdict(False, True) == "RUBRIC_A_FAIL")


def test_failed_gate_returns_no_profiles():
    insider = synth_pool(BASE, noise=4.0, n_coders=5, seed=9)
    naive = synth_pool(BASE, noise=0.15, n_coders=5, seed=10)
    W = RB.make_rubric({"t_intensity": [1, 0, 0, 0], "t_hardness": [0, 1, 0, 0],
                        "t_brightness": [0, 0, 1, 0]})
    res = RB.bridge(insider, naive, W, W)
    _check("failed gate: status propagated", res["status"] == "MEASUREMENT_FAILURE")
    _check("failed gate: no profiles_A", res["profiles_A"] is None)
    _check("failed gate: no profiles_B", res["profiles_B"] is None)


def test_no_real_data_loaded():
    # bridge is a pure function of synthetic arrays + synthetic rubrics — no disk, no fit.
    insider = synth_pool(BASE, noise=0.15, n_coders=4, seed=11)
    naive = synth_pool(BASE, noise=0.15, n_coders=4, seed=12)
    W = RB.make_rubric({"t_intensity": [1, 0, 0, 0], "t_hardness": [0, 1, 0, 0],
                        "t_brightness": [0, 0, 1, 0]})
    res = RB.bridge(insider, naive, W, W)
    _check("synthetic-only: trait inventory is placeholder", all(t.startswith("t_") for t in RB.TRAIT_INVENTORY))
    _check("synthetic-only: vṛtti vocab is placeholder", all(v.startswith("v") for v in RB.VRTTI_VOCAB))
    _check("synthetic-only: bridge ran on inline arrays", res["status"] == "OK")
    # the rubric module must not pull in the real lexicon / synonym loaders
    _check("synthetic-only: rubric does not import lexicon/g2p/selection",
           not any(m in sys.modules and getattr(sys.modules[m], "__file__", "").endswith(
               f"synonym_selection/{m}.py") for m in ("lexicon", "g2p", "selection")))


def main():
    print("synonym_selection rubric bridge — synthetic tests (no real data, no fit)\n")
    for name, fn in sorted(globals().items()):
        if name.startswith("test_") and callable(fn):
            fn()
    print("\nAll rubric-bridge scaffolding tests passed.")


if __name__ == "__main__":
    main()
