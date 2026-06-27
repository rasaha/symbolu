"""Tests for the complementarity probe harness.

These test the MACHINERY (determinism, shapes, controls, alignment) — not the
scientific hypothesis. Run: python -m pytest symbolu_neural/complementarity_probe/tests
or simply: python symbolu_neural/complementarity_probe/tests/test_probe.py
"""
from __future__ import annotations

import numpy as np

from symbolu_neural.complementarity_probe.symbolu_engine import SymbolUEngine
from symbolu_neural.complementarity_probe import nulls, metrics, exp1_invariance


def test_engine_deterministic_and_real_mappers():
    eng = SymbolUEngine()
    a = eng.encode_word("happy")
    b = eng.encode_word("happy")
    assert a.vritti == b.vritti
    assert "vritti_mapper" in a.active_components
    assert abs(sum(a.vritti) - 1.0) < 1e-9
    assert len(a.vritti) == 5


def test_synonyms_scatter_more_than_repeats():
    """A word with itself is identical (dist 0); true synonyms differ -> the
    engine is phonological, exactly the property exp1 measures."""
    eng = SymbolUEngine()
    happy = np.asarray(eng.vritti_vec("happy"))
    glad = np.asarray(eng.vritti_vec("glad"))
    assert np.linalg.norm(happy - happy) == 0.0
    assert np.linalg.norm(happy - glad) > 0.0  # synonyms are NOT invariant


def test_u_matrix_shape_and_dim():
    eng = SymbolUEngine()
    texts = ["happy", "the cat sat", "glad"]
    U = nulls.symbolu_matrix(texts, eng)
    assert U.shape == (3, eng.dim)


def test_nulls_aligned_and_matched_dim():
    eng = SymbolUEngine()
    texts = ["happy", "sad", "big", "small", "fast", "slow"]
    U = nulls.symbolu_matrix(texts, eng)
    alln = nulls.all_nulls(texts, U, seed=0)
    assert alln["random"].shape == U.shape           # matched dim
    assert alln["shuffled_U"].shape == U.shape
    assert len(alln["surface"]) == len(texts)
    assert len(alln["phonological"]) == len(texts)
    # shuffled_U is a permutation: same row-multiset, different order (n>1)
    assert sorted(map(tuple, alln["shuffled_U"].round(6))) == \
        sorted(map(tuple, U.round(6)))


def test_invariance_index_bounds():
    # identical groups -> within==between -> index ~ 0
    g = [np.array([[1.0, 0.0], [1.0, 0.0]]), np.array([[1.0, 0.0], [1.0, 0.0]])]
    r = metrics.invariance_index(g)
    assert abs(r["index"]) < 1e-6
    # well-separated groups -> index > 0
    g2 = [np.array([[0.0, 0.0], [0.01, 0.0]]), np.array([[10.0, 0.0], [10.01, 0.0]])]
    assert metrics.invariance_index(g2)["index"] > 0.5


def test_cv_probe_runs_and_bounded():
    rng = np.random.default_rng(0)
    X = rng.standard_normal((40, 6))
    y = (X[:, 0] > 0).astype(int)
    acc = metrics.cv_probe_accuracy(X, y, folds=4)
    assert 0.0 <= acc <= 1.0
    assert acc > 0.6  # separable -> probe should learn it


def test_exp1_runs_end_to_end():
    r = exp1_invariance.run(n_perm=100, seed=0)
    assert r["n_groups"] > 0
    assert "index" in r["symbolu_vritti"]
    assert 0.0 <= r["symbolu_vritti"]["p_value"] <= 1.0


if __name__ == "__main__":
    fns = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    passed = 0
    for fn in fns:
        fn()
        print(f"PASS {fn.__name__}")
        passed += 1
    print(f"\n{passed}/{len(fns)} tests passed")
