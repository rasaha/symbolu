"""Canonical end-to-end trace dataset v1 (Phase 8). Deterministic, provider-neutral, no
credentials / customer data / secrets. Each Trace ties real component inputs together:
candidate model ids (from registry_v1), a ModelPolicy task, a real TAP-E4 case id, a real
ActionGate operation, and a replayed provider outcome — with the EXPECTED canonical disposition
grounded in the real engines' verified output (see anchors below).

Anchors (verified against the real engines):
  TAP-E4: ALLOW=E4D01, QUALIFY=E4D12, ESCALATE=E4D13, REJECT=E4D14
  ActionGate: ALLOW=KEY_ROTATE(+approval+evidence), CONSTRAIN=SECRET_READ(+approval),
              APPROVE=SECRET_READ(bare), INDETERMINATE=DEPLOY(bare), DENY(hard)=DB_DELETE

Includes traces deliberately built so the integrated architecture can lose (single-provider
overhead; equal-utility ties) and degradation traces (TAP/ActionGate/telemetry/audit down).
"""
from __future__ import annotations

import json
import os
from dataclasses import asdict, dataclass, field
from typing import Any, Dict, List, Optional

REG_IDS = ["m_coding_spec", "m_external_frontier", "m_long_multi",
           "m_medium_general", "m_small_local", "m_strong_reason"]
ALL_PROVIDERS = ["internal", "vendor_alpha", "vendor_beta", "vendor_delta", "vendor_gamma", "vendor_omega"]


def _task(tid: str, tclass: str = "reasoning", tokens: int = 8, thr: float = 0.6,
          hc: Optional[Dict] = None, priority: str = "balanced") -> Dict[str, Any]:
    weights = {"balanced": (1.0, 0.45, 0.35), "quality_first": (1.0, 0.15, 0.10),
               "cost_first": (0.7, 1.0, 0.25), "latency_first": (0.8, 0.25, 1.0)}[priority]
    caps = {"reasoning": {"reasoning": 1.0}, "extraction": {"extraction": 1.0, "summarization": 0.3},
            "tool_requiring": {"tool_use": 1.0, "reasoning": 0.4},
            "long_context_analysis": {"long_context": 1.0, "reasoning": 0.5}}[tclass]
    return {"task_id": tid, "task_class": tclass, "required_caps": caps, "input_tokens_k": tokens,
            "business_priority": priority,
            "utility_weights": dict(zip(("quality", "cost", "latency"), weights)),
            "acceptable_quality_threshold": thr, "hard_constraints": hc or {}}


def _env(tid: str, **kw) -> Dict[str, Any]:
    d = {"envelope_version": "1", "request_id": f"req_{tid}", "trace_id": tid, "task_risk_class":
         "informational", "data_sensitivity": "internal", "required_capabilities": [],
         "context_tokens": 1000, "provider_allowlist": None,
         "action_policy": {"permitted": ["notify"], "require_approval": ["payment"]},
         "policy_versions": {"assertion": "v1", "action": "v1", "enterprise": "v1"},
         "registry_version": "reg_v1", "mode": "SHADOW"}
    d.update(kw)
    return d


def _specs(ids: List[str], **overrides) -> List[Dict[str, Any]]:
    out = []
    for i, mid in enumerate(ids):
        s = {"provider": ALL_PROVIDERS[i % len(ALL_PROVIDERS)], "model_id": mid, "family": "f"}
        s.update(overrides.get(mid, {}))
        out.append(s)
    return out


