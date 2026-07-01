"""Synthetic tests for vṛtti-as-deterministic-operator composition (no real data, no result).

Verifies (per the requested scaffold):
  - order sensitivity,
  - associativity of composition,
  - non-commutativity when operators differ,
  - identity behavior,
  - deterministic reproducibility,
  - additive/bag model CANNOT distinguish anagrams but the operator model CAN,
  - the guarded runner emits NOT_RUN (no real result),
  - synthetic-only (no real varṇa table imported).

    python3 experiments/varna_operator/test_varna_operator.py
"""
from __future__ import annotations

import pathlib
import sys

import numpy as np

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import operators as OP          # noqa: E402
import run_varna_operator as RUN  # noqa: E402


def _check(name, ok):
    print(f"[{'PASS' if ok else 'FAIL'}] {name}")
    if not ok:
        raise AssertionError(name)


KEYS = ["a", "b", "c", "d"]


def test_order_sensitivity():
    M = OP.random_operators(KEYS, d=4, seed=1)
    ab = OP.word_operator(["a", "b"], M)
    ba = OP.word_operator(["b", "a"], M)
    _check("order: R([a,b]) != R([b,a]) for non-commuting ops", not np.allclose(ab, ba))
    _check("order: representations differ too",
           not np.allclose(OP.word_representation(["a", "b"], M),
                           OP.word_representation(["b", "a"], M)))


def test_associativity():
    M = OP.random_operators(KEYS, d=4, seed=2)
    Ma, Mb, Mc = M["a"], M["b"], M["c"]
    full = OP.word_operator(["a", "b", "c"], M)
    _check("assoc: word product == M_c·M_b·M_a", np.allclose(full, Mc @ Mb @ Ma))
    _check("assoc: (M_c·M_b)·M_a == M_c·(M_b·M_a)",
           np.allclose((Mc @ Mb) @ Ma, Mc @ (Mb @ Ma)))
    # composing a subword then the rest equals composing the whole
    sub = OP.word_operator(["a", "b"], M)
    _check("assoc: compose(subword) then apply rest == full",
           np.allclose(Mc @ sub, full))


def test_non_commutativity():
    M = OP.random_operators(KEYS, d=4, seed=3)
    _check("noncommute: M_a·M_b != M_b·M_a for differing ops",
           not np.allclose(M["a"] @ M["b"], M["b"] @ M["a"]))


def test_identity_behavior():
    M = OP.with_identity(OP.random_operators(KEYS, d=4, seed=4), key="_id")
    _check("identity: inserting _id leaves the product unchanged",
           np.allclose(OP.word_operator(["a", "_id", "b"], M),
                       OP.word_operator(["a", "b"], M)))
    _check("identity: empty word == I",
           np.allclose(OP.word_operator([], M), np.eye(4)))


def test_deterministic_reproducibility():
    M1 = OP.random_operators(KEYS, d=4, seed=7)
    M2 = OP.random_operators(KEYS, d=4, seed=7)
    _check("determinism: same seed -> identical operators",
           all(np.allclose(M1[k], M2[k]) for k in KEYS))
    _check("determinism: same seed -> identical representation",
           np.allclose(OP.word_representation(["a", "b", "c"], M1),
                       OP.word_representation(["a", "b", "c"], M2)))
    M3 = OP.random_operators(KEYS, d=4, seed=8)
    _check("determinism: different seed -> different operators",
           not np.allclose(M1["a"], M3["a"]))


def test_anagram_operator_vs_bag():
    M = OP.random_operators(KEYS, d=4, seed=5)
    vmap = OP.vector_map(M)
    w1 = ["a", "b", "c"]
    w2 = ["c", "b", "a"]           # anagram: same multiset, different order
    # additive / bag baselines are order-invariant -> anagrams identical
    _check("anagram: additive-vector model CANNOT distinguish anagrams",
           np.allclose(OP.additive_vector_model(w1, vmap),
                       OP.additive_vector_model(w2, vmap)))
    _check("anagram: bag-operator-sum CANNOT distinguish anagrams",
           np.allclose(OP.bag_operator_sum(w1, M), OP.bag_operator_sum(w2, M)))
    # operator product IS order-sensitive -> anagrams differ
    _check("anagram: operator model CAN distinguish anagrams",
           not np.allclose(OP.word_operator(w1, M), OP.word_operator(w2, M)))


def test_no_real_result_and_synthetic_only():
    res = RUN.run()
    _check("runner: NOT_RUN with no config", res["status"] == "NOT_RUN")
    _check("runner: computed is False", res["computed"] is False)
    _check("runner: no result", res["result"] is None)
    _check("runner: gated config still NOT_RUN", RUN.run({"x": 1})["status"] == "NOT_RUN")
    # synthetic-only: the operator module must not pull in a real varṇa lexicon
    _check("synthetic-only: no lexicon/g2p/table module imported by operators",
           not any(m in sys.modules for m in ("lexicon", "g2p", "table_structure", "varna_lens")))


def main():
    print("varna_operator — deterministic-operator scaffold synthetic tests (no real result)\n")
    for name, fn in sorted(globals().items()):
        if name.startswith("test_") and callable(fn):
            fn()
    print("\nAll varna_operator scaffolding tests passed.")


if __name__ == "__main__":
    main()
