"""Exceptions raised by the safety state machine.

Two layers:

* :class:`SafetyStateMachineError` — base class. A buyer's error
  handler can ``except SafetyStateMachineError`` to catch every
  state-machine-specific failure without catching unrelated
  ``ValueError`` / ``RuntimeError`` slips.
* :class:`IllegalTransitionError` — subclass raised when a
  transition is attempted that the §6 direct-jump prohibition
  forbids. The error names the offending ``(from_state, to_state)``
  pair so a debug reader can find the bug without grepping the
  legal-edge table.

The base class is the one a downstream caller catches; the
subclass is the one the test suite asserts on.
"""

from __future__ import annotations


class SafetyStateMachineError(Exception):
    """Base class for safety-state-machine errors."""


class IllegalTransitionError(SafetyStateMachineError):
    """Raised when a transition is attempted that violates the §6
    direct-jump prohibition.

    The legal-edge table in :mod:`safety_state.state` enumerates
    the six allowed transitions. Any ``(from_state, to_state)`` pair
    not in that table raises this error rather than silently
    transitioning. See ``SAFETY_STATE_MACHINE_DESIGN.md`` §6 for
    the rationale.
    """

    def __init__(self, from_state, to_state, reason: str = "") -> None:
        msg = (
            f"illegal safety-state transition: "
            f"{getattr(from_state, 'name', from_state)} → "
            f"{getattr(to_state, 'name', to_state)}"
        )
        if reason:
            msg += f" ({reason})"
        msg += (
            " — direct jumps prohibited by SAFETY_STATE_MACHINE_DESIGN.md "
            "§6; the machine must walk through DEGRADED"
        )
        super().__init__(msg)
        self.from_state = from_state
        self.to_state = to_state
        self.reason = reason
