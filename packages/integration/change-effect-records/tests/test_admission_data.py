"""The admission succession and control-register tables — that they are data, and correct.

These tables exist so that two implementations cannot quietly disagree about what the
legal successions are. The tests check the tables say what the rule says, and that this
package does not act on them.
"""

from __future__ import annotations

import pytest

from ugence_change_effect_records import (
    COMMITTING_CLAIM,
    CONTROL_REGISTER_TRANSITIONS,
    DOCUMENTARY_CLAIM,
    LEGAL_SUCCESSIONS,
    RECOVERY_OUTCOMES,
    RESERVATION_REFUSAL_BY_STATE,
    TERMINAL_CONTROL_STATES,
    ControlRegisterState,
)


def test_succession_is_a_function_not_a_relation():
    """Every transition has at most one legal successor kind."""

    for transition, successors in LEGAL_SUCCESSIONS.items():
        assert len(successors) <= 1, transition


def test_a_cancel_claim_is_terminal_and_an_apply_claim_is_not():
    assert LEGAL_SUCCESSIONS["ADMISSION_CLAIM:CANCEL"] == ()
    assert LEGAL_SUCCESSIONS["ADMISSION_CLAIM:APPLY"] == ("ADMISSION_COMPLETE",)


def test_only_outcome_unknown_admits_a_human_resolution():
    assert LEGAL_SUCCESSIONS["ADMISSION_COMPLETE:OUTCOME_UNKNOWN"] == ("ADMISSION_RESOLVE",)
    assert LEGAL_SUCCESSIONS["ADMISSION_COMPLETE:APPLIED"] == ()
    assert LEGAL_SUCCESSIONS["ADMISSION_COMPLETE:FAILED"] == ()


def test_apply_commits_execution_and_cancel_documents():
    assert COMMITTING_CLAIM == "APPLY" and DOCUMENTARY_CLAIM == "CANCEL"


def test_revoked_is_terminal_absolutely():
    assert TERMINAL_CONTROL_STATES == frozenset({"REVOKED"})
    assert not [t for t in CONTROL_REGISTER_TRANSITIONS if t[0] == "REVOKED"], (
        "nothing returns from REVOKED")


def test_every_revocable_state_can_reach_revoked():
    revocable = {ControlRegisterState.ACTIVE.value,
                 ControlRegisterState.APPLY_COMMITTED.value,
                 ControlRegisterState.APPLIED.value}
    assert {f for f, t, _ in CONTROL_REGISTER_TRANSITIONS if t == "REVOKED"} == revocable


def test_a_completion_moves_the_register_only_out_of_apply_committed():
    """The recorded erratum to 4.2.10: a completion never resurrects a revoked resolution."""

    by_completion = [t for t in CONTROL_REGISTER_TRANSITIONS if "completion" in t[2]]
    assert by_completion, "the table must say what a completion does"
    assert all(f == ControlRegisterState.APPLY_COMMITTED.value for f, _, _ in by_completion)


def test_failed_returns_to_active_and_applied_is_terminal_for_the_admission():
    targets = {t for f, t, by in CONTROL_REGISTER_TRANSITIONS if "FAILED" in by}
    assert "ACTIVE" in targets
    assert ("APPLY_COMMITTED", "APPLIED", ) == tuple(
        (f, t) for f, t, by in CONTROL_REGISTER_TRANSITIONS if "APPLIED completion" in by)[0]


def test_the_three_reservation_refusals_are_distinct():
    assert len(set(RESERVATION_REFUSAL_BY_STATE.values())) == 3
    assert RESERVATION_REFUSAL_BY_STATE["REVOKED"] == "RESOLUTION_REVOKED"
    assert RESERVATION_REFUSAL_BY_STATE["APPLIED"] == "RESOLUTION_ALREADY_APPLIED"
    assert RESERVATION_REFUSAL_BY_STATE["APPLY_COMMITTED"] == "ADMISSION_IN_FLIGHT"
    assert "ACTIVE" not in RESERVATION_REFUSAL_BY_STATE, "ACTIVE is the state that permits"


def test_the_recovery_rule_has_an_outcome_for_every_case():
    assert set(RECOVERY_OUTCOMES) == {
        "TAG_PRESENT_POST_STATE_MATCHES", "TAG_ABSENT_PRE_STATE_MATCHES", "NEITHER"}
    assert RECOVERY_OUTCOMES["NEITHER"] == "OUTCOME_UNKNOWN"


def test_the_tables_are_read_only():
    with pytest.raises(TypeError):
        LEGAL_SUCCESSIONS["ADMISSION_RESERVE"] = ()  # type: ignore[index]
    with pytest.raises(TypeError):
        RESERVATION_REFUSAL_BY_STATE["ACTIVE"] = "x"  # type: ignore[index]
