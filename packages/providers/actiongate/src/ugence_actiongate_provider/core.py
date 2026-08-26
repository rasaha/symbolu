"""ActionGate core engine — the vendor governance engine (pure).

This module is the ActionGate *product core*. Per the platform's dependency
rules it imports **neither** the DGM kernel **nor** the provider framework: it
speaks only its own native governance vocabulary. The provider layer
(``actiongate_provider.provider``) adapts this core onto the neutral
``ActionGovernanceProvider`` contract.

Deterministic and offline: a decision is a pure function of the request and the
configured policy. Configurable failure flags simulate a real engine's error
modes (timeout / unavailable / malformed / config) so the provider's error
translation can be validated without a network.

Policy evaluation itself lives in :mod:`.vnext`, which reads every governance
dimension the neutral contract carries. This module keeps the native
vocabulary, the failure modes, and the constrained-rule payloads (constraints,
obligations, expiry) that the vNext dimension model does not own; it delegates
the decision. ``vnext`` imports neither the kernel nor the framework, so the
dependency rule above still holds.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from enum import Enum
from typing import Mapping, Optional

from .vnext import ActionGatePolicy
from .vnext import ActionGateReasonCode as _RC
from .vnext import ActionGateTier as _Tier
from .vnext import VNextAuthorizationRequest as _VReq
from .vnext import evaluate as _vnext_evaluate


# --- native exceptions (must never cross the provider boundary) -------------

class ActionGateError(Exception):
    """Base class for ActionGate engine failures."""


class ActionGateTimeout(ActionGateError):
    """The engine did not respond within its deadline."""


class ActionGateUnavailable(ActionGateError):
    """The engine is not currently available."""


class ActionGateConfigError(ActionGateError):
    """The engine configuration is invalid."""


class ActionGateMalformedResponse(ActionGateError):
    """The engine produced a response that failed its own schema."""


# --- native vocabulary ------------------------------------------------------

class ActionGateOutcome(str, Enum):
    ALLOW = "ALLOW"
    DENY = "DENY"
    ALLOW_WITH_CONSTRAINTS = "ALLOW_WITH_CONSTRAINTS"
    UNKNOWN = "UNKNOWN"
    #: The upstream authorization had already expired when the request arrived.
    #: Distinct from DENY (policy refused) and from UNKNOWN (policy could not
    #: decide): nothing was evaluated, because there was no live authorization
    #: left to evaluate against.
    EXPIRED = "EXPIRED"


@dataclass(frozen=True)
class ActionGateConstraint:
    """A typed runtime control (e.g. maximum_amount, allowed_region)."""

    type: str
    value: str


@dataclass(frozen=True)
class ActionGateObligation:
    """A typed obligation the caller must fulfil (e.g. notification, logging)."""

    type: str
    value: str = ""


@dataclass(frozen=True)
class ActionGateRequest:
    action_type: str
    parameters: Mapping[str, str] = field(default_factory=dict)
    principal: str = ""
    authority: str = ""
    resource: str = ""
    policy_context: tuple[str, ...] = ()
    risk_context: Mapping[str, str] = field(default_factory=dict)
    evidence_refs: tuple[str, ...] = ()
    decision_refs: tuple[str, ...] = ()
    tenant: str = ""
    correlation_id: str = ""
    idempotency_key: str = ""
    #: Whether the upstream authorization this request rides on has expired.
    #: Computed by the caller against the inclusive boundary (``now >=
    #: expires_at``); ActionGate consumes the verdict rather than re-deriving it,
    #: because only the caller holds the authorization record's clock.
    authorization_expired: bool = False


@dataclass(frozen=True)
class ActionGateDecision:
    outcome: ActionGateOutcome
    constraints: tuple[ActionGateConstraint, ...] = ()
    obligations: tuple[ActionGateObligation, ...] = ()
    expiry_seconds: Optional[int] = None
    authority_basis: str = ""
    reason_codes: tuple[str, ...] = ()
    trace_id: str = ""


@dataclass(frozen=True)
class _ConstrainedRule:
    constraints: tuple[ActionGateConstraint, ...]
    obligations: tuple[ActionGateObligation, ...]
    expiry_seconds: Optional[int] = None


#: vNext tier → native ActionGate outcome.
#:
#: Chosen so that composing this with ``mapping.result._OUTCOME_MAP`` reproduces
#: ``vnext.NEUTRAL_OUTCOME_V2`` exactly — the native vocabulary is a waypoint,
#: not a second opinion. ``tests/vnext/test_outcome_composition.py`` asserts the
#: composition for every tier, so the two tables cannot drift apart.
TIER_TO_NATIVE: Mapping[_Tier, ActionGateOutcome] = {
    _Tier.EXPIRED: ActionGateOutcome.EXPIRED,
    _Tier.DENIED: ActionGateOutcome.DENY,
    _Tier.EVIDENCE_REQUIRED: ActionGateOutcome.UNKNOWN,
    _Tier.SIMULATION_REQUIRED: ActionGateOutcome.UNKNOWN,
    _Tier.ESCALATION_REQUIRED: ActionGateOutcome.UNKNOWN,
    _Tier.AUTHORIZED_WITH_CONSTRAINTS: ActionGateOutcome.ALLOW_WITH_CONSTRAINTS,
    _Tier.AUTHORIZED: ActionGateOutcome.ALLOW,
}


def _split_constraint(encoded: str) -> ActionGateConstraint:
    """Decode a vNext ``type=value`` constraint into the native pair."""
    type_, _, value = encoded.partition("=")
    return ActionGateConstraint(type=type_, value=value)


class ActionGateEngine:
    """A deterministic ActionGate policy engine.

    Every governance dimension the neutral contract carries is evaluated, by
    delegating to :func:`.vnext.evaluate`. The ``denied`` / ``unknown`` /
    ``constrained`` action-type sets remain the ergonomic shorthand they always
    were and are folded into the vNext policy; ``policy`` supplies the richer
    dimension rules (authority, principal, resource, parameters, risk, evidence,
    decision refs). The ``fail`` flag simulates an engine error mode by
    native-exception type.

    An expired authorization short-circuits before any policy is consulted: it
    is not a policy question, so it yields EXPIRED with no authority basis and
    no constraints.
    """

    #: policy schema/version the engine reports (used for health + observability)
    policy_version = "policy-2"

    def __init__(
        self,
        *,
        denied: frozenset[str] = frozenset(),
        constrained: Optional[Mapping[str, _ConstrainedRule]] = None,
        unknown: frozenset[str] = frozenset(),
        default_obligations: tuple[ActionGateObligation, ...] = (
            ActionGateObligation(type="logging", value="audit"),),
        authority_basis: str = "actiongate-policy",
        fail: Optional[str] = None,
        available: bool = True,
        policy: Optional[ActionGatePolicy] = None,
    ) -> None:
        self._denied = denied
        self._constrained = dict(constrained or {})
        self._unknown = unknown
        self._default_obligations = default_obligations
        self._authority_basis = authority_basis
        self._fail = fail
        self._available = available
        self._policy = self._resolve_policy(policy)

    def _resolve_policy(self, policy: Optional[ActionGatePolicy]) -> ActionGatePolicy:
        """Fold the action-type shorthand into the supplied dimension policy.

        The shorthand sets and the dimension policy are two ways of saying the
        same thing, so they are merged into one object rather than evaluated in
        two passes — a second pass would be a second place for a dimension to be
        silently skipped.
        """
        base = policy or ActionGatePolicy(policy_id="actiongate", policy_version="2")
        from dataclasses import replace
        return replace(
            base,
            denied_action_types=frozenset(base.denied_action_types) | frozenset(self._denied),
            unknown_action_types=frozenset(base.unknown_action_types) | frozenset(self._unknown),
        )

    @property
    def available(self) -> bool:
        return self._available and self._fail != "unavailable"

    @property
    def governed_dimensions(self) -> frozenset:
        """Exactly the dimensions this engine's policy can make dispositive."""
        return self._policy.governed_dimensions()

    def evaluate(self, request: ActionGateRequest) -> ActionGateDecision:
        if self._fail == "timeout":
            raise ActionGateTimeout("actiongate engine timed out")
        if self._fail == "unavailable":
            raise ActionGateUnavailable("actiongate engine unavailable")
        if self._fail == "config":
            raise ActionGateConfigError("actiongate engine misconfigured")
        if self._fail == "malformed":
            raise ActionGateMalformedResponse("actiongate returned a malformed response")

        trace = self._trace(request)
        decision = _vnext_evaluate(_to_vnext_request(request), self._policy)
        native = TIER_TO_NATIVE[decision.tier]
        reasons = decision.reason_codes

        # Non-authorizing outcomes carry no authority basis: ActionGate must
        # never publish a basis for something it did not authorize.
        if native is ActionGateOutcome.EXPIRED:
            return ActionGateDecision(native, reason_codes=reasons, trace_id=trace)
        if native is ActionGateOutcome.UNKNOWN:
            return ActionGateDecision(native, reason_codes=reasons, trace_id=trace)
        if native is ActionGateOutcome.DENY:
            return ActionGateDecision(native, reason_codes=reasons,
                                      authority_basis=self._authority_basis, trace_id=trace)

        # Authorizing. A configured constrained rule supplies the payload the
        # dimension model does not own (obligations, expiry, curated controls)
        # and composes with any constraint the dimension evaluation emitted.
        rule = self._constrained.get(request.action_type)
        dimension_constraints = tuple(_split_constraint(c) for c in decision.constraints)
        if rule is not None:
            merged = rule.constraints + dimension_constraints
            # The bare POLICY_ALLOW the dimension pass emitted is superseded:
            # this decision authorizes under constraints, and reporting both
            # would say two different things about the same outcome.
            merged_reasons = tuple(sorted(
                (set(reasons) - {_RC.POLICY_ALLOW.value})
                | {_RC.POLICY_ALLOW_WITH_CONSTRAINTS.value}))
            return ActionGateDecision(
                ActionGateOutcome.ALLOW_WITH_CONSTRAINTS, constraints=merged,
                obligations=rule.obligations or self._default_obligations,
                expiry_seconds=rule.expiry_seconds, authority_basis=self._authority_basis,
                reason_codes=merged_reasons, trace_id=trace)
        if native is ActionGateOutcome.ALLOW_WITH_CONSTRAINTS:
            return ActionGateDecision(
                native, constraints=dimension_constraints,
                obligations=self._default_obligations,
                authority_basis=self._authority_basis, reason_codes=reasons, trace_id=trace)
        return ActionGateDecision(ActionGateOutcome.ALLOW, obligations=self._default_obligations,
                                  authority_basis=self._authority_basis,
                                  reason_codes=reasons, trace_id=trace)

    @staticmethod
    def _trace(request: ActionGateRequest) -> str:
        """A trace id over every dimension that can affect the decision.

        Previously this covered ``action_type``, ``parameters`` and ``tenant``
        only — and ``tenant`` was always empty — so two requests differing in
        actor, authority, resource, risk, evidence and expiry produced the same
        trace id. A trace that cannot distinguish those requests cannot be used
        to investigate one, which is most of what a trace id is for.
        """
        payload = json.dumps({
            "action_type": request.action_type,
            "parameters": dict(request.parameters),
            "principal": request.principal,
            "authority": request.authority,
            "resource": request.resource,
            "policy_context": list(request.policy_context),
            "risk_context": dict(request.risk_context),
            "evidence_refs": list(request.evidence_refs),
            "decision_refs": list(request.decision_refs),
            "tenant": request.tenant,
            "authorization_expired": request.authorization_expired,
        }, sort_keys=True, default=str)
        return "ag-" + hashlib.sha256(payload.encode()).hexdigest()[:16]


def _to_vnext_request(request: ActionGateRequest) -> _VReq:
    """Project the native request onto the vNext evaluation request.

    Total over the native type's governance dimensions: correlation and
    idempotency are carried for binding but are not evaluation inputs.
    """
    return _VReq(
        action_type=request.action_type,
        parameters=dict(request.parameters),
        principal=request.principal,
        authority=request.authority,
        resource=request.resource,
        policy_context=tuple(request.policy_context),
        risk_context=dict(request.risk_context),
        evidence_refs=tuple(request.evidence_refs),
        decision_refs=tuple(request.decision_refs),
        tenant=request.tenant,
        correlation_id=request.correlation_id,
        idempotency_key=request.idempotency_key,
        authorization_expired=request.authorization_expired,
    )


# Re-export the constrained-rule builder for policy authoring in configuration.
ConstrainedRule = _ConstrainedRule
