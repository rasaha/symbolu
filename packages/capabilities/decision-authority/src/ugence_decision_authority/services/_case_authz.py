"""Shared authorization + audit helpers for the Phase-4A case services.

Repository access confers no authority: every case mutation authenticates the
principal and consults the grant-based access policy. Denials are audited as
``DECISION_CASE_ACCESS_DENIED`` and raise a typed error. Kept in one place so the
three case services enforce it identically.
"""

from __future__ import annotations

from typing import Optional

from ..identity.actor import ActorType
from ..audit.events import AuditEventType
from ..errors import DecisionCaseAuthorizationError
from ..identity import IdentityProvider
from ..policy import (
    AccessRequest,
    EvidenceAccessPolicy,
    Permission,
)
from ..audit import AuditService


def authorize_case_action(
    identity_provider: IdentityProvider,
    access_policy: EvidenceAccessPolicy,
    audit_service: AuditService,
    *,
    actor: str,
    permission: Permission,
    tenant_id: str,
    subject_id: Optional[str],
    correlation_id: str,
    entity_id: str,
) -> ActorType:
    """Authenticate + authorize a case action, auditing and raising on denial."""
    identity = identity_provider.authenticate(actor)
    denied: Optional[str] = None
    if not identity.authenticated:
        denied = "unauthenticated"
    else:
        decision = access_policy.authorize(AccessRequest(
            principal_id=actor, tenant_id=tenant_id, operation=permission,
            candidate_id=subject_id))
        if not decision.allowed:
            denied = decision.reason
    if denied is not None:
        audit_service.record(
            event_type=AuditEventType.DECISION_CASE_ACCESS_DENIED,
            entity_type="decision_case", entity_id=entity_id or (tenant_id or "unknown"),
            actor_type=identity.actor_type, actor_id=actor,
            correlation_id=correlation_id,
            payload={"operation": permission.value, "reason": denied})
        raise DecisionCaseAuthorizationError(
            f"actor '{actor}' not authorized for {permission.value}: {denied}")
    return identity.actor_type
