"""Deterministic decisions, runtime state machine, and session serialization."""

from __future__ import annotations

import pytest

from action_gateway import ToolRequest
from action_gateway import state as S
from action_gateway._ref import errors as E
from action_gateway.errors import IllegalStateError
from action_gateway.gateway import Gateway
from tests.helpers import approved_terraform, make_gateway, sim


def test_same_inputs_same_decision_across_gateways():
    outs = []
    hashes = []
    for _ in range(2):
        gw = make_gateway()
        s = gw.submit_action(ToolRequest(
            tool="filesystem", verb="write", target=["file://d/f.txt"],
            args={"unbounded": False, "affected_count": "1", "content": "x"}))
        d = gw.evaluate_action(s["request_id"], evidence=[sim(s["action_hash"], gw, "MEDIUM")])
        outs.append(d["outcome"])
        hashes.append(s["action_hash"])
    assert outs[0] == outs[1]
    assert hashes[0] == hashes[1]  # deterministic action hash


def test_repeated_evaluation_is_stable():
    gw = make_gateway()
    s = gw.submit_action(ToolRequest(tool="terraform", verb="apply",
                                     target=["svc://x"], args={}))
    # DEPLOY with no evidence: missing signed_artifact (REQUEST_MORE_EVIDENCE)
    # outranks missing simulation by precedence; the result is stable.
    o1 = gw.evaluate_action(s["request_id"])["outcome"]
    o2 = gw.evaluate_action(s["request_id"])["outcome"]
    assert o1 == o2 == "REQUEST_MORE_EVIDENCE"
    assert gw.status(s["request_id"])["state"] == S.PENDING


def test_illegal_runtime_transition_blocked():
    gw = make_gateway()
    s = approved_terraform(gw)
    gw.execute_action(s["request_id"])  # -> COMPLETED (terminal)
    # cannot re-evaluate a terminal request
    with pytest.raises(IllegalStateError):
        gw.evaluate_action(s["request_id"])


def test_runtime_states_are_not_spec_states():
    # runtime lifecycle states are distinct from the frozen decision trace states
    assert set(S.ALL) == {"PENDING", "APPROVED", "EXECUTING", "COMPLETED",
                          "FAILED", "DENIED", "ESCALATED", "EXPIRED"}
    # the frozen spec's state trace lives in the harness decision, untouched
    gw = make_gateway()
    s = approved_terraform(gw)
    dec = gw.records[s["request_id"]].decision
    assert dec["state_trace"][0] == "RECEIVED"
    assert dec["terminal"] in ("COMMITTED", "DENIED", "ESCALATED", "AUDIT_LOGGED")


def test_snapshot_restore_round_trip_and_replay_still_blocked():
    gw = make_gateway()
    s = approved_terraform(gw)
    gw.execute_action(s["request_id"])
    snap = gw.snapshot()
    gw2 = Gateway.restore(snap, clock=gw.clock)
    assert gw2.verify_audit()["intact"]
    assert gw2.status(s["request_id"])["state"] == S.COMPLETED
    # spent nonce survived restore -> replay still rejected
    with pytest.raises(E.NonceReplayError):
        gw2.execute_action(s["request_id"])
