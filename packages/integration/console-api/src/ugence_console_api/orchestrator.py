"""The governed loop — the product.

Runs a single proposed action through the consolidated control plane and records
the trail. The runtime *proposes*; the control plane *governs*; every step is
*recorded*:

    Gateway   -> Context Minimization    what may enter
    Verify    -> Truth Assurance         is the assertion supported
    Authorize -> ActionGate              may THIS exact action execute (CER-bound)
    Clear     -> Autonomous Control Plane is it operationally safe right now
    Record    -> Audit                   reconstructable decision chain

Deployment mode governs consequence, not evaluation. In SHADOW the loop evaluates
and records but changes nothing; ``would_execute`` still reports what ENFORCEMENT
would have done. Any stage that finds a blocking condition makes ``would_execute``
false — the gates are non-compensatory (a clean authorization cannot buy back an
operational HOLD or an unsupported assertion).
"""

from __future__ import annotations

import uuid

from .audit import AuditChain, AuditEntry, AuditStore
from .capabilities import (
    action_control,
    context_gateway,
    operational_safety,
    registry,
    truth_evidence,
)
from .models import (
    DeploymentMode,
    GovernedLoopRequest,
    GovernedLoopResult,
    StageResult,
)

# Verdicts that permit execution at each gate (everything else blocks).
_ASSERTION_OK = {"SUPPORTED", "CONSTRAINED"}
_ACTION_OK = {"AUTHORIZED", "AUTHORIZED_WITH_CONSTRAINTS"}
_CLEARANCE_OK = {"CLEAR"}


def _stage(key: str, stage: str, question: str, decision: str, summary: str,
           detail: dict) -> StageResult:
    m = registry.get(key)
    return StageResult(
        stage=stage, capability=m.capability, module=m.name,
        module_maturity=m.maturity, question=question, decision=decision,
        summary=summary, detail=detail,
    )


def run(req: GovernedLoopRequest, audit: AuditStore) -> GovernedLoopResult:
    correlation_id = req.correlation_id or f"corr-{uuid.uuid4().hex[:12]}"
    # Propagate correlation id into every sub-request.
    req.assertion.correlation_id = correlation_id
    req.action.correlation_id = correlation_id

    stages: list[StageResult] = []
    would_execute = True

    # --- Gateway · Context Minimization ---------------------------------- #
    if req.context_units:
        min_res = context_gateway.minimize(req.context_units)
        stages.append(_stage(
            "context_minimization", "Gateway",
            "What information may the reasoning process receive?",
            "ADMITTED",
            f"Admitted {len(min_res.kept_ids)}/{min_res.total_units} units "
            f"({min_res.removed_units} redundant dropped, lossless={min_res.lossless}).",
            min_res.model_dump(),
        ))

    # --- Verify · Truth Assurance Platform ------------------------------- #
    tap = truth_evidence.evaluate(req.assertion)
    assertion_ok = tap.coverage in _ASSERTION_OK
    would_execute = would_execute and assertion_ok
    stages.append(_stage(
        "tap", "Verify", "Is the completed response sufficiently supported?",
        tap.coverage,
        f"Assertion {tap.coverage.lower()} at evidence coverage {tap.evidence_coverage:.0%}.",
        tap.model_dump(),
    ))

    # --- Authorize · ActionGate (CER-bound) ------------------------------ #
    act = action_control.authorize(req.action)
    action_ok = act.outcome in _ACTION_OK
    would_execute = would_execute and action_ok
    stages.append(_stage(
        "actiongate", "Authorize", "May THIS exact action be executed?",
        act.outcome,
        f"ActionGate {act.outcome} (cer {act.cer_id}); reasons {act.reason_codes}.",
        act.model_dump(),
    ))

    # --- Clear · Autonomous Control Plane -------------------------------- #
    clr = operational_safety.clear(req.operational_signals)
    clearance_ok = clr.disposition in _CLEARANCE_OK
    would_execute = would_execute and clearance_ok
    stages.append(_stage(
        "autonomous_control_plane", "Clear", "Is execution operationally safe right now?",
        clr.disposition,
        f"Operational clearance {clr.disposition}: {', '.join(clr.reason_codes)}.",
        clr.model_dump(),
    ))

    # --- Record · Audit -------------------------------------------------- #
    final = _final_disposition(req.mode, would_execute)
    entries = [
        AuditEntry(stage=s.stage, module=s.module, decision=s.decision,
                   summary=s.summary, detail=s.detail)
        for s in stages
    ]
    chain = AuditChain(
        correlation_id=correlation_id, cer_id=act.cer_id, mode=req.mode.value,
        final_disposition=final, entries=entries,
    )
    audit.record(chain)
    stages.append(_stage(
        "actiongate", "Record", "Can the decision be reconstructed?", "RECORDED",
        f"Decision chain recorded under correlation {correlation_id}.",
        {"correlation_id": correlation_id, "cer_id": act.cer_id, "stages": len(entries)},
    ))

    return GovernedLoopResult(
        correlation_id=correlation_id, cer_id=act.cer_id, mode=req.mode,
        stages=stages, final_disposition=final, would_execute=would_execute,
        recorded=True,
    )


def _final_disposition(mode: DeploymentMode, would_execute: bool) -> str:
    verdict = "would ALLOW" if would_execute else "would BLOCK"
    if mode is DeploymentMode.SHADOW:
        return f"OBSERVED (shadow) — enforcement {verdict}; nothing changed."
    if mode is DeploymentMode.RECOMMENDATION:
        action = "no escalation required" if would_execute else "escalation surfaced to humans"
        return f"RECOMMENDATION — {verdict}; {action}."
    return "ALLOWED" if would_execute else "BLOCKED"
