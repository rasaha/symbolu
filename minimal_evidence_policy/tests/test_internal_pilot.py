"""Phase 10 tests: internal pilot is non-enforcing, audited, replayable, preserves native ActionGate,
and shows the minimal policy safe-and-useful vs the comparison policies."""
from minimal_evidence_policy.internal_pilot import pilot


def test_non_enforcing_audited_replayable():
    m = pilot.run()
    assert m["non_enforcing"] is True
    assert m["no_external_actions"] is True and m["no_external_customer_data"] is True
    assert m["audit_completeness"] == 1.0
    assert m["replay_deterministic"] is True


def test_native_actiongate_preserved():
    m = pilot.run()
    assert m["native_actiongate_outcomes_preserved"] is True
    assert m["native_actiongate_semantic_loss_pct"] == 0.0


def test_minimal_policy_safe_and_useful_in_pilot():
    c = pilot.run()["policy_comparison"]
    mp = c["minimal_policy"]["held_out_natural"]
    assert mp["unsafe_allow"] == 0
    assert mp["clean_allow_rate"] > c["frozen_natural_pilot_derivation"]["held_out_natural"]["clean_allow_rate"]
