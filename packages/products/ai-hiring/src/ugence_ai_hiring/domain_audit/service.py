"""Hiring domain audit service (H1).

Standardizes creation of hiring-owned domain audit events: assigns event ids and
timestamps, computes the deterministic payload hash, and maintains a per-entity
tamper-evident hash chain (``previous_event_hash`` → ``event_hash``). All hiring
product services record through this service so the domain audit format stays
uniform and reconstructable.

Hiring-owned and additive — it never touches the frozen kernel audit surface.
"""

from __future__ import annotations

from typing import Any, Callable, Mapping, Optional

from ugence_decision_authority.api.common import canonical_hash, new_id, utc_now
from ugence_decision_authority.api.identity import ActorType

from .event import HiringDomainAuditEvent
from .events import HiringDomainEventType
from .repository import InMemoryHiringDomainAuditRepository


class HiringDomainAuditService:
    def __init__(
        self,
        repository: InMemoryHiringDomainAuditRepository,
        *,
        id_factory: Callable[[str], str] = new_id,
        clock: Callable[[], Any] = utc_now,
    ) -> None:
        self._repo = repository
        self._new_id = id_factory
        self._clock = clock

    def record(
        self,
        *,
        event_type: HiringDomainEventType,
        entity_type: str,
        entity_id: str,
        tenant_id: str,
        actor_id: str,
        actor_type: ActorType,
        previous_state: Optional[str] = None,
        new_state: Optional[str] = None,
        payload: Optional[Mapping[str, Any]] = None,
        correlation_id: str = "",
        causation_id: str = "",
        entity_version: int = 0,
    ) -> HiringDomainAuditEvent:
        """Create, chain, persist, and return one append-only domain audit event."""
        previous_event_hash = self._repo.last_hash_for(entity_type, entity_id)
        event = HiringDomainAuditEvent(
            event_id=self._new_id("hde"),
            event_type=event_type,
            entity_type=entity_type,
            entity_id=entity_id,
            tenant_id=tenant_id,
            actor_id=actor_id,
            actor_type=actor_type,
            timestamp=self._clock(),
            previous_state=previous_state,
            new_state=new_state,
            payload_hash=canonical_hash(dict(payload or {})),
            previous_event_hash=previous_event_hash,
            correlation_id=correlation_id,
            causation_id=causation_id,
            entity_version=entity_version,
        ).with_hash()
        return self._repo.append(event)

    def record_denial(
        self,
        *,
        entity_type: str,
        entity_id: str,
        tenant_id: str,
        actor_id: str,
        actor_type: ActorType,
        reason: str,
        correlation_id: str = "",
    ) -> HiringDomainAuditEvent:
        """Record a denied domain access / boundary rejection."""
        return self.record(
            event_type=HiringDomainEventType.DOMAIN_ACCESS_DENIED,
            entity_type=entity_type,
            entity_id=entity_id,
            tenant_id=tenant_id,
            actor_id=actor_id,
            actor_type=actor_type,
            payload={"reason": reason, "denied": "true"},
            correlation_id=correlation_id,
        )
