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
# Emitted when the last-mile authority-recheck hook itself misbehaves — it raises,
# or returns anything other than the exact ``(bool, reasons)`` shape (RA-6 §8,
# audit F-1). Any such invalid recheck is normalized to a deterministic
# fail-closed rejection: the provider is NEVER invoked on an invalid recheck, and
# a malformed-but-truthy result can never be mistaken for "permit".
AUTHORITY_RECHECK_ERROR = "GOVERNANCE_AUTHORITY_RECHECK_ERROR"


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
    plus the hook's reasons. A hook that raises, or returns anything other than
    the exact ``(bool, reasons)`` shape, is normalized to the same fail-closed
    rejection carrying :data:`AUTHORITY_RECHECK_ERROR` (audit F-1) — never a
    permit. When it is ``None`` (the default) behavior is identical to before —
    the runtime adds no authority concept of its own.
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
        ok, recheck_reasons = _invoke_authority_recheck(
            authority_recheck, evaluation, proposal, now
        )
        if not ok:
            return False, (CLEAR_REJECTED_AUTHORITY_STALE,) + recheck_reasons

    return True, ()


def _invoke_authority_recheck(
    authority_recheck: "AuthorityRecheck",
    evaluation: Optional[GovernanceEvaluation],
    proposal: TransitionProposal,
    now: float,
) -> Tuple[bool, Tuple[str, ...]]:
    """Run the last-mile authority-recheck hook inside a narrow fail-closed boundary.

    Returns a normalized ``(ok, reasons)`` in which ``ok`` is strictly a ``bool``
    and ``reasons`` a tuple of ``str``. The hook contract is ``(bool, reasons)``;
    any exception raised by the hook, or any result that does not match that exact
    shape, is converted to a deterministic fail-closed rejection carrying
    :data:`AUTHORITY_RECHECK_ERROR`. Only the hook call itself is guarded — an
    invalid recheck can only DENY, never permit, and unrelated runtime errors in
    the surrounding clearance logic are not swallowed (RA-6 §8, audit F-1).
    """

    try:
        result = authority_recheck(evaluation, proposal, now)
    except Exception:
        return False, (AUTHORITY_RECHECK_ERROR,)
    return _normalize_recheck_result(result)


def _normalize_recheck_result(result: object) -> Tuple[bool, Tuple[str, ...]]:
    """Validate a recheck result's shape; anything malformed ⇒ fail-closed rejection.

    Guards every malformed shape observed in the F-1 reproduction, including the
    fail-open ones: a truthy non-bool first element (``"allow"``, ``1``) must
    never read as "permit", and a bare ``str`` reasons value must not fragment
    into per-character reason codes.
    """

    if not isinstance(result, (tuple, list)) or len(result) != 2:
        return False, (AUTHORITY_RECHECK_ERROR,)
    ok, reasons = result
    if not isinstance(ok, bool):
        return False, (AUTHORITY_RECHECK_ERROR,)
    if isinstance(reasons, (str, bytes)):
        return False, (AUTHORITY_RECHECK_ERROR,)
    try:
        normalized = tuple(reasons)
    except TypeError:
        return False, (AUTHORITY_RECHECK_ERROR,)
    if not all(isinstance(r, str) for r in normalized):
        return False, (AUTHORITY_RECHECK_ERROR,)
    return ok, normalized
