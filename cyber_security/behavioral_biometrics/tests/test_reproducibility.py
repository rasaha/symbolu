"""Determinism: same inputs + seeds -> identical features, analyses, verdicts."""

from __future__ import annotations

from cyber_security.behavioral_biometrics import (
    analysis,
    features,
    pilot,
    splits,
    synthetic,
)


def test_synthetic_generation_reproducible():
    a = synthetic.generate_session(participant="p", device="d", task_id="t", session_id="s",
                                   trial_id="t", seed=7, coupling_user_gain=0.5)
    b = synthetic.generate_session(participant="p", device="d", task_id="t", session_id="s",
                                   trial_id="t", seed=7, coupling_user_gain=0.5)
    assert a["events"] == b["events"]


def test_cohort_reproducible():
    a = synthetic.generate_cohort(n_participants=8, sessions_per=3, seed=1)
    b = synthetic.generate_cohort(n_participants=8, sessions_per=3, seed=1)
    assert [s["session_meta"]["session_id"] for s in a] == \
           [s["session_meta"]["session_id"] for s in b]


def test_feature_extraction_reproducible():
    s = synthetic.generate_session(participant="p", device="d", task_id="t", session_id="s",
                                   trial_id="t", seed=9, coupling_user_gain=0.6)
    assert features.extract(s) == features.extract(s)


def test_analysis_reproducible():
    coh = synthetic.generate_cohort(n_participants=10, sessions_per=4, coupling_user_gain=0.5)
    recs = [features.extract(s) for s in coh]
    plan = splits.session_disjoint(recs, seed=1)
    c1 = analysis.marginal_identity(recs, plan)
    c2 = analysis.marginal_identity(recs, plan)
    assert c1["auc"] == c2["auc"]
    d1 = analysis.coupling_residual(recs, plan)
    d2 = analysis.coupling_residual(recs, plan)
    assert d1["gain_vs_marginal"] == d2["gain_vs_marginal"]


def test_pilot_report_reproducible():
    coh = synthetic.generate_cohort(n_participants=10, sessions_per=4, coupling_user_gain=0.5)
    r1 = pilot.run_pilot(coh)
    r2 = pilot.run_pilot(coh)
    assert r1["C_marginal_identity"]["auc"] == r2["C_marginal_identity"]["auc"]
    assert r1["marginal_signal_verdict"]["verdict"] == r2["marginal_signal_verdict"]["verdict"]
