"""Shadow orchestrator (Phase 12). Drives a Trace through the REAL adapters (replay where real
execution is unavailable), preserves the authoritative route separately, produces a shadow
recommendation, NEVER executes a real action, NEVER hard-blocks the authoritative path, records
disagreements and unverified (NOT_ATTEMPTED) branches, validates contract versions, enforces
integration invariants, maintains trace context, writes append-only audit, and supports
deterministic replay.

Decision order (the hypothesis under test): normalize+policy -> ExecutionGate -> ModelPolicy ->
Provider(replay) -> TAP(assertion) -> ActionGate -> ActionRuntime(sim) -> Telemetry. ActionGate
receives the GOVERNED assertion output + provenance (preregistered rule), never raw output.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from control_plane_shadow.adapters.action_gate_adapter import ActionGateAdapter
from control_plane_shadow.adapters.action_runtime_adapter import ActionRuntimeAdapter
from control_plane_shadow.adapters.audit_adapter import AuditAdapter
from control_plane_shadow.adapters.execution_gate_adapter import ExecutionGateAdapter
from control_plane_shadow.adapters.model_policy_adapter import ModelPolicyAdapter
from control_plane_shadow.adapters.provider_runtime_adapter import ProviderRuntimeAdapter
from control_plane_shadow.adapters.tap_adapter import TAPAssertionAdapter
from control_plane_shadow.adapters.telemetry_adapter import TelemetryAdapter
from control_plane_shadow.traces.v1.dataset import Trace

CP_VERSION = "shadow_cp_v1"
_ACTION_OP_SET = ActionGateAdapter.OPS


@dataclass
class ShadowTraceResult:
    trace_id: str
    shadow_outcome: str = "INIT"
    authoritative_outcome: Optional[str] = None
    agree: bool = True
    reason_codes: List[str] = field(default_factory=list)
    selected: Optional[str] = None
    assertion_disposition: Optional[str] = None
    action_disposition: Optional[str] = None
    unsafe_transitions: List[str] = field(default_factory=list)
    disagreements: List[str] = field(default_factory=list)
    unverified_branches: List[str] = field(default_factory=list)   # NOT_ATTEMPTED (not success/failure)
    information_loss: List[str] = field(default_factory=list)
    component_calls: int = 0
    records: int = 0
    audit_ok: bool = True
    trace_complete: bool = True
    real_action_executed: bool = False              # must always stay False
    tier_ceiling: str = "TIER3"


class ShadowOrchestrator:
    def __init__(self, *, validate_contracts: bool = True, enforce_invariants: bool = True):
        self.validate_contracts = validate_contracts
        self.enforce_invariants = enforce_invariants
        self.eg = ExecutionGateAdapter()
        self.mp = ModelPolicyAdapter()
        self.px = ProviderRuntimeAdapter()
        self.tap = TAPAssertionAdapter()
        self.ag = ActionGateAdapter()
        self.ax = ActionRuntimeAdapter()

    def _mk_adapters(self, tr: Trace):
        tel = TelemetryAdapter(available=not tr.telemetry_unavailable)
        audit = AuditAdapter(available=not tr.audit_unavailable)
        return tel, audit

    def _rec(self, res, audit, tr, component, dtype, out, reasons=None):
        res.records += 1
        ok = audit.record(request_id=tr.envelope["request_id"], trace_id=tr.trace_id,
                          component=component, component_version=CP_VERSION, decision_type=dtype,
                          output_state=out, reason_codes=reasons or [],
                          policy_version=tr.envelope["policy_versions"].get("enterprise", ""),
                          registry_version=tr.envelope["registry_version"])
        return ok

    def _absorb(self, res, ar):
        res.component_calls += 1
        res.information_loss.extend(ar.information_loss)

    def _terminal(self, res, audit, tr, state, reasons):
        res.shadow_outcome = state
        res.reason_codes = list(reasons)
        self._rec(res, audit, tr, "Orchestrator", "terminal", state, reasons)
        res.audit_ok = audit.verify() if not tr.audit_unavailable else False
        tc = audit.trace_complete(tr.trace_id) if not tr.audit_unavailable else "TRACE_INCOMPLETE"
        res.trace_complete = tc is None
        res.authoritative_outcome = tr.expected_terminal
        res.agree = (res.shadow_outcome == tr.expected_terminal)
        if not res.agree:
            res.disagreements.append(f"expected {tr.expected_terminal}, got {res.shadow_outcome}")
        return res

    def run(self, tr: Trace) -> ShadowTraceResult:
        res = ShadowTraceResult(trace_id=tr.trace_id, tier_ceiling=tr.component_tier_ceiling)
        tel, audit = self._mk_adapters(tr)
        env = tr.envelope

        # layer 1: version/compat + data-flow gate (fail-closed)
        if self.validate_contracts:
            if env.get("envelope_version") != "1":
                return self._terminal(res, audit, tr, "REJECTED", ["POLICY.CONTRACT_VERSION_UNSUPPORTED"])
            if env.get("registry_version") != "reg_v1":
                return self._terminal(res, audit, tr, "REJECTED", ["POLICY.REGISTRY_VERSION_MISMATCH"])
            if env.get("policy_versions", {}).get("assertion") != "v1":
                return self._terminal(res, audit, tr, "REJECTED", ["POLICY.POLICY_VERSION_MISMATCH"])
        sensitive = env.get("data_sensitivity") in ("confidential", "regulated")
        if sensitive and not env.get("provider_allowlist"):
            return self._terminal(res, audit, tr, "REJECTED", ["POLICY.DATA_FLOW_NOT_APPROVED"])

        # ExecutionGate (real)
        eg_res, eligible = self.eg.evaluate(tr.candidate_specs, env, now=1_000_000.0)
        self._absorb(res, eg_res)
        self._rec(res, audit, tr, "ExecutionGate", "eligibility", eg_res.canonical["state"], eg_res.reason_codes)
        if not eligible:
            return self._terminal(res, audit, tr, "NO_ELIGIBLE_MODEL", ["EXEC.NO_ELIGIBLE_MODEL"])
        eligible_ids = [s["model_id"] for s, _ in eligible]

        # ModelPolicy (real), constrained to eligible set
        mp_res = self.mp.select(tr.task, eligible_ids, eg_res.canonical["eligibility_decision_id"])
        self._absorb(res, mp_res)
        self._rec(res, audit, tr, "ModelPolicy", "selection", mp_res.canonical["state"], mp_res.reason_codes)
        if mp_res.canonical["state"] == "SELECTED_NOT_ELIGIBLE":
            res.unsafe_transitions.append("MODEL.SELECTED_MODEL_NOT_ELIGIBLE")
            return self._terminal(res, audit, tr, "INVALID_SELECTION", ["MODEL.SELECTED_MODEL_NOT_ELIGIBLE"])
        if mp_res.canonical["state"] != "SELECTED":
            return self._terminal(res, audit, tr, "NO_ELIGIBLE_MODEL", ["MODEL.NO_SELECTION"])
        selected = mp_res.canonical["selected_candidate"]
        res.selected = selected
        # invariant: selection within eligible set
        if selected not in eligible_ids:
            res.unsafe_transitions.append("selection_outside_eligible")

        # Provider (replay) with fallback re-entry on failure
        px = self.px.call(selected, outcome=tr.provider_outcome)
        self._absorb(res, px)
        self._rec(res, audit, tr, "ProviderAdapter", "execution", px.canonical["state"], px.reason_codes)
        if px.canonical["state"] == "PROVIDER_EXECUTION_FAILED":
            remaining = [i for i in eligible_ids if i != selected]
            if remaining:                                   # fallback re-enters eligibility+policy (invariant 19)
                mp2 = self.mp.select(tr.task, remaining, eg_res.canonical["eligibility_decision_id"])
                self._absorb(res, mp2)
                self._rec(res, audit, tr, "ModelPolicy", "selection(fallback)", mp2.canonical["state"], mp2.reason_codes)
                if mp2.canonical["state"] == "SELECTED":
                    selected = mp2.canonical["selected_candidate"]; res.selected = selected
                    px = self.px.call(selected, outcome="SUCCESS")
                    self._absorb(res, px)
                    self._rec(res, audit, tr, "ProviderAdapter", "execution(fallback)", px.canonical["state"], [])
                else:
                    return self._terminal(res, audit, tr, "PROVIDER_FAILED", ["RUNTIME.PROVIDER_EXECUTION_FAILED"])
            else:
                return self._terminal(res, audit, tr, "PROVIDER_FAILED", ["RUNTIME.PROVIDER_EXECUTION_FAILED"])

        # TAP availability -> fail-closed governance
        if tr.tap_unavailable:
            return self._terminal(res, audit, tr, "GOVERNANCE_UNAVAILABLE", ["RUNTIME.GOVERNANCE_COMPONENT_UNAVAILABLE"])

        # TAP assertion governance (real E4)
        if tr.tap_case_id:
            tap_res = self.tap.govern(tr.tap_case_id)
            self._absorb(res, tap_res)
            disp = tap_res.canonical["assertion_disposition"]
            res.assertion_disposition = disp
            self._rec(res, audit, tr, "TAP", "assertion", disp, tap_res.reason_codes)
            if disp in ("REJECT", "ESCALATE"):
                state = "ASSERTION_REJECTED" if disp == "REJECT" else "ASSERTION_ESCALATED"
                return self._terminal(res, audit, tr, state, tap_res.reason_codes)
            # QUALIFY / INDETERMINATE / ALLOW proceed (INDETERMINATE => fail-closed if action requested)

        # assertion-only path
        if tr.action_op is None or tr.action_op not in _ACTION_OP_SET:
            # telemetry (prospective) then deliver assertion
            t = tel.observe(tr.trace_id, selected, "ok", 1_000_000.0)
            self._absorb(res, t)
            self._rec(res, audit, tr, "Telemetry", "telemetry", t.canonical["state"], t.reason_codes)
            if tr.audit_unavailable:
                return self._terminal(res, audit, tr, "AUDIT_FAILURE", ["AUDIT.TELEMETRY_WRITE_FAILED"])
            return self._terminal(res, audit, tr, "ASSERTION_DELIVERED", [])

        # ActionGate availability -> fail-closed for action-producing requests
        if tr.actiongate_unavailable:
            return self._terminal(res, audit, tr, "GOVERNANCE_UNAVAILABLE", ["RUNTIME.GOVERNANCE_COMPONENT_UNAVAILABLE"])

        # ActionGate (real) — receives governed assertion output + provenance (preregistered)
        ag_res = self.ag.authorize(tr.action_op, with_approval=tr.action_with_approval,
                                   with_evidence=tr.action_with_evidence)
        self._absorb(res, ag_res)
        adisp = ag_res.canonical["action_disposition"]
        res.action_disposition = adisp
        self._rec(res, audit, tr, "ActionGate", "action", adisp, ag_res.reason_codes)
        if adisp != "ALLOW":
            # denied/approve/constrain/escalate/indeterminate => terminal-before-execution (invariant 7)
            state = {"DENY": "ACTION_DENIED", "APPROVE": "ACTION_APPROVAL_REQUIRED",
                     "CONSTRAIN": "ACTION_CONSTRAINED", "ESCALATE": "ACTION_ESCALATED",
                     "INDETERMINATE": "ACTION_INDETERMINATE"}.get(adisp, "ACTION_TERMINAL")
            return self._terminal(res, audit, tr, state, ag_res.reason_codes)

        # ActionRuntime — SIMULATE ONLY (never executes; shadow suppresses)
        ax = self.ax.execute(tr.action_op, mode=env.get("mode", "SHADOW"))
        self._absorb(res, ax)
        res.real_action_executed = ax.canonical["executed"]   # always False
        res.unverified_branches.append(f"action_execution:{tr.action_op}:NOT_ATTEMPTED")
        self._rec(res, audit, tr, "ActionRuntime", "action_execution", ax.canonical["state"], [])
        if res.real_action_executed:                          # can never happen; hard guard
            res.unsafe_transitions.append("REAL_ACTION_EXECUTED")

        t = tel.observe(tr.trace_id, selected, "ok", 1_000_000.0)
        self._absorb(res, t)
        self._rec(res, audit, tr, "Telemetry", "telemetry", t.canonical["state"], t.reason_codes)
        return self._terminal(res, audit, tr, "COMPLETED_SUPPRESSED", [])
