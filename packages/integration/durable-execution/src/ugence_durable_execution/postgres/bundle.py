"""Store bundles, and the posture flag that separates a durable one from a reference one.

The bundle exists so a composition root cannot mix a durable checkpoint store with an
in-memory event store — a combination that passes every functional test and then loses
the events on restart.
"""
from __future__ import annotations

from typing import Any, Callable

from .budgets import PostgresBudgetLedger
from .stores import (
    PostgresCheckpointStore,
    PostgresRuntimeEventStore,
    PostgresRuntimeStateStore,
)

__all__ = ["PostgresStoreBundle", "InMemoryReferenceBundle"]


class PostgresStoreBundle:
    """The durable bundle. All four stores share one session provider, hence one
    transaction (ADR §5.4, OD-1)."""

    def __init__(
        self,
        session_provider: Callable[[], Any],
        *,
        engine_id: str,
        definition_digest: str = "",
    ) -> None:
        self._checkpoint = PostgresCheckpointStore(session_provider)
        self._events = PostgresRuntimeEventStore(session_provider, engine_id=engine_id)
        self._state = PostgresRuntimeStateStore(
            session_provider, engine_id=engine_id, definition_digest=definition_digest
        )
        self._budgets = PostgresBudgetLedger(session_provider)

    @property
    def checkpoint_store(self) -> PostgresCheckpointStore:
        return self._checkpoint

    @property
    def event_store(self) -> PostgresRuntimeEventStore:
        return self._events

    @property
    def state_store(self) -> PostgresRuntimeStateStore:
        return self._state

    @property
    def budget_ledger(self) -> PostgresBudgetLedger:
        return self._budgets

    @property
    def is_production_authoritative(self) -> bool:
        """True: durable, integrity-checked, and shared across processes."""
        return True


class InMemoryReferenceBundle:
    """Agent Runtime's in-memory reference stores, bundled.

    Useful for a single-process run. ``is_production_authoritative`` is **permanently
    False** — a production composition root refuses it, and no configuration flips it.
    """

    def __init__(self) -> None:
        from ugence_agent_runtime.persistence.in_memory import (
            InMemoryCheckpointStore,
            InMemoryRuntimeEventStore,
            InMemoryRuntimeStateStore,
        )

        self._checkpoint = InMemoryCheckpointStore()
        self._events = InMemoryRuntimeEventStore()
        self._state = InMemoryRuntimeStateStore()

    @property
    def checkpoint_store(self) -> Any:
        return self._checkpoint

    @property
    def event_store(self) -> Any:
        return self._events

    @property
    def state_store(self) -> Any:
        return self._state

    @property
    def is_production_authoritative(self) -> bool:
        return False
