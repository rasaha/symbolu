"""Prove there is no execution path that bypasses the gate + token + broker."""

from __future__ import annotations

import pytest

from action_gateway import ToolRequest
from action_gateway.adapters import TerraformTool
from action_gateway.broker import MockCredentialBroker, ScopedCredential
from action_gateway.errors import CredentialError, NoExecutionTokenError
from tests.helpers import backup, make_gateway


def test_execute_without_evaluate_has_no_token():
    gw = make_gateway()
    s = gw.submit_action(ToolRequest(tool="terraform", verb="apply",
                                     target=["svc://x"], args={}))
    # never evaluated -> no token -> cannot execute
    with pytest.raises(NoExecutionTokenError):
        gw.execute_action(s["request_id"])


def test_denied_action_cannot_execute():
    gw = make_gateway()
    s = gw.submit_action(ToolRequest(tool="filesystem", verb="delete",
                                     target=["file://x"], args={"last_replica": False}))
    gw.evaluate_action(s["request_id"])  # DB_DELETE, no backup -> DENY
    with pytest.raises(NoExecutionTokenError):
        gw.execute_action(s["request_id"])


def test_escalated_action_cannot_execute():
    gw = make_gateway()
    s = gw.submit_action(ToolRequest(
        tool="kubernetes", verb="delete", target=["k8s://p/x"],
        args={"last_replica": False}, reversibility="REVERSIBLE_WITH_COST"))
    gw.evaluate_action(s["request_id"], evidence=[backup(s["action_hash"], gw)])  # ESCALATE
    with pytest.raises(NoExecutionTokenError):
        gw.execute_action(s["request_id"])


def test_adapter_cannot_execute_without_broker_credential():
    # A forged capability object (not minted by the broker) is rejected.
    broker = MockCredentialBroker()
    tool = TerraformTool()
    forged = ScopedCredential(credential_id="forged", principal="agent://x",
                              permissions=frozenset({"tf:apply"}), token_hash="deadbeef",
                              expires_at="2999-01-01T00:00:00.000Z")
    req = ToolRequest(tool="terraform", verb="apply", target=["svc://x"], args={})
    with pytest.raises(CredentialError):
        tool.execute(req, forged, broker=broker, now="2026-07-12T14:00:00.000Z")


def test_broker_credential_bound_to_permission():
    # A capability that lacks the needed permission cannot drive the adapter.
    broker = MockCredentialBroker()
    tool = TerraformTool()
    fake_token = {"payload": {"credential_scope": {"permissions": ["tf:plan"]},
                              "expiration": "2999-01-01T00:00:00.000Z"},
                  "token_hash": "h"}
    cred = broker.issue(token=fake_token, requested_permissions=["tf:plan"],
                        principal="agent://x", now="2026-07-12T14:00:00.000Z")
    req = ToolRequest(tool="terraform", verb="apply", target=["svc://x"], args={})
    # adapter needs tf:apply, credential only has tf:plan
    with pytest.raises(CredentialError):
        tool.execute(req, cred, broker=broker, now="2026-07-12T14:00:00.000Z")


def test_every_completed_execution_had_a_token():
    from tests.helpers import approved_terraform
    gw = make_gateway()
    s = approved_terraform(gw)
    rec = gw.records[s["request_id"]]
    assert rec.token is not None
    gw.execute_action(s["request_id"])
    # token nonce is now spent (single-use)
    assert rec.token_nonce in gw._spent_nonces
