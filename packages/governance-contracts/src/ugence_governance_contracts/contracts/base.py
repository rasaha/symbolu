"""Common provider surface — identity + deterministic lifecycle.

Every provider (assertion, action, execution) exposes a descriptor and a
lifecycle. The concrete :class:`BaseProvider` handles deterministic state
transitions; structural typing means subclassing is optional.
"""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from ..lifecycle import ProviderLifecycleState, assert_transition
from ..metadata import ProviderDescriptor, ProviderHealth


@runtime_checkable
class Provider(Protocol):
    """Identity + lifecycle common to every provider kind."""

    def descriptor(self) -> ProviderDescriptor: ...
    def initialize(self) -> None: ...
    def health(self) -> ProviderHealth: ...
    def shutdown(self) -> None: ...


class BaseProvider:
    """Concrete lifecycle bookkeeping shared by reference and real providers."""

    def __init__(self, descriptor: ProviderDescriptor) -> None:
        self._descriptor = descriptor
        self._state = ProviderLifecycleState.REGISTERED

    def descriptor(self) -> ProviderDescriptor:
        return self._descriptor

    @property
    def state(self) -> ProviderLifecycleState:
        return self._state

    def _transition(self, target: ProviderLifecycleState) -> None:
        assert_transition(self._state, target)
        self._state = target

    def initialize(self) -> None:
        self._transition(ProviderLifecycleState.INITIALIZING)
        self._transition(ProviderLifecycleState.AVAILABLE)

    def degrade(self, detail: str = "") -> None:
        self._transition(ProviderLifecycleState.DEGRADED)

    def mark_unavailable(self, detail: str = "") -> None:
        self._transition(ProviderLifecycleState.UNAVAILABLE)

    def shutdown(self) -> None:
        if self._state is not ProviderLifecycleState.STOPPED:
            self._transition(ProviderLifecycleState.STOPPING)
            self._transition(ProviderLifecycleState.STOPPED)

    def health(self) -> ProviderHealth:
        healthy = self._state in (ProviderLifecycleState.AVAILABLE,
                                  ProviderLifecycleState.DEGRADED)
        return ProviderHealth(state=self._state, healthy=healthy, detail=self._state.value)