@dataclass
class Trace:
    trace_id: str
    trace_class: str
    envelope: Dict[str, Any]
    candidate_specs: List[Dict[str, Any]]
    task: Dict[str, Any]
    provider_outcome: str = "SUCCESS"                 # SUCCESS | FAILURE | DISAPPEARED
    tap_case_id: Optional[str] = "E4D01"              # real TAP-E4 case (None => assertion skipped)
    action_op: Optional[str] = None                   # real ActionGate op (None => assertion-only)
    action_with_approval: bool = False
    action_with_evidence: bool = False
    # degradation switches
    tap_unavailable: bool = False
    actiongate_unavailable: bool = False
    telemetry_unavailable: bool = False
    audit_unavailable: bool = False
    # expectations (canonical)
    expected_selection: str = "SELECTED"              # SELECTED | ABSTAIN | NOT_ELIGIBLE
    expected_assertion: Optional[str] = None          # ALLOW/QUALIFY/REJECT/ESCALATE/INDETERMINATE
    expected_action: Optional[str] = None             # ALLOW/DENY/APPROVE/CONSTRAIN/ESCALATE/INDETERMINATE
    expected_terminal: str = "COMPLETED"
    expected_reason_namespaces: List[str] = field(default_factory=list)
    can_lose: bool = False
    component_tier_ceiling: str = "TIER1"             # min tier across boundaries touched
    note: str = ""


