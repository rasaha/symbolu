"""Hiring-owned domain audit trail for H1 product entities.

Additive, application-local, and boundary-correct: AI Hiring owns the audit of
its product entities (requisitions, job definitions, candidates, applications,
evidence intake). The frozen kernel audit surface is untouched and reserved for
the governance chain (later phases).
"""

from __future__ import annotations

from .event import HiringDomainAuditEvent
from .events import DENIAL_EVENTS, HiringDomainEventType
from .repository import (
    HiringDomainAuditRepository,
    InMemoryHiringDomainAuditRepository,
)
from .service import HiringDomainAuditService

__all__ = [
    "HiringDomainEventType",
    "DENIAL_EVENTS",
    "HiringDomainAuditEvent",
    "HiringDomainAuditRepository",
    "InMemoryHiringDomainAuditRepository",
    "HiringDomainAuditService",
]
