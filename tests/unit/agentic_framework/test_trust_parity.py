"""
test_trust_parity.py — Phase 1.5 parity mapping coverage + CG decision-gate regression.

Two layers:
  * unit parity over the legacy-authority mapping (JEPA DENY/DEFER, domain modes, shadow
    containment modes) via shadow_compare with crafted inputs — deterministic, exhaustive;
  * an integration CG decision-gate regression: CG-derived vritti is recorded in audit and
    is INERT when enable_cg_state_signals=False, but CAN change the decision when True.
  * a harness smoke test (zero unintended/unsafe_relaxation on the focused corpus).
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
    # every intermediate containment mode is a legacy DEFER → CONFIRM (must not relax to ALLOW)
    ("observe_only", TrustDecision.CONFIRM),
    ("read_only", TrustDecision.CONFIRM),
    ("draft_only", TrustDecision.CONFIRM),
    ("sandbox_only", TrustDecision.CONFIRM),
    ("memory_write_denied", TrustDecision.CONFIRM),
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


# ---- permission-overclaim observable (PROVISIONAL advisory) -----------------

def test_overclaim_escalates_to_confirm_and_classifies_intended():
    from agentic.agentic_framework.trust.permission_overclaim import PermissionContext
    result, tool_def, gate = _ctx(decision="allowed")     # legacy ALLOWs a clean tool
    ctx = PermissionContext(requested_authority="admin", granted_authority="read")
    cmp = shadow_compare(tool_def=tool_def, result=result, gate_decision=gate,
                         permission_context=ctx)
    assert cmp.legacy == TrustDecision.ALLOW
    assert cmp.trust == TrustDecision.CONFIRM            # advisory escalation (never blocks)
    assert cmp.classification == "intended"             # stricter-only, not unintended
    assert "permission_overclaim" in [o.name for o in cmp.outcome.drivers]


def test_overclaim_does_not_relax_a_real_block():
    # The observable only ever raises trust; a real (domain) BLOCK dominates the overclaim
    # CONFIRM by weakest-link → still BLOCK, classified match, never unsafe_relaxation.
    from agentic.agentic_framework.trust.permission_overclaim import PermissionContext
    result, tool_def, gate = _ctx(decision="blocked")
    domain = SimpleNamespace(mode=DomainActionMode.BLOCKED)
    ctx = PermissionContext(policy_bypass_requested=True)
    cmp = shadow_compare(tool_def=tool_def, result=result, gate_decision=gate,
                         domain_result=domain, permission_context=ctx)
    assert cmp.trust == TrustDecision.BLOCK
    assert cmp.classification == "match"
    assert cmp.classification != "unsafe_relaxation"
    assert "permission_overclaim" in [o.name for o in cmp.outcome.observations]


def test_no_permission_context_is_inert_match():
    # Absent context → no overclaim observation → decision identical to baseline (match).
    result, tool_def, gate = _ctx(decision="allowed")
    cmp = shadow_compare(tool_def=tool_def, result=result, gate_decision=gate)
    assert cmp.classification == "match"
    assert "permission_overclaim" not in [o.name for o in cmp.outcome.observations]


# ---- outcome-reputation observable (PROVISIONAL advisory) -------------------

def test_reputation_escalates_to_confirm_and_classifies_intended():
    from agentic.agentic_framework.trust.outcome_reputation import (
        ReputationStats)
    result, tool_def, gate = _ctx(decision="allowed")    # legacy ALLOWs a clean tool
    # poor history: mostly denied (approval_rate 0.2), enough volume/adjudication
    stats = ReputationStats(action_key="t", n=8, approvals=1, denials=4)
    cmp = shadow_compare(tool_def=tool_def, result=result, gate_decision=gate,
                         reputation_context=stats)
    assert cmp.legacy == TrustDecision.ALLOW
    assert cmp.trust == TrustDecision.CONFIRM            # advisory escalation
    assert cmp.classification == "intended"
    assert "outcome_reputation" in [o.name for o in cmp.outcome.drivers]


def test_good_reputation_and_below_volume_are_inert():
    from agentic.agentic_framework.trust.outcome_reputation import ReputationStats
    result, tool_def, gate = _ctx(decision="allowed")
    good = ReputationStats(action_key="t", n=10, approvals=8)        # SAFE
    assert shadow_compare(tool_def=tool_def, result=result, gate_decision=gate,
                          reputation_context=good).classification == "match"
    thin = ReputationStats(action_key="t", n=3, denials=3)           # below MIN_VOLUME
    cmp = shadow_compare(tool_def=tool_def, result=result, gate_decision=gate,
                         reputation_context=thin)
    assert cmp.classification == "match"
    assert "outcome_reputation" not in [o.name for o in cmp.outcome.observations]


# ---- hallucinated-capability observable (PROVISIONAL advisory) --------------

def test_hallucinated_capability_escalates_to_confirm_intended():
    from agentic.agentic_framework.trust.hallucinated_capability import CapabilityContext
    result, tool_def, gate = _ctx(decision="allowed")
    ctx = CapabilityContext(referenced_tools=("teleport",),
                            available_tools=frozenset({"file_read"}))
    cmp = shadow_compare(tool_def=tool_def, result=result, gate_decision=gate,
                         capability_context=ctx)
    assert cmp.legacy == TrustDecision.ALLOW
    assert cmp.trust == TrustDecision.CONFIRM
    assert cmp.classification == "intended"
    assert "hallucinated_capability" in [o.name for o in cmp.outcome.drivers]


def test_hallucinated_valid_and_absent_are_inert():
    from agentic.agentic_framework.trust.hallucinated_capability import CapabilityContext
    result, tool_def, gate = _ctx(decision="allowed")
    valid = CapabilityContext(referenced_tools=("file_read",),
                              available_tools=frozenset({"file_read"}))
    assert shadow_compare(tool_def=tool_def, result=result, gate_decision=gate,
                          capability_context=valid).classification == "match"
    cmp = shadow_compare(tool_def=tool_def, result=result, gate_decision=gate)
    assert "hallucinated_capability" not in [o.name for o in cmp.outcome.observations]


# ---- plan-action-consistency observable (PROVISIONAL advisory) --------------

def test_plan_action_escalates_to_confirm_intended():
    from agentic.agentic_framework.trust.plan_action_consistency import PlanActionContext
    result, tool_def, gate = _ctx(decision="allowed")
    ctx = PlanActionContext(stated_plan="read and summarize the report",
                            proposed_action="delete_report", action_args={"id": "q3"})
    cmp = shadow_compare(tool_def=tool_def, result=result, gate_decision=gate,
                         plan_action_context=ctx)
    assert cmp.legacy == TrustDecision.ALLOW
    assert cmp.trust == TrustDecision.CONFIRM
    assert cmp.classification == "intended"
    assert "plan_action_consistency" in [o.name for o in cmp.outcome.drivers]


def test_plan_action_consistent_and_absent_inert():
    from agentic.agentic_framework.trust.plan_action_consistency import PlanActionContext
    result, tool_def, gate = _ctx(decision="allowed")
    ok = PlanActionContext(stated_plan="read the logs", proposed_action="read_logs")
    assert shadow_compare(tool_def=tool_def, result=result, gate_decision=gate,
                          plan_action_context=ok).classification == "match"
    cmp = shadow_compare(tool_def=tool_def, result=result, gate_decision=gate)
    assert "plan_action_consistency" not in [o.name for o in cmp.outcome.observations]


# ---- forbidden-capability HARD_VETO (hard pre-gate parity) ------------------

def _forbidden_ctx(cap="credential_access", *, decision="blocked", risk="write",
                   confidence=0.99, min_confidence=0.0):
    result = SimpleNamespace(decision=SimpleNamespace(value=decision),
                             human_confirmed=False, confidence=confidence)
    tool_def = SimpleNamespace(min_confidence=min_confidence, requires_confirmation=False,
                               risk_level=SimpleNamespace(value=risk), capabilities=[cap])
    gate = SimpleNamespace(execution=SimpleNamespace(can_execute=True),
                           escalation=SimpleNamespace(requires_human=False))
    return result, tool_def, gate


def test_forbidden_capability_hard_veto_blocks():
    result, tool_def, gate = _forbidden_ctx()
    cmp = shadow_compare(tool_def=tool_def, result=result, gate_decision=gate,
                         forbidden_capabilities={"credential_access"})
    assert cmp.legacy == TrustDecision.BLOCK
    assert cmp.trust == TrustDecision.BLOCK          # trust reproduces the legacy BLOCK
    assert cmp.classification == "match"
    assert "forbidden_capability" in [o.name for o in cmp.outcome.drivers]


def test_forbidden_veto_unoverridable_by_confidence_and_gap():
    # Max confidence + a confidence-risk gap escalation must NOT lower the veto below BLOCK.
    result, tool_def, gate = _forbidden_ctx(confidence=0.999)
    gap = SimpleNamespace(available=True, escalate=True, level="confirm")
    cmp = shadow_compare(tool_def=tool_def, result=result, gate_decision=gate,
                         confidence_risk_gap=gap,
                         forbidden_capabilities={"credential_access"})
    assert cmp.trust == TrustDecision.BLOCK


def test_forbidden_veto_holds_under_reviewed_policy():
    # The HARD_VETO is PROVEN regardless of authority policy (not demotable like JEPA).
    result, tool_def, gate = _forbidden_ctx(cap="privilege_escalation")
    cmp = shadow_compare(tool_def=tool_def, result=result, gate_decision=gate,
                         forbidden_capabilities={"privilege_escalation"},
                         policy=REVIEWED_POLICY)
    assert cmp.trust == TrustDecision.BLOCK and cmp.classification == "match"


def test_non_forbidden_capability_adds_no_veto():
    result, tool_def, gate = _forbidden_ctx(cap="read_files", decision="allowed")
    cmp = shadow_compare(tool_def=tool_def, result=result, gate_decision=gate,
                         forbidden_capabilities={"credential_access"})
    assert cmp.trust == TrustDecision.ALLOW          # no false veto / no regression
    assert "forbidden_capability" not in [o.name for o in cmp.outcome.observations]


# ---- shadow driver attribution (reporting only — no decision change) --------
# A shadow escalation that is SOLELY caused by a derived (JEPA-regime / semantic-mismatch)
# signal is attributed to a distinct driver name so a future demotion is measurable from the
# persisted trust_shadow.drivers. The verdict/authority/decision are never affected.

def _shadow(containment, reason_codes=()):
    return SimpleNamespace(containment_mode=SimpleNamespace(value=containment),
                           reason_codes=tuple(reason_codes))


def _shadow_cmp(shadow):
    result, tool_def, gate = _ctx()
    return shadow_compare(tool_def=tool_def, result=result, gate_decision=gate,
                          shadow_assessment=shadow)


def test_shadow_jepa_derived_block_is_attributed_not_hidden():
    # QUARANTINE caused ONLY by the JEPA-regime escalation → reattributed, not hidden
    # behind the generic `shadow` driver. Decision is still BLOCK.
    cmp = _shadow_cmp(_shadow("quarantined",
                              ["UNKNOWN_ASSET:x", "JEPA_REGIME_ESCALATION:dual_anomaly"]))
    names = [o.name for o in cmp.outcome.drivers]
    assert "shadow_jepa_derived" in names
    assert "shadow" not in names                       # generic name no longer used here
    assert cmp.trust == TrustDecision.BLOCK            # decision unchanged


def test_shadow_semantic_derived_confirm_is_attributed():
    cmp = _shadow_cmp(_shadow("require_confirmation",
                              ["SEMANTIC_MISMATCH_ESCALATION:mismatch=0.50"]))
    names = [o.name for o in cmp.outcome.drivers]
    assert "shadow_semantic_derived" in names
    assert cmp.trust == TrustDecision.CONFIRM


def test_shadow_deterministic_rule_keeps_generic_name():
    # A named declarative rule (policy-backed) keeps `shadow`, even when a derived escalation
    # ALSO fired — the block stands on policy grounds (conservative: no demotion over-claim).
    cmp = _shadow_cmp(_shadow("quarantined",
                              ["RULE:unapproved_mcp_quarantine:quarantined",
                               "JEPA_REGIME_ESCALATION:dual_anomaly"]))
    names = [o.name for o in cmp.outcome.drivers]
    assert "shadow" in names and "shadow_jepa_derived" not in names


def test_shadow_failclosed_keeps_generic_name():
    cmp = _shadow_cmp(_shadow("blocked", ["FAIL_CLOSED:shadow_mutating"]))
    names = [o.name for o in cmp.outcome.drivers]
    assert "shadow" in names and "shadow_jepa_derived" not in names


def test_shadow_safe_is_never_reattributed():
    # SAFE shadow does not escalate → stays generic `shadow` (a cleared gate, not a raiser),
    # even if a derived reason code is present.
    cmp = _shadow_cmp(_shadow("allow", ["JEPA_REGIME_ESCALATION:dual_anomaly"]))
    names = [o.name for o in cmp.outcome.drivers]
    assert "shadow" in names
    assert all(not n.startswith("shadow_") for n in names)


def test_attribution_is_reporting_only_decision_and_class_unchanged():
    # Identical containment, with vs without derived reason codes → identical decision AND
    # mismatch classification; ONLY the driver name differs. Proves reporting-only.
    plain = _shadow_cmp(_shadow("quarantined"))                       # legacy-style, no codes
    derived = _shadow_cmp(_shadow("quarantined",
                                  ["JEPA_REGIME_ESCALATION:dual_anomaly"]))
    assert plain.trust == derived.trust                              # decision identical
    assert plain.legacy == derived.legacy
    assert plain.classification == derived.classification            # mismatch class identical
    assert "shadow" in {o.name for o in plain.outcome.drivers}
    assert "shadow_jepa_derived" in {o.name for o in derived.outcome.drivers}


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
    assert c.get("intended", 0) >= 3             # JEPA DEFER + two JEPA DENY demotions


def test_broadened_corpus_covers_each_authority():
    # The broadened in-scope corpus stresses every mapped authority at least once.
    from experiments.trust_signal.parity_harness import CORPUS
    authorities = {s.authority for s in CORPUS}
    assert {"confidence_risk_gap", "raw_entropy", "jepa", "domain", "shadow",
            "approval", "confidence_floor"} <= authorities
    assert len(CORPUS) >= 24


def test_in_scope_flip_gate_clean_and_default_exit_zero():
    from experiments.trust_signal.parity_harness import build_report, exit_code
    res = build_report()
    rev = res["in_scope"]["reviewed"]["counts"]
    assert rev.get("unintended", 0) == 0
    assert rev.get("unsafe_relaxation", 0) == 0
    assert exit_code(res) == 0                    # in-scope clean → default exit 0


def test_forbidden_hard_veto_now_mapped_in_scope():
    # The forbidden-capability / overclaim hard veto is now a PROVEN HARD_VETO observation:
    # every such scenario reproduces legacy BLOCK == trust BLOCK (match), and all exit
    # codes are 0 (including the compat --strict-pregate path).
    from experiments.trust_signal.parity_harness import (
        build_report, exit_code, _hard_veto_rows)
    res = build_report()
    veto = _hard_veto_rows(res["in_scope"]["reviewed"])
    assert len(veto) >= 3
    for r in veto:
        assert r["legacy"] == "block" and r["trust"] == "block" and r["class"] == "match"
        assert "forbidden_capability" in r["drivers"]
    assert exit_code(res, strict_pregate=False) == 0
    assert exit_code(res, strict_pregate=True) == 0   # compat no-op, still clean


def test_external_cohort_parity_clean_if_fixtures_present():
    # AgentDojo/InjecAgent minisets, mapped structurally, must reproduce legacy (no
    # unintended / unsafe_relaxation) — this is what the shadow intermediate-containment
    # parity fix guarantees. Skips cleanly if the committed fixtures are absent.
    from experiments.trust_signal.parity_harness import external_scenarios, run_harness
    ext = external_scenarios()
    if not ext:
        import pytest as _pytest
        _pytest.skip("external fixtures not present")
    for policy in (PARITY_POLICY, REVIEWED_POLICY):
        c = run_harness(policy, ext)["counts"]
        assert c.get("unintended", 0) == 0
        assert c.get("unsafe_relaxation", 0) == 0
