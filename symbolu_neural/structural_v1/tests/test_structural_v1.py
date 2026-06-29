"""Minimal correctness tests for Stage A machinery."""
from __future__ import annotations

import numpy as np

from symbolu_neural.structural_v1.features import feature_matrix, decompose, N_UNITS, K
from symbolu_neural.structural_v1.operators import (
    GENERATORS, D, assert_generator_algebra, commuting_generator_pairs,
    feature_operators, random_orthogonal_operators, weak_coupling_operators, expm,
)
from symbolu_neural.structural_v1.engine import read_product, read_bag, S0
from symbolu_neural.structural_v1.metrics import (
    order_effect_matrix, mean_standardized_order_effect, structure_score,
    effective_rank, commuting_vs_coupling_coeffs,
)
from symbolu_neural.structural_v1.gate import run_stage_a, SEED


def test_feature_chart_shape_and_range():
    F = feature_matrix()
    assert F.shape == (N_UNITS, K)
    assert np.abs(F).max() <= 1.0 + 1e-12


def test_decompose_surfaces_warnings_no_silent_fallback():
    idx, warns = decompose("p@k")        # '@' not in chart
    assert any("not in chart" in w for w in warns)
    idx2, warns2 = decompose("###")      # all dropped -> empty
    assert any("empty unit sequence" in w for w in warns2)


def test_generators_skew_and_algebra():
    assert_generator_algebra()           # raises if violated
    for G in GENERATORS:
        assert np.allclose(G, -G.T)
    # disjoint factors commute; coupling pairs do not
    assert (0, 1) in commuting_generator_pairs()
    assert (0, 3) not in commuting_generator_pairs()
    assert (1, 2) not in commuting_generator_pairs()


def test_expm_orthogonal_and_matches_rotation():
    # expm of a skew generator is orthogonal
    M = expm(0.7 * GENERATORS[0])
    assert np.allclose(M @ M.T, np.eye(D), atol=1e-9)
    # G_A = J (x) I rotates the (0,2) plane by theta
    theta = 0.5
    R = expm(theta * GENERATORS[0])
    assert np.isclose(R[0, 0], np.cos(theta), atol=1e-8)
    assert np.isclose(R[2, 0], np.sin(theta), atol=1e-8)


def test_feature_operators_orthogonal():
    F = feature_matrix()
    ops = feature_operators(F)
    assert len(ops) == N_UNITS
    for M in ops:
        assert np.allclose(M @ M.T, np.eye(D), atol=1e-6)


def test_bag_is_order_blind_but_product_is_not():
    F = feature_matrix()
    ops = feature_operators(F)
    seq = [0, 5, 9, 2]
    rev = list(reversed(seq))
    # bag identical under permutation
    assert np.allclose(read_bag(seq, F), read_bag(rev, F))
    # product generally differs (operators chosen to be non-commuting)
    assert not np.allclose(read_product(seq, ops), read_product(rev, ops))


def test_order_effect_matrix_symmetric_zero_diag_and_positive():
    F = feature_matrix()
    ops = feature_operators(F)
    B, E = order_effect_matrix(ops)
    assert np.allclose(np.diag(B), 0.0)
    assert np.allclose(B, B.T)
    assert mean_standardized_order_effect(B) > 0.0


def test_random_orthogonal_are_orthogonal():
    rng = np.random.default_rng(0)
    for M in random_orthogonal_operators(5, rng):
        assert np.allclose(M @ M.T, np.eye(D), atol=1e-9)


def test_weak_coupling_suppresses_order_effect():
    F = feature_matrix()
    strong = feature_operators(F)
    weak = weak_coupling_operators(F, eps=1e-2)
    Bs, _ = order_effect_matrix(strong)
    Bw, _ = order_effect_matrix(weak)
    # weak coupling order-effect is far smaller (O(eps^2))
    assert mean_standardized_order_effect(Bw) < 0.05 * mean_standardized_order_effect(Bs)


def test_commuting_coefficient_near_zero():
    F = feature_matrix()
    ops = feature_operators(F)
    B, _ = order_effect_matrix(ops)
    c = commuting_vs_coupling_coeffs(B, F)
    # commuting-pair wedge should contribute ~nothing vs coupling
    assert c["coupling_coef_mean_abs"] > c["commuting_coef_mean_abs"]


def test_structure_score_deterministic():
    F = feature_matrix()
    ops = feature_operators(F)
    B, _ = order_effect_matrix(ops)
    s1 = structure_score(B, F, seed=SEED)
    s2 = structure_score(B, F, seed=SEED)
    assert s1 == s2


def test_stage_a_runs_and_is_deterministic():
    r1 = run_stage_a()
    r2 = run_stage_a()
    assert r1.verdict in {"PASS", "FAIL", "INCONCLUSIVE"}
    assert r1.verdict == r2.verdict
    assert len(r1.gates) == 4
    # diagnostics reproduce exactly (fixed seeds)
    assert r1.diagnostics["real_structure_score"] == r2.diagnostics["real_structure_score"]


_TESTS = [v for k, v in dict(globals()).items() if k.startswith("test_")]

if __name__ == "__main__":
    failed = 0
    for t in _TESTS:
        try:
            t()
            print(f"PASS {t.__name__}")
        except Exception as e:  # noqa: BLE001
            failed += 1
            print(f"FAIL {t.__name__}: {e}")
    print(f"\n{len(_TESTS) - failed}/{len(_TESTS)} passed")
    raise SystemExit(1 if failed else 0)
