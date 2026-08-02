"""Neutral, immutable runtime configuration.

Configuration wires the runtime's injected dependencies (provider registry,
governance hook, clock, id generator, event sink) and its neutral policies
(concurrency, timeout, retry). It contains NO credentials, NO product policy, NO
governance decisions, and NO backend-specific data.

Constructing a config performs no I/O and starts nothing. Defaults are pure and
dependency-free so ``AgentRuntimeConfig()`` is safe to build at any time.
"""
from __future__ import annotations

import itertools
import time
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Callable, Optional

from .governance.interfaces import GovernanceHook
from .governance.noop import NoopGovernanceHook
from .providers.registry import ProviderRegistry
from .runtime.errors import RuntimeConfigurationError
from .runtime.retry import RetryPolicy

if TYPE_CHECKING:  # pragma: no cover - annotations only, avoids an import cycle
    from .persistence.interfaces import (
        CheckpointStore,
        RuntimeEventStore,
        RuntimeStateStore,
    )


def _default_clock() -> float:
    # Monotonic logical clock; only read when a timeout is configured.
    return time.monotonic()


class _SequentialIdGenerator:
    """Deterministic, side-effect-free id generator (no randomness, no wall clock)."""

    def __init__(self, prefix: str = "id") -> None:
        self._prefix = prefix
        self._counter = itertools.count(1)

    def __call__(self) -> str:
        return f"{self._prefix}-{next(self._counter)}"


@dataclass(frozen=True)
class AgentRuntimeConfig:
    runtime_id: str = "agent-runtime"
    runtime_version: str = "0.1.0"
    max_concurrent_tasks: int = 1
    default_timeout: Optional[float] = None
    retry_policy: RetryPolicy = field(default_factory=RetryPolicy)
    provider_registry: ProviderRegistry = field(default_factory=ProviderRegistry)
    governance_hook: GovernanceHook = field(default_factory=NoopGovernanceHook)
    checkpoint_store: Optional[CheckpointStore] = None
    state_store: Optional[RuntimeStateStore] = None
    event_store: Optional[RuntimeEventStore] = None
    event_sink: Optional[Callable] = None
    clock: Callable[[], float] = _default_clock
    id_generator: Callable[[], str] = field(
        default_factory=lambda: _SequentialIdGenerator("wf")
    )

    def __post_init__(self) -> None:
        if not self.runtime_id:
            raise RuntimeConfigurationError("runtime_id required")
        # Reject unbounded concurrency: the runtime supports bounded concurrency,
        # so a non-positive bound is a configuration error.
        if self.max_concurrent_tasks < 1:
            raise RuntimeConfigurationError(
                "max_concurrent_tasks must be >= 1 (unbounded concurrency is rejected)"
            )
        if self.default_timeout is not None and self.default_timeout <= 0:
            raise RuntimeConfigurationError("default_timeout must be positive when set")
