"""End-to-end orchestrator (Phase 13). Executes the stages in canonical order, preserves stage-local
outcomes, stops safely on fatal contract failures, continues diagnostically where safe, records every
stage event, emits one unified audit trace, supports deterministic replay, risk-tier configurations,
and component toggles for ablation. NEVER performs an external governed action.
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple

from . import contracts, dispositions, reason_codes, model_execution, evidence_binding, action_extraction
from .audit import AuditTrace, AuditEvent, artifact_hash
from .adapters import (execution_gate as a_exec, model_policy as a_model, claim_integrity as a_ci,
                       evidence_assurance as a_ea, assertion_gate as a_ag, action_gate as a_act)

# risk-tier configurations (Phase 14): which stages run
CONFIGS = {
    "FULL_STACK_HIGH_RISK": ["execution_gate", "model_policy", "claim_integrity", "scope_integrity",
                             "evidence_assurance", "assertion_gate", "action_gate"],
    "ASSERTION_GOVERNANCE": ["execution_gate", "model_policy", "claim_integrity",
                             "evidence_assurance", "assertion_gate"],
    "ACTION_GOVERNANCE": ["execution_gate", "model_policy", "claim_integrity", "action_gate"],
    "MINIMUM_VIABLE_CONTROL_PLANE": ["execution_gate", "model_policy", "assertion_gate"],
}
DEFAULT_CONFIG = "FULL_STACK_HIGH_RISK"


def _fail_closed(trace: AuditTrace, code: str, final: str, note: str = "") -> AuditTrace:
    trace.add(AuditEvent(trace_id=trace.trace_id, seq=0, stage="orchestrator",
                         component_version="gip_orch_v1", disposition="HALT", shadow_outcome=final,
                         reason_codes=[code], error=note))
    trace.finalize(final)
    return trace


def run_case(case: Dict[str, Any], config: str = DEFAULT_CONFIG,
             disabled: Optional[set] = None) -> AuditTrace:
    disabled = disabled or set()
    stages = [s for s in CONFIGS.get(config, CONFIGS[DEFAULT_CONFIG]) if s not in disabled]
    req = case["request"]
    trace = AuditTrace(trace_id=f"trace-{case['case_id']}", request_snapshot=req,
                       source_artifact_hashes={"model_output": artifact_hash(case["model_output"])},
                       component_versions={}, policy_versions={"gip": "gip_policy_v1"})
    risk = req.get("risk_tier", case.get("risk_tier", "medium"))
    stage_outcomes: List[Tuple[str, str]] = []

    # request -> ExecutionGate contract
    c = contracts.validate("request__execution_gate", req)
    if not c.ok:
        return _fail_closed(trace, "GIP.CONTRACT_ERROR", "CONTRACT_ERROR", ",".join(c.reason_codes))

    # injected contract/metadata fault (CONTRACT_OR_METADATA_FAILURE partition)
    if case.get("inject_fault"):
        return _fail_closed(trace, "GIP.CONTRACT_ERROR", "CONTRACT_ERROR", case["inject_fault"])

    claims: List[str] = []
    action_prop = case.get("action_proposal")

    for stage in stages:
        r = _run_stage(stage, case, req, risk, claims)
        if r is None:
            continue
        trace.component_versions[stage] = r.component_version
        shadow = dispositions.map_stage(stage, r.local_disposition)
        ev = AuditEvent(trace_id=trace.trace_id, seq=0, stage=stage,
                        component_version=r.component_version, disposition=r.local_disposition,
                        shadow_outcome=shadow, reason_codes=reason_codes.namespace(stage, r.reason_codes),
                        source_repr=r.source_repr, transformed_repr=r.transformed_repr,
                        semantic_loss=r.semantic_loss, latency_units=r.latency_units,
                        estimated_cost_usd=r.cost_usd)
        trace.add(ev)
        stage_outcomes.append((stage, shadow))

        # capture claims for downstream stages
        if stage == "claim_integrity":
            claims = r.extra.get("claims", [])
        elif stage == "scope_integrity":
            claims = r.extra.get("claims", claims)

        # fail-closed stops: execution/model unavailable halt the pipeline (nothing to govern)
        if stage == "execution_gate" and r.local_disposition == "INELIGIBLE":
            trace.finalize("EXECUTION_UNAVAILABLE"); return trace
        if stage == "model_policy" and r.local_disposition == "abstain":
            trace.finalize("EXECUTION_UNAVAILABLE"); return trace

    final, per_stage = dispositions.reconcile(stage_outcomes)
    # human review routing
    if req.get("human_review_required") and final in ("WOULD_ALLOW", "WOULD_QUALIFY"):
        trace.human_review_state = "required"
    trace.finalize(final)
    return trace


def _run_stage(stage, case, req, risk, claims):
    if stage == "execution_gate":
        return a_exec.run(case["registry"], req)
    if stage == "model_policy":
        elig = [m["model_id"] for m in case["registry"] if m.get("eligible", True)]
        return a_model.run(case["registry"], elig, case["telemetry"], req)
    if stage == "claim_integrity":
        return a_ci.run_claim_integrity(case["model_output"])
    if stage == "scope_integrity":
        return a_ci.run_scope_integrity(case["model_output"], claims)
    if stage == "evidence_assurance":
        evidence_binding.bind(claims, case["evidence_steer"])   # binding runs; disposition is EA's
        return a_ea.run(case["evidence_steer"], risk)
    if stage == "assertion_gate":
        return a_ag.run(case["assertion_signals"], risk)
    if stage == "action_gate":
        extracted = action_extraction.extract(case["model_output"], case.get("action_proposal"))
        if not extracted.found:
            return None                     # no action -> stage contributes nothing
        return a_act.run(extracted.action, req)
    return None
