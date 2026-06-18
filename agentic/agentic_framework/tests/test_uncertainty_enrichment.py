"""
End-to-end wiring: adapter model-uncertainty signals -> MCPToolCall -> gateway gap.

Proves the confidence-risk gap fires through the real dispatcher path when an adapter
exposes raw entropy + a verbalized safety score, degrades cleanly when it does not, and
never breaks providers that expose neither. The MistralCGAdapter raw-entropy computation
itself needs a GPU model and is exercised on-pod; here the deterministic StubCGLLMAdapter
and small fakes prove the wiring.
"""

import asyncio
import math

import pytest

from agentic.agentic_framework.cg_tool_dispatcher import CGToolDispatcher
from agentic.agentic_framework.confidence_gate import EscalationLevel
from agentic.agentic_framework.llm_adapters import StubCGLLMAdapter
from agentic.agentic_framework.mcp_gateway import (
    GatewayDecision, InteractiveEscalationHandler, MCPToolDefinition, MockMCPClient,
    SafeMCPGateway, ToolRiskLevel,
)
from agentic.agentic_framework.request_enrichment import (
    build_uncertainty_enrichment_kwargs,
)


class _UncertaintyAdapter:
    """Exposes only model-uncertainty signals (and NO last_cg_metadata, so the CG
    vritti/JEPA path stays out of the way and we isolate the gap wiring)."""

    def __init__(self, *, raw_entropy=None, safety=None, logprobs=None, logits=None):
        if raw_entropy is not None:
            self.last_raw_entropy = raw_entropy
        if safety is not None:
            self.last_safety_confidence = safety
        if logprobs is not None:
            self.last_raw_logprobs = logprobs
        if logits is not None:
            self.last_decision_logits = logits


def _gateway(*, deny=True):
    client = MockMCPClient()
    client.register_tool("update_record", lambda p: "updated", ToolRiskLevel.WRITE)

    async def cb(call, tool_def, decision):
        return not deny

    gw = SafeMCPGateway(
        mcp_client=client,
        escalation_handler=InteractiveEscalationHandler(confirm_callback=cb))
    gw.register_tool(MCPToolDefinition(
        name="update_record", description="Update a record",
        risk_level=ToolRiskLevel.WRITE, requires_confirmation=False, min_confidence=0.2))
    return gw


def _run_async(coro):
    # Private loop (created + closed, never set global) — see test_gateway_confidence_risk_gap.
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


def _dispatch(adapter, *, deny=True):
    gw = _gateway(deny=deny)
    result = _run_async(CGToolDispatcher(adapter, gw).dispatch(
        tool_name="update_record", parameters={}))
    return result, gw.audit_log[-1]


# ----- enrichment helper: provider-agnostic extraction ------------------------

def test_helper_extracts_deterministic_stub_signals():
    stub = StubCGLLMAdapter(default_response="ok")
    stub.call("hello")                       # populates the deterministic fixtures
    kw = build_uncertainty_enrichment_kwargs(stub)
    assert kw["raw_entropy"] == pytest.approx(0.85)
    assert kw["verbalized_safety_confidence"] == pytest.approx(0.95)


def test_helper_computes_raw_entropy_from_logits():
    kw = build_uncertainty_enrichment_kwargs(_UncertaintyAdapter(logits=[0, 0, 0, 0]))
    assert kw["raw_entropy"] == pytest.approx(1.0, abs=1e-9)


def test_helper_passes_logprobs_through():
    kw = build_uncertainty_enrichment_kwargs(
        _UncertaintyAdapter(logprobs=[math.log(0.5), math.log(0.5)]))
    assert "raw_logprobs" in kw and "raw_entropy" not in kw


def test_helper_empty_for_unsupported_or_none():
    assert build_uncertainty_enrichment_kwargs(_UncertaintyAdapter()) == {}
    assert build_uncertainty_enrichment_kwargs(None) == {}


# ----- end-to-end through the dispatcher --------------------------------------

def test_gap_fires_end_to_end_when_both_signals_present():
    result, entry = _dispatch(
        _UncertaintyAdapter(raw_entropy=0.9, safety=0.95), deny=True)
    assert result.decision == GatewayDecision.ESCALATE
    assert result.escalation_level == EscalationLevel.CONFIRM
    # audit records the full provenance (task 6)
    assert entry.raw_entropy == pytest.approx(0.9)
    assert entry.raw_entropy_available is True
    assert entry.raw_entropy_source == "scalar"
    assert entry.confidence_risk_gap_escalate is True
    assert entry.confidence_risk_gap_verbalized_safety == pytest.approx(0.95)
    assert "internally uncertain" in (entry.confidence_risk_gap_reason or "")


def test_gap_does_not_fire_when_raw_entropy_unavailable():
    # Verbalized safety present but no raw entropy -> gap cannot assess -> executes.
    result, entry = _dispatch(_UncertaintyAdapter(safety=0.95), deny=True)
    assert result.decision == GatewayDecision.ALLOWED and result.success
    assert entry.raw_entropy_available is False
    assert entry.confidence_risk_gap_escalate is False


def test_unsupported_provider_degrades_gracefully():
    # Adapter exposes no uncertainty signals (OpenAI/Anthropic today) -> executes.
    result, entry = _dispatch(_UncertaintyAdapter(), deny=True)
    assert result.decision == GatewayDecision.ALLOWED and result.success
    assert entry.raw_entropy_available is False
    assert entry.confidence_risk_gap_escalate is False


def test_raw_entropy_via_logprobs_fires_end_to_end():
    near_uniform = [math.log(0.25)] * 4
    result, _ = _dispatch(
        _UncertaintyAdapter(safety=0.95, logprobs=near_uniform), deny=True)
    assert result.decision == GatewayDecision.ESCALATE


def test_stub_signals_flow_through_to_audit():
    # The deterministic stub carries CG metadata too (so JEPA may act); regardless,
    # the raw-entropy + gap signals must reach governance and be recorded in audit.
    stub = StubCGLLMAdapter(default_response="ok")
    stub.call("please update the record")
    _, entry = _dispatch(stub, deny=False)
    assert entry.raw_entropy == pytest.approx(0.85)
    assert entry.raw_entropy_available is True
    assert entry.confidence_risk_gap_verbalized_safety == pytest.approx(0.95)
    assert entry.confidence_risk_gap_escalate is True
