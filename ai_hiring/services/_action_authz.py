"""Shared authorization + audit helper for the Phase-4B action-request services.

Repository access confers no authority: every action-request mutation authenticates
the principal and consults the grant-based access policy. Having created the
underlying decision grants no automatic action-request privilege. Denials are
audited as ``ACTION_REQUEST_ACCESS_DENIED`` and raise a typed error.
"""

from __future__ import annotations

from typing import Optional

from ..domain.enums import ActorType, AuditEventType
from ..errors import ActionRequestAuthorizationError
from ..policies.decision_boundary import IdentityProvider
from ..policies.evidence_access_policy import (
    AccessRequest,
    EvidenceAccessPolicy,
    Permission,
)
from .audit_service import AuditService


def authorize_action(
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
    """Authenticate + authorize an action-request operation, auditing on denial."""
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
            event_type=AuditEventType.ACTION_REQUEST_ACCESS_DENIED,
            entity_type="action_request", entity_id=entity_id or (tenant_id or "unknown"),
            actor_type=identity.actor_type, actor_id=actor,
            correlation_id=correlation_id,
            payload={"operation": permission.value, "reason": denied})
        raise ActionRequestAuthorizationError(
            f"actor '{actor}' not authorized for {permission.value}: {denied}")
    return identity.actor_type
