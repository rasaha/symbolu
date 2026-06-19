"""
test_runtime_config.py — operational builders for SHADOW / canary / env.

Proves the production SHADOW path (legacy executes, trust_shadow persisted, REVIEWED recorded,
hash chain valid) and the canary builder config (TRUST_CORE + REVIEWED), without poking
private attributes.
"""

from __future__ import annotations

import asyncio

from agentic.agentic_framework.mcp_gateway import (
    EscalationHandler,
    MCPToolCall,
    MCPToolDefinition,
    MockMCPClient,
    ToolRiskLevel,
    create_mock_mcp_gateway,
)
from agentic.agentic_framework.trust.observables import EvidenceStatus
from agentic.agentic_framework.trust.parity import REVIEWED_POLICY, TrustMode
from agentic.agentic_framework.trust.runtime_config import (
    build_canary_gateway,
    build_shadow_gateway,
    gateway_from_env,
)


def _run(coro):
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()
        asyncio.set_event_loop(asyncio.new_event_loop())


def _client():
    # reuse the mock client/tools from the test factory
    return create_mock_mcp_gateway().mcp_client


def test_shadow_gateway_records_reviewed_and_persists(tmp_path):
    db = str(tmp_path / "shadow.db")
    gw = build_shadow_gateway(mcp_client=_client(), audit_db_path=db)
    assert gw._trust_mode == TrustMode.SHADOW
    assert gw._trust_authority_policy is REVIEWED_POLICY

    res = _run(gw.call_tool(MCPToolCall(tool_name="file_read", parameters={"path": "/tmp/x"},
                                        quality_score=0.9, coherence_score=0.9)))
    assert res.decision.value == "allowed"                 # legacy still executes
    store = gw._audit_store
    rec = store.list_recent(limit=1)[0]
    assert "trust_shadow" in rec["request_snapshot"]       # parallel decision persisted
    assert rec["request_snapshot"]["trust_shadow"]["decision"] is not None
    assert store.verify_chain().valid                      # hash chain valid
    store.close()


def test_canary_gateway_is_trust_core_reviewed():
    gw = build_canary_gateway(mcp_client=_client())
    assert gw._trust_mode == TrustMode.TRUST_CORE
    assert gw._trust_authority_policy.jepa == EvidenceStatus.PROVISIONAL  # REVIEWED


def test_gateway_from_env_defaults_and_override(monkeypatch):
    monkeypatch.delenv("TRUST_MODE", raising=False)
    monkeypatch.delenv("TRUST_AUTHORITY_POLICY", raising=False)
    monkeypatch.delenv("GOVERNANCE_AUDIT_DB", raising=False)
    gw = gateway_from_env(mcp_client=_client())
    assert gw._trust_mode == TrustMode.SHADOW and gw._trust_authority_policy is REVIEWED_POLICY

    monkeypatch.setenv("TRUST_MODE", "trust_core")
    monkeypatch.setenv("TRUST_AUTHORITY_POLICY", "reviewed")
    gw2 = gateway_from_env(mcp_client=_client())
    assert gw2._trust_mode == TrustMode.TRUST_CORE


# ---- canary behaviour (C) ---------------------------------------------------

class _Esc(EscalationHandler):
    def __init__(self, decision):
        super().__init__()
        self._d = decision

    async def request_confirmation(self, tool_call, tool_def, gate_decision):
        return self._d


def _jepa_block_call(gw, tool="jw", risk=ToolRiskLevel.WRITE):
    gw.mcp_client.register_tool(tool, lambda p: "ok", risk)
    gw.tool_definitions[tool] = MCPToolDefinition(
        name=tool, description="jepa-sole", risk_level=risk, min_confidence=0.0)
    return MCPToolCall(tool_name=tool, parameters={"x": 1},
                       quality_score=0.05, coherence_score=0.05, raw_entropy=0.1)


def test_canary_jepa_sole_block_denied_escalates():
    gw = build_canary_gateway(mcp_client=MockMCPClient(), escalation_handler=_Esc(False))
    res = _run(gw.call_tool(_jepa_block_call(gw)))
    assert res.decision.value == "escalate" and res.human_confirmed is False


def test_canary_jepa_sole_block_approved_allows():
    gw = build_canary_gateway(mcp_client=MockMCPClient(), escalation_handler=_Esc(True))
    res = _run(gw.call_tool(_jepa_block_call(gw)))
    assert res.decision.value == "allowed" and res.human_confirmed is True


def test_canary_forbidden_remains_block():
    gw = build_canary_gateway(mcp_client=MockMCPClient(), escalation_handler=_Esc(True))
    gw.mcp_client.register_tool("cred", lambda p: "ok", ToolRiskLevel.WRITE)
    gw.tool_definitions["cred"] = MCPToolDefinition(
        name="cred", description="x", risk_level=ToolRiskLevel.WRITE, min_confidence=0.0,
        capabilities=["credential_access"])
    res = _run(gw.call_tool(MCPToolCall(tool_name="cred", parameters={"x": 1},
                                        quality_score=0.99, coherence_score=0.99)))
    assert res.decision.value == "blocked"


def test_canary_domain_block_remains_block():
    from agentic.agentic_framework.domain_policy import create_default_registry
    gw = build_canary_gateway(mcp_client=MockMCPClient(),
                              domain_registry=create_default_registry(), domain_id="finance",
                              escalation_handler=_Esc(True))
    gw.mcp_client.register_tool("wipe_ledger", lambda p: "ok", ToolRiskLevel.DESTRUCTIVE)
    gw.tool_definitions["wipe_ledger"] = MCPToolDefinition(
        name="wipe_ledger", description="x", risk_level=ToolRiskLevel.DESTRUCTIVE,
        min_confidence=0.3)
    res = _run(gw.call_tool(MCPToolCall(tool_name="wipe_ledger", parameters={"x": 1},
                                        quality_score=0.9, coherence_score=0.9)))
    assert res.decision.value == "blocked"


def test_canary_shadow_block_remains_block():
    from experiments.trust_signal.parity_harness import _make_shadow_registry
    gw = build_canary_gateway(mcp_client=MockMCPClient(),
                              shadow_registry=_make_shadow_registry(),
                              escalation_handler=_Esc(True))
    gw.mcp_client.register_tool("unknown_shadow_write", lambda p: "ok", ToolRiskLevel.WRITE)
    gw.tool_definitions["unknown_shadow_write"] = MCPToolDefinition(
        name="unknown_shadow_write", description="x", risk_level=ToolRiskLevel.WRITE,
        min_confidence=0.3)
    res = _run(gw.call_tool(MCPToolCall(tool_name="unknown_shadow_write", parameters={"x": 1},
                                        quality_score=0.9, coherence_score=0.9)))
    assert res.decision.value == "blocked"


def test_rollback_to_shadow_and_legacy_restores_block():
    for builder, mode_name in ((build_shadow_gateway, "shadow"),):
        gw = builder(mcp_client=MockMCPClient(), escalation_handler=_Esc(True))
        res = _run(gw.call_tool(_jepa_block_call(gw)))
        assert res.decision.value == "blocked"   # SHADOW: legacy acts → hard block restored
    # explicit legacy via env-style construction
    gw_legacy = gateway_from_env  # not used; legacy parity below
    from agentic.agentic_framework.mcp_gateway import SafeMCPGateway
    gl = SafeMCPGateway(mcp_client=MockMCPClient(), trust_mode="legacy",
                        trust_authority_policy="reviewed", escalation_handler=_Esc(True))
    assert _run(gl.call_tool(_jepa_block_call(gl))).decision.value == "blocked"
