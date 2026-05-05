"""Safety states + the legal-transition table.

This module is intentionally pure data — no side effects, no I/O,
no state. Anyone walking the codebase to understand the four-state
contract should be able to read this file in isolation and have
the full state graph: the four states, the six legal edges, and
the ASIL classification per edge.

The :data:`LEGAL_TRANSITIONS` tuple is the single source of truth
for which ``(from_state, to_state)`` pairs the machine permits;
:func:`is_legal_transition` and :func:`legal_target_states` are
read-only helpers that walk it.

See ``SAFETY_STATE_MACHINE_DESIGN.md`` §2 for the rendered
diagram and §5 for the ASIL decomposition.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Tuple


class SafetyState(str, Enum):
    """The four named safety states.

    String-valued so equality checks are stable across module
    reloads (a comparison ``record["state"] == SafetyState.NORMAL``
    works against both a serialized JSON string and a live enum).
    """

    NORMAL = "NORMAL"
    DEGRADED = "DEGRADED"
    FAULT = "FAULT"
    FAILSAFE = "FAILSAFE"


# Trigger names — referenced from the legal-edge table and from
# the state-machine's per-tick dispatch logic. Centralised so a
# rename surfaces as a search-and-replace target rather than as a
# silent string mismatch.
TRIGGER_NEAR_VETO_RATE = "near_veto_rate"
TRIGGER_SUSTAINED_RECOVERY = "sustained_recovery"
TRIGGER_EXCLUSION_SUSTAINED = "exclusion_sustained"
TRIGGER_MULTI_PREDICTOR_EXCLUDED = "multi_predictor_excluded"
TRIGGER_MANUAL_RESET = "manual_reset"


@dataclass(frozen=True)
class StateTransition:
    """One legal edge of the state graph.

    The tuple ``(from_state, to_state, trigger, asil)`` is the
    auditor-readable row of the §5 ASIL decomposition table.
    Pinned by the test suite — a future refactor that adds an
    edge without updating the test count fails the suite.
    """

    from_state: SafetyState
    to_state: SafetyState
    trigger: str
    asil: str

    def __post_init__(self) -> None:
        if self.asil not in ("ASIL-B", "ASIL-D"):
            raise ValueError(
                f"asil must be 'ASIL-B' or 'ASIL-D'; got {self.asil!r}"
            )


# The six legal edges. Order matches the §5 ASIL-decomposition
# table top-to-bottom so a diff against the doc is readable.
LEGAL_TRANSITIONS: Tuple[StateTransition, ...] = (
    StateTransition(
        from_state=SafetyState.NORMAL,
        to_state=SafetyState.DEGRADED,
        trigger=TRIGGER_NEAR_VETO_RATE,
        asil="ASIL-B",
    ),
    StateTransition(
        from_state=SafetyState.DEGRADED,
        to_state=SafetyState.NORMAL,
        trigger=TRIGGER_SUSTAINED_RECOVERY,
        asil="ASIL-B",
    ),
    StateTransition(
        from_state=SafetyState.DEGRADED,
        to_state=SafetyState.FAULT,
        trigger=TRIGGER_EXCLUSION_SUSTAINED,
        asil="ASIL-D",
    ),
    StateTransition(
        from_state=SafetyState.FAULT,
        to_state=SafetyState.FAILSAFE,
        trigger=TRIGGER_MULTI_PREDICTOR_EXCLUDED,
        asil="ASIL-D",
    ),
    StateTransition(
        from_state=SafetyState.FAULT,
        to_state=SafetyState.DEGRADED,
        trigger=TRIGGER_MANUAL_RESET,
        asil="ASIL-B",
    ),
    StateTransition(
        from_state=SafetyState.FAILSAFE,
        to_state=SafetyState.FAULT,
        trigger=TRIGGER_MANUAL_RESET,
        asil="ASIL-B",
    ),
)


def is_legal_transition(
    from_state: SafetyState, to_state: SafetyState
) -> bool:
    """``True`` if the ``(from_state, to_state)`` pair is in the
    legal-edge table. Self-transitions are not legal (the machine
    holds state without recording a transition)."""
    if from_state == to_state:
        return False
    return any(
        t.from_state == from_state and t.to_state == to_state
        for t in LEGAL_TRANSITIONS
    )


def legal_target_states(
    from_state: SafetyState,
) -> Tuple[SafetyState, ...]:
    """Tuple of states reachable from ``from_state`` in one
    transition. Used by the per-tick dispatch logic to know which
    targets to evaluate triggers for."""
    return tuple(
        t.to_state
        for t in LEGAL_TRANSITIONS
        if t.from_state == from_state
    )


def lookup_transition(
    from_state: SafetyState, to_state: SafetyState
) -> StateTransition:
    """Return the :class:`StateTransition` for the given pair, or
    raise :class:`KeyError` if the edge isn't legal. Used by the
    machine when it has already decided to transition and needs to
    look up the trigger / ASIL metadata for the log entry."""
    for t in LEGAL_TRANSITIONS:
        if t.from_state == from_state and t.to_state == to_state:
            return t
    raise KeyError(
        f"no legal transition from {from_state.name} to {to_state.name}"
    )
