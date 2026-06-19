"""
test_trust_parity.py — Phase 1.5 parity mapping coverage + CG decision-gate regression.

Two layers:
  * unit parity over the legacy-authority mapping (JEPA DENY/DEFER, domain modes, shadow
    containment modes) via shadow_compare with crafted inputs — deterministic, exhaustive;
  * an integration CG decision-gate regression: CG-derived vritti is recorded in audit and
    is INERT when enable_cg_state_signals=False, but CAN change the decision when True.
  * a harness smoke test (zero unintended/unresolved on the focused corpus).
"""

from __future__ import annotations

import asyncio
from types import SimpleNamespace

import pytest

from agentic.agentic_framework.domain_policy import DomainActionMode
from agentic.agentic_framework.mcp_gateway import (
    MockMCPClient,
    MCPToolCall,
    MCPToolDefinition,
    SafeMCPGateway,
    ToolRiskLevel,
)
from agentic.agentic_framework.signal_config import SignalConfig
from agentic.agentic_framework.trust.observables import TrustDecision
from agentic.agentic_framework.trust.parity import (
    PARITY_POLICY,
    REVIEWED_POLICY,
    TrustMode,
    shadow_compare,
)


def _run(coro):
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()
        asyncio.set_event_loop(asyncio.new_event_loop())


def _ctx(*, decision="allowed", human_confirmed=False, risk="write",
         can_execute=True, requires_human=False, requires_confirmation=False,
         min_confidence=0.3, confidence=0.9):
    result = SimpleNamespace(decision=SimpleNamespace(value=decision),
                             human_confirmed=human_confirmed, confidence=confidence)
    tool_def = SimpleNamespace(min_confidence=min_confidence,
                               requires_confirmation=requires_confirmation,
                               risk_level=SimpleNamespace(value=risk))
    gate = SimpleNamespace(execution=SimpleNamespace(can_execute=can_execute),
                           escalation=SimpleNamespace(requires_human=requires_human))
    return result, tool_def, gate


# ---- JEPA DENY / DEFER edge cases -------------------------------------------

@pytest.mark.parametrize("regime,risk,expected", [
    ("normal", "write", TrustDecision.ALLOW),
    ("dual_anomaly", "write", TrustDecision.BLOCK),     # HALT → block
    ("unknown", "read_only", TrustDecision.BLOCK),      # HALT → block even read-only
    ("process_drift", "write", TrustDecision.BLOCK),    # DEFER → block non-read-only
    ("process_drift", "read_only", TrustDecision.CONFIRM),  # DEFER → escalate read-only
    ("semantic_shift", "write", TrustDecision.BLOCK),
    ("semantic_shift", "read_only", TrustDecision.CONFIRM),
])
def test_jepa_regime_parity_mapping(regime, risk, expected):
    result, tool_def, gate = _ctx(risk=risk)
    jepa = SimpleNamespace(regime=SimpleNamespace(value=regime))
    cmp = shadow_compare(tool_def=tool_def, result=result, gate_decision=gate,
                         jepa_assessment=jepa)
    assert cmp.trust == expected


# ---- domain policy modes ----------------------------------------------------

@pytest.mark.parametrize("mode,expected", [
    (DomainActionMode.ALLOW, TrustDecision.ALLOW),
    (DomainActionMode.CONFIRM_REQUIRED, TrustDecision.CONFIRM),
    (DomainActionMode.BLOCKED, TrustDecision.BLOCK),
])
def test_domain_mode_parity_mapping(mode, expected):
    result, tool_def, gate = _ctx()
    domain = SimpleNamespace(mode=mode)
    cmp = shadow_compare(tool_def=tool_def, result=result, gate_decision=gate,
                         domain_result=domain)
    assert cmp.trust == expected


# ---- shadow containment modes ----------------------------------------------

@pytest.mark.parametrize("containment,expected", [
    ("allow", TrustDecision.ALLOW),
    ("require_confirmation", TrustDecision.CONFIRM),
    ("quarantined", TrustDecision.BLOCK),
    ("blocked", TrustDecision.BLOCK),
])
def test_shadow_mode_parity_mapping(containment, expected):
    result, tool_def, gate = _ctx()
    shadow = SimpleNamespace(containment_mode=SimpleNamespace(value=containment))
    cmp = shadow_compare(tool_def=tool_def, result=result, gate_decision=gate,
                         shadow_assessment=shadow)
    assert cmp.trust == expected


# ---- confidence-risk gap + min_confidence floor (unit) ---------------------

