"""The closed ActionGate vNext reason-code catalogue and its severity lattice.

Two disciplines are borrowed rather than invented:

* the **closed enum + default-tier map** shape comes from
  ``ugence_action_clearance.reason_codes`` (a capability that consumes an
  already-authorized action and can never create authorization — nothing here
  imports it, and this module is not a clearance layer);
* the **non-compensatory severity lattice** comes from the ActionGate reference
  evaluator ``cyber_security/action_gate_reference/action_gate_ref/gate.py``
  (``_SEVERITY``). No number of satisfied conditions offsets one dispositive
  restriction: the outcome is the minimum-severity tier over all contributions.

Codes are UPPER_SNAKE and carry no vendor prefix. The catalogue is closed: an
evaluator may not emit a code that is not a member of
:class:`ActionGateReasonCode`, and every member has a declared default tier.
"""

from __future__ import annotations

from enum import Enum


class ActionGateTier(str, Enum):
    """Native vNext outcome tiers, most restrictive first.

    Six of these are the reference evaluator's frozen outcomes; ``EXPIRED`` is
    the seventh, and it is the one tier with no reference counterpart — the
    reference has no notion of an upstream authorization that has already
    expired (its ``E_EXPIRED`` covers approval and token expiry, a different
    artifact).
    """

    EXPIRED = "EXPIRED"
    DENIED = "DENIED"
    EVIDENCE_REQUIRED = "EVIDENCE_REQUIRED"
    SIMULATION_REQUIRED = "SIMULATION_REQUIRED"
    ESCALATION_REQUIRED = "ESCALATION_REQUIRED"
    AUTHORIZED_WITH_CONSTRAINTS = "AUTHORIZED_WITH_CONSTRAINTS"
    AUTHORIZED = "AUTHORIZED"


#: Non-compensatory precedence: lower wins. Mirrors ``gate._SEVERITY`` with
#: ``EXPIRED`` inserted below ``DENIED`` because expiry is evaluated before
#: policy is consulted at all — an expired authorization is not a policy
#: question.
TIER_PRECEDENCE: dict = {
    ActionGateTier.EXPIRED: 0,
    ActionGateTier.DENIED: 1,
    ActionGateTier.EVIDENCE_REQUIRED: 2,
    ActionGateTier.SIMULATION_REQUIRED: 3,
    ActionGateTier.ESCALATION_REQUIRED: 4,
    ActionGateTier.AUTHORIZED_WITH_CONSTRAINTS: 5,
    ActionGateTier.AUTHORIZED: 6,
}


def combine_tiers(tiers) -> ActionGateTier:
    """Least-permissive-wins combination. Empty contributions => AUTHORIZED."""
    worst = ActionGateTier.AUTHORIZED
    for tier in tiers:
        if TIER_PRECEDENCE[tier] < TIER_PRECEDENCE[worst]:
            worst = tier
    return worst


class ActionGateReasonCode(str, Enum):
    """The closed catalogue of ActionGate vNext reason codes."""

    # positive
    POLICY_ALLOW = "POLICY_ALLOW"

    # action_type
    POLICY_DENIED = "POLICY_DENIED"
    POLICY_UNKNOWN = "POLICY_UNKNOWN"
    POLICY_NO_RULE = "POLICY_NO_RULE"

    # authority (hard)
    AUTHORITY_ABSENT = "AUTHORITY_ABSENT"
    AUTHORITY_INSUFFICIENT = "AUTHORITY_INSUFFICIENT"

    # principal (hard)
    PRINCIPAL_UNRESOLVED = "PRINCIPAL_UNRESOLVED"
    PRINCIPAL_UNRECOGNIZED = "PRINCIPAL_UNRECOGNIZED"

    # decision binding (hard)
    DECISION_REF_MISSING = "DECISION_REF_MISSING"

    # resource (hard)
    RESOURCE_NOT_PERMITTED = "RESOURCE_NOT_PERMITTED"
    RESOURCE_UNRESOLVED = "RESOURCE_UNRESOLVED"

    # parameters (mixed)
    PARAMETER_LIMIT_EXCEEDED = "PARAMETER_LIMIT_EXCEEDED"
    PARAMETER_BOUND_APPLIED = "PARAMETER_BOUND_APPLIED"
    PARAMETER_UNRESOLVED = "PARAMETER_UNRESOLVED"

    # risk (soft)
    RISK_THRESHOLD_EXCEEDED = "RISK_THRESHOLD_EXCEEDED"
    RISK_THRESHOLD_CONSTRAINED = "RISK_THRESHOLD_CONSTRAINED"
    RISK_CONTEXT_UNAVAILABLE = "RISK_CONTEXT_UNAVAILABLE"

    # evidence (soft)
    EVIDENCE_INSUFFICIENT = "EVIDENCE_INSUFFICIENT"

    # upstream authorization validity
    AUTHORIZATION_EXPIRED = "AUTHORIZATION_EXPIRED"


