"""Baseline action engine — a deterministic, capability-limited vendor core (pure).

A legitimate but intentionally simpler alternative to ActionGate. It imports
neither the DGM kernel nor the provider framework, and never executes actions.

Capabilities (honestly limited):
* deterministic allow / deny;
* a restricted constraint vocabulary (``maximum_amount`` only);
* a restricted obligation vocabulary (``logging``, ``notification``);
* any policy construct outside that vocabulary → UNKNOWN (→ INDETERMINATE at the
  provider boundary), never a less-safe AUTHORIZED.
"""
from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from enum import Enum
from typing import Mapping, Optional


class BaselineActionError(Exception):
    pass


class BaselineActionTimeout(BaselineActionError):
    pass


class BaselineActionUnavailable(BaselineActionError):
    pass


class BaselineActionConfigError(BaselineActionError):
    pass


class BaselineActionMalformed(BaselineActionError):
    pass


class BaselineActionOutcome(str, Enum):
    ALLOW = "ALLOW"
    DENY = "DENY"
    ALLOW_WITH_CONSTRAINTS = "ALLOW_WITH_CONSTRAINTS"
    UNKNOWN = "UNKNOWN"


#: the only controls this capability-limited engine can enforce
SUPPORTED_CONSTRAINTS = frozenset({"maximum_amount"})
SUPPORTED_OBLIGATIONS = frozenset({"logging", "notification"})


@dataclass(frozen=True)
class BaselineActionConstraint:
    type: str
    value: str = ""


@dataclass(frozen=True)
class BaselineActionObligation:
    type: str
    value: str = ""


@dataclass(frozen=True)
class BaselineActionRequest:
    action_type: str
    parameters: Mapping[str, str] = field(default_factory=dict)
    correlation_id: str = ""


@dataclass(frozen=True)
class BaselineActionDecision:
    outcome: BaselineActionOutcome
    constraints: tuple[BaselineActionConstraint, ...] = ()
    obligations: tuple[BaselineActionObligation, ...] = ()
    reason_codes: tuple[str, ...] = ()
    trace_id: str = ""


@dataclass(frozen=True)
class ConstrainedRule:
    constraints: tuple[BaselineActionConstraint, ...] = ()
    obligations: tuple[BaselineActionObligation, ...] = ()


class BaselineActionEngine:
    """A deterministic, capability-limited action-authorization engine.

    ``denied`` action types → DENY; ``constrained`` rules whose controls all fall
    within the supported vocabulary → ALLOW_WITH_CONSTRAINTS; rules referencing an
    unsupported control → UNKNOWN (capability-limited); otherwise ALLOW.
    """

    policy_version = "baseline-action-1"

    def __init__(self, *, denied: frozenset = frozenset(),
                 constrained: Optional[Mapping[str, ConstrainedRule]] = None,
                 unknown: frozenset = frozenset(),
                 default_obligations: tuple[BaselineActionObligation, ...] = (
                     BaselineActionObligation("logging", "audit"),),
                 fail: Optional[str] = None, available: bool = True) -> None:
        self._denied = denied
        self._constrained = dict(constrained or {})
        self._unknown = unknown
        self._default_obligations = default_obligations
        self._fail = fail
        self._available = available

    @property
    def available(self) -> bool:
        return self._available and self._fail != "unavailable"

    def evaluate(self, request: BaselineActionRequest) -> BaselineActionDecision:
        if self._fail == "timeout":
            raise BaselineActionTimeout("baseline action engine timed out")
        if self._fail == "unavailable":
            raise BaselineActionUnavailable("baseline action engine unavailable")
        if self._fail == "config":
            raise BaselineActionConfigError("baseline action engine misconfigured")
        if self._fail == "malformed":
            raise BaselineActionMalformed("baseline action returned a malformed result")
        trace = self._trace(request)
        at = request.action_type
        if at in self._denied:
            return BaselineActionDecision(BaselineActionOutcome.DENY,
                                          reason_codes=("policy_denied",), trace_id=trace)
        if at in self._unknown:
            return BaselineActionDecision(BaselineActionOutcome.UNKNOWN,
                                          reason_codes=("policy_unknown",), trace_id=trace)
        if at in self._constrained:
            rule = self._constrained[at]
            unsupported = [c.type for c in rule.constraints if c.type not in SUPPORTED_CONSTRAINTS]
            unsupported += [o.type for o in rule.obligations if o.type not in SUPPORTED_OBLIGATIONS]
            if unsupported:
                # honestly cannot serve this policy construct
                return BaselineActionDecision(
                    BaselineActionOutcome.UNKNOWN,
                    reason_codes=("unsupported_policy_construct",), trace_id=trace)
            return BaselineActionDecision(
                BaselineActionOutcome.ALLOW_WITH_CONSTRAINTS, constraints=rule.constraints,
                obligations=rule.obligations or self._default_obligations,
                reason_codes=("policy_allow_with_constraints",), trace_id=trace)
        return BaselineActionDecision(BaselineActionOutcome.ALLOW,
                                      obligations=self._default_obligations,
                                      reason_codes=("policy_allow",), trace_id=trace)

    @staticmethod
    def _trace(request: BaselineActionRequest) -> str:
        payload = json.dumps({"a": request.action_type, "p": dict(request.parameters)},
                             sort_keys=True)
        return "base-action-" + hashlib.sha256(payload.encode()).hexdigest()[:16]
