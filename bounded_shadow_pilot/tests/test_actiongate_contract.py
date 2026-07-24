"""Phase 5 tests. Locks the native ActionGate contract's mandatory claim: all six native outcomes are
preserved with zero loss, and no safety-relevant outcome is ever collapsed. Read-only; non-enforcing.
"""
from bounded_shadow_pilot import actiongate_contract as ac


def test_all_six_native_outcomes_preserved():
    c = ac.conformance()
    assert c["all_native_outcomes_preserved"] is True
    assert c["outcomes_preserved"] == 6
    got = {r["expected"]: r["native_outcome"] for r in c["rows"]}
    for name in ac.NATIVE_OUTCOMES:
        assert got[name] == name, (name, got[name])          # verbatim, never collapsed


def test_metadata_preserved_per_outcome():
    rows = {r["expected"]: r for r in ac.conformance()["rows"]}
    # every outcome carries action + policy hash and a state trace
    for name in ac.NATIVE_OUTCOMES:
        assert rows[name]["has_action_hash"], name
        assert rows[name]["has_policy_hash"], name
        assert rows[name]["has_state_trace"], name
    # ALLOW_WITH_CONSTRAINTS carries constraints
    assert rows["ALLOW_WITH_CONSTRAINTS"]["applied_constraints_present"] is True


def test_semantic_roles_distinct():
    rows = {r["expected"]: r for r in ac.conformance()["rows"]}
    assert rows["REQUEST_MORE_EVIDENCE"]["semantics"].get("requires_evidence") is True
    assert rows["SIMULATE_AND_RETRY"]["semantics"].get("requires_simulation") is True
    assert rows["ESCALATE_TO_HUMAN"]["semantics"].get("requires_human") is True
    assert rows["DENY"]["semantics"].get("blocks") is True
    assert rows["ALLOW"]["semantics"].get("permits") is True


def test_no_safety_relevant_outcome_lost_no_blocker():
    s = ac.semantic_loss_report()
    assert s["native_semantic_loss_pct"] == 0.0
    assert s["safety_relevant_outcomes_lost_under_native_contract"] == []
    assert s["blocker"] is False


def test_native_contract_recovers_shadow_collapsed_outcomes():
    s = ac.semantic_loss_report()
    assert s["outcomes_collapsed_under_shadow_mapping"] == 3
    assert set(s["recovered_by_native_contract"]) == {
        "ALLOW_WITH_CONSTRAINTS", "REQUEST_MORE_EVIDENCE", "SIMULATE_AND_RETRY"}


def test_gate_error_fails_closed_non_native():
    # A malformed operation must fail closed to a non-native, blocking, never-permissive decision.
    d = ac.evaluate_raw_operation("NOT_A_REAL_OPERATION")
    assert d.is_native is False
    assert d.permits is False
    assert d.blocks is True or d.fail_closed is True


def test_no_action_returns_none():
    assert ac.evaluate(None) is None


def test_determinism():
    a = ac.conformance()
    b = ac.conformance()
    assert [r["native_outcome"] for r in a["rows"]] == [r["native_outcome"] for r in b["rows"]]
