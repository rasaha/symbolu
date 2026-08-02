"""Optional persistence interfaces and an in-memory reference implementation."""
from __future__ import annotations

from .checkpoints import Checkpoint
from .in_memory import (
    InMemoryCheckpointStore,
    InMemoryRuntimeEventStore,
    InMemoryRuntimeStateStore,
)
from .interfaces import CheckpointStore, RuntimeEventStore, RuntimeStateStore
from .recovery import RuntimeRecoveryResult, recover_instance

__all__ = [
    "Checkpoint",
    "CheckpointStore",
    "RuntimeEventStore",
    "RuntimeStateStore",
    "InMemoryCheckpointStore",
    "InMemoryRuntimeEventStore",
    "InMemoryRuntimeStateStore",
    "RuntimeRecoveryResult",
    "recover_instance",
]
