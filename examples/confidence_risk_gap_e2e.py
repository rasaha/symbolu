#!/usr/bin/env python3
"""
Focused end-to-end validation of the raw-entropy escalation path:

    LLM adapter -> raw_entropy -> MCPToolCall -> SafeMCPGateway -> escalation -> audit

It drives the REAL runtime components — `CGToolDispatcher` and `SafeMCPGateway`, not mocks of
them — on a write-risk tool, and asserts the gap behaves CONSISTENTLY WITH ITS THRESHOLD:

  * the model's raw_entropy is present on the MCPToolCall the gateway receives,
  * if raw_entropy >= threshold (and verbalized safety is high) the gap fires, the gateway
    escalates / requires human confirmation, and the tool is NOT silently executed,
  * if raw_entropy < threshold the gap stays silent and the tool executes,
  * the audit entry records raw-entropy source, verbalized confidence, gap trigger, reason.

The default offline path uses a deterministic adapter (forced high entropy) + a negative
control (low entropy). `--real` drives a live MistralCGAdapter (GPU): its raw entropy is
DATA-DEPENDENT, so the assertion checks consistency-with-threshold (not unconditional
firing). Use `--entropy-threshold` to make a real model's lower entropy cross the bar, and
`--prompt` to try genuinely-uncertain inputs. The CG 32-D metadata is cleared so the
(demoted, experimental) JEPA path does not confound this raw-entropy test.

Run:
    PYTHONPATH=. python examples/confidence_risk_gap_e2e.py
    PYTHONPATH=. python examples/confidence_risk_gap_e2e.py --real --entropy-threshold 0.10
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
from agentic.agentic_framework.signal_config import SignalConfig

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
    (the provider-agnostic case), and NO CG 32-D metadata — isolates raw_entropy -> gap."""

    IS_STUB = True

    def __init__(self, raw_entropy: float, safety: float):
        self.last_raw_entropy = raw_entropy
        self.last_safety_confidence = safety

    def call(self, prompt: str) -> str:
        return "OK"


def _build_gateway(executed: dict, signal_config: SignalConfig):
    client = MockMCPClient()

    def _handler(p):
        executed["ran"] = True
        return "updated"

    client.register_tool(TOOL, _handler, ToolRiskLevel.WRITE)

    async def deny(call, tool_def, decision):
        return False                          # human declines -> ESCALATE (action withheld)

    gw = SafeMCPGateway(
        mcp_client=client,
        escalation_handler=InteractiveEscalationHandler(confirm_callback=deny),
        signal_config=signal_config)
    gw.register_tool(MCPToolDefinition(
        name=TOOL, description="Update account settings",
        risk_level=ToolRiskLevel.WRITE, requires_confirmation=False, min_confidence=0.2))
    return gw


def _dispatch_capturing_call(adapter, signal_config):
    """Run the real dispatcher->gateway path; capture the MCPToolCall the gateway sees."""
    executed: dict = {}
    gw = _build_gateway(executed, signal_config)
    captured: dict = {}
    original_call_tool = gw.call_tool

    async def _capturing(call):
        captured["call"] = call
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


def _flowed(adapter, call, entry) -> bool:
    re_val = adapter.last_raw_entropy
    return (getattr(call, "raw_entropy", None) is not None
            and entry.raw_entropy is not None and entry.raw_entropy_available is True
            and re_val is not None and abs(entry.raw_entropy - re_val) < 1e-6)


def _gap_consistent(adapter, cfg, result, entry, ran) -> bool:
    """The gap must fire iff its inputs cross the configured thresholds; check it did."""
    re_val = adapter.last_raw_entropy
    vs_val = adapter.last_safety_confidence
    expect_fire = (re_val is not None and re_val >= cfg.raw_entropy_high
                   and vs_val is not None and vs_val >= cfg.verbalized_safety_high)
    if expect_fire:
        return (entry.confidence_risk_gap_escalate is True
                and result.decision == GatewayDecision.ESCALATE
                and result.escalation_level == EscalationLevel.CONFIRM
                and ran is False
                and bool(entry.confidence_risk_gap_reason))
    return entry.confidence_risk_gap_escalate is False


