"""Mock regimes + metrics."""

from __future__ import annotations

import numpy as np

from cyber_security.behavioral_biometrics.study import metrics, mockdata
from cyber_security.behavioral_biometrics.version import ORIGIN_MOCK


def test_all_regimes_generate_and_marked_mock():
    for regime in mockdata.ALL_REGIMES:
        fx = mockdata.generate(regime, seed=1)
        assert fx["origin"] == ORIGIN_MOCK
        if fx["kind"] == "cohort":
            assert all(r["meta"]["data_origin"] == ORIGIN_MOCK for r in fx["records"])
            assert fx["records"]


def test_cohort_ground_truth_present():
    d = mockdata.make_cohort("KEYBOARD_ONLY_SIGNAL", seed=1)
    assert d["ground_truth"]["kbd"] > 0 and d["ground_truth"]["ptr"] == 0


def test_deterministic_generation():
    a = mockdata.make_cohort("COUPLING_ONLY_SIGNAL", seed=3)["records"]
    b = mockdata.make_cohort("COUPLING_ONLY_SIGNAL", seed=3)["records"]
    assert [r["marginal"] for r in a] == [r["marginal"] for r in b]


def test_auc_reference():
    s = np.array([0.9, 0.8, 0.4, 0.2]); y = np.array([1, 0, 1, 0])
    assert abs(metrics.summary(s, y)["auc"] - 0.75) < 1e-9


def test_eer_and_tar():
    rng = np.random.default_rng(0)
    pos = rng.normal(1.0, 1.0, 200); neg = rng.normal(-1.0, 1.0, 200)
    s = np.concatenate([pos, neg]); y = np.concatenate([np.ones(200), np.zeros(200)])
    m = metrics.summary(s, y, 0.05)
    assert 0.0 <= m["eer"] <= 0.5
    assert 0.0 <= m["tar_at_far"] <= 1.0
    assert 0.0 <= m["balanced_accuracy"] <= 1.0


def test_roc_and_det_monotone():
    s = np.array([0.9, 0.7, 0.6, 0.3, 0.1]); y = np.array([1, 1, 0, 1, 0])
    roc = metrics.roc_curve(s, y)
    assert roc["fpr"] == sorted(roc["fpr"])
    det = metrics.det_curve(s, y)
    assert len(det["fpr"]) == len(det["fnr"])


def test_clustered_bootstrap_reproducible():
    rng = np.random.default_rng(1)
    s = rng.normal(0, 1, 200); y = (rng.random(200) < 0.5).astype(int); g = rng.integers(0, 10, 200)
    a = metrics.clustered_bootstrap_ci(s, y, g, iters=200, seed=5)
    b = metrics.clustered_bootstrap_ci(s, y, g, iters=200, seed=5)
    assert a == b
