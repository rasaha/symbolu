"""Mapping from governance disposition to runtime coordination behavior.

This is the ONE place the runtime translates a governance result into a coordination
action. The mapping is fixed and non-broadening:

    CLEAR    -> runtime may continue (invoke the provider)
    HOLD     -> runtime waits; no authority is created
    BLOCK    -> runtime does not execute the proposed transition
    ESCALATE -> runtime pauses pending external authority/review

The runtime never converts HOLD or ESCALATE into CLEAR, and never treats an absent
or malformed evaluation as CLEAR (fail closed).
"""
from __future__ import annotations

from enum import Enum

from .interfaces import GovernanceDisposition, GovernanceEvaluation


class RuntimeDirective(str, Enum):
    """What the engine does in response to a disposition."""

    CONTINUE = "CONTINUE"  # CLEAR
    WAIT = "WAIT"          # HOLD
    STOP = "STOP"          # BLOCK
    PAUSE = "PAUSE"        # ESCALATE


_MAPPING = {
    GovernanceDisposition.CLEAR: RuntimeDirective.CONTINUE,
    GovernanceDisposition.HOLD: RuntimeDirective.WAIT,
    GovernanceDisposition.BLOCK: RuntimeDirective.STOP,
    GovernanceDisposition.ESCALATE: RuntimeDirective.PAUSE,
}


def directive_for(evaluation: GovernanceEvaluation) -> RuntimeDirective:
    """Resolve the coordination directive for an evaluation.

    Fails closed: anything that is not an explicit, recognized CLEAR is treated as
    at-least-as-restrictive. An unrecognized disposition never yields CONTINUE.
    """
    if evaluation is None:
        return RuntimeDirective.STOP
    directive = _MAPPING.get(evaluation.disposition)
    if directive is None:
        # Unknown disposition: never broaden to CONTINUE.
        return RuntimeDirective.STOP
    return directive


def permits_execution(evaluation: GovernanceEvaluation) -> bool:
    """True only for an explicit CLEAR disposition."""
    return directive_for(evaluation) is RuntimeDirective.CONTINUE
