"""Append-only audit repository — the kernel's audit-event storage port + sink.

The port exposes append/read only (no update or delete by construction). The
in-memory sink is a deterministic reference implementation for development and
tests. Applications may inject a durable sink implementing the same port.
"""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from .event import AuditEvent


@runtime_checkable
class AuditRepository(Protocol):
    def append(self, event: AuditEvent) -> AuditEvent: ...
    def list_by_entity(self, entity_id: str) -> tuple[AuditEvent, ...]: ...
    def list_by_correlation(self, correlation_id: str) -> tuple[AuditEvent, ...]: ...
    def all(self) -> tuple[AuditEvent, ...]: ...


class InMemoryAuditRepository:
    """Strictly append/read-only audit log.

    There is no update or delete operation by construction — the only mutation
    is :meth:`append`.
    """

    def __init__(self) -> None:
        self._events: list[AuditEvent] = []

    def append(self, event: AuditEvent) -> AuditEvent:
        self._events.append(event)
        return event

    def list_by_entity(self, entity_id: str) -> tuple[AuditEvent, ...]:
        return tuple(
            sorted(
                (e for e in self._events if e.entity_id == entity_id),
                key=lambda e: (e.timestamp, self._events.index(e)),
            )
        )

    def list_by_correlation(self, correlation_id: str) -> tuple[AuditEvent, ...]:
        return tuple(
            sorted(
                (e for e in self._events if e.correlation_id == correlation_id),
                key=lambda e: (e.timestamp, self._events.index(e)),
            )
        )

    def all(self) -> tuple[AuditEvent, ...]:
        return tuple(self._events)
