"""The vNext dimension policy — a resolved, immutable projection.

This is the *input* to the evaluator, never a mutable policy database. There is
no policy administration, no remote loading, and no source registry here: a
deployment resolves its policy elsewhere and hands this object in, exactly as
``ugence_action_clearance.policy.ClearancePolicy`` does for its own layer.

A dimension is governed only when this policy says so. That is deliberate and it
is the point of the whole module: the pre-vNext engine mapped seven governance
dimensions and read none of them, so a dimension could look governed while being
inert. Here, a dimension with no declared requirement contributes nothing *and
says so* — ``DimensionPolicy.governed_dimensions`` reports exactly which
dimensions can affect an outcome, so vacuity is observable instead of implicit.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Mapping, Optional, Tuple

from .reason_codes import ActionGateTier


@dataclass(frozen=True)
class ParameterBound:
    """A declared numeric ceiling on one request parameter.

    ``deny_above`` is the hard limit. ``constrain_above``, when set and lower
    than ``deny_above``, is the point at which the action is still authorized
    but carries an emitted constraint.
    """

    parameter: str
    deny_above: int
    constrain_above: Optional[int] = None

    def __post_init__(self) -> None:
        if self.constrain_above is not None and self.constrain_above > self.deny_above:
            raise ValueError(
                f"parameter bound {self.parameter!r}: constrain_above "
                f"({self.constrain_above}) must not exceed deny_above ({self.deny_above})")


@dataclass(frozen=True)
class ActionGatePolicy:
    """A resolved, immutable ActionGate vNext policy."""

    policy_id: str
    policy_version: str

    # --- action_type (the one dimension the pre-vNext engine already read) ---
    denied_action_types: frozenset = frozenset()
    unknown_action_types: frozenset = frozenset()

    # --- hard dimensions -------------------------------------------------
    #: Action types that may not proceed without a non-empty authority context.
    authority_required_action_types: frozenset = frozenset()
    #: Authority contexts accepted for an action type. Absent key => any
    #: non-empty authority is accepted (presence is still required above).
    accepted_authority_contexts: Mapping[str, Tuple[str, ...]] = field(default_factory=dict)
    #: Action types that may not proceed without a resolvable principal.
    principal_required_action_types: frozenset = frozenset()
    #: Closed principal allowlist. Empty => no allowlist is enforced.
    principal_allowlist: frozenset = frozenset()
    #: Action types that must carry at least one decision reference.
    decision_ref_required_action_types: frozenset = frozenset()
    #: Resource prefixes permitted per action type. Absent key => unrestricted.
    permitted_resource_prefixes: Mapping[str, Tuple[str, ...]] = field(default_factory=dict)
    #: Action types that may not proceed without a resolvable target resource.
    resource_required_action_types: frozenset = frozenset()

    # --- mixed / soft dimensions -----------------------------------------
    parameter_bounds: Tuple[ParameterBound, ...] = ()
    #: Action types requiring a risk score. Absent risk => uncertainty, not denial.
    risk_required_action_types: frozenset = frozenset()
    #: Risk scores that deny outright, and scores that authorize under constraint.
    risk_deny_scores: frozenset = frozenset()
    risk_constrain_scores: frozenset = frozenset()
    #: Minimum evidence references per action type.
    minimum_evidence_refs: Mapping[str, int] = field(default_factory=dict)
    #: Action types requiring at least one policy reference to resolve a rule.
    policy_ref_required_action_types: frozenset = frozenset()

    # --- policy-configurable tier elevation -------------------------------
    #: Reason code value -> tier, for codes the policy is permitted to elevate.
    #: The evaluator accepts an override only when it is strictly more
    #: restrictive than the code's default, so a softening override is rejected
    #: for every code; a ``NON_SOFTENABLE`` code additionally rejects hardening.
    tier_overrides: Mapping[str, ActionGateTier] = field(default_factory=dict)

    @property
    def policy_ref(self) -> str:
        return f"{self.policy_id}:{self.policy_version}"

    def governed_dimensions(self) -> frozenset:
        """Exactly the dimensions this policy can make dispositive.

        A dimension absent from this set cannot change any outcome under this
        policy. Reporting it is what makes an inert dimension visible rather
        than a silent assumption of governance.
        """
        governed = set()
        if self.denied_action_types or self.unknown_action_types:
            governed.add("action_type")
        if self.authority_required_action_types or self.accepted_authority_contexts:
            governed.add("authority")
        if self.principal_required_action_types or self.principal_allowlist:
            governed.add("principal")
        if self.decision_ref_required_action_types:
            governed.add("decision_refs")
        if self.permitted_resource_prefixes or self.resource_required_action_types:
            governed.add("resource")
        if self.parameter_bounds:
            governed.add("parameters")
        if (self.risk_required_action_types or self.risk_deny_scores
                or self.risk_constrain_scores):
            governed.add("risk_context")
        if self.minimum_evidence_refs:
            governed.add("evidence_refs")
        if self.policy_ref_required_action_types:
            governed.add("policy_context")
        return frozenset(governed)


__all__ = ["ActionGatePolicy", "ParameterBound"]
