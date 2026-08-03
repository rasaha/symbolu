"""Append/read-only repository for hiring domain audit events (H1).

Deliberately exposes no update or delete — the domain audit trail is immutable.
The in-memory adapter preserves append order and indexes by (entity_type,
entity_id) so a per-entity chain can be reconstructed and verified.
"""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from .event import HiringDomainAuditEvent


@runtime_checkable
class HiringDomainAuditRepository(Protocol):
    def append(self, event: HiringDomainAuditEvent) -> HiringDomainAuditEvent: ...
    def events_for(self, entity_type: str, entity_id: str) -> tuple[HiringDomainAuditEvent, ...]: ...
    def all_events(self) -> tuple[HiringDomainAuditEvent, ...]: ...


class InMemoryHiringDomainAuditRepository:
    """Reference append/read-only in-memory domain audit store."""

    def __init__(self) -> None:
        self._events: list[HiringDomainAuditEvent] = []
        self._by_entity: dict[tuple[str, str], list[HiringDomainAuditEvent]] = {}

    def append(self, event: HiringDomainAuditEvent) -> HiringDomainAuditEvent:
        self._events.append(event)
        self._by_entity.setdefault((event.entity_type, event.entity_id), []).append(event)
        return event

    def events_for(self, entity_type: str, entity_id: str) -> tuple[HiringDomainAuditEvent, ...]:
        return tuple(self._by_entity.get((entity_type, entity_id), ()))

    def all_events(self) -> tuple[HiringDomainAuditEvent, ...]:
        return tuple(self._events)

    def last_hash_for(self, entity_type: str, entity_id: str) -> str:
        """The ``event_hash`` of the most recent event for an entity ('' if none)."""
        chain = self._by_entity.get((entity_type, entity_id), ())
        return chain[-1].event_hash if chain else ""
