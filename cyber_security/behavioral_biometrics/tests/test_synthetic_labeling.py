"""Synthetic data is always visibly marked and never yields a positive verdict."""

from __future__ import annotations

from cyber_security.behavioral_biometrics import features, pilot, synthetic, verdicts
from cyber_security.behavioral_biometrics.version import SYNTHETIC_MARKER


def test_single_session_marked():
    s = synthetic.generate_session(participant="p", device="d", task_id="t", session_id="s",
                                   trial_id="t", seed=1)
    assert s["session_meta"]["data_provenance"] == SYNTHETIC_MARKER
    assert "SYNTHETIC_TEST_ONLY" in s["session_meta"]["notes"]


def test_cohort_all_marked():
    coh = synthetic.generate_cohort(n_participants=6, sessions_per=3)
    assert all(s["session_meta"]["data_provenance"] == SYNTHETIC_MARKER for s in coh)


def test_feature_record_carries_synthetic_provenance():
    s = synthetic.generate_session(participant="p", device="d", task_id="t", session_id="s",
                                   trial_id="t", seed=1)
    rec = features.extract(s)
    assert rec["meta"]["data_provenance"] == SYNTHETIC_MARKER


def test_pilot_report_flags_synthetic_and_refuses_verdicts():
    coh = synthetic.generate_cohort(n_participants=12, sessions_per=4, coupling_user_gain=0.6,
                                    second_device=True)
    report = pilot.run_pilot(coh)
    assert report["data_provenance"] == "SYNTHETIC_TEST_ONLY"
    assert report["marginal_signal_verdict"]["verdict"] == verdicts.MARGINAL_SYNTHETIC
    assert report["coupling_verdict"]["verdict"] == verdicts.COUPLING_SYNTHETIC
    # but instrumentation IS allowed on synthetic (it concerns the instrument)
    assert report["instrumentation_verdict"]["verdict"] in ("INSTRUMENTATION_READY",
                                                            "INSTRUMENTATION_DEGRADED",
                                                            "INSTRUMENTATION_NOT_READY")


def test_no_positive_biometric_verdict_from_synthetic():
    coh = synthetic.generate_cohort(n_participants=12, sessions_per=4, coupling_user_gain=1.0)
    recs = [features.extract(s) for s in coh]
    assert verdicts.data_is_synthetic(recs)
    assert not verdicts.all_real(recs)
