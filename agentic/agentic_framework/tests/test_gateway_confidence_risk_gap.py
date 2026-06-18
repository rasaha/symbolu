"""
Gateway integration: the confidence-risk gap escalates fooled-unsafe calls via raw
entropy, while the CG 32-D sovereign-state signal stays OPTIONAL (off by default).

The fooled-unsafe signature (from the falsification): high verbalized safety confidence +
high raw next-token entropy on a non-trivial tool -> escalate to a human.
"""

import asyncio

from agentic.agentic_framework.mcp_gateway import (
    GatewayDecision, InteractiveEscalationHandler, MCPToolCall, MCPToolDefinition,
    MockMCPClient, SafeMCPGateway, ToolRiskLevel,
)
from agentic.agentic_framework.confidence_gate import EscalationLevel
from agentic.agentic_framework.signal_config import SignalConfig


def run_async(coro):
    # asyncio.run manages the loop lifecycle cleanly (no global-loop pollution that
    # would break other async test modules when the full suite runs together).
    return asyncio.run(coro)


def _gateway(*, deny: bool = True, signal_config=None):
    client = MockMCPClient()
    client.register_tool("update_record", lambda p: "updated", ToolRiskLevel.WRITE)

    async def cb(call, tool_def, decision):
        return not deny

    gw = SafeMCPGateway(
        mcp_client=client,
        escalation_handler=InteractiveEscalationHandler(confirm_callback=cb),
        signal_config=signal_config,
    )
    gw.register_tool(MCPToolDefinition(
        name="update_record", description="Update a record",
        risk_level=ToolRiskLevel.WRITE, requires_confirmation=False, min_confidence=0.2))
    return gw


def _call(**kw):
    return MCPToolCall(tool_name="update_record", parameters={},
                       quality_score=0.9, coherence_score=0.9, **kw)


def test_control_executes_without_uncertainty_signals():
    # Same tool, no uncertainty signals -> executes (the baseline the gap modifies).
    result = run_async(_gateway(deny=True).call_tool(_call()))
    assert result.decision == GatewayDecision.ALLOWED and result.success


def test_fooled_unsafe_escalates_via_raw_entropy_gap():
    # Confident-but-uncertain on a WRITE tool -> gap requests a human -> denied -> ESCALATE.
    result = run_async(_gateway(deny=True).call_tool(
        _call(verbalized_safety_confidence=0.95, raw_entropy=0.95)))
    assert result.decision == GatewayDecision.ESCALATE
    assert result.escalation_level == EscalationLevel.CONFIRM
    assert not result.success


def test_gap_proceeds_when_human_confirms():
    result = run_async(_gateway(deny=False).call_tool(
        _call(verbalized_safety_confidence=0.95, raw_entropy=0.95)))
    assert result.decision == GatewayDecision.ALLOWED and result.success


def test_raw_entropy_computed_from_logprobs_also_escalates():
    import math
    near_uniform = [math.log(0.25)] * 4   # high raw entropy from a top-k logprobs list
    result = run_async(_gateway(deny=True).call_tool(
        _call(verbalized_safety_confidence=0.95, raw_logprobs=near_uniform)))
    assert result.decision == GatewayDecision.ESCALATE


def test_confident_and_certain_does_not_escalate():
    # Low raw entropy = the model is confidently CERTAIN -> no gap, executes.
    result = run_async(_gateway(deny=True).call_tool(
        _call(verbalized_safety_confidence=0.95, raw_entropy=0.05)))
    assert result.decision == GatewayDecision.ALLOWED and result.success


def test_audit_explains_why_the_gap_escalated():
    gw = _gateway(deny=True)
    run_async(gw.call_tool(_call(verbalized_safety_confidence=0.95, raw_entropy=0.95)))
    entry = gw.audit_log[-1]
    assert entry.confidence_risk_gap_escalate is True
    assert entry.raw_entropy == 0.95 and entry.raw_entropy_available is True
    assert "internally uncertain" in (entry.confidence_risk_gap_reason or "")


def test_cg_state_signal_is_optional_off_by_default():
    # A high CG 32-D sovereign-state entropy alone (no raw entropy, no verbalized) must
    # NOT change the decision by default — CG is demoted to experimental.
    class _CGEntropy:
        combined_entropy = 0.95
        guna_entropy = 0.95
        kosha_entropy = 0.95
        cross_domain_entropy = 0.95
        gate = "ALLOW"

    result = run_async(_gateway(deny=True).call_tool(_call(entropy_result=_CGEntropy())))
    assert result.decision == GatewayDecision.ALLOWED and result.success


def test_cg_state_signal_applies_when_explicitly_enabled():
    # Opt-in (experimental): enabling CG-state signals lets its penalty lower confidence.
    class _CGEntropy:
        combined_entropy = 0.95
        guna_entropy = 0.95
        kosha_entropy = 0.95
        cross_domain_entropy = 0.95
        gate = "ALLOW"

    cfg = SignalConfig(enable_cg_state_signals=True)
    off = run_async(_gateway(deny=True).call_tool(_call(entropy_result=_CGEntropy())))
    on = run_async(_gateway(deny=True, signal_config=cfg).call_tool(
        _call(entropy_result=_CGEntropy())))
    # The penalty only reduces confidence; it must not raise it.
    assert on.confidence <= off.confidence
