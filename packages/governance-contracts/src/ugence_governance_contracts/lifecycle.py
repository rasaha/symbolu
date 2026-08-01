"""Provider lifecycle — deterministic state machine, separate from DGM records.

Provider lifecycle governs the *availability* of a governance capability; it is
entirely distinct from DGM business-record lifecycles (cases, actions,
executions). No background threads are used.
"""

from __future__ import annotations

from enum import Enum

from .errors import ProviderError


class ProviderLifecycleState(str, Enum):
    REGISTERED = "REGISTERED"
    INITIALIZING = "INITIALIZING"
    AVAILABLE = "AVAILABLE"
    DEGRADED = "DEGRADED"
    UNAVAILABLE = "UNAVAILABLE"
    STOPPING = "STOPPING"
    STOPPED = "STOPPED"


#: Legal transitions. A provider may go DEGRADED↔AVAILABLE, fail to UNAVAILABLE,
#: and always be stopped.
_ALLOWED: dict[ProviderLifecycleState, frozenset[ProviderLifecycleState]] = {
    ProviderLifecycleState.REGISTERED: frozenset({
        ProviderLifecycleState.INITIALIZING, ProviderLifecycleState.STOPPING}),
    ProviderLifecycleState.INITIALIZING: frozenset({
        ProviderLifecycleState.AVAILABLE, ProviderLifecycleState.UNAVAILABLE,
        ProviderLifecycleState.STOPPING}),
    ProviderLifecycleState.AVAILABLE: frozenset({
        ProviderLifecycleState.DEGRADED, ProviderLifecycleState.UNAVAILABLE,
        ProviderLifecycleState.STOPPING}),
    ProviderLifecycleState.DEGRADED: frozenset({
        ProviderLifecycleState.AVAILABLE, ProviderLifecycleState.UNAVAILABLE,
        ProviderLifecycleState.STOPPING}),
    ProviderLifecycleState.UNAVAILABLE: frozenset({
        ProviderLifecycleState.INITIALIZING, ProviderLifecycleState.STOPPING}),
    ProviderLifecycleState.STOPPING: frozenset({ProviderLifecycleState.STOPPED}),
    ProviderLifecycleState.STOPPED: frozenset(),
}


def is_legal_transition(current: ProviderLifecycleState,
                        target: ProviderLifecycleState) -> bool:
    return target in _ALLOWED.get(current, frozenset())


def assert_transition(current: ProviderLifecycleState,
                      target: ProviderLifecycleState) -> None:
    if not is_legal_transition(current, target):
        raise ProviderError(
            f"illegal provider lifecycle transition {current.value} -> {target.value}")
