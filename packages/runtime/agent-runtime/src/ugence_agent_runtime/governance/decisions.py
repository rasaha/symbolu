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
from typing import Callable, Optional, Tuple

from ..models.proposal import TransitionProposal
from .interfaces import GovernanceDisposition, GovernanceEvaluation

# A neutral pre-effect authority-recheck callable (RA-6 §8 "last-mile TOCTOU").
# The runtime stays concrete-free: it knows nothing about Risk Authority, epochs,
# or revocation. An external governance integration may supply a callable that,
# immediately before the irreversible effect, re-verifies that the authority the
# CLEAR was bound to is *still* valid (not expired, not revoked, not stale-epoch,
# and status fresh enough). It returns ``(ok, reason_codes)`` and MUST NOT mint
# authority or mutate state — it can only confirm or fail closed. When no callable
# is configured, behavior is exactly as before (fully backward compatible).
AuthorityRecheck = Callable[
    [Optional[GovernanceEvaluation], TransitionProposal, float],
    Tuple[bool, Tuple[str, ...]],
]


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
# Emitted when a configured last-mile authority recheck fails immediately before
# the effect (RA-6 §8): the CLEAR was validly bound, but the authority it rested
# on is no longer valid at the commit point (expired / revoked / stale epoch /
# status too stale). Fail closed.
CLEAR_REJECTED_AUTHORITY_STALE = "GOVERNANCE_CLEAR_AUTHORITY_STALE"


def validate_clearance(
    evaluation: Optional[GovernanceEvaluation],
    proposal: TransitionProposal,
    now: float,
    authority_recheck: "Optional[AuthorityRecheck]" = None,
) -> Tuple[bool, Tuple[str, ...]]:
    """Decide whether a CLEAR result may be acted on for this exact proposal.

    Returns ``(permitted, reason_codes)``. Fails closed: any missing, mismatched,
    unreferenced, or expired binding yields ``(False, reasons)``. This is the sole
    gate between a governance result and a provider invocation.

    ``authority_recheck`` (optional, RA-6 §8) is a neutral last-mile hook run
    ONLY after every existing binding check has passed — i.e. immediately before
    the irreversible effect. If supplied and it returns ``(False, reasons)`` the
    clearance is rejected fail-closed with :data:`CLEAR_REJECTED_AUTHORITY_STALE`
    plus the hook's reasons. When it is ``None`` (the default) behavior is
    identical to before — the runtime adds no authority concept of its own.
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

    # Last-mile authority re-verification (RA-6 §8): the CLEAR is validly bound to
    # this exact proposal; re-confirm the underlying authority is STILL valid at
    # the commit point. This runs last, closest to the effect, and can only fail
    # closed — it never broadens a decision.
    if authority_recheck is not None:
        ok, recheck_reasons = authority_recheck(evaluation, proposal, now)
        if not ok:
            return False, (CLEAR_REJECTED_AUTHORITY_STALE,) + tuple(recheck_reasons)

    return True, ()
