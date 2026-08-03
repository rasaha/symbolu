"""Reconstruction & audit support for H1 hiring product records.

Rebuilds the full, ordered lifecycle of any H1 entity from two independent,
tamper-evident sources and cross-checks them:

* the immutable **versioned record history** (every stored version, in order);
* the append-only **domain audit event chain** (hash-chained per entity).

The result reports whether the per-entity audit hash chain verifies, whether the
audit lineage of ``new_state`` values is consistent with the versioned statuses,
and the reconstructed final state. Read-only; enforces tenant isolation.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

from ..domain_audit.event import HiringDomainAuditEvent
from ..domain_audit.repository import HiringDomainAuditRepository
from ..errors import CrossTenantHiringAccessError, HiringProductError
from ..repositories.product_repositories import (
    ApplicationRepository,
    CandidateRepository,
    EvidenceIntakeRepository,
    JobDefinitionRepository,
    RequisitionRepository,
)
from ._hiring_context import ActorContext

_ENTITY_TYPES = ("requisition", "job_definition", "candidate", "application", "evidence_intake")


@dataclass(frozen=True)
class ReconstructionResult:
    entity_type: str
    entity_id: str
    versions: tuple = ()
    events: tuple[HiringDomainAuditEvent, ...] = ()
    hash_chain_valid: bool = False
    state_lineage_consistent: bool = False
    final_state: Optional[str] = None
    version_count: int = 0
    event_count: int = 0
    issues: tuple[str, ...] = ()

    @property
    def reconstructed(self) -> bool:
        """Fully reconstructable iff the chain verifies and state lineage is consistent."""
        return self.hash_chain_valid and self.state_lineage_consistent and not self.issues


class HiringReconstructionService:
    def __init__(
        self,
        *,
        requisitions: RequisitionRepository,
        job_definitions: JobDefinitionRepository,
        candidates: CandidateRepository,
        applications: ApplicationRepository,
        evidence_intake: EvidenceIntakeRepository,
        audit_repository: HiringDomainAuditRepository,
    ) -> None:
        self._repos = {
            "requisition": requisitions,
            "job_definition": job_definitions,
            "candidate": candidates,
            "application": applications,
            "evidence_intake": evidence_intake,
        }
        self._audit_repo = audit_repository

    def _status_of(self, record) -> Optional[str]:
        status = getattr(record, "status", None)
        return status.value if status is not None else None

    def _verify_chain(self, events: tuple[HiringDomainAuditEvent, ...]) -> tuple[bool, list[str]]:
        issues: list[str] = []
        prev = ""
        ok = True
        for i, ev in enumerate(events):
            if not ev.hash_is_valid():
                ok = False
                issues.append(f"event[{i}] {ev.event_id}: event_hash does not match content")
            if ev.previous_event_hash != prev:
                ok = False
                issues.append(f"event[{i}] {ev.event_id}: broken chain link")
            prev = ev.event_hash
        return ok, issues

    def reconstruct(self, ctx: ActorContext, *, entity_type: str, entity_id: str) -> ReconstructionResult:
        if entity_type not in _ENTITY_TYPES:
            raise HiringProductError(f"unknown entity_type '{entity_type}'")
        repo = self._repos[entity_type]

        versions = repo.history(entity_id)  # raises typed NotFound if absent
        latest = versions[-1]
        # Tenant isolation on a read path (no audit side effect):
        if latest.tenant_id != ctx.tenant_id:
            raise CrossTenantHiringAccessError(
                f"actor in tenant '{ctx.tenant_id}' may not reconstruct {entity_type} '{entity_id}'"
            )

        events = self._audit_repo.events_for(entity_type, entity_id)
        # Only this entity's tenant events (defensive; ids are unique per entity).
        events = tuple(e for e in events if e.tenant_id == latest.tenant_id)

        hash_ok, issues = self._verify_chain(events)

        # State-lineage consistency: the audit events that carry a new_state must
        # match, in order, the distinct statuses observed across versioned history.
        version_states = [self._status_of(v) for v in versions if self._status_of(v) is not None]
        event_states = [e.new_state for e in events if e.new_state is not None]
        # Collapse consecutive duplicates in the version sequence (a profile revision
        # keeps status the same but bumps version).
        collapsed_versions: list[str] = []
        for s in version_states:
            if not collapsed_versions or collapsed_versions[-1] != s:
                collapsed_versions.append(s)
        # The event new_state stream, restricted to status-bearing events, should
        # reproduce the collapsed version-state sequence.
        collapsed_events: list[str] = []
        for s in event_states:
            if not collapsed_events or collapsed_events[-1] != s:
                collapsed_events.append(s)
        state_ok = collapsed_events == collapsed_versions
        if not state_ok:
            issues.append(
                f"state lineage mismatch: versions={collapsed_versions} events={collapsed_events}"
            )

        return ReconstructionResult(
            entity_type=entity_type, entity_id=entity_id, versions=versions, events=events,
            hash_chain_valid=hash_ok, state_lineage_consistent=state_ok,
            final_state=self._status_of(latest), version_count=len(versions),
            event_count=len(events), issues=tuple(issues),
        )
