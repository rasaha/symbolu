"""Governance-case reconstruction (H3).

Rebuilds a fully governed hiring decision across the hiring domain and the frozen
DGM kernel, and **cross-links the hiring-owned audit with the DGM governance
audit** (by correlation id). Shows the exact hiring recommendation + its claims and
provider (TAP) results, the bound DGM case and its recommendation/decision/override/
review records, the reviewer disposition path, and verification of the hiring audit
hash chain and the decision→recommendation citation. Read-only; tenant-isolated.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

from ..errors import CrossTenantHiringAccessError


@dataclass(frozen=True)
class GovernanceCaseReconstruction:
    recommendation_id: str
    tenant_id: str
    binding_versions: tuple = ()
    binding_status: Optional[str] = None
    hiring_recommendation: object = None
    claims: tuple = ()
    provider_bindings: tuple = ()
    decision_case: object = None
    case_history: tuple = ()
    kernel_recommendations: tuple = ()
    decisions: tuple = ()
    overrides: tuple = ()
    review_tasks: tuple = ()
    hiring_audit_events: tuple = ()
    governance_audit_events: tuple = ()
    hiring_hash_chain_valid: bool = False
    decision_cites_recommendation: bool = False
    human_authority_upheld: bool = False
    issues: tuple[str, ...] = ()

    @property
    def reconstructed(self) -> bool:
        return self.hiring_hash_chain_valid and not self.issues


class GovernanceCaseReconstructionService:
    def __init__(
        self, *, recommendations, claims, provider_bindings, bindings, cases,
        case_recommendations, case_decisions, hiring_audit_repository, kernel_audit_repository,
    ) -> None:
        self._recs = recommendations
        self._claims = claims
        self._provider_bindings = provider_bindings
        self._bindings = bindings
        self._cases = cases
        self._case_recs = case_recommendations
        self._case_decs = case_decisions
        self._hiring_audit = hiring_audit_repository
        self._kernel_audit = kernel_audit_repository

    def reconstruct(self, ctx, recommendation_id: str) -> GovernanceCaseReconstruction:
        binding = self._bindings.for_recommendation(recommendation_id)
        if binding is None:
            from ..errors import RecommendationNotFoundError
            raise RecommendationNotFoundError(
                f"no governance binding for recommendation '{recommendation_id}'")
        if binding.tenant_id != ctx.tenant_id:
            raise CrossTenantHiringAccessError(
                f"actor in tenant '{ctx.tenant_id}' may not reconstruct '{recommendation_id}'")

        rec = self._recs.get(recommendation_id)
        claims = self._claims.claims_for(recommendation_id, 1)
        pbindings = self._provider_bindings.bindings_for(recommendation_id, 1)

        case = self._cases.get_case(binding.decision_case_id)
        case_history = self._cases.get_case_history(binding.decision_case_id)
        kernel_recs = self._case_recs.list_recommendations(binding.decision_case_id)
        decisions = self._case_decs.list_decisions(binding.decision_case_id)
        overrides = self._case_decs.list_overrides(binding.decision_case_id)
        review_tasks = case.review_tasks

        hiring_events = tuple(e for e in self._hiring_audit.events_for("recommendation", recommendation_id)
                              if e.tenant_id == binding.tenant_id)
        gov_events = tuple(self._kernel_audit.list_by_correlation(binding.correlation_id))

        # verify hiring audit hash chain
        issues: list[str] = []
        prev = ""
        hash_ok = True
        for i, ev in enumerate(hiring_events):
            if not ev.hash_is_valid() or ev.previous_event_hash != prev:
                hash_ok = False
                issues.append(f"hiring event[{i}] {ev.event_id}: chain/hash invalid")
            prev = ev.event_hash

        # decision cites the kernel recommendation
        cites = False
        human_ok = True
        for d in decisions:
            ref_ids = {r.ref_id for r in d.recommendation_refs}
            if binding.kernel_recommendation_id in ref_ids:
                cites = True
            if d.authority_type.value not in ("HUMAN_REVIEWER", "HUMAN_APPROVER", "COMMITTEE"):
                human_ok = False
                issues.append(f"decision {d.decision_id}: non-human authority {d.authority_type.value}")
        if decisions and not cites:
            issues.append("no decision cites the bound kernel recommendation")

        return GovernanceCaseReconstruction(
            recommendation_id=recommendation_id, tenant_id=binding.tenant_id,
            binding_versions=self._bindings.history(binding.binding_id),
            binding_status=binding.status.value, hiring_recommendation=rec, claims=claims,
            provider_bindings=pbindings, decision_case=case, case_history=case_history,
            kernel_recommendations=kernel_recs, decisions=decisions, overrides=overrides,
            review_tasks=review_tasks, hiring_audit_events=hiring_events,
            governance_audit_events=gov_events, hiring_hash_chain_valid=hash_ok,
            decision_cites_recommendation=cites,
            human_authority_upheld=human_ok if decisions else True, issues=tuple(issues))
