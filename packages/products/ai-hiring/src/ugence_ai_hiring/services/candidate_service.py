"""Candidate application service (H1).

Registers candidates and manages their profile revisions and withdrawal, with
tenant isolation and domain-audit recording. Candidate data is hiring-owned; the
governance kernel only ever sees the opaque ``subject_id``.
"""

from __future__ import annotations

from typing import Callable, Optional

from ugence_decision_authority.api.common import new_id

from ..candidates.candidate import Candidate, CandidateProfile
from ..domain_audit.events import HiringDomainEventType
from ..domain_audit.service import HiringDomainAuditService
from ..repositories.product_repositories import CandidateRepository
from ._hiring_context import ActorContext, guard_tenant


class CandidateService:
    def __init__(
        self,
        *,
        candidates: CandidateRepository,
        audit: HiringDomainAuditService,
        id_factory: Callable[[str], str] = new_id,
    ) -> None:
        self._candidates = candidates
        self._audit = audit
        self._new_id = id_factory

    def register_candidate(
        self, ctx: ActorContext, *, subject_id: str, candidate_id: Optional[str] = None,
        profile: Optional[CandidateProfile] = None, correlation_id: str = "",
    ) -> Candidate:
        cid = candidate_id or self._new_id("cand")
        candidate = Candidate(
            candidate_id=cid, tenant_id=ctx.tenant_id, subject_id=subject_id,
            profile=profile or CandidateProfile(), created_by=ctx.actor_id,
            correlation_id=correlation_id,
        )
        self._candidates.add(candidate)
        self._audit.record(
            event_type=HiringDomainEventType.CANDIDATE_REGISTERED, entity_type="candidate",
            entity_id=cid, tenant_id=ctx.tenant_id, actor_id=ctx.actor_id, actor_type=ctx.actor_type,
            new_state=candidate.status.value, entity_version=candidate.version,
            correlation_id=correlation_id,
        )
        return candidate

    def revise_profile(self, ctx: ActorContext, candidate_id: str, profile: CandidateProfile) -> Candidate:
        current = self._candidates.get(candidate_id)
        guard_tenant(ctx, record_tenant_id=current.tenant_id, entity_type="candidate",
                     entity_id=candidate_id, audit=self._audit)
        updated = current.with_profile(profile)
        self._candidates.add(updated)
        self._audit.record(
            event_type=HiringDomainEventType.CANDIDATE_PROFILE_REVISED, entity_type="candidate",
            entity_id=candidate_id, tenant_id=ctx.tenant_id, actor_id=ctx.actor_id,
            actor_type=ctx.actor_type, previous_state=current.status.value,
            new_state=updated.status.value, entity_version=updated.version,
            correlation_id=current.correlation_id,
        )
        return updated

    def withdraw_candidate(self, ctx: ActorContext, candidate_id: str) -> Candidate:
        current = self._candidates.get(candidate_id)
        guard_tenant(ctx, record_tenant_id=current.tenant_id, entity_type="candidate",
                     entity_id=candidate_id, audit=self._audit)
        updated = current.withdrawn()
        self._candidates.add(updated)
        self._audit.record(
            event_type=HiringDomainEventType.CANDIDATE_WITHDRAWN, entity_type="candidate",
            entity_id=candidate_id, tenant_id=ctx.tenant_id, actor_id=ctx.actor_id,
            actor_type=ctx.actor_type, previous_state=current.status.value,
            new_state=updated.status.value, entity_version=updated.version,
            correlation_id=current.correlation_id,
        )
        return updated
