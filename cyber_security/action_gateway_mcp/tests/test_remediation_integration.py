"""R1.5 runtime integration tests — MCP transport.

Proves the MCP surface forwards advisory remediation from the gateway, resolves privileged
disclosure from the AUTHENTICATED caller context (never by request alone), and stays
byte-identical by default.
"""

from __future__ import annotations

import json

import pytest

from tests.helpers import make

_REM_KEYS = {"response_schema_version", "all_unmet_conditions", "required_changes",
             "retryability", "disclosure", "retry_budget"}


def _prepare(mcp, cs):
    p = mcp.prepare(cs.context(), "terraform.apply", {"workspace": "w"})
    return p["request_id"]


def _ctx(cs, *, caps=None, authenticated=True):
    ctx = cs.context()
    if caps is not None:
        ctx.client_capabilities = list(caps)
    if not authenticated:
        ctx.authenticated_agent_id = None
    return ctx


# --------------------------------------------------------------------------- #
def test_mcp_default_off_has_no_remediation():
    mcp, cs = make()
    rid = _prepare(mcp, cs)
    resp = mcp.evaluate(cs.context(), rid)
    assert not (_REM_KEYS & set(resp))          # passthrough byte-shape unchanged


def test_mcp_standard_adds_fields_without_changing_outcome():
    mcp, cs = make()
    rid = _prepare(mcp, cs)
    off = mcp.evaluate(cs.context(), rid)
    mcp2, cs2 = make()
    rid2 = _prepare(mcp2, cs2)
    std = mcp2.evaluate(cs2.context(), rid2, remediation_mode="standard")
    assert _REM_KEYS <= set(std)
    assert std["outcome"] == off["outcome"]
    assert std["dispositive_rules"] == off["dispositive_rules"]
    assert std["response_schema_version"] == "1.1"


def test_mcp_full_requires_authenticated_capability():
    mcp, cs = make()
    rid = _prepare(mcp, cs)
    # authenticated caller WITH the capability -> FULL granted
    ctx = _ctx(cs, caps=["remediation:full"])
    full = mcp.evaluate(ctx, rid, remediation_mode="full")
    assert full["disclosure"]["mode"] == "FULL"


def test_mcp_full_without_capability_is_clamped():
    mcp, cs = make()
    rid = _prepare(mcp, cs)
    ctx = _ctx(cs, caps=[])                       # authenticated but no capability
    resp = mcp.evaluate(ctx, rid, remediation_mode="full")
    assert resp["disclosure"]["mode"] == "STANDARD"


def test_mcp_full_without_authentication_not_granted():
    # capability present but NO authenticated identity -> privileged not granted (resolver)
    mcp, cs = make()
    ctx = _ctx(cs, caps=["remediation:full"], authenticated=False)
    mode, trusted = mcp._resolve_remediation(ctx, "full")
    assert mode == "FULL" and trusted is False


def test_mcp_passthrough_forwards_all_remediation_fields():
    mcp, cs = make()
    rid = _prepare(mcp, cs)
    ctx = _ctx(cs, caps=["remediation:full"])
    resp = mcp.evaluate(ctx, rid, remediation_mode="full")
    for k in _REM_KEYS:
        assert k in resp
    # advisory only: still no execution authority in the protocol response
    assert resp["execution_token"] is None


def test_mcp_remediation_does_not_change_decision_or_hash():
    mcp, cs = make()
    rid = _prepare(mcp, cs)
    off = mcp.evaluate(cs.context(), rid)
    head_off = mcp.gateway.audit_log()["head"]
    mcp2, cs2 = make()
    rid2 = _prepare(mcp2, cs2)
    on = mcp2.evaluate(_ctx(cs2, caps=["remediation:full"]), rid2, remediation_mode="full")
    head_on = mcp2.gateway.audit_log()["head"]
    assert off["outcome"] == on["outcome"]
    assert off["action_hash"] == on["action_hash"]
    assert head_off == head_on                   # audit hash unchanged by remediation


def test_mcp_minimal_hides_policy_structure():
    # threshold-hiding is proven at the gateway/R1 level; here assert MINIMAL omits
    # policy structure (no rule_id/operator/field_path) even over MCP transport
    mcp, cs = make()
    rid = _prepare(mcp, cs)                       # DEPLOY missing evidence -> a required change
    resp = mcp.evaluate(cs.context(), rid, remediation_mode="minimal")
    for ch in resp["required_changes"]:
        assert "field_path" not in ch and "source_rule_id" not in ch and "operator" not in ch
    assert resp["disclosure"]["mode"] == "MINIMAL"
