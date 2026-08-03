"""Shared actor context + tenant guard for H1 hiring product services.

Every product operation runs under an :class:`ActorContext` (tenant + actor
identity). Cross-tenant access to a record is denied and recorded on the
hiring-owned domain audit trail. Structural product operations do not make binding
hiring decisions — those remain human-authored governance decisions in later
phases — so this layer never grants decision authority to any actor.
"""

from __future__ import annotations

from dataclasses import dataclass

from ugence_decision_authority.api.identity import ActorType

from ..domain_audit.service import HiringDomainAuditService
from ..errors import CrossTenantHiringAccessError


@dataclass(frozen=True)
class ActorContext:
    """Who is performing an operation, and in which tenant."""

    tenant_id: str
    actor_id: str
    actor_type: ActorType = ActorType.HUMAN

    def __post_init__(self) -> None:
        if not str(self.tenant_id).strip():
            raise CrossTenantHiringAccessError("tenant_id is required in ActorContext")
        if not str(self.actor_id).strip():
            raise CrossTenantHiringAccessError("actor_id is required in ActorContext")


def guard_tenant(
    ctx: ActorContext,
    *,
    record_tenant_id: str,
    entity_type: str,
    entity_id: str,
    audit: HiringDomainAuditService,
) -> None:
    """Raise + record a denial if the record is outside the caller's tenant."""
    if record_tenant_id != ctx.tenant_id:
        audit.record_denial(
            entity_type=entity_type, entity_id=entity_id, tenant_id=ctx.tenant_id,
            actor_id=ctx.actor_id, actor_type=ctx.actor_type,
            reason=f"cross_tenant_access:{entity_type}",
        )
        raise CrossTenantHiringAccessError(
            f"actor in tenant '{ctx.tenant_id}' may not access {entity_type} "
            f"'{entity_id}' in tenant '{record_tenant_id}'"
        )
