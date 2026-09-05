"""Clock discipline for durable deployments (ADR §6.4).

``AgentRuntimeConfig.clock`` defaults to ``time.monotonic`` (verified at
``packages/runtime/agent-runtime/src/ugence_agent_runtime/config.py:33-35``), and that
reading is what ``validate_clearance`` compares against a clearance's ``valid_until``
(``runtime/engine.py:547-548``).

``time.monotonic()`` is **process-local**. Its origin is arbitrary and differs between
processes, so after a crash and recovery in a new process a ``valid_until`` minted
before the crash is compared against an unrelated number. That is not an imprecise
comparison — it is a meaningless one, and it can read as *not yet expired* for an
arbitrarily long outage.

So a durable deployment injects a wall clock, and the production composition root
refuses the monotonic default. This module supplies the clock and the refusal. It
changes nothing in Agent Runtime: ``clock`` is already an injection point on a frozen
config dataclass.
"""
from __future__ import annotations

import time
from typing import Callable

from .errors import ClockDisciplineError

__all__ = ["wall_clock", "assert_durable_clock", "is_monotonic_clock"]

Clock = Callable[[], float]


def wall_clock() -> float:
    """Epoch seconds — comparable across processes, restarts and hosts.

    This is the only clock a durable deployment may give the runtime. It is the same
    time base a governance evaluator must mint ``valid_until`` on; the two being
    different bases is the skew condition ADR §8 row 11 tests.
    """
    return time.time()


def is_monotonic_clock(clock: Clock) -> bool:
    """True when ``clock`` is a process-local monotonic reading.

    Recognises ``time.monotonic`` itself and Agent Runtime's ``_default_clock``, which
    wraps it. Detection is deliberately conservative: anything it cannot positively
    identify as monotonic is allowed through, because this guard exists to catch the
    known default, not to police every callable a deployment might legitimately inject.
    A deployment that hides a monotonic reading behind an unrecognisable wrapper defeats
    the guard, and that residual is stated rather than papered over.
    """
    if clock is time.monotonic:
        return True
    # Agent Runtime's default is a module-level function whose body returns
    # time.monotonic(); match it by identity of its module and qualified name so we
    # never import the runtime's private config module just to compare.
    module = getattr(clock, "__module__", "")
    qualname = getattr(clock, "__qualname__", "")
    return (
        module == "ugence_agent_runtime.config" and qualname == "_default_clock"
    ) or qualname == "monotonic"


def assert_durable_clock(clock: Clock) -> None:
    """Refuse a process-local clock. Raises :class:`ClockDisciplineError`.

    Called by the production composition root at construction, so the refusal happens
    before any consequential call rather than at the first expiry comparison after a
    recovery — which is exactly when it would be too late to notice.
    """
    if is_monotonic_clock(clock):
        raise ClockDisciplineError(
            "a durable deployment must inject a wall clock (epoch seconds); "
            "the configured clock is process-local (time.monotonic), whose origin "
            "differs between processes, so a clearance's valid_until minted before a "
            "crash would be compared against an unrelated number after recovery. "
            "Pass ugence_durable_execution.clock.wall_clock."
        )
