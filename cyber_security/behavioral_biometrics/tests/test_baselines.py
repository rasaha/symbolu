"""Identity baselines + temporal observer + fusion."""

from __future__ import annotations

import numpy as np

from cyber_security.behavioral_biometrics import baselines, features, splits, synthetic
from cyber_security.behavioral_biometrics.numerics import GaussianPrototype, auc


def _cohort(**kw):
    coh = synthetic.generate_cohort(n_participants=12, sessions_per=4, **kw)
    return [features.extract(s) for s in coh]


def test_prototype_identity_auc_above_chance_on_synthetic():
    recs = _cohort()
    plan = splits.session_disjoint(recs, seed=1)
    res = baselines.evaluate_identity(recs, plan, baselines.build_marginal, model="prototype")
    assert res["usable"]
    assert res["auc"] > 0.6  # SYNTHETIC_TEST_ONLY separability (not a biometric claim)


def test_mahalanobis_usable():
    recs = _cohort()
    plan = splits.session_disjoint(recs, seed=1)
    res = baselines.evaluate_identity(recs, plan, baselines.build_marginal, model="mahalanobis")
    assert res["usable"]


def test_auc_metric_matches_reference():
    scores = np.array([0.9, 0.8, 0.4, 0.2])
    labels = np.array([1, 0, 1, 0])
    # pairs genuine>impostor: (0.9>0.8),(0.9>0.2),(0.4<0.8 -> 0),(0.4>0.2) => 3/4
    assert abs(auc(scores, labels) - 0.75) < 1e-9


def test_quality_weighted_fusion_no_coupling():
    recs = _cohort()
    plan = splits.session_disjoint(recs, seed=1)
    res = baselines.quality_weighted_fusion(recs, plan)
    assert res["usable"]
    assert 0.0 <= res["auc"] <= 1.0


def test_kalman_llt_cusum_flags_shift():
    base = np.zeros(60)
    shifted = np.concatenate([np.zeros(30), 5 + np.zeros(30)])
    r_base = baselines.kalman_llt_cusum(base)
    r_shift = baselines.kalman_llt_cusum(shifted)
    assert r_shift["cusum_max"] > r_base["cusum_max"]


def test_temporal_observer_is_deterministic():
    s = synthetic.generate_session(participant="p", device="d", task_id="t", session_id="s",
                                   trial_id="t", seed=1)
    series = baselines.session_rate_series(s)
    a = baselines.kalman_llt_cusum(series)
    b = baselines.kalman_llt_cusum(series)
    assert np.allclose(a["innovation"], b["innovation"])


def test_gaussian_prototype_mahalanobis_zero_at_mean():
    X = np.random.default_rng(0).normal(size=(50, 4))
    g = GaussianPrototype.fit(X, ridge=1e-3)
    assert g.mahalanobis(g.mean.reshape(1, -1))[0] < 1e-6
