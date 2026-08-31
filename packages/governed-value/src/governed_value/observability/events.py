"""An in-process governance-event bus.

Every scoring emits a :class:`~governed_value.domain.events.GovernedValueEvent`;
the bus fans it out to subscribers (an audit store, a metrics sink, a GRC
export) without the scorer knowing the consumers. Auditability is present from
day one, not bolted on later.
"""

from __future__ import annotations

from typing import Callable

from ..domain.events import GovernedValueEvent

__all__ = ["EventBus"]

Subscriber = Callable[[GovernedValueEvent], None]


class EventBus:
    def __init__(self) -> None:
        self._subscribers: list[Subscriber] = []
        self._log: list[GovernedValueEvent] = []

    def subscribe(self, subscriber: Subscriber) -> None:
        self._subscribers.append(subscriber)

    def publish(self, event: GovernedValueEvent) -> GovernedValueEvent:
        self._log.append(event)
        for subscriber in self._subscribers:
            subscriber(event)
        return event

    @property
    def log(self) -> tuple[GovernedValueEvent, ...]:
        return tuple(self._log)
