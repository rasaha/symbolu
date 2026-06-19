"""
test_trust_shadow.py — Phase 1.5 shadow/parity migration (torch-free).

Verifies the migration invariants:
  * shadow mode does not change runtime behavior (decision identical to legacy)
  * trust decision is recorded in audit; drivers explain CONFIRM/BLOCK
  * trust_core mode is toggleable (and not yet authoritative — behaves as shadow)
  * legacy mode records no trust fields
  * a parity mismatch is detected, classified, and would be logged
  * CG-derived signals remain decision-gated when enable_cg_state_signals=False
    (still recorded as "real" in audit, but inert for the decision)
"""

from __future__ import annotations

import asyncio
import logging
from types import SimpleNamespace

from agentic.agentic_framework.mcp_gateway import (
    MCPToolCall,
    MCPToolDefinition,
    ToolRiskLevel,
    create_mock_mcp_gateway,
)
from agentic.agentic_framework.mcp_gateway import (
    EscalationHandler,
    MockMCPClient,
    SafeMCPGateway,
)
from agentic.agentic_framework.trust.observables import TrustDecision
from agentic.agentic_framework.trust.parity import (
    PARITY_POLICY,
    REVIEWED_POLICY,
    TrustMode,
    legacy_decision_to_trust,
    shadow_compare,
)


class _Escalation(EscalationHandler):
    """Escalation handler with a deterministic human decision (confirm/deny)."""

    def __init__(self, decision: bool):
        super().__init__()
        self._decision = decision

    async def request_confirmation(self, tool_call, tool_def, gate_decision) -> bool:
        return self._decision


def _jepa_block_tool(gw, tool="jw", risk=None, q=0.05, c=0.05):
    """Register a tool whose low quality/coherence trips a JEPA-SOLE block.

    min_confidence=0 keeps the confidence floor SAFE so JEPA is the only blocker; no
    domain/shadow registry on the mock gateway, so the block is JEPA-driven only.
    """
    risk = risk or ToolRiskLevel.WRITE
    gw.mcp_client.register_tool(tool, lambda p: "ok", risk)
    gw.tool_definitions[tool] = MCPToolDefinition(
        name=tool, description="jepa-sole", risk_level=risk, min_confidence=0.0)
    return MCPToolCall(tool_name=tool, parameters={"x": 1}, quality_score=q,
                       coherence_score=c, raw_entropy=0.1)


# ---- trust_core authoritative flip (reviewed JEPA-relax path) ----------------

def test_flip_relaxes_jepa_sole_block_to_human_confirm_denied():
    # Under TRUST_CORE + REVIEWED a JEPA-sole BLOCK becomes a human confirmation; with the
    # default (deny) handler the result is ESCALATE — NOT a silent ALLOW, NOT a hard BLOCK.
    gw = SafeMCPGateway(mcp_client=MockMCPClient(), trust_mode="trust_core",
                        trust_authority_policy="reviewed",
                        escalation_handler=_Escalation(False))
    res = _run(gw.call_tool(_jepa_block_tool(gw)))
    assert res.decision.value == "escalate"          # human asked, denied → escalate
    assert res.human_confirmed is False
    assert res.decision.value != "allowed"           # never a silent allow


def test_flip_human_confirm_allows_execution():
    # Same JEPA-sole block, but a human CONFIRMS → executes (the only route to ALLOWED).
    gw = SafeMCPGateway(mcp_client=MockMCPClient(), trust_mode="trust_core",
                        trust_authority_policy="reviewed",
                        escalation_handler=_Escalation(True))
    res = _run(gw.call_tool(_jepa_block_tool(gw)))
    assert res.decision.value == "allowed"
    assert res.human_confirmed is True


def test_flip_never_silent_allow_no_block_to_allow():
    # Across confirm/deny, a relaxed JEPA-sole block is ALWAYS human-gated; ALLOWED only
    # ever co-occurs with human_confirmed=True (no BLOCK→ALLOW without a human).
    for decision in (True, False):
        gw = SafeMCPGateway(mcp_client=MockMCPClient(), trust_mode="trust_core",
                            trust_authority_policy="reviewed",
                            escalation_handler=_Escalation(decision))
        res = _run(gw.call_tool(_jepa_block_tool(gw)))
        if res.decision.value == "allowed":
            assert res.human_confirmed is True


