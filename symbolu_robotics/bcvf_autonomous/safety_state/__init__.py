"""Functional-safety state machine package.

Public surface (provisional, see ``API_STABILITY.md`` §2.2 +
``SAFETY_STATE_MACHINE_DESIGN.md`` §9):

* :class:`SafetyState` — four-state enum (NORMAL / DEGRADED /
  FAULT / FAILSAFE).
* :class:`SafetyStateMachine` — the state machine itself.
* :class:`SafetyStateMachineConfig` — calibration knobs.
* :class:`StateTransition` — one row of the legal-edge table.
* :class:`StateTransitionLog` / :class:`StateTransitionLogEntry`
  — append-only transition audit log.
* :class:`TickView` / :class:`RollingWindow` /
  :class:`TriggerCondition` — the trigger primitives.
* :class:`SafetyStateMachineError` /
  :class:`IllegalTransitionError` — exception hierarchy.
* :data:`LEGAL_TRANSITIONS` — the six-edge legal-transition tuple.

See ``SAFETY_STATE_MACHINE_DESIGN.md`` for the full design.
"""

from .errors import IllegalTransitionError, SafetyStateMachineError
from .machine import (
    SafetyStateMachine,
    SafetyStateMachineConfig,
    StateTransitionLog,
    StateTransitionLogEntry,
)
from .state import (
    LEGAL_TRANSITIONS,
    SafetyState,
    StateTransition,
    is_legal_transition,
    legal_target_states,
    lookup_transition,
)
from .triggers import (
    RollingWindow,
    TickView,
    TriggerCondition,
    tick_views_from_record,
)


__all__ = [
    # state
    "SafetyState",
    "StateTransition",
    "LEGAL_TRANSITIONS",
    "is_legal_transition",
    "legal_target_states",
    "lookup_transition",
    # triggers
    "RollingWindow",
    "TickView",
    "TriggerCondition",
    "tick_views_from_record",
    # machine
    "SafetyStateMachine",
    "SafetyStateMachineConfig",
    "StateTransitionLog",
    "StateTransitionLogEntry",
    # errors
    "SafetyStateMachineError",
    "IllegalTransitionError",
]
