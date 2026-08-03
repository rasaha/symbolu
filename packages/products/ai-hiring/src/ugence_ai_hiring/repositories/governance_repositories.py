"""In-memory repository for H3 governance-case bindings.

Versioned, immutable, tenant-agnostic storage (tenant isolation enforced in the
service) with lookups by hiring recommendation, application, and decision case.
"""

from __future__ import annotations

from typing import Optional

from ..errors import HiringProductError
from ..governance.binding import GovernanceCaseBinding
from .product_repositories import _VersionedStore


class GovernanceBindingNotFoundError(HiringProductError):
    """No governance-case binding exists for the given key."""


class InMemoryGovernanceCaseBindingRepository:
    def __init__(self) -> None:
        self._s: _VersionedStore[GovernanceCaseBinding] = _VersionedStore(
            id_of=lambda r: r.binding_id, version_of=lambda r: r.version,
            not_found=lambda k: GovernanceBindingNotFoundError(f"governance binding '{k}' not found"),
            label="governance_binding")

    def add(self, record): return self._s.add(record)
    def get(self, binding_id): return self._s.get(binding_id)
    def exists(self, binding_id): return self._s.exists(binding_id)
    def history(self, binding_id): return self._s.history(binding_id)

    def for_recommendation(self, hiring_recommendation_id: str) -> Optional[GovernanceCaseBinding]:
        matches = [b for b in self._s.latest_records()
                   if b.hiring_recommendation_id == hiring_recommendation_id]
        return max(matches, key=lambda b: b.version) if matches else None

    def for_application(self, application_id: str) -> tuple[GovernanceCaseBinding, ...]:
        return tuple(sorted((b for b in self._s.latest_records() if b.application_id == application_id),
                            key=lambda b: b.binding_id))

    def by_tenant(self, tenant_id: str) -> tuple[GovernanceCaseBinding, ...]:
        return tuple(sorted((b for b in self._s.latest_records() if b.tenant_id == tenant_id),
                            key=lambda b: b.binding_id))