def test_confidence_floor_blocks():
    result, tool_def, gate = _ctx(confidence=0.2, min_confidence=0.9)
    cmp = shadow_compare(tool_def=tool_def, result=result, gate_decision=gate)
    assert cmp.trust == TrustDecision.BLOCK


def test_confidence_risk_gap_confirms():
    result, tool_def, gate = _ctx()
    gap = SimpleNamespace(available=True, escalate=True, level="confirm")
    cmp = shadow_compare(tool_def=tool_def, result=result, gate_decision=gate,
                         confidence_risk_gap=gap)
    assert cmp.trust == TrustDecision.CONFIRM


# ---- CG decision-gate regression (off vs on) -------------------------------

def _cg_state(vritti):
    s = [0.1] * 32
    s[0:12] = [1.0 / 12] * 12
    s[12:17] = [0.3] * 5
    s[17:22] = vritti
    s[22:28] = [0.5] * 6
    s[28:32] = [0.0] * 4
    return s


def _cg_gateway(*, cg_enabled: bool) -> SafeMCPGateway:
    gw = SafeMCPGateway(
        mcp_client=MockMCPClient(),
        signal_config=SignalConfig(enable_cg_state_signals=cg_enabled),
        trust_mode=TrustMode.SHADOW,
    )
    gw.mcp_client.register_tool("cg_write", lambda p: "ok", ToolRiskLevel.WRITE)
    gw.tool_definitions["cg_write"] = MCPToolDefinition(
        name="cg_write", description="cg write", risk_level=ToolRiskLevel.WRITE)
    return gw


_HIGH_ERROR_VRITTI = [0.05, 0.80, 0.05, 0.05, 0.05]   # viparyaya-dominant (trips JEPA)


def test_cg_recorded_and_inert_when_disabled():
    gw_off = _cg_gateway(cg_enabled=False)
    gw_base = _cg_gateway(cg_enabled=False)
    withcg = _run(gw_off.call_tool_simple("cg_write", {"x": 1}, 0.9, 0.9,
                                          cg_metadata={"state": _cg_state(_HIGH_ERROR_VRITTI)}))
    nocg = _run(gw_base.call_tool_simple("cg_write", {"x": 1}, 0.9, 0.9))
    # CG attached but disabled → inert for the decision, yet recorded as "real".
    assert withcg.decision == nocg.decision
    assert gw_off.audit_log[-1].vritti_signal_source == "real"


def test_cg_can_affect_decision_when_enabled():
    gw_on = _cg_gateway(cg_enabled=True)
    gw_off = _cg_gateway(cg_enabled=False)
    on = _run(gw_on.call_tool_simple("cg_write", {"x": 1}, 0.9, 0.9,
                                     cg_metadata={"state": _cg_state(_HIGH_ERROR_VRITTI)}))
    off = _run(gw_off.call_tool_simple("cg_write", {"x": 1}, 0.9, 0.9,
                                       cg_metadata={"state": _cg_state(_HIGH_ERROR_VRITTI)}))
    on_entry = gw_on.audit_log[-1]
    off_entry = gw_off.audit_log[-1]
    # With CG enabled the real (viparyaya-dominant) vritti drives JEPA; disabled uses the
    # non-CG approximation. The CG-derived signal must be ABLE to change the outcome —
    # observable as a different decision or a different JEPA regime.
    assert (on.decision != off.decision) or (on_entry.jepa_regime != off_entry.jepa_regime)


# ---- Phase 1.5A: authority-policy demotion ----------------------------------

def test_jepa_demotion_relaxes_block_to_confirm_not_allow():
    # A JEPA-only block: PARITY blocks; REVIEWED (JEPA provisional) → CONFIRM, never ALLOW.
    result, tool_def, gate = _ctx(risk="write")
    jepa = SimpleNamespace(regime=SimpleNamespace(value="dual_anomaly"))
    parity = shadow_compare(tool_def=tool_def, result=result, gate_decision=gate,
                            jepa_assessment=jepa, policy=PARITY_POLICY)
    reviewed = shadow_compare(tool_def=tool_def, result=result, gate_decision=gate,
                              jepa_assessment=jepa, policy=REVIEWED_POLICY)
    assert parity.trust == TrustDecision.BLOCK
    assert reviewed.trust == TrustDecision.CONFIRM        # relaxed, still human-gated
    assert reviewed.trust != TrustDecision.ALLOW          # never a silent allow


