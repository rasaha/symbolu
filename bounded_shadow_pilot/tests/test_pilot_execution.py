"""Phase 19 test: the frozen pilot execution completes with guards intact, no stop condition, zero
unsafe permits, non-enforcing, and native ActionGate outcomes preserved.
"""
from bounded_shadow_pilot import pilot_execution as pe


def test_pilot_completes_without_stop():
    m = pe.run()
    assert m["guards"]["guards_ok"] is True
    assert m["stop_conditions"]["should_stop"] is False
    assert m["safety"]["unsafe_permit"] == 0
    assert m["safety"]["all_non_enforcing"] is True
    assert m["pilot_outcome"] == "COMPLETED_NO_STOP"


def test_native_actiongate_outcomes_are_native():
    m = pe.run()
    na = m["native_actiongate"]
    # any derived action carries a native outcome (never GATE_ERROR / collapsed)
    for outcome in na["native_outcome_distribution"]:
        assert outcome in ("ALLOW", "ALLOW_WITH_CONSTRAINTS", "DENY", "ESCALATE_TO_HUMAN",
                           "REQUEST_MORE_EVIDENCE", "SIMULATE_AND_RETRY")
