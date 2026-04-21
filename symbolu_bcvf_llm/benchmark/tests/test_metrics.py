"""§6.5 metrics tests — accuracy, McNemar, latency, §1.10 classification."""

from __future__ import annotations

import numpy as np
import pytest

from symbolu_bcvf_llm.benchmark.metrics import (
    accuracy,
    classify_phase_six_result,
    latency_stats,
    mcnemar_paired,
)


def test_accuracy_basic():
    assert accuracy(np.array([True, True, False, True])) == 0.75
    assert accuracy(np.array([], dtype=bool)) == 0.0


def test_mcnemar_all_agree_returns_p_1():
    a = np.array([True, True, False, False])
    b = a.copy()
    r = mcnemar_paired(a, b)
    assert r.b == 0
    assert r.c == 0
    assert r.p_value_exact == 1.0


def test_mcnemar_totally_discordant_p_small():
    a = np.array([True] * 10 + [False] * 10)
    b = np.array([False] * 10 + [True] * 10)
    r = mcnemar_paired(a, b)
    assert r.b == 10
    assert r.c == 10
    # b == c, so exact two-sided p should be 1.0 (balanced discordance).
    assert r.p_value_exact == pytest.approx(1.0)


def test_mcnemar_unbalanced_discordance_small_p():
    a = np.array([True] * 8 + [False] * 2)
    b = np.array([False] * 8 + [True] * 2)
    r = mcnemar_paired(a, b)
    assert r.b == 8
    assert r.c == 2
    # 8 vs 2 out of 10 discordant pairs → pretty small p.
    assert r.p_value_exact < 0.2


def test_mcnemar_shape_mismatch_raises():
    with pytest.raises(ValueError):
        mcnemar_paired(np.array([True, False]), np.array([True]))


def test_latency_stats_basic():
    x = np.array([0.1, 0.2, 0.3, 0.4])
    s = latency_stats(x)
    assert s.n == 4
    assert s.mean_s == pytest.approx(0.25)
    assert s.median_s == pytest.approx(0.25)
    assert s.min_s == 0.1
    assert s.max_s == 0.4


def test_classify_pass():
    trust = np.array([True] * 12 + [False] * 2)
    blend = np.array([True] * 9 + [False] * 5)
    # delta_pp = (12/14 - 9/14)*100 ≈ 21 pp → clear PASS.
    lat_trust = np.full(14, 0.1)
    lat_blend = np.full(14, 0.1)
    v = classify_phase_six_result(trust, blend, lat_trust, lat_blend)
    assert v.classification == "PASS"


def test_classify_null_within_half_pp():
    N = 200
    trust = np.zeros(N, dtype=bool); trust[:100] = True
    blend = np.zeros(N, dtype=bool); blend[:100] = True
    lat = np.full(N, 0.1)
    v = classify_phase_six_result(trust, blend, lat, lat)
    assert v.classification == "NULL"


def test_classify_regression():
    N = 100
    trust = np.zeros(N, dtype=bool); trust[:50] = True
    blend = np.zeros(N, dtype=bool); blend[:60] = True
    lat = np.full(N, 0.1)
    v = classify_phase_six_result(trust, blend, lat, lat)
    assert v.classification == "REGRESSION"
    assert v.delta_pp == pytest.approx(-10.0)


def test_classify_unviable_cost():
    N = 20
    trust = np.ones(N, dtype=bool)
    blend = np.ones(N, dtype=bool)
    lat_blend = np.full(N, 0.1)
    lat_trust = np.full(N, 0.7)  # 7× blend
    v = classify_phase_six_result(trust, blend, lat_trust, lat_blend)
    assert v.classification == "UNVIABLE_COST"


def test_classify_ambiguous_between_bands():
    N = 200
    # 1 pp delta — above null band (0.5 pp) but below success band (2 pp).
    trust = np.zeros(N, dtype=bool); trust[:101] = True
    blend = np.zeros(N, dtype=bool); blend[:100] = True
    lat = np.full(N, 0.1)
    v = classify_phase_six_result(trust, blend, lat, lat)
    assert v.classification == "AMBIGUOUS"