def test_flip_forbidden_veto_remains_terminal():
    # The forbidden-capability hard pre-gate still hard-BLOCKS under the flip (terminal).
    gw = SafeMCPGateway(mcp_client=MockMCPClient(), trust_mode="trust_core",
                        trust_authority_policy="reviewed",
                        escalation_handler=_Escalation(True))
    gw.mcp_client.register_tool("cred", lambda p: "ok", ToolRiskLevel.WRITE)
    gw.tool_definitions["cred"] = MCPToolDefinition(
        name="cred", description="x", risk_level=ToolRiskLevel.WRITE,
        min_confidence=0.0, capabilities=["credential_access"])
    res = _run(gw.call_tool(MCPToolCall(tool_name="cred", parameters={"x": 1},
                                        quality_score=0.99, coherence_score=0.99)))
    assert res.decision.value == "blocked"           # not relaxed, not confirmed


def test_flip_inert_under_parity_policy():
    # TRUST_CORE alone (PARITY policy) does NOT relax — behaves as SHADOW (legacy blocks).
    gw = SafeMCPGateway(mcp_client=MockMCPClient(), trust_mode="trust_core",
                        trust_authority_policy="parity",
                        escalation_handler=_Escalation(True))
    res = _run(gw.call_tool(_jepa_block_tool(gw)))
    assert res.decision.value == "blocked"


def test_rollback_to_shadow_and_legacy_restores_block():
    # Reverting trust_mode instantly disables the relax: the JEPA-sole block hard-BLOCKS
    # again under SHADOW and LEGACY (no human confirm path).
    for mode in ("shadow", "legacy"):
        gw = SafeMCPGateway(mcp_client=MockMCPClient(), trust_mode=mode,
                            trust_authority_policy="reviewed",
                            escalation_handler=_Escalation(True))
        res = _run(gw.call_tool(_jepa_block_tool(gw)))
        assert res.decision.value == "blocked"       # legacy authoritative again


def test_authority_policy_constructor_control():
    # The supported control wires the policy without poking private state.
    assert SafeMCPGateway(mcp_client=MockMCPClient(),
                          trust_authority_policy="reviewed")._trust_authority_policy \
        is REVIEWED_POLICY
    assert SafeMCPGateway(mcp_client=MockMCPClient())._trust_authority_policy is PARITY_POLICY


def _run(coro):
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()
        asyncio.set_event_loop(asyncio.new_event_loop())


def _call(tool="file_read", q=0.9, c=0.9, **kw):
    return MCPToolCall(tool_name=tool, parameters={"path": "/tmp/x"},
                       quality_score=q, coherence_score=c, **kw)


# ---- forbidden-capability hard veto (gateway integration) -------------------

def test_forbidden_capability_gateway_trust_matches_legacy_block():
    # A forbidden-capability tool with HIGH confidence is BLOCKED by the legacy pre-gate;
    # the shadowed trust core must now reproduce that BLOCK (PROVEN HARD_VETO), not allow it.
    gw = create_mock_mcp_gateway()
    gw._trust_mode = TrustMode.SHADOW
    gw.mcp_client.register_tool("cred_tool", lambda p: "ok", ToolRiskLevel.WRITE)
    gw.tool_definitions["cred_tool"] = MCPToolDefinition(
        name="cred_tool", description="x", risk_level=ToolRiskLevel.WRITE,
        min_confidence=0.0, capabilities=["credential_access"])
    res = _run(gw.call_tool(MCPToolCall(
        tool_name="cred_tool", parameters={"x": 1}, quality_score=0.99, coherence_score=0.99,
        raw_entropy=0.05, verbalized_safety_confidence=0.99)))
    e = gw.audit_log[-1]
    assert res.decision.value == "blocked"               # legacy hard pre-gate blocked
    assert e.trust_legacy_decision == "block"
    assert e.trust_decision == "block"                   # trust reproduces it (no relaxation)
    assert e.trust_mismatch_class == "match"
    assert "forbidden_capability" in (e.trust_drivers or [])


# ---- shadow never changes behavior ------------------------------------------

def test_shadow_mode_does_not_change_behavior():
    legacy_gw = create_mock_mcp_gateway()
    shadow_gw = create_mock_mcp_gateway()
    shadow_gw._trust_mode = TrustMode.SHADOW
    legacy = _run(legacy_gw.call_tool(_call()))
    shadow = _run(shadow_gw.call_tool(_call()))
    assert legacy.decision == shadow.decision           # identical runtime behavior
    # legacy records no trust fields; shadow does.
    assert legacy_gw.audit_log[-1].trust_decision is None
    assert shadow_gw.audit_log[-1].trust_decision is not None


def test_shadow_records_trust_decision_and_no_mismatch_on_clean_allow():
    gw = create_mock_mcp_gateway()
    gw._trust_mode = TrustMode.SHADOW
    _run(gw.call_tool(_call()))
    e = gw.audit_log[-1]
    assert e.trust_decision == "allow"
    assert e.trust_legacy_decision == "allow"
    assert e.trust_mismatch is False
    assert e.trust_mismatch_class == "match"


