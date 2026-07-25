"""Shared authorization + audit helper for the Phase-4C execution services.

Repository access confers no authority: every execution operation authenticates the
principal and consults the grant-based access policy. Having authorized the action
request (Phase 4B) or made the decision (Phase 4A) grants **no** automatic dispatch
privilege. Denials are audited as ``EXECUTION_ACCESS_DENIED`` and raise a typed
error.
"""

from __future__ import annotations

from typing import Optional

from ..identity.actor import ActorType
from ..audit.events import AuditEventType
from ..errors import ExecutionAuthorizationError
from ..identity import IdentityProvider
from ..policy import (
    AccessRequest,
    EvidenceAccessPolicy,
    Permission,
)
from ..audit import AuditService


def authorize_execution(
    identity_provider: IdentityProvider,
    access_policy: EvidenceAccessPolicy,
    audit_service: AuditService,
    *,
    actor: str,
    permission: Permission,
    tenant_id: str,
    correlation_id: str,
    entity_id: str,
) -> ActorType:
    """Authenticate + authorize an execution operation, auditing on denial."""
    identity = identity_provider.authenticate(actor)
    denied: Optional[str] = None
    if not identity.authenticated:
        denied = "unauthenticated"
    else:
        decision = access_policy.authorize(AccessRequest(
            principal_id=actor, tenant_id=tenant_id, operation=permission))
        if not decision.allowed:
            denied = decision.reason
    if denied is not None:
        audit_service.record(
            event_type=AuditEventType.EXECUTION_ACCESS_DENIED,
            entity_type="execution", entity_id=entity_id or (tenant_id or "unknown"),
            actor_type=identity.actor_type, actor_id=actor,
            correlation_id=correlation_id,
            payload={"operation": permission.value, "reason": denied})
        raise ExecutionAuthorizationError(
            f"actor '{actor}' not authorized for {permission.value}: {denied}")
    return identity.actor_type
