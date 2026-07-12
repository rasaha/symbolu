"""Bypass-resistance: every path fails closed before any tool side effect."""

from __future__ import annotations

import copy

from action_gateway import ToolRequest
from action_gateway.broker import MockCredentialBroker, ScopedCredential
from tests.helpers import approved_terraform, make


def test_direct_adapter_invocation_rejected():
    mcp, cs = make()
    tool = mcp.gateway.adapters["terraform"]
    forged = ScopedCredential(credential_id="forged", principal="p",
                              permissions=frozenset({"tf:apply"}), token_hash="h",
                              expires_at="2999-01-01T00:00:00.000Z")
    try:
        tool.execute(ToolRequest(tool="terraform", verb="apply", target=["t"], args={}),
                     forged, broker=MockCredentialBroker(), now=mcp.clock.now())
        assert False, "adapter executed with a forged capability"
    except Exception as e:  # noqa: BLE001
        assert getattr(e, "code", "") == "E_CREDENTIAL"


def test_unregistered_tool_rejected():
    mcp, cs = make()
    r = mcp.prepare(cs.context(), "database.drop", {})
    assert r["reason_codes"] == ["E_MCP_UNKNOWN_TOOL"]


def test_no_direct_credential_request_api():
    mcp, cs = make()
    # the MCP surface exposes no way for a client to mint a capability
    for attr in ("issue", "issue_credential", "mint_capability", "broker_issue"):
        assert not hasattr(mcp, attr)


def test_modified_action_rejected():
    mcp, cs = make()
    p = approved_terraform(mcp, cs)
    bad = copy.deepcopy(mcp.gateway.records[p["request_id"]].envelope)
    bad["arguments"] = {"changes": "9999"}
    r = mcp._commit(cs.context(), p["request_id"], call_envelope=bad)
    assert r["reason_codes"] == ["E_ACTION_HASH_MISMATCH"]


def test_modified_target_rejected():
    mcp, cs = make()
    p = approved_terraform(mcp, cs)
    bad = copy.deepcopy(mcp.gateway.records[p["request_id"]].envelope)
    bad["target_resource"] = ["tf://somewhere-else"]
    r = mcp._commit(cs.context(), p["request_id"], call_envelope=bad)
    assert r["reason_codes"][0].startswith("E_")  # hash mismatch / target mismatch


def test_scope_expansion_rejected():
    mcp, cs = make()
    p = approved_terraform(mcp, cs)
    r = mcp._commit(cs.context(), p["request_id"], requested_permissions=["tf:apply", "iam:*"])
    assert r["reason_codes"] == ["E_CREDENTIAL"]


def test_replayed_protocol_request_rejected():
    mcp, cs = make()
    ctx = cs.context()
    mcp.prepare(ctx, "terraform.apply", {"workspace": "w"})
    r = mcp.prepare(cs.replayed_context(ctx), "terraform.apply", {"workspace": "w"})
    assert r["reason_codes"] == ["E_MCP_REPLAYED_REQUEST"]


def test_replayed_execution_token_rejected():
    mcp, cs = make()
    p = approved_terraform(mcp, cs)
    mcp.execute(cs.context(), p["request_id"])
    r = mcp.execute(cs.context(), p["request_id"])
    assert r["reason_codes"] == ["E_NONCE_REPLAY"]


def test_replayed_broker_capability_rejected():
    mcp, cs = make()
    p = approved_terraform(mcp, cs)
    res = mcp.execute(cs.context(), p["request_id"])
    cred = mcp.broker._issued[res["credential_id"]]
    try:
        mcp.broker.validate(cred, needed_permission="tf:apply", now=mcp.clock.now())
        assert False, "capability reused"
    except Exception as e:  # noqa: BLE001
        assert getattr(e, "code", "") == "E_CREDENTIAL"


def test_stale_state_rejected():
    mcp, cs = make()
    p = approved_terraform(mcp, cs, "toc")
    mcp.gateway.oracle.bump("terraform", ["tf://toc"])
    r = mcp.execute(cs.context(), p["request_id"])
    assert r["reason_codes"] == ["E_STALE_STATE"]


def test_sequence_rollback_rejected():
    mcp, cs = make()
    mcp.prepare(cs.context(), "terraform.apply", {"workspace": "w"})  # advances watermark
    r = mcp.prepare(cs.context(sequence_override=1), "terraform.apply", {"workspace": "w"})
    assert r["reason_codes"] == ["E_MCP_SEQUENCE_ROLLBACK"]


def test_policy_change_rejected_at_commit():
    mcp, cs = make()
    p = approved_terraform(mcp, cs)
    r = mcp._commit(cs.context(), p["request_id"], active_policy_hash="rotated")
    assert r["reason_codes"] == ["E_POLICY_MISMATCH"]