R = ActionGateReasonCode
T = ActionGateTier

#: Default tier each reason code contributes. A policy may elevate a soft code
#: to a harder tier; it may never soften a hard one (enforced in evaluator).
DEFAULT_TIER: dict = {
    R.POLICY_ALLOW: T.AUTHORIZED,
    R.POLICY_DENIED: T.DENIED,
    R.POLICY_UNKNOWN: T.ESCALATION_REQUIRED,
    R.POLICY_NO_RULE: T.ESCALATION_REQUIRED,
    R.AUTHORITY_ABSENT: T.DENIED,
    R.AUTHORITY_INSUFFICIENT: T.DENIED,
    R.PRINCIPAL_UNRESOLVED: T.DENIED,
    R.PRINCIPAL_UNRECOGNIZED: T.DENIED,
    R.DECISION_REF_MISSING: T.DENIED,
    R.RESOURCE_NOT_PERMITTED: T.DENIED,
    R.RESOURCE_UNRESOLVED: T.DENIED,
    R.PARAMETER_LIMIT_EXCEEDED: T.DENIED,
    R.PARAMETER_BOUND_APPLIED: T.AUTHORIZED_WITH_CONSTRAINTS,
    R.PARAMETER_UNRESOLVED: T.EVIDENCE_REQUIRED,
    R.RISK_THRESHOLD_EXCEEDED: T.DENIED,
    R.RISK_THRESHOLD_CONSTRAINED: T.AUTHORIZED_WITH_CONSTRAINTS,
    R.RISK_CONTEXT_UNAVAILABLE: T.EVIDENCE_REQUIRED,
    R.EVIDENCE_INSUFFICIENT: T.EVIDENCE_REQUIRED,
    R.AUTHORIZATION_EXPIRED: T.EXPIRED,
}

#: Codes whose tier a policy may not soften. These are the ratified "hard"
#: dimensions plus expiry: absent authority, an unresolved principal and a
#: missing decision binding are boundary violations, never uncertainty.
NON_SOFTENABLE = frozenset({
    R.AUTHORITY_ABSENT, R.AUTHORITY_INSUFFICIENT,
    R.PRINCIPAL_UNRESOLVED, R.PRINCIPAL_UNRECOGNIZED,
    R.DECISION_REF_MISSING, R.AUTHORIZATION_EXPIRED,
})


def default_tier(code: ActionGateReasonCode) -> ActionGateTier:
    return DEFAULT_TIER[code]


def canonical_reason_order(codes) -> tuple:
    """Deterministic reason ordering (alphabetical by value) with dedup."""
    return tuple(sorted({c for c in codes}, key=lambda c: c.value))


# --- completeness self-check ------------------------------------------------
# A code without a declared tier would silently contribute nothing to the
# lattice, which is exactly the vacuity this evaluator exists to remove.
assert set(DEFAULT_TIER) == set(ActionGateReasonCode), (
    "every reason code must declare a default tier")


__all__ = [
    "ActionGateTier",
    "ActionGateReasonCode",
    "TIER_PRECEDENCE",
    "DEFAULT_TIER",
    "NON_SOFTENABLE",
    "combine_tiers",
    "default_tier",
    "canonical_reason_order",
]
