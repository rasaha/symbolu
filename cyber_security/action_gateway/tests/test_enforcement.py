"""Token/binding enforcement at the execution boundary + the nine demo scenarios."""

from __future__ import annotations

import copy

import pytest

from action_gateway import state as S
from action_gateway._ref import errors as E
from action_gateway.errors import CredentialError
from demos import scenarios
from tests.helpers import approved_terraform, make_gateway


@pytest.mark.parametrize("fn", scenarios.ALL_SCENARIOS, ids=lambda f: f.__name__)
def test_demo_scenario_enforces(fn):
    r = fn()
    assert r["passed"], r
    assert r["audit_intact"]


def test_replay_rejected():
    gw = make_gateway()
    s = approved_terraform(gw)
    gw.execute_action(s["request_id"])
    with pytest.raises(E.NonceReplayError):
        gw.execute_action(s["request_id"])


def test_expired_token_sets_expired_state():
    gw = make_gateway()
    s = approved_terraform(gw)
    gw.clock.advance(400)  # token ttl is 300s
    with pytest.raises(E.ExpiredError):
        gw.execute_action(s["request_id"])
    assert gw.status(s["request_id"])["state"] == S.EXPIRED


def test_modified_action_rejected():
    gw = make_gateway()
    s = approved_terraform(gw)
    bad = copy.deepcopy(gw.records[s["request_id"]].envelope)
    bad["arguments"] = {"changes": "9999"}
    with pytest.raises(E.ActionHashMismatchError):
        gw.execute_action(s["request_id"], call_envelope=bad)


def test_scope_expansion_rejected():
    gw = make_gateway()
    s = approved_terraform(gw)
    with pytest.raises(CredentialError):
        gw.execute_action(s["request_id"], requested_permissions=["tf:apply", "iam:*"])


def test_policy_mismatch_rejected():
    gw = make_gateway()
    s = approved_terraform(gw)
    with pytest.raises(E.PolicyMismatchError):
        gw.execute_action(s["request_id"], active_policy_hash="rotated")


def test_toctou_rejected():
    gw = make_gateway()
    s = approved_terraform(gw)
    gw.oracle.bump("terraform", ["svc://billing"])
    with pytest.raises(E.StaleStateError):
        gw.execute_action(s["request_id"])


def test_target_retarget_rejected():
    gw = make_gateway()
    s = approved_terraform(gw)
    bad = copy.deepcopy(gw.records[s["request_id"]].envelope)
    bad["target_resource"] = ["svc://somewhere-else"]
    # retarget changes the action hash -> mismatch before target check
    with pytest.raises(E.GateError):
        gw.execute_action(s["request_id"], call_envelope=bad)
