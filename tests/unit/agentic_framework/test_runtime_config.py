"""
test_runtime_config.py — operational builders for SHADOW / canary / env.

Proves the production SHADOW path (legacy executes, trust_shadow persisted, REVIEWED recorded,
hash chain valid) and the canary builder config (TRUST_CORE + REVIEWED), without poking
private attributes.
"""

from __future__ import annotations

import asyncio

from agentic.agentic_framework.mcp_gateway import (
    MCPToolCall,
    MCPToolDefinition,
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
