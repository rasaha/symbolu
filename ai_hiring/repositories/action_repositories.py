"""In-memory repositories for H4 action/authorization/execution records.

Versioned proposals + append-only authorization, execution-attempt, reconciliation,
and compensation records. Immutable, tenant-agnostic storage (tenant isolation in
services), deterministic ordering, duplicate prevention. No production database.
"""

from __future__ import annotations

from typing import Optional

from ..actions.proposal import HiringActionProposal
from ..actions.records import (
    ActionAuthorizationRecord,
    CompensationRequirement,
    ExecutionAttempt,
    ReconciliationRecord,
)
from ..errors import (
    ActionAuthorizationNotFoundError,
    ActionProposalNotFoundError,
    VersionConflictError,
)
from .product_repositories import _VersionedStore


class InMemoryHiringActionProposalRepository:
    def __init__(self) -> None:
        self._s: _VersionedStore[HiringActionProposal] = _VersionedStore(
            id_of=lambda r: r.action_proposal_id, version_of=lambda r: r.version,
            not_found=lambda k: ActionProposalNotFoundError(f"action proposal '{k}' not found"),
            label="action_proposal")

    def add(self, record): return self._s.add(record)
    def get(self, proposal_id): return self._s.get(proposal_id)
    def exists(self, proposal_id): return self._s.exists(proposal_id)
    def history(self, proposal_id): return self._s.history(proposal_id)

    def for_application(self, application_id: str) -> tuple[HiringActionProposal, ...]:
        return tuple(sorted((p for p in self._s.latest_records() if p.application_id == application_id),
                            key=lambda p: p.action_proposal_id))

    def for_recommendation(self, recommendation_id: str) -> tuple[HiringActionProposal, ...]:
        return tuple(sorted((p for p in self._s.latest_records() if p.recommendation_id == recommendation_id),
                            key=lambda p: p.action_proposal_id))

    def by_tenant(self, tenant_id: str) -> tuple[HiringActionProposal, ...]:
        return tuple(sorted((p for p in self._s.latest_records() if p.tenant_id == tenant_id),
                            key=lambda p: p.action_proposal_id))

    def for_idempotency_key(self, tenant_id: str, idempotency_key: str) -> Optional[HiringActionProposal]:
        matches = [p for p in self._s.latest_records()
                   if p.tenant_id == tenant_id and p.idempotency_key == idempotency_key]
        return matches[0] if matches else None


class _AppendStore:
    def __init__(self, id_of, label):
        self._id_of = id_of
        self._label = label
        self._by_id: dict = {}

    def add(self, record):
        rid = self._id_of(record)
        if rid in self._by_id:
            raise VersionConflictError(f"{self._label} '{rid}' already exists")
        self._by_id[rid] = record
        return record

    def all(self):
        return tuple(self._by_id.values())


class InMemoryActionAuthorizationRepository:
    def __init__(self) -> None:
        self._s = _AppendStore(lambda r: r.authorization_id, "authorization")

    def add(self, record): return self._s.add(record)

    def get(self, authorization_id: str) -> ActionAuthorizationRecord:
        for r in self._s.all():
            if r.authorization_id == authorization_id:
                return r
        raise ActionAuthorizationNotFoundError(f"authorization '{authorization_id}' not found")

    def latest_for_proposal(self, proposal_id: str) -> Optional[ActionAuthorizationRecord]:
        matches = [r for r in self._s.all() if r.action_proposal_id == proposal_id]
        return max(matches, key=lambda r: r.created_at) if matches else None

    def for_proposal(self, proposal_id: str) -> tuple[ActionAuthorizationRecord, ...]:
        return tuple(r for r in self._s.all() if r.action_proposal_id == proposal_id)


class InMemoryExecutionAttemptRepository:
    def __init__(self) -> None:
        self._s = _AppendStore(lambda r: r.attempt_id, "attempt")

    def add(self, record): return self._s.add(record)

    def for_proposal(self, proposal_id: str) -> tuple[ExecutionAttempt, ...]:
        return tuple(sorted((r for r in self._s.all() if r.action_proposal_id == proposal_id),
                            key=lambda r: r.attempt_number))


class InMemoryReconciliationRepository:
    def __init__(self) -> None:
        self._s = _AppendStore(lambda r: r.reconciliation_id, "reconciliation")

    def add(self, record): return self._s.add(record)

    def latest_for_proposal(self, proposal_id: str) -> Optional[ReconciliationRecord]:
        matches = [r for r in self._s.all() if r.action_proposal_id == proposal_id]
        return max(matches, key=lambda r: r.created_at) if matches else None

    def for_proposal(self, proposal_id: str) -> tuple[ReconciliationRecord, ...]:
        return tuple(r for r in self._s.all() if r.action_proposal_id == proposal_id)


class InMemoryCompensationRepository:
    def __init__(self) -> None:
        self._s = _AppendStore(lambda r: r.compensation_id, "compensation")

    def add(self, record): return self._s.add(record)

    def for_proposal(self, proposal_id: str) -> tuple[CompensationRequirement, ...]:
        return tuple(r for r in self._s.all() if r.action_proposal_id == proposal_id)

    def by_tenant(self, tenant_id: str) -> tuple[CompensationRequirement, ...]:
        return tuple(r for r in self._s.all() if r.tenant_id == tenant_id)