def test_domain_kept_blocking_under_reviewed():
    result, tool_def, gate = _ctx()
    domain = SimpleNamespace(mode=DomainActionMode.BLOCKED)
    reviewed = shadow_compare(tool_def=tool_def, result=result, gate_decision=gate,
                              domain_result=domain, policy=REVIEWED_POLICY)
    assert reviewed.trust == TrustDecision.BLOCK


def test_shadow_kept_blocking_under_reviewed():
    result, tool_def, gate = _ctx()
    shadow = SimpleNamespace(containment_mode=SimpleNamespace(value="quarantined"))
    reviewed = shadow_compare(tool_def=tool_def, result=result, gate_decision=gate,
                              shadow_assessment=shadow, policy=REVIEWED_POLICY)
    assert reviewed.trust == TrustDecision.BLOCK


def test_jepa_demotion_classified_intended_when_legacy_blocked():
    # legacy BLOCKED solely via JEPA; under REVIEWED the difference is a reviewed demotion.
    result, tool_def, gate = _ctx(decision="blocked", risk="write")
    jepa = SimpleNamespace(regime=SimpleNamespace(value="process_drift"))
    cmp = shadow_compare(tool_def=tool_def, result=result, gate_decision=gate,
                         jepa_assessment=jepa, policy=REVIEWED_POLICY)
    assert cmp.legacy == TrustDecision.BLOCK
    assert cmp.trust == TrustDecision.CONFIRM
    assert cmp.classification == "intended"


# ---- Phase 1.5B: trust_core authoritative flip (safe, opt-in) ---------------

def _jepa_block_gateway(*, trust_mode, policy):
    gw = SafeMCPGateway(mcp_client=MockMCPClient(), trust_mode=trust_mode)
    gw._trust_authority_policy = policy
    gw.mcp_client.register_tool("jw", lambda p: "ok", ToolRiskLevel.WRITE)
    gw.tool_definitions["jw"] = MCPToolDefinition(
        name="jw", description="", risk_level=ToolRiskLevel.WRITE, min_confidence=0.0)
    return gw


def _jepa_block_call():
    # low quality/coherence trips JEPA process_drift; min_confidence=0 keeps the floor SAFE
    return MCPToolCall(tool_name="jw", parameters={"x": 1},
                       quality_score=0.05, coherence_score=0.05, raw_entropy=0.1)


def test_trust_core_default_policy_keeps_jepa_block():
    # TRUST_CORE but PARITY policy (jepa PROVEN) → no relaxation → still blocked.
    gw = _jepa_block_gateway(trust_mode=TrustMode.TRUST_CORE, policy=PARITY_POLICY)
    r = _run(gw.call_tool(_jepa_block_call()))
    assert r.decision.value == "blocked"


def test_shadow_mode_never_relaxes_behavior():
    # SHADOW + REVIEWED must NOT change runtime behavior — still blocked (shadow only audits).
    gw = _jepa_block_gateway(trust_mode=TrustMode.SHADOW, policy=REVIEWED_POLICY)
    r = _run(gw.call_tool(_jepa_block_call()))
    assert r.decision.value == "blocked"


def test_trust_core_reviewed_relaxes_jepa_block_to_human_confirm_not_allow():
    # TRUST_CORE + REVIEWED (jepa demoted): the JEPA-only block is relaxed to require human
    # confirmation. It must NOT be a hard block and must NOT be a silent allow — the default
    # escalation handler denies/does-not-confirm, so the safe outcome is ESCALATE.
    gw = _jepa_block_gateway(trust_mode=TrustMode.TRUST_CORE, policy=REVIEWED_POLICY)
    r = _run(gw.call_tool(_jepa_block_call()))
    assert r.decision.value != "blocked"            # relaxed
    assert r.decision.value != "allowed"            # but NOT a silent allow (no human yes)
    assert r.decision.value == "escalate"


# ---- harness smoke ----------------------------------------------------------

def test_parity_harness_parity_policy_all_match():
    from experiments.trust_signal.parity_harness import run_harness
    report = run_harness(PARITY_POLICY)
    c = report["counts"]
    assert c.get("unintended", 0) == 0
    assert c.get("unsafe_relaxation", 0) == 0
    assert c.get("match", 0) == len(report["rows"])


def test_parity_harness_reviewed_policy_only_intended_and_safe():
    from experiments.trust_signal.parity_harness import run_harness
    report = run_harness(REVIEWED_POLICY)
    c = report["counts"]
    assert c.get("unintended", 0) == 0           # no unreviewed mismatches
    assert c.get("unsafe_relaxation", 0) == 0    # no BLOCK/CONFIRM → ALLOW
    assert c.get("intended", 0) >= 1             # the JEPA demotion is exercised
