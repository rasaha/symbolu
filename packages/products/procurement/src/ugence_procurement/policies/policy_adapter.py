"""Procurement access-policy adapter over the kernel grant-based policy.

``ProcurementPolicyAdapter`` composes the kernel ``GrantStore`` /
``EvidenceAccessPolicy`` for procurement principals (requesters, approvers,
service principals). It adds no new authorization mechanism — it configures the
existing kernel policy with procurement grants and exposes the resulting
``EvidenceAccessPolicy`` for the composition root to inject into the kernel
services.
"""

from __future__ import annotations

from ugence_decision_authority.api.policy import (
    AccessGrant,
    EvidenceAccessPolicy,
    GrantStore,
    Permission,
)


class ProcurementPolicyAdapter:
    """Builds and holds the kernel access policy for procurement principals."""

    def __init__(self) -> None:
        self._grants = GrantStore()
        self._policy = EvidenceAccessPolicy(self._grants)

    @property
    def policy(self) -> EvidenceAccessPolicy:
        return self._policy

    @property
    def grants(self) -> GrantStore:
        return self._grants

    def grant_all(self, principal_id: str, tenant_id: str) -> None:
        """Grant a principal every procurement permission within a tenant."""
        self._grants.add(AccessGrant(principal_id, tenant_id, frozenset(Permission)))

    def grant(self, principal_id: str, tenant_id: str,
              permissions: frozenset[Permission]) -> None:
        self._grants.add(AccessGrant(principal_id, tenant_id, permissions))
