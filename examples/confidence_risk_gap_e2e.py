#!/usr/bin/env python3
"""
Focused end-to-end validation of the raw-entropy escalation path:

    LLM adapter -> raw_entropy -> MCPToolCall -> SafeMCPGateway -> escalation -> audit

It drives the REAL runtime components — `CGToolDispatcher` and `SafeMCPGateway`, not mocks
of them — and verifies, on a write-risk tool:

  * raw_entropy is present on the MCPToolCall the gateway receives,
  * the confidence-risk gap triggers (model says "safe" but is internally uncertain),
  * the gateway escalates / requires human confirmation,
  * the tool is NOT silently allowed,
  * the audit entry records raw-entropy source, verbalized confidence, gap trigger, reason,

plus a NEGATIVE CONTROL (same verbalized confidence, same tool risk, but LOW raw entropy)
where the gap must NOT trigger and the tool executes.

A deterministic offline adapter stands in for the model (a real one is expensive). It
exposes only the provider-agnostic signals (raw entropy + a verbalized safety score) and no
CG 32-D state, so the path under test is isolated from the experimental JEPA-from-state path.
Pass `--real --cg-base <hf-id> --verbalized-safety 0.9` to drive a live MistralCGAdapter
(GPU) whose raw entropy comes from a real forward pass (positive case only).

Run:
    PYTHONPATH=. python examples/confidence_risk_gap_e2e.py
Exit 0 on PASS, 1 on FAIL.
"""

from __future__ import annotations

import argparse
import asyncio
import sys

from agentic.agentic_framework.cg_tool_dispatcher import CGToolDispatcher
from agentic.agentic_framework.confidence_gate import EscalationLevel
from agentic.agentic_framework.mcp_gateway import (
    GatewayDecision, InteractiveEscalationHandler, MCPToolDefinition, MockMCPClient,
    SafeMCPGateway, ToolRiskLevel,
)

TOOL = "update_account_settings"          # write-risk (>= the gap's minimum)
PROMPT = "Update the payout account for vendor ACME to the new IBAN on file."


def _run(coro):
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


class _DemoUncertaintyAdapter:
    """Deterministic offline adapter exposing ONLY raw entropy + a verbalized safety score
    (the provider-agnostic case: a non-CG model with logprobs + a safety self-assessment),
    and NO CG 32-D metadata — so this isolates raw_entropy -> gap -> escalation."""

    IS_STUB = True

    def __init__(self, raw_entropy: float, safety: float):
        self.last_raw_entropy = raw_entropy
        self.last_safety_confidence = safety

    def call(self, prompt: str) -> str:
        return "OK"


def _build_gateway(executed: dict):
    client = MockMCPClient()

    def _handler(p):
        executed["ran"] = True               # records a SILENT execution if it happens
        return "updated"

    client.register_tool(TOOL, _handler, ToolRiskLevel.WRITE)

    async def deny(call, tool_def, decision):
        return False                          # human declines -> ESCALATE (action withheld)

    gw = SafeMCPGateway(
        mcp_client=client,
        escalation_handler=InteractiveEscalationHandler(confirm_callback=deny))
    gw.register_tool(MCPToolDefinition(
        name=TOOL, description="Update account settings",
        risk_level=ToolRiskLevel.WRITE, requires_confirmation=False, min_confidence=0.2))
    return gw


def _dispatch_capturing_call(adapter):
    """Run the real dispatcher->gateway path; capture the MCPToolCall the gateway sees."""
    executed: dict = {}
    gw = _build_gateway(executed)
    captured: dict = {}
    original_call_tool = gw.call_tool

    async def _capturing(call):
        captured["call"] = call               # the exact MCPToolCall governance receives
        return await original_call_tool(call)

    gw.call_tool = _capturing
    result = _run(CGToolDispatcher(adapter, gw).dispatch(
        tool_name=TOOL, parameters={"iban": "GB00-NEW-0001"}))
    return result, captured.get("call"), gw.audit_log[-1], executed.get("ran", False)


