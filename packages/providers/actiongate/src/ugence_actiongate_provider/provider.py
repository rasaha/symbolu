"""ActionGateProvider — a real ActionGovernanceProvider on the DGM framework.

Wraps the ActionGate core (in-process or remote client) and implements the
neutral ``ActionGovernanceProvider`` contract by mapping requests/results and
translating errors. ActionGate governs **authorization only** — this provider has
no dispatch/observe surface and never executes.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional

from governance_providers.api import (
    ActionGovernanceProvider,
    ActionGovernanceRequest,
    ActionGovernanceResult,
    BaseProvider,
    ProviderCapabilities,
    ProviderCompatibility,
    ProviderDescriptor,
    ProviderError,
    ProviderHealth,
    ProviderKind,
    ProviderLifecycleState,
)

from .client import ActionGateClient
from .errors import translate_error
from .mapping import MAPPING_VERSION, map_request, map_result
from .observability import ActionGateInvocationLog, ActionGateInvocationRecord
from .version import __version__ as PROVIDER_VERSION

_CONTRACT_VERSION = "1.0.0"
_FEATURES = frozenset({
    "authorize", "constraints", "obligations", "expiry", "authority_basis",
    "reason_codes", "in_process", "remote",
})


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


class ActionGateProvider(BaseProvider):
    """An ActionGovernanceProvider backed by the ActionGate engine."""

    def __init__(self, client: ActionGateClient, *, provider_id: str = "actiongate",
                 default: bool = True, clock=_utc_now,
                 invocation_log: Optional[ActionGateInvocationLog] = None) -> None:
        descriptor = ProviderDescriptor(
            provider_id=provider_id, kind=ProviderKind.ACTION_GOVERNANCE,
            implementation_version=PROVIDER_VERSION,
            compatibility=ProviderCompatibility(
                contract_version=_CONTRACT_VERSION, compatible_kernel_majors=frozenset({"1"}),
                config_schema_version="1"),
            capabilities=ProviderCapabilities(
                kind=ProviderKind.ACTION_GOVERNANCE, features=_FEATURES, deterministic=True),
            factory=lambda: ActionGateProvider(client, provider_id=provider_id, default=default,
                                               clock=clock),
            vendor="ActionGate", default=default,
            metadata={"mode": getattr(client, "mode", "in_process")})
        super().__init__(descriptor)
        self._client = client
        self._clock = clock
        self._log = invocation_log

    # --- ActionGovernanceProvider -----------------------------------------

    def authorize(self, request: ActionGovernanceRequest) -> ActionGovernanceResult:
        native = map_request(request)
        try:
            decision = self._client.evaluate(native)
        except Exception as exc:  # translate — no native exception may escape
            provider_error = translate_error(exc)
            self._record(completed=False, error=provider_error)
            raise provider_error
        result = map_result(decision, now=self._clock())
        self._record(completed=True, outcome=result.outcome.value, trace=result.provider_trace_id)
        return result

    # --- health & lifecycle -----------------------------------------------

    def health(self) -> ProviderHealth:
        base = super().health()
        engine_ok = False
        detail = base.detail
        try:
            engine_ok = self._client.ping()
            detail = f"{base.detail}|policy:{self._client.policy_version()}"
        except Exception:  # noqa: BLE001 - health must never raise
            engine_ok = False
        state = base.state
        if base.healthy and not engine_ok:
            state = ProviderLifecycleState.DEGRADED
        return ProviderHealth(state=state, healthy=base.healthy and engine_ok, detail=detail)

    # --- observability -----------------------------------------------------

    def _record(self, *, completed: bool, outcome: str = "", trace: str = "",
                error: Optional[ProviderError] = None) -> None:
        if self._log is None:
            return
        d = self.descriptor()
        self._log.append(ActionGateInvocationRecord(
            provider_id=d.provider_id, provider_version=d.implementation_version,
            mapping_version=MAPPING_VERSION, mode=d.metadata.get("mode", ""),
            compatible=str(1) in d.compatibility.compatible_kernel_majors,
            completed=completed, outcome=outcome, trace_id=trace,
            policy_version=_safe_policy_version(self._client),
            error_class=type(error).__name__ if error else None,
            failure_class=getattr(error, "failure_class", None).value if error else None))


def _safe_policy_version(client: ActionGateClient) -> str:
    try:
        return client.policy_version()
    except Exception:  # noqa: BLE001
        return ""


# structural self-check: an ActionGateProvider is an ActionGovernanceProvider
assert issubclass(ActionGateProvider, BaseProvider)
