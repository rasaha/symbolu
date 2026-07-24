"""M11 tests - pilot stop conditions (Phase 17)."""
from reviewer_ready_pilot import stop_conditions as sc
from reviewer_ready_pilot import metrics as m


def test_no_signals_no_metrics_no_stop():
    r = sc.evaluate({}, {"status": m.STATUS_NO_HUMAN})
    assert r.should_stop is False
    assert not r.immediate_fired and not r.cumulative_fired


def test_immediate_enforcement_halts():
    r = sc.evaluate({"enforcement_attempt": True}, {"status": m.STATUS_NO_HUMAN})
    assert r.should_stop and "enforcement_attempt" in r.immediate_fired


def test_immediate_blinding_and_actiongate_and_data():
    for cond in ("blinding_breach", "native_actiongate_semantic_loss", "prohibited_or_unapproved_data",
                 "simulation_labeled_as_human_validation", "external_customer_onboarded"):
        r = sc.evaluate({cond: True}, {"status": m.STATUS_NO_HUMAN})
        assert r.should_stop and cond in r.immediate_fired


def test_no_human_evidence_cannot_fire_cumulative():
    # even with alarming-looking numbers, if status is not COMPUTED nothing cumulative fires
    metrics = {"status": m.STATUS_NO_HUMAN, "reviewer_system_agreement": 0.0, "override_rate": 1.0}
    assert sc.check_cumulative(metrics) == []


def test_cumulative_fires_on_real_breach():
    metrics = {"status": m.STATUS_OK, "reviewer_reviewer_agreement": 0.5,
               "reviewer_system_agreement": 0.5, "override_rate": 0.6, "trap_catch_rate": 0.5}
    fired = sc.check_cumulative(metrics)
    assert "reviewer_system_agreement_below_threshold" in fired
    assert "override_rate_excessive" in fired
    assert "trap_catch_rate_below_threshold" in fired


def test_cumulative_clean_metrics_no_fire():
    metrics = {"status": m.STATUS_OK, "reviewer_reviewer_agreement": 0.95,
               "reviewer_system_agreement": 0.9, "override_rate": 0.1, "trap_catch_rate": 0.95}
    assert sc.check_cumulative(metrics) == []


def test_fail_closed_on_erroring_signal():
    class Bad(dict):
        def get(self, k, d=None):
            raise RuntimeError("boom")
    fired = sc.check_immediate(Bad())
    assert fired  # every immediate condition treated as fired
