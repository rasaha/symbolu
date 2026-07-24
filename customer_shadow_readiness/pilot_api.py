"""Non-enforcing pilot API (M6). The single shadow-only entry point for a bounded customer pilot. It
composes security (authn/authz/tenant) + secure intake + data minimization + the READ-ONLY pilot
orchestrator, returning a WOULD_* shadow disposition and a minimized, redacted trace. It NEVER enforces
and NEVER executes an external action. Deterministic.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from . import security, intake as intake_mod, data_controls as dc, killswitch
from governed_inference_pilot import orchestrator                     # read-only


@dataclass
class ShadowResponse:
    accepted: bool
    final_shadow_disposition: str = "CONTRACT_ERROR"
    stage_dispositions: Dict[str, str] = field(default_factory=dict)
    reason_codes: List[str] = field(default_factory=list)
    replay_signature: str = ""
    human_review_state: str = "not_required"
    tenant: str = ""
    enforced: bool = False                # ALWAYS False - shadow only


def submit(token: Optional[str], tenant: str, case: Dict[str, Any]) -> ShadowResponse:
    """A tenant submits a governed case (a GIP-shaped dict). Returns a shadow disposition only."""
    # 0. kill switches (pilot-wide and tenant-level) - fail closed if tripped
    ks = killswitch.check(tenant)
    if not ks.active:
        return ShadowResponse(False, "EXECUTION_UNAVAILABLE", reason_codes=[f"KILL.{ks.reason}"],
                              tenant=tenant)
    # 1. access control
    acc = security.check_access(token, "shadow:submit", tenant)
    if not acc.allowed:
        return ShadowResponse(False, "CONTRACT_ERROR", reason_codes=acc.reason_codes, tenant=tenant)
    # 2. tenant scoping on the case itself (no cross-tenant reference)
    if case.get("request", {}).get("tenant_id") not in (tenant, None):
        return ShadowResponse(False, "CONTRACT_ERROR",
                              reason_codes=["SEC.CROSS_TENANT_CASE"], tenant=tenant)
    # 3. secure intake of the model output artifact
    clearance = case.get("request", {}).get("data_sensitivity", "internal")
    itk = intake_mod.intake(case.get("model_output", ""), clearance)
    if not itk.accepted:
        return ShadowResponse(False, "CONTRACT_ERROR", reason_codes=itk.reason_codes, tenant=tenant)
    # 4. run the READ-ONLY pilot orchestrator (shadow disposition only)
    trace = orchestrator.run_case(case)
    stage = {e.stage: e.disposition for e in trace.events}
    return ShadowResponse(
        accepted=True, final_shadow_disposition=trace.final_shadow_disposition,
        stage_dispositions=stage,
        reason_codes=[rc for e in trace.events for rc in e.reason_codes][:20],
        replay_signature=trace.replay_signature, human_review_state=trace.human_review_state,
        tenant=tenant, enforced=False)
