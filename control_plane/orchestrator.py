"""Reference orchestrator (Phase 10). Coordinates components in order, validates contract
versions, preserves trace context, enforces invariants, stops invalid transitions, writes
audit records, and normalizes terminal outcomes. It holds NO decision authority: it never
decides eligibility, selection, assertion, or action itself — it only routes, guards, and
records.

Parameterized for the Phase-15 evaluation:
  validate_contracts / enforce_invariants  →
    (False, False) = disconnected glue        (config 1)
    (True,  False) = orchestrator, no invariants (config 2)
    (True,  True)  = unified control plane     (config 3)

When enforce_invariants is False, a detected violation is RECORDED but the transition is
allowed to proceed (so the evaluation can measure what leaks through). When True, the
violation is terminal and fail-closed.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from control_plane import contracts as K
from control_plane.adapters import (ExecutionGateAdapter, MockActionAdapter, MockActionGateAdapter,
                                    MockAssertionAdapter, MockProviderAdapter, ModelPolicyAdapter,
                                    MockTelemetryAdapter)
from control_plane.audit import Audit
from control_plane.failure_codes import Failure
from control_plane.modes import caps
from control_plane.policy_context import PolicyContext
from control_plane.telemetry import Telemetry

CP_VERSION = "cp_v1"


@dataclass
class Scenario:
    """A deterministic, provider-neutral scenario input (Phase 9)."""
    name: str
    envelope: Any
    candidate_specs: List[Dict[str, Any]] = field(default_factory=list)
    provider_fail: bool = False
    provider_fail_then_ok: bool = False        # first attempt fails, fallback succeeds
    raw_provider_error: Optional[str] = None
    assertion: str = "APPROVE"                 # APPROVE|QUALIFY|CONSTRAIN|ESCALATE|REJECT
    proposed_action: Optional[str] = None
    forced_action_disposition: Optional[str] = None
    override_actor: Optional[str] = None
    override_rationale: Optional[str] = None
    corrupt_audit: bool = False
    tap_unavailable: bool = False
    actiongate_unavailable: bool = False
    now: float = 1_000_000.0


@dataclass
class TraceResult:
    trace_id: str
    terminal_state: str
    terminal_reasons: List[str] = field(default_factory=list)
    violations: List[str] = field(default_factory=list)     # invariant violations DETECTED
    blocked: List[str] = field(default_factory=list)        # violations that were BLOCKED (enforced)
    component_calls: int = 0
    records: int = 0
    audit_ok: bool = True
    trace_complete: bool = True
    selected: Optional[str] = None
    executed_action: bool = False


class Orchestrator:
    def __init__(self, *, validate_contracts: bool = True, enforce_invariants: bool = True,
                 audit_path: Optional[str] = None):
        self.validate_contracts = validate_contracts
        self.enforce_invariants = enforce_invariants
        self.eg = ExecutionGateAdapter()
        self.mp = ModelPolicyAdapter()
        self.px = MockProviderAdapter()
        self.tap = MockAssertionAdapter()
        self.ag = MockActionGateAdapter()
        self.ax = MockActionAdapter()
        self.tel = MockTelemetryAdapter()
        self.telemetry = Telemetry()
        self.audit = Audit(audit_path)

    # -- invariant helper: returns True if the trace should STOP here --------
    def _violate(self, res: TraceResult, code: Failure) -> bool:
        res.violations.append(code.value)
        if self.enforce_invariants:
            res.blocked.append(code.value)
            return True
        return False

    def _rec(self, res, env, ctx, component, dtype, out, reasons=None, **extra):
        res.records += 1
        self.audit.record(request_id=env.request_id, trace_id=env.trace_id, component=component,
                          component_version=CP_VERSION, decision_type=dtype, output_state=out,
                          reason_codes=reasons or [], policy_version=ctx.policy_versions.get("enterprise", ""),
                          registry_version=ctx.registry_version, **extra)

    def _terminal(self, res, env, ctx, state, reasons):
        res.terminal_state = state
        res.terminal_reasons = list(reasons)
        self._rec(res, env, ctx, "Orchestrator", "terminal", state, reasons)
        return self._finish(res, env, ctx)

    def _finish(self, res, env, ctx):
        # invariant 20: verify trace completeness + chain integrity
        res.audit_ok = self.audit.verify()
        tc = self.audit.trace_complete(env.trace_id)
        res.trace_complete = tc is None
        if tc is not None and tc.value not in res.terminal_reasons:
            res.violations.append(tc.value)
        return res

    def run(self, sc: Scenario) -> TraceResult:
        env, now = sc.envelope, sc.now
        res = TraceResult(trace_id=env.trace_id, terminal_state="INIT")
        ctx = PolicyContext.resolve(env)

        # layer 1: compatibility + data-flow gate (fail-closed)
        if not env.compatible():
            return self._terminal(res, env, ctx, "REJECTED", [Failure.CONTRACT_VERSION_UNSUPPORTED.value])
        dfg = ctx.data_flow_gate()
        if dfg is not None:
            return self._terminal(res, env, ctx, "REJECTED", [dfg.value])

        # ---- C1 normalizer -> ExecutionGate --------------------------------
        if self.validate_contracts:
            ok, errs = K.validate_payload("normalizer->execution_gate", {
                "envelope_version": env.envelope_version, "request_id": env.request_id,
                "trace_id": env.trace_id, "task_risk_class": env.task_risk_class,
                "required_capabilities": env.required_capabilities, "policy_versions": env.policy_versions,
                "registry_version": env.registry_version, "candidate_set": sc.candidate_specs,
                "mode": env.mode})
            if not ok:
                return self._terminal(res, env, ctx, "REJECTED", [Failure.CONTRACT_VERSION_UNSUPPORTED.value])

        # ---- ExecutionGate (real): what CAN execute ------------------------
        eg_res, eligible = self.eg.evaluate(sc.candidate_specs, env, now)
        res.component_calls += 1
        self._rec(res, env, ctx, "ExecutionGate", "eligibility", eg_res.output_state,
                  eg_res.reason_codes, evidence_refs=eg_res.evidence_refs)
        eligibility_decision_id = f"{env.trace_id}:eg"
        if not eligible:
            return self._terminal(res, env, ctx, "NO_ELIGIBLE_MODEL", [Failure.NO_ELIGIBLE_MODEL.value])
        eligible_ids = {s["model_id"] for s, _ in eligible}

        # ---- ModelPolicy (real): what SHOULD execute -----------------------
        sel = self.mp.select(eligible, env, now, eligibility_decision_id)
        res.component_calls += 1
        self._rec(res, env, ctx, "ModelPolicy", "selection", sel.output_state, sel.reason_codes,
                  selected_candidate=sel.payload.get("selected_candidate"),
                  projected_cost_usd=sel.projected_cost_usd)
        if sel.output_state != "SELECTED":
            return self._terminal(res, env, ctx, "NO_SELECTION", sel.reason_codes or [Failure.NO_ELIGIBLE_MODEL.value])
        selected = sel.payload["selected_candidate"]
        res.selected = selected
        # invariant 1: selection within eligible set
        if selected not in eligible_ids:
            if self._violate(res, Failure.SELECTED_MODEL_NOT_ELIGIBLE):
                return self._terminal(res, env, ctx, "INVALID_SELECTION",
                                      [Failure.SELECTED_MODEL_NOT_ELIGIBLE.value])

        # ---- Provider execution (mock) with fallback re-entry (invariant 19)
        attempt_fail = sc.provider_fail or sc.provider_fail_then_ok
        px = self.px.call(selected, env, now, fail=attempt_fail, raw_error=sc.raw_provider_error)
        res.component_calls += 1
        # invariant 3: executed == selected (no silent substitution)
        if px.payload.get("executed_candidate") != selected:
            if self._violate(res, Failure.UPSTREAM_EXCLUSION_BYPASSED):
                return self._terminal(res, env, ctx, "BYPASS", [Failure.UPSTREAM_EXCLUSION_BYPASSED.value])
        self._rec(res, env, ctx, "ProviderAdapter", "execution", px.output_state, px.reason_codes,
                  evidence_refs=px.evidence_refs, execution_outcome=px.output_state)
        if px.output_state == "PROVIDER_EXECUTION_FAILED":
            # fallback MUST re-enter eligibility+policy (invariant 19), excluding the failed candidate
            remaining = [(s, d) for s, d in eligible if s["model_id"] != selected]
            if sc.provider_fail_then_ok and remaining:
                if self.enforce_invariants:
                    # re-enter: re-select from remaining eligible, then succeed
                    sel2 = self.mp.select(remaining, env, now, eligibility_decision_id)
                    res.component_calls += 1
                    self._rec(res, env, ctx, "ModelPolicy", "selection(fallback)", sel2.output_state,
                              sel2.reason_codes, selected_candidate=sel2.payload.get("selected_candidate"))
                    selected = sel2.payload.get("selected_candidate", selected)
                    res.selected = selected
                    px = self.px.call(selected, env, now, fail=False)
                    res.component_calls += 1
                    self._rec(res, env, ctx, "ProviderAdapter", "execution(fallback)", px.output_state,
                              px.reason_codes, execution_outcome=px.output_state)
                else:
                    # glue path: silent in-place retry of SAME candidate = bypass (invariant 19)
                    self._violate(res, Failure.UPSTREAM_EXCLUSION_BYPASSED)
                    px = self.px.call(selected, env, now, fail=False)
                    res.component_calls += 1
            else:
                return self._terminal(res, env, ctx, "PROVIDER_FAILED", [Failure.PROVIDER_EXECUTION_FAILED.value])

        # ---- governance-component availability: degrade to fail-closed refusal,
        #      never silent allow (Phase 16 safe-degradation) --------------------
        if sc.tap_unavailable:
            return self._terminal(res, env, ctx, "GOVERNANCE_UNAVAILABLE",
                                  [Failure.GOVERNANCE_COMPONENT_UNAVAILABLE.value])

        # ---- TAP / assertion governance (mock): what may be ASSERTED -------
        tap = self.tap.govern(px.payload["model_output_ref"], env, now, sc.assertion)
        res.component_calls += 1
        self._rec(res, env, ctx, "TAP", "assertion", tap.output_state, tap.reason_codes,
                  assertion_disposition=tap.output_state, evidence_refs=tap.evidence_refs)
        if tap.output_state in ("REJECT", "ESCALATE"):
            state = "ASSERTION_REJECTED" if tap.output_state == "REJECT" else "ASSERTION_ESCALATED"
            return self._terminal(res, env, ctx, state, tap.reason_codes)

        # ---- assertion-only path: no proposed action ----------------------
        if sc.proposed_action is None:
            return self._terminal(res, env, ctx, "ASSERTION_DELIVERED", [])

        if sc.actiongate_unavailable:
            return self._terminal(res, env, ctx, "GOVERNANCE_UNAVAILABLE",
                                  [Failure.GOVERNANCE_COMPONENT_UNAVAILABLE.value])

        # ---- Action governance (mock): what may be DONE (invariants 5,6) ---
        authority = ctx.authority_envelope()
        ag = self.ag.authorize(sc.proposed_action, authority, env, now, forced=sc.forced_action_disposition)
        res.component_calls += 1
        override_fields = {}
        if sc.override_actor:
            override_fields = {"override_status": "applied", "override_actor": sc.override_actor,
                               "override_rationale": sc.override_rationale}
            # invariant 8: override must be attributable AND have a rationale
            if not sc.override_rationale:
                if self._violate(res, Failure.UNAUTHORIZED_OVERRIDE):
                    return self._terminal(res, env, ctx, "UNAUTHORIZED_OVERRIDE",
                                          [Failure.UNAUTHORIZED_OVERRIDE.value])
        self._rec(res, env, ctx, "ActionGate", "action", ag.output_state, ag.reason_codes,
                  action_disposition=ag.output_state, evidence_refs=ag.evidence_refs, **override_fields)

        allow = ag.output_state == "ALLOW" or (sc.override_actor and sc.override_rationale
                                               and ag.output_state == "APPROVE_REQUIRED")
        # invariant 7: denied/escalated/approval-required cannot reach the adapter
        if not allow:
            state = {"DENY": "ACTION_DENIED", "APPROVE_REQUIRED": "ACTION_APPROVAL_REQUIRED",
                     "ESCALATE": "ACTION_ESCALATED", "INDETERMINATE": "ACTION_INDETERMINATE",
                     "CONSTRAIN": "ACTION_CONSTRAINED"}.get(ag.output_state, "ACTION_TERMINAL")
            return self._terminal(res, env, ctx, state, ag.reason_codes)

        # ---- Action execution (mock; real only in ENFORCEMENT) ------------
        ax = self.ax.execute(sc.proposed_action, env.mode, now)
        res.component_calls += 1
        res.executed_action = ax.payload.get("executed", False)
        self._rec(res, env, ctx, "ActionAdapter", "action_execution", ax.output_state, [],
                  execution_outcome=ax.output_state)

        # ---- Telemetry (prospective; invariants 11,12) --------------------
        obs = self.telemetry.record_outcome(env.trace_id, selected, "ok", now)
        circ = self.telemetry.feed_forward(obs)
        res.component_calls += 1
        self._rec(res, env, ctx, "Telemetry", "telemetry", "RECORDED",
                  [circ.value] if circ else [])

        return self._terminal(res, env, ctx, "COMPLETED", [])
