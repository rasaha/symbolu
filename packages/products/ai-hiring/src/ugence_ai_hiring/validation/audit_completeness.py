"""Audit-completeness scoring (H5) — validation-only, read-only.

A transparent per-case checklist of the presence and integrity of every accountable
record along the chain. A composite score never hides a critical missing record:
critical items are scored separately and any critical failure fails the case.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from .composition import ValidationEnv
from .lifecycle import CaseRun

# Items marked critical must be present for a consequential (executed) case.
_CRITICAL = frozenset({
    "source_evidence", "human_authority", "authorization_record", "execution_attempt",
    "receipt", "reconciliation", "hash_chain_verified"})


@dataclass
class AuditCompletenessScore:
    case_id: str
    items: dict = field(default_factory=dict)      # item -> bool
    critical_failures: tuple[str, ...] = ()
    present_count: int = 0
    total_count: int = 0

    @property
    def passed(self) -> bool:
        return not self.critical_failures

    @property
    def ratio(self) -> float:
        return self.present_count / self.total_count if self.total_count else 0.0


def score_case(env: ValidationEnv, run: CaseRun) -> AuditCompletenessScore:
    executed = bool(run.execution_status)
    items: dict[str, bool] = {}

    items["source_evidence"] = bool(env.intake.items_for_application(run.application_id)) if run.application_id else False
    items["provenance"] = all(i.provenance.collected_by for i in env.intake.items_for_application(run.application_id)) \
        if run.application_id else False
    items["recommendation_claims"] = bool(env.claims.claims_for(run.recommendation_id, 1)) if run.recommendation_id else False
    items["assertion_assessments"] = bool(env.provider_bindings.bindings_for(run.recommendation_id, 1)) \
        if run.recommendation_id else False
    items["human_authority"] = bool(run.decision_id)
    items["decision_rationale"] = bool(run.decision_id)  # kernel decision carries reason codes
    items["authorization_record"] = bool(env.authorizations.latest_for_proposal(run.action_proposal_id)) \
        if run.action_proposal_id else False
    auth = env.authorizations.latest_for_proposal(run.action_proposal_id) if run.action_proposal_id else None
    items["constraints_and_obligations"] = auth is not None  # record carries them (possibly empty)
    items["execution_attempt"] = bool(env.attempts.for_proposal(run.action_proposal_id)) if run.action_proposal_id else False
    attempts = env.attempts.for_proposal(run.action_proposal_id) if run.action_proposal_id else ()
    items["receipt"] = any(a.receipt is not None for a in attempts)
    items["reconciliation"] = bool(env.reconciliations.latest_for_proposal(run.action_proposal_id)) \
        if run.action_proposal_id else False
    # correlation / causation present on the hiring audit for this action
    action_events = env.audit_repo.events_for("action", run.action_proposal_id) if run.action_proposal_id else ()
    items["correlation_chain"] = all(e.correlation_id for e in action_events) if action_events else False
    items["causation_chain"] = any(e.causation_id for e in action_events) if action_events else False
    # hiring audit hash chain verifies (via reconstruction)
    if run.action_proposal_id:
        rc = env.action_reconstruction.reconstruct(env.ai(), run.action_proposal_id)
        items["hash_chain_verified"] = rc.hiring_hash_chain_valid
    else:
        items["hash_chain_verified"] = False

    # For a non-executed case, action-stage items are N/A → not scored as failures.
    if not executed:
        for k in ("authorization_record", "constraints_and_obligations", "execution_attempt",
                  "receipt", "reconciliation", "correlation_chain", "causation_chain", "hash_chain_verified"):
            items[k] = True if not run.action_proposal_id else items[k]

    critical_failures = tuple(sorted(k for k in _CRITICAL if not items.get(k, False))) if executed else ()
    present = sum(1 for v in items.values() if v)
    return AuditCompletenessScore(case_id=run.spec.case_id, items=items,
                                  critical_failures=critical_failures, present_count=present,
                                  total_count=len(items))