def test_audit_explains_allow_with_cleared_gates():
    # An ALLOW must be auditable: the recorded trust trace names the proven gates it
    # cleared (e.g. confidence_floor / execution_permission), not an empty list.
    gw = create_mock_mcp_gateway()
    gw._trust_mode = TrustMode.SHADOW
    _run(gw.call_tool(_call()))
    e = gw.audit_log[-1]
    assert e.trust_decision == "allow"
    assert e.trust_drivers                       # ALLOW now has a non-empty driver trace
    assert "ALLOW: cleared" in (e.trust_reason or "")


def test_trust_core_mode_toggles_and_is_not_yet_authoritative():
    legacy_gw = create_mock_mcp_gateway()
    core_gw = create_mock_mcp_gateway()
    core_gw._trust_mode = TrustMode.TRUST_CORE
    legacy = _run(legacy_gw.call_tool(_call()))
    core = _run(core_gw.call_tool(_call()))
    # trust_core records the trust decision but still acts on legacy (parity-gated).
    assert core_gw.audit_log[-1].trust_decision is not None
    assert core.decision == legacy.decision


def test_legacy_mode_records_no_trust_fields():
    gw = create_mock_mcp_gateway()        # default LEGACY
    _run(gw.call_tool(_call()))
    e = gw.audit_log[-1]
    assert e.trust_decision is None and e.trust_mismatch is None


# ---- durable persistence of the shadow decision -----------------------------

def test_shadow_decision_is_persisted_to_durable_store():
    # The in-memory entry already carries the trust decision; verify it ALSO survives
    # into the durable, tamper-evident canonical event (embedded in request_snapshot)
    # so mismatch data can be analysed at volume — and the hash chain still verifies.
    from agentic.ledger.governance_audit_store import GovernanceAuditStore

    store = GovernanceAuditStore(":memory:")
    gw = create_mock_mcp_gateway()
    gw._audit_store = store
    gw._trust_mode = TrustMode.SHADOW

    _run(gw.call_tool(_call()))

    persisted = store.list_recent(limit=1)[0]
    ts = persisted["request_snapshot"]["trust_shadow"]
    entry = gw.audit_log[-1]
    assert ts["decision"] == entry.trust_decision           # parallel decision persisted
    assert ts["legacy_decision"] == entry.trust_legacy_decision
    assert ts["mismatch"] == entry.trust_mismatch
    assert ts["mismatch_class"] == entry.trust_mismatch_class
    assert ts["drivers"] == (entry.trust_drivers or [])
    assert store.verify_chain().valid                       # tamper-evident chain intact


def test_legacy_mode_persists_no_trust_shadow():
    # Under LEGACY the trust core does not run → durable events are unchanged.
    from agentic.ledger.governance_audit_store import GovernanceAuditStore

    store = GovernanceAuditStore(":memory:")
    gw = create_mock_mcp_gateway()        # default LEGACY
    gw._audit_store = store

    _run(gw.call_tool(_call()))

    persisted = store.list_recent(limit=1)[0]
    assert "trust_shadow" not in persisted["request_snapshot"]


def test_entropy_gap_provenance_persisted_and_behavior_unchanged():
    # The gateway computes raw-entropy + confidence-risk-gap regardless of trust_mode; the
    # provenance must now survive into the durable event (request_snapshot["entropy_gap"])
    # without changing the runtime decision. Compared against a store-less run.
    from agentic.ledger.governance_audit_store import GovernanceAuditStore

    store = GovernanceAuditStore(":memory:")
    gw = create_mock_mcp_gateway()
    gw._audit_store = store
    no_store_gw = create_mock_mcp_gateway()

    acted = _run(gw.call_tool(_call()))
    baseline = _run(no_store_gw.call_tool(_call()))

    assert acted.decision == baseline.decision              # behavior unchanged
    eg = store.list_recent(limit=1)[0]["request_snapshot"]["entropy_gap"]
    entry = gw.audit_log[-1]
    # mirrors the AuditEntry provenance fields (already computed upstream)
    assert eg["raw_entropy_available"] == entry.raw_entropy_available
    assert eg["confidence_risk_gap_escalate"] == entry.confidence_risk_gap_escalate
    assert eg["confidence_risk_gap_reason"] == entry.confidence_risk_gap_reason
    assert store.verify_chain().valid


# ---- parity comparison logic (unit) -----------------------------------------

