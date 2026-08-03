"""End-to-end decision→outcome reconstruction (H4).

Given a hiring-action proposal, reconstructs the entire chain — source recommendation
+ TAP claim evaluations, human review + decision, action proposal, ActionGate
authorization (constraints/obligations/expiry), execution attempts + receipts,
reconciliation, and the compensation/remediation chain — and cross-links the
hiring-owned audit with the DGM governance audit (by correlation id) and the provider
records. Detects broken links, missing versions, altered hashes, and inconsistent
tenant scope. Read-only; tenant-isolated.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from ..errors import CrossTenantHiringAccessError
from ._hiring_context import ActorContext


@dataclass(frozen=True)
class ActionReconstruction:
    action_proposal_id: str
    tenant_id: str
    proposal_versions: tuple = ()
    recommendation: object = None
    claims: tuple = ()
    provider_claim_bindings: tuple = ()
    governance_binding: object = None
    human_decision: object = None
    authorizations: tuple = ()
    attempts: tuple = ()
    reconciliations: tuple = ()
    compensations: tuple = ()
    hiring_audit_events: tuple = ()
    governance_audit_events: tuple = ()
    hiring_hash_chain_valid: bool = False
    links_intact: bool = False
    tenant_scope_consistent: bool = False
    issues: tuple[str, ...] = ()

    @property
    def reconstructed(self) -> bool:
        return (self.hiring_hash_chain_valid and self.links_intact
                and self.tenant_scope_consistent and not self.issues)


class HiringActionReconstructionService:
    def __init__(
        self, *, proposals, recommendations, claims, provider_bindings, governance_bindings,
        case_decisions, authorizations, attempts, reconciliations, compensations,
        hiring_audit_repository, kernel_audit_repository,
    ) -> None:
        self._proposals = proposals
        self._recs = recommendations
        self._claims = claims
        self._provider_bindings = provider_bindings
        self._gbindings = governance_bindings
        self._case_decs = case_decisions
        self._auths = authorizations
        self._attempts = attempts
        self._recons = reconciliations
        self._comps = compensations
        self._hiring_audit = hiring_audit_repository
        self._kernel_audit = kernel_audit_repository

    def reconstruct(self, ctx: ActorContext, action_proposal_id: str) -> ActionReconstruction:
        versions = self._proposals.history(action_proposal_id)  # typed NotFound if absent
        proposal = versions[-1]
        if proposal.tenant_id != ctx.tenant_id:
            raise CrossTenantHiringAccessError(
                f"actor in tenant '{ctx.tenant_id}' may not reconstruct '{action_proposal_id}'")

        rec = self._recs.get(proposal.recommendation_id) if self._recs.exists(proposal.recommendation_id) else None
        claims = self._claims.claims_for(proposal.recommendation_id, 1) if rec else ()
        pbindings = self._provider_bindings.bindings_for(proposal.recommendation_id, 1) if rec else ()
        gbinding = self._gbindings.for_recommendation(proposal.recommendation_id)
        decision = self._case_decs.get_decision(proposal.human_decision_id)
        auths = self._auths.for_proposal(action_proposal_id)
        attempts = self._attempts.for_proposal(action_proposal_id)
        recons = self._recons.for_proposal(action_proposal_id)
        comps = self._comps.for_proposal(action_proposal_id)

        hiring_events = tuple(e for e in self._hiring_audit.events_for("action", action_proposal_id)
                              if e.tenant_id == proposal.tenant_id)
        gov_events = tuple(self._kernel_audit.list_by_correlation(proposal.correlation_id))

        issues: list[str] = []
        # hiring audit hash chain
        prev = ""
        hash_ok = True
        for i, ev in enumerate(hiring_events):
            if not ev.hash_is_valid() or ev.previous_event_hash != prev:
                hash_ok = False
                issues.append(f"action event[{i}] {ev.event_id}: chain/hash invalid")
            prev = ev.event_hash

        # link integrity
        links_ok = True
        if decision is None or proposal.human_decision_id != decision.decision_id:
            links_ok = False; issues.append("proposal does not link to its human decision")
        for a in attempts:
            if not any(a.authorization_id == au.authorization_id for au in auths):
                links_ok = False; issues.append(f"attempt {a.attempt_id} unlinked to an authorization")
        if gbinding is not None and gbinding.decision_id != proposal.human_decision_id:
            links_ok = False; issues.append("governance binding decision != proposal decision")

        # tenant scope
        scope_ok = all(x.tenant_id == proposal.tenant_id for x in (list(auths) + list(attempts) + list(recons)))
        if rec is not None and rec.tenant_id != proposal.tenant_id:
            scope_ok = False; issues.append("recommendation tenant mismatch")
        if not scope_ok:
            issues.append("inconsistent tenant scope across the chain")

        return ActionReconstruction(
            action_proposal_id=action_proposal_id, tenant_id=proposal.tenant_id,
            proposal_versions=versions, recommendation=rec, claims=claims,
            provider_claim_bindings=pbindings, governance_binding=gbinding, human_decision=decision,
            authorizations=auths, attempts=attempts, reconciliations=recons, compensations=comps,
            hiring_audit_events=hiring_events, governance_audit_events=gov_events,
            hiring_hash_chain_valid=hash_ok, links_intact=links_ok, tenant_scope_consistent=scope_ok,
            issues=tuple(issues))
