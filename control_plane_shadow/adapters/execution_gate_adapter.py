"""Real ExecutionGate adapter (Phase 5). Wraps execution_gate.gate.ExecutionGate (TIER 3).
Preserves the EligibilityDecision, emits canonical eligibility, normalizes reasons to EXEC.*.
Pure; no network; no mutation of the wrapped component.
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple

from execution_gate import gate as eg_gate
from execution_gate import model as eg_model
from execution_gate.states import Evidence, EvidenceSource, EligibilityState

from control_plane_shadow.adapters.base import AdapterHealth, ShadowAdapter
from control_plane_shadow.vocabulary import map_exec, provenance


def _sig(value, now, stale=False, ttl=900.0, hint=None):
    ts = now - 100000 if stale else now
    src = EvidenceSource.CACHE if stale else EvidenceSource.TELEMETRY
    return eg_model.Signal(value=value,
                           evidence=Evidence(source=src, timestamp=ts, confidence=0.99,
                                             ttl_seconds=ttl, raw_signal=None),
                           reason_hint=hint)


class ExecutionGateAdapter(ShadowAdapter):
    component = "ExecutionGate"
    source_version = "exec_gate_v1"

    def __init__(self, config: Optional[eg_model.GateConfig] = None):
        self.gate = eg_gate.ExecutionGate(config)

    def health(self) -> AdapterHealth:
        return AdapterHealth(self.component, available=True, determinism="deterministic",
                             live_call_risk=False, real_action_risk=False,
                             source_version=self.source_version, adapter_version=self.adapter_version,
                             capabilities=["eligibility", "evidence_ttl", "fail_closed"])

    def _candidate(self, spec: Dict[str, Any], now: float) -> eg_model.Candidate:
        defaults = {"reachable": True, "network_allowed": True, "authenticated": True,
                    "credential_expiry_ts": now + 1e9, "billing_active": True, "quota_state": "ok",
                    "model_available": True, "region_allowed": True, "feature_supported": True,
                    "reliability": 0.99}
        raw = dict(defaults); raw.update(spec.get("signals", {}))
        sigs = {k: _sig(v, now, stale=spec.get("stale", {}).get(k, False),
                        hint=spec.get("hints", {}).get(k)) for k, v in raw.items()}
        return eg_model.Candidate(
            provider=spec["provider"], model_id=spec["model_id"], family=spec.get("family", "?"),
            region=spec.get("region", "global"), context_limit=spec.get("context_limit", 8000),
            structured_output=spec.get("structured_output", False), tool_use=spec.get("tool_use", False),
            price_in_per_mtok=spec.get("price_in", 0.0), price_out_per_mtok=spec.get("price_out", 0.0),
            signals=sigs)

    def evaluate(self, candidate_specs: List[Dict[str, Any]], envelope, now: float
                 ) -> Tuple[Any, List[Tuple[Dict, Any]]]:
        req = eg_model.Request(
            request_id=envelope["request_id"], context_tokens=envelope.get("context_tokens", 1000),
            features_required=set(envelope.get("required_capabilities", [])),
            approved_providers=set(envelope["provider_allowlist"]) if envelope.get("provider_allowlist") else None,
            residency_required=envelope.get("residency_requirements"),
            latency_limit_ms=envelope.get("latency_budget_ms"), cost_cap_usd=envelope.get("cost_budget_usd"))
        decisions, eligible, prov, loss = [], [], [], []
        for spec in candidate_specs:
            dec = self.gate.evaluate(self._candidate(spec, now), req, now)   # REAL engine
            decisions.append(dec)
            canon = map_exec(dec.state.value)
            prov.append(provenance("ExecutionGate", dec.state.value, canon))
            if dec.selectable:
                eligible.append((spec, dec))
        # information loss: per-condition evidence detail is summarized to reason codes
        if decisions:
            loss.append("per-condition ConditionResult detail summarized to reason codes")
        state = "ELIGIBLE_SET_NONEMPTY" if eligible else "ELIGIBLE_SET_EMPTY"
        reasons: List[str] = []
        if not eligible:
            reasons.append("EXEC.NO_ELIGIBLE_MODEL")
            if any(d.state == EligibilityState.INDETERMINATE for d in decisions):
                reasons.append("EXEC.STALE_ELIGIBILITY_EVIDENCE")
        canonical = {
            "eligible_set": [s["model_id"] for s, _ in eligible],
            "eligibility_decision_id": f"{envelope['trace_id']}:eg",
            "eligibility_states": {d.model_id: d.state.value for d in decisions},
            "excluded_with_reasons": [{"model_id": d.model_id, "state": d.state.value,
                                       "reasons": [r.value for r in d.reasons]}
                                      for d in decisions if not d.selectable],
            "eligibility_evidence_timestamps": {d.model_id: d.evaluated_at for d in decisions},
            "policy_version": decisions[0].policy_version if decisions else "exec_gate_v1",
        }
        res = self._result(tier="TIER3", canonical=canonical, source_output=[d.to_dict() for d in decisions],
                           reason_codes=[f"EXEC.{r.value}" for d in decisions for r in d.reasons][:8] or reasons,
                           information_loss=loss, provenance=prov)
        # keep explicit terminal reason codes when empty
        if not eligible:
            res.reason_codes = reasons
        res.canonical["state"] = state
        return res, eligible
