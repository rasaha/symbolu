"""Authenticated-vs-declared identity handling."""

from __future__ import annotations

from action_gateway_mcp import RequestContext
from tests.helpers import make


def _ctx(cs, **over):
    return cs.context(**over)


def test_authenticated_identity_wins():
    ctx = RequestContext(
        connection_id="c", session_id="s", correlation_id="k", sequence_id="k:1",
        request_nonce="n", request_timestamp="2026-07-12T14:00:00.000Z",
        declared_agent_id="agent://declared", authenticated_agent_id="agent://real")
    assert ctx.effective_agent_id() == "agent://real"
    assert ctx.identity_conflicts()  # differ -> recorded conflict


def test_no_conflict_when_absent_or_equal():
    ctx = RequestContext(
        connection_id="c", session_id="s", correlation_id="k", sequence_id="k:1",
        request_nonce="n", request_timestamp="2026-07-12T14:00:00.000Z",
        declared_agent_id="agent://x", authenticated_agent_id=None)
    assert ctx.identity_conflicts() == []
    assert ctx.effective_agent_id() == "agent://x"


def test_client_identity_mismatch_denied():
    mcp, cs = make()
    r = mcp.prepare(cs.context(declared_agent_id="agent://evil"),
                    "terraform.apply", {"workspace": "w"})
    assert r["outcome"] == "DENY" and r["reason_codes"] == ["E_MCP_IDENTITY_MISMATCH"]
    assert mcp.metrics.identity_rejections == 1


def test_tool_server_mismatch_denied():
    mcp, cs = make()
    r = mcp.prepare(cs.context(declared_tool_server="mcp://spoofed"),
                    "terraform.apply", {"workspace": "w"})
    assert r["outcome"] == "DENY" and r["reason_codes"] == ["E_MCP_IDENTITY_MISMATCH"]


def test_effective_identity_used_in_envelope():
    mcp, cs = make()
    p = mcp.prepare(cs.context(), "terraform.apply", {"workspace": "w"})
    env = mcp.gateway.records[p["request_id"]].envelope
    assert env["agent_identity"]["id"] == "agent://sre/1"  # authenticated
    assert env["credential_scope"]["principal"] == "agent://sre/1"
