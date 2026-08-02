"""Public API — audit event contract, catalog, namespace partition, service."""
from __future__ import annotations

from ..audit import (
    DOMAIN_EVENTS,
    KERNEL_EVENTS,
    LEGACY_EVENTS,
    AuditEvent,
    AuditEventType,
    AuditNamespace,
    AuditRepository,
    AuditService,
    InMemoryAuditRepository,
    audit_namespace,
    is_kernel_event,
)

__all__ = [
    "AuditEvent",
    "AuditEventType",
    "AuditNamespace",
    "audit_namespace",
    "is_kernel_event",
    "KERNEL_EVENTS",
    "LEGACY_EVENTS",
    "DOMAIN_EVENTS",
    "AuditRepository",
    "InMemoryAuditRepository",
    "AuditService",
]
