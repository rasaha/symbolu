"""Audit service.

Standardizes audit-event creation: assigns event ids, timestamps, and a
deterministic payload hash, and preserves correlation/causation chaining. All
other services record through this service so the audit format stays uniform.
"""

from __future__ import annotations

from typing import Any, Mapping, Optional

from ..common import Clock, IdFactory, canonical_hash, new_id, utc_now
from .event import AuditEvent
from ..identity.actor import ActorType
from .events import AuditEventType
from .repository import AuditRepository


class AuditService:
    def __init__(
        self,
        repository: AuditRepository,
        *,
        id_factory: IdFactory = new_id,
        clock: Clock = utc_now,
    ) -> None:
        self._repo = repository
        self._new_id = id_factory
        self._clock = clock

    def record(
        self,
        *,
        event_type: AuditEventType,
        entity_type: str,
        entity_id: str,
        actor_type: ActorType,
        correlation_id: str,
        actor_id: Optional[str] = None,
        previous_state: Optional[str] = None,
        new_state: Optional[str] = None,
        payload: Optional[Mapping[str, Any]] = None,
        causation_id: Optional[str] = None,
        metadata: Optional[Mapping[str, str]] = None,
    ) -> AuditEvent:
        """Create, persist, and return one append-only audit event."""
        event = AuditEvent(
            event_id=self._new_id("evt"),
            event_type=event_type,
            entity_type=entity_type,
            entity_id=entity_id,
            actor_type=actor_type,
            actor_id=actor_id,
            timestamp=self._clock(),
            previous_state=previous_state,
            new_state=new_state,
            payload_hash=canonical_hash(payload or {}),
            correlation_id=correlation_id,
            causation_id=causation_id,
            metadata=dict(metadata or {}),
        )
        return self._repo.append(event)

    def record_denial(
        self,
        *,
        entity_type: str,
        entity_id: str,
        actor_type: ActorType,
        correlation_id: str,
        reason: str,
        actor_id: Optional[str] = None,
        security: bool = False,
        causation_id: Optional[str] = None,
    ) -> AuditEvent:
        """Record a denied policy action (or a security violation)."""
        return self.record(
            event_type=(
                AuditEventType.SECURITY_VIOLATION
                if security
                else AuditEventType.POLICY_DENIED
            ),
            entity_type=entity_type,
            entity_id=entity_id,
            actor_type=actor_type,
            actor_id=actor_id,
            correlation_id=correlation_id,
            causation_id=causation_id,
            payload={"reason": reason},
            metadata={"denied": "true"},
        )

    # --- queries -----------------------------------------------------------
    def history(self, entity_id: str) -> tuple[AuditEvent, ...]:
        """Ordered audit history for a single entity."""
        return self._repo.list_by_entity(entity_id)

    def by_correlation(self, correlation_id: str) -> tuple[AuditEvent, ...]:
        """Ordered audit events sharing a correlation id (a request chain)."""
        return self._repo.list_by_correlation(correlation_id)

    def latest_for(self, entity_id: str) -> Optional[AuditEvent]:
        events = self._repo.list_by_entity(entity_id)
        return events[-1] if events else None
