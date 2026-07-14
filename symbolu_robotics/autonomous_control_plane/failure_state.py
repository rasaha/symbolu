"""Failure-state scaffolding.

Implements the posture enum and legal-transition table from
``ACP_FAILURE_STATE_MACHINE.md`` (the approved ACP document), using that
document's exact posture names. Phase 0 provides:

* transition validation (illegal transitions raise ``IllegalTransitionError``);
* manual-reset gating for latched terminal states (ESTOP / HANDOVER require an
  operator + reason);
* deterministic, immutable event/transition recording.

It is NOT wired into the existing robot runtime in this phase.

Name mapping to the Phase-0 task's suggested list (kept for reference):
NORMAL→NOMINAL, REPLAN_REQUIRED→handled via the ``REPLAN`` decision +
DEGRADED/SAFE_HOLD posture, OPERATOR_REQUIRED→HANDOVER, SAFE_STOP→SAFE_HOLD/MRM,
FAILED→ESTOP.

Standard-library only.
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Optional, Tuple

from .errors import IllegalTransitionError, SchemaValidationError


class FailureState(str, Enum):
    NOMINAL = "NOMINAL"
    DEGRADED = "DEGRADED"
    SAFE_HOLD = "SAFE_HOLD"
    MRM = "MRM"              # minimum-risk maneuver
    ESTOP = "ESTOP"
    HANDOVER = "HANDOVER"


# Legal directed transitions (from ACP_FAILURE_STATE_MACHINE.md §1 diagram).
LEGAL_TRANSITIONS = frozenset({
    (FailureState.NOMINAL, FailureState.DEGRADED),
    (FailureState.DEGRADED, FailureState.NOMINAL),
    (FailureState.NOMINAL, FailureState.SAFE_HOLD),
    (FailureState.DEGRADED, FailureState.SAFE_HOLD),
    (FailureState.SAFE_HOLD, FailureState.NOMINAL),
    (FailureState.SAFE_HOLD, FailureState.MRM),
    (FailureState.DEGRADED, FailureState.MRM),
    (FailureState.MRM, FailureState.SAFE_HOLD),
    # hard-fault fast paths into ESTOP from any active posture
    (FailureState.NOMINAL, FailureState.ESTOP),
    (FailureState.DEGRADED, FailureState.ESTOP),
    (FailureState.SAFE_HOLD, FailureState.ESTOP),
    (FailureState.MRM, FailureState.ESTOP),
    # latched-terminal exits (manual)
    (FailureState.ESTOP, FailureState.HANDOVER),
    (FailureState.SAFE_HOLD, FailureState.HANDOVER),
    (FailureState.HANDOVER, FailureState.NOMINAL),
})

# Transitions that require an operator + reason (leaving a latched state).
MANUAL_RESET_TRANSITIONS = frozenset({
    (FailureState.ESTOP, FailureState.HANDOVER),
    (FailureState.HANDOVER, FailureState.NOMINAL),
})


def is_legal(src: FailureState, dst: FailureState) -> bool:
    return src == dst or (src, dst) in LEGAL_TRANSITIONS


def requires_manual_reset(src: FailureState, dst: FailureState) -> bool:
    return (src, dst) in MANUAL_RESET_TRANSITIONS


@dataclass(frozen=True)
class TransitionRecord:
    sequence: int
    from_state: FailureState
    to_state: FailureState
    event_code: str
    reason: str
    operator: Optional[str]  # required for manual-reset transitions


class FailureStateMachine:
    """Deterministic posture machine. Not connected to the runtime in Phase 0."""

    def __init__(self, initial: FailureState = FailureState.NOMINAL):
        self._state = initial
        self._history: Tuple[TransitionRecord, ...] = ()
        self._seq = 0

    @property
    def state(self) -> FailureState:
        return self._state

    @property
    def history(self) -> Tuple[TransitionRecord, ...]:
        return self._history

    def transition(
        self,
        to_state: FailureState,
        *,
        event_code: str,
        reason: str,
        operator: Optional[str] = None,
    ) -> TransitionRecord:
        """Validate + apply a transition. Raises on illegal / ungated moves."""
        if not isinstance(to_state, FailureState):
            raise SchemaValidationError("to_state must be a FailureState")
        if not event_code or not reason:
            raise SchemaValidationError("event_code and reason are required")
        if not is_legal(self._state, to_state):
            raise IllegalTransitionError(
                f"illegal transition {self._state.value} -> {to_state.value}")
        if requires_manual_reset(self._state, to_state) and not operator:
            raise IllegalTransitionError(
                f"transition {self._state.value} -> {to_state.value} requires an "
                f"operator (manual reset)")
        rec = TransitionRecord(
            sequence=self._seq, from_state=self._state, to_state=to_state,
            event_code=event_code, reason=reason, operator=operator)
        self._seq += 1
        self._history = self._history + (rec,)
        self._state = to_state
        return rec
