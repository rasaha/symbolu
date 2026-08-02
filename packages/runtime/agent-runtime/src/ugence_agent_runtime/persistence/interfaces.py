"""Optional persistence interfaces.

The runtime owns the *interfaces*; it does not own a durable backend. The core ships
only an in-memory reference implementation (``in_memory``). Product deployments
supply durable implementations (SQL, KV, event store) externally — the runtime core
never imports a persistence backend and never depends on a governance product's
persistence.
"""
from __future__ import annotations

from typing import List, Optional, Protocol, runtime_checkable

from ..models.events import RuntimeEvent
from .checkpoints import Checkpoint


@runtime_checkable
class CheckpointStore(Protocol):
    def put(self, checkpoint: Checkpoint) -> None:
        ...

    def latest(self, instance_id: str) -> Optional[Checkpoint]:
        ...


@runtime_checkable
class RuntimeEventStore(Protocol):
    def append(self, instance_id: str, event: RuntimeEvent) -> None:
        ...

    def events(self, instance_id: str) -> List[RuntimeEvent]:
        ...


@runtime_checkable
class RuntimeStateStore(Protocol):
    """Persists the latest full checkpoint per instance for recovery.

    Kept separate from ``CheckpointStore`` so a deployment may retain a checkpoint
    history in one place and only the resume-point snapshot in another. The
    in-memory reference backs both with the same store.
    """

    def save(self, checkpoint: Checkpoint) -> None:
        ...

    def load(self, instance_id: str) -> Optional[Checkpoint]:
        ...
