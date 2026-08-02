"""Deterministic timeout accounting via an injected clock.

The runtime does not spawn timers or read the system clock directly. It measures
elapsed logical time using the ``clock`` callable supplied on the configuration
(default: a monotonic stdlib clock). Injecting a deterministic clock in tests makes
timeout behavior fully reproducible.
"""
from __future__ import annotations

from typing import Callable


def exceeded(started_at: float, now: float, timeout: float) -> bool:
    """True when ``now - started_at`` has passed the ``timeout`` budget."""
    if timeout is None or timeout <= 0:
        return False
    return (now - started_at) > timeout


class TimeoutBudget:
    """A small helper that records a start mark from an injected clock and reports
    whether a timeout budget has since been exceeded."""

    def __init__(self, clock: Callable[[], float], timeout: float) -> None:
        self._clock = clock
        self._timeout = timeout
        self._started_at = clock()

    def exceeded(self) -> bool:
        return exceeded(self._started_at, self._clock(), self._timeout)
