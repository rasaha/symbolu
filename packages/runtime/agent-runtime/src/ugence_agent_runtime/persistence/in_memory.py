"""In-memory reference implementations of the persistence interfaces.

These are deterministic, dependency-free, and intended for tests, simulation, and
single-process use. They are NOT a durable backend. They round-trip checkpoints
through their serialized form so tests exercise the same (de)serialization a durable
backend would use.
"""
from __future__ import annotations

from typing import Dict, List, Optional

from ..models.events import RuntimeEvent
from .checkpoints import Checkpoint


class InMemoryCheckpointStore:
    def __init__(self) -> None:
        self._history: Dict[str, List[dict]] = {}

    def put(self, checkpoint: Checkpoint) -> None:
        self._history.setdefault(checkpoint.instance_id, []).append(checkpoint.to_dict())

    def latest(self, instance_id: str) -> Optional[Checkpoint]:
        history = self._history.get(instance_id)
        if not history:
            return None
        return Checkpoint.from_dict(history[-1])

    def history(self, instance_id: str) -> List[Checkpoint]:
        return [Checkpoint.from_dict(d) for d in self._history.get(instance_id, [])]


class InMemoryRuntimeStateStore:
    def __init__(self) -> None:
        self._latest: Dict[str, dict] = {}

    def save(self, checkpoint: Checkpoint) -> None:
        self._latest[checkpoint.instance_id] = checkpoint.to_dict()

    def load(self, instance_id: str) -> Optional[Checkpoint]:
        d = self._latest.get(instance_id)
        return Checkpoint.from_dict(d) if d is not None else None


class InMemoryRuntimeEventStore:
    def __init__(self) -> None:
        self._events: Dict[str, List[RuntimeEvent]] = {}

    def append(self, instance_id: str, event: RuntimeEvent) -> None:
        self._events.setdefault(instance_id, []).append(event)

    def events(self, instance_id: str) -> List[RuntimeEvent]:
        return list(self._events.get(instance_id, []))
