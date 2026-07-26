"""BaselineActionProvider — a capability-limited ActionGovernanceProvider.

Adapts the baseline action engine onto the neutral ``ActionGovernanceProvider``
contract (authorization only — it never executes). Honestly declares a limited
capability set (allow/deny + amount limits + logging/notification obligations) and
returns INDETERMINATE for policy constructs it cannot serve. Native failures are
translated to classified framework errors (the control-plane adapter normalizes
them to a fail-safe INDETERMINATE). No native exception crosses the boundary.

Independent of ActionGate and of every assertion provider (enforced by tests).
"""
from __future__ import annotations

import hashlib
import json
from typing import Optional

from governance_providers.api import (
    ActionGovernanceOutcome, ActionGovernanceRequest, ActionGovernanceResult, BaseProvider,
    ProviderCapabilities, ProviderCompatibility, ProviderConfigurationError, ProviderDescriptor,
    ProviderError, ProviderHealth, ProviderKind, ProviderLifecycleState,
    ProviderResultValidationError, ProviderTimeoutError, ProviderUnavailableError)

from .core import (
    BaselineActionConfigError, BaselineActionDecision, BaselineActionEngine, BaselineActionError,
    BaselineActionMalformed, BaselineActionOutcome, BaselineActionRequest, BaselineActionTimeout,
    BaselineActionUnavailable)
from .version import __version__ as PROVIDER_VERSION

_CONTRACT_VERSION = "1.0.0"
MAPPING_VERSION = "baseline-action-map-1"

CAPABILITIES = frozenset({
    "authorize", "allow_deny", "amount_limits", "notifications", "logging", "in_process"})

_OUTCOME_MAP = {
    BaselineActionOutcome.ALLOW: ActionGovernanceOutcome.AUTHORIZED,
    BaselineActionOutcome.ALLOW_WITH_CONSTRAINTS: ActionGovernanceOutcome.AUTHORIZED_WITH_CONSTRAINTS,
    BaselineActionOutcome.DENY: ActionGovernanceOutcome.DENIED,
    BaselineActionOutcome.UNKNOWN: ActionGovernanceOutcome.INDETERMINATE,
}
_ERROR_MAP = {
    BaselineActionConfigError: ProviderConfigurationError,
    BaselineActionTimeout: ProviderTimeoutError,
    BaselineActionMalformed: ProviderResultValidationError,
    BaselineActionUnavailable: ProviderUnavailableError,
}
_KNOWN_C = frozenset({"maximum_amount"})
_KNOWN_O = frozenset({"logging", "notification"})


def translate_error(exc: Exception) -> ProviderError:
    for native, provider in _ERROR_MAP.items():
        if isinstance(exc, native):
            return provider(f"baseline-action: {exc}")
    if isinstance(exc, BaselineActionError):
        return ProviderError(f"baseline-action: {exc}")
    return ProviderError(f"baseline-action-unexpected: {type(exc).__name__}: {exc}")


def _encode(items, known) -> tuple:
    out = []
    for it in items:
        prefix = "" if it.type in known else "ext:"
        out.append(f"{prefix}{it.type}={it.value}" if it.value else f"{prefix}{it.type}")
    return tuple(out)


class BaselineActionProvider(BaseProvider):
    def __init__(self, engine: BaselineActionEngine, *,
                 provider_id: str = "baseline-action", default: bool = False) -> None:
        descriptor = ProviderDescriptor(
            provider_id=provider_id, kind=ProviderKind.ACTION_GOVERNANCE,
            implementation_version=PROVIDER_VERSION,
            compatibility=ProviderCompatibility(
                contract_version=_CONTRACT_VERSION, compatible_kernel_majors=frozenset({"1"}),
                config_schema_version="1"),
            capabilities=ProviderCapabilities(
                kind=ProviderKind.ACTION_GOVERNANCE, features=CAPABILITIES, deterministic=True),
            factory=lambda: BaselineActionProvider(engine, provider_id=provider_id,
                                                   default=default),
            vendor="BaselineAction", default=default, metadata={"mode": "in_process"})
        super().__init__(descriptor)
        self._engine = engine

    def authorize(self, request: ActionGovernanceRequest) -> ActionGovernanceResult:
        native = BaselineActionRequest(
            action_type=request.action_type,
            parameters={k: str(v) for k, v in dict(request.requested_parameters).items()},
            correlation_id=request.correlation_id)
        try:
            decision = self._engine.evaluate(native)
        except Exception as exc:  # translate — no native exception may escape
            raise translate_error(exc)
        return self._map(decision)

    def _map(self, decision: BaselineActionDecision) -> ActionGovernanceResult:
        outcome = _OUTCOME_MAP.get(decision.outcome, ActionGovernanceOutcome.INDETERMINATE)
        constraints = _encode(decision.constraints, _KNOWN_C)
        obligations = _encode(decision.obligations, _KNOWN_O)
        payload = json.dumps({"o": outcome.value, "c": sorted(constraints),
                              "ob": sorted(obligations), "t": decision.trace_id,
                              "r": sorted(decision.reason_codes)}, sort_keys=True)
        fp = hashlib.sha256(payload.encode()).hexdigest()
        return ActionGovernanceResult(
            outcome=outcome, constraints=constraints, obligations=obligations,
            reason_codes=decision.reason_codes, provider_trace_id=decision.trace_id,
            fingerprint=fp)

    def health(self) -> ProviderHealth:
        base = super().health()
        ok = False
        try:
            ok = self._engine.available
        except Exception:  # noqa: BLE001
            ok = False
        state = base.state
        if base.healthy and not ok:
            state = ProviderLifecycleState.DEGRADED
        return ProviderHealth(state=state, healthy=base.healthy and ok,
                              detail=f"{base.detail}|policy:{self._engine.policy_version}")


assert issubclass(BaselineActionProvider, BaseProvider)