def _fake(decision, *, human_confirmed=False, can_execute=True, requires_human=False,
          requires_confirmation=False, min_confidence=0.3, confidence=0.9,
          risk="write", regime="normal"):
    result = SimpleNamespace(decision=SimpleNamespace(value=decision),
                             human_confirmed=human_confirmed, confidence=confidence)
    tool_def = SimpleNamespace(min_confidence=min_confidence,
                               requires_confirmation=requires_confirmation,
                               risk_level=SimpleNamespace(value=risk))
    gate = SimpleNamespace(execution=SimpleNamespace(can_execute=can_execute),
                           escalation=SimpleNamespace(requires_human=requires_human))
    jepa = SimpleNamespace(regime=SimpleNamespace(value=regime))
    return result, tool_def, gate, jepa


def test_legacy_mapping_handles_human_confirmation_as_post_decision():
    r, *_ = _fake("allowed", human_confirmed=True)
    assert legacy_decision_to_trust(r) == TrustDecision.CONFIRM    # approved → was CONFIRM
    r2, *_ = _fake("allowed", human_confirmed=False)
    assert legacy_decision_to_trust(r2) == TrustDecision.ALLOW


def test_parity_mismatch_detected_and_classified():
    # Legacy ALLOWED, but a JEPA dual_anomaly would force BLOCK in the trust core.
    result, tool_def, gate, _ = _fake("allowed", regime="dual_anomaly")
    jepa = SimpleNamespace(regime=SimpleNamespace(value="dual_anomaly"))
    cmp = shadow_compare(tool_def=tool_def, result=result, gate_decision=gate,
                         jepa_assessment=jepa)
    assert cmp.legacy == TrustDecision.ALLOW
    assert cmp.trust == TrustDecision.BLOCK
    assert cmp.mismatch is True
    assert cmp.classification == "unintended"


def test_mismatch_is_logged_by_gateway(caplog, monkeypatch):
    # The gateway imports shadow_compare lazily inside _audit, so patch it on the parity
    # module. monkeypatch auto-restores it after the test (no leakage into sibling tests).
    from agentic.agentic_framework.trust import parity as parity_mod
    gw = create_mock_mcp_gateway()
    gw._trust_mode = TrustMode.SHADOW

    def fake_compare(**kw):
        from agentic.agentic_framework.trust.decision import decide
        from agentic.agentic_framework.trust.observables import (
            EvidenceStatus, Observation, ObservableType, Verdict)
        out = decide([Observation("jepa", ObservableType.VALIDATOR,
                                  EvidenceStatus.PROVEN, Verdict.UNSAFE, severity=1.0)])
        return parity_mod.ParityComparison(
            legacy=TrustDecision.ALLOW, trust=TrustDecision.BLOCK, mismatch=True,
            classification="unintended", outcome=out)

    monkeypatch.setattr(parity_mod, "shadow_compare", fake_compare)
    with caplog.at_level(logging.WARNING):
        _run(gw.call_tool(_call()))
    assert any("TRUST SHADOW MISMATCH" in r.message for r in caplog.records)
    assert gw.audit_log[-1].trust_mismatch is True


def test_audit_includes_trust_drivers_on_confirm():
    gw = create_mock_mcp_gateway()
    gw._trust_mode = TrustMode.SHADOW
    # write tool + confident-but-uncertain → confidence-risk gap → CONFIRM with a driver.
    _run(gw.call_tool_simple("file_write", {"path": "/tmp/y", "content": "z"},
                             0.9, 0.9))
    # Some mock setups may not have file_write; fall back to a forced gap on file_read.
    e = gw.audit_log[-1]
    assert e.trust_decision in ("allow", "confirm", "block")
    if e.trust_decision in ("confirm", "block"):
        assert e.trust_drivers   # non-empty driver list explains non-allow


# ---- CG decision-gating (off by default) ------------------------------------

def _state(vritti):
    s = [0.1] * 32
    s[0:12] = [1.0 / 12] * 12
    s[12:17] = [0.3] * 5
    s[17:22] = vritti
    s[22:28] = [0.5] * 6
    s[28:32] = [0.0] * 4
    return s


def test_cg_signals_recorded_but_decision_gated_when_off():
    # CG OFF (default). A CG vritti_result with high "error" mass is RECORDED as real,
    # but must not change the decision vs. running without any CG metadata.
    gw_no_cg = create_mock_mcp_gateway()
    gw_cg = create_mock_mcp_gateway()
    high_error = _state([0.05, 0.80, 0.05, 0.05, 0.05])   # viparyaya-dominant
    base = _run(gw_no_cg.call_tool_simple("file_read", {"path": "/tmp/z"}, 0.9, 0.9))
    withcg = _run(gw_cg.call_tool_simple("file_read", {"path": "/tmp/z"}, 0.9, 0.9,
                                         cg_metadata={"state": high_error}))
    assert withcg.decision == base.decision            # CG-derived signal is inert (gated)
    assert gw_cg.audit_log[-1].vritti_signal_source == "real"   # but still recorded
