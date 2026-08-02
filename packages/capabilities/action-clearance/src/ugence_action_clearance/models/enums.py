"""Neutral enumerations for Action Clearance (design §14, §9, §25)."""
from __future__ import annotations

from enum import Enum


class ClearanceStatus(str, Enum):
    """The exactly-four top-level clearance statuses.

    Precedence is least-permissive-wins: ``BLOCK > ESCALATE > HOLD > CLEAR``.
    There is deliberately no ``DENY`` — ActionGate owns authorization denial.
    """

    CLEAR = "CLEAR"
    HOLD = "HOLD"
    BLOCK = "BLOCK"
    ESCALATE = "ESCALATE"


#: Least-permissive-wins precedence (higher int = wins).
STATUS_PRECEDENCE = {
    ClearanceStatus.CLEAR: 0,
    ClearanceStatus.HOLD: 1,
    ClearanceStatus.ESCALATE: 2,
    ClearanceStatus.BLOCK: 3,
}


def combine_statuses(statuses) -> ClearanceStatus:
    """Combine contributions least-permissive-wins. Empty → CLEAR."""
    worst = ClearanceStatus.CLEAR
    for s in statuses:
        if STATUS_PRECEDENCE[s] > STATUS_PRECEDENCE[worst]:
            worst = s
    return worst


class SignalStatus(str, Enum):
    """Structural liveness of a trusted signal.

    ``UNKNOWN`` on a required signal fails closed (HOLD).
    """

    PRESENT = "PRESENT"
    ABSENT = "ABSENT"
    UNKNOWN = "UNKNOWN"


class SignalType(str, Enum):
    """Current-state fact a trusted signal asserts (merged neutral vocabulary)."""

    AUTHORIZATION_VALIDITY = "AUTHORIZATION_VALIDITY"
    ACTOR_STATUS = "ACTOR_STATUS"
    POLICY_VALIDITY = "POLICY_VALIDITY"
    CHANGE_FREEZE = "CHANGE_FREEZE"
    ACTIVE_INCIDENT = "ACTIVE_INCIDENT"
    ARTIFACT_IDENTITY = "ARTIFACT_IDENTITY"
    REQUIRED_CONTROL = "REQUIRED_CONTROL"
    TARGET_AVAILABILITY = "TARGET_AVAILABILITY"
    PRIOR_CONSUMPTION = "PRIOR_CONSUMPTION"


class SignalTrustLevel(str, Enum):
    """Integrity/provenance trust level a signal carries (policy input only).

    The evaluator consumes trust level as policy input; it never verifies PKI,
    retrieves keys, or contacts identity/adapter systems.
    """

    LEVEL_1_TRUSTED_INGESTION = "LEVEL_1_TRUSTED_INGESTION"
    LEVEL_2_AUTHENTICATED_ENVELOPE = "LEVEL_2_AUTHENTICATED_ENVELOPE"
    LEVEL_3_SIGNED_PRODUCER = "LEVEL_3_SIGNED_PRODUCER"


#: Ordering for "at least" comparisons.
_TRUST_ORDER = {
    SignalTrustLevel.LEVEL_1_TRUSTED_INGESTION: 1,
    SignalTrustLevel.LEVEL_2_AUTHENTICATED_ENVELOPE: 2,
    SignalTrustLevel.LEVEL_3_SIGNED_PRODUCER: 3,
}


def trust_at_least(actual: SignalTrustLevel, required: SignalTrustLevel) -> bool:
    return _TRUST_ORDER[actual] >= _TRUST_ORDER[required]


class ConsumptionStatus(str, Enum):
    """Advisory one-time-use status carried by a PRIOR_CONSUMPTION signal.

    The evaluator READS this from the authoritative downstream ledger; it never
    atomically owns consumption and never reserves.
    """

    UNUSED = "UNUSED"
    RESERVED = "RESERVED"
    CONSUMED = "CONSUMED"
    UNKNOWN = "UNKNOWN"


class AuthorizationOutcome(str, Enum):
    """Neutral ActionGate outcome vocabulary (by value; contract not imported).

    Only AUTHORIZED / AUTHORIZED_WITH_CONSTRAINTS are eligible inputs; the other
    outcomes are never reinterpreted as clearable.
    """

    AUTHORIZED = "AUTHORIZED"
    AUTHORIZED_WITH_CONSTRAINTS = "AUTHORIZED_WITH_CONSTRAINTS"
    DENIED = "DENIED"
    INDETERMINATE = "INDETERMINATE"
    EXPIRED = "EXPIRED"


ELIGIBLE_OUTCOMES = frozenset({
    AuthorizationOutcome.AUTHORIZED.value,
    AuthorizationOutcome.AUTHORIZED_WITH_CONSTRAINTS.value,
})


__all__ = [
    "ClearanceStatus",
    "STATUS_PRECEDENCE",
    "combine_statuses",
    "SignalStatus",
    "SignalType",
    "SignalTrustLevel",
    "trust_at_least",
    "ConsumptionStatus",
    "AuthorizationOutcome",
    "ELIGIBLE_OUTCOMES",
]
