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
from typing import Optional, Tuple

from ..models.proposal import TransitionProposal
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
    """True only for an explicit CLEAR disposition (disposition-level check only).

    This does NOT validate exact-action binding; use :func:`validate_clearance` before
    invoking a provider.
    """
    return directive_for(evaluation) is RuntimeDirective.CONTINUE


# Reason codes emitted when a CLEAR result is rejected before provider invocation.
CLEAR_REJECTED_MISSING = "GOVERNANCE_CLEAR_MISSING_EVALUATION"
CLEAR_REJECTED_NOT_CLEAR = "GOVERNANCE_NOT_CLEAR"
CLEAR_REJECTED_NO_FINGERPRINT = "GOVERNANCE_CLEAR_MISSING_FINGERPRINT"
CLEAR_REJECTED_FINGERPRINT_MISMATCH = "GOVERNANCE_CLEAR_FINGERPRINT_MISMATCH"
CLEAR_REJECTED_PROPOSAL_TAMPERED = "GOVERNANCE_PROPOSAL_TAMPERED"
CLEAR_REJECTED_NO_REFERENCE = "GOVERNANCE_CLEAR_MISSING_REFERENCE"
CLEAR_REJECTED_EXPIRED = "GOVERNANCE_CLEAR_EXPIRED"
CLEAR_REJECTED_MISSING_CORRELATION = "GOVERNANCE_CLEAR_MISSING_CORRELATION"
CLEAR_REJECTED_CORRELATION = "GOVERNANCE_CLEAR_CORRELATION_MISMATCH"


def validate_clearance(
    evaluation: Optional[GovernanceEvaluation],
    proposal: TransitionProposal,
    now: float,
) -> Tuple[bool, Tuple[str, ...]]:
    """Decide whether a CLEAR result may be acted on for this exact proposal.

    Returns ``(permitted, reason_codes)``. Fails closed: any missing, mismatched,
    unreferenced, or expired binding yields ``(False, reasons)``. This is the sole
    gate between a governance result and a provider invocation.
    """
    if evaluation is None:
        return False, (CLEAR_REJECTED_MISSING,)
    if directive_for(evaluation) is not RuntimeDirective.CONTINUE:
        return False, (CLEAR_REJECTED_NOT_CLEAR,)

    # The proposal must not have changed since it was built.
    if not proposal.is_intact():
        return False, (CLEAR_REJECTED_PROPOSAL_TAMPERED,)

    reasons = []
    if not evaluation.proposal_fingerprint:
        reasons.append(CLEAR_REJECTED_NO_FINGERPRINT)
    elif evaluation.proposal_fingerprint != proposal.fingerprint:
        reasons.append(CLEAR_REJECTED_FINGERPRINT_MISMATCH)

    if not evaluation.binding_reference():
        reasons.append(CLEAR_REJECTED_NO_REFERENCE)

    # Inclusive expiration: at the exact valid_until instant the clearance is expired
    # and cannot authorize invocation (now >= valid_until, not now > valid_until).
    if evaluation.valid_until is not None and now >= evaluation.valid_until:
        reasons.append(CLEAR_REJECTED_EXPIRED)

    # Correlation is part of exact-action identity (it is fingerprinted). When the
    # proposal carries a correlation id, the CLEAR result MUST echo the same id:
    # missing or mismatched correlation fails closed. When the proposal has no
    # correlation id (the runtime always sets one; this covers external callers), no
    # correlation binding is required.
    if proposal.correlation_id is not None:
        if evaluation.correlation_reference is None:
            reasons.append(CLEAR_REJECTED_MISSING_CORRELATION)
        elif evaluation.correlation_reference != proposal.correlation_id:
            reasons.append(CLEAR_REJECTED_CORRELATION)

    if reasons:
        return False, tuple(reasons)
    return True, ()
