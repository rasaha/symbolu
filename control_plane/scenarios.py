"""Integration scenario suite (Phase 9). Deterministic, provider-neutral. Each entry pairs
a Scenario with its expected terminal state (and an optional expected reason-code substring),
so the test suite and the mock evaluation can assert against ground truth.

Includes scenarios deliberately constructed so the integrated architecture can *lose*
(single-provider overhead; glue and unified reaching the same outcome at different cost).
No live calls; MOCK mode throughout.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import List, Optional

from control_plane.envelope import RequestEnvelope
from control_plane.orchestrator import Scenario

_ACTION_POLICY = {"permitted": ["notify"], "require_approval": ["payment"]}


def _env(trace_id: str, **kw) -> RequestEnvelope:
    d = dict(request_id=f"req_{trace_id}", trace_id=trace_id, required_capabilities=set(),
             action_policy=_ACTION_POLICY)
    d.update(kw)
    return RequestEnvelope(**d)


def _two(**overrides):
    a = {"provider": "anthropic", "model_id": "claude-x", "family": "claude",
         "quality": 0.85, "latency_ms": 800}
    b = {"provider": "google", "model_id": "gemma-y", "family": "gemma",
         "quality": 0.6, "latency_ms": 400}
    a.update(overrides.get("a", {}))
    b.update(overrides.get("b", {}))
    return [a, b]


@dataclass
class Case:
    scenario: Scenario
    expected_terminal: str
    expected_reason: Optional[str] = None
    can_lose: bool = False          # architecture may not beat a simple script here
    note: str = ""


def all_cases() -> List[Case]:
    C: List[Case] = []

    # 1 eligible model selected and successful (assertion-only)
    C.append(Case(Scenario("eligible_success", _env("s1"), _two()),
                  "ASSERTION_DELIVERED"))
    # 2 preferred model ineligible, fallback selected
    specs = _two(a={"signals": {"model_available": False}})
    C.append(Case(Scenario("preferred_ineligible_fallback", _env("s2"), specs),
                  "ASSERTION_DELIVERED", note="claude-x ineligible; gemma-y selected"))
    # 3 no eligible model
    none = [{"provider": "x", "model_id": "m", "family": "f", "signals": {"authenticated": False}}]
    C.append(Case(Scenario("no_eligible_model", _env("s3"), none),
                  "NO_ELIGIBLE_MODEL", "EXEC.NO_ELIGIBLE_MODEL"))
    # 4 model executes but assertion unsupported (rejected)
    C.append(Case(Scenario("assertion_rejected", _env("s4"), _two(), assertion="REJECT",
                           proposed_action="notify"),
                  "ASSERTION_REJECTED", "ASSERT.ASSERTION_REJECTED"))
    # 5 model executes but assertion requires qualification (proceeds)
    C.append(Case(Scenario("assertion_qualified", _env("s5"), _two(), assertion="QUALIFY"),
                  "ASSERTION_DELIVERED", note="QUALIFY proceeds; assertion delivered"))
    # 6 assertion accepted but proposed action denied (outside authority)
    C.append(Case(Scenario("action_denied", _env("s6"), _two(), proposed_action="delete_db"),
                  "ACTION_DENIED", "ACTION.ACTION_DENIED"))
    # 7 assertion accepted but action requires approval
    C.append(Case(Scenario("action_approval_required", _env("s7"), _two(), proposed_action="payment"),
                  "ACTION_APPROVAL_REQUIRED", "ACTION.ACTION_APPROVAL_REQUIRED"))
    # 8 action approved and executed (MOCK simulates; no real effect)
    C.append(Case(Scenario("action_allowed_executed", _env("s8"), _two(), proposed_action="notify"),
                  "COMPLETED", note="MOCK: action SIMULATED, not really executed"))
    # 9 action approved but execution fails — reachable only in ENFORCEMENT; MOCK simulates
    C.append(Case(Scenario("action_exec_fail_modegated", _env("s9"), _two(), proposed_action="notify"),
                  "COMPLETED", can_lose=False,
                  note="action-execution failure requires ENFORCEMENT (disabled); MOCK cannot fail"))
    # 10 stale eligibility evidence (only candidate goes INDETERMINATE)
    stale = [{"provider": "anthropic", "model_id": "claude-x", "family": "claude",
              "signals": {"billing_active": None}, "stale": {"billing_active": True}}]
    C.append(Case(Scenario("stale_eligibility_evidence", _env("s10"), stale),
                  "NO_ELIGIBLE_MODEL", note="INDETERMINATE -> not selectable -> fail-closed"))
    # 11 provider disappears after selection (no fallback)
    C.append(Case(Scenario("provider_disappears", _env("s11"), _two(), provider_fail=True),
                  "PROVIDER_FAILED", "RUNTIME.PROVIDER_EXECUTION_FAILED"))
    # 12 fallback bypass attempt (provider fails, fallback available)
    C.append(Case(Scenario("fallback_reentry", _env("s12"), _two(), provider_fail_then_ok=True,
                           proposed_action="notify"),
                  "COMPLETED", note="unified re-enters eligibility and selects fallback"))
    # 13 provider available but residency-prohibited
    res_specs = _two(a={"region": "us"}, b={"region": "us"})
    C.append(Case(Scenario("residency_prohibited", _env("s13", residency_requirements="eu"), res_specs),
                  "NO_ELIGIBLE_MODEL", note="region/residency mismatch -> INELIGIBLE"))
    # 14 model capability mismatch (tool_use required, none support it)
    cap_specs = _two()
    C.append(Case(Scenario("capability_mismatch",
                           _env("s14", required_capabilities={"tool_use"}), cap_specs),
                  "NO_ELIGIBLE_MODEL", note="feature required but unsupported"))
    # 15 human override on approval-required (attributable + rationale)
    C.append(Case(Scenario("human_override", _env("s15"), _two(), proposed_action="payment",
                           override_actor="ops:alice", override_rationale="approved ticket #42"),
                  "COMPLETED", note="explicit attributable override allows APPROVE_REQUIRED"))
    # 16 unauthorized override (actor without rationale)
    C.append(Case(Scenario("unauthorized_override", _env("s16"), _two(), proposed_action="payment",
                           override_actor="ops:bob"),
                  "UNAUTHORIZED_OVERRIDE", "AUDIT.UNAUTHORIZED_OVERRIDE"))
    # 17 low-risk assertion-only request
    C.append(Case(Scenario("low_risk_assertion_only",
                           _env("s17", task_risk_class="informational"), _two()),
                  "ASSERTION_DELIVERED"))
    # 18 high-risk action-producing request (permitted action)
    C.append(Case(Scenario("high_risk_action",
                           _env("s18", task_risk_class="decision-bearing",
                                provider_allowlist={"anthropic", "google"}),
                           _two(), proposed_action="notify"),
                  "COMPLETED"))
    # 19 multiple eligible models with equal utility (deterministic tie-break)
    tie = _two(a={"quality": 0.7, "latency_ms": 500, "model_id": "aaa"},
               b={"quality": 0.7, "latency_ms": 500, "model_id": "bbb"})
    C.append(Case(Scenario("equal_utility_tie", _env("s19"), tie),
                  "ASSERTION_DELIVERED", note="deterministic tie-break by internal id"))
    # 20 TAP unavailable -> safe fail-closed degradation
    C.append(Case(Scenario("tap_unavailable", _env("s20"), _two(), tap_unavailable=True,
                           proposed_action="notify"),
                  "GOVERNANCE_UNAVAILABLE", "RUNTIME.GOVERNANCE_COMPONENT_UNAVAILABLE"))
    # 21 ActionGate unavailable -> safe fail-closed degradation
    C.append(Case(Scenario("actiongate_unavailable", _env("s21"), _two(),
                           actiongate_unavailable=True, proposed_action="notify"),
                  "GOVERNANCE_UNAVAILABLE", "RUNTIME.GOVERNANCE_COMPONENT_UNAVAILABLE"))
    # 22 assertion escalated -> terminal human path
    C.append(Case(Scenario("assertion_escalated", _env("s22"), _two(), assertion="ESCALATE",
                           proposed_action="notify"),
                  "ASSERTION_ESCALATED", "ASSERT.ASSERTION_ESCALATED"))
    # 23 assertion constrained -> proceeds
    C.append(Case(Scenario("assertion_constrained", _env("s23"), _two(), assertion="CONSTRAIN"),
                  "ASSERTION_DELIVERED", note="CONSTRAIN proceeds"))
    # 24 action forced ESCALATE by gate -> terminal, no execution
    C.append(Case(Scenario("action_escalated", _env("s24"), _two(), proposed_action="notify",
                           forced_action_disposition="ESCALATE"),
                  "ACTION_ESCALATED", "ACTION.ACTION_DENIED"))
    # 25 action forced INDETERMINATE -> fail-closed, no execution (invariant 9)
    C.append(Case(Scenario("action_indeterminate", _env("s25"), _two(), proposed_action="notify",
                           forced_action_disposition="INDETERMINATE"),
                  "ACTION_INDETERMINATE", "ACTION.ACTION_DENIED"))
    # 26 action forced CONSTRAIN -> terminal (constrained, not executed as-proposed)
    C.append(Case(Scenario("action_constrained", _env("s26"), _two(), proposed_action="notify",
                           forced_action_disposition="CONSTRAIN"),
                  "ACTION_CONSTRAINED", "ACTION.ACTION_CONSTRAINED"))
    # 27 confidential data without approved provider flow -> data-flow refusal (invariant 16)
    C.append(Case(Scenario("data_flow_not_approved",
                           _env("s27", data_sensitivity="regulated", provider_allowlist=None),
                           _two()),
                  "REJECTED", "POLICY.DATA_FLOW_NOT_APPROVED"))
    # 28 incompatible envelope version -> fail-closed
    C.append(Case(Scenario("incompatible_envelope",
                           _env("s28", envelope_version="99"), _two()),
                  "REJECTED", "POLICY.CONTRACT_VERSION_UNSUPPORTED"))
    # 29 single-provider stable environment (architecture may not beat a script)
    single = [{"provider": "anthropic", "model_id": "claude-x", "family": "claude", "quality": 0.8}]
    C.append(Case(Scenario("single_provider_overhead", _env("s29"), single),
                  "ASSERTION_DELIVERED", can_lose=True,
                  note="one provider, no action: control-plane overhead may exceed benefit"))
    # 30 partial degradation: provider fails, no fallback, assertion-only intent
    C.append(Case(Scenario("partial_degradation", _env("s30"), _two(), provider_fail=True),
                  "PROVIDER_FAILED", "RUNTIME.PROVIDER_EXECUTION_FAILED"))
    # 31 model selected then action needs capability it lacks (denied by authority)
    C.append(Case(Scenario("downstream_capability_gap", _env("s31"), _two(),
                           proposed_action="unlisted_action"),
                  "ACTION_DENIED", "ACTION.ACTION_DENIED",
                  note="selected model fine, but proposed action outside authority envelope"))
    # 32 approval-required action, no override -> approval required (not executed)
    C.append(Case(Scenario("approval_required_no_override", _env("s32"), _two(),
                           proposed_action="payment"),
                  "ACTION_APPROVAL_REQUIRED", "ACTION.ACTION_APPROVAL_REQUIRED"))

    return C


def count() -> int:
    return len(all_cases())