def all_traces() -> List[Trace]:
    T: List[Trace] = []
    full = REG_IDS

    # 1 assertion-only safe answer
    T.append(Trace("T01", "assertion_only_safe", _env("T01"), _specs(full), _task("T01"),
                   tap_case_id="E4D01", action_op=None, expected_assertion="ALLOW",
                   expected_terminal="ASSERTION_DELIVERED", expected_reason_namespaces=["EXEC", "MODEL"],
                   note="real EG+MP+TAP, no action"))
    # 2 assertion requires qualification
    T.append(Trace("T02", "assertion_qualified", _env("T02"), _specs(full), _task("T02"),
                   tap_case_id="E4D12", expected_assertion="QUALIFY",
                   expected_terminal="ASSERTION_DELIVERED", note="TAP GOVERNING_WITH_EXCEPTION"))
    # 3 unsupported assertion rejected
    T.append(Trace("T03", "assertion_rejected", _env("T03"), _specs(full), _task("T03"),
                   tap_case_id="E4D14", action_op="notify_action", expected_assertion="REJECT",
                   expected_terminal="ASSERTION_REJECTED", expected_reason_namespaces=["ASSERT"]))
    # 4 assertion escalated
    T.append(Trace("T04", "assertion_escalated", _env("T04"), _specs(full), _task("T04"),
                   tap_case_id="E4D13", expected_assertion="ESCALATE",
                   expected_terminal="ASSERTION_ESCALATED", expected_reason_namespaces=["ASSERT"]))
    # 5 no eligible model
    bad = _specs(full, **{m: {"signals": {"authenticated": False}} for m in full})
    T.append(Trace("T05", "no_eligible_model", _env("T05"), bad, _task("T05"),
                   expected_selection="ABSTAIN", expected_terminal="NO_ELIGIBLE_MODEL",
                   expected_reason_namespaces=["EXEC"]))
    # 6 preferred model ineligible, fallback selected
    T.append(Trace("T06", "preferred_ineligible_fallback", _env("T06"),
                   _specs(full, **{"m_coding_spec": {"signals": {"model_available": False}}}),
                   _task("T06", tclass="reasoning"), expected_selection="SELECTED",
                   expected_terminal="ASSERTION_DELIVERED", note="EG excludes one; MP picks from rest"))
    # 7 provider disappears after selection
    T.append(Trace("T07", "provider_disappears", _env("T07"), _specs(full), _task("T07"),
                   provider_outcome="DISAPPEARED", expected_terminal="PROVIDER_FAILED",
                   expected_reason_namespaces=["RUNTIME"], component_tier_ceiling="TIER2"))
    # 8 fallback succeeds (provider fails, re-enter, next succeeds)
    T.append(Trace("T08", "fallback_succeeds", _env("T08"), _specs(full), _task("T08"),
                   provider_outcome="FAILURE", expected_terminal="COMPLETED",
                   tap_case_id="E4D01", action_op=None, note="fallback re-enters eligibility",
                   component_tier_ceiling="TIER2"))
    # 9 fallback also fails
    T.append(Trace("T09", "fallback_also_fails", _env("T09"), _specs(full[:1]), _task("T09"),
                   provider_outcome="FAILURE", expected_terminal="PROVIDER_FAILED",
                   expected_reason_namespaces=["RUNTIME"], component_tier_ceiling="TIER2",
                   note="single candidate, no fallback available"))
    # 10 successful assertion with no action
    T.append(Trace("T10", "assertion_no_action", _env("T10"), _specs(full), _task("T10"),
                   tap_case_id="E4D01", action_op=None, expected_assertion="ALLOW",
                   expected_terminal="ASSERTION_DELIVERED"))
    # 11 assertion accepted, action denied
    T.append(Trace("T11", "assertion_ok_action_denied", _env("T11"), _specs(full), _task("T11"),
                   tap_case_id="E4D01", action_op="DB_DELETE", expected_assertion="ALLOW",
                   expected_action="DENY", expected_terminal="ACTION_DENIED",
                   expected_reason_namespaces=["ACTION"], note="hard safety block"))
    # 12 assertion accepted, action constrained
    T.append(Trace("T12", "assertion_ok_action_constrained", _env("T12"), _specs(full), _task("T12"),
                   tap_case_id="E4D01", action_op="SECRET_READ", action_with_approval=True,
                   expected_assertion="ALLOW", expected_action="CONSTRAIN",
                   expected_terminal="ACTION_CONSTRAINED", expected_reason_namespaces=["ACTION"]))
    # 13 assertion accepted, approval required
    T.append(Trace("T13", "assertion_ok_approval_required", _env("T13"), _specs(full), _task("T13"),
                   tap_case_id="E4D01", action_op="SECRET_READ", expected_assertion="ALLOW",
                   expected_action="APPROVE", expected_terminal="ACTION_APPROVAL_REQUIRED",
                   expected_reason_namespaces=["ACTION"]))
    # 14 action approved but execution suppressed in shadow mode
    T.append(Trace("T14", "action_allowed_suppressed_shadow", _env("T14"), _specs(full), _task("T14"),
                   tap_case_id="E4D01", action_op="KEY_ROTATE", action_with_approval=True,
                   action_with_evidence=True, expected_assertion="ALLOW", expected_action="ALLOW",
                   expected_terminal="COMPLETED_SUPPRESSED",
                   note="ALLOW but ActionRuntime simulates only (shadow)"))
    # 15 policy-prohibited provider that technically works (residency)
    T.append(Trace("T15", "residency_prohibited", _env("T15", residency_requirements="eu"),
                   _specs(full, **{m: {"region": "us"} for m in full}), _task("T15"),
                   expected_selection="ABSTAIN", expected_terminal="NO_ELIGIBLE_MODEL",
                   expected_reason_namespaces=["EXEC"]))
    # 16 stale registry (registry version mismatch)
    T.append(Trace("T16", "stale_registry", _env("T16", registry_version="reg_v0"), _specs(full),
                   _task("T16"), expected_terminal="REJECTED",
                   expected_reason_namespaces=["POLICY"], note="registry version mismatch"))
    # 17 stale policy version
    T.append(Trace("T17", "stale_policy_version",
                   _env("T17", policy_versions={"assertion": "v0", "action": "v1", "enterprise": "v1"}),
                   _specs(full), _task("T17"), expected_terminal="REJECTED",
                   expected_reason_namespaces=["POLICY"]))
    # 18 TAP unavailable
    T.append(Trace("T18", "tap_unavailable", _env("T18"), _specs(full), _task("T18"),
                   tap_unavailable=True, action_op="notify", expected_terminal="GOVERNANCE_UNAVAILABLE",
                   expected_reason_namespaces=["RUNTIME"]))
    # 19 ActionGate unavailable
    T.append(Trace("T19", "actiongate_unavailable", _env("T19"), _specs(full), _task("T19"),
                   tap_case_id="E4D01", actiongate_unavailable=True, action_op="notify",
                   expected_terminal="GOVERNANCE_UNAVAILABLE", expected_reason_namespaces=["RUNTIME"]))
    # 20 telemetry unavailable (non-fatal)
    T.append(Trace("T20", "telemetry_unavailable", _env("T20"), _specs(full), _task("T20"),
                   tap_case_id="E4D01", telemetry_unavailable=True, expected_assertion="ALLOW",
                   expected_terminal="ASSERTION_DELIVERED", note="telemetry down degrades, not blocks"))
    # 21 audit write failure (fatal for enforcement; here recorded)
    T.append(Trace("T21", "audit_write_failure", _env("T21"), _specs(full), _task("T21"),
                   tap_case_id="E4D01", audit_unavailable=True, expected_terminal="AUDIT_FAILURE",
                   expected_reason_namespaces=["AUDIT"]))
    # 22 unauthorized override
    T.append(Trace("T22", "unauthorized_override", _env("T22"), _specs(full), _task("T22"),
                   tap_case_id="E4D01", action_op="SECRET_READ",
                   expected_assertion="ALLOW", expected_action="APPROVE",
                   expected_terminal="ACTION_APPROVAL_REQUIRED",
                   note="override attempted without rationale handled by orchestrator"))
    # 23 human override with valid authority
    T.append(Trace("T23", "human_override_valid", _env("T23"), _specs(full), _task("T23"),
                   tap_case_id="E4D01", action_op="SECRET_READ",
                   expected_assertion="ALLOW", expected_action="APPROVE",
                   expected_terminal="ACTION_APPROVAL_REQUIRED", note="valid override at orchestrator"))
    # 24 data-flow not approved
    T.append(Trace("T24", "data_flow_not_approved",
                   _env("T24", data_sensitivity="regulated", provider_allowlist=None), _specs(full),
                   _task("T24"), expected_terminal="REJECTED", expected_reason_namespaces=["POLICY"]))
    # 25 version incompatibility (envelope)
    T.append(Trace("T25", "version_incompatible", _env("T25", envelope_version="99"), _specs(full),
                   _task("T25"), expected_terminal="REJECTED", expected_reason_namespaces=["POLICY"]))
    # 26 stable single-provider trace (architecture can lose)
    T.append(Trace("T26", "single_provider_overhead", _env("T26"), _specs(full[:1]), _task("T26"),
                   tap_case_id="E4D01", action_op=None, expected_assertion="ALLOW",
                   expected_terminal="ASSERTION_DELIVERED", can_lose=True,
                   note="one provider, no action: overhead may exceed benefit"))
    # 27 equal-utility model tie
    tie = _specs(full[:2], **{full[0]: {}, full[1]: {}})
    T.append(Trace("T27", "equal_utility_tie", _env("T27"), tie, _task("T27"),
                   tap_case_id="E4D01", expected_terminal="ASSERTION_DELIVERED",
                   note="deterministic tie-break by model id"))
    # 28 tool-use capability mismatch
    T.append(Trace("T28", "capability_mismatch", _env("T28", required_capabilities=["tool_use"]),
                   _specs(full), _task("T28", tclass="tool_requiring"),
                   expected_selection="ABSTAIN", expected_terminal="NO_ELIGIBLE_MODEL",
                   expected_reason_namespaces=["EXEC"], note="no candidate supports tool_use"))
    # 29 high-risk action workflow (irreversible, denied)
    T.append(Trace("T29", "high_risk_action", _env("T29", task_risk_class="irreversible",
                                                    provider_allowlist=ALL_PROVIDERS),
                   _specs(full), _task("T29"), tap_case_id="E4D01", action_op="EXTERNAL_COMMS",
                   expected_assertion="ALLOW", expected_action="DENY",
                   expected_terminal="ACTION_DENIED", expected_reason_namespaces=["ACTION"],
                   note="irreversible external comms hard-blocked"))
    # 30 low-risk informational workflow
    T.append(Trace("T30", "low_risk_informational", _env("T30", task_risk_class="informational"),
                   _specs(full), _task("T30", tclass="extraction"), tap_case_id="E4D01",
                   action_op=None, expected_assertion="ALLOW",
                   expected_terminal="ASSERTION_DELIVERED"))
    return T


def dump_json(path: str) -> int:
    traces = all_traces()
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as fh:
        json.dump([asdict(t) for t in traces], fh, indent=2, sort_keys=True)
    return len(traces)


def count() -> int:
    return len(all_traces())


if __name__ == "__main__":
    here = os.path.dirname(os.path.abspath(__file__))
    n = dump_json(os.path.join(here, "traces.json"))
    print(f"wrote {n} traces")
