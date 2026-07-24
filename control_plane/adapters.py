"""Component adapters (Phase 10). Adapters wrap existing packages; they do NOT merge or
modify them. ExecutionGate and ModelPolicy adapters call the REAL frozen packages
(`execution_gate.gate`, `execution_gate.policy`). Provider / Assertion (TAP) / ActionGate
/ ActionAdapter / Telemetry are deterministic, provider-neutral MOCKS — no live provider
calls, no real action execution (task constraint).

Each adapter returns an AdapterResult the orchestrator converts into a DecisionRecord.
An adapter never writes audit state or another component's state.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional, Tuple

from execution_gate import gate as eg_gate
from execution_gate import model as eg_model
from execution_gate import policy as eg_policy
from execution_gate import registry as eg_registry
from execution_gate import states as eg_states
from execution_gate.states import Evidence, EvidenceSource, EligibilityState

from control_plane.failure_codes import Failure


@dataclass
class AdapterResult:
    component: str
    output_state: str
    reason_codes: List[str] = field(default_factory=list)
    payload: Dict[str, Any] = field(default_factory=dict)
    evidence_refs: List[str] = field(default_factory=list)
    latency_ms: float = 0.0
    projected_cost_usd: float = 0.0
    observed_cost_usd: float = 0.0


# ---------------------------------------------------------------------------
# ExecutionGate adapter — REAL package. Answers "what CAN execute?"
# ---------------------------------------------------------------------------

def _mk_signal(value, now, source=EvidenceSource.TELEMETRY, ttl=900.0, hint=None):
    return eg_model.Signal(value=value,
                           evidence=Evidence(source=source, timestamp=now, confidence=0.99,
                                             ttl_seconds=ttl, raw_signal=None),
                           reason_hint=hint)


class ExecutionGateAdapter:
    """Wraps the real ExecutionGate. Input: candidate specs + envelope. Output: eligible set."""

    def __init__(self, config: Optional[eg_model.GateConfig] = None):
        self.gate = eg_gate.ExecutionGate(config)
        self.component = "ExecutionGate"

    def _candidate(self, spec: Dict[str, Any], now: float) -> eg_model.Candidate:
        sigs = {}
        defaults = {"reachable": True, "network_allowed": True, "authenticated": True,
                    "credential_expiry_ts": now + 1e9, "billing_active": True,
                    "quota_state": "ok", "model_available": True, "region_allowed": True,
                    "feature_supported": True, "reliability": 0.99}
        raw = dict(defaults)
        raw.update(spec.get("signals", {}))
        for k, v in raw.items():
            hint = spec.get("hints", {}).get(k)
            ttl = spec.get("ttl", {}).get(k, 900.0)
            src = EvidenceSource.CACHE if spec.get("stale", {}).get(k) else EvidenceSource.TELEMETRY
            ts = now - 100000 if spec.get("stale", {}).get(k) else now
            sigs[k] = _mk_signal(v, ts, source=src, ttl=ttl, hint=hint)
        return eg_model.Candidate(
            provider=spec["provider"], model_id=spec["model_id"], family=spec.get("family", "?"),
            developer=spec.get("developer", ""), region=spec.get("region", "global"),
            context_limit=spec.get("context_limit", 8000),
            structured_output=spec.get("structured_output", False),
            tool_use=spec.get("tool_use", False),
            price_in_per_mtok=spec.get("price_in", 0.0),
            price_out_per_mtok=spec.get("price_out", 0.0), signals=sigs)

    def _request(self, env, now) -> eg_model.Request:
        return eg_model.Request(
            request_id=env.request_id, context_tokens=env.context_tokens,
            features_required=set(env.required_capabilities),
            approved_providers=set(env.provider_allowlist) if env.provider_allowlist else None,
            residency_required=env.residency_requirements,
            latency_limit_ms=env.latency_budget_ms, cost_cap_usd=env.cost_budget_usd)

    def evaluate(self, candidate_specs: List[Dict[str, Any]], env, now: float
                 ) -> Tuple[AdapterResult, List[Tuple[Dict, Any]]]:
        req = self._request(env, now)
        eligible: List[Tuple[Dict, Any]] = []
        decisions = []
        for spec in candidate_specs:
            cand = self._candidate(spec, now)
            dec = self.gate.evaluate(cand, req, now)
            decisions.append(dec)
            if dec.selectable:
                eligible.append((spec, dec))
        state = "ELIGIBLE_SET_NONEMPTY" if eligible else "ELIGIBLE_SET_EMPTY"
        reasons = [] if eligible else [Failure.NO_ELIGIBLE_MODEL.value]
        # surface stale-evidence signal if any candidate went INDETERMINATE via stale evidence
        if not eligible and any(d.state == EligibilityState.INDETERMINATE for d in decisions):
            reasons.append(Failure.STALE_ELIGIBILITY_EVIDENCE.value)
        res = AdapterResult(self.component, state, reasons,
                            payload={"eligible": [s["model_id"] for s, _ in eligible],
                                     "excluded": [{"model_id": d.model_id, "state": d.state.value,
                                                   "reasons": [r.value for r in d.reasons]}
                                                  for d in decisions if not d.selectable]},
                            evidence_refs=[f"eligibility:{d.model_id}:{d.state.value}" for d in decisions])
        return res, eligible


# ---------------------------------------------------------------------------
# ModelPolicy adapter — REAL select(). Answers "what SHOULD execute?"
# ---------------------------------------------------------------------------

class ModelPolicyAdapter:
    def __init__(self, quality_of: Optional[Callable] = None):
        self.component = "ModelPolicy"
        self.quality_of = quality_of or (lambda rec: rec.candidate.__dict__.get("_quality", 0.7))

    def select(self, eligible: List[Tuple[Dict, Any]], env, now: float,
               eligibility_decision_id: str) -> AdapterResult:
        if not eligible:
            return AdapterResult(self.component, "NO_SELECTION",
                                 [Failure.NO_ELIGIBLE_MODEL.value])
        req = eg_model.Request(request_id=env.request_id, context_tokens=env.context_tokens,
                               est_output_tokens=200)
        selectable = []
        for spec, dec in eligible:
            cand = eg_model.Candidate(
                provider=spec["provider"], model_id=spec["model_id"], family=spec.get("family", "?"),
                price_in_per_mtok=spec.get("price_in", 0.0), price_out_per_mtok=spec.get("price_out", 0.0),
                structured_output=spec.get("structured_output", False),
                tool_use=spec.get("tool_use", False))
            cand.__dict__["_quality"] = spec.get("quality", 0.7)
            rec = eg_registry.ModelRecord(internal_id=spec["model_id"], candidate=cand,
                                          observed_latency_ms=spec.get("latency_ms", 1000.0))
            selectable.append((rec, dec))
        sel = eg_policy.select(selectable, req, self.quality_of)
        if sel.abstained or sel.selected is None:
            return AdapterResult(self.component, "NO_SELECTION", [Failure.NO_ELIGIBLE_MODEL.value])
        eligible_ids = {spec["model_id"] for spec, _ in eligible}
        chosen = sel.selected.internal_id
        # invariant 1 guard (should always hold since select() only sees selectable)
        if chosen not in eligible_ids:
            return AdapterResult(self.component, "NO_SELECTION",
                                 [Failure.SELECTED_MODEL_NOT_ELIGIBLE.value])
        cost = eg_policy._est_cost(sel.selected, req)
        return AdapterResult(self.component, "SELECTED", payload={
            "selected_candidate": chosen, "eligibility_decision_id": eligibility_decision_id,
            "ranked": [(r.internal_id, u) for r, u in sel.ranked],
            "selection_rationale": sel.reason}, projected_cost_usd=round(cost, 6))


# ---------------------------------------------------------------------------
# MOCK downstream adapters — deterministic, provider-neutral, no live effects.
# ---------------------------------------------------------------------------

class MockProviderAdapter:
    """Simulates provider execution. Normalizes any raw error to RUNTIME.* (invariant 14)."""
    component = "ProviderAdapter"

    def call(self, selected_candidate: str, env, now: float,
             fail: bool = False, raw_error: Optional[str] = None) -> AdapterResult:
        if fail:
            # raw provider error is read HERE and normalized; it never leaves this boundary
            return AdapterResult(self.component, "PROVIDER_EXECUTION_FAILED",
                                 [Failure.PROVIDER_EXECUTION_FAILED.value],
                                 payload={"executed_candidate": selected_candidate,
                                          "normalized_from_raw": bool(raw_error)},
                                 evidence_refs=[f"provider:{selected_candidate}:failed"])
        return AdapterResult(self.component, "OUTPUT_PRODUCED",
                             payload={"executed_candidate": selected_candidate,
                                      "model_output_ref": f"sha256:mock:{selected_candidate}"},
                             evidence_refs=[f"provider:{selected_candidate}:ok"],
                             observed_cost_usd=0.0)


class MockAssertionAdapter:
    """TAP / assertion governance mock. Answers 'what may be ASSERTED?' — independent of
    provider technical success (invariant 4)."""
    component = "TAP"

    def govern(self, output_ref: str, env, now: float,
               disposition: str = "APPROVE") -> AdapterResult:
        codes = {"REJECT": Failure.ASSERTION_REJECTED.value,
                 "CONSTRAIN": Failure.ASSERTION_CONSTRAINED.value,
                 "ESCALATE": Failure.ASSERTION_ESCALATED.value}
        reasons = [codes[disposition]] if disposition in codes else []
        return AdapterResult(self.component, disposition, reasons,
                             payload={"assertion_disposition": disposition,
                                      "governed_output_ref": f"governed:{output_ref}"},
                             evidence_refs=[f"assertion:{disposition}"])


class MockActionGateAdapter:
    """Action governance mock. Answers 'what may be DONE?' — independent of assertion
    approval (invariant 5); bounded by the request authority envelope (invariant 6)."""
    component = "ActionGate"

    def authorize(self, proposed_action: Optional[str], authority: Dict[str, Any],
                  env, now: float, forced: Optional[str] = None) -> AdapterResult:
        if proposed_action is None:
            return AdapterResult(self.component, "NO_ACTION")
        permitted = authority.get("permitted_actions", set())
        approval = authority.get("approval_required") or authority.get("require_approval") or set()
        if forced:                                   # scenario-forced disposition
            disp = forced
        elif proposed_action in approval:
            disp = "APPROVE_REQUIRED"
        elif proposed_action in permitted:
            disp = "ALLOW"
        else:
            disp = "DENY"                            # outside authority envelope (invariant 6)
        codes = {"DENY": Failure.ACTION_DENIED.value,
                 "APPROVE_REQUIRED": Failure.ACTION_APPROVAL_REQUIRED.value,
                 "CONSTRAIN": Failure.ACTION_CONSTRAINED.value,
                 "ESCALATE": Failure.ACTION_DENIED.value,
                 "INDETERMINATE": Failure.ACTION_DENIED.value}
        reasons = [codes[disp]] if disp in codes else []
        return AdapterResult(self.component, disp, reasons,
                             payload={"action_disposition": disp, "authorized_action":
                                      proposed_action if disp == "ALLOW" else None},
                             evidence_refs=[f"action:{proposed_action}:{disp}"])


class MockActionAdapter:
    """Executes an approved action — ONLY in ENFORCEMENT mode. Never in this environment."""
    component = "ActionAdapter"

    def execute(self, authorized_action: Optional[str], mode: str, now: float) -> AdapterResult:
        from control_plane.modes import may_execute_actions
        if not may_execute_actions(mode):
            # non-enforcing modes: simulate only, no real effect
            return AdapterResult(self.component, "SIMULATED",
                                 payload={"executed": False, "mode": mode,
                                          "would_execute": authorized_action})
        return AdapterResult(self.component, "EXECUTED",
                             payload={"executed": True, "action": authorized_action})


class MockTelemetryAdapter:
    """Observes outcomes; updates registry PROSPECTIVELY only (invariants 11,12)."""
    component = "Telemetry"

    def observe(self, trace_id: str, outcome: Dict[str, Any], now: float) -> AdapterResult:
        return AdapterResult(self.component, "RECORDED",
                             payload={"observation": outcome, "prospective": True})