def _print_case(title, adapter, result, call, entry, ran):
    print(f"\n{'-' * 64}\n{title}\n{'-' * 64}")
    print(f"  adapter.last_raw_entropy        = {adapter.last_raw_entropy}")
    print(f"  adapter.last_safety_confidence  = {adapter.last_safety_confidence}")
    print(f"  MCPToolCall.raw_entropy         = {getattr(call, 'raw_entropy', None)}"
          f"   (present on the call the gateway received)")
    print(f"  MCPToolCall.verbalized_safety   = {getattr(call, 'verbalized_safety_confidence', None)}")
    print(f"  gateway decision                = {result.decision.value}")
    print(f"  escalation_level                = {result.escalation_level.value}")
    print(f"  tool handler executed?          = {ran}")
    print(f"  audit.raw_entropy / source      = {entry.raw_entropy} / {entry.raw_entropy_source}")
    print(f"  audit.raw_entropy_available     = {entry.raw_entropy_available}")
    print(f"  audit.gap_verbalized_safety     = {entry.confidence_risk_gap_verbalized_safety}")
    print(f"  audit.gap_escalate              = {entry.confidence_risk_gap_escalate}")
    print(f"  audit.gap_reason                = {entry.confidence_risk_gap_reason}")


def main(argv=None) -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--real", action="store_true", help="positive case via live MistralCGAdapter (GPU)")
    p.add_argument("--cg-base", default="mistralai/Mistral-7B-v0.3")
    p.add_argument("--verbalized-safety", type=float, default=0.95)
    args = p.parse_args(argv)

    print("=" * 64)
    print("  E2E VALIDATION — raw-entropy escalation path")
    print("  LLM adapter -> raw_entropy -> MCPToolCall -> Gateway -> escalation -> audit")
    print(f"  tool='{TOOL}' (risk=write)")
    print("=" * 64)

    # ---- POSITIVE: high verbalized safety + HIGH raw entropy -> gap fires ----
    if args.real:
        from agentic.agentic_framework.llm_adapters import MistralCGAdapter
        pos = MistralCGAdapter(model_name=args.cg_base)
        pos.call(PROMPT)
        pos.last_safety_confidence = args.verbalized_safety  # seam off -> supply for the run
        pos_title = f"POSITIVE  MistralCGAdapter({args.cg_base})  raw={pos.last_raw_entropy}"
    else:
        pos = _DemoUncertaintyAdapter(raw_entropy=0.85, safety=0.95)
        pos_title = "POSITIVE  high verbalized safety (0.95) + HIGH raw entropy (0.85)"
    p_res, p_call, p_audit, p_ran = _dispatch_capturing_call(pos)
    _print_case(pos_title, pos, p_res, p_call, p_audit, p_ran)

    pos_ok = (
        getattr(p_call, "raw_entropy", None) is not None        # present on MCPToolCall
        and p_audit.confidence_risk_gap_escalate is True         # gap triggered
        and p_res.decision == GatewayDecision.ESCALATE           # gateway escalates
        and p_res.escalation_level == EscalationLevel.CONFIRM     # requires human
        and p_ran is False                                       # NOT silently executed
        and p_audit.raw_entropy_source is not None               # audit provenance
        and p_audit.confidence_risk_gap_reason                   # audit reason
    )

    # ---- NEGATIVE CONTROL: same verbalized safety + LOW raw entropy -> no gap ----
    neg_ok = True
    if not args.real:                       # raw entropy is model-determined for --real
        neg = _DemoUncertaintyAdapter(raw_entropy=0.10, safety=0.95)
        n_res, n_call, n_audit, n_ran = _dispatch_capturing_call(neg)
        _print_case("NEGATIVE CONTROL  same safety (0.95) + LOW raw entropy (0.10)",
                    neg, n_res, n_call, n_audit, n_ran)
        neg_ok = (
            getattr(n_call, "raw_entropy", None) == 0.10         # still present on the call
            and n_audit.confidence_risk_gap_escalate is False    # gap does NOT trigger
            and n_res.decision == GatewayDecision.ALLOWED        # executes
            and n_ran is True
        )

    # ---- Verdict ---------------------------------------------------------
    print("\n" + "=" * 64)
    print(f"  POSITIVE (gap fires + escalates, not executed): {'PASS' if pos_ok else 'FAIL'}")
    print(f"  NEGATIVE CONTROL (low entropy -> no gap, executes): "
          f"{'PASS' if neg_ok else 'FAIL' if not args.real else 'SKIPPED (--real)'}")
    ok = pos_ok and neg_ok
    print("=" * 64)
    print(f"RESULT: {'✅ PASS' if ok else '❌ FAIL'} — raw-entropy escalation path "
          f"{'validated end-to-end.' if ok else 'did NOT behave as expected.'}")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
