"""The deterministic ActionGate vNext evaluator.

``evaluate`` is a pure function of ``(request, policy)``: no clock read, no
randomness, no network, no persistence, no dispatch. It is a reduction of the
ActionGate reference evaluator
(``cyber_security/action_gate_reference/action_gate_ref/gate.py``) onto the
dimensions the neutral governance contract can actually carry — the reference's
24-field envelope has no neutral carrier for ``delegation_chain``,
``credential_scope``, ``current_state_hash``, ``state_freshness`` or
``reversibility``, so the operators that read those are not ported here.

What *is* ported is the part that matters: the non-compensatory severity lattice
(``reason_codes.combine_tiers``), the accumulate-then-combine control flow, and
the discipline that every contribution names a closed reason code.

Authority boundary (unchanged from the pre-vNext provider, and enforced by
``tests/authority/test_authority_boundary.py``): this evaluator decides
authorization only. It never dispatches, executes, observes, reconciles, or
compensates; it never fabricates a principal or widens an authority; and an
absent input is never silently treated as a satisfied one.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import List, Optional, Tuple

from .policy import ActionGatePolicy
from .reason_codes import (
    NON_SOFTENABLE,
    ActionGateReasonCode as RC,
    ActionGateTier as Tier,
    canonical_reason_order,
    combine_tiers,
    default_tier,
)
from .request import VNextAuthorizationRequest

#: Native tier -> neutral ``ActionGovernanceOutcome`` value, as staged today.
#:
#: Per the ratified decision, the three non-authorizing middle tiers are carried
#: as reason codes on a single neutral ``INDETERMINATE`` rather than as new
#: neutral enum values, so the shared ``governance_providers.api`` surface stays
#: frozen and no other action provider is disturbed. A consumer that reads
#: ``reason_codes`` loses nothing; a consumer that reads only the outcome enum
#: sees three distinct situations as one, which is the accepted cost.
#:
#: ``EXPIRED`` maps to ``INDETERMINATE`` here too — non-authorizing and correct,
#: but not yet the distinct neutral ``EXPIRED`` value. See ``NEUTRAL_OUTCOME_V2``.
NEUTRAL_OUTCOME_STAGED: dict = {
    Tier.EXPIRED: "INDETERMINATE",
    Tier.DENIED: "DENIED",
    Tier.EVIDENCE_REQUIRED: "INDETERMINATE",
    Tier.SIMULATION_REQUIRED: "INDETERMINATE",
    Tier.ESCALATION_REQUIRED: "INDETERMINATE",
    Tier.AUTHORIZED_WITH_CONSTRAINTS: "AUTHORIZED_WITH_CONSTRAINTS",
    Tier.AUTHORIZED: "AUTHORIZED",
}

#: The same map after the MAJOR step that adds the native ``EXPIRED`` outcome and
#: wires ``authorization_expired`` through request mapping. The single differing
#: row is the whole of that change's observable effect on this table.
NEUTRAL_OUTCOME_V2: dict = {**NEUTRAL_OUTCOME_STAGED, Tier.EXPIRED: "EXPIRED"}

_AUTHORIZING = frozenset({"AUTHORIZED", "AUTHORIZED_WITH_CONSTRAINTS"})


@dataclass(frozen=True)
class VNextDecision:
    """A native vNext decision. Deterministic for a given (request, policy)."""

    tier: Tier
    reason_codes: Tuple[str, ...] = ()
    constraints: Tuple[str, ...] = ()
    governed_dimensions: Tuple[str, ...] = ()
    policy_ref: str = ""

    def neutral_outcome(self, *, expired_outcome_available: bool = False) -> str:
        table = NEUTRAL_OUTCOME_V2 if expired_outcome_available else NEUTRAL_OUTCOME_STAGED
        # An unmapped tier must never authorize. The table is total over the
        # enum, so this default is unreachable by construction — it is here so
        # that adding a tier without a mapping fails closed rather than open.
        return table.get(self.tier, "INDETERMINATE")

    @property
    def authorizes(self) -> bool:
        return self.neutral_outcome() in _AUTHORIZING


class _Accumulator:
    """Collects (reason, tier) contributions before the lattice combines them."""

    def __init__(self, policy: ActionGatePolicy) -> None:
        self._policy = policy
        self._reasons: List[RC] = []
        self._tiers: List[Tier] = []
        self._constraints: List[str] = []

    def add(self, reason: RC, *, constraint: Optional[str] = None) -> None:
        self._reasons.append(reason)
        self._tiers.append(self._tier_for(reason))
        if constraint is not None:
            self._constraints.append(constraint)

    def _tier_for(self, reason: RC) -> Tier:
        """Resolve a reason's tier, honouring policy elevation but not softening.

        Two separate refusals, and it matters which one carries which weight:

        1. The **precedence comparison** below accepts an override only when it
           is strictly more restrictive than the default. That is what refuses
           softening, and it refuses it for *every* code in the catalogue — a
           policy cannot downgrade any finding, hard or soft, so none can
           authorize its way around a boundary. A policy may still make a soft
           finding harder (an operator treating missing risk data as a denial is
           making their own control stricter), which is the intended latitude.
        2. ``NON_SOFTENABLE`` membership refuses the override outright, in both
           directions. Since softening is already gone, its live effect is to
           refuse the remaining *hardenings*: for these codes that is only
           DENIED -> EXPIRED, so a policy can never relabel an authority,
           principal or decision-binding failure as an expiry.

        ``resource`` and ``parameters`` are ratified hard/mixed without
        appearing in ``NON_SOFTENABLE``, and lose nothing by it: refusal (1)
        covers them identically.
        """
        base = default_tier(reason)
        override = self._policy.tier_overrides.get(reason.value)
        if override is None:
            return base
        if reason in NON_SOFTENABLE:
            return base
        from .reason_codes import TIER_PRECEDENCE
        return override if TIER_PRECEDENCE[override] < TIER_PRECEDENCE[base] else base

    @property
    def tiers(self) -> Tuple[Tier, ...]:
        return tuple(self._tiers)

    @property
    def reasons(self) -> Tuple[RC, ...]:
        return tuple(self._reasons)

    @property
    def constraints(self) -> Tuple[str, ...]:
        return tuple(sorted(set(self._constraints)))


def evaluate(request: VNextAuthorizationRequest,
             policy: ActionGatePolicy) -> VNextDecision:
    """Evaluate one authorization request against a resolved policy."""
    acc = _Accumulator(policy)
    at = request.action_type

    # --- terminal pre-check: an expired authorization is not a policy question
    if request.authorization_expired:
        return VNextDecision(
            tier=Tier.EXPIRED,
            reason_codes=(RC.AUTHORIZATION_EXPIRED.value,),
            governed_dimensions=tuple(sorted(policy.governed_dimensions())),
            policy_ref=policy.policy_ref)

    # --- action_type ------------------------------------------------------
    if at in policy.denied_action_types:
        acc.add(RC.POLICY_DENIED)
    if at in policy.unknown_action_types:
        acc.add(RC.POLICY_UNKNOWN)

    # --- authority (hard) -------------------------------------------------
    if at in policy.authority_required_action_types and not request.authority:
        acc.add(RC.AUTHORITY_ABSENT)
    accepted = policy.accepted_authority_contexts.get(at)
    if accepted is not None and request.authority and request.authority not in accepted:
        acc.add(RC.AUTHORITY_INSUFFICIENT)

    # --- principal (hard) -------------------------------------------------
    if at in policy.principal_required_action_types and not request.principal:
        acc.add(RC.PRINCIPAL_UNRESOLVED)
    if policy.principal_allowlist and request.principal \
            and request.principal not in policy.principal_allowlist:
        acc.add(RC.PRINCIPAL_UNRECOGNIZED)

    # --- decision binding (hard) -----------------------------------------
    if at in policy.decision_ref_required_action_types and not request.decision_refs:
        acc.add(RC.DECISION_REF_MISSING)

    # --- resource (hard) --------------------------------------------------
    if at in policy.resource_required_action_types and not request.resource:
        acc.add(RC.RESOURCE_UNRESOLVED)
    prefixes = policy.permitted_resource_prefixes.get(at)
    if prefixes is not None and request.resource \
            and not any(request.resource.startswith(p) for p in prefixes):
        acc.add(RC.RESOURCE_NOT_PERMITTED)

    # --- parameters (mixed) -----------------------------------------------
    for bound in policy.parameter_bounds:
        raw = request.parameters.get(bound.parameter)
        if raw is None:
            continue  # a bound on a parameter this request does not carry
        try:
            value = int(raw)
        except (TypeError, ValueError):
            # A bound was declared but cannot be evaluated. That is uncertainty,
            # not permission — never skip the bound silently.
            acc.add(RC.PARAMETER_UNRESOLVED)
            continue
        if value > bound.deny_above:
            acc.add(RC.PARAMETER_LIMIT_EXCEEDED)
        elif bound.constrain_above is not None and value > bound.constrain_above:
            acc.add(RC.PARAMETER_BOUND_APPLIED,
                    constraint=f"maximum_{bound.parameter}={bound.deny_above}")

    # --- risk (soft) ------------------------------------------------------
    score = request.risk_score
    if at in policy.risk_required_action_types and not score:
        acc.add(RC.RISK_CONTEXT_UNAVAILABLE)
    elif score:
        if score in policy.risk_deny_scores:
            acc.add(RC.RISK_THRESHOLD_EXCEEDED)
        elif score in policy.risk_constrain_scores:
            acc.add(RC.RISK_THRESHOLD_CONSTRAINED, constraint=f"risk_review={score}")

    # --- evidence (soft) --------------------------------------------------
    minimum = policy.minimum_evidence_refs.get(at)
    if minimum is not None and len(request.evidence_refs) < minimum:
        acc.add(RC.EVIDENCE_INSUFFICIENT)

    # --- policy_context (soft) --------------------------------------------
    if at in policy.policy_ref_required_action_types and not request.policy_context:
        acc.add(RC.POLICY_NO_RULE)

    # --- combine ----------------------------------------------------------
    tier = combine_tiers(acc.tiers) if acc.tiers else Tier.AUTHORIZED
    reasons = list(acc.reasons) or [RC.POLICY_ALLOW]
    if tier is Tier.AUTHORIZED:
        reasons = [RC.POLICY_ALLOW]

    # Constraints are meaningful only on an authorizing outcome; a denied action
    # carrying "constraints" would invite a caller to proceed under them.
    constraints = acc.constraints if tier is Tier.AUTHORIZED_WITH_CONSTRAINTS else ()

    return VNextDecision(
        tier=tier,
        reason_codes=tuple(c.value for c in canonical_reason_order(reasons)),
        constraints=constraints,
        governed_dimensions=tuple(sorted(policy.governed_dimensions())),
        policy_ref=policy.policy_ref)


__all__ = [
    "VNextDecision",
    "evaluate",
    "NEUTRAL_OUTCOME_STAGED",
    "NEUTRAL_OUTCOME_V2",
]
