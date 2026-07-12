"""Split generation + leakage prevention + train-only fitting discipline."""

from __future__ import annotations

import numpy as np

from cyber_security.behavioral_biometrics import baselines, features, splits, synthetic


def _cohort():
    coh = synthetic.generate_cohort(n_participants=10, sessions_per=4, second_device=True)
    return [features.extract(s) for s in coh]


def test_session_disjoint_no_leakage():
    recs = _cohort()
    plan = splits.session_disjoint(recs, seed=1)
    assert plan.enroll
    assert splits.check_leakage(plan, recs) == []


def test_enroll_and_test_sessions_disjoint():
    recs = _cohort()
    plan = splits.session_disjoint(recs, seed=1)
    for pid in plan.enroll:
        enroll_sids = {recs[i]["meta"]["session_id"] for i in plan.enroll[pid]}
        test_sids = {recs[i]["meta"]["session_id"]
                     for i in plan.genuine_test.get(pid, []) + plan.impostor_test.get(pid, [])}
        assert enroll_sids.isdisjoint(test_sids)


def test_live_impostor_only_uses_impostors():
    recs = _cohort()
    plan = splits.live_impostor_only(recs)
    for pid, idxs in plan.impostor_test.items():
        for i in idxs:
            assert recs[i]["meta"]["condition"] == "live_impostor"


def test_participant_disjoint_transfer_no_user_overlap():
    recs = _cohort()
    plan = splits.participant_disjoint(recs, seed=1)
    assert set(plan.train_participants).isdisjoint(set(plan.test_participants))
    assert splits.check_leakage(plan, recs) == []


def test_device_instance_split_crosses_devices():
    recs = _cohort()
    plan = splits.device_instance(recs)
    assert plan.enroll  # cohort has a second device
    for pid in plan.enroll:
        edev = {recs[i]["meta"]["device_id"] for i in plan.enroll[pid]}
        tdev = {recs[i]["meta"]["device_id"] for i in plan.genuine_test.get(pid, [])}
        assert edev.isdisjoint(tdev)


def test_injected_leakage_is_caught():
    recs = _cohort()
    plan = splits.session_disjoint(recs, seed=1)
    pid = next(iter(plan.enroll))
    # deliberately leak an enroll session into the test set
    plan.genuine_test[pid] = plan.genuine_test.get(pid, []) + [plan.enroll[pid][0]]
    assert splits.check_leakage(plan, recs)


def test_standardizer_fits_on_train_only():
    """The standardizer used for scoring must be fit only on enroll (train) vectors."""
    recs = _cohort()
    plan = splits.session_disjoint(recs, seed=1)
    train_idx = plan.all_train_indices()
    train_dicts = [baselines.build_marginal(recs[i]) for i in train_idx]
    names, Xtr = features.vectorize_dicts(train_dicts)
    from cyber_security.behavioral_biometrics.numerics import Standardizer
    std = Standardizer.fit(Xtr)
    # the fitted mean must equal the mean of TRAIN vectors, independent of test rows
    assert np.allclose(std.mean, Xtr.mean(axis=0))
