"""Read-only observation-source boundary for canonical capacity states.

An observation source turns a provider or monitoring system into a
:class:`~.state.CanonicalCapacityState`. The interface is deliberately **read-only**: it
exposes ``observe`` and nothing that could mutate infrastructure. No write-capable client
is reachable through it.

Phase 1 ships only low-risk, dependency-free sources:

* :class:`FixtureObservationSource` — returns a fixed, in-memory canonical state
  (fixtures / synthetic tests).
* :class:`ReplayObservationSource` — yields a supplied sequence of canonical states in
  order, preserving each state's caller-supplied timestamps and provenance.

Network-backed adapters (Prometheus, CloudWatch, Azure Monitor, GCP Monitoring, the
Kubernetes read APIs) are future work. Any such adapter must remain opt-in, read-only,
lazily imported, absent from the default core import path, free of credential
requirements at import time, and outside the decision kernel — mirroring the existing
read-only ``signals`` / ``shadow`` extras. This module adds no such dependency.
"""

from __future__ import annotations

from typing import Iterable, Iterator, List, Protocol, runtime_checkable

from .state import CanonicalCapacityState


@runtime_checkable
class CapacityObservationSource(Protocol):
    """Read-only source of canonical capacity observations.

    Implementations MUST NOT expose any write/mutation capability. ``observe`` returns
    the current canonical state; a source with no reading available should raise rather
    than fabricate one.
    """

    def observe(self) -> CanonicalCapacityState:
        ...


class FixtureObservationSource:
    """A source that returns a fixed canonical state. Read-only; no network, no I/O."""

    def __init__(self, state: CanonicalCapacityState):
        if not isinstance(state, CanonicalCapacityState):
            raise TypeError("state must be a CanonicalCapacityState")
        self._state = state

    def observe(self) -> CanonicalCapacityState:
        return self._state


class ReplayObservationSource:
    """A source that replays a supplied sequence of canonical states in order.

    Timestamps and provenance carried by each state are preserved exactly — replay never
    converts a recorded observation into a freshly-timestamped live one.
    """

    def __init__(self, states: Iterable[CanonicalCapacityState]):
        materialized: List[CanonicalCapacityState] = list(states)
        for s in materialized:
            if not isinstance(s, CanonicalCapacityState):
                raise TypeError("every replay item must be a CanonicalCapacityState")
        self._states = materialized
        self._cursor = 0

    def __len__(self) -> int:
        return len(self._states)

    def __iter__(self) -> Iterator[CanonicalCapacityState]:
        return iter(self._states)

    def observe(self) -> CanonicalCapacityState:
        """Return the next canonical state in the replay sequence (fail-closed at end)."""
        if self._cursor >= len(self._states):
            raise StopIteration("replay exhausted")
        state = self._states[self._cursor]
        self._cursor += 1
        return state

    def reset(self) -> None:
        self._cursor = 0


__all__ = [
    "CapacityObservationSource",
    "FixtureObservationSource",
    "ReplayObservationSource",
]
