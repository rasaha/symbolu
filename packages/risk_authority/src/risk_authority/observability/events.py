"""An in-process governance-event bus.

Every state-changing operation emits a :class:`GovernanceEvent`; the bus fans
those out to subscribers (an audit store, metrics, a downstream GRC export)
without the emitting service knowing the consumers. Auditability is present
from day one (user brief §23), not bolted on later.
"""

from __future__ import annotations

from typing import Callable

from ..domain.events import GovernanceEvent

__all__ = ["EventBus"]

Subscriber = Callable[[GovernanceEvent], None]


class EventBus:
    def __init__(self) -> None:
        self._subscribers: list[Subscriber] = []
        self._log: list[GovernanceEvent] = []

    def subscribe(self, subscriber: Subscriber) -> None:
        self._subscribers.append(subscriber)

    def publish(self, event: GovernanceEvent) -> GovernanceEvent:
        self._log.append(event)
        for subscriber in self._subscribers:
            subscriber(event)
        return event

    @property
    def log(self) -> tuple[GovernanceEvent, ...]:
        return tuple(self._log)
