"""The incident lifecycle, and the containment state that is deliberately not part of it.

::

    OPEN -> CONTAINMENT_REQUESTED -> REMEDIATION_PROPOSED -> CLOSED
      |                                                       ^
      +-------------------------------------------------------+

Forward-only, like every other record machine in this repository: each transition
strictly increases :data:`STATE_RANK`, so any arrival order converges and a closed
incident never reopens. A new observation is a **new** incident.

**Containment is not a state of the incident.** It is requested by one record and
lifted by another, and neither is implied by the incident's own lifecycle. Closing
an incident does not lift containment, and a lifted containment does not close an
incident — the two are tracked apart precisely so that neither can be inferred from
the other. That is the ``PilotKillSwitchState`` rule
(``products/code-governance/.../pilot_operator/api.py:270``: clearing the switch
"does NOT restart the pilot") carried forward.
"""

from __future__ import annotations

from enum import Enum

from .errors import IllegalTransitionError

__all__ = [
    "IncidentState", "ContainmentState", "LEGAL_TRANSITIONS", "STATE_RANK",
    "TERMINAL_STATES", "OPEN_STATES", "is_legal_transition", "require_transition",
]


class IncidentState(str, Enum):
    """Where one incident stands. Exactly one applies."""

    OPEN = "OPEN"
    CONTAINMENT_REQUESTED = "CONTAINMENT_REQUESTED"
    REMEDIATION_PROPOSED = "REMEDIATION_PROPOSED"
    CLOSED = "CLOSED"


class ContainmentState(str, Enum):
    """Whether containment is currently asked for. Never inferred from the incident."""

    NONE = "NONE"
    REQUESTED = "REQUESTED"
    LIFTED = "LIFTED"


#: Forward-only ordering. Every legal transition strictly increases this rank.
STATE_RANK: dict[IncidentState, int] = {
    IncidentState.OPEN: 0,
    IncidentState.CONTAINMENT_REQUESTED: 1,
    IncidentState.REMEDIATION_PROPOSED: 2,
    IncidentState.CLOSED: 3,
}

LEGAL_TRANSITIONS: dict[IncidentState, frozenset[IncidentState]] = {
    IncidentState.OPEN: frozenset({
        IncidentState.CONTAINMENT_REQUESTED, IncidentState.REMEDIATION_PROPOSED,
        IncidentState.CLOSED}),
    IncidentState.CONTAINMENT_REQUESTED: frozenset({
        IncidentState.REMEDIATION_PROPOSED, IncidentState.CLOSED}),
    IncidentState.REMEDIATION_PROPOSED: frozenset({IncidentState.CLOSED}),
    IncidentState.CLOSED: frozenset(),
}

#: Nothing follows this. A new observation opens a new incident.
TERMINAL_STATES = frozenset({IncidentState.CLOSED})

#: Still live.
OPEN_STATES = frozenset(s for s in IncidentState if s not in TERMINAL_STATES)


def is_legal_transition(current: IncidentState, target: IncidentState) -> bool:
    return target in LEGAL_TRANSITIONS.get(current, frozenset())


def require_transition(current: IncidentState, target: IncidentState) -> None:
    """Refuse an illegal or backward transition; never coerce one."""

    if not is_legal_transition(current, target):
        raise IllegalTransitionError(
            f"{current.value} -> {target.value} is not a legal incident transition")
    if STATE_RANK[target] <= STATE_RANK[current]:
        raise IllegalTransitionError(
            f"{current.value} -> {target.value} is not forward-only")
