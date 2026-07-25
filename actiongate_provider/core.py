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
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from enum import Enum
from typing import Mapping, Optional


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


class ActionGateEngine:
    """A deterministic ActionGate policy engine.

    Policy: ``denied`` action types → DENY; ``constrained`` action types →
    ALLOW_WITH_CONSTRAINTS carrying the configured controls; ``unknown`` action
    types → UNKNOWN; otherwise ALLOW. The ``fail`` flag simulates an engine error
    mode by native-exception type.
    """

    #: policy schema/version the engine reports (used for health + observability)
    policy_version = "policy-1"

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
    ) -> None:
        self._denied = denied
        self._constrained = dict(constrained or {})
        self._unknown = unknown
        self._default_obligations = default_obligations
        self._authority_basis = authority_basis
        self._fail = fail
        self._available = available

    @property
    def available(self) -> bool:
        return self._available and self._fail != "unavailable"

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
        at = request.action_type
        if at in self._denied:
            return ActionGateDecision(ActionGateOutcome.DENY,
                                      reason_codes=("policy_denied",),
                                      authority_basis=self._authority_basis, trace_id=trace)
        if at in self._unknown:
            return ActionGateDecision(ActionGateOutcome.UNKNOWN,
                                      reason_codes=("policy_unknown",), trace_id=trace)
        if at in self._constrained:
            rule = self._constrained[at]
            return ActionGateDecision(
                ActionGateOutcome.ALLOW_WITH_CONSTRAINTS, constraints=rule.constraints,
                obligations=rule.obligations or self._default_obligations,
                expiry_seconds=rule.expiry_seconds, authority_basis=self._authority_basis,
                reason_codes=("policy_allow_with_constraints",), trace_id=trace)
        return ActionGateDecision(ActionGateOutcome.ALLOW, obligations=self._default_obligations,
                                  authority_basis=self._authority_basis,
                                  reason_codes=("policy_allow",), trace_id=trace)

    @staticmethod
    def _trace(request: ActionGateRequest) -> str:
        payload = json.dumps({"a": request.action_type, "p": dict(request.parameters),
                              "t": request.tenant}, sort_keys=True, default=str)
        return "ag-" + hashlib.sha256(payload.encode()).hexdigest()[:16]


# Re-export the constrained-rule builder for policy authoring in configuration.
ConstrainedRule = _ConstrainedRule