def main(argv=None) -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--real", action="store_true", help="positive case via live MistralCGAdapter (GPU)")
    p.add_argument("--cg-base", default="mistralai/Mistral-7B-v0.3")
    p.add_argument("--verbalized-safety", type=float, default=0.95)
    p.add_argument("--entropy-threshold", type=float, default=None,
                   help="override raw_entropy_high (test-only; lets a real model's lower "
                        "entropy cross the bar). Default uses SignalConfig (0.70).")
    p.add_argument("--prompt", default=PROMPT, help="prompt for --real (hunt for high entropy)")
    args = p.parse_args(argv)

    cfg = (SignalConfig(raw_entropy_high=args.entropy_threshold)
           if args.entropy_threshold is not None else SignalConfig())

    print("=" * 64)
    print("  E2E VALIDATION — raw-entropy escalation path")
    print("  LLM adapter -> raw_entropy -> MCPToolCall -> Gateway -> escalation -> audit")
    print(f"  tool='{TOOL}' (risk=write)  |  raw_entropy_high={cfg.raw_entropy_high}  "
          f"verbalized_safety_high={cfg.verbalized_safety_high}")
    print("=" * 64)

    # ---- POSITIVE -------------------------------------------------------------
    if args.real:
        from agentic.agentic_framework.llm_adapters import MistralCGAdapter
        pos = MistralCGAdapter(model_name=args.cg_base)
        pos.call(args.prompt)
        pos.last_safety_confidence = args.verbalized_safety   # seam off -> supply for the run
        pos.last_cg_metadata = {}                             # isolate from the JEPA path
        pos_title = f"POSITIVE (--real)  MistralCGAdapter  REAL raw_entropy={pos.last_raw_entropy:.4f}"
    else:
        pos = _DemoUncertaintyAdapter(raw_entropy=0.85, safety=0.95)
        pos_title = "POSITIVE  verbalized safety 0.95 + HIGH raw entropy 0.85"
    p_res, p_call, p_audit, p_ran = _dispatch_capturing_call(pos, cfg)
    _print_case(pos_title, pos, p_res, p_call, p_audit, p_ran)

    pos_ok = _flowed(pos, p_call, p_audit) and _gap_consistent(pos, cfg, p_res, p_audit, p_ran)
    fired = p_audit.confidence_risk_gap_escalate
    if args.real:
        print(f"\n  [--real] real raw_entropy={pos.last_raw_entropy:.4f} vs threshold "
              f"{cfg.raw_entropy_high}: gap {'FIRED (escalated)' if fired else 'silent (entropy below threshold — model not uncertain on this prompt; pass --entropy-threshold lower or --prompt an uncertain one)'}.")

    # ---- NEGATIVE CONTROL (offline, deterministic) ---------------------------
    neg_ok = True
    if not args.real:
        neg_raw = round(cfg.raw_entropy_high * 0.2, 3)        # clearly below threshold
        neg = _DemoUncertaintyAdapter(raw_entropy=neg_raw, safety=0.95)
        n_res, n_call, n_audit, n_ran = _dispatch_capturing_call(neg, cfg)
        _print_case(f"NEGATIVE CONTROL  same safety 0.95 + LOW raw entropy {neg_raw}",
                    neg, n_res, n_call, n_audit, n_ran)
        neg_ok = (_flowed(neg, n_call, n_audit)
                  and n_audit.confidence_risk_gap_escalate is False   # gap does NOT fire
                  and n_res.decision == GatewayDecision.ALLOWED and n_ran is True)

    # ---- Verdict -------------------------------------------------------------
    print("\n" + "=" * 64)
    print(f"  POSITIVE (raw entropy flows + gap consistent with threshold): "
          f"{'PASS' if pos_ok else 'FAIL'}")
    print(f"  NEGATIVE CONTROL (low entropy -> no gap, executes): "
          f"{'SKIPPED (--real)' if args.real else ('PASS' if neg_ok else 'FAIL')}")
    ok = pos_ok and neg_ok
    print("=" * 64)
    print(f"RESULT: {'✅ PASS' if ok else '❌ FAIL'} — raw-entropy escalation path "
          f"{'validated end-to-end.' if ok else 'did NOT behave as expected.'}")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
