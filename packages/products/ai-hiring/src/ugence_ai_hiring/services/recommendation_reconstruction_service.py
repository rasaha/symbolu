"""Deterministic recommendation-provenance reconstruction (H2).

Rebuilds the exact provenance of a recommendation: its version history, the exact
evidence set and package fingerprint, the rubric and job-definition versions, every
claim and its provider (TAP) evaluation, reviewer dispositions, the supersession
chain, and verification of the recommendation's hiring-owned audit hash chain.
Read-only; enforces tenant isolation.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

from ..domain_audit.repository import HiringDomainAuditRepository
from ..errors import CrossTenantHiringAccessError
from ..recommendations.recommendation import HiringRecommendation
from ._hiring_context import ActorContext


@dataclass(frozen=True)
class RecommendationReconstruction:
    recommendation_id: str
    tenant_id: str
    versions: tuple = ()
    final_status: Optional[str] = None
    evidence_refs: tuple[str, ...] = ()
    evidence_package_ref: str = ""
    provenance_fingerprint: str = ""
    rubric_version: int = 0
    job_definition_version: int = 0
    claims: tuple = ()
    provider_bindings: tuple = ()
    reviewer_dispositions: tuple = ()
    supersedes: str = ""
    superseded_by: str = ""
    events: tuple = ()
    hash_chain_valid: bool = False
    issues: tuple[str, ...] = ()

    @property
    def reconstructed(self) -> bool:
        return self.hash_chain_valid and not self.issues


class RecommendationReconstructionService:
    def __init__(
        self, *, recommendations, claims, bindings, dispositions,
        audit_repository: HiringDomainAuditRepository,
    ) -> None:
        self._recs = recommendations
        self._claims = claims
        self._bindings = bindings
        self._dispositions = dispositions
        self._audit_repo = audit_repository

    def reconstruct(self, ctx: ActorContext, recommendation_id: str) -> RecommendationReconstruction:
        versions = self._recs.history(recommendation_id)  # typed NotFound if absent
        latest: HiringRecommendation = versions[-1]
        if latest.tenant_id != ctx.tenant_id:
            raise CrossTenantHiringAccessError(
                f"actor in tenant '{ctx.tenant_id}' may not reconstruct recommendation "
                f"'{recommendation_id}'")

        first = versions[0]
        claims = self._claims.claims_for(recommendation_id, first.version)
        bindings = self._bindings.bindings_for(recommendation_id, first.version)
        dispositions = self._dispositions.dispositions_for(recommendation_id)

        events = tuple(e for e in self._audit_repo.events_for("recommendation", recommendation_id)
                       if e.tenant_id == latest.tenant_id)
        issues: list[str] = []
        prev = ""
        hash_ok = True
        for i, ev in enumerate(events):
            if not ev.hash_is_valid():
                hash_ok = False
                issues.append(f"event[{i}] {ev.event_id}: event_hash mismatch")
            if ev.previous_event_hash != prev:
                hash_ok = False
                issues.append(f"event[{i}] {ev.event_id}: broken chain link")
            prev = ev.event_hash

        # Cross-check: material claims recorded == recommendation's material_claim_ids.
        material_ids = {c.claim_id for c in claims if c.material}
        if material_ids != set(first.material_claim_ids):
            issues.append("material claim set mismatch vs recommendation record")

        return RecommendationReconstruction(
            recommendation_id=recommendation_id, tenant_id=latest.tenant_id, versions=versions,
            final_status=latest.status.value, evidence_refs=first.evidence_refs,
            evidence_package_ref=first.evidence_package_ref, provenance_fingerprint=first.provenance_id,
            rubric_version=first.rubric_version, job_definition_version=first.job_definition_version,
            claims=claims, provider_bindings=bindings, reviewer_dispositions=dispositions,
            supersedes=latest.supersedes, superseded_by=latest.superseded_by, events=events,
            hash_chain_valid=hash_ok, issues=tuple(issues))
