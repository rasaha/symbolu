"""Kernel audit — immutable event contract, event catalog, sink port, service."""

from __future__ import annotations

from .event import AuditEvent
from .events import AuditEventType
from .namespace import (
    DOMAIN_EVENTS,
    KERNEL_EVENTS,
    LEGACY_EVENTS,
    AuditNamespace,
    audit_namespace,
    is_kernel_event,
)
from .repository import AuditRepository, InMemoryAuditRepository
from .service import AuditService

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
